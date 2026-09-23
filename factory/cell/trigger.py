"""Релизный триггер: сервер сам спрашивает GitHub, а не GitHub стучится на сервер.

Почему опрос, а не webhook
--------------------------

Чтобы CI положил заявку на VPS, ему нужен входящий доступ и учётные данные в
секретах workflow. Это ровно та поверхность, которой в задании велено избегать:
ветка эксперимента или PR из форка получили бы ключ к боевому серверу.

Опрос переворачивает направление доверия. Сервер сам спрашивает GitHub: «какой
последний УСПЕШНЫЙ прогон на разрешённой ветке этого репозитория». Наружу не
открывается ничего, в CI не кладётся ни одного секрета, а ветки экспериментов
не попадают в выборку по построению — они не разрешённая ветка.

Что триггер делает и чего не делает
-----------------------------------

Делает: находит коммит, собирает из него артефакт (сборка воспроизводима,
поэтому байты те же, что проверил CI), кладёт заявку с digest и номером прогона.

Не делает: ничего не переключает. Заявку разбирает привилегированный
исполнитель, и он проверяет её заново — связку «репозиторий → коммит → прогон»
и digest. Триггер ошибиться может; пройти мимо проверки — нет.
"""
from __future__ import annotations

import json
import re
import ssl
import subprocess
import urllib.request
from pathlib import Path
from typing import Any

from factory.cell import admin_exec, queue, registry

#: Ветки, с которых выпуск разрешён. Эксперименты и форки сюда не попадают.
РАЗРЕШЁННЫЕ_ВЕТКИ = ("main", "claude/extract-*", "release/*")


class TriggerError(Exception):
    """Триггер не смог определить выпуск. Ничего не подано."""


def _подходит(ref: str) -> bool:
    from fnmatch import fnmatch
    return any(fnmatch(ref, шаблон) for шаблон in РАЗРЕШЁННЫЕ_ВЕТКИ)


def проект(remote: str) -> str:
    return "/".join(remote.rstrip("/").split("/")[-2:]).removesuffix(".git")


def последний_успешный(remote: str) -> dict[str, Any]:
    """Последний успешный прогон на разрешённой ветке."""
    готово = subprocess.run(
        ["gh", "run", "list", "-R", проект(remote), "--limit", "20",
         "--json", "headSha,headBranch,conclusion,databaseId,workflowName"],
        capture_output=True, text=True)
    if готово.returncode != 0:
        raise TriggerError(f"gh не ответил по {проект(remote)}: "
                           f"{готово.stderr.strip()[:200]}")
    for прогон in json.loads(готово.stdout or "[]"):
        if прогон.get("conclusion") != "success":
            continue
        if not _подходит(прогон.get("headBranch") or ""):
            continue
        return прогон
    raise TriggerError(
        f"{проект(remote)}: успешного прогона на разрешённой ветке нет. "
        f"Разрешены {list(РАЗРЕШЁННЫЕ_ВЕТКИ)}")


def живой_коммит(cell: registry.Cell) -> str:
    """Коммит, который сайт исполняет ПРЯМО СЕЙЧАС.

    Берётся из публичного build-id (`<коммит>-<site_id>`), а не из записи в
    реестре: запись отражает намерение, страница — действительность. Разошлись
    они хотя бы раз, и решение о выпуске должно опираться на вторую.
    """
    домен = cell.domain
    try:
        req = urllib.request.Request(f"https://{домен}/",
                                     headers={"User-Agent": "site-factory-trigger"})
        тело = urllib.request.urlopen(req, timeout=20,
                                      context=ssl.create_default_context()).read(200000)
    except Exception:
        return ""
    м = re.search(rb'site-factory-build-id" content="([^"]+)"', тело)
    if not м:
        return ""
    построение = м.group(1).decode("utf-8", "replace")
    голова = построение.split("-", 1)[0]
    return голова if re.fullmatch(r"[0-9a-f]{7,40}", голова) else ""


def дата_коммита(repo: Path, commit: str) -> int:
    готово = subprocess.run(["git", "-C", str(repo), "show", "-s", "--format=%ct", commit],
                            capture_output=True, text=True)
    return int(готово.stdout.strip()) if готово.returncode == 0 and готово.stdout.strip() else 0


