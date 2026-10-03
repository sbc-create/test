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
import http.server
import json
import os
import pathlib
import socket
import subprocess
import sys
import traceback
import urllib.parse
from typing import Any, Callable

from factory.qwen import editorial, indexing, registry

ВЕРСИЯ_ПРОТОКОЛА = "2024-11-05"

#: Инструменты, которые МЕНЯЮТ состояние. Перечислены отдельно, потому что
#: ограничение «только чтение» обязано быть проверяемым свойством сервера, а
#: не обещанием в описании подключения: на этапе приёмки коннектор объявлен
#: read-only, и сервер не вправе предлагать ему то, чего тот не должен уметь.
ПИШУЩИЕ = ("set_indexing_mode",)

#: Только чтение: пишущие инструменты не объявляются в `tools/list` и
#: отказывают при вызове. Включается ключом `--read-only` или переменной
#: `QWEN_MCP_READ_ONLY=1`.
ТОЛЬКО_ЧТЕНИЕ = os.environ.get("QWEN_MCP_READ_ONLY", "").strip().lower() in (
    "1", "true", "yes")
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
        "read_only": ТОЛЬКО_ЧТЕНИЕ,
        "operations": sorted(доступные()),
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


def доступные() -> dict[str, dict[str, Any]]:
    """Инструменты, объявляемые клиенту с учётом режима только чтения."""
    if not ТОЛЬКО_ЧТЕНИЕ:
        return dict(ИНСТРУМЕНТЫ)
    return {и: св for и, св in ИНСТРУМЕНТЫ.items() if и not in ПИШУЩИЕ}


def вызвать(имя: str, аргументы: dict | None = None) -> dict[str, Any]:
    """Вызов инструмента по имени. Неизвестное имя — отказ."""
    if ТОЛЬКО_ЧТЕНИЕ and имя in ПИШУЩИЕ:
        raise ОшибкаИнструмента(
            f"{имя}: сервер запущен в режиме только чтения (--read-only), и "
            "менять состояние он не вправе. Это ограничение подключения на "
            "этапе приёмки, а не отказ операции: та же смена режима "
            "выполняется командой "
            "`python3 -m factory.qwen indexing-set --site <домен> --mode <режим>` "
            "на сервере фабрики со всеми её предпроверками")
    запись = ИНСТРУМЕНТЫ.get(имя)
    if запись is None:
        raise ОшибкаИнструмента(
            f"инструмента {имя!r} нет; есть: {', '.join(sorted(доступные()))}")
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
                           "read_only": ТОЛЬКО_ЧТЕНИЕ,
                           "environment": окружение()},
        })
    if метод in ("notifications/initialized", "initialized"):
        return None
    if метод == "tools/list":
        return _ответ(идент, {"tools": [
            {"name": имя, "description": св["описание"],
             "inputSchema": св["схема"]}
            for имя, св in sorted(доступные().items())]})
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


#: Адрес по умолчанию для транспорта HTTP. ТОЛЬКО петля: управляющая точка
#: фабрики в интернет не публикуется, и адрес вне петли требует явного
#: разрешения ключом `--allow-nonlocal`. Доступ снаружи даётся туннелем или
#: сетью контейнеров, а не слушателем на публичном адресе.
HTTP_АДРЕС_ПО_УМОЛЧАНИЮ = ("127.0.0.1", 9000)
ПУТЬ_MCP = "/mcp"


def _петля(адрес: str) -> bool:
    try:
        import ipaddress
        return ipaddress.ip_address(адрес).is_loopback
    except ValueError:
        return адрес in ("localhost",)


