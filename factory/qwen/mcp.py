"""Инструменты Qwen поверх ФАКТИЧЕСКОЙ фабрики: MCP-сервер без зависимостей.

Зачем он появился
-----------------

В сессии Qwen есть инструменты `site-factory_system_readiness`,
`list_registered_sites`, `get_registered_site` и runbook. Измерено 2026-10-03 на
`claude-control-01`:

* ни одного совпадения `list_registered_sites`, `get_registered_site` или
  `system_readiness` в этом репозитории и во всём `/srv/site-factory` — этого
  кода здесь нет;
* ни одна локальная служба не отдаёт оболочку `{"version": 1, "sites": [...]}`;
  перебраны ВСЕ слушающие порты хоста;
* местный Control API (`127.0.0.1:8790`, юнит `site-factory-control-api.service`,
  релиз `e698e2adf502`, корень состояния `/srv/site-factory/repo`) отвечает
  `{"items": [...]}` и отдаёт непустой список — другая оболочка и другие имена
  полей.

Вывод по доказательствам: инструменты Qwen обслуживает НЕ этот хост и не этот
код, и его реестр — не авторитетный реестр фабрики. Поэтому пустой `sites: []`
при `registry.valid: true` — согласованный ответ ДРУГОГО источника, а не
поломка здешнего реестра.

Что делает этот модуль
----------------------

Отдаёт те же имена инструментов, но поверх авторитетного реестра и ШТАТНЫХ
операций `factory.qwen`. Ни второго реестра, ни второго оркестратора здесь нет:
каждый инструмент вызывает существующий модуль. Подключение — перенастройка
коннектора на одну команду; недостающий параметр назван в
`docs/QWEN_MCP_BRIDGE.md`.

Три правила ответа
------------------

1. **Пустой успех запрещён.** Нечитаемый реестр, недоступный путь или
   неизвестный домен — это `isError` с названной причиной, а не `sites: []`.
2. **Окружение называется в каждом ответе**: хост, учётная запись, рабочий
   каталог, путь и версия правил, версия кода. Ответ без них проверить нечем.
3. **Проверки владельца и выпуска остаются на месте.** Смена режима идёт через
   `indexing.установить`, то есть через те же предпроверки; произвольной
   команды оболочки здесь нет и быть не может.

Протокол: JSON-RPC 2.0 по стандартному вводу/выводу (`initialize`,
`tools/list`, `tools/call`) — ровно то, чем клиент запускает локальный
MCP-сервер. Внешних зависимостей нет намеренно: пакет `mcp` на хосте
отсутствует, а тащить его ради трёх методов значило бы добавить к
доставке ещё один шаг.
"""
from __future__ import annotations

import getpass
import json
import os
import pathlib
import socket
import subprocess
import sys
import traceback
from typing import Any, Callable

from factory.qwen import editorial, indexing, registry

ВЕРСИЯ_ПРОТОКОЛА = "2024-11-05"
ИМЯ_СЕРВЕРА = "site-factory"
ВЕРСИЯ_ОБОЛОЧКИ = 1

#: Хост, на котором живёт фабрика. Не для запрета, а для СВЕРКИ: ответ обязан
#: говорить, с какой машины он пришёл, иначе «реестр пуст» невозможно отличить
#: от «спросили не ту машину» — ровно эта неразличимость и привела к задаче.
ОЖИДАЕМЫЙ_ХОСТ = "claude-control-01"


class ОшибкаИнструмента(RuntimeError):
    """Отказ с названной причиной. Пустого успеха вместо него не бывает."""


def _версия_кода() -> dict[str, Any]:
    корень = pathlib.Path(__file__).resolve().parents[2]
    def git(*арг: str) -> str:
        п = subprocess.run(["git", "-C", str(корень), *арг],
                           capture_output=True, text=True)
        return п.stdout.strip() if п.returncode == 0 else ""
    грязно = git("status", "--porcelain")
    return {"worktree": str(корень), "commit": git("rev-parse", "HEAD")[:12],
            "branch": git("rev-parse", "--abbrev-ref", "HEAD"),
            "dirty": bool(грязно)}


def окружение() -> dict[str, Any]:
    """Идентичность окружения. Присутствует в ЛЮБОМ ответе сервера."""
    хост = socket.gethostname()
    return {
        "host": хост,
        "host_matches_factory": хост == ОЖИДАЕМЫЙ_ХОСТ,
        "expected_host": ОЖИДАЕМЫЙ_ХОСТ,
        "user": getpass.getuser(),
        "cwd": os.getcwd(),
        "code": _версия_кода(),
        "instruction": {"path": ИНСТРУКЦИЯ_ПУТЬ, "version": ИНСТРУКЦИЯ_ВЕРСИЯ},
    }


