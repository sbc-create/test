"""Компонент многоисточниковых оценок.

Контракт `ratings_by_source` на момент написания ещё не пришёл от направления
«Архитектор», поэтому здесь он ЗАФИКСИРОВАН фикстурами: тест — это и есть
описание того, что витрина готова принять. Производственных данных тест не
выдумывает и не требует.

Главное правило, ради которого тест существует: подпись источника принадлежит
источнику. Показать Shikimori под подписью «КП» — не косметическая ошибка, а
ложное утверждение о происхождении числа.
"""

from __future__ import annotations

import importlib.util
import json
import os
import sys
from pathlib import Path

import pytest

КОРЕНЬ = Path(__file__).resolve().parents[2]
ИСХОДНИК = КОРЕНЬ / "automation" / "host" / "lords-frontend.py"


def _манифест(семейство: str, версия: str) -> dict:
    return {"schema_version": 1, "template_family": семейство,
            "design_version": версия, "source_commit": "0" * 40,
            "build_id": "TEST", "artifact_sha256": "0" * 64,
            "profile": f"{семейство}-test", "built_at": "2026-09-15T00:00:00Z"}


def _модуль(tmp_path, семейство: str = "zona", версия: str = "1.2.0"):
    корень = tmp_path / семейство
    корень.mkdir(parents=True, exist_ok=True)
    каталог = корень / f"{семейство}-catalog.json"
    каталог.write_text(json.dumps({"items": [], "fields_absent": []}), encoding="utf-8")
    манифест = корень / "manifest.json"
    манифест.write_text(json.dumps(_манифест(семейство, версия)), encoding="utf-8")
    прежние = dict(sys.modules)
    старое = dict(os.environ)
    os.environ["LORDS_TEMPLATE_MANIFEST"] = str(манифест)
    os.environ["LORDS_CATALOG"] = str(каталог)
    os.environ.pop("LORDS_DETAILS", None)
    os.environ.pop("LORDS_METRIKA_COUNTER", None)
    try:
        имя = f"rbs_{семейство}_{версия.replace('.', '_')}"
        спец = importlib.util.spec_from_file_location(имя, ИСХОДНИК)
        модуль = importlib.util.module_from_spec(спец)
        sys.modules[имя] = модуль
        спец.loader.exec_module(модуль)
    finally:
        os.environ.clear()
        os.environ.update(старое)
        for к in set(sys.modules) - set(прежние):
            if not к.startswith("rbs_"):
                sys.modules.pop(к, None)
    return модуль


@pytest.fixture(scope="module")
def м(tmp_path_factory):
    return _модуль(tmp_path_factory.mktemp("rbs"))


#: Полный контракт: пять источников, объектная форма со шкалой и голосами.
ПОЛНЫЙ = {"ratings_by_source": {
    "kp":        {"value": 7.4, "scale": 10, "votes": 12043},
    "imdb":      {"value": 6.8, "scale": 10, "votes": 5120},
    "shikimori": {"value": 8.21, "scale": 10, "votes": 3310},
    "mal":       {"value": 7.95, "scale": 10, "votes": 88120},
    "amd":       {"value": 9.1, "scale": 10, "votes": 412},
}}


class TestРазборИсточников:
    def test_все_пять_источников_разобраны(self, м):
        о = м.оценки_по_источникам(ПОЛНЫЙ)
        assert [x["ключ"] for x in о] == ["kp", "imdb", "shikimori", "mal", "amd"]

    def test_подпись_привязана_к_ключу(self, м):
        подписи = {x["ключ"]: x["подпись"] for x in м.оценки_по_источникам(ПОЛНЫЙ)}
        assert подписи == {"kp": "КП", "imdb": "IMDb", "shikimori": "Shikimori",
                           "mal": "MyAnimeList", "amd": "AMD"}

    def test_голоса_и_шкала_сохранены(self, м):
        о = {x["ключ"]: x for x in м.оценки_по_источникам(ПОЛНЫЙ)}
        assert о["kp"]["голоса"] == 12043
        assert о["mal"]["шкала"] == "10"

    def test_числовая_форма_тоже_принимается(self, м):
        о = м.оценки_по_источникам({"ratings_by_source": {"kp": 7.4}})
        assert len(о) == 1 and о[0]["значение"] == "7.4" and о[0]["голоса"] is None

    def test_ноль_null_и_пустое_оценкой_не_являются(self, м):
        о = м.оценки_по_источникам({"ratings_by_source": {
            "kp": 0, "imdb": None, "shikimori": "", "mal": {"value": 0.0},
            "amd": {"value": None}}})
        assert о == []

    def test_нечисловое_значение_отбрасывается(self, м):
        о = м.оценки_по_источникам({"ratings_by_source": {"kp": "нет", "imdb": True}})
        assert о == []

    def test_совместимость_с_прежними_полями(self, м):
        о = м.оценки_по_источникам({"kinopoisk_rating": 7.4, "imdb_rating": 6.8})
        assert [x["ключ"] for x in о] == ["kp", "imdb"]

    def test_порядок_не_зависит_от_величины(self, м):
        о = м.оценки_по_источникам({"ratings_by_source": {
            "mal": 9.9, "kp": 1.1, "imdb": 5.0}})
        assert [x["ключ"] for x in о] == ["kp", "imdb", "mal"]