class _ОбработчикHTTP(http.server.BaseHTTPRequestHandler):
    """Streamable HTTP: один POST — один ответ JSON-RPC.

    Почему без потока событий. Клиент Open WebUI объявляет транспорт
    `MCP Streamable HTTP`; в нём поток `text/event-stream` НЕОБЯЗАТЕЛЕН —
    сервер вправе ответить одиночным JSON, и именно так отвечают все
    инструменты этого моста: они возвращают готовый результат, а не поток
    частей. Если клиент просит поток заголовком `Accept`, тот же ответ
    отдаётся одним событием `data:` — так совместимость сохраняется без
    второй реализации.
    """

    protocol_version = "HTTP/1.1"
    server_version = f"site-factory-mcp/{ИНСТРУКЦИЯ_ВЕРСИЯ}"

    def log_message(self, *_):   # журнал пишет вызывающая сторона
        pass

    def _отдать(self, код: int, тело: bytes, тип: str,
                заголовки: dict[str, str] | None = None) -> None:
        self.send_response(код)
        self.send_header("Content-Type", тип)
        self.send_header("Content-Length", str(len(тело)))
        self.send_header("Cache-Control", "no-store")
        for имя, значение in (заголовки or {}).items():
            self.send_header(имя, значение)
        self.end_headers()
        self.wfile.write(тело)

    def _json(self, код: int, полезное: Any) -> None:
        self._отдать(код, json.dumps(полезное, ensure_ascii=False).encode("utf-8"),
                     "application/json; charset=utf-8")

    def do_GET(self) -> None:  # noqa: N802
        путь = urllib.parse.urlsplit(self.path).path
        if путь == "/healthz":
            self._json(200, {"ready": True, "read_only": ТОЛЬКО_ЧТЕНИЕ,
                             "server": ИМЯ_СЕРВЕРА,
                             "instruction_version": ИНСТРУКЦИЯ_ВЕРСИЯ,
                             "environment": окружение()})
            return
        if путь == ПУТЬ_MCP:
            # Поток, открываемый сервером, здесь не нужен: ответ всегда
            # приходит на POST. Отказ называет причину, а не молчит 404.
            self._json(405, {"error": {
                "code": "stream_not_supported",
                "message": ("этот сервер отвечает на POST " + ПУТЬ_MCP +
                            "; поток, открываемый сервером (GET), не нужен: "
                            "каждый инструмент возвращает готовый результат")}})
            return
        self._json(404, {"error": {"code": "not_found",
                                   "message": f"нет маршрута {путь}"}})

    def do_POST(self) -> None:  # noqa: N802
        путь = urllib.parse.urlsplit(self.path).path
        if путь != ПУТЬ_MCP:
            self._json(404, {"error": {"code": "not_found",
                                       "message": f"нет маршрута {путь}"}})
            return
        длина = int(self.headers.get("Content-Length") or 0)
        сырое = self.rfile.read(длина) if длина else b""
        try:
            запрос = json.loads(сырое.decode("utf-8") or "{}")
        except (ValueError, UnicodeDecodeError):
            self._json(400, {"jsonrpc": "2.0", "id": None, "error": {
                "code": -32700, "message": "тело не разбирается как JSON"}})
            return
        пачка = запрос if isinstance(запрос, list) else [запрос]
        ответы = [о for о in (обработать(з) for з in пачка) if о is not None]
        if not ответы:
            # Только уведомления: по протоколу ответа нет вовсе.
            self.send_response(202)
            self.send_header("Content-Length", "0")
            self.end_headers()
            return
        полезное = ответы if isinstance(запрос, list) else ответы[0]
        принимает = (self.headers.get("Accept") or "")
        if "text/event-stream" in принимает:
            событие = ("event: message\ndata: "
                       + json.dumps(полезное, ensure_ascii=False) + "\n\n")
            self._отдать(200, событие.encode("utf-8"),
                         "text/event-stream; charset=utf-8")
            return
        self._json(200, полезное)


def служить_http(адрес: str, порт: int, *, разрешить_не_петлю: bool = False,
                 сервер_готов=None) -> int:
    """Транспорт HTTP для существующего коннектора. Петля по умолчанию."""
    if not _петля(адрес) and not разрешить_не_петлю:
        raise SystemExit(
            f"адрес {адрес} вне петли: управляющая точка фабрики в интернет не "
            "публикуется. Доступ снаружи даётся туннелем или сетью "
            "контейнеров; если адрес действительно внутренний, повторите с "
            "--allow-nonlocal и объясните это в журнале подключения")
    сервер = http.server.ThreadingHTTPServer((адрес, порт), _ОбработчикHTTP)
    сервер.daemon_threads = True
    print(json.dumps({
        "listening": f"http://{адрес}:{порт}{ПУТЬ_MCP}",
        "health": f"http://{адрес}:{порт}/healthz",
        "read_only": ТОЛЬКО_ЧТЕНИЕ, "tools": sorted(доступные()),
        "environment": окружение()}, ensure_ascii=False), flush=True)
    if сервер_готов is not None:
        сервер_готов(сервер)
    try:
        сервер.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        сервер.server_close()
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
    global ТОЛЬКО_ЧТЕНИЕ
    арг = list(argv if argv is not None else sys.argv[1:])
    if "--read-only" in арг:
        ТОЛЬКО_ЧТЕНИЕ = True
        арг.remove("--read-only")
    разрешить = "--allow-nonlocal" in арг
    if разрешить:
        арг.remove("--allow-nonlocal")
    if "--http" in арг:
        место = арг.index("--http")
        значение = арг[место + 1] if len(арг) > место + 1 else ""
        адрес, порт = HTTP_АДРЕС_ПО_УМОЛЧАНИЮ
        if значение and not значение.startswith("--"):
            if ":" in значение:
                адрес, _, хвост = значение.rpartition(":")
                порт = int(хвост)
            else:
                порт = int(значение)
        return служить_http(адрес or HTTP_АДРЕС_ПО_УМОЛЧАНИЮ[0], порт,
                            разрешить_не_петлю=разрешить)
    if "--self-check" in арг:
        return самопроверка()
    if "--tools" in арг:
        print(json.dumps([
            {"name": имя, "description": св["описание"]}
            for имя, св in sorted(доступные().items())],
            ensure_ascii=False, indent=1))
        return 0
    return служить()


if __name__ == "__main__":
    raise SystemExit(главная())
