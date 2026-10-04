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
import hashlib
import http.server
import json
import os
import pathlib
import socket
import subprocess
import sys
import time
import traceback
import urllib.parse
from typing import Any, Callable

from factory.qwen import editorial, indexing, registry

ВЕРСИЯ_ПРОТОКОЛА = "2024-11-05"

#: Инструменты, которые МЕНЯЮТ состояние. Перечислены отдельно, потому что
#: ограничение «только чтение» обязано быть проверяемым свойством сервера, а
#: не обещанием в описании подключения: на этапе приёмки коннектор объявлен
#: read-only, и сервер не вправе предлагать ему то, чего тот не должен уметь.
ПИШУЩИЕ = ("set_indexing_mode", "rollback_indexing", "release_site",
           "rollback_site", "refresh_executor_access", "prepare_material",
           "publish_material", "unpublish_material")

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


def отпечаток_сайтов(сайты) -> str:
    """sha256 отсортированного списка доменов.

    Нужен приёмке: «совпадает ли список сайтов с фабрикой» проверяется ОДНИМ
    значением, а не перечислением двадцати трёх имён в чужом терминале. Берутся
    только домены и только в сортированном порядке: порядок чтения реестра к
    тождеству списка отношения не имеет.
    """
    домены = sorted(с.domain for с in сайты)
    return hashlib.sha256("\n".join(домены).encode("utf-8")).hexdigest()


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
                     "sites_digest": отпечаток_сайтов(сайты),
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
            "registry": {"sources": _источники(),
                         "sites": len(сайты),
                         "sites_digest": отпечаток_сайтов(сайты)}}


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


def инструмент_отката(аргументы: dict) -> dict[str, Any]:
    """Откат последней смены режима ШТАТНОЙ операцией.

    Без этого инструмента откат существовал только командой на сервере, то
    есть требовал человека ровно в том случае, для которого и нужен —
    после неудачной попытки. Проверок он не обходит: `indexing.откатить`
    читает журнал, находит предыдущее состояние и возвращает его той же
    операцией со всеми её предпроверками.
    """
    сайт = str(аргументы.get("site") or "").strip()
    if not сайт:
        raise ОшибкаИнструмента("нужен параметр site")
    try:
        итог = indexing.откатить(сайт,
                                 author=str(аргументы.get("author") or "qwen"))
    except (indexing.Отказано, editorial.ОперацияОтклонена) as ош:
        raise ОшибкаИнструмента(str(ош)) from None
    return {"version": ВЕРСИЯ_ОБОЛОЧКИ, "result": итог,
            "confirmed": bool(итог.get("confirmed")),
            "environment": окружение()}


#: Вердикты готовности аналитики. Закрытый перечень: «что-то не так» вердиктом
#: не является, и у каждого свой следующий шаг.
АНАЛИТИКА_ВЕРДИКТЫ = ("REGISTRY_UNREADABLE", "DOMAIN_UNKNOWN", "COUNTER_MISSING",
                      "HOSTS_MISMATCH", "COLLECTION_DISABLED", "READY")


