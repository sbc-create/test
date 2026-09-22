"""Новый тайтл появляется на витрине сам, без пересборки сайта.

Проверяется весь путь: запись попала в снимок каталога → витрина заметила
изменение файла → карточка встала первой в «Недавно добавленных» → запись
находится поиском → она же попадает в реестр событий сравнением снимков.

Тестовая запись живёт только в изолированном снимке во временном каталоге.
В боевой снимок она не попадает и попасть не может: путь задаётся
переменной окружения, которая действует только внутри теста.
"""
from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

ЖИВОЙ_КАТАЛОГ = Path("/srv/lords/.frontend/animedia-01-catalog.json")
ЖИВЫЕ_ПОДРОБНОСТИ = Path("/srv/lords/.frontend/animedia-01-details.json")


def _снимок(записи: list, ревизия: str = "r1") -> dict:
    return {"revision": ревизия, "builtAt": "2026-09-22T00:00:00Z", "items": записи}


def _запись(slug: str, название: str, дата: str, год: int = 2026) -> dict:
    return {"slug": slug, "title": название, "url": f"/title/{slug}/",
            "kind": "Аниме", "year": год, "poster": "",
            "published_at": дата, "published_at_estimated": False}


@pytest.fixture()
def контур(tmp_path):
    """Изолированный контур витрины: свой снимок, свои пути, свои данные."""
    каталог = tmp_path / "animedia-01-catalog.json"
    подробности = tmp_path / "animedia-01-details.json"
    манифест = tmp_path / "manifest.json"
    манифест.write_text(json.dumps({
        "schema_version": 1, "template_family": "animedia", "design_version": "1.2.4",
        "source_commit": "0" * 40, "build_id": "test", "artifact_sha256": "0" * 64,
        "profile": "animedia-icu", "built_at": "2026-09-21T00:00:00Z"}), encoding="utf-8")
    базовые = [_запись(f"staroe-{i}", f"Старое {i}", f"2026-08-{i + 10:02d}T10:00:00Z")
               for i in range(1, 6)]
    каталог.write_text(json.dumps(_снимок(базовые)), encoding="utf-8")
    подробности.write_text(json.dumps({
        "details": {з["slug"]: {"name": з["title"], "type": "tv", "genres": ["аниме"],
                                "seasons": [{"n": 1, "eps": 12, "avail": 12}]}
                    for з in базовые}}), encoding="utf-8")
    прежние = {к: os.environ.get(к) for к in (
        "ANIMEDIA_TEMPLATE_MANIFEST", "ANIMEDIA_CATALOG", "ANIMEDIA_DETAILS",
        "LORDS_TEMPLATE_MANIFEST", "ANIMEDIA_SITE_DATA_DIR", "ANIMEDIA_EPISODE_LEDGER")
    }
    os.environ["ANIMEDIA_TEMPLATE_MANIFEST"] = str(манифест)
    os.environ["ANIMEDIA_CATALOG"] = str(каталог)
    os.environ["ANIMEDIA_DETAILS"] = str(подробности)
    os.environ["ANIMEDIA_SITE_DATA_DIR"] = str(tmp_path / "data")
    os.environ["ANIMEDIA_EPISODE_LEDGER"] = str(tmp_path / "events.json")
    os.environ.pop("LORDS_TEMPLATE_MANIFEST", None)
    спец = importlib.util.spec_from_file_location(
        f"animedia_auto_{tmp_path.name}", ROOT / "automation/host/animedia-frontend.py")
    модуль = importlib.util.module_from_spec(спец)
    sys.modules[спец.name] = модуль
    спец.loader.exec_module(модуль)
    yield модуль, каталог, подробности, базовые
    for к, з in прежние.items():
        if з is None:
            os.environ.pop(к, None)
        else:
            os.environ[к] = з