def не_откат(cell: registry.Cell, commit: str) -> None:
    """Запретить выкладку коммита старше того, что уже работает.

    Иначе триггер, увидев зелёный прогон на своей ветке, накатил бы вчерашний
    выпуск поверх сегодняшнего — и снаружи это выглядело бы не откатом, а
    обычной выкладкой.
    """
    живой = живой_коммит(cell)
    if not живой:
        return
    путь = (cell.repo or {}).get("path")
    if not путь:
        return
    repo = Path(путь)
    свежий, текущий = дата_коммита(repo, commit), дата_коммита(repo, живой)
    if текущий and свежий and свежий < текущий:
        raise TriggerError(
            f"{cell.site_id}: кандидат {commit[:12]} старше работающего "
            f"{живой[:12]}. Выкладывать назад автоматически нельзя — это откат, "
            "и он должен быть осознанным решением")


def уже_выложен(cell: registry.Cell, commit: str, живой: str = "") -> bool:
    """Выложен ли этот коммит.

    Сравнение идёт с ЖИВЫМ build-id, а не с записью в реестре: запись отражает
    намерение и отстаёт, страница отвечает за действительность. Запись остаётся
    запасным ответом на случай, когда домен недоступен.
    """
    живой = живой or живой_коммит(cell)
    if живой and (живой.startswith(commit[:12]) or commit.startswith(живой[:12])):
        return True
    выложено = (cell.deployed or {}).get("source_commit") or ""
    return bool(выложено) and (выложено.startswith(commit[:12])
                               or commit.startswith(выложено[:12]))


def digest_коммита(site_id: str, commit: str) -> str:
    """Отпечаток артефакта этого коммита.

    Сборка воспроизводима, поэтому локальная сборка даёт те же байты, что
    проверил CI. Отпечаток из заявки исполнитель всё равно пересчитает — здесь
    он нужен, чтобы заявка была самодостаточной и проверяемой.
    """
    решение = admin_exec.план(site_id, commit=commit)
    return решение.digest


def проверить_сайт(site_id: str, *, submit: bool = False,
                   база: Path | None = None) -> dict[str, Any]:
    """Нужен ли выпуск этому сайту, и подать заявку, если нужен."""
    cell = registry.resolve(site_id)
    remote = registry.require_own_repo(cell)
    удержание = cell.release or {}
    if удержание.get("hold"):
        return {"site_id": cell.site_id, "domain": cell.domain,
                "action": "удержан",
                "reason": удержание.get("hold_reason") or "без причины"}
    прогон = последний_успешный(remote)
    commit = прогон["headSha"]

    итог: dict[str, Any] = {
        "site_id": cell.site_id, "domain": cell.domain, "repo": проект(remote),
        "branch": прогон.get("headBranch"), "commit": commit,
        "ci_run": str(прогон.get("databaseId")),
    }
    живой = живой_коммит(cell)
    итог["live_commit"] = живой or None
    if уже_выложен(cell, commit, живой):
        итог["action"] = "нечего выкладывать"
        return итог

    не_откат(cell, commit)
    итог["digest"] = digest_коммита(site_id, commit)
    заявка = queue.собрать(cell.site_id, commit, итог["digest"],
                           ci_run=итог["ci_run"], repo=проект(remote),
                           note=f"триггер: ветка {прогон.get('headBranch')}")
    итог["request_id"] = заявка.request_id
    if not submit:
        итог["action"] = "подал бы заявку"
        return итог
    итог["submission"] = queue.подать(заявка, база=база)
    итог["action"] = "заявка подана"
    return итог


def обойти(*, submit: bool = False, база: Path | None = None) -> list[dict[str, Any]]:
    """Все выделенные сайты. Отказ одного не отменяет остальных."""
    итоги = []
    for site_id in sorted(registry.extracted_sites()):
        try:
            итоги.append(проверить_сайт(site_id, submit=submit, база=база))
        except (TriggerError, admin_exec.ExecutorRefused, registry.RegistryError,
                queue.RequestRejected) as exc:
            итоги.append({"site_id": site_id, "action": "пропущен",
                          "error": str(exc)[:300]})
    return итоги
