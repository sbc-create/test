"""Пагинация показывает окно, а не весь каталог ссылками.

На боевой витрине первая страница каталога несла **2 253** ссылки пагинации
при 24 карточках: блок пагинации был в сотню раз объёмнее содержимого, весил
основную часть из ~132 тысяч знаков разметки и растягивался на тысячи
пикселей.

Причина прямая: разметка перечисляла все страницы циклом `range(1, pages + 1)`.

Скрыть лишнее стилями нельзя: узлы всё равно приходят по сети, разбираются
браузером и читаются экранным диктором. Их не должно быть в разметке.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from factory.lords import render as render_mod  # noqa: E402

MAX_LINKS = 11


def _links(html: str) -> list[str]:
    return re.findall(r"<a\b[^>]*>(.*?)</a>", html)


class TestОкноПагинации:
    def test_на_огромном_каталоге_ссылок_не_больше_одиннадцати(self):
        html = render_mod._pagination("/catalog/", 1, 2253)
        links = _links(html)
        assert len(links) <= MAX_LINKS, (
            f"ссылок {len(links)} при пределе {MAX_LINKS}: блок пагинации "
            "объёмнее содержимого страницы")

    def test_первая_и_последняя_страницы_достижимы(self):
        html = render_mod._pagination("/catalog/", 1100, 2253)
        assert 'href="/catalog/"' in html, "нет пути на первую страницу"
        assert "page/2253/" in html, "нет пути на последнюю страницу"

    def test_текущая_страница_объявлена(self):
        html = render_mod._pagination("/catalog/", 5, 2253)
        assert 'aria-current="page"' in html
        assert ">5<" in html

    def test_соседние_страницы_рядом(self):
        html = render_mod._pagination("/catalog/", 100, 2253)
        for n in (98, 99, 101, 102):
            assert f"page/{n}/" in html, f"страница {n} не в окне"

    def test_далёкие_страницы_не_рендерятся(self):
        html = render_mod._pagination("/catalog/", 100, 2253)
        assert "page/500/" not in html, "далёкая страница попала в разметку"
        assert "page/1500/" not in html

    def test_разрыв_обозначен(self):
        html = render_mod._pagination("/catalog/", 100, 2253)
        assert "…" in html or "..." in html, "разрыв между окном и краями не обозначен"

    def test_назад_и_вперёд_на_месте(self):
        html = render_mod._pagination("/catalog/", 5, 2253)
        assert 'rel="prev"' in html and 'rel="next"' in html

    def test_на_первой_странице_нет_назад(self):
        html = render_mod._pagination("/catalog/", 1, 10)
        assert 'rel="prev"' not in html

    def test_на_последней_нет_вперёд(self):
        html = render_mod._pagination("/catalog/", 10, 10)
        assert 'rel="next"' not in html

    def test_короткий_список_показан_целиком(self):
        """Пять страниц умещаются: разрывы и края здесь только мешают."""
        html = render_mod._pagination("/catalog/", 1, 5)
        for n in (2, 3, 4, 5):
            assert f"page/{n}/" in html
        assert "…" not in html

    def test_одна_страница_не_рисует_пагинацию(self):
        assert render_mod._pagination("/catalog/", 1, 1) == ""
