"""Мост инструментов Qwen к ФАКТИЧЕСКОЙ фабрике.

Проверяется поведение, из-за которого мост и понадобился: сторонний источник
отвечал `{"version": 1, "sites": []}` и при этом `registry.valid: true` —
согласованный пустой успех, по которому нельзя отличить «сайтов нет» от
«спросили не ту машину». Здесь пустой успех невозможен по построению.
"""
from __future__ import annotations

import json
import pathlib
import sys

import pytest

КОРЕНЬ = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(КОРЕНЬ))

from factory.qwen import mcp, registry  # noqa: E402

#: Имена, которые УЖЕ есть в сессии Qwen. Совпадение обязательно: иначе
#: переключение коннектора потребует правок на стороне клиента, а задача
#: ровно в том, чтобы этого не требовалось.
ИМЕНА_КЛИЕНТА = ("system_readiness", "list_registered_sites", "get_registered_site")


def test_имена_инструментов_совпадают_с_имеющимися_у_qwen():
    объявлены = {и["name"] for и in
                 mcp.обработать({"jsonrpc": "2.0", "id": 1,
                                 "method": "tools/list"})["result"]["tools"]}
    for имя in ИМЕНА_КЛИЕНТА:
        assert имя in объявлены, (
            f"{имя}: имя не совпало с тем, что уже есть у Qwen — переключение "
            "коннектора потребует правок на стороне клиента")
    # Операции режима тоже объявлены: без них Qwen видит только чтение.
    for имя in ("domain_indexing_readiness", "set_indexing_mode",
                "confirm_indexing", "indexing_journal"):
        assert имя in объявлены, имя


def test_список_сайтов_в_оболочке_клиента_и_непустой():
    итог = mcp.вызвать("list_registered_sites", {})
    assert итог["version"] == 1, "оболочка не та, которую разбирает клиент"
    assert итог["sites"], "авторитетный реестр не бывает пустым"
    # Источник называется в ответе: без него «пусто» неотличимо от «не тот файл».
    источники = итог["registry"]["sources"]
    assert источники["site_cells"]["path"].endswith("config/site-cells.json")
    assert источники["site_cells"]["count"] == len(
        [с for с in итог["sites"] if not с["site_id"].startswith("(вне реестра)")])
    # Идентичность окружения — в каждом ответе.
    окр = итог["environment"]
    assert окр["host"] and окр["user"] and окр["cwd"]
    assert окр["instruction"]["version"] and окр["code"]["commit"]


def test_нечитаемый_реестр_это_ошибка_а_не_пустой_список(monkeypatch):
    """Ровно то, из-за чего задача и возникла.

    Пустой успешный список означает «сайтов нет», а на самом деле означал
    «источник не тот». Нечитаемый источник обязан быть отказом.
    """
    monkeypatch.setattr(registry, "РЕЕСТР_ЯЧЕЕК",
                        pathlib.Path("/нет/такого/site-cells.json"))
    for имя, аргументы in (("list_registered_sites", {}),
                           ("get_registered_site", {"site": "any.example"}),
                           ("system_readiness", {})):
        with pytest.raises(mcp.ОшибкаИнструмента) as ош:
            mcp.вызвать(имя, аргументы)
        assert "site-cells.json" in str(ош.value), имя


def test_прочитанный_но_пустой_реестр_тоже_отказ(monkeypatch, tmp_path):
    """Пустой список при прочитанном файле — состояние источника, не факт."""
    пустой = tmp_path / "site-cells.json"
    пустой.write_text(json.dumps({"schema_version": 1, "cells": []}),
                      encoding="utf-8")
    monkeypatch.setattr(registry, "РЕЕСТР_ЯЧЕЕК", пустой)
    сетевой = tmp_path / "network-allowlist.yaml"
    сетевой.write_text("hosts: []\n", encoding="utf-8")
    monkeypatch.setattr(registry, "СЕТЕВОЙ_СПИСОК", сетевой)
    with pytest.raises(mcp.ОшибкаИнструмента) as ош:
        mcp.вызвать("list_registered_sites", {})
    assert "ни одного сайта" in str(ош.value) or "не содержит" in str(ош.value)