def инструмент_аналитики(аргументы: dict) -> dict[str, Any]:
    """Готовность аналитики домена по АВТОРИТЕТНОМУ реестру фабрики.

    Зачем это здесь. Инструмент `analytics_readiness` сессии Qwen отвечал
    одной строкой «Error executing tool analytics_readiness» — без причины,
    домена и источника. Данные об аналитике принадлежат фабрике
    (`config/analytics.json`, 19 записей), и у моста их не было вовсе: ни
    прочитать, ни назвать источник он не мог. Теперь может — чтением, без
    единой записи.

    Секреты не выводятся. Счётчик и перечень хостов секретами не являются,
    токен доступа живёт в `secret_ref` вне реестра, и сюда попадает только
    признак «учётные данные настроены», без пути и значения.
    """
    # В сессии Qwen этот инструмент вызывается с аргументом `domain`
    # ({"domain": "lordserials22.info"}), а остальные — с `site`. Принимаются
    # оба: отказ «нужен параметр site» на вызов с `domain` был бы отказом из-за
    # имени поля, а не из-за существа.
    сайт = str(аргументы.get("site") or аргументы.get("domain") or "").strip()
    if not сайт:
        raise ОшибкаИнструмента("нужен параметр site (или domain)")
    try:
        с = editorial._сайт(сайт)
    except editorial.ОперацияОтклонена as ош:
        raise ОшибкаИнструмента(
            f"{сайт}: {ош}. Это отсутствие записи в реестре ячеек, а не вывод "
            "об аналитике") from None

    from factory.analytics import registry as аналитика

    путь = аналитика.registry_path()
    try:
        данные = аналитика.load()
    except (OSError, ValueError) as ош:
        raise ОшибкаИнструмента(
            f"реестр аналитики {путь} не прочитан ({type(ош).__name__}: {ош}): "
            "вердикт не выносится — пустой ответ выглядел бы как «аналитики "
            "нет»") from None

    записи = данные.get("properties") or []
    запись = аналитика.by_domain(с.domain)
    итог: dict[str, Any] = {
        "version": ВЕРСИЯ_ОБОЛОЧКИ, "site": с.domain, "site_id": с.site_id,
        "source": {"path": str(путь), "entries": len(записи),
                   "provider": данные.get("provider"),
                   "updated_at": данные.get("updated_at")},
        "verdicts_known": list(АНАЛИТИКА_ВЕРДИКТЫ),
        "environment": окружение(),
    }
    if запись is None:
        итог.update({
            "verdict": "DOMAIN_UNKNOWN", "ok": False,
            "reason": (f"домена {с.domain} нет в реестре аналитики {путь} "
                       f"({len(записи)} записей). Это отсутствие записи, а не "
                       "вывод о счётчике"),
            "next_action": "завести запись домена в config/analytics.json "
                           "штатной операцией аналитики; счётчик не выдумывать",
        })
        return итог

    сырое = запись.raw
    хосты = запись.allowed_hosts
    счётчик = запись.counter_id
    собирает = запись.analytics_enabled
    совпали = (not хосты) or any(
        str(х).lower().endswith(с.domain.lower()) for х in хосты)
    if not счётчик:
        вердикт, причина, дальше = (
            "COUNTER_MISSING",
            "в записи домена нет counter_id: собирать некуда",
            "создать счётчик штатной операцией аналитики "
            "(`python3 -m factory analytics …`), значение не придумывать")
    elif not совпали:
        вердикт, причина, дальше = (
            "HOSTS_MISMATCH",
            f"counter_id {счётчик} объявлен для хостов {хосты}, домена "
            f"{с.domain} среди них нет",
            "привести allowed_hosts к домену сайта; расхождение означает сбор "
            "не с того сайта")
    elif not собирает:
        вердикт, причина, дальше = (
            "COLLECTION_DISABLED",
            f"счётчик {счётчик} есть, но analytics_enabled = false: сбор "
            "выключен",
            "включать сбор отдельным решением владельца; счётчик, включённый "
            "до запуска сайта, собирает пустоту")
    else:
        вердикт, причина, дальше = (
            "READY", f"счётчик {счётчик} объявлен и сбор включён",
            "ничего не делать")

    from factory.analytics import credentials as уд

    итог.update({
        "verdict": вердикт, "ok": вердикт == "READY", "reason": причина,
        "next_action": дальше,
        "counter_id": счётчик,
        "counter_state": сырое.get("counter_state"),
        "analytics_enabled": собирает,
        "webvisor": bool(сырое.get("webvisor")),
        "allowed_hosts": хосты,
        "goals": list(сырое.get("goals") or []),
        "webmaster_status": запись.webmaster_status,
        # Признак, а не путь и не значение: учётные данные остаются вне ответа.
        "credentials_configured": bool(уд.credentials_directory()),
    })
    return итог


# ------------------------------------------------- выпуск сайта: штатные операции
#
# Операции выпуска в фабрике УЖЕ есть: план и подачу заявки делает
# `factory.cell.trigger`, применяет привилегированный исполнитель по таймеру,
# результат лежит в очереди. У Qwen их не было — поэтому «исправить индексацию»
# он мог, а «выпустить сайт» нет. Здесь они подключаются как есть: второго
# исполнителя не появляется, произвольной команды оболочки нет, все проверки
# (происхождение из CI, доступ исполнителя, ворота защищённых данных) остаются
# на своих местах — они живут в очереди и в исполнителе, а не здесь.


def _site_id(значение: str) -> str:
    """Принять домен или site_id и вернуть site_id реестра."""
    сайт = str(значение or "").strip()
    if not сайт:
        raise ОшибкаИнструмента("нужен параметр site (домен или site_id)")
    try:
        return editorial._сайт(сайт).site_id
    except editorial.ОперацияОтклонена as ош:
        raise ОшибкаИнструмента(str(ош)) from None


