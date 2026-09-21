"""Поиск витрины Yummy: расширение запроса и запасной поиск по каталогу.

Что здесь закрепляется
----------------------

Поиск ведёт приложение, и подменять его нельзя: у него свой индекс. Но
измерено на боевом каталоге, что на целом классе запросов он отдаёт ноль при
непустом каталоге — запрос «воин» не находит ничего при 115 аниме с этим
словом в названии. Причина в приложении и названа отдельно
(`docs/handoff/YUMMY-SEARCH-ANIME-FILTER.md`): оно спрашивает поставщика по
всему его каталогу, берёт первую сотню найденного и только потом отсеивает
не-аниме; на частом слове первая сотня состоит из не-аниме целиком.

Витрина закрывает это двумя способами, и оба проверяются здесь:

1. **расширение запроса** — если полный запрос ничего не нашёл, пробуются
   последовательно укороченные варианты с СОХРАНЁННЫМИ разделителями;
2. **запасной поиск** — если и они ничего не нашли, отвечает собственный
   каталог контура, и порядок его ответа объявлен.

Оба — расширение, а не подмена: когда приложение находит, отвечает оно.
"""

from __future__ import annotations

import importlib.machinery
import importlib.util
import json
import os
import sqlite3
import sys
from pathlib import Path

import pytest

КОРЕНЬ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(КОРЕНЬ / "tests" / "fixtures" / "yummy"))

import contract_fixture as ФИКСТУРА  # noqa: E402


def _модуль(имя: str, файл: str):
    путь = КОРЕНЬ / "automation" / "host" / файл
    спец = importlib.util.spec_from_loader(
        имя, importlib.machinery.SourceFileLoader(имя, str(путь)))
    м = importlib.util.module_from_spec(спец)
    sys.modules.setdefault(имя, м)
    спец.loader.exec_module(м)
    return м


СВЯЗЬ = _модуль("yummy_contract", "yummy_contract.py")


@pytest.fixture(scope="module")
def ФРОНТ(tmp_path_factory):
    """Рантайм импортируется как модуль: манифест обязателен уже при импорте.

    Без него витрина не поднимается вовсе — это правило владельца, и обходить
    его в тесте нельзя. Поэтому манифест кладётся во временный каталог и
    объявляется переменной окружения, как в бою.
    """
    куда = tmp_path_factory.mktemp("yummy-front")
    манифест = куда / "manifest.json"
    манифест.write_text(json.dumps({
        "schema_version": 1, "template_family": "yummy",
        "design_version": "0.0.0-test", "source_commit": "0" * 40,
        "build_id": "test", "artifact_sha256": "0" * 64,
        "profile": "test", "built_at": "2026-09-10T00:00:00Z"}), encoding="utf-8")
    было = os.environ.get("LORDS_TEMPLATE_MANIFEST")
    os.environ["LORDS_TEMPLATE_MANIFEST"] = str(манифест)
    os.environ.setdefault("LORDS_CATALOG", str(куда / "нет-каталога.json"))
    try:
        yield _модуль("yummy_frontend_под_тест", "yummy-frontend.py")
    finally:
        if было is None:
            os.environ.pop("LORDS_TEMPLATE_MANIFEST", None)
        else:
            os.environ["LORDS_TEMPLATE_MANIFEST"] = было


@pytest.fixture()
def база():
    соед = sqlite3.connect(":memory:")
    соед.row_factory = sqlite3.Row
    return ФИКСТУРА.построить(соед)


