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


# --- эталон из ld+json: четвёртый способ, и первый, не зависящий от разметки ---
#
# Три прежних давали неверный ответ, и каждый раз ответ был свойством признака:
# страница целиком не отличала сквозное меню от своего жанра; вычитание меню
# убивало жанр, который и в меню, и свой; список классов «блока характеристик»
# не знал контейнера `ztitle__genres` у Zona — и признак напечатал «ноль
# ссылок» про витрину, где связаны все три жанра.

def test_объявленные_жанры_берутся_из_узла_произведения():
    тело = ('<script type="application/ld+json">'
            '{"@type":"TVSeries","genre":["Драма","Ужасы"]}</script>')
    assert МОД.объявленные_жанры(тело) == ["Драма", "Ужасы"]


def test_жанр_строкой_а_не_списком_тоже_читается():
    тело = ('<script type="application/ld+json">'
            '{"@type":"Movie","genre":"Драма"}</script>')
    assert МОД.объявленные_жанры(тело) == ["Драма"]


def test_узлы_о_сайте_жанров_не_дают():
    """`WebSite` и `BreadcrumbList` описывают сайт, а не произведение."""
    тело = ('<script type="application/ld+json">'
            '{"@type":"WebSite","genre":["Чепуха"]}</script>')
    assert МОД.объявленные_жанры(тело) == []


def test_битый_блок_не_валит_разбор_остальных():
    тело = ('<script type="application/ld+json">{не json</script>'
            '<script type="application/ld+json">'
            '{"@type":"Movie","genre":["Драма"]}</script>')
    assert МОД.объявленные_жанры(тело) == ["Драма"]


def test_повтор_жанра_в_двух_узлах_это_один_жанр():
    тело = ('<script type="application/ld+json">'
            '{"@type":"Movie","genre":["Драма"]}</script>'
            '<script type="application/ld+json">'
            '{"@type":"VideoObject","genre":["драма"]}</script>')
    assert МОД.объявленные_жанры(тело) == ["Драма"]


def test_связь_по_тексту_ссылки():
    """Zona: адрес несёт КОД (`west_content`), а имя стоит текстом ссылки."""
    тело = '<a href="/catalog/?genre=horror">ужасы</a>'
    assert МОД.связан("Ужасы", тело)


def test_связь_по_адресу_с_параметром():
    тело = '<a href="/catalog/?genre=%D1%83%D0%B6%D0%B0%D1%81%D1%8B">смотреть</a>'
    assert МОД.связан("ужасы", тело)


def test_связь_путём_когда_код_и_есть_имя():
    тело = '<a href="/genre/drama/">подборка</a>'
    assert МОД.связан("drama", тело)


def test_жанр_текстом_без_ссылки_связью_не_считается():
    """B017 ровно про это, и это единственная настоящая находка класса."""
    тело = '<dd>Боевик · Фэнтези</dd><a href="/catalog/">Каталог</a>'
    assert not МОД.связан("Боевик", тело)
    assert not МОД.связан("Фэнтези", тело)