def test_новый_тайтл_встаёт_первым_без_перезапуска(контур):
    """Главный сценарий: снимок обновился — витрина показала это сама."""
    модуль, каталог, подробности, базовые = контур
    модуль.освежить_снимок(принудительно=True)
    до = модуль.Обработчик.данные
    assert до is not None and len(до.items) == 5

    новая = _запись("novyy-tayтl", "Новый тайтл", "2026-09-22T12:00:00Z")
    каталог.write_text(json.dumps(_снимок(базовые + [новая], "r2")), encoding="utf-8")
    данные = json.loads(подробности.read_text(encoding="utf-8"))
    данные["details"][новая["slug"]] = {
        "name": новая["title"], "original_name": "Novyy Tightle", "type": "tv",
        "genres": ["аниме"], "seasons": [{"n": 1, "eps": 12, "avail": 3}]}
    подробности.write_text(json.dumps(данные), encoding="utf-8")
    # Время правки файла — часть отпечатка снимка; на быстрой машине две
    # записи попадают в одну и ту же секунду.
    time.sleep(1.1)

    assert модуль.освежить_снимок() is True, "витрина не заметила новый снимок"
    после = модуль.Обработчик.данные
    assert len(после.items) == 6

    первые = модуль.недавно_добавленные(после.items, 1)
    assert первые and первые[0]["slug"] == новая["slug"], (
        "новая запись не встала первой в «Недавно добавленных»")


def test_новый_тайтл_сразу_находится_поиском(контур):
    """Поиск работает по тому же снимку и не ждёт отдельной переиндексации."""
    модуль, каталог, подробности, базовые = контур
    модуль.освежить_снимок(принудительно=True)
    assert модуль.Обработчик.данные.искать("Новый тайтл") == []

    новая = _запись("novyy-tayтl", "Новый тайтл", "2026-09-22T12:00:00Z")
    каталог.write_text(json.dumps(_снимок(базовые + [новая], "r2")), encoding="utf-8")
    данные = json.loads(подробности.read_text(encoding="utf-8"))
    данные["details"][новая["slug"]] = {
        "name": новая["title"], "original_name": "Novyy Taitl", "type": "tv",
        "genres": ["аниме"], "seasons": [{"n": 1, "eps": 12, "avail": 3}]}
    подробности.write_text(json.dumps(данные), encoding="utf-8")
    time.sleep(1.1)
    модуль.освежить_снимок()

    д = модуль.Обработчик.данные
    assert [з["slug"] for з in д.искать("Новый тайтл")][:1] == ["novyy-tayтl"]
    # И по оригинальному написанию, которого в снимке каталога нет вовсе.
    assert [з["slug"] for з in д.искать("Novyy Taitl")][:1] == ["novyy-tayтl"]


def test_снимок_без_изменений_не_перечитывается(контур):
    """Сторож снимка не должен пересобирать указатель на каждом тике."""
    модуль, _, _, _ = контур
    модуль.освежить_снимок(принудительно=True)
    assert модуль.освежить_снимок() is False


def test_битый_снимок_не_рушит_витрину(контур):
    """Оборванная запись файла не должна обнулять работающую витрину."""
    модуль, каталог, _, _ = контур
    модуль.освежить_снимок(принудительно=True)
    было = len(модуль.Обработчик.данные.items)
    каталог.write_text("{ это не json", encoding="utf-8")
    time.sleep(1.1)
    assert модуль.освежить_снимок() is False
    assert len(модуль.Обработчик.данные.items) == было, (
        "витрина потеряла каталог из-за одного битого файла")
    assert модуль.СНИМОК_СОСТОЯНИЕ["ошибок"] >= 1