class TestРасширениеЗапроса:
    """Варианты пробуются сверху вниз; приложение проверяет каждый."""

    def test_хвост_издания_отбрасывается(self, ФРОНТ):
        варианты = ФРОНТ.варианты_запроса("Grand Blue Dreaming Season 3")
        assert варианты[0] == "Grand Blue Dreaming"

    def test_слово_тайтла_не_выбрасывается_из_середины(self, ФРОНТ):
        """«dreaming» когда-то стояло в списке изданий — и резало чужие имена.

        Выбрасывать слово из середины нельзя ещё и потому, что приложение
        ищет строку целиком: «Grand Blue Season 3» без «Dreaming» — строка,
        которой нет ни в одном названии.
        """
        варианты = ФРОНТ.варианты_запроса("Grand Blue Dreaming Season 3")
        assert all("Dreaming" in в or в == "Grand Blue" or в == "Grand"
                   for в in варианты), варианты

    def test_разделители_сохраняются(self, ФРОНТ):
        """«Жил-был» находит «Жил-был воин», «Жил был» — нет."""
        варианты = ФРОНТ.варианты_запроса("Жил-был-воин")
        assert "Жил-был" in варианты
        assert варианты.index("Жил-был") < варианты.index("Жил был воин")

    def test_замена_разделителей_пробуется_последней(self, ФРОНТ):
        варианты = ФРОНТ.варианты_запроса("Жил-был-воин")
        assert варианты[-1] == "Жил был воин"

    def test_сам_запрос_в_варианты_не_попадает(self, ФРОНТ):
        """Повторять приложению тот же запрос — лишний заход наверх."""
        for запрос in ("Жил-был воин", "океан", "Grand Blue"):
            assert запрос not in ФРОНТ.варианты_запроса(запрос)

    def test_одно_слово_расширять_нечем(self, ФРОНТ):
        assert ФРОНТ.варианты_запроса("воин") == []

    def test_пустой_запрос(self, ФРОНТ):
        assert ФРОНТ.варианты_запроса("   ") == []


class TestПоискПоКаталогу:
    """Запасной поиск: объявленное сравнение и объявленный порядок."""

    def test_находит_по_русскому_названию(self, база):
        найдено = СВЯЗЬ.поиск(база, "Фикстура: полная карточка")
        assert [з for з in найдено if з["entity_id"] == ФИКСТУРА.ГЛАВНЫЙ]

    def test_находит_по_оригинальному_названию(self, база):
        найдено = СВЯЗЬ.поиск(база, "Fixture: Complete Entity")
        assert [з for з in найдено if з["entity_id"] == ФИКСТУРА.ГЛАВНЫЙ]

    def test_регистр_ё_и_знаки_не_решают(self, база):
        база.execute("UPDATE entity SET title_ru='Ёжик: Мир!' WHERE entity_id=?",
                     (ФИКСТУРА.ГЛАВНЫЙ,))
        база.commit()
        for запрос in ("ёжик мир", "ЕЖИК МИР", "ежик - мир", "  Ёжик   Мир  "):
            assert СВЯЗЬ.поиск(база, запрос), запрос

    def test_вхождение_в_середину_находится(self, база):
        """Ровно то, чего не умеет индекс приложения на частом слове."""
        база.execute("UPDATE entity SET title_ru='Мобильный воин Гандам'"
                     " WHERE entity_id=?", (ФИКСТУРА.ГЛАВНЫЙ,))
        база.commit()
        найдено = СВЯЗЬ.поиск(база, "воин")
        assert [з for з in найдено if з["title"] == "Мобильный воин Гандам"]

    def test_порядок_объявлен_точное_начало_вхождение(self, база):
        база.execute("UPDATE entity SET title_ru='Гандам' WHERE entity_id=?",
                     (ФИКСТУРА.ГЛАВНЫЙ,))
        база.execute("UPDATE entity SET title_ru='Гандам Винг' WHERE entity_id=?",
                     ("ent-fixture-on-1",))
        база.execute("UPDATE entity SET title_ru='Мобильный Гандам' WHERE entity_id=?",
                     ("ent-fixture-on-2",))
        база.commit()
        порядок = [з["title"] for з in СВЯЗЬ.поиск(база, "гандам")]
        assert порядок[:3] == ["Гандам", "Гандам Винг", "Мобильный Гандам"]

    def test_без_канонического_адреса_не_публикуется(self, база):
        база.execute("UPDATE entity SET canonical_path=NULL")
        база.commit()
        assert СВЯЗЬ.поиск(база, "Фикстура") == []

    def test_пустой_запрос_ничего_не_ищет(self, база):
        assert СВЯЗЬ.поиск(база, "   ") == []

    def test_несуществующее_не_выдумывается(self, база):
        assert СВЯЗЬ.поиск(база, "zzqqxxvv") == []

    def test_предел_соблюдается(self, база):
        assert len(СВЯЗЬ.поиск(база, "Фикстура", 3)) == 3

    def test_результат_воспроизводим(self, база):
        """Дважды один запрос — дважды один порядок."""
        assert ([з["entity_id"] for з in СВЯЗЬ.поиск(база, "Фикстура")]
                == [з["entity_id"] for з in СВЯЗЬ.поиск(база, "Фикстура")])