def test_отказ_уходит_клиенту_признаком_ошибки(monkeypatch):
    """`tools/call` на отказе обязан вернуть isError, а не правдоподобный JSON."""
    monkeypatch.setattr(registry, "РЕЕСТР_ЯЧЕЕК",
                        pathlib.Path("/нет/такого/site-cells.json"))
    ответ = mcp.обработать({"jsonrpc": "2.0", "id": 7, "method": "tools/call",
                            "params": {"name": "list_registered_sites",
                                       "arguments": {}}})
    результат = ответ["result"]
    assert результат["isError"] is True
    полезное = json.loads(результат["content"][0]["text"])
    assert полезное["error"], полезное
    assert полезное["environment"]["host"], "окружение обязано быть и в отказе"
    assert "sites" not in полезное, "в отказе не может быть списка сайтов"


def test_неизвестный_сайт_и_неизвестный_инструмент_отказ():
    with pytest.raises(mcp.ОшибкаИнструмента):
        mcp.вызвать("get_registered_site", {"site": "нет-такого.example"})
    with pytest.raises(mcp.ОшибкаИнструмента):
        mcp.вызвать("такого-инструмента-нет", {})


def test_смена_режима_проверяет_значение_и_не_обходит_предпроверки():
    with pytest.raises(mcp.ОшибкаИнструмента) as ош:
        mcp.вызвать("set_indexing_mode", {"site": "lordserials22.info",
                                          "mode": "включить"})
    assert "open или closed" in str(ош.value)
    # Открытие домена без разрешений отклоняется ШТАТНОЙ предпроверкой, и
    # причина приходит от неё, а не от моста.
    with pytest.raises(mcp.ОшибкаИнструмента) as ош:
        mcp.вызвать("set_indexing_mode", {"site": "lordserials22.info",
                                          "mode": "open"})
    текст = str(ош.value)
    assert "предпроверка не пройдена" in текст, текст
    assert "release_permits_open" in текст or "владелец" in текст, текст


def test_мост_не_заводит_второй_реестр_и_второй_оркестратор():
    """Мост обязан ВЫЗЫВАТЬ существующее, а не повторять его.

    Второй реестр разошёлся бы с первым, и именно такое расхождение привело к
    задаче. Проверяется исходник: ни своего пути к реестру, ни своей логики
    разрешений, ни произвольной команды оболочки.
    """
    import ast

    исходник = (КОРЕНЬ / "factory" / "qwen" / "mcp.py").read_text(encoding="utf-8")
    дерево = ast.parse(исходник)

    # 1. Ни одного ПУТИ, построенного мостом к реестру. Упоминание имени файла
    #    в описании инструмента — это документация для Qwen, а не источник;
    #    проверяются именно вызовы `pathlib.Path(...)`.
    пути: list[str] = []
    for узел in ast.walk(дерево):
        if not isinstance(узел, ast.Call):
            continue
        имя = ast.unparse(узел.func)
        if имя not in ("pathlib.Path", "Path"):
            continue
        for арг in узел.args:
            if isinstance(арг, ast.Constant) and isinstance(арг.value, str):
                пути.append(арг.value)
            elif isinstance(арг, ast.JoinedStr):
                пути.append(ast.unparse(арг))
    свои = [п for п in пути
            if "site-cells.json" in п or "network-allowlist" in п
            or "/var/lib/site-cells" in п or "/srv/sites/indexing" in п]
    assert not свои, (
        f"мост строит путь к реестру или очереди сам: {свои} — это второй "
        "знающий, и он разойдётся с первым при первом же переносе каталога")

    # 2. Делегирование существующему, а не повтор его логики.
    тело = исходник.split('"""', 2)[2]
    assert "registry.собрать(" in тело, "список сайтов обязан идти из реестра"
    assert "indexing.установить(" in тело, "смена режима — штатной операцией"
    assert "indexing.готовность(" in тело, "вердикт — штатной операцией"

    # 3. Ни произвольной оболочки, ни своей логики разрешений.
    for запрет in ("os.system", "shell=True", "open_authorized",
                   "release_permits_open ="):
        assert запрет not in тело, (
            f"в мосте есть {запрет!r}: либо произвольная оболочка, либо своя "
            "логика разрешений")
    команды = [ast.unparse(у) for у in ast.walk(дерево)
               if isinstance(у, ast.Call)
               and ast.unparse(у.func) in ("subprocess.run", "subprocess.Popen")]
    for вызов in команды:
        assert '"git"' in вызов or "'git'" in вызов, (
            f"мост запускает посторонний процесс: {вызов[:80]}")