def _инструкция() -> tuple[str, str]:
    from factory.qwen import __main__ as точка
    return точка.ИНСТРУКЦИЯ, точка.ВЕРСИЯ_ИНСТРУКЦИИ


ИНСТРУКЦИЯ_ПУТЬ, ИНСТРУКЦИЯ_ВЕРСИЯ = _инструкция()


def _источники() -> dict[str, Any]:
    """Состояние источников реестра: путь, читаемость, число записей, ошибка."""
    return registry.состояние_источников()


# --------------------------------------------------------------- инструменты

def инструмент_готовности(_: dict) -> dict[str, Any]:
    """Готовность СИСТЕМЫ: окружение, источники реестра, версия правил.

    `registry.valid` ставится ТОЛЬКО по факту прочитанных источников. Прежний
    ответ сторонней реализации объявлял `valid: true` рядом с пустым списком
    сайтов; здесь это невозможно по построению: признак и список считаются из
    одного чтения.
    """
    итог: dict[str, Any] = {"environment": окружение()}
    try:
        сайты = registry.собрать(опрашивать_сеть=False)
    except registry.РеестрНедоступен as ош:
        итог.update({"ok": False, "registry": {"valid": False,
                                               "error": str(ош),
                                               "sources": _источники()}})
        raise ОшибкаИнструмента(json.dumps(итог, ensure_ascii=False)) from None
    источники = _источники()
    прочитаны = all(с.get("ok") for с in источники.values())
    итог.update({
        "ok": прочитаны,
        "registry": {"valid": прочитаны, "sites": len(сайты),
                     "sources": источники},
        "operations": sorted(ИНСТРУМЕНТЫ),
    })
    return итог


def инструмент_списка(аргументы: dict) -> dict[str, Any]:
    """Список сайтов из авторитетного реестра. Пустого успеха не бывает.

    Оболочка `{"version": 1, "sites": [...]}` — та же, что ждёт клиент Qwen,
    поэтому переключение коннектора не требует правок на его стороне.
    """
    опрашивать = bool(аргументы.get("probe_network"))
    try:
        сайты = registry.собрать(опрашивать_сеть=опрашивать)
    except registry.РеестрНедоступен as ош:
        raise ОшибкаИнструмента(
            f"реестр не прочитан: {ош}. Источники: "
            f"{json.dumps(_источники(), ensure_ascii=False)}") from None
    if not сайты:
        # Пустой список при прочитанном реестре означает НЕ «сайтов нет», а
        # «источник не тот»: в авторитетном реестре записи есть всегда.
        raise ОшибкаИнструмента(
            "реестр прочитан, но не дал ни одного сайта — это состояние "
            "источника, а не факт о сети. Источники: "
            f"{json.dumps(_источники(), ensure_ascii=False)}")
    return {"version": ВЕРСИЯ_ОБОЛОЧКИ,
            "sites": [с.as_dict() for с in сайты],
            "environment": окружение(),
            "registry": {"sources": _источники()}}


def инструмент_сайта(аргументы: dict) -> dict[str, Any]:
    """Один сайт по домену или site_id. Неизвестный — отказ, не пустота."""
    запрос = str(аргументы.get("site") or аргументы.get("domain") or "").strip()
    if not запрос:
        raise ОшибкаИнструмента("нужен параметр site (домен или site_id)")
    try:
        сайты = registry.собрать(опрашивать_сеть=False)
    except registry.РеестрНедоступен as ош:
        raise ОшибкаИнструмента(f"реестр не прочитан: {ош}") from None
    для = next((с for с in сайты if запрос in (с.domain, с.site_id)), None)
    if для is None:
        raise ОшибкаИнструмента(
            f"{запрос}: в авторитетном реестре такого сайта нет. Известные: "
            + ", ".join(sorted(с.domain for с in сайты)))
    return {"version": ВЕРСИЯ_ОБОЛОЧКИ, "site": для.as_dict(),
            "environment": окружение(), "registry": {"sources": _источники()}}


def инструмент_готовности_домена(аргументы: dict) -> dict[str, Any]:
    """Вердикт готовности домена к открытию. Ничего не меняет."""
    сайт = str(аргументы.get("site") or "").strip()
    if not сайт:
        raise ОшибкаИнструмента("нужен параметр site")
    доказать = аргументы.get("prove", True)
    try:
        вердикт = indexing.готовность(сайт, доказать=bool(доказать))
    except (indexing.Отказано, editorial.ОперацияОтклонена) as ош:
        raise ОшибкаИнструмента(str(ош)) from None
    return {"version": ВЕРСИЯ_ОБОЛОЧКИ, "verdict": вердикт,
            "environment": окружение()}


