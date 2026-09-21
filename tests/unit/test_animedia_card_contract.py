"""Контракт карточки Animedia: состав задаётся вариантом, а не местом вызова.

Владелец увидел на витринах «почти одни постеры»: часть блоков рисовала
карточку без подписи и оценки, а лента прятала поля стилем, хотя разметка их
отдавала. Такой разрыв между обещанным и видимым и закрывает этот контракт.

Здесь проверяется сам контракт и то, как он превращается в разметку; как он
выглядит на отрисованной странице — проверяет `animedia-card-audit.py`, и его
запись читается в конце файла.
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
ДОК = ROOT / "artifacts/evidence/animedia-original-parity-01"


@pytest.fixture(scope="module")
def рантайм():
    """Модуль витрины с подставным манифестом: он нужен ему при импорте."""
    манифест = ROOT / "artifacts/evidence/animedia-original-parity-01/_манифест-теста.json"
    манифест.parent.mkdir(parents=True, exist_ok=True)
    манифест.write_text(json.dumps({
        "schema_version": 1, "template_family": "animedia", "design_version": "1.2.4",
        "source_commit": "0" * 40, "build_id": "test", "artifact_sha256": "0" * 64,
        "profile": "animedia-icu", "built_at": "2026-09-21T00:00:00Z"}), encoding="utf-8")
    import os
    прежние = {k: os.environ.get(k) for k in
               ("ANIMEDIA_TEMPLATE_MANIFEST", "ANIMEDIA_CATALOG", "LORDS_TEMPLATE_MANIFEST")}
    os.environ["ANIMEDIA_TEMPLATE_MANIFEST"] = str(манифест)
    os.environ.pop("LORDS_TEMPLATE_MANIFEST", None)
    спец = importlib.util.spec_from_file_location(
        "animedia_runtime_для_теста", ROOT / "automation/host/animedia-frontend.py")
    модуль = importlib.util.module_from_spec(спец)
    sys.modules[спец.name] = модуль
    спец.loader.exec_module(модуль)
    yield модуль
    for k, v in прежние.items():
        if v is None:
            os.environ.pop(k, None)
        else:
            os.environ[k] = v
    манифест.unlink(missing_ok=True)


# --- сам контракт -------------------------------------------------------------

def test_каждый_вариант_обещает_название(рантайм):
    """Изображение без подписи карточкой не является — ни в одном блоке."""
    for имя, состав in рантайм.АНИМЕДИА_ВАРИАНТЫ_КАРТОЧКИ.items():
        assert состав["название"] is True, имя


def test_варианты_покрывают_все_блоки(рантайм):
    нужны = {"catalog-title", "catalog", "related", "recommendation",
             "compact", "related-row"}
    assert нужны <= set(рантайм.АНИМЕДИА_ВАРИАНТЫ_КАРТОЧКИ)


def test_сетчатые_варианты_показывают_мету_и_оценки(рантайм):
    for имя in ("catalog-title", "catalog", "related", "recommendation"):
        состав = рантайм.АНИМЕДИА_ВАРИАНТЫ_КАРТОЧКИ[имя]
        assert состав["мета"] is True, имя
        assert состав["оценок"] >= 1, имя
        assert состав["бейджи"] is True, имя


def test_неизвестный_вариант_получает_полный_состав(рантайм):
    """Опечатка в имени варианта не должна тихо обеднять карточку."""
    по_умолчанию = рантайм.АНИМЕДИА_ВАРИАНТ_ПО_УМОЛЧАНИЮ
    assert по_умолчанию["название"] and по_умолчанию["мета"] and по_умолчанию["оценок"] >= 1


# --- счётчик серий ------------------------------------------------------------

def test_счётчик_серий_складывает_сезоны(рантайм):
    assert рантайм._счётчик_серий({"seasons": [{"avail": 12, "eps": 12, "n": 1},
                                               {"avail": 3, "eps": 10, "n": 2}]}) == (15, 22)


@pytest.mark.parametrize("деталь", [
    {},
    {"seasons": []},
    {"seasons": [{"avail": 0, "eps": 0}]},
    {"seasons": [{"avail": "нет", "eps": "нет"}]},
    {"seasons": "двенадцать"},
])
def test_без_чисел_счётчика_нет(рантайм, деталь):
    assert рантайм._счётчик_серий(деталь) is None


# --- оценки -------------------------------------------------------------------

def test_оценка_приводится_к_десяти_но_хранит_исходное(рантайм):
    деталь = {"ratings_by_source": {"shikimori": {"value": 4.2, "scale": 5.0, "votes": 10}}}
    о = рантайм._оценки_для_карточки(деталь, 1)[0]
    assert о["на_десять"] == "8.4"
    assert о["исходное"] == "4.2"
    assert о["исходная_шкала"] == "5"
    assert о["голоса"] == 10


def test_ноль_и_пустое_не_показываются(рантайм):
    for сырое in ({"value": 0, "scale": 10}, {"value": None, "scale": 10},
                  {"value": "", "scale": 10}):
        деталь = {"ratings_by_source": {"imdb": сырое}}
        assert рантайм._оценки_для_карточки(деталь, 2) == [], сырое


def test_две_оценки_разных_источников(рантайм):
    деталь = {"ratings_by_source": {
        "imdb": {"value": 7.5, "scale": 10.0, "votes": 100},
        "shikimori": {"value": 8.1, "scale": 10.0}}}
    оценки = рантайм._оценки_для_карточки(деталь, 2)
    assert len(оценки) == 2
    assert len({о["ключ"] for о in оценки}) == 2, "источники не должны повторяться"
    for о in оценки:
        assert о["подпись"], "источник обязан быть назван"


def test_источники_не_смешиваются_в_одно_число(рантайм):
    """Среднее по несводимым шкалам — выдуманная величина, её здесь нет."""
    деталь = {"ratings_by_source": {"imdb": {"value": 6.0, "scale": 10.0},
                                    "shikimori": {"value": 8.0, "scale": 10.0}}}
    значения = {о["на_десять"] for о in рантайм._оценки_для_карточки(деталь, 2)}
    assert значения == {"6", "8"}
    assert "7" not in значения


# --- разметка -----------------------------------------------------------------

def test_запись_проверки_карточек_зелёная():
    файл = ДОК / "38-card-fill" / "CARD_AUDIT.json"
    assert файл.is_file(), "нет записи разбора карточек"
    з = json.loads(файл.read_text(encoding="utf-8"))
    assert з["CARD_AUDIT_PASS"] is True, з["findings"][:5]
    # Разбор обязан покрывать нижние блоки внутренних страниц.
    маршруты = {c["route"] for c in з["cells"]}
    assert {"title", "episode", "catalog", "home"} <= маршруты
    for c in з["cells"]:
        for блок, с in c["blocks"].items():
            if с["cards"] >= 3 and "compact" not in с["variants"]:
                assert с["title_visible_share"] >= 0.95, (c["route"], блок)
                assert с["zero_ratings_shown"] == 0, (c["route"], блок)


def test_запись_проверки_хронологии_зелёная():
    файл = ДОК / "39-chronology-fill" / "CHRONOLOGY_CHECK.json"
    assert файл.is_file(), "нет записи проверки хронологии"
    з = json.loads(файл.read_text(encoding="utf-8"))
    assert з["CHRONOLOGY_PASS"] is True, з["failures"][:5]
    assert з["snapshot_order_violations"] == []
    # Проверены обе ширины и несколько страниц листалки.
    assert {p["width"] for p in з["pages"]} == {390, 1440}
    assert len({p["path"] for p in з["pages"]}) >= 3
