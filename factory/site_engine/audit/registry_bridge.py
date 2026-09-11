#!/usr/bin/env python3
"""Мост: outbox Site Registry → Audit Ledger. Первый реальный производитель.

Реестр остаётся источником истины о сайтах. Журнал хранит ФАКТ о том, что
событие реестра случилось, и не становится вторым реестром: он не отвечает на
вопрос «какие сейчас сайты», он отвечает «что происходило».

Идемпотентность — по ключу (producer_service, idempotency_key), где ключом
служит `event_id` реестра. Повторный replay всей ленты не создаёт дублей:
это проверяется, а не предполагается.
"""
from __future__ import annotations

import argparse, errno, fcntl, json, os, signal, sqlite3, sys, time
from pathlib import Path

from . import ledger_store as store

РЕЕСТР = os.environ.get("REGISTRY_DB",
                        "/srv/site-factory/registry-core/registry.sqlite3")
ЖУРНАЛ = os.environ.get("AUDIT_LEDGER_DB",
                        "/srv/site-factory/audit-ledger/audit_ledger.sqlite3")
ПОТРЕБИТЕЛЬ = "registry-outbox"
ПОПЫТОК = 3

#: Как часто заглядывать в outbox реестра и как часто сверяться целиком.
ИНТЕРВАЛ_ОПРОСА = float(os.environ.get("BRIDGE_POLL_SECONDS", "5"))
ИНТЕРВАЛ_СВЕРКИ = float(os.environ.get("BRIDGE_RECONCILE_SECONDS", "300"))

#: Замок единственного экземпляра. Два моста, читающие один outbox, спорили бы
#: за курсор: каждый двигал бы его за себя, и часть событий осталась бы
#: непрочитанной при внешне исправной работе обоих.
ЗАМОК = Path(os.environ.get(
    "BRIDGE_LOCK", "/srv/site-factory/audit-ledger/registry-bridge.lock"))


class УжеЗапущен(RuntimeError):
    """Второй экземпляр моста при живом первом."""