def test_появление_серии_попадает_в_реестр_событий(tmp_path):
    """Вторая половина пути: новая серия становится событием, а не догадкой."""
    рантайм = tmp_path / "runtime"
    рантайм.mkdir()
    каталог = рантайм / "animedia-01-catalog.json"
    подробности = рантайм / "animedia-01-details.json"
    записи = [_запись("s1", "Сериал", "2026-09-01T10:00:00Z")]
    каталог.write_text(json.dumps(_снимок(записи)), encoding="utf-8")

    def снимок_подробностей(доступно: int, ревизия: str) -> None:
        подробности.write_text(json.dumps({
            "catalog_revision": ревизия,
            "catalog_built_at": f"2026-09-2{доступно}T00:00:00Z",
            "details": {"s1": {"name": "Сериал", "type": "tv",
                               "seasons": [{"n": 1, "eps": 12, "avail": доступно}]}},
        }), encoding="utf-8")

    окружение = dict(os.environ, ANIMEDIA_RUNTIME_ROOT=str(рантайм))
    инструмент = [sys.executable, str(ROOT / "automation/host/animedia-episode-ledger.py"),
                  "--site", "animedia-01"]

    снимок_подробностей(3, "rev-a")
    первый = subprocess.run(инструмент, cwd=str(ROOT), env=окружение,
                            capture_output=True, text=True)
    assert первый.returncode == 0, первый.stderr
    реестр = json.loads((рантайм / "animedia-01-episode-events.json").read_text("utf-8"))
    assert реестр["events"] == [], "первый запуск не должен выдумывать событий"
    assert реестр["first_run_seeded"] is True

    снимок_подробностей(5, "rev-b")
    второй = subprocess.run(инструмент, cwd=str(ROOT), env=окружение,
                            capture_output=True, text=True)
    assert второй.returncode == 0, второй.stderr
    реестр = json.loads((рантайм / "animedia-01-episode-events.json").read_text("utf-8"))
    assert len(реестр["events"]) == 1
    событие = реестр["events"][0]
    assert событие["slug"] == "s1"
    assert (событие["episode_from"], событие["episode_to"]) == (3, 5)
    assert событие["detected_from"] == "snapshot-diff"
    # Дата события — отметка снимка, а не часы машины и не год произведения.
    assert событие["episode_published_at"] == "2026-09-25T00:00:00Z"


def test_реестр_не_повторяет_событие_на_том_же_снимке(tmp_path):
    """Повторный прогон без нового снимка не должен плодить события."""
    рантайм = tmp_path / "runtime"
    рантайм.mkdir()
    (рантайм / "animedia-01-catalog.json").write_text(
        json.dumps(_снимок([_запись("s1", "Сериал", "2026-09-01T10:00:00Z")])),
        encoding="utf-8")
    (рантайм / "animedia-01-details.json").write_text(json.dumps({
        "catalog_revision": "rev-a", "catalog_built_at": "2026-09-22T00:00:00Z",
        "details": {"s1": {"name": "Сериал", "type": "tv",
                           "seasons": [{"n": 1, "eps": 12, "avail": 3}]}}}),
        encoding="utf-8")
    окружение = dict(os.environ, ANIMEDIA_RUNTIME_ROOT=str(рантайм))
    инструмент = [sys.executable, str(ROOT / "automation/host/animedia-episode-ledger.py"),
                  "--site", "animedia-01"]
    for _ in range(3):
        assert subprocess.run(инструмент, cwd=str(ROOT), env=окружение,
                              capture_output=True, text=True).returncode == 0
    реестр = json.loads((рантайм / "animedia-01-episode-events.json").read_text("utf-8"))
    assert реестр["events"] == []


@pytest.mark.skipif(not ЖИВОЙ_КАТАЛОГ.is_file(), reason="живого снимка нет на хосте")
def test_на_живом_снимке_самая_свежая_запись_действительно_первая():
    """То же правило на боевых данных, без тестовой записи."""
    спец = importlib.util.spec_from_file_location(
        "animedia_auto_live", ROOT / "automation/host/animedia-frontend.py")
    манифест = Path("/srv/lords/.frontend/template-manifest-animedia-01.json")
    прежний = os.environ.get("ANIMEDIA_TEMPLATE_MANIFEST")
    os.environ["ANIMEDIA_TEMPLATE_MANIFEST"] = str(манифест)
    os.environ.pop("LORDS_TEMPLATE_MANIFEST", None)
    модуль = importlib.util.module_from_spec(спец)
    sys.modules[спец.name] = модуль
    спец.loader.exec_module(модуль)
    if прежний is not None:
        os.environ["ANIMEDIA_TEMPLATE_MANIFEST"] = прежний
    записи = json.loads(ЖИВОЙ_КАТАЛОГ.read_text(encoding="utf-8"))["items"]
    порядок = модуль.недавно_добавленные(записи, 10)
    assert порядок, "на живом снимке не нашлось ни одной датированной записи"
    даты = [з["published_at"] for з in порядок]
    assert даты == sorted(даты, reverse=True), "порядок не по убыванию даты"
    # Когорта массового импорта в новинки не попадает.
    массовые = модуль.массовые_метки(записи)
    assert массовые, "когорта массового импорта не распознана"
    assert not (set(даты) & массовые)
