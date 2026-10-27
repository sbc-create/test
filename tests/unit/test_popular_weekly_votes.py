"""Недельная полка не ставит наверх оценку по десятку голосов.

Повод измеренный (линия SEO, 27.10 09:40Z, живые главные): в блоке «Высокие
оценки недели» наверху стояли 8.5 при 14 голосах, 8.5 при 16, 8.2 при 12, а
рядом — работы, у которых числа голосов в каталоге нет вовсе. Поручение
владельца: «Высокая оценка с несколькими голосами не должна автоматически
давать первое место. Учесть объём выборки».

Проверяется поведение сборщика снимка, а не текст: работы без известного
числа оценок и работы ниже порога в ранжирование не попадают.
"""
from __future__ import annotations

import importlib.util
import pathlib

import pytest

КОРЕНЬ = pathlib.Path(__file__).resolve().parents[2]
СБОРЩИКИ = (
    КОРЕНЬ / "var" / "site-repos" / "zonafilm-space" / "src" / "popular_weekly.py",
    КОРЕНЬ / "var" / "site-repos" / "zonafilm12-site" / "src" / "popular_weekly.py",
)


@pytest.fixture(params=СБОРЩИКИ, ids=lambda п: п.parts[-3])
def м(request):
    спец = importlib.util.spec_from_file_location("popular_weekly", request.param)
    модуль = importlib.util.module_from_spec(спец)
    спец.loader.exec_module(модуль)
    return модуль


def _данные(записи):
    items = [{"slug": с, "kind": k, "published_at": p} for с, k, p, _, _ in записи]
    details = {с: {"imdb_rating": r,
                   "ratings_by_source": ({"imdb": {"votes": v}} if v is not None else {})}
               for с, _, _, r, v in записи}
    return items, details


def test_мало_голосов_не_попадает_в_полку(м):
    items, details = _данные([
        ("malo", "Фильм", "2026-10-26T00:00:00Z", 9.8, 14),
        ("mnogo", "Фильм", "2026-10-25T00:00:00Z", 7.1, 120_000),
    ])
    снимок = м.build_snapshot(items, details, clock="2026-10-27T00:00:00Z")
    полка = снимок["shelves"]["pop-films"]
    assert "malo" not in полка, полка
    assert полка == ["mnogo"], полка


def test_без_числа_голосов_не_попадает(м):
    """Отсутствие числа — это «неизвестно», а не «мало»: проверить нечем."""
    items, details = _данные([
        ("bez", "Фильм", "2026-10-26T00:00:00Z", 9.0, None),
        ("s", "Фильм", "2026-10-25T00:00:00Z", 6.0, 5_000),
    ])
    снимок = м.build_snapshot(items, details, clock="2026-10-27T00:00:00Z")
    assert снимок["shelves"]["pop-films"] == ["s"]


def test_порог_назван_в_снимке(м):
    """Снимок обязан объявлять, по какому правилу собран: иначе через месяц
    никто не отличит его от прежнего."""
    items, details = _данные([("x", "Фильм", "2026-10-26T00:00:00Z", 8.0, 9_000)])
    снимок = м.build_snapshot(items, details, clock="2026-10-27T00:00:00Z")
    assert снимок["ranking_signal"] == "source_rating_in_recent_pool_min_votes"
    assert снимок["min_votes"] == м.MIN_VOTES
    assert м.MIN_VOTES >= 1000, м.MIN_VOTES


def test_порядок_по_оценке_среди_годных(м):
    items, details = _данные([
        ("sredne", "Сериал", "2026-10-26T00:00:00Z", 7.0, 50_000),
        ("luchshe", "Сериал", "2026-10-24T00:00:00Z", 8.4, 50_000),
    ])
    снимок = м.build_snapshot(items, details, clock="2026-10-27T00:00:00Z")
    assert снимок["shelves"]["pop-series"] == ["luchshe", "sredne"]


def test_пул_достаточен_чтобы_полка_не_пустела(м):
    """400 последних поступлений с порогом давали 3/1/0 — почти пустую полку."""
    assert м.DEFAULT_POOL >= 3000, м.DEFAULT_POOL


def test_блок_больше_не_обещает_неделю():
    """Имя блока обязано совпадать с основанием: состав — оценки, а не
    события недели."""
    for имя in ("zonafilm-space", "zonafilm12-site"):
        т = (КОРЕНЬ / "var" / "site-repos" / имя / "src"
             / "lords-frontend.py").read_text(encoding="utf-8")
        assert "Высокие оценки недели" not in т, имя
        assert "Высокие оценки зрителей" in т, имя
        for ярлык in ("Фильмы недели", "Сериалы недели", "Анимация недели"):
            assert f'"{ярлык}"' not in т, (имя, ярлык)


def test_аниме_блок_не_обещает_популярности():
    """Состав взят из утверждённого недельного снимка витрины-оригинала, а не
    из данных о просмотрах и не из нашего отбора. Имя «Популярное за неделю»
    обещало первое, «Выбор редакции» обещало бы второе; верное имя — «Аниме
    недели» (решение линии SEO, 27.10)."""
    т = (КОРЕНЬ / "var" / "site-repos" / "animedia-icu" / "src"
         / "animedia-frontend.py").read_text(encoding="utf-8")
    assert '"Популярное за неделю"' not in т
    assert '"Аниме недели"' in т
