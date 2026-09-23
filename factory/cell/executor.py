"""Привилегированный исполнитель заявок: закрытый набор операций, журнал, замок.

Что он делает и чего не делает
------------------------------

Делает: берёт заявку из очереди, проверяет её по реестру и по GitHub, выполняет
одну из четырёх операций и записывает результат. Между «намерен» и «сделал»
всегда есть запись на диске — после гибели процесса или перезагрузки хоста
восстановление начинается со сверки журнала с фактом, а не с догадки.

Не делает: не выполняет путей, скриптов и команд из заявки. Их там нет как
понятия — схема заявки закрыта. Пути, юниты, порты и учётные записи берутся из
реестра, а артефакт собирается из названного коммита и сверяется по digest.

Почему замок с владельцем, а не с возрастом
-------------------------------------------

Старый замок направления лежал без pid, и решение «протух или нет» пришлось
принимать человеку. Возраст ничего не доказывает: долгая выкладка живёт часами,
а мёртвый процесс не становится живым от того, что замок свежий. Поэтому в
замке записан владелец — pid и время старта процесса — и живость проверяется,
а не предполагается. Совпадение одного pid недостаточно: номера переиспользуются,
и время старта отличает нового владельца от призрака.
"""
from __future__ import annotations

import contextlib
import json
import os
import subprocess
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from factory.cell import admin_exec, queue, registry, runtime


class ExecutorError(Exception):
    """Операция не выполнена. Витрина не тронута либо возвращена."""


def _сейчас() -> str:
    return datetime.now(timezone.utc).isoformat()


def _время_старта(pid: int) -> str:
    """Отметка старта процесса из /proc. Отличает живого владельца от тёзки."""
    try:
        поля = Path(f"/proc/{pid}/stat").read_text(encoding="utf-8").rsplit(")", 1)[1].split()
        return поля[19]  # starttime в тиках с загрузки системы
    except (OSError, IndexError):
        return ""


@dataclass
class Замок:
    путь: Path
    владелец: dict[str, Any]

    def снять(self) -> None:
        with contextlib.suppress(OSError):
            self.путь.unlink()