def _план_выпуска(сайт: str, *, подать: bool) -> dict[str, Any]:
    from factory.cell import admin_exec
    from factory.cell import queue as очередь_ячеек
    from factory.cell import registry as реестр_ячеек
    from factory.cell import trigger as триггер

    site_id = _site_id(сайт)
    try:
        итог = триггер.проверить_сайт(site_id, submit=подать)
    # `ExecutorRefused` в этот список попал по настоящему прогону: рабочая копия
    # репозитория сайта стояла на другом коммите, и расчёт digest отказал —
    # инструмент отдал НЕОБРАБОТАННОЕ исключение вместо названной причины.
    # Отказ фабрики обязан приходить отказом инструмента, а не трассировкой.
    except (триггер.TriggerError, реестр_ячеек.RegistryError,
            admin_exec.ExecutorRefused, очередь_ячеек.RequestRejected) as ош:
        raise ОшибкаИнструмента(f"{site_id}: {ош}") from None
    return итог


def инструмент_плана_выпуска(аргументы: dict) -> dict[str, Any]:
    """Что было бы выпущено: коммит, прогон CI, digest, препятствия. Без мутаций."""
    итог = _план_выпуска(str(аргументы.get("site") or ""), подать=False)
    return {"version": ВЕРСИЯ_ОБОЛОЧКИ, "plan": итог,
            "blocked": итог.get("blocked"),
            "environment": окружение()}


def инструмент_выпуска(аргументы: dict) -> dict[str, Any]:
    """Подать заявку на выпуск последнего успешного прогона CI.

    Ничего не выкладывает сама: заявка уходит привилегированному исполнителю,
    который проверяет происхождение (прогон CI, ветка, коммит), digest
    артефакта и защищённые данные, применяет выпуск кандидатом, прогревает его
    и переключает трафик только после проверки ответом. При неуспехе кандидата
    возвращает трафик сам.
    """
    итог = _план_выпуска(str(аргументы.get("site") or ""), подать=True)
    заявка = итог.get("request_id")
    if итог.get("blocked"):
        raise ОшибкаИнструмента(
            f"{итог.get('site_id')}: заявка не подана — {итог['blocked']}")
    return {"version": ВЕРСИЯ_ОБОЛОЧКИ, "submitted": bool(заявка),
            "request_id": заявка, "release": итог,
            "next_action": ("исполнитель разбирает очередь раз в минуту; "
                            "результат — инструментом operation_result по "
                            "request_id. Повторная подача того же коммита "
                            "второго выпуска не делает"),
            "environment": окружение()}


def инструмент_результата(аргументы: dict) -> dict[str, Any]:
    """Результат заявки: судьба в очереди, исход операции и её журнал."""
    from factory.cell import queue as очередь

    идент = str(аргументы.get("request_id") or "").strip()
    if not идент:
        raise ОшибкаИнструмента("нужен параметр request_id")
    try:
        состояние = очередь.состояние(идент)
    except (OSError, ValueError) as ош:
        raise ОшибкаИнструмента(
            f"состояние заявки {идент} не прочитано: {type(ош).__name__}: {ош}") from None
    результат = состояние.get("result") or {}
    исход = результат.get("outcome") or {}
    return {
        "version": ВЕРСИЯ_ОБОЛОЧКИ, "request_id": идент,
        "queue_status": состояние.get("status"),
        "status": результат.get("status"),
        "outcome": исход.get("status"), "stage": исход.get("stage"),
        "build_id": исход.get("build_id"),
        "error": результат.get("error"),
        # Журнал операции: этапы, которые исполнитель прошёл фактически.
        "steps": sorted((исход.get("steps") or {})),
        "stages": (состояние.get("request") or {}).get("stages"),
        "result_path": str(очередь.БАЗА / "results" / f"{идент}.json"),
        "environment": окружение(),
    }


def инструмент_откката_сайта(аргументы: dict) -> dict[str, Any]:
    """Вернуть трафик действующей версии штатной заявкой `rollback`."""
    from factory.cell import queue as очередь

    site_id = _site_id(str(аргументы.get("site") or ""))
    коммит = str(аргументы.get("commit") or "").strip()
    if not коммит:
        raise ОшибкаИнструмента(
            "нужен параметр commit: заявка откката называет выпуск, от "
            "которого откатываются — его видно в release_plan (live_commit)")
    try:
        заявка = очередь.собрать(site_id, коммит, "", operation="rollback",
                                 note=str(аргументы.get("note") or "")[:200])
        подача = очередь.подать(заявка)
    except очередь.RequestRejected as ош:
        raise ОшибкаИнструмента(f"{site_id}: заявка откката отвергнута: {ош}") from None
    except OSError as ош:
        raise ОшибкаИнструмента(
            f"{site_id}: очередь недоступна ({type(ош).__name__})") from None
    return {"version": ВЕРСИЯ_ОБОЛОЧКИ, "request_id": заявка.request_id,
            "submission": подача.get("status"), "environment": окружение()}


