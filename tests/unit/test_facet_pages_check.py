"""REQ-SEO-FACET-CHECK: признак «фасет называет себя» различает три формы.

Инструмент появился после измеренного дефекта: 2026-10-18 на восьми витринах
партии K2 `/genre/boevik/` отдавал 11 830 записей из 66 159, а title и h1 были
«Каталог», canonical — `/catalog/`. Двенадцать ссылок с главной вели на
страницы, которые сами от себя отказываются.

Остальные двенадцать витрин сети этим не болели — значит дефект приходит с
партией, а не живёт в семействе, и проверка нужна постоянная.

Здесь проверяется ПРИЗНАК, а не сеть: он должен различать три формы канона
(путь, запрос, чужая страница) и не считать дефектом то, что дефектом не
является.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

ПУТЬ = (Path(__file__).resolve().parents[2] / "automation" / "local"
        / "facet-pages-check.py")


def _модуль():
    спец = importlib.util.spec_from_file_location("facet_pages_check", ПУТЬ)
    м = importlib.util.module_from_spec(спец)
    спец.loader.exec_module(м)
    return м


МОД = _модуль()


def test_канон_на_себя_путём():
    assert МОД.канон_свой("https://x.example/genre/boevik/",
                          "/genre/boevik/") is True


def test_канон_на_себя_запросом():
    """У Zona и Animedia канонична форма с запросом — требовать путь нельзя."""
    assert МОД.канон_свой("https://x.example/catalog/?genre=action",
                          "/catalog/?genre=action") is True


def test_канон_на_каталог_это_дефект():
    """Ровно то, что измерено на восьми витринах."""
    assert МОД.канон_свой("https://x.example/catalog/", "/genre/boevik/") is False


def test_пустой_канон_не_считается_своим():
    """Отсутствие canonical — не доказательство, что страница назвала себя."""
    assert МОД.канон_свой("", "/genre/boevik/") is False


def test_похожий_путь_не_проходит():
    """Отрицательный контроль к сравнению строк."""
    assert МОД.канон_свой("https://x.example/genre/boevik-2/",
                          "/genre/boevik/") is False


def test_обе_формы_ссылок_распознаются():
    разметка = ('<a href="/genre/boevik/">Боевик</a>'
                '<a href="/country/ssha/">США</a>')
    assert МОД.ссылки_фасетов(разметка) == ["/country/ssha/", "/genre/boevik/"]
    запросная = '<a href="/catalog/?genre=action">Боевик</a>'
    assert МОД.ссылки_фасетов(запросная) == ["/catalog/?genre=action"]


def test_путевая_форма_имеет_приоритет():
    """Если есть обе, берётся путь: у Lords он канонический, и проверять надо
    то, что витрина объявляет каноном."""
    разметка = ('<a href="/catalog/?genre=action">А</a>'
                '<a href="/genre/boevik/">Б</a>')
    assert МОД.ссылки_фасетов(разметка) == ["/genre/boevik/"]


def test_служебные_ссылки_не_считаются_фасетами():
    разметка = '<a href="/catalog/?kind=Сериал">С</a><a href="/new/">Н</a>'
    assert МОД.ссылки_фасетов(разметка) == []


def test_мета_читает_заголовок_и_канон():
    т = ('<title>Боевик — витрина</title>'
         '<link rel="canonical" href="https://x.example/genre/boevik/">'
         '<h1 class="lead">Боевик</h1>')
    титул, h1, канон = МОД.мета(т)
    assert титул == "Боевик — витрина"
    assert h1 == "Боевик"
    assert канон == "https://x.example/genre/boevik/"


def test_мета_не_падает_на_пустой_странице():
    assert МОД.мета("") == ("", "", "")
