"""Проверка согласованности индекса карты: решающая логика, без выхода в сеть.

Инструмент сравнивает `lastmod` индекса с содержимым части. Ошибка в этом
сравнении дороже отсутствия проверки: «согласовано» у расходящейся карты
означало бы, что никто не узнает, почему свежие адреса не попадают в поиск.
"""
import importlib.util
import pathlib

import pytest

КОРЕНЬ = pathlib.Path(__file__).resolve().parents[2]
_сп = importlib.util.spec_from_file_location(
    "sitemap_index_audit",
    КОРЕНЬ / "automation" / "local" / "sitemap-index-audit.py")
инс = importlib.util.module_from_spec(_сп)
_сп.loader.exec_module(инс)


def индекс(части: list[tuple[str, str | None]]) -> str:
    тело = "".join(
        f"<sitemap><loc>https://x.test/sitemap/{имя}.xml</loc>"
        + (f"<lastmod>{дата}</lastmod>" if дата else "")
        + "</sitemap>"
        for имя, дата in части)
    return f'<?xml version="1.0"?><sitemapindex>{тело}</sitemapindex>'


def часть(даты: list[str]) -> str:
    тело = "".join(f"<url><loc>https://x.test/a/{i}</loc>"
                   + (f"<lastmod>{д}</lastmod>" if д else "")
                   + "</url>" for i, д in enumerate(даты))
    return f'<?xml version="1.0"?><urlset>{тело}</urlset>'


@pytest.fixture()
def ответы(monkeypatch):
    таблица: dict[str, tuple[str, str]] = {}

    def достать(адрес, таймаут):
        return таблица.get(адрес, ("404", ""))

    monkeypatch.setattr(инс, "достать", достать)
    return таблица


def test_индекс_старше_содержимого_это_расхождение(ответы):
    """Тот самый дефект: обходчик не перезапросит карту."""
    ответы["https://x.test/sitemap.xml"] = (
        "200", индекс([("titles", "2026-08-21T00:00:00.000Z")]))
    ответы["https://x.test/sitemap/titles.xml"] = (
        "200", часть(["2026-10-12T07:43:13.000Z"]))
    итог = инс.проверить("x.test")
    assert итог["ok"] is False
    assert итог["parts"][0]["stale_index"] is True
    assert "не перезапрашивать" in итог["problems"][0]


def test_совпадение_дат_расхождением_не_считается(ответы):
    ответы["https://x.test/sitemap.xml"] = (
        "200", индекс([("seasons", "2026-08-21T00:00:00.000Z")]))
    ответы["https://x.test/sitemap/seasons.xml"] = (
        "200", часть(["2026-08-21T00:00:00.000Z"]))
    итог = инс.проверить("x.test")
    assert итог["ok"] is True, итог["problems"]


def test_карта_без_дат_внутри_не_винится(ответы):
    """Карта без дат имеет право нести дату сборки — это не ошибка."""
    ответы["https://x.test/sitemap.xml"] = (
        "200", индекс([("static", "2026-08-21T00:00:00.000Z")]))
    ответы["https://x.test/sitemap/static.xml"] = ("200", часть([None, None]))
    итог = инс.проверить("x.test")
    assert итог["ok"] is True, итог["problems"]


def test_отсутствие_lastmod_в_индексе_называется(ответы):
    ответы["https://x.test/sitemap.xml"] = ("200", индекс([("titles", None)]))
    ответы["https://x.test/sitemap/titles.xml"] = (
        "200", часть(["2026-10-12T07:43:13.000Z"]))
    итог = инс.проверить("x.test")
    assert итог["ok"] is False
    assert "нечем решать" in итог["problems"][0]


def test_недоступная_часть_это_расхождение(ответы):
    ответы["https://x.test/sitemap.xml"] = (
        "200", индекс([("titles", "2026-10-12T07:43:13.000Z")]))
    итог = инс.проверить("x.test")          # части нет → 404
    assert итог["ok"] is False
    assert "ответ 404" in итог["problems"][0]


def test_индекс_без_частей_не_молчит(ответы):
    ответы["https://x.test/sitemap.xml"] = ("200", индекс([]))
    итог = инс.проверить("x.test")
    assert итог["ok"] is not True
    assert "проверять нечего" in итог["problems"][0]


def test_недоступный_индекс_не_читается_как_успех(ответы):
    итог = инс.проверить("x.test")          # индекса нет → 404
    assert итог.get("ok") is not True
    assert "индекс ответил 404" in итог["problems"]


def test_перечень_витрин_совпадает_с_заданием():
    """Пять витрин Yummy названы в задании владельца поимённо."""
    assert set(инс.ВИТРИНЫ_YUMMY) == {
        "yummyani.site", "yummyani.org", "yummyani.biz",
        "yummyani7.site", "yummyani7.info"}
