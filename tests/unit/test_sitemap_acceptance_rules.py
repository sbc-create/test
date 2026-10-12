"""Правила приёмки карты сайта: три ложных срабатывания и их границы.

Прогон 12.10 по `yummyani.site` и `yummyani7.site` — витринам с наибольшим
трафиком сети — дал три FAIL, и все три были ложными. Инструмент, который
кричит зря на главном сайте, перестают читать, и тогда настоящий отказ пройдёт
незамеченным. Дожили эти срабатывания до живых витрин потому, что решения жили
внутри сетевой функции: стенда, на котором они видны, не существовало.

Поэтому здесь закреплены не только исправления, но и их ГРАНИЦЫ: ослабленная
проверка обязана по-прежнему ловить настоящий дефект.
"""
from __future__ import annotations

import importlib.util
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

КОРЕНЬ = Path(__file__).resolve().parents[2]
ИСТОЧНИК = КОРЕНЬ / "automation" / "local" / "sitemap-acceptance.py"


def _модуль():
    спец = importlib.util.spec_from_file_location("sitemap_acceptance",
                                                  ИСТОЧНИК)
    м = importlib.util.module_from_spec(спец)
    sys.modules["sitemap_acceptance"] = м
    спец.loader.exec_module(м)
    return м


па = _модуль()

SM = "http://www.sitemaps.org/schemas/sitemap/0.9"
IMG = "http://www.google.com/schemas/sitemap-image/1.1"


# ---------------------------------------------------------------- один адрес
def test_главная_со_слэшем_и_без_это_один_адрес():
    """RFC 3986: пустой путь нормализуется в «/». Это ОДИН адрес.

    В карте стоит `https://host/`, страница объявляет `https://host` — и
    сравнение строк называло это расхождением у каждой главной.
    """
    assert па.один_адрес("https://yummyani.site", "https://yummyani.site/")
    assert па.один_адрес("https://yummyani.site/", "https://yummyani.site")


def test_слэш_в_конце_пути_расхождение_настоящее():
    """Граница послабления: `/catalog` и `/catalog/` — РАЗНЫЕ адреса."""
    assert not па.один_адрес("https://проба.test/catalog",
                             "https://проба.test/catalog/")


def test_разные_хосты_одним_адресом_не_становятся():
    assert not па.один_адрес("https://проба.test/", "https://www.проба.test/")


def test_разные_пути_различаются():
    assert not па.один_адрес("https://проба.test/a", "https://проба.test/b")


# ------------------------------------------------------------ служебные пути
def test_человеческая_карта_служебной_не_считается():
    """`/sitemap` — настоящая HTML-страница с canonical на себя и index, follow."""
    assert па.служебные_адреса(["https://проба.test/sitemap"]) == []


def test_файл_карты_внутри_карты_это_дефект():
    """Карта не перечисляет себя как страницу — это настоящее замечание."""
    плохо = па.служебные_адреса(["https://проба.test/sitemap.xml",
                                 "https://проба.test/sitemap/titles.xml"])
    assert len(плохо) == 2, плохо


def test_настоящие_служебные_пути_по_прежнему_ловятся():
    """Послабление не должно открыть дорогу остальному перечню."""
    адреса = [f"https://проба.test{п}" for п in
              ("/api/v1/x", "/healthz", "/poster/1.webp", "/robots.txt",
               "/search?q=1", "/event/1", "/community/2", "/__debug")]
    плохо = па.служебные_адреса(адреса)
    assert len(плохо) == len(адреса), плохо


def test_повторы_в_перечне_замечаний_не_множатся():
    """Адрес, подошедший под два правила, называется один раз."""
    плохо = па.служебные_адреса(["https://проба.test/api/карта.xml"])
    assert плохо == ["https://проба.test/api/карта.xml"], плохо


# -------------------------------------------------------------- карта картинок
def _часть(с_картинками: bool, адреса: list[str]) -> ET.Element:
    атрибуты = {} if not с_картинками else {f"{{{IMG}}}dummy": "x"}
    корень = ET.Element(f"{{{SM}}}urlset", атрибуты)
    for адрес in адреса:
        у = ET.SubElement(корень, f"{{{SM}}}url")
        ET.SubElement(у, f"{{{SM}}}loc").text = адрес
        if с_картинками:
            к = ET.SubElement(у, f"{{{IMG}}}image")
            ET.SubElement(к, f"{{{IMG}}}loc").text = f"{адрес}.webp"
    return корень


def test_карта_картинок_узнаётся_по_элементу():
    """Узнаётся по объявлению и элементу, а не по имени файла.

    Имя файла — договорённость, объявление — факт.
    """
    часть = _часть(True, ["https://проба.test/anime/один"])
    assert па.это_карта_картинок(часть) is True


def test_обычная_часть_картой_картинок_не_считается():
    часть = _часть(False, ["https://проба.test/anime/один"])
    assert па.это_карта_картинок(часть) is False


def test_карта_картинок_узнаётся_и_без_атрибута_на_корне():
    """Разбор ElementTree может не сохранить объявление в attrib.

    Тогда остаётся сам элемент `image:image`, и он решает. Без этой ветви
    приёмка снова считала бы 7985 дублей.
    """
    корень = ET.Element(f"{{{SM}}}urlset")
    у = ET.SubElement(корень, f"{{{SM}}}url")
    ET.SubElement(у, f"{{{SM}}}loc").text = "https://проба.test/anime/один"
    к = ET.SubElement(у, f"{{{IMG}}}image")
    ET.SubElement(к, f"{{{IMG}}}loc").text = "https://cdn/1.webp"
    assert па.это_карта_картинок(корень) is True


def test_разбор_настоящей_карты_картинок():
    """Та же форма, что отдаёт живая витрина, но из строки."""
    xml = f'''<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="{SM}" xmlns:image="{IMG}">
  <url>
    <loc>https://yummyani.site/anime/один</loc>
    <image:image><image:loc>https://poster/1.webp</image:loc></image:image>
  </url>
</urlset>'''
    assert па.это_карта_картинок(ET.fromstring(xml)) is True