class TestРазметка:
    def test_все_источники_видны_и_подписаны(self, м):
        h = м.разметка_оценок(ПОЛНЫЙ)
        for ключ, подпись in (("kp", "КП"), ("imdb", "IMDb"), ("shikimori", "Shikimori"),
                              ("mal", "MyAnimeList"), ("amd", "AMD")):
            assert f'data-source="{ключ}"' in h
            assert подпись in h

    def test_оценка_витрины_отделена_от_внешних(self, м):
        h = м.разметка_оценок(ПОЛНЫЙ)
        assert "rbs__l--own" in h
        свой = h.split("rbs__l--own")[1]
        # В группе оценки витрины нет ни одного внешнего источника.
        for чужой in ("kp", "imdb", "shikimori", "mal"):
            assert f'data-source="{чужой}"' not in свой

    def test_чужая_подпись_не_подставляется(self, м):
        h = м.разметка_оценок({"ratings_by_source": {"shikimori": 8.2}})
        assert "Shikimori" in h
        assert "КП" not in h and "IMDb" not in h

    def test_одна_оценка_тоже_рисуется(self, м):
        h = м.разметка_оценок({"ratings_by_source": {"imdb": {"value": 6.8}}})
        assert 'data-source="imdb"' in h and "rbs__l--own" not in h

    def test_пустое_состояние_честное_и_без_нулей(self, м):
        h = м.разметка_оценок({})
        assert "rbs--none" in h
        assert ">0<" not in h and "null" not in h

    def test_пустое_состояние_можно_не_рисовать(self, м):
        assert м.разметка_оценок({}, пусто=False) == ""

    def test_шкала_показана_явно(self, м):
        h = м.разметка_оценок({"ratings_by_source": {"kp": {"value": 7.4, "scale": 5}}})
        assert "/5" in h

    def test_число_голосов_показано_когда_известно(self, м):
        h = м.разметка_оценок({"ratings_by_source": {"kp": {"value": 7.4, "votes": 120}}})
        assert "120" in h
        без = м.разметка_оценок({"ratings_by_source": {"kp": {"value": 7.4}}})
        assert "голос" not in без

    def test_доступность_каждая_оценка_читается_целиком(self, м):
        h = м.разметка_оценок(ПОЛНЫЙ)
        assert "КП 7.4 из 10, 12043 голосов" in h
        assert 'role="group"' in h and 'aria-label="Оценки"' in h
        # Визуальные части скрыты от чтения вслух, чтобы не дублировать.
        assert h.count('aria-hidden="true"') >= 10


class TestСемействаПоддерживаютКомпонент:
    @pytest.mark.parametrize("семейство,версия", [
        ("lords", "1.1.0"), ("zona", "1.2.0"), ("animedia", "1.2.0"), ("zona", "1.1.0"),
    ])
    def test_стиль_семейства_описывает_компонент(self, tmp_path_factory, семейство, версия):
        м = _модуль(tmp_path_factory.mktemp(f"rbs-{семейство}-{версия}"), семейство, версия)
        стиль = м.СЕМЕЙСТВА_1_1.get(семейство, м.СЕМЕЙСТВА_1_1["lords"])["стиль"]()
        assert ".rbs{" in стиль and ".rbs__s{" in стиль and ".rbs--none{" in стиль
