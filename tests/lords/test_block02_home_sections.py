"""Block 02 — Lords home section order and non-duplication."""

from __future__ import annotations

import pathlib
import re

КОРЕНЬ = pathlib.Path(__file__).resolve().parents[2]
ИСХОДНИК = КОРЕНЬ / "automation" / "host" / "lords-frontend.py"


def _главная_src() -> str:
    текст = ИСХОДНИК.read_text(encoding="utf-8")
    # First ВидЛордс.главная (after class ВидЛордс)
    i = текст.index("class ВидЛордс")
    j = текст.index("def главная(self)", i)
    k = текст.index("\n    def ", j + 1)
    return текст[j:k]


class TestHomeSectionOrder:
    def test_cinema_branch_premiere_before_new(self):
        src = _главная_src()
        # lords-cinema-v2 branch: Премьеры → Фильмы по жанрам → Новинки
        assert '_полоса("Премьеры недели"' in src
        assert src.index('_полоса("Премьеры недели"') < src.index('_полоса("Новинки"')
        assert '_полоса("Фильмы по жанрам"' in src

    def test_series_and_curated_branches_present(self):
        src = _главная_src()
        assert "lords-series-feed-v2" in src
        assert "lords-curated-v2" in src
        assert "Продолжающиеся сериалы" in src
        assert "Выбор редакции" in src

    def test_no_popular_or_high_rating_duplicate_shelves(self):
        src = _главная_src()
        assert "Популярное сейчас" not in src
        assert "Высокий рейтинг" not in src

    def test_empty_section_returns_empty_string(self):
        текст = ИСХОДНИК.read_text(encoding="utf-8")
        assert "def _полоса(self, титул: str, ссылка: str, набор" in текст
        блок = текст[текст.index("def _полоса"):текст.index("def _полоса_подборок")]
        assert 'if not набор:\n            return ""' in блок

    def test_nav_films_before_new(self):
        текст = ИСХОДНИК.read_text(encoding="utf-8")
        m = re.search(r'"lords":\s*\{.*?"нав":\s*\[(.*?)\]', текст, re.S)
        assert m
        nav = m.group(1)
        assert nav.index("/movies/") < nav.index("/new/")
        assert nav.index("/series/") < nav.index("/new/")

    def test_dedupe_set_used(self):
        src = _главная_src()
        assert "занято" in src
        assert 'з["slug"] in занято' in src