def test_протокол_отвечает_на_инициализацию_и_пинг():
    ответ = mcp.обработать({"jsonrpc": "2.0", "id": 1, "method": "initialize",
                            "params": {"protocolVersion": "2024-11-05"}})
    сведения = ответ["result"]["serverInfo"]
    assert сведения["name"] == "site-factory"
    assert сведения["version"] == mcp.ИНСТРУКЦИЯ_ВЕРСИЯ
    assert сведения["environment"]["host_matches_factory"] in (True, False)
    assert mcp.обработать({"jsonrpc": "2.0", "method": "notifications/initialized"}) is None
    assert mcp.обработать({"jsonrpc": "2.0", "id": 2, "method": "ping"})["result"] == {}
    плохой = mcp.обработать({"jsonrpc": "2.0", "id": 3, "method": "нет/такого"})
    assert плохой["error"]["code"] == -32601


# --- транспорт HTTP и режим только чтения --------------------------------

def test_только_чтение_скрывает_и_отклоняет_пишущий_инструмент(monkeypatch):
    """Ограничение подключения обязано быть свойством сервера.

    На этапе приёмки коннектор объявлен read-only. Сервер, объявляющий
    пишущий инструмент «потому что в описании сказано только читать»,
    полагается на дисциплину клиента — а должен не предлагать его вовсе.
    """
    monkeypatch.setattr(mcp, "ТОЛЬКО_ЧТЕНИЕ", True)
    объявлены = {и["name"] for и in
                 mcp.обработать({"jsonrpc": "2.0", "id": 1,
                                 "method": "tools/list"})["result"]["tools"]}
    assert "set_indexing_mode" not in объявлены, объявлены
    for имя in ИМЕНА_КЛИЕНТА:
        assert имя in объявлены, f"{имя}: чтение не должно пропадать"
    with pytest.raises(mcp.ОшибкаИнструмента) as ош:
        mcp.вызвать("set_indexing_mode", {"site": "lordserials22.info",
                                          "mode": "closed"})
    текст = str(ош.value)
    assert "только чтения" in текст
    assert "indexing-set" in текст, (
        "отказ обязан называть, ЧЕМ операция выполняется, а не просто "
        "запрещать")
    # Признак режима виден клиенту сразу, без вызова инструментов.
    сведения = mcp.обработать({"jsonrpc": "2.0", "id": 2,
                               "method": "initialize"})["result"]["serverInfo"]
    assert сведения["read_only"] is True


def test_адрес_вне_петли_без_разрешения_отклоняется():
    """Управляющая точка фабрики в интернет не публикуется.

    Привязка к публичному адресу — не настройка, а решение; по умолчанию её
    нет, и ошибка называет, чем заменить (туннель или сеть контейнеров).
    """
    with pytest.raises(SystemExit) as ош:
        mcp.служить_http("0.0.0.0", 9000)
    текст = str(ош.value)
    assert "вне петли" in текст and "туннелем" in текст
    assert mcp._петля("127.0.0.1") and mcp._петля("localhost")
    assert not mcp._петля("0.0.0.0") and not mcp._петля("83.237.185.70")


