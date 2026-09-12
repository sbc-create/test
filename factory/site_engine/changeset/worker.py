#!/usr/bin/env python3
"""Рабочий процесс контура изменений.

Делает ровно четыре вещи и ничего сверх:

* сливает исходящий ящик в журнал аудита;
* доводит до конца наборы, прерванные на середине;
* помечает устаревшие планы и истёкшие одобрения;
* отпускает просроченные аренды.

Один экземпляр на область замка. Два процесса, доводящих до конца один и тот
же набор, применили бы изменение дважды — от этого защищает не договорённость,
а замок файла и маркер ограждения.
"""
from __future__ import annotations

import argparse
import errno
import fcntl
import json
import os
import signal
import sys
import time
from pathlib import Path

from . import audit_bridge as AB
from . import engine as E
from . import model as M
from . import policy as POL
from . import store as S
from .planner import обнаружить_дрейф
from .registry_client import RegistryClient, RegistryUnavailable

ИНТЕРВАЛ = float(os.environ.get("CHANGESET_POLL_SECONDS", "5"))
ЗАМОК = Path(os.environ.get(
    "CHANGESET_WORKER_LOCK",
    "/srv/site-factory/changeset-store/changeset-worker.lock"))
WORKER_ID = os.environ.get("CHANGESET_WORKER_ID") or f"worker-{os.getpid()}"

#: Сколько раз подряд позволено сорваться, прежде чем прерыватель разомкнётся
#: и набор уйдёт на разбор человеку. Бесконечные повторы превращают одну
#: поломку в непрерывный поток одинаковых отказов.
ПРЕДЕЛ_ПОПЫТОК = 3


class УжеЗапущен(RuntimeError):
    pass