def инструмент_смены_режима(аргументы: dict) -> dict[str, Any]:
    """Смена режима ШТАТНОЙ операцией: предпроверки остаются на месте.

    Здесь нет ни своей логики разрешений, ни обхода проверок: вызывается
    `indexing.установить`, которая сама спрашивает разрешение владельца,
    разрешение выпуска, читателя в выпуске и подтверждает результат публичным
    ответом. Произвольной команды оболочки сервер не предоставляет.
    """
    сайт = str(аргументы.get("site") or "").strip()
    режим = str(аргументы.get("mode") or "").strip().lower()
    if not сайт:
        raise ОшибкаИнструмента("нужен параметр site")
    if режим not in ("open", "closed"):
        raise ОшибкаИнструмента("mode: open или closed")
    try:
        итог = indexing.установить(
            сайт, mode=режим, author=str(аргументы.get("author") or "qwen"),
            expect_release=str(аргументы.get("expect_release") or ""))
    except (indexing.Отказано, editorial.ОперацияОтклонена) as ош:
        raise ОшибкаИнструмента(str(ош)) from None
    return {"version": ВЕРСИЯ_ОБОЛОЧКИ, "result": итог,
            "confirmed": bool(итог.get("confirmed")),
            "environment": окружение()}


def инструмент_подтверждения(аргументы: dict) -> dict[str, Any]:
    """Что домен отдаёт СЕЙЧАС: подтверждение режима публичным ответом."""
    сайт = str(аргументы.get("site") or "").strip()
    if not сайт:
        raise ОшибкаИнструмента("нужен параметр site")
    ожидаемый = str(аргументы.get("expected") or "").strip().upper()
    try:
        итог = indexing.подтвердить(сайт, ожидаемый=ожидаемый)
    except (indexing.Отказано, editorial.ОперацияОтклонена) as ош:
        raise ОшибкаИнструмента(str(ош)) from None
    return {"version": ВЕРСИЯ_ОБОЛОЧКИ, "confirmation": итог,
            "environment": окружение()}


def инструмент_журнала(аргументы: dict) -> dict[str, Any]:
    """Журнал: файл состояния, записи операций и результат заявки слоя."""
    сайт = str(аргументы.get("site") or "").strip()
    if not сайт:
        raise ОшибкаИнструмента("нужен параметр site")
    try:
        с = editorial._сайт(сайт)
    except editorial.ОперацияОтклонена as ош:
        raise ОшибкаИнструмента(str(ош)) from None
    итог: dict[str, Any] = {"version": ВЕРСИЯ_ОБОЛОЧКИ,
                            "site": с.domain, "site_id": с.site_id,
                            "environment": окружение()}
    итог["state_file"] = indexing.текущее(с.domain)
    журнал = indexing.ЖУРНАЛ / "operations.jsonl"
    записи: list[dict] = []
    if журнал.is_file():
        try:
            for строка in журнал.read_text(encoding="utf-8").splitlines():
                if not строка.strip():
                    continue
                запись = json.loads(строка)
                if запись.get("site") == с.domain:
                    записи.append(запись)
        except (OSError, ValueError) as ош:
            raise ОшибкаИнструмента(
                f"журнал операций {журнал} не читается: {type(ош).__name__}") from None
    итог["operations"] = записи[-20:]
    итог["operations_log"] = str(журнал)
    # Результат заявки слоя спрашивается У ОЧЕРЕДИ, а не читается файлом:
    # путь к каталогу результатов знает она (`queue.БАЗА`), и второй знающий
    # разошёлся бы с ней при первом же переносе каталога. Внешний `status`
    # очереди называет судьбу заявки, внутренний — исход операции.
    from factory.cell import queue as очередь

    из_очереди: dict[str, Any] = {}
    for режим in ("closed", "open"):
        идентификатор = f"{с.site_id}-idx-{режим}"
        try:
            состояние = очередь.состояние(идентификатор)
        except (OSError, ValueError) as ош:
            из_очереди[режим] = {"request_id": идентификатор,
                                 "error": f"{type(ош).__name__}: {ош}"}
            continue
        if состояние.get("status") == "unknown":
            continue
        результат = состояние.get("result") or {}
        исход = (результат.get("outcome") or {})
        применение = (исход.get("steps") or {}).get("apply") or {}
        из_очереди[режим] = {
            "request_id": идентификатор,
            "queue_status": состояние.get("status"),
            "status": результат.get("status"),
            "outcome": исход.get("status"), "stage": исход.get("stage"),
            "error": результат.get("error"),
            "nginx_test": применение.get("nginx_test"),
            "nginx_reload": применение.get("nginx_reload"),
            "path": str(очередь.БАЗА / "results" / f"{идентификатор}.json"),
        }
    итог["layer_requests"] = из_очереди
    итог["queue_root"] = str(очередь.БАЗА)
    return итог