def инструмент_проверки_доступа(аргументы: dict) -> dict[str, Any]:
    """Обновить проверку доступа исполнителя — названное условие выпуска.

    Проверка устаревает (сутки), и просроченная останавливает выпуск с точным
    текстом. Это отдельная штатная операция очереди, а не произвольная
    команда: `access-check` ничего не выкладывает.
    """
    from factory.cell import queue as очередь

    site_id = _site_id(str(аргументы.get("site") or ""))
    try:
        заявка = очередь.собрать(site_id, "", "", operation="access-check")
        подача = очередь.подать(заявка)
    except очередь.RequestRejected as ош:
        raise ОшибкаИнструмента(f"{site_id}: {ош}") from None
    except OSError as ош:
        raise ОшибкаИнструмента(
            f"{site_id}: очередь недоступна ({type(ош).__name__})") from None
    return {"version": ВЕРСИЯ_ОБОЛОЧКИ, "request_id": заявка.request_id,
            "submission": подача.get("status"),
            "next_action": "результат — operation_result по этому request_id",
            "environment": окружение()}


# ------------------------------- публикация материала: существующие операции
#
# Операции публикации в фабрике УЖЕ есть: `editorial.подготовить`,
# `публиковать`, `подтвердить`, `снять`, `восстановить` — с проверкой
# материала, доставкой через очередь и подтверждением на ответе витрины. У Qwen
# их не было, поэтому «опубликуй материал» он выполнить не мог. Здесь они
# подключаются как есть; ни одной своей проверки качества или прав тут нет.
#
# Право писать выводится из ВОЗМОЖНОСТЕЙ сайта (`deliver`, `display`): у витрины
# без читателя правок записанный текст на странице не появится, и операция
# отказывает — это её собственное решение, а не ограничение моста.


def инструмент_факты(аргументы: dict) -> dict[str, Any]:
    """Факты каталога по произведению — источник для текста, не выдумка."""
    сайт = str(аргументы.get("site") or "").strip()
    слаг = str(аргументы.get("slug") or "").strip() or None
    if not сайт:
        raise ОшибкаИнструмента("нужен параметр site")
    try:
        итог = editorial.факты(сайт, слаг)
    except (editorial.ОперацияОтклонена, indexing.Отказано) as ош:
        raise ОшибкаИнструмента(str(ош)) from None
    return {"version": ВЕРСИЯ_ОБОЛОЧКИ, "facts": итог, "environment": окружение()}


def инструмент_состояния_материалов(аргументы: dict) -> dict[str, Any]:
    """Что подготовлено и опубликовано у сайта: состояния и отпечатки."""
    сайт = str(аргументы.get("site") or "").strip()
    if not сайт:
        raise ОшибкаИнструмента("нужен параметр site")
    try:
        итог = editorial.состояние(сайт)
    except (editorial.ОперацияОтклонена, indexing.Отказано) as ош:
        raise ОшибкаИнструмента(str(ош)) from None
    return {"version": ВЕРСИЯ_ОБОЛОЧКИ, "editorial": итог,
            "environment": окружение()}


def инструмент_подготовки(аргументы: dict) -> dict[str, Any]:
    """Подготовить материал: проверка качества и фактов ДО публикации."""
    сайт = str(аргументы.get("site") or "").strip()
    слаг = str(аргументы.get("slug") or "").strip()
    тело = str(аргументы.get("body") or "")
    if not (сайт and слаг and тело):
        raise ОшибкаИнструмента("нужны параметры site, slug и body")
    try:
        итог = editorial.подготовить(сайт, слаг, тело,
                                     author=str(аргументы.get("author") or "qwen"))
    except (editorial.ОперацияОтклонена, indexing.Отказано) as ош:
        raise ОшибкаИнструмента(str(ош)) from None
    return {"version": ВЕРСИЯ_ОБОЛОЧКИ, "prepared": итог,
            "ok": not итог.get("quality_problems"),
            "environment": окружение()}


def инструмент_публикации(аргументы: dict) -> dict[str, Any]:
    """Опубликовать ПОДГОТОВЛЕННЫЙ материал штатной операцией."""
    сайт = str(аргументы.get("site") or "").strip()
    слаг = str(аргументы.get("slug") or "").strip()
    if not (сайт and слаг):
        raise ОшибкаИнструмента("нужны параметры site и slug")
    try:
        итог = editorial.публиковать(
            сайт, слаг, author=str(аргументы.get("author") or "qwen"),
            expected_generation=str(аргументы.get("expect_generation") or "") or None)
    except (editorial.ОперацияОтклонена, indexing.Отказано) as ош:
        raise ОшибкаИнструмента(str(ош)) from None
    return {"version": ВЕРСИЯ_ОБОЛОЧКИ, "result": итог,
            "confirmed": итог.get("state") == "confirmed",
            "environment": окружение()}