def взять_замок(site_id: str, *, база: Path, операция: str) -> Замок:
    """Живая блокировка на сайт. Возраст не является разрешением на захват."""
    каталог = база / "locks"
    каталог.mkdir(parents=True, exist_ok=True)
    файл = каталог / f"{site_id}.json"
    мой = {"pid": os.getpid(), "starttime": _время_старта(os.getpid()),
           "site": site_id, "operation": операция, "at": _сейчас(),
           "host": os.uname().nodename}

    if файл.is_file():
        try:
            чужой = json.loads(файл.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            raise ExecutorError(
                f"замок {файл} нечитаем. Испорченный замок хуже отсутствующего: "
                "он молча разрешает всё. Нужно решение человека") from None
        pid = чужой.get("pid")
        живой = False
        if isinstance(pid, int) and pid > 0:
            try:
                os.kill(pid, 0)
                живой = _время_старта(pid) == (чужой.get("starttime") or "")
            except OSError:
                живой = False
        if живой:
            raise ExecutorError(
                f"{site_id}: операцию {чужой.get('operation')} держит живой процесс "
                f"{pid} с {чужой.get('at')}. Ждём его, а не отнимаем")
        if not чужой.get("starttime"):
            raise ExecutorError(
                f"{site_id}: в замке {файл} нет отметки старта владельца. "
                "Снимать такой замок автоматически нельзя — возраст не "
                "доказывает смерть процесса")
        # Владелец мёртв и это доказано: pid не отвечает либо это другой процесс.
        файл.unlink()

    queue.записать_атомарно(файл, мой)
    return Замок(путь=файл, владелец=мой)


def проверить_заявку(заявка: queue.Заявка) -> dict[str, Any]:
    """Всё, что можно проверить до единой мутации."""
    try:
        cell = registry.resolve(заявка.site_id)
    except registry.RegistryError as exc:
        raise ExecutorError(
            f"{заявка.site_id}: сайта нет в реестре ячеек — исполнитель работает "
            "только с зарегистрированными сайтами") from exc
    remote = registry.require_own_repo(cell)

    # Имя репозитория из заявки — не источник доверия, а повод отказать при
    # расхождении: доверенным остаётся то, что записано в реестре.
    if заявка.repo and заявка.repo.split("/")[-1].removesuffix(".git") not in remote:
        raise ExecutorError(
            f"заявка называет репозиторий {заявка.repo}, а в реестре у "
            f"{заявка.site_id} записан {remote}")

    размещение = runtime.размещение(заявка.site_id)
    if размещение.previous_unit and размещение.unit == размещение.previous_unit:
        raise ExecutorError(
            f"{заявка.site_id}: реестр называет один и тот же юнит текущим и "
            "прежним; исполнять по такому описанию нельзя")
    return {"remote": remote, "runtime": размещение.as_dict()}


def проверить_ci(заявка: queue.Заявка, *, remote: str) -> dict[str, Any]:
    """Прогон CI обязан относиться именно к этому коммиту.

    Один хеш файла не доказывает происхождение: артефакт с тем же digest можно
    собрать где угодно. Доверие даёт связка «этот репозиторий → этот коммит →
    этот успешный прогон», и проверяется она у GitHub, а не по словам заявки.
    """
    if not заявка.ci_run:
        return {"checked": False, "reason": "прогон не назван в заявке"}
    проект = "/".join(remote.rstrip("/").split("/")[-2:]).removesuffix(".git")
    готово = subprocess.run(
        ["gh", "run", "view", заявка.ci_run, "-R", проект,
         "--json", "headSha,conclusion,workflowName"],
        capture_output=True, text=True)
    if готово.returncode != 0:
        return {"checked": False,
                "reason": f"gh не ответил: {готово.stderr.strip()[:200]}"}
    данные = json.loads(готово.stdout or "{}")
    if данные.get("conclusion") != "success":
        raise ExecutorError(
            f"прогон {заявка.ci_run} завершился как {данные.get('conclusion')!r}; "
            "выкладывается только проверенный выпуск")
    if (данные.get("headSha") or "") != заявка.commit:
        raise ExecutorError(
            f"прогон {заявка.ci_run} относится к коммиту "
            f"{(данные.get('headSha') or '')[:12]}, а заявка — к {заявка.commit[:12]}. "
            "Зелёный CI на другой ветке ничего не доказывает об этом выпуске")
    return {"checked": True, "workflow": данные.get("workflowName"),
            "conclusion": данные.get("conclusion")}


def выполнить(заявка: queue.Заявка, *, база: Path, dry_run: bool = True) -> dict[str, Any]:
    """Одна операция целиком, с журналом переходов."""
    файл = база / "requests" / f"{заявка.request_id}.json"
    результат: dict[str, Any] = {"request_id": заявка.request_id,
                                 "site_id": заявка.site_id,
                                 "operation": заявка.operation,
                                 "commit": заявка.commit,
                                 "dry_run": dry_run,
                                 "started_at": _сейчас()}
    замок = None
    try:
        проверено = проверить_заявку(заявка)
        if файл.is_file():
            queue.отметить(файл, "validated", {"remote": проверено["remote"]})
        результат["runtime"] = проверено["runtime"]

        результат["ci"] = проверить_ci(заявка, remote=проверено["remote"])

        замок = взять_замок(заявка.site_id, база=база, операция=заявка.operation)
        результат["lock"] = замок.владелец

        if заявка.operation == "activate":
            итог = admin_exec.активировать(
                заявка.site_id, commit=заявка.commit, dry_run=dry_run,
                expect_digest=заявка.digest)
            результат["outcome"] = итог
            этап = "live_verified" if итог.get("status") == "activated" else (
                "failed" if итог.get("status") in ("failed", "dry-run-failed") else "switched")
        elif заявка.operation == "deliver":
            from factory.cell import delivery
            итог = delivery.доставить(заявка.site_id, dry_run=dry_run)
            результат["outcome"] = итог.as_dict()
            этап = "live_verified" if итог.writable else "failed"
        else:
            raise ExecutorError(
                f"операция {заявка.operation} ещё не реализована исполнителем; "
                "объявлять её выполненной нельзя")

        if файл.is_file():
            queue.отметить(файл, этап, {"dry_run": dry_run})
        результат["status"] = "ok" if этап != "failed" else "failed"
    except (ExecutorError, admin_exec.ExecutorRefused, registry.RegistryError) as exc:
        результат["status"] = "rejected"
        результат["error"] = str(exc)
        if файл.is_file():
            queue.отметить(файл, "failed", {"error": str(exc)[:500]})
    finally:
        if замок is not None:
            замок.снять()
        результат["finished_at"] = _сейчас()
    return результат


def обслужить_очередь(*, база: Path | None = None, dry_run: bool = True,
                      предел: int = 10) -> list[dict[str, Any]]:
    """Разобрать накопившиеся заявки. Порядок — по времени появления."""
    корень = база or queue.БАЗА
    очередь = корень / "requests"
    if not очередь.is_dir():
        return []
    итоги = []
    for файл in sorted(очередь.glob("*.json"), key=lambda p: p.stat().st_mtime)[:предел]:
        try:
            заявка = queue.разобрать(json.loads(файл.read_text(encoding="utf-8")))
        except (queue.RequestRejected, ValueError) as exc:
            итоги.append({"request_id": файл.stem, "status": "rejected",
                          "error": str(exc)})
            queue.записать_атомарно(корень / "results" / файл.name,
                                    итоги[-1])
            файл.unlink()
            continue
        итог = выполнить(заявка, база=корень, dry_run=dry_run)
        queue.записать_атомарно(корень / "results" / файл.name, итог)
        # Заявка уходит из очереди только после записи результата: обратный
        # порядок терял бы операцию при гибели процесса между двумя шагами.
        файл.unlink()
        итоги.append(итог)
    return итоги


def ждать(*, база: Path | None = None, интервал: float = 5.0,
          dry_run: bool = True, циклов: int = 0) -> None:
    """Цикл службы. `циклов=0` — до остановки."""
    сделано = 0
    while циклов == 0 or сделано < циклов:
        обслужить_очередь(база=база, dry_run=dry_run)
        сделано += 1
        if циклов and сделано >= циклов:
            break
        time.sleep(интервал)
