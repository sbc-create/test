"""Проверка защиты зарабатывающих страниц: вывод без контроля не делается.

Проверяются чистые функции: разбор признаков, различающий исход, выборка с
семенем. Сеть не трогается — тела страниц заданы в тесте.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

ИСТОЧНИК = (Path(__file__).resolve().parents[2]
            / "automation" / "local" / "earning-pages-guard.py")


@pytest.fixture()
def м():
    спец = importlib.util.spec_from_file_location("earning_guard", ИСТОЧНИК)
    модуль = importlib.util.module_from_spec(спец)
    спец.loader.exec_module(модуль)
    return модуль


ЦЕЛАЯ = ('<html><head><meta name="robots" content="index, follow">'
         '<link rel="canonical" href="https://d.test/title/x/"></head>'
         '<body><h1>Название</h1><iframe src="https://player/"></iframe>'
         '</body></html>')


def test_целая_страница_не_даёт_ни_одной_беды(м):
    з = {"код": "200", "признаки": м.признаки(ЦЕЛАЯ, "/title/x/", "d.test")}
    assert м.беда(з) == []


def test_noindex_на_зарабатывающей_это_беда(м):
    тело = ЦЕЛАЯ.replace("index, follow", "noindex, follow")
    з = {"код": "200", "признаки": м.признаки(тело, "/title/x/", "d.test")}
    assert any("noindex" in б for б in м.беда(з))


def test_canonical_на_другой_адрес_это_беда(м):
    тело = ЦЕЛАЯ.replace("https://d.test/title/x/", "https://d.test/other/")
    п = м.признаки(тело, "/title/x/", "d.test")
    assert п["canonical"] == "на /other/"
    assert any("canonical" in б for б in м.беда({"код": "200", "признаки": п}))


def test_canonical_без_схемы_и_хоста_сравнивается_по_пути(м):
    тело = ЦЕЛАЯ.replace("https://d.test/title/x/", "/title/x")
    п = м.признаки(тело, "/title/x/", "d.test")
    assert п["canonical"] == "на себя"


def test_пустой_h1_это_беда(м):
    тело = ЦЕЛАЯ.replace("<h1>Название</h1>", "<h1>   </h1>")
    з = {"код": "200", "признаки": м.признаки(тело, "/title/x/", "d.test")}
    assert "h1 пуст" in м.беда(з)


def test_отсутствие_плеера_на_странице_произведения_это_беда(м):
    тело = ЦЕЛАЯ.replace('<iframe src="https://player/"></iframe>', "")
    з = {"код": "200", "признаки": м.признаки(тело, "/title/x/", "d.test")}
    assert "признака плеера нет" in м.беда(з)


def test_каталогу_плеер_не_требуется(м):
    """Требовать плеер от каталога значит выдумать дефект."""
    тело = ЦЕЛАЯ.replace('<iframe src="https://player/"></iframe>', "")
    тело = тело.replace("https://d.test/title/x/", "https://d.test/catalog/")
    п = м.признаки(тело, "/catalog/", "d.test")
    assert п["плеер"] is None
    assert м.беда({"код": "200", "признаки": п}) == []


def test_код_404_это_беда(м):
    з = {"код": "404", "признаки": м.признаки(ЦЕЛАЯ, "/title/x/", "d.test")}
    assert "код 404" in м.беда(з)


def test_пустое_тело_это_не_измерено_а_не_беда(м):
    """Отсутствие тела — отсутствие измерения, а не плохие признаки."""
    п = м.признаки("", "/title/x/", "d.test")
    assert п == {"robots": None, "canonical": None, "h1": None, "плеер": None}
    assert м.беда({"код": "", "признаки": п}) == []


# --- различающий исход ------------------------------------------------------

def _страница(беда=False):
    тело = ЦЕЛАЯ if not беда else ЦЕЛАЯ.replace("index, follow", "noindex")
    return {"код": "200", "беда": [], "путь": "/title/x/",
            "признаки": {"robots": "noindex" if беда else "index, follow",
                         "canonical": "на себя", "h1": "Н", "плеер": True}}


def test_без_контроля_исход_не_делается(м):
    assert м.исход([_страница()], []).startswith("НЕ ИЗМЕРЕНО")


def test_пустой_перечень_зарабатывающих_это_не_измерено(м):
    assert м.исход([], [_страница()]).startswith("НЕ ИЗМЕРЕНО")


def test_беда_только_на_зарабатывающих_называется_своим_именем(м):
    и = м.исход([_страница(беда=True)], [_страница()])
    assert и.startswith("БЕДА НА ЗАРАБАТЫВАЮЩИХ")


def test_беда_и_там_и_там_это_беда_витрины(м):
    и = м.исход([_страница(беда=True)], [_страница(беда=True)])
    assert и.startswith("БЕДА ВИТРИНЫ")


def test_беда_только_в_контроле_не_называется_бедой_зарабатывающих(м):
    и = м.исход([_страница()], [_страница(беда=True)])
    assert и.startswith("БЕДА В КОНТРОЛЕ")


def test_исправно_называет_оба_числа(м):
    и = м.исход([_страница(), _страница()], [_страница()])
    assert и.startswith("исправно") and "2 из 2" in и and "1 из 1" in и


# --- выборка и карта --------------------------------------------------------

def test_выборка_с_одним_семенем_повторяется(м):
    адреса = [f"/title/{i}/" for i in range(100)]
    assert м.выборка(адреса, 20261022, 5) == м.выборка(адреса, 20261022, 5)


def test_разные_семена_дают_разную_выборку(м):
    адреса = [f"/title/{i}/" for i in range(100)]
    assert м.выборка(адреса, 1, 5) != м.выборка(адреса, 2, 5)


def test_выборка_меньше_запроса_отдаёт_всё_без_повторов(м):
    assert м.выборка(["/a/", "/a/", "/b/"], 1, 5) == ["/a/", "/b/"]


def test_части_индекса_отделяются_от_страниц(м):
    тело = ("<loc>https://d.test/sitemap-1.xml</loc>"
            "<loc>https://d.test/title/x/</loc>")
    части, страницы = м.адреса_карты(тело)
    assert части == ["https://d.test/sitemap-1.xml"]
    assert страницы == ["https://d.test/title/x/"]


def test_пустая_карта_не_даёт_контроля(м):
    assert м.адреса_карты("") == ([], [])
    assert м.выборка([], 1, 5) == []


# --- знак плеера измерен, а не придуман -------------------------------------

def test_знак_плеера_узнаёт_монтаж_питоновского_семейства(м):
    """`data-player-host` — измеренный монтаж animedia/lords/zona."""
    тело = ('<html><head><meta name="robots" content="index, follow">'
            '<link rel="canonical" href="/title/x/"></head><body><h1>Н</h1>'
            '<div data-player data-state="resolving">'
            '<div data-player-host data-src-candidates="[]"></div></div>'
            '</body></html>')
    assert м.признаки(тело, "/title/x/", "d.test")["плеер"] is True


def test_знак_плеера_узнаёт_монтаж_yummy_без_host(м):
    """У Yummy на Next.js `data-player-host` нет вовсе — знак общий."""
    тело = ('<html><head><meta name="robots" content="index, follow">'
            '<link rel="canonical" href="/anime/x"></head><body><h1>Н</h1>'
            '<section data-player></section></body></html>')
    assert м.признаки(тело, "/anime/x", "d.test")["плеер"] is True


def test_первая_редакция_знака_не_нашла_бы_ни_одного_монтажа(м):
    """Знак, не находящийся НИГДЕ, включая контроль, — отказ меры.

    Разметка ниже — настоящая со страницы `animedia.icu`: ни `<iframe`, ни
    класса `player` в ней нет, и прежний знак дал «плеера нет» на всех
    десяти зарабатывающих И на всех пяти контрольных.
    """
    прежний = м.re.compile(r"<iframe|class=\"[^\"]*player|id=\"[^\"]*player",
                           м.re.I)
    разметка = '<div class="zpl__f" data-player data-state="resolving">'
    assert not прежний.search(разметка)
    assert м.ПРИЗНАК_ПЛЕЕРА.search(разметка)
