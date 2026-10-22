"""Снимок спроса называет ОХВАТ сохранённых страниц, а не только их число.

Повод измеренный, 22.10. По сохранённым десяти страницам я разобрала состав
поисковых входов двух домéнов и сравнила разборы между собой. Оказалось, что
опирались они на разную полноту: у `animedia.icu` десять страниц несут **82.8 %**
поискового итога, у `lordserials22.info` — **25.6 %** при 144 страницах в
разрезе. Сравнение состава без охвата было бы сравнением разных по полноте
картин.

Примечание «страниц в разрезе 144, сохранено 10» этого не показывает: число
страниц не говорит, какую долю визитов они несут. Поэтому охват — отдельное
числовое поле, обязательное схемой.
"""
from __future__ import annotations

import json
import pathlib

import pytest

jsonschema = pytest.importorskip("jsonschema")

КОРЕНЬ = pathlib.Path(__file__).resolve().parents[2]
СНИМОК = КОРЕНЬ / "config" / "demand-snapshot.json"
СХЕМА = КОРЕНЬ / "schemas" / "demand-snapshot.schema.json"


@pytest.fixture(scope="module")
def снимок() -> dict:
    return json.loads(СНИМОК.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def схема() -> dict:
    return json.loads(СХЕМА.read_text(encoding="utf-8"))


def test_охват_есть_у_каждого_домена(снимок):
    без = [з["domain"] for з in снимок["domains"]
           if "search_landing_covered" not in з]
    assert not без, без


def test_охват_обязателен_схемой(схема):
    """Иначе снимок без охвата пройдёт молча, и разбор снова будет неполным."""
    def найти(о):
        if isinstance(о, dict):
            if "properties" in о and "search_pages_total" in о["properties"]:
                return о
            for зн in о.values():
                н = найти(зн)
                if н is not None:
                    return н
        elif isinstance(о, list):
            for зн in о:
                н = найти(зн)
                if н is not None:
                    return н
        return None

    узел = найти(схема)
    assert узел is not None
    assert "search_landing_covered" in узел["required"]


def test_охват_сходится_с_сохранёнными_страницами(снимок):
    """Величина не придумана: она считается из того же снимка."""
    плохие = []
    for з in снимок["domains"]:
        поиск = з.get("search_visits") or 0
        сумма = sum((с.get("visits") or 0)
                    for с in (з.get("search_landing_pages") or []))
        ожидалось = round(100 * сумма / поиск, 1) if поиск else None
        if з.get("search_landing_covered") != ожидалось:
            плохие.append((з["domain"], з.get("search_landing_covered"),
                           ожидалось))
    assert not плохие, плохие


def test_без_поиска_охват_не_ноль_а_неизвестен(снимок):
    """Ноль здесь был бы выдумкой: делить нечего, а не нечем."""
    for з in снимок["domains"]:
        if not (з.get("search_visits") or 0):
            assert з.get("search_landing_covered") is None, з["domain"]


def test_охват_в_разумных_границах(снимок):
    for з in снимок["domains"]:
        о = з.get("search_landing_covered")
        if о is None:
            continue
        assert 0 <= о <= 100, (з["domain"], о)


def test_разброс_охвата_реальный_и_потому_поле_нужно(снимок):
    """Если бы охват был у всех одинаков, поле было бы украшением.

    Проверка намеренно мягкая: требуется не конкретное число, а то, что
    разброс ЕСТЬ — иначе разбор состава можно было бы сравнивать без него.
    """
    охваты = [з["search_landing_covered"] for з in снимок["domains"]
              if з.get("search_landing_covered") is not None
              and (з.get("search_visits") or 0) >= 20]
    assert охваты
    assert max(охваты) - min(охваты) > 20, охваты


def test_число_страниц_в_разрезе_не_равно_числу_сохранённых(снимок):
    """Печатать длину сохранённого как «страниц с поиском» — прежняя ошибка."""
    есть_разница = [з["domain"] for з in снимок["domains"]
                    if (з.get("search_pages_total") or 0)
                    > len(з.get("search_landing_pages") or [])]
    assert есть_разница, "ни у одного домена предел хранения не сработал"

# --- «прочие» поисковые системы получают ИМЕНА ----------------------------
#
# Мера сводила всё, кроме Яндекса и Google, в одну графу. Измерено 22.10: у
# `zonafilm.cc` эта графа несёт 99 визитов из 715 — `bing_search` 73,
# `duckduckgo` 22, `yahoo_search` 4, то есть 13.8 % поискового трафика домена.
# Называть восьмую часть трафика «прочие» значит не знать, откуда она.


def test_имена_прочих_систем_есть_у_каждого_домена(снимок):
    без = [з["domain"] for з in снимок["domains"]
           if "search_engines_other" not in з]
    assert not без, без


def test_сумма_прочих_сходится_с_группой(снимок):
    """Имена не подменяют группировку: суммы обязаны совпадать."""
    плохие = []
    for з in снимок["domains"]:
        группа = (з.get("search_engines") or {}).get("прочие", 0)
        поимённо = sum((з.get("search_engines_other") or {}).values())
        if группа != поимённо:
            плохие.append((з["domain"], группа, поимённо))
    assert not плохие, плохие


def test_пустой_словарь_значит_прочих_нет_а_не_не_смотрели(снимок):
    """У домена без прочих систем поле пустое, но ПРИСУТСТВУЕТ."""
    без_прочих = [з for з in снимок["domains"]
                  if not (з.get("search_engines") or {}).get("прочие")]
    assert без_прочих
    for з in без_прочих:
        assert з.get("search_engines_other") == {}, з["domain"]


def test_у_одного_домена_прочие_действительно_весомы(снимок):
    """Если бы они были везде единицами, поле было бы украшением."""
    веса = []
    for з in снимок["domains"]:
        поиск = з.get("search_visits") or 0
        прочие = sum((з.get("search_engines_other") or {}).values())
        if поиск:
            веса.append(100 * прочие / поиск)
    assert веса
    assert max(веса) > 5, max(веса)


def test_семьи_яндекса_и_google_в_прочие_не_попадают(снимок):
    """Иначе имена «прочих» подменят собой основные системы."""
    for з in снимок["domains"]:
        for имя in (з.get("search_engines_other") or {}):
            assert not имя.startswith(("yandex", "google")), (з["domain"], имя)