def занять_замок():
    """Взять эксклюзивный замок или отказаться запускаться."""
    ЗАМОК.parent.mkdir(parents=True, exist_ok=True)
    ф = ЗАМОК.open("a+")
    try:
        fcntl.flock(ф.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError as e:
        ф.close()
        if e.errno in (errno.EAGAIN, errno.EACCES):
            raise УжеЗапущен(f"мост уже работает, замок {ЗАМОК} занят") from e
        raise
    ф.seek(0); ф.truncate()
    ф.write(str(os.getpid())); ф.flush()
    return ф


def _курсор(соед) -> int:
    р = соед.execute("SELECT position FROM consumer_cursor WHERE consumer=?",
                     (ПОТРЕБИТЕЛЬ,)).fetchone()
    return int(р["position"]) if р else 0


def _сохранить_курсор(соед, позиция: int) -> None:
    соед.execute(
        "INSERT INTO consumer_cursor(consumer, position, updated_at) "
        "VALUES(?,?,?) ON CONFLICT(consumer) DO UPDATE SET "
        "position=excluded.position, updated_at=excluded.updated_at",
        (ПОТРЕБИТЕЛЬ, str(позиция), store.сейчас()))


def _в_dlq(соед, ссылка, код, причина, попытки, нагрузка):
    т = store.сейчас()
    соед.execute(
        "INSERT INTO ledger_dlq(consumer, source_ref, error_code, reason, "
        "attempts, first_at, last_at, payload) VALUES(?,?,?,?,?,?,?,?)",
        (ПОТРЕБИТЕЛЬ, str(ссылка), код, причина[:400], попытки, т, т,
         json.dumps(нагрузка, ensure_ascii=False)[:2000]))


def перенести(*, предел: int = 5000) -> dict:
    ж = store.открыть(ЖУРНАЛ)
    r = sqlite3.connect(f"file:{РЕЕСТР}?mode=ro", uri=True)
    r.row_factory = sqlite3.Row
    сайты = {x[0] for x in r.execute("SELECT site_id FROM site")}
    курсор = _курсор(ж)
    добавлено = повторов = отказов = 0
    последний = курсор
    try:
        for е in r.execute("SELECT * FROM outbox WHERE seq > ? ORDER BY seq "
                           "LIMIT ?", (курсор, предел)):
            нагрузка = {
                "event_type": f"registry.{е['event_type']}",
                "phase": "SUCCEEDED", "result": "SUCCESS",
                "scope": "SITE", "site_id": е["site_id"],
                "environment": "control-plane",
                "resource_type": "site", "resource_id": е["site_id"],
                "resource_owner": "architect",
                "correlation_id": е["correlation_id"],
                "causation_id": е["causation_id"],
                # Ключ идемпотентности — event_id реестра. Один и тот же факт
                # не станет двумя записями, сколько раз ленту ни перечитай.
                "idempotency_key": е["event_id"],
                "occurred_at": е["occurred_at"],
                "action_id": е["correlation_id"],
                "summary": (f"реестр: {е['event_type']} для {е['site_id']}, "
                            f"aggregate_version {е['aggregate_version']}, "
                            f"registry_version {е['registry_version']}"),
                "run_id": f"registry-seq-{е['seq']}",
            }
            попытка, задержка = 0, 0.05
            while True:
                попытка += 1
                try:
                    итог = store.append(
                        ж, нагрузка, producer_service="registry",
                        actor_id="service:registry", actor_type="SERVICE",
                        authority="EXECUTE",
                        известные_сайты=сайты or None)
                    добавлено += 0 if итог["idempotent_replay"] else 1
                    повторов += 1 if итог["idempotent_replay"] else 0
                    break
                except store.LedgerError as ош:
                    if попытка >= ПОПЫТОК or ош.error_code in (
                            "SITE_ID_UNKNOWN", "IDEMPOTENCY_CONFLICT",
                            "SECRET_IN_PAYLOAD"):
                        # Неповторяемое уходит в DLQ с кодом и причиной:
                        # молчаливый пропуск превратил бы потерю в «успех».
                        _в_dlq(ж, е["seq"], ош.error_code, ош.detail,
                               попытка, нагрузка)
                        отказов += 1
                        break
                    time.sleep(задержка)
                    задержка = min(задержка * 2, 1.0)
            последний = е["seq"]
            _сохранить_курсор(ж, последний)
    finally:
        r.close()
    backlog = ж.execute("SELECT count(*) c FROM ledger_outbox "
                        "WHERE published_at IS NULL").fetchone()["c"]
    dlq = ж.execute("SELECT count(*) c FROM ledger_dlq").fetchone()["c"]
    ж.close()
    return {"appended": добавлено, "idempotent_replays": повторов,
            "failed": отказов, "cursor": последний,
            "ledger_outbox_backlog": backlog, "dlq": dlq}


def сверка() -> dict:
    """Сколько событий реестра ожидается и сколько дошло. Пропуски — по именам."""
    r = sqlite3.connect(f"file:{РЕЕСТР}?mode=ro", uri=True)
    ожидаемые = {x[0] for x in r.execute("SELECT event_id FROM outbox")}
    r.close()
    ж = sqlite3.connect(f"file:{ЖУРНАЛ}?mode=ro", uri=True)
    дошли = [x[0] for x in ж.execute(
        "SELECT idempotency_key FROM ledger_event WHERE producer_service='registry'")]
    ж.close()
    множество = set(дошли)
    return {"expected": len(ожидаемые), "in_ledger": len(множество),
            "missing": sorted(ожидаемые - множество),
            "missing_count": len(ожидаемые - множество),
            "duplicates": len(дошли) - len(множество),
            "extra": sorted(множество - ожидаемые),
            "verdict": "PASS" if (ожидаемые == множество
                                  and len(дошли) == len(множество)) else "FAIL"}


def служить() -> int:
    """Постоянный режим: опрос, перенос, периодическая сверка.

    Завершение по SIGTERM — мягкое: текущий проход доводится до конца, и
    только потом процесс выходит. Обрыв на середине прохода не потерял бы
    событий (курсор двигается после каждого), но оставил бы в логе обрубок,
    по которому потом не понять, успел проход отработать или нет.
    """
    замок = занять_замок()
    остановиться = {"да": False}

    def по_сигналу(номер, _кадр):
        остановиться["да"] = True
        print(f"  сигнал {номер}: завершаю после текущего прохода", flush=True)

    signal.signal(signal.SIGTERM, по_сигналу)
    signal.signal(signal.SIGINT, по_сигналу)

    сообщить_готовность()
    последняя_сверка = 0.0
    print(f"  мост запущен, pid {os.getpid()}, опрос {ИНТЕРВАЛ_ОПРОСА}с",
          flush=True)
    try:
        while not остановиться["да"]:
            try:
                итог = перенести()
                if итог["appended"] or итог["failed"]:
                    print("  перенос: " + json.dumps(итог, ensure_ascii=False),
                          flush=True)
            except Exception as ош:  # noqa: BLE001
                # Мост обязан пережить недоступность любой из двух баз:
                # падение здесь означало бы, что перезапуск службы зависит от
                # чужой готовности.
                print(f"  проход не удался: {type(ош).__name__}: {ош}",
                      flush=True)
            сейчас = time.monotonic()
            if сейчас - последняя_сверка >= ИНТЕРВАЛ_СВЕРКИ:
                последняя_сверка = сейчас
                try:
                    с = сверка()
                    if с["verdict"] != "PASS":
                        print("  СВЕРКА НЕ СОШЛАСЬ: "
                              + json.dumps(с, ensure_ascii=False), flush=True)
                except Exception as ош:  # noqa: BLE001
                    print(f"  сверка не выполнена: {ош}", flush=True)
            for _ in range(int(max(ИНТЕРВАЛ_ОПРОСА, 0.1) * 10)):
                if остановиться["да"]:
                    break
                time.sleep(0.1)
    finally:
        замок.close()
    print("  мост остановлен", flush=True)
    return 0


def сообщить_готовность() -> None:
    """Сообщить systemd о готовности, если запущены под Type=notify."""
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


def main() -> int:
    ap = argparse.ArgumentParser(description="мост Registry → Audit Ledger")
    ap.add_argument("режим", nargs="?", default="once",
                    choices=["once", "serve", "reconcile"])
    a = ap.parse_args()
    if a.режим == "serve":
        try:
            return служить()
        except УжеЗапущен as ош:
            print(f"  {ош}", flush=True)
            return 3
    if a.режим == "reconcile":
        с = сверка()
        print(json.dumps(с, ensure_ascii=False))
        return 0 if с["verdict"] == "PASS" else 1
    print(" перенос:", json.dumps(перенести(), ensure_ascii=False))
    с = сверка()
    print(" сверка: expected=%d in_ledger=%d missing=%d duplicates=%d -> %s"
          % (с["expected"], с["in_ledger"], с["missing_count"],
             с["duplicates"], с["verdict"]))
    return 0 if с["verdict"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