def инструмент_снятия(аргументы: dict) -> dict[str, Any]:
    """Снять опубликованный материал — откат публикации той же операцией."""
    сайт = str(аргументы.get("site") or "").strip()
    слаг = str(аргументы.get("slug") or "").strip()
    if not (сайт and слаг):
        raise ОшибкаИнструмента("нужны параметры site и slug")
    try:
        итог = editorial.снять(сайт, слаг,
                               author=str(аргументы.get("author") or "qwen"))
    except (editorial.ОперацияОтклонена, indexing.Отказано) as ош:
        raise ОшибкаИнструмента(str(ош)) from None
    return {"version": ВЕРСИЯ_ОБОЛОЧКИ, "result": итог,
            "confirmed": итог.get("state") == "confirmed",
            "environment": окружение()}


# --------------------------------------------- SEO страницы: измерение, не оценка
#
# Три инструмента сессии Qwen (`audit_page_seo`, `inspect_sitemap`,
# `explain_url_scope`) обслуживает сторонняя служба, и они отказывали. Здесь
# они закрываются ИЗМЕРЕНИЕМ живого домена теми же помощниками, которыми
# пользуется вердикт индексации (`indexing.сигналы`, `_ответ_с_цепочкой`), без
# прогнозов позиций и без оценок «хорошо/плохо»: инструмент сообщает факты и
# называет контракт семейства, а вывод делает человек.
#
# Инструменты фабрики `factory/seo/*` сюда НЕ подключены сознательно: они
# работают по каталогу СБОРКИ пакета DLE, а у переносимых ячеек такого каталога
# нет. Подключить их к домену ячейки значило бы выдать чужой инструмент за
# подходящий.


def _страница_домена(домен: str, путь: str = "/") -> dict[str, Any]:
    # Помощник возвращает ЧЕТЫРЕ величины: код, заголовки, тело и пройденную
    # цепочку перенаправлений. Цепочка нужна в ответе: заголовки
    # перенаправления — не заголовки страницы, и путать их уже доводилось.
    код, заголовки, тело, цепочка = indexing._ответ_с_цепочкой(
        f"https://{домен}{путь}")
    return {"http": код, "headers": заголовки, "body": тело, "chain": цепочка}


def инструмент_seo_страницы(аргументы: dict) -> dict[str, Any]:
    """Измеренные SEO-признаки одной страницы живого домена. Только чтение."""
    сайт = str(аргументы.get("site") or аргументы.get("domain") or "").strip()
    путь = str(аргументы.get("path") or "/")
    if not путь.startswith("/"):
        путь = "/" + путь
    try:
        с = editorial._сайт(сайт)
    except editorial.ОперацияОтклонена as ош:
        raise ОшибкаИнструмента(str(ош)) from None
    сиг = indexing.сигналы(с.domain, порт=indexing.порт_приложения(с.site_id))
    стр = _страница_домена(с.domain, путь)
    тело = стр.get("body") or ""
    import re as _re

    def первое(шаблон: str) -> str:
        m = _re.search(шаблон, тело, _re.I | _re.S)
        return (m.group(1).strip()[:300] if m else "")

    режим, запреты = indexing.оценить(сиг)
    итог = {
        "version": ВЕРСИЯ_ОБОЛОЧКИ, "site": с.domain, "site_id": с.site_id,
        "path": путь, "adapter": с.adapter or None,
        "http": стр.get("http"), "redirect_chain": стр.get("chain"),
        "title": первое(r"<title[^>]*>(.*?)</title>"),
        "meta_description": первое(r'<meta[^>]+name=["\']description["\'][^>]+content=["\'](.*?)["\']'),
        "meta_robots": первое(r'<meta[^>]+name=["\']robots["\'][^>]+content=["\'](.*?)["\']'),
        "canonical": первое(r'<link[^>]+rel=["\']canonical["\'][^>]+href=["\'](.*?)["\']'),
        "h1": первое(r"<h1[^>]*>(.*?)</h1>"),
        "x_robots_tag": сиг.get("x_robots_values"),
        "robots_txt_http": сиг.get("robots_txt_http"),
        "sitemap_http": сиг.get("sitemap_http"),
        "public_mode": режим, "denying_signals": запреты,
        "contract": indexing.контракт(с.adapter) or None,
        "note": ("это ИЗМЕРЕНИЕ, а не оценка: прогнозов позиций и трафика "
                 "инструмент не делает"),
        "environment": окружение(),
    }
    return итог


