"""Разметка против видимого: признак называет себя, иначе ноль не проверить.

Первая версия замечания гласила «крошки не объявлены ни навигацией, ни
расширенным результатом», а измерялось ровно одно — отсутствие узла
`BreadcrumbList`. Отсутствие узла разметки не означает отсутствия видимых
крошек. По правилу 10 признак видимых крошек называется в самом выводе.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

ПУТЬ = (Path(__file__).resolve().parents[2] / "automation" / "local"
        / "schema-vs-visible.py")


def _модуль():
    спец = importlib.util.spec_from_file_location("schema_vs_visible", ПУТЬ)
    м = importlib.util.module_from_spec(спец)
    спец.loader.exec_module(м)
    return м


МОД = _модуль()


def test_узлы_разбираются_и_список_и_одиночный():
    один = '<script type="application/ld+json">{"@type":"Movie"}</script>'
    список = ('<script type="application/ld+json">'
              '[{"@type":"WebSite"},{"@type":"Movie"}]</script>')
    assert [у["@type"] for у in МОД.узлы(один)[0]] == ["Movie"]
    assert [у["@type"] for у in МОД.узлы(список)[0]] == ["WebSite", "Movie"]


def test_битый_блок_называется_а_не_пропускается():
    """Иначе страница с нерабочей разметкой выглядела бы страницей без неё."""
    собрано, битые = МОД.узлы(
        '<script type="application/ld+json">{нет</script>')
    assert собрано == []
    assert len(битые) == 1, битые


def test_видимый_текст_не_включает_мета_теги():
    """`description` несёт жанры и там, где на странице их нет.

    Если считать мета видимым, несоответствие исчезнет, а посетитель всё равно
    ничего не увидит.
    """
    тело = ('<head><meta name="description" content="Жанры: драма, ужасы">'
            "</head><body><p>Описание фильма</p></body>")
    видимо = МОД.видимый_текст(тело)
    assert "описание фильма" in видимо
    assert "драма" not in видимо, видимо


def test_видимый_текст_не_включает_скрипты_и_стили():
    тело = ("<body><script>var жанр='драма';</script>"
            "<style>.x{content:'ужасы'}</style><p>текст</p></body>")
    видимо = МОД.видимый_текст(тело)
    assert "текст" in видимо
    assert "драма" not in видимо and "ужасы" not in видимо


def test_значения_поля_читаются_из_строки_списка_и_узла():
    assert МОД.значения("Драма") == ["Драма"]
    assert МОД.значения(["Драма", "Ужасы"]) == ["Драма", "Ужасы"]
    assert МОД.значения({"@type": "Country", "name": "США"}) == ["США"]
    assert МОД.значения(None) == []


def test_признак_видимых_крошек_назван_списком():
    """Список печатается в выводе: ноль неполного признака иначе не отличить."""
    assert len(МОД.ПРИЗНАКИ_КРОШЕК) == 3
    assert any("крошк" in п for п in МОД.ПРИЗНАКИ_КРОШЕК)
    assert any("breadcrumb" in п for п in МОД.ПРИЗНАКИ_КРОШЕК)


def test_видимые_крошки_находятся_по_каждому_признаку():
    да, чем = МОД.видимые_крошки('<nav aria-label="Хлебные крошки"></nav>')
    assert да and "крошк" in чем
    да, чем = МОД.видимые_крошки('<ol class="breadcrumbs"></ol>')
    assert да and "breadcrumb" in чем
    да, чем = МОД.видимые_крошки('<a href="/">Главная</a>')
    assert да and "Главная" in чем


def test_страница_без_признаков_крошек_даёт_ложь_и_пустой_признак():
    да, чем = МОД.видимые_крошки("<body><h1>Тайтл</h1></body>")
    assert not да and чем == ""


def test_типы_произведения_не_включают_узлы_о_сайте():
    assert "WebSite" not in МОД.ТИПЫ_ПРОИЗВЕДЕНИЯ
    assert "BreadcrumbList" not in МОД.ТИПЫ_ПРОИЗВЕДЕНИЯ
    assert "Movie" in МОД.ТИПЫ_ПРОИЗВЕДЕНИЯ and "TVSeries" in МОД.ТИПЫ_ПРОИЗВЕДЕНИЯ
