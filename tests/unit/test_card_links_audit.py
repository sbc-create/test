"""Переходы по таксономии: обе формы адреса, и текст ссылкой не считается.

Формы две, и обе встречаются в сети: путём (`/genre/drama/`) у Lords и AnimeGo,
параметром (`/catalog/?genre=drama`) у Zona и Animedia. Признак, знающий одну
форму, объявил бы половину сети тупиковой — та же ошибка, что с формой адреса
карточки (`/title/` против `/anime/`).
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

ПУТЬ = (Path(__file__).resolve().parents[2] / "automation" / "local"
        / "card-links-audit.py")


def _модуль():
    спец = importlib.util.spec_from_file_location("card_links_audit", ПУТЬ)
    м = importlib.util.module_from_spec(спец)
    спец.loader.exec_module(м)
    return м


МОД = _модуль()


def test_жанр_путём_и_параметром_оба_считаются():
    п = МОД.переходы('<a href="/genre/drama/">д</a>'
                     '<a href="/catalog/?genre=horror">у</a>')
    assert len(п["жанр"]) == 2, п["жанр"]


def test_текст_без_ссылки_переходом_не_считается():
    """B017 ровно про это: жанр, выведенный текстом, выглядит ссылкой."""
    п = МОД.переходы("<dd>драма · мелодрама</dd>")
    assert sum(len(v) for v in п.values()) == 0, п


def test_один_жанр_в_двух_местах_это_один_переход():
    """Жанр стоит и в характеристиках, и в крошках — переход один."""
    п = МОД.переходы('<a href="/genre/drama/">д</a>'
                     '<nav><a href="/genre/drama/">д</a></nav>')
    assert len(п["жанр"]) == 1, п["жанр"]


def test_год_страна_и_раздел_различаются():
    п = МОД.переходы('<a href="/year/2026/">2026</a>'
                     '<a href="/c/usa/">США</a>'
                     '<a href="/movies/">Фильмы</a>')
    assert len(п["год"]) == 1 and len(п["страна"]) == 1 and len(п["раздел"]) == 1


def test_процентное_кодирование_раскрывается():
    """Иначе один и тот же жанр в двух записях считался бы двумя."""
    п = МОД.переходы('<a href="/catalog/?genre=%D0%B4%D1%80%D0%B0%D0%BC%D0%B0">д</a>')
    assert п["жанр"] == ["/catalog/?genre=драма"], п["жанр"]


def test_форма_адреса_карточки_известна_в_двух_видах():
    тело = '<a href="/anime/alpha">A</a>'
    assert МОД.карточки(тело) == ["/anime/alpha"]
    assert МОД.карточки('<a href="/title/beta">B</a>') == ["/title/beta"]
    assert МОД.карточки('<a href="/film/gamma">G</a>') == []


def test_закрытая_страница_распознаётся_и_заголовком_и_meta():
    assert МОД.закрыта("", {"x-robots-tag": "noindex, follow"})
    assert МОД.закрыта('<meta name="robots" content="NOINDEX">', {})
    assert not МОД.закрыта('<meta name="robots" content="index, follow">',
                           {"x-robots-tag": "index"})


def test_предел_целей_на_карточку_назван_числом():
    """Обход всех жанровых ссылок карточки — часы; предел должен быть явным."""
    assert isinstance(МОД.ЦЕЛЕЙ_НА_КАРТОЧКУ, int)
    assert МОД.ЦЕЛЕЙ_НА_КАРТОЧКУ >= 1