def инструмент_карты_сайта(аргументы: dict) -> dict[str, Any]:
    """Карта сайта домена: код ответа, число адресов, хост и первые записи."""
    сайт = str(аргументы.get("site") or аргументы.get("domain") or "").strip()
    try:
        с = editorial._сайт(сайт)
    except editorial.ОперацияОтклонена as ош:
        raise ОшибкаИнструмента(str(ош)) from None
    стр = _страница_домена(с.domain, str(аргументы.get("path") or "/sitemap.xml"))
    тело = стр.get("body") or ""
    import re as _re

    адреса = _re.findall(r"<loc>\s*([^<\s]+)\s*</loc>", тело, _re.I)
    чужие = sorted({а for а in адреса
                    if с.domain not in а.split("//", 1)[-1].split("/", 1)[0]})
    return {
        "version": ВЕРСИЯ_ОБОЛОЧКИ, "site": с.domain, "site_id": с.site_id,
        "http": стр.get("http"), "urls": len(адреса),
        "first_urls": адреса[:10],
        "foreign_hosts": чужие[:10],
        "is_index": "<sitemapindex" in тело.lower(),
        "bytes": len(тело),
        "reason": ("" if адреса else
                   "адресов не найдено: либо карта пуста, либо ответ не XML — "
                   "код ответа и размер названы рядом"),
        "environment": окружение(),
    }


