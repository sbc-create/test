"""Сборщик патча `lastmod` частей карты: отказы и неподменяемая репетиция.

Повод — MOD-111: у 12 домéнов сети `lastmod` частей в `/sitemap.xml` нет вовсе,
и обходчику нечем решать, перезапрашивать ли часть на 45 000 адресов.

Отрицательные контроли, названные заранее:

* **неоднозначный якорь — отказ**, а не правка «по похожему месту»;
* **уже исправленный файл — отказ**, иначе патч наложился бы вторым слоем;
* **не обслуживаемое витриной дерево — отказ** с указанием работающего пути
  (ошибку с `/app/` поймала линия zona-01 на другом патче 20.10);
* **репетиция обязана различать «максимум внутри части» и «максимум по всему
  набору»**. Первая её версия этого не умела: набор умещался в одну часть, где
  оба максимума совпадают. Поэтому предел на часть в репетиции понижен, и ниже
  проверяется, что он остался понижен.
"""
from __future__ import annotations

import importlib.util
import pathlib

import pytest

КОРЕНЬ = pathlib.Path(__file__).resolve().parents[2]
_с = importlib.util.spec_from_file_location(
    "prepare_sitemap_lastmod_patch",
    КОРЕНЬ / "automation/local/prepare-sitemap-lastmod-patch.py")
ИНСТР = importlib.util.module_from_spec(_с)
_с.loader.exec_module(ИНСТР)

ОБРАЗЕЦ = '''"""Проба."""
import xml.etree.ElementTree as ET

SM_NS = "http://www.sitemaps.org/schemas/sitemap/0.9"
ПРЕДЕЛ_URL = 50000


def _урл(родитель, адрес, lastmod=""):
    у = ET.SubElement(родитель, "url")
    ET.SubElement(у, "loc").text = адрес
    if lastmod:
        ET.SubElement(у, "lastmod").text = lastmod


def построить_sitemap(хост, страницы, разделы=()):
    адреса = []
    видели = set()
    for р in разделы:
        а = f"https://{хост}{р}"
        if а not in видели:
            видели.add(а)
            адреса.append((а, ""))
    for с in страницы:
        путь = с.get("url") or (f"/title/{с['slug']}/" if с.get("slug") else "")
        if not путь:
            continue
        а = f"https://{хост}{путь}"
        if а in видели:
            continue
        видели.add(а)
        адреса.append((а, str(с.get("lastmod") or "")))

    файлы: list[tuple[str, bytes]] = []
    части = [адреса[i:i + ПРЕДЕЛ_URL] for i in range(0, len(адреса), ПРЕДЕЛ_URL)] or [[]]
    for н, часть in enumerate(части, start=1):
        корень = ET.Element("urlset", xmlns=SM_NS)
        for а, lm in часть:
            _урл(корень, а, lm)
        файлы.append((f"sitemap-{н}.xml",
                      ET.tostring(корень, encoding="utf-8", xml_declaration=True)))
    индекс = ET.Element("sitemapindex", xmlns=SM_NS)
    for имя, _ in файлы:
        s = ET.SubElement(индекс, "sitemap")
        ET.SubElement(s, "loc").text = f"https://{хост}/{имя}"
    файлы.append(("sitemap.xml",
                  ET.tostring(индекс, encoding="utf-8", xml_declaration=True)))
    return файлы
'''


def test_правка_вписывается():
    стало = ИНСТР.переписать(ОБРАЗЕЦ)
    assert "даты_частей" in стало
    assert "max((lm for _, lm in часть if lm), default=\"\")" in стало
    assert "zip(файлы, даты_частей)" in стало


def test_неоднозначный_якорь_это_отказ():
    with pytest.raises(SystemExit) as ош:
        ИНСТР.переписать(ОБРАЗЕЦ + "\n\n" + ОБРАЗЕЦ)
    assert "вместо одного" in str(ош.value)


def test_отсутствие_якоря_это_отказ():
    with pytest.raises(SystemExit):
        ИНСТР.переписать('"""Пустой."""\n')