def test_транспорт_http_отвечает_тем_же_протоколом(tmp_path):
    """Тот же JSON-RPC, что по stdio: POST /mcp — один ответ.

    Проверяется НАСТОЯЩИЙ сокет, а не обработчик в отрыве: коннектор Open
    WebUI ходит по HTTP, и подтверждать надо то, что он получит.
    """
    import socket as _socket
    import threading
    import urllib.error
    import urllib.request

    c = _socket.socket()
    c.bind(("127.0.0.1", 0))
    порт = c.getsockname()[1]
    c.close()
    готов = threading.Event()
    держатель: dict[str, object] = {}

    def запустить():
        mcp.служить_http("127.0.0.1", порт,
                         сервер_готов=lambda с: (держатель.update(сервер=с),
                                                 готов.set()))

    поток = threading.Thread(target=запустить, daemon=True)
    поток.start()
    assert готов.wait(20), "сервер HTTP не поднялся"
    try:
        def позвать(полезное, принимает="application/json"):
            зап = urllib.request.Request(
                f"http://127.0.0.1:{порт}/mcp",
                data=json.dumps(полезное, ensure_ascii=False).encode("utf-8"),
                headers={"Content-Type": "application/json",
                         "Accept": принимает})
            о = urllib.request.urlopen(зап, timeout=30)
            return о.status, о.headers.get("Content-Type", ""), о.read().decode("utf-8")

        код, тип, тело = позвать({"jsonrpc": "2.0", "id": 1,
                                  "method": "initialize"})
        assert код == 200 and "application/json" in тип
        сведения = json.loads(тело)["result"]["serverInfo"]
        assert сведения["name"] == "site-factory"
        assert сведения["environment"]["host"], "ответ без идентичности окружения"

        код, _, тело = позвать({"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
        имена = {и["name"] for и in json.loads(тело)["result"]["tools"]}
        assert ИМЕНА_КЛИЕНТА[1] in имена

        # Клиент, просящий поток, получает тот же ответ одним событием.
        код, тип, тело = позвать(
            {"jsonrpc": "2.0", "id": 3, "method": "tools/call",
             "params": {"name": "system_readiness", "arguments": {}}},
            принимает="application/json, text/event-stream")
        assert "text/event-stream" in тип, тип
        конверт = json.loads(тело.split("data: ", 1)[1])
        полезное = json.loads(конверт["result"]["content"][0]["text"])
        assert полезное["registry"]["valid"] is True
        assert полезное["registry"]["sources"]["site_cells"]["path"].endswith(
            "config/site-cells.json")

        # Уведомление без id — 202 и ни байта тела.
        зап = urllib.request.Request(
            f"http://127.0.0.1:{порт}/mcp",
            data=json.dumps({"jsonrpc": "2.0",
                             "method": "notifications/initialized"}).encode(),
            headers={"Content-Type": "application/json"})
        assert urllib.request.urlopen(зап, timeout=20).status == 202

        # Поток, открываемый сервером, не поддержан — и причина названа.
        with pytest.raises(urllib.error.HTTPError) as ош:
            urllib.request.urlopen(f"http://127.0.0.1:{порт}/mcp", timeout=20)
        assert ош.value.code == 405
        assert json.loads(ош.value.read())["error"]["code"] == "stream_not_supported"

        # Готовность: без неё подключение нечем проверить снаружи.
        о = urllib.request.urlopen(f"http://127.0.0.1:{порт}/healthz", timeout=20)
        здоровье = json.loads(о.read())
        assert здоровье["ready"] is True
        assert здоровье["instruction_version"] == mcp.ИНСТРУКЦИЯ_ВЕРСИЯ
    finally:
        сервер = держатель.get("сервер")
        if сервер is not None:
            сервер.shutdown()
