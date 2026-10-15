"""Прогрев карт сайта: решения инструмента, без выхода в сеть.

Проверки не выходят в сеть (правило `.claude/rules/tests.md`), поэтому
`достать` подменяется. Проверяется ровно то, из-за чего инструмент и появился:
отказ вложенной карты не должен прятаться за успешным индексом.
"""
import importlib.util
import pathlib

import pytest

КОРЕНЬ = pathlib.Path(__file__).resolve().parents[2]
_сп = importlib.util.spec_from_file_location(
    "warm_sitemaps", КОРЕНЬ / "automation" / "local" / "warm-sitemaps.py")
инс = importlib.util.module_from_spec(_сп)
_сп.loader.exec_module(инс)

ИНДЕКС = """<?xml version="1.0" encoding="UTF-8"?>
<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <sitemap><loc>https://x.test/sitemap/titles.xml</loc></sitemap>
  <sitemap><loc>https://x.test/sitemap/pages.xml</loc></sitemap>
</sitemapindex>
"""
ОДИНОЧНАЯ = """<?xml version="1.0"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url><loc>https://x.test/</loc></url>
</urlset>
"""


@pytest.fixture()
def ответы(monkeypatch):
    таблица: dict = {}

    def достать(адрес, таймаут):
        код, тело, сек = таблица.get(адрес, (404, "", 0.1))
        return код, тело, сек

    monkeypatch.setattr(инс, "достать", достать)
    return таблица


def test_вложенные_адреса_разбираются():
    assert инс.вложенные(ИНДЕКС) == ["https://x.test/sitemap/titles.xml",
                                     "https://x.test/sitemap/pages.xml"]


def test_одиночная_карта_вложенных_не_даёт():
    assert инс.вложенные(ОДИНОЧНАЯ) == []


def test_обрезанный_индекс_не_валит_разбор():
    """Падение разбора превратило бы «карта битая» в «причина неизвестна»."""
    обрезан = ИНДЕКС[:ИНДЕКС.index("pages")]
    assert инс.вложенные(обрезан) == ["https://x.test/sitemap/titles.xml"]


def test_504_вложенной_карты_не_прячется_за_индексом(ответы):
    """Ровно тот дефект, из-за которого инструмент и появился."""
    ответы["https://x.test/sitemap.xml"] = (200, ИНДЕКС, 0.1)
    ответы["https://x.test/sitemap/titles.xml"] = (504, "", 30.0)
    ответы["https://x.test/sitemap/pages.xml"] = (200, ОДИНОЧНАЯ, 0.2)
    итог = инс.прогреть("x.test", 5)
    assert итог["ok"] is False
    assert "504" in итог["reason"]
    assert итог["index"]["status"] == 200


def test_все_карты_прогреты(ответы):
    ответы["https://x.test/sitemap.xml"] = (200, ИНДЕКС, 0.1)
    ответы["https://x.test/sitemap/titles.xml"] = (200, ОДИНОЧНАЯ, 4.0)
    ответы["https://x.test/sitemap/pages.xml"] = (200, ОДИНОЧНАЯ, 0.2)
    итог = инс.прогреть("x.test", 5)
    assert итог["ok"] is True
    assert "reason" not in итог
    assert len(итог["maps"]) == 2
    # Тёплое время измеряется вторым запросом: иначе отчёт показывал бы время
    # робота, а не результат прогрева.
    assert all("seconds_warm" in м for м in итог["maps"])


def test_недоступный_индекс_это_отдельный_случай(ответы):
    ответы["https://x.test/sitemap.xml"] = (503, "", 0.1)
    итог = инс.прогреть("x.test", 5)
    assert итог["ok"] is False
    assert "прогревать нечего" in итог["reason"]
    assert итог["maps"] == []


def test_ошибка_сети_не_подменяется_кодом(ответы):
    ответы["https://x.test/sitemap.xml"] = ("URLError: timed out", "", 60.0)
    итог = инс.прогреть("x.test", 5)
    assert итог["ok"] is False
    assert "URLError" in str(итог["index"]["status"])


def test_одиночная_карта_считается_прогретой(ответы):
    ответы["https://x.test/sitemap.xml"] = (200, ОДИНОЧНАЯ, 0.3)
    итог = инс.прогреть("x.test", 5)
    assert итог["ok"] is True
    assert "прогрет сам он" in итог["reason"]


def test_служебные_имена_не_опрашиваются():
    """RFC 6761: их молчание — свойство имени, а не состояние витрины."""
    живые = инс.живые_домены()
    assert живые, "реестр не дал ни одного действующего домена"
    assert not [д for д in живые
                if any(д.endswith(с) for с in инс.СЛУЖЕБНЫЕ)]


def test_заголовок_только_ascii():
    """Кириллица в User-Agent валит запрос ещё до сети (latin-1)."""
    т = (КОРЕНЬ / "automation" / "local" / "warm-sitemaps.py").read_text(
        encoding="utf-8")
    строка = next(с for с in т.split("\n") if '"User-Agent"' in с)
    значение = строка.split(":", 1)[1]
    assert значение.isascii(), значение