def test_уже_исправленный_файл_это_отказ():
    with pytest.raises(SystemExit) as ош:
        ИНСТР.переписать(ИНСТР.переписать(ОБРАЗЕЦ))
    assert "УЖЕ есть" in str(ош.value)


def test_необслуживаемое_дерево_отвергается(capsys, tmp_path):
    ловушка = tmp_path / "srv" / "animedia-space" / "app" / "src"
    ловушка.mkdir(parents=True)
    файл = ловушка / "seo_layer.py"
    файл.write_text(ОБРАЗЕЦ, encoding="utf-8")
    assert ИНСТР.главное(["--source", str(файл)]) == 2
    assert "не обслуживаемое витриной дерево" in capsys.readouterr().out


# --- репетиция ------------------------------------------------------------------

def test_репетиция_различает_максимум_части(tmp_path):
    было = tmp_path / "до.py"
    стало = tmp_path / "после.py"
    было.write_text(ОБРАЗЕЦ, encoding="utf-8")
    стало.write_text(ИНСТР.переписать(ОБРАЗЕЦ), encoding="utf-8")
    строки = ИНСТР.репетиция(было, стало)
    слитно = "\n".join(строки)
    assert "ПРОВАЛ" not in слитно, слитно
    assert "sitemap-1.xml ждали 2025-06-10" in слитно
    assert "sitemap-3.xml ждали без lastmod" in слитно


def test_репетиция_ловит_общий_максимум(tmp_path):
    """Подмена «максимум по всему набору» обязана ронять репетицию."""
    было = tmp_path / "до.py"
    стало = tmp_path / "после.py"
    было.write_text(ОБРАЗЕЦ, encoding="utf-8")
    плохо = ИНСТР.переписать(ОБРАЗЕЦ).replace(
        'max((lm for _, lm in часть if lm), default="")',
        'max((lm for _, lm in адреса if lm), default="")')
    стало.write_text(плохо, encoding="utf-8")
    слитно = "\n".join(ИНСТР.репетиция(было, стало))
    assert "ПРОВАЛ" in слитно
    assert "всем частям поставлена одна дата" in слитно


def test_репетиция_ловит_дату_сборки(tmp_path):
    """Подстановка «сегодня» обязана ронять репетицию отдельной проверкой."""
    было = tmp_path / "до.py"
    стало = tmp_path / "после.py"
    было.write_text(ОБРАЗЕЦ, encoding="utf-8")
    плохо = ИНСТР.переписать(ОБРАЗЕЦ).replace(
        'max((lm for _, lm in часть if lm), default="")',
        '__import__("datetime").date.today().isoformat()')
    стало.write_text(плохо, encoding="utf-8")
    слитно = "\n".join(ИНСТР.репетиция(было, стало))
    assert "в индексе стоит дата сборки" in слитно


def test_репетиция_ловит_изменение_частей(tmp_path):
    """Если правка тронет сами части, это обязано быть видно."""
    было = tmp_path / "до.py"
    стало = tmp_path / "после.py"
    было.write_text(ОБРАЗЕЦ, encoding="utf-8")
    плохо = ИНСТР.переписать(ОБРАЗЕЦ).replace(
        '        for а, lm in часть:\n            _урл(корень, а, lm)',
        '        for а, lm in часть:\n            _урл(корень, а + "?x", lm)')
    стало.write_text(плохо, encoding="utf-8")
    слитно = "\n".join(ИНСТР.репетиция(было, стало))
    assert "ПРОВАЛ: содержимое частей изменилось" in слитно


def test_предел_репетиции_понижен_и_обоснован():
    assert ИНСТР.ПРЕДЕЛ_ДЛЯ_РЕПЕТИЦИИ == 10
    текст = " ".join(
        pathlib.Path(ИНСТР.__file__).read_text(encoding="utf-8").split())
    assert "ничего не проверив" in текст, "основание понижения должно быть названо"