def инструмент_области_адреса(аргументы: dict) -> dict[str, Any]:
    """Чей это адрес и что о нём говорят реестр и слой nginx."""
    адрес = str(аргументы.get("url") or аргументы.get("site") or "").strip()
    if not адрес:
        raise ОшибкаИнструмента("нужен параметр url")
    без_схемы = адрес.split("//", 1)[-1]
    хост = без_схемы.split("/", 1)[0]
    путь = "/" + без_схемы.split("/", 1)[1] if "/" in без_схемы else "/"
    сайты = editorial._реестр(опрашивать_сеть=False)
    свой = next((s for s in сайты if s.domain == хост), None)
    if свой is None:
        return {"version": ВЕРСИЯ_ОБОЛОЧКИ, "url": адрес, "host": хост,
                "in_registry": False,
                "reason": (f"домена {хост} нет в авторитетном реестре фабрики "
                           f"({len(сайты)} записей): адрес вне её области"),
                "environment": окружение()}
    слой = indexing.слой_nginx(свой.site_id, свой.domain)
    служебный = any(путь.startswith(п) for п in
                    ("/poster/", "/api/", "/healthz", "/__", "/.well-known/"))
    return {
        "version": ВЕРСИЯ_ОБОЛОЧКИ, "url": адрес, "host": хост, "path": путь,
        "in_registry": True, "site_id": свой.site_id,
        "adapter": свой.adapter or None, "account": свой.account,
        "published_release": свой.published_release or None,
        "service_path": служебный,
        "nginx_layer": {"mode": слой.get("mode"), "denying": слой.get("denying")},
        "note": ("служебные пути закрыты для обхода независимо от режима "
                 "индексации домена" if служебный else
                 "обычный путь витрины: режим определяется слоями индексации"),
        "environment": окружение(),
    }


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
    "release_plan": {
        "обработчик": инструмент_плана_выпуска,
        "описание": ("Что было бы выпущено: ветка, коммит последнего успешного "
                     "прогона CI, его номер, digest артефакта, живой коммит и "
                     "препятствия предполётных проверок. Ничего не меняет."),
        "схема": {"type": "object", "properties": {
            "site": {"type": "string", "description": "домен или site_id"}},
            "required": ["site"], "additionalProperties": False},
    },
    "release_site": {
        "обработчик": инструмент_выпуска,
        "описание": ("Подать заявку на выпуск последнего успешного прогона CI. "
                     "Выкладывает привилегированный исполнитель: он проверяет "
                     "происхождение из CI, digest артефакта и защищённые "
                     "данные, ставит кандидата, прогревает его и переключает "
                     "трафик только после проверки ответом, а при неуспехе "
                     "возвращает трафик сам."),
        "схема": {"type": "object", "properties": {
            "site": {"type": "string", "description": "домен или site_id"}},
            "required": ["site"], "additionalProperties": False},
    },
    "operation_result": {
        "обработчик": инструмент_результата,
        "описание": ("Результат заявки по request_id: судьба в очереди, исход "
                     "операции, этап, build_id, ошибка, пройденные этапы и "
                     "путь к журналу результата."),
        "схема": {"type": "object", "properties": {
            "request_id": {"type": "string"}},
            "required": ["request_id"], "additionalProperties": False},
    },
    "rollback_site": {
        "обработчик": инструмент_откката_сайта,
        "описание": ("Вернуть трафик действующей версии штатной заявкой "
                     "rollback. Нужен commit выпуска, от которого откат."),
        "схема": {"type": "object", "properties": {
            "site": {"type": "string"},
            "commit": {"type": "string"},
            "note": {"type": "string"}},
            "required": ["site", "commit"], "additionalProperties": False},
    },
    "refresh_executor_access": {
        "обработчик": инструмент_проверки_доступа,
        "описание": ("Обновить проверку доступа исполнителя (операция "
                     "access-check). Просроченная проверка останавливает "
                     "выпуск; ничего не выкладывает."),
        "схема": {"type": "object", "properties": {
            "site": {"type": "string"}},
            "required": ["site"], "additionalProperties": False},
    },
    "rollback_indexing": {
        "обработчик": инструмент_отката,
        "описание": ("Откат последней смены режима: журнал называет предыдущее "
                     "состояние, возврат идёт той же штатной операцией с её "
                     "предпроверками и подтверждением публичным ответом."),
        "схема": {"type": "object", "properties": {
            "site": {"type": "string"},
            "author": {"type": "string"}},
            "required": ["site"], "additionalProperties": False},
    },
    "editorial_facts": {
        "обработчик": инструмент_факты,
        "описание": ("Факты каталога по произведению: источник для текста. "
                     "Сведений, которых здесь нет, в материале быть не может."),
        "схема": {"type": "object", "properties": {
            "site": {"type": "string"}, "slug": {"type": "string"}},
            "required": ["site"], "additionalProperties": False},
    },
    "editorial_status": {
        "обработчик": инструмент_состояния_материалов,
        "описание": ("Что подготовлено и опубликовано у сайта: состояния, "
                     "отпечатки, доступные операции витрины."),
        "схема": {"type": "object", "properties": {
            "site": {"type": "string"}},
            "required": ["site"], "additionalProperties": False},
    },
    "prepare_material": {
        "обработчик": инструмент_подготовки,
        "описание": ("Подготовить материал: проверки качества и фактов идут ДО "
                     "публикации и возвращаются списком. Ничего не публикует."),
        "схема": {"type": "object", "properties": {
            "site": {"type": "string"}, "slug": {"type": "string"},
            "body": {"type": "string"}, "author": {"type": "string"}},
            "required": ["site", "slug", "body"], "additionalProperties": False},
    },
    "publish_material": {
        "обработчик": инструмент_публикации,
        "описание": ("Опубликовать подготовленный материал штатной операцией: "
                     "доставка очередью, подтверждение ответом витрины. У "
                     "витрины без читателя правок операция отказывает."),
        "схема": {"type": "object", "properties": {
            "site": {"type": "string"}, "slug": {"type": "string"},
            "expect_generation": {"type": "string"},
            "author": {"type": "string"}},
            "required": ["site", "slug"], "additionalProperties": False},
    },
    "unpublish_material": {
        "обработчик": инструмент_снятия,
        "описание": "Снять опубликованный материал — откат публикации.",
        "схема": {"type": "object", "properties": {
            "site": {"type": "string"}, "slug": {"type": "string"},
            "author": {"type": "string"}},
            "required": ["site", "slug"], "additionalProperties": False},
    },
    "audit_page_seo": {
        "обработчик": инструмент_seo_страницы,
        "описание": ("ИЗМЕРЕННЫЕ признаки одной страницы живого домена: код "
                     "ответа, title, description, canonical, meta robots, H1, "
                     "X-Robots-Tag, код robots.txt и карты сайта, публичный "
                     "режим и контракт семейства. Оценок и прогнозов не даёт."),
        "схема": {"type": "object", "properties": {
            "site": {"type": "string", "description": "домен или site_id"},
            "domain": {"type": "string"},
            "path": {"type": "string", "description": "путь страницы, по умолчанию /"}},
            "additionalProperties": False},
    },
    "inspect_sitemap": {
        "обработчик": инструмент_карты_сайта,
        "описание": ("Карта сайта домена: код ответа, число адресов, признак "
                     "индекса карт, первые адреса и ЧУЖИЕ хосты в них."),
        "схема": {"type": "object", "properties": {
            "site": {"type": "string"}, "domain": {"type": "string"},
            "path": {"type": "string", "description": "по умолчанию /sitemap.xml"}},
            "additionalProperties": False},
    },
    "explain_url_scope": {
        "обработчик": инструмент_области_адреса,
        "описание": ("Чей это адрес: есть ли хост в авторитетном реестре "
                     "фабрики, какой это сайт и семейство, выложенный выпуск, "
                     "служебный ли путь и режим слоя nginx."),
        "схема": {"type": "object", "properties": {
            "url": {"type": "string"}, "site": {"type": "string"}},
            "additionalProperties": False},
    },
    "analytics_readiness": {
        "обработчик": инструмент_аналитики,
        "описание": ("Готовность аналитики домена по авторитетному реестру "
                     "фабрики config/analytics.json: вердикт из закрытого "
                     "перечня, counter_id, сбор, хосты, цели и источник. "
                     "Только чтение; секреты не выводятся."),
        "схема": {"type": "object", "properties": {
            "site": {"type": "string", "description": "домен или site_id"},
            "domain": {"type": "string",
                       "description": "то же, что site: имя из сессии Qwen"}},
            "additionalProperties": False},
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


def редактированное(текст: str) -> str:
    """Текст ошибки без секретов.

    Мост читает реестры и запускает штатные операции, и в сообщение об ошибке
    может попасть значение из окружения. Редактирование здесь — последняя
    точка перед отправкой клиенту: пропустить её значило бы доверять каждому
    сообщению по отдельности.
    """
    try:
        from factory import redaction

        return redaction.redact(текст)
    except Exception:  # noqa: BLE001 — редактирование не вправе ронять ответ
        return текст


def место_исключения(ош: BaseException) -> str:
    """Файл и строка последнего кадра: место, а не весь след стека."""
    try:
        import traceback

        кадры = traceback.extract_tb(ош.__traceback__)
        if not кадры:
            return ""
        к = кадры[-1]
        return f"{pathlib.Path(к.filename).name}:{к.lineno} в {к.name}"
    except Exception:  # noqa: BLE001
        return ""


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


def записать_вызов(имя: str, аргументы: dict, начало: float, *,
                   исход: str, причина: str = "") -> None:
    """Строка журнала на каждый вызов инструмента. В stderr, не в протокол.

    Зачем. `log_message` обработчика HTTP подавлен (журнал пишет вызывающая
    сторона), и на стороне фабрики не оставалось НИЧЕГО: указание «найди
    исходное исключение по журналам» упиралось в их отсутствие. Теперь каждый
    вызов оставляет след: имя инструмента, исход, длительность и ИМЕНА
    аргументов.

    Значения аргументов не пишутся. Домен секретом не является, но правило
    одно для всех полей: имя — да, значение — нет; текст причины проходит
    через `factory.redaction`. Поток — stderr, потому что stdout у транспорта
    stdio занят самим протоколом.
    """
    try:
        запись = {
            "at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "tool": имя, "outcome": исход,
            "ms": int((time.monotonic() - начало) * 1000),
            "args": sorted(аргументы or {}),
        }
        if причина:
            запись["reason"] = редактированное(причина)[:300]
        sys.stderr.write(json.dumps(запись, ensure_ascii=False) + "\n")
        sys.stderr.flush()
    except Exception:  # noqa: BLE001 — журнал не вправе ронять ответ
        pass


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
        начало = time.monotonic()
        try:
            полезное = вызвать(имя, аргументы)
            записать_вызов(имя, аргументы, начало, исход="ok")
        except ОшибкаИнструмента as ош:
            # ОТКАЗ, а не пустой успех: клиент обязан увидеть ошибку.
            записать_вызов(имя, аргументы, начало, исход="refused",
                           причина=str(ош))
            return _ответ(идент, {**_текст({
                "error": редактированное(str(ош)), "tool": имя,
                "arguments": sorted(аргументы),
                "environment": окружение()}), "isError": True})
        except Exception as ош:  # noqa: BLE001 — см. ниже
            записать_вызов(имя, аргументы, начало, исход="unexpected",
                           причина=f"{type(ош).__name__}: {ош}")
            # ЛЮБОЕ другое исключение тоже обязано вернуться ОТВЕТОМ, а не
            # уйти наружу. Иначе клиент получает обрыв запроса и показывает
            # «Error executing tool <имя>» — строку без причины, домена и
            # источника. Именно так выглядел отказ инструмента аналитики, и
            # разобрать его по такому тексту нельзя.
            #
            # В ответ идёт тип исключения, отредактированный текст и МЕСТО
            # (файл и строка последнего кадра): этого достаточно, чтобы найти
            # причину, и недостаточно, чтобы выдать секрет — весь текст
            # проходит через `factory.redaction`.
            return _ответ(идент, {**_текст({
                "error": f"{type(ош).__name__}: {редактированное(str(ош))}",
                "tool": имя, "arguments": sorted(аргументы),
                "unexpected": True,
                "where": место_исключения(ош),
                "next_action": ("это дефект инструмента, а не отказ операции: "
                                "сообщите error и where — по ним причина "
                                "находится по коду и журналам"),
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
                               "sites": len(значение["sites"]),
                               "sites_digest":
                                   значение["registry"]["sites_digest"][:16]})
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