#: Имена СОВПАДАЮТ с теми, что уже есть в сессии Qwen: переключение коннектора
#: не должно требовать правок на его стороне.
ИНСТРУМЕНТЫ: dict[str, dict[str, Any]] = {
    "system_readiness": {
        "обработчик": инструмент_готовности,
        "описание": ("Готовность системы: идентичность окружения, источники "
                     "реестра с путями и числом записей, версия правил и "
                     "версия кода. registry.valid ставится только по факту "
                     "прочитанных источников."),
        "схема": {"type": "object", "properties": {}, "additionalProperties": False},
    },
    "list_registered_sites": {
        "обработчик": инструмент_списка,
        "описание": ("Сайты из авторитетного реестра фабрики "
                     "(config/site-cells.json + inventory/network-allowlist.yaml). "
                     "Нечитаемый или пустой источник — ошибка, а не пустой список."),
        "схема": {"type": "object", "properties": {
            "probe_network": {"type": "boolean",
                              "description": "опрашивать домены по сети"}},
            "additionalProperties": False},
    },
    "get_registered_site": {
        "обработчик": инструмент_сайта,
        "описание": "Одна запись реестра по домену или site_id.",
        "схема": {"type": "object", "properties": {
            "site": {"type": "string", "description": "домен или site_id"}},
            "required": ["site"], "additionalProperties": False},
    },
    "domain_indexing_readiness": {
        "обработчик": инструмент_готовности_домена,
        "описание": ("Вердикт готовности домена к открытию: статус из закрытого "
                     "перечня, release_gap, required_release, next_action. "
                     "Ничего не меняет."),
        "схема": {"type": "object", "properties": {
            "site": {"type": "string"},
            "prove": {"type": "boolean",
                      "description": "поднимать выложенный релиз для "
                                     "доказательства чтения конфигурации"}},
            "required": ["site"], "additionalProperties": False},
    },
    "set_indexing_mode": {
        "обработчик": инструмент_смены_режима,
        "описание": ("Смена режима индексации ШТАТНОЙ операцией с её "
                     "предпроверками: разрешение владельца, разрешение "
                     "выпуска, читатель в выпуске, подтверждение публичным "
                     "ответом и возврат при частичном отказе."),
        "схема": {"type": "object", "properties": {
            "site": {"type": "string"},
            "mode": {"type": "string", "enum": ["open", "closed"]},
            "expect_release": {"type": "string",
                               "description": "ожидаемый выложенный выпуск"},
            "author": {"type": "string"}},
            "required": ["site", "mode"], "additionalProperties": False},
    },
    "confirm_indexing": {
        "обработчик": инструмент_подтверждения,
        "описание": "Что домен отдаёт сейчас: подтверждение режима ответом.",
        "схема": {"type": "object", "properties": {
            "site": {"type": "string"},
            "expected": {"type": "string", "enum": ["OPEN", "CLOSED", ""]}},
            "required": ["site"], "additionalProperties": False},
    },
    "indexing_journal": {
        "обработчик": инструмент_журнала,
        "описание": ("Журнал домена: файл состояния, последние записи операций "
                     "и результаты заявок слоя nginx с фактическими nginx_test "
                     "и nginx_reload."),
        "схема": {"type": "object", "properties": {
            "site": {"type": "string"}},
            "required": ["site"], "additionalProperties": False},
    },
}


def вызвать(имя: str, аргументы: dict | None = None) -> dict[str, Any]:
    """Вызов инструмента по имени. Неизвестное имя — отказ."""
    запись = ИНСТРУМЕНТЫ.get(имя)
    if запись is None:
        raise ОшибкаИнструмента(
            f"инструмента {имя!r} нет; есть: {', '.join(sorted(ИНСТРУМЕНТЫ))}")
    обработчик: Callable[[dict], dict] = запись["обработчик"]
    return обработчик(аргументы or {})


# ------------------------------------------------------------- протокол MCP

def _ответ(идент: Any, результат: dict) -> dict:
    return {"jsonrpc": "2.0", "id": идент, "result": результат}


