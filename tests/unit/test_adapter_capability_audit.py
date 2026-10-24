"""Сверка объявленных возможностей адаптера с фактическими читателями витрин.

ПОВОД ИЗМЕРЕННЫЙ, 24.10 (MOD-172). `ТРЕБУЕТ_ВОЗМОЖНОСТИ['publish']` требует
`deliver` и `display`, а `ВОЗМОЖНОСТИ_АДАПТЕРА` объявляет `display` только у
`animedia`. Поэтому очередь отказывает в заданиях на описание 15 витринам,
которые текст ПОКАЗЫВАЮТ: у пяти Yummy — через монтирование в контейнер, у
трёх AnimeGo — `src/seo_overlay.py`, у семи Lords и Zona — накладка витрины.

Проверяется главное свойство детектора: он не ДОСМАТРИВАЕТ. Первая редакция
требовала литерал `editorial-overrides` в самом модуле читателя и потому не
видела `lordserial33.biz` и `zonafilm.space` — путь читатель берёт из
`config/site.json`. Недосмотр здесь опаснее ложной тревоги: по нему решают,
что витрина показывать не умеет, и работа редактора простаивает.

Пути подставляются, сеть и docker не нужны.
"""
from __future__ import annotations

import importlib.util
import json
import pathlib

КОРЕНЬ = pathlib.Path(__file__).resolve().parents[2]
ПУТЬ = КОРЕНЬ / "automation" / "local" / "adapter-capability-audit.py"
_с = importlib.util.spec_from_file_location("adapter_capability_audit", ПУТЬ)
МОДУЛЬ = importlib.util.module_from_spec(_с)
assert _с.loader is not None
_с.loader.exec_module(МОДУЛЬ)


def _витрина(корень: pathlib.Path, *, читатель: str = "",
             site_json: bool = False) -> pathlib.Path:
    текущий = корень / "current"
    (текущий / "src").mkdir(parents=True)
    if читатель:
        (текущий / "src" / читатель).write_text("# читатель\n", encoding="utf-8")
    if site_json:
        (текущий / "config").mkdir()
        (текущий / "config" / "site.json").write_text(
            json.dumps({"editorial": "data/editorial-overrides.json"}),
            encoding="utf-8")
    return корень


def test_наложение_в_дереве_узнаётся(tmp_path):
    к = _витрина(tmp_path / "витрина", читатель="seo_overlay.py")
    маршрут, довод = МОДУЛЬ.читатель_в_дереве(к)
    assert маршрут == "наложение в дереве", (маршрут, довод)
    assert "seo_overlay.py" in довод


def test_накладка_узнаётся_без_литерала_в_модуле(tmp_path):
    """Ровно недосмотр первой редакции: путь лежит в config/site.json."""
    к = _витрина(tmp_path / "витрина", читатель="editorial_overlay.py",
                 site_json=True)
    маршрут, довод = МОДУЛЬ.читатель_в_дереве(к)
    assert маршрут == "накладка витрины", (маршрут, довод)
    assert "подтверждено: site.json" in довод, довод


def test_накладка_узнаётся_и_без_подтверждения(tmp_path):
    """Читатель на месте — значит показывает; подтверждение лишь усиливает."""
    к = _витрина(tmp_path / "витрина", читатель="editorial_overlay.py")
    маршрут, довод = МОДУЛЬ.читатель_в_дереве(к)
    assert маршрут == "накладка витрины"
    assert "подтверждено" not in довод


def test_витрина_без_читателя_не_выдаётся_за_показывающую(tmp_path):
    """Отрицательный контроль: витрины K2 читателя не имеют вовсе.

    Для них правка объявления ничего не даст — нужен читатель в рантайме, и
    смешивать эти два случая нельзя.
    """
    к = _витрина(tmp_path / "витрина", читатель="episode_sync.py")
    маршрут, довод = МОДУЛЬ.читатель_в_дереве(к)
    assert маршрут == ""
    assert "нет" in довод


def test_отсутствие_выпуска_называется_отдельно(tmp_path):
    к = tmp_path / "витрина"
    к.mkdir()
    маршрут, довод = МОДУЛЬ.читатель_в_дереве(к)
    assert маршрут == ""
    assert "current" in довод


def test_маршрут_контейнера_сопоставляется_по_домену():
    кон = {"yummyani-staging-web-site-1": {
        "переменные": ["TITLE_OVERLAYS_PATH=/app/content/overlays/t.json"],
        "монтирования": [
            "/srv/sites/yummyani-staging/runtime/overlays/yummyani.site"
            "->/app/content/overlays"]}}
    маршрут, довод = МОДУЛЬ.маршрут_контейнера("yummyani.site", кон)
    assert маршрут == "наложение в контейнере", (маршрут, довод)
    assert "TITLE_OVERLAYS_PATH" in довод
    # чужой домен тем же контейнером не подтверждается
    assert МОДУЛЬ.маршрут_контейнера("yummyani.org", кон)[0] == ""


def test_дерево_витрины_ищется_и_с_приставкой_site(tmp_path, monkeypatch):
    monkeypatch.setattr(МОДУЛЬ, "SRV", tmp_path)
    (tmp_path / "site-1lordserials1-online").mkdir()
    assert МОДУЛЬ.дерево("1lordserials1.online") == (
        tmp_path / "site-1lordserials1-online")
    (tmp_path / "zonafilm12-site").mkdir()
    assert МОДУЛЬ.дерево("zonafilm12.site") == tmp_path / "zonafilm12-site"
    assert МОДУЛЬ.дерево("нет.такого") is None
