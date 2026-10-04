"""Карта сайта собирается из данных витрины и только для ОТКРЫТОГО режима.

Генератор карты (`построить_sitemap`) лежал во всех репозиториях семейства и не
вызывался НИ В ОДНОМ: измерено 2026-10-04 по девяти доменам — `/sitemap.xml`
отдавал 200 только animedia.space, у остальных восьми 404 и ни одной ссылки
`Sitemap:` в robots.txt. Здесь закреплён сборщик, который его зовёт, и те
свойства, из-за которых карту вообще можно отдавать поисковику:

* чужих домена в карте не бывает: адрес собирается из переданного хоста;
* служебных путей в карте не бывает;
* 404 в карте не бывает: адрес карточки берётся из её же записи в снимке —
  того самого поля, по которому витрина эту страницу и отдаёт;
* `lastmod` ставится только у ТОЧНЫХ дат: у снимка есть признак
  `published_at_estimated`, и оценочная дата, выданная за факт, обесценила бы
  поле у всех остальных страниц;
* закрытая витрина карту не публикует.
"""
from __future__ import annotations

import importlib.util
import pathlib
import xml.etree.ElementTree as ET

import pytest

КОРЕНЬ = pathlib.Path(__file__).resolve().parents[2]
ШАБЛОН = КОРЕНЬ / "automation" / "host" / "seo_layer.py"
NS = {"s": "http://www.sitemaps.org/schemas/sitemap/0.9"}


@pytest.fixture()
def слой():
    спец = importlib.util.spec_from_file_location("seo_layer_шаблон", ШАБЛОН)
    м = importlib.util.module_from_spec(спец)
    спец.loader.exec_module(м)
    return м


class _Данные:
    revision = "r1"

    def __init__(self, items):
        self.items = items


class _Рантайм:
    """Минимальная витрина: снимок, разделы и режим."""

    РАЗДЕЛЫ_КАРТЫ = ("/movies/", "/series/")

    def __init__(self, items, режим="OPEN"):
        self.Обработчик = type("О", (), {"данные": _Данные(items)})
        self._режим = режим

    def режим_индексации(self):
        return (self._режим, "стенд")


ЗАПИСИ = [
    {"url": "/title/первая/", "published_at": "2026-10-01T10:00:00Z",
     "published_at_estimated": False, "slug": "первая"},
    {"slug": "вторая", "published_at": "2026-09-30T10:00:00Z",
     "published_at_estimated": True},
    {"url": "/poster/служебный.webp", "slug": "служебный"},
    {"url": "/api/titles", "slug": "апи"},
    {"url": "/title/первая/", "slug": "первая"},          # дубль
    {"slug": ""},                                          # без адреса
]


def test_состав_карты_без_служебного_и_дублей(слой):
    страницы, разделы = слой.адреса_карты(_Рантайм(ЗАПИСИ))
    адреса = [с["url"] for с in страницы]
    assert "/poster/служебный.webp" not in адреса, "служебный путь попал в карту"
    assert "/api/titles" not in адреса, "служебный путь попал в карту"
    assert адреса.count("/title/первая/") == 2, (
        "сборщик не обязан снимать дубли — это делает построить_sitemap")
    assert "/title/вторая/" in адреса, "запись без url адресуется по slug"
    assert "" not in адреса
    assert разделы[0] == "/" and "/movies/" in разделы


def test_карта_несёт_только_свой_домен_и_точные_даты(слой, tmp_path):
    итог = слой.обновить_карту(_Рантайм(ЗАПИСИ), str(tmp_path), "t-map.example")
    assert итог["written"] is True, итог
    части = sorted(p for p in tmp_path.iterdir() if p.name.startswith("sitemap-"))
    корень = ET.fromstring(части[0].read_bytes())
    адреса = [э.text for э in корень.findall("s:url/s:loc", NS)]
    assert адреса, "карта пуста"
    assert all(а.startswith("https://t-map.example/") for а in адреса), адреса
    assert len(адреса) == len(set(адреса)), "дубли адресов остались"
    assert not any(("/poster/" in а or "/api/" in а or "/healthz" in а)
                   for а in адреса), адреса
    # Дата есть у записи с точной публикацией и отсутствует у оценочной.
    по_адресу = {э.findtext("s:loc", namespaces=NS): э.findtext("s:lastmod", namespaces=NS)
                 for э in корень.findall("s:url", NS)}
    assert по_адресу["https://t-map.example/title/первая/"] == "2026-10-01"
    assert по_адресу["https://t-map.example/title/вторая/"] is None, (
        "оценочная дата выдана за точную")


def test_индекс_ссылается_на_свои_части(слой, tmp_path):
    слой.обновить_карту(_Рантайм(ЗАПИСИ), str(tmp_path), "t-map.example")
    индекс = ET.fromstring((tmp_path / "sitemap.xml").read_bytes())
    ссылки = [э.text for э in индекс.findall("s:sitemap/s:loc", NS)]
    assert ссылки == ["https://t-map.example/sitemap-1.xml"], ссылки
    assert (tmp_path / "sitemap-1.xml").is_file()


def test_закрытая_витрина_карту_не_пишет(слой, tmp_path):
    итог = слой.обновить_карту(_Рантайм(ЗАПИСИ, режим="CLOSED"),
                               str(tmp_path), "t-map.example")
    assert итог["written"] is False
    assert "CLOSED" in итог["reason"]
    assert not list(tmp_path.iterdir()), "карта записана при закрытой индексации"


def test_пустой_снимок_не_затирает_прежнюю_карту(слой, tmp_path):
    слой.обновить_карту(_Рантайм(ЗАПИСИ), str(tmp_path), "t-map.example")
    было = (tmp_path / "sitemap-1.xml").read_bytes()
    итог = слой.обновить_карту(_Рантайм([]), str(tmp_path), "t-map.example")
    assert итог["written"] is False and "пуст" in итог["reason"], итог
    assert (tmp_path / "sitemap-1.xml").read_bytes() == было, (
        "пустой снимок стёр рабочую карту — это хуже устаревшей")


def test_поток_называет_причину_отказа(слой, monkeypatch, capsys):
    monkeypatch.delenv("LORDS_SITEMAP_DIR", raising=False)
    assert слой.запустить_карту(_Рантайм(ЗАПИСИ)) is False
    assert "LORDS_SITEMAP_DIR" in capsys.readouterr().out
    monkeypatch.setenv("LORDS_SITEMAP_DIR", "/tmp/нет")
    for имя in ("LORDS_SITE_HOST", "LORDS_INDEXING_SITE", "LORDS_SITE_DOMAIN"):
        monkeypatch.delenv(имя, raising=False)
    assert слой.запустить_карту(_Рантайм(ЗАПИСИ)) is False
    assert "домен" in capsys.readouterr().out
