"""REQ-FLEET-OBSERVE: измеряется то, что можно измерить; остальное называется.

Сборщик — единственное место, где центр управления соприкасается с внешним
миром. Соблазн у такого места один: подставить ноль там, где источник не
ответил, и получить ровный экран без пустот. Ровный экран здесь опаснее
пустого: по нулю принимают решение, по «не подключено» — нет.
"""

from __future__ import annotations

import importlib.util
import json
import sys
import time
from pathlib import Path

import pytest

РЕПО = Path(__file__).resolve().parents[2]
СЦЕНАРИЙ = РЕПО / "automation" / "host" / "fleet-observe.py"


@pytest.fixture(scope="module")
def сборщик():
    спец = importlib.util.spec_from_file_location("fleet_observe_под_тестом", СЦЕНАРИЙ)
    модуль = importlib.util.module_from_spec(спец)
    sys.modules["fleet_observe_под_тестом"] = модуль
    спец.loader.exec_module(модуль)
    return модуль


@pytest.fixture()
def корень(tmp_path):
    рантайм = tmp_path / "runtime" / "site-1"
    релиз = рантайм / "releases" / "rel1"
    релиз.mkdir(parents=True)
    (релиз / "release-manifest.json").write_text(json.dumps({
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "content_count": 1234,
    }), encoding="utf-8")
    (рантайм / "current").symlink_to(релиз)
    return tmp_path


НАСТРОЙКИ = {
    "runtime": {"root": None},
    "collectors": {
        "analytics": {"enabled": False, "reason": "учётные данные не переданы"},
        "search_console": {"enabled": False, "reason": "доступ не выдан"},
    },
}


def _настройки(корень):
    из = json.loads(json.dumps(НАСТРОЙКИ))
    из["runtime"]["root"] = str(корень / "runtime")
    return из


def test_свежесть_и_счёт_измеряются(сборщик, корень):
    из = сборщик.собрать(корень, "site-1", _настройки(корень), порт=None, журнал=None)
    assert из["freshnessSeconds"]["state"] == "CONNECTED"
    assert из["freshnessSeconds"]["value"] is not None
    assert из["contentCountObserved"]["value"] == 1234


def test_неподключённая_аналитика_не_даёт_нулей(сборщик, корень):
    из = сборщик.собрать(корень, "site-1", _настройки(корень), порт=None, журнал=None)
    for имя in ("visitors", "pageviews", "playerStarts", "iks", "coreWebVitals"):
        assert из[имя]["value"] is None, f"{имя}: неизвестное показано числом"
        assert из[имя]["state"] == "NOT_CONNECTED"
        assert "не переданы" in из[имя]["reason"]


def test_недоступная_поисковая_консоль_названа_отдельно(сборщик, корень):
    из = сборщик.собрать(корень, "site-1", _настройки(корень), порт=None, журнал=None)
    assert из["indexedPages"]["state"] == "NOT_CONNECTED"
    assert "доступ не выдан" in из["indexedPages"]["reason"]


def test_отсутствующий_порт_не_выдаётся_за_здоровье(сборщик, корень):
    из = сборщик.собрать(корень, "site-1", _настройки(корень), порт=None, журнал=None)
    assert из["health"]["state"] == "NOT_CONNECTED"
    assert из["health"]["value"] is None


def test_испорченный_манифест_называет_отказ(сборщик, корень):
    (корень / "runtime" / "site-1" / "current" / "release-manifest.json").write_text(
        "{сломано", encoding="utf-8")
    из = сборщик.собрать(корень, "site-1", _настройки(корень), порт=None, журнал=None)
    assert из["freshnessSeconds"]["state"] == "ERROR"
    assert "не читается" in из["freshnessSeconds"]["reason"]


def test_ошибки_считаются_по_журналу(сборщик, корень, tmp_path):
    журнал = tmp_path / "site-1.access.log"
    журнал.write_text(
        '1.2.3.4 - - [06/Sep/2026:10:00:00 +0000] "GET / HTTP/1.1" 200 100\n'
        '1.2.3.4 - - [06/Sep/2026:10:00:01 +0000] "GET /нет HTTP/1.1" 404 100\n'
        '1.2.3.4 - - [06/Sep/2026:10:00:02 +0000] "GET /бум HTTP/1.1" 500 100\n',
        encoding="utf-8")
    из = сборщик.собрать(корень, "site-1", _настройки(корень), порт=None, журнал=журнал)
    assert из["errors4xx"]["value"] == 1
    assert из["errors5xx"]["value"] == 1
    assert из["errors4xx"]["state"] == "CONNECTED"


def test_отсутствующий_журнал_не_ноль_ошибок(сборщик, корень, tmp_path):
    из = сборщик.собрать(корень, "site-1", _настройки(корень), порт=None,
                         журнал=tmp_path / "нет.log")
    assert из["errors4xx"]["value"] is None, "ноль ошибок при отсутствующем журнале"
    assert из["errors4xx"]["state"] == "NOT_CONNECTED"


def test_у_каждого_наблюдения_есть_время_и_источник(сборщик, корень):
    из = сборщик.собрать(корень, "site-1", _настройки(корень), порт=None, журнал=None)
    for имя, о in из.items():
        if имя == "collectedAt":
            continue
        assert о["observedAt"], f"{имя}: нет времени"
        assert о["source"], f"{имя}: нет источника"
