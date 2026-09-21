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
    def test_cinema_branch_films_new_popular(self):
        src = _главная_src()
        cinema = src[src.index("# Cinema IA"):]
        titles = re.findall(r'_полоса\(\s*"([^"]+)"', cinema)
        assert titles[:3] == ["Фильмы", "Недавно добавлено", "Популярное"]
        assert "Премьеры недели" not in cinema

    def test_series_and_curated_branches_present(self):
        src = _главная_src()
        assert "lords-series-feed-v2" in src
        assert "lords-curated-v2" in src
        # Honest labels: no false ongoing / editorial claims.
        assert "Сериалы в каталоге" in src
        assert "Высокие оценки" in src
        assert "Продолжающиеся сериалы" not in src
        assert "Выбор редакции" not in src

    def test_no_popular_or_high_rating_duplicate_shelves(self):
        src = _главная_src()
        assert "Популярное сейчас" not in src
        assert "Высокий рейтинг" not in src

    def test_empty_section_returns_empty_string(self):
        текст = ИСХОДНИК.read_text(encoding="utf-8")
        assert "def _полоса(self, титул: str, ссылка: str, набор" in текст
        блок = текст[текст.index("def _полоса"):текст.index("def _полоса_подборок")]
        assert 'if not набор:\n            return ""' in блок

    def test_nav_films_before_new_in_cinema(self):
        текст = ИСХОДНИК.read_text(encoding="utf-8")
        # Cinema nav lives in _лорды_нав default branch.
        i = текст.index("def _лорды_нав()")
        j = текст.index("\ndef _лорды_лид()", i)
        nav_fn = текст[i:j]
        assert nav_fn.index('("/movies/", "Фильмы")') < nav_fn.index('("/new/", "Новое в каталоге")')
        assert nav_fn.index('("/series/", "Сериалы")') < nav_fn.index('("/new/", "Новое в каталоге")')

    def test_dedupe_set_used(self):
        src = _главная_src()
        assert "занято" in src
        assert 'з["slug"] in занято' in src