def занять_замок():
    ЗАМОК.parent.mkdir(parents=True, exist_ok=True)
    ф = ЗАМОК.open("a+")
    try:
        fcntl.flock(ф.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError as e:
        ф.close()
        if e.errno in (errno.EAGAIN, errno.EACCES):
            raise УжеЗапущен(f"процесс уже работает, замок {ЗАМОК} занят") from e
        raise
    ф.seek(0); ф.truncate(); ф.write(str(os.getpid())); ф.flush()
    return ф


def сообщить_готовность() -> None:
    адрес = os.environ.get("NOTIFY_SOCKET")
    if not адрес:
        return
    import socket
    if адрес.startswith("@"):
        адрес = "\0" + адрес[1:]
    с = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
    try:
        с.connect(адрес)
        с.sendall(b"READY=1")
    except OSError:
        pass
    finally:
        с.close()


# --- отдельные обязанности ---------------------------------------------------

def слить_ящик(соед) -> dict:
    return AB.опубликовать(соед)


def отпустить_аренды(соед) -> int:
    """Аренда, по которой давно нет отметок, освобождается.

    Маркер при этом НЕ сбрасывается: следующий исполнитель получит больший
    номер, и вернувшийся прежний будет отвергнут.
    """
    сейчас_м = time.monotonic()
    with соед:
        n = соед.execute("DELETE FROM changeset_lease WHERE expires_at < ?",
                         (сейчас_м,)).rowcount
    return n


def пометить_истёкшие(соед) -> int:
    """Одобрение с истёкшим сроком не применяется и не ждёт вечно."""
    т = S.сейчас()
    помечено = 0
    for r in соед.execute(
            "SELECT changeset_id, status, expires_at FROM changeset "
            "WHERE status IN (?, ?) AND expires_at IS NOT NULL AND expires_at < ?",
            (M.AWAITING_APPROVAL, M.APPROVED, т)):
        действие = ("expire" if r["status"] == M.AWAITING_APPROVAL
                    else "expire_approved")
        try:
            S.применить_переход(соед, r["changeset_id"], действие,
                                actor_id=f"service:{WORKER_ID}",
                                служба="control-plane", роль=M.EXECUTOR,
                                reason="истёк срок")
            помечено += 1
        except S.ChangeSetError:
            continue
    return помечено


def пометить_устаревшие(соед, *, реестр: RegistryClient) -> int:
    """Одобренный план сверяется с миром до того, как его применят."""
    помечено = 0
    for r in соед.execute("SELECT changeset_id FROM changeset WHERE status=?",
                          (M.APPROVED,)):
        набор = S.получить(соед, r["changeset_id"])
        if not набор or not набор.get("dry_run_result"):
            continue
        try:
            дрейф = обнаружить_дрейф(набор, реестр=реестр)
        except (S.ChangeSetError, RegistryUnavailable):
            continue
        if дрейф["stale"]:
            try:
                S.применить_переход(
                    соед, r["changeset_id"], "mark_stale_approved",
                    actor_id=f"service:{WORKER_ID}", служба="control-plane",
                    роль=M.EXECUTOR, reason=f"дрейф: {дрейф['drift']}",
                    поля={"failure_reason": S.канон(дрейф["drift"])})
                помечено += 1
            except S.ChangeSetError:
                continue
    return помечено


def восстановить_прерванные(соед) -> int:
    """Набор, застрявший в APPLYING или VERIFYING, доводится до конца.

    Возобновление идёт с последней ПОДТВЕРЖДЁННОЙ стадии: состояние целей
    записано, поэтому повторный проход не применяет заново то, что уже
    применено, — адаптер отвечает идемпотентным повтором.
    """
    восстановлено = 0
    for r in соед.execute("SELECT changeset_id, status FROM changeset "
                          "WHERE status IN (?, ?, ?)",
                          (M.APPLYING, M.VERIFYING, M.ROLLING_BACK)):
        cid = r["changeset_id"]
        набор = S.получить(соед, cid)
        if not набор:
            continue
        попыток = max((t["attempts"] for t in набор["targets"]), default=0)
        if попыток >= ПРЕДЕЛ_ПОПЫТОК:
            try:
                if набор["status"] != M.ROLLBACK_FAILED:
                    S.применить_переход(
                        соед, cid, "rollback_fail",
                        actor_id=f"service:{WORKER_ID}", служба="control-plane",
                        роль=M.EXECUTOR, fencing_token=_маркер(соед, cid),
                        reason="исчерпан предел повторов")
                S.применить_переход(
                    соед, cid, "escalate", actor_id=f"service:{WORKER_ID}",
                    служба="control-plane", роль=M.EXECUTOR,
                    reason="прерыватель разомкнут")
            except S.ChangeSetError:
                pass
            continue
        try:
            аренда = S.взять_аренду(соед, cid, WORKER_ID)
        except S.ChangeSetError:
            # Аренда у живого исполнителя — набор ведёт он. Просроченные к
            # этому моменту уже освобождены отдельным шагом прохода.
            continue
        дв = E.Engine(соед)
        try:
            if набор["status"] == M.ROLLING_BACK:
                дв.откатить(cid, actor_id=f"service:{WORKER_ID}",
                            служба="control-plane",
                            fencing_token=аренда["fencing_token"])
            else:
                дв.применить(cid, actor_id=f"service:{WORKER_ID}",
                             служба="control-plane",
                             fencing_token=аренда["fencing_token"])
            восстановлено += 1
        except S.ChangeSetError:
            continue
    return восстановлено


def _маркер(соед, cid: str) -> int | None:
    р = соед.execute("SELECT fencing_token FROM changeset_lease "
                     "WHERE changeset_id=?", (cid,)).fetchone()
    return р["fencing_token"] if р else None


# --- цикл --------------------------------------------------------------------

def проход(соед, *, реестр: RegistryClient) -> dict:
    итог = {"published": 0, "expired": 0, "stale": 0, "resumed": 0,
            "leases_released": 0, "backlog": 0, "dlq": 0}
    я = слить_ящик(соед)
    итог.update(published=я["published"], backlog=я["backlog"], dlq=я["dlq"])
    итог["leases_released"] = отпустить_аренды(соед)
    итог["expired"] = пометить_истёкшие(соед)
    итог["stale"] = пометить_устаревшие(соед, реестр=реестр)
    итог["resumed"] = восстановить_прерванные(соед)
    return итог


def служить() -> int:
    замок = занять_замок()
    стоп = {"да": False}

    def по_сигналу(номер, _кадр):
        стоп["да"] = True
        print(f"  сигнал {номер}: завершаю после текущего прохода", flush=True)

    signal.signal(signal.SIGTERM, по_сигналу)
    signal.signal(signal.SIGINT, по_сигналу)
    соед = S.открыть()
    реестр = RegistryClient()
    сообщить_готовность()
    print(f"  контур изменений запущен, pid {os.getpid()}, "
          f"опрос {ИНТЕРВАЛ}с, автономное production-применение "
          f"{'ВКЛЮЧЕНО' if POL.AUTONOMOUS_PRODUCTION_APPLY else 'выключено'}",
          flush=True)
    try:
        while not стоп["да"]:
            try:
                и = проход(соед, реестр=реестр)
                если_есть = {k: v for k, v in и.items() if v}
                if если_есть:
                    print("  проход: " + json.dumps(если_есть, ensure_ascii=False),
                          flush=True)
            except Exception as ош:  # noqa: BLE001
                # Процесс обязан пережить недоступность журнала и реестра:
                # падение здесь означало бы, что восстановление контура
                # зависит от чужой готовности.
                print(f"  проход не удался: {type(ош).__name__}: {ош}", flush=True)
            for _ in range(int(max(ИНТЕРВАЛ, 0.1) * 10)):
                if стоп["да"]:
                    break
                time.sleep(0.1)
    finally:
        соед.close()
        замок.close()
    print("  контур изменений остановлен", flush=True)
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="рабочий процесс ChangeSet")
    ap.add_argument("режим", nargs="?", default="serve",
                    choices=["serve", "once", "status"])
    a = ap.parse_args(argv)
    if a.режим == "serve":
        try:
            return служить()
        except УжеЗапущен as ош:
            print(f"  {ош}", flush=True)
            return 3
    соед = S.открыть()
    try:
        if a.режим == "once":
            print(json.dumps(проход(соед, реестр=RegistryClient()),
                             ensure_ascii=False))
            return 0
        по_состояниям = {r["status"]: r["n"] for r in соед.execute(
            "SELECT status, count(*) n FROM changeset GROUP BY status")}
        backlog = соед.execute("SELECT count(*) c FROM changeset_outbox "
                               "WHERE published_at IS NULL").fetchone()["c"]
        print(json.dumps({"by_status": по_состояниям, "outbox_backlog": backlog,
                          "autonomous_production_apply":
                              POL.AUTONOMOUS_PRODUCTION_APPLY},
                         ensure_ascii=False))
        return 0
    finally:
        соед.close()


if __name__ == "__main__":
    sys.exit(main())