def _текст(полезное: dict) -> dict:
    return {"content": [{"type": "text",
                         "text": json.dumps(полезное, ensure_ascii=False,
                                            indent=1)}]}


def обработать(запрос: dict) -> dict | None:
    """Один запрос JSON-RPC. None — уведомление, ответ не нужен."""
    метод = запрос.get("method")
    идент = запрос.get("id")
    if метод == "initialize":
        return _ответ(идент, {
            "protocolVersion": ВЕРСИЯ_ПРОТОКОЛА,
            "capabilities": {"tools": {}},
            "serverInfo": {"name": ИМЯ_СЕРВЕРА,
                           "version": ИНСТРУКЦИЯ_ВЕРСИЯ,
                           "environment": окружение()},
        })
    if метод in ("notifications/initialized", "initialized"):
        return None
    if метод == "tools/list":
        return _ответ(идент, {"tools": [
            {"name": имя, "description": св["описание"],
             "inputSchema": св["схема"]}
            for имя, св in sorted(ИНСТРУМЕНТЫ.items())]})
    if метод == "tools/call":
        параметры = запрос.get("params") or {}
        имя = параметры.get("name") or ""
        аргументы = параметры.get("arguments") or {}
        try:
            полезное = вызвать(имя, аргументы)
        except ОшибкаИнструмента as ош:
            # ОТКАЗ, а не пустой успех: клиент обязан увидеть ошибку.
            return _ответ(идент, {**_текст({
                "error": str(ош), "tool": имя,
                "environment": окружение()}), "isError": True})
        except Exception as ош:  # noqa: BLE001 — наружу идёт факт, не трасса
            return _ответ(идент, {**_текст({
                "error": f"непредвиденный отказ {type(ош).__name__}: {ош}",
                "tool": имя, "environment": окружение(),
                "traceback_tail": traceback.format_exc()[-400:]}),
                "isError": True})
        return _ответ(идент, _текст(полезное))
    if метод == "ping":
        return _ответ(идент, {})
    return {"jsonrpc": "2.0", "id": идент,
            "error": {"code": -32601, "message": f"метод {метод!r} не поддержан"}}


def служить(поток_ввода=None, поток_вывода=None) -> int:
    """Цикл stdio: по строке на запрос, по строке на ответ."""
    ввод = поток_ввода or sys.stdin
    вывод = поток_вывода or sys.stdout
    for строка in ввод:
        строка = строка.strip()
        if not строка:
            continue
        try:
            запрос = json.loads(строка)
        except ValueError:
            вывод.write(json.dumps({"jsonrpc": "2.0", "id": None, "error": {
                "code": -32700, "message": "запрос не разбирается как JSON"}},
                ensure_ascii=False) + "\n")
            вывод.flush()
            continue
        ответ = обработать(запрос)
        if ответ is None:
            continue
        вывод.write(json.dumps(ответ, ensure_ascii=False) + "\n")
        вывод.flush()
    return 0


def самопроверка() -> int:
    """Прогон трёх читающих инструментов без клиента. Ничего не меняет."""
    итог: dict[str, Any] = {"environment": окружение(), "checks": {}}
    плохо = 0
    for имя, аргументы in (("system_readiness", {}),
                           ("list_registered_sites", {}),
                           ("get_registered_site", {"site": "lordserials22.info"})):
        try:
            значение = вызвать(имя, аргументы)
            кратко: dict[str, Any] = {"ok": True}
            if имя == "list_registered_sites":
                кратко.update({"version": значение["version"],
                               "sites": len(значение["sites"])})
            elif имя == "system_readiness":
                кратко.update({"registry_valid": значение["registry"]["valid"],
                               "sites": значение["registry"]["sites"]})
            else:
                кратко.update({"site_id": значение["site"]["site_id"]})
            итог["checks"][имя] = кратко
        except ОшибкаИнструмента as ош:
            плохо += 1
            итог["checks"][имя] = {"ok": False, "error": str(ош)[:400]}
    итог["ok"] = плохо == 0
    print(json.dumps(итог, ensure_ascii=False, indent=1))
    return 0 if плохо == 0 else 1


def главная(argv: list[str] | None = None) -> int:
    арг = list(argv if argv is not None else sys.argv[1:])
    if "--self-check" in арг:
        return самопроверка()
    if "--tools" in арг:
        print(json.dumps([
            {"name": имя, "description": св["описание"]}
            for имя, св in sorted(ИНСТРУМЕНТЫ.items())],
            ensure_ascii=False, indent=1))
        return 0
    return служить()


if __name__ == "__main__":
    raise SystemExit(главная())
