"""Цепочка карт сайта: проверка обязана уметь провалиться и не кричать зря.

Сеть здесь не нужна и запрещена правилами: `запрос` подменяется, и каждый тест
задаёт состояние мира ответами подставной функции. Проверяется поведение —
какой вывод и какой код выхода допустим при каком ответе сервера.

Три различения стоят отдельных тестов, потому что каждое уже привело к ошибке
в живом замере:

* индекс карт и обычная карта — разные вещи: у индекса `<loc>` указывает на
  другие КАРТЫ, и проверять код только у `/sitemap.xml` значит не проверить
  ничего;
* домен без DNS — состояние записи реестра, а не поломка карты;
* успех у границы таймаута — находка, а не зелёный результат.
"""
from __future__ import annotations

import importlib.util
import io
import json
from contextlib import redirect_stdout
from pathlib import Path

import pytest

КОРЕНЬ = Path(__file__).resolve().parents[2]
ИСТОЧНИК = КОРЕНЬ / "automation" / "local" / "sitemap-chain.py"

ИНДЕКС = """<?xml version="1.0"?>
<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <sitemap><loc>https://x.example/sitemap/static.xml</loc></sitemap>
  <sitemap><loc>https://x.example/sitemap/titles.xml</loc></sitemap>
</sitemapindex>"""

КАРТА = """<?xml version="1.0"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url><loc>https://x.example/anime/a</loc></url>
  <url><loc>https://x.example/anime/b</loc></url>
</urlset>"""

ПУСТАЯ = """<?xml version="1.0"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"></urlset>"""

ROBOTS = "User-agent: *\nAllow: /\n\nSitemap: https://x.example/sitemap.xml\n"


def _модуль():
    спец = importlib.util.spec_from_file_location("sitemap_chain", ИСТОЧНИК)
    м = importlib.util.module_from_spec(спец)
    спец.loader.exec_module(м)
    return м


@pytest.fixture(scope="module")
def м():
    return _модуль()


def _подменить(м, monkeypatch, ответы: dict):
    """ответы: адрес → (код, секунды, тело). Неназванный адрес — отказ теста.

    Молчаливое значение по умолчанию здесь недопустимо: тест, где забыли
    описать запрос, обязан падать, а не проверять выдуманное состояние.
    """
    def поддельный(адрес, таймаут):
        assert адрес in ответы, f"тест не описал запрос {адрес}"
        return ответы[адрес]
    monkeypatch.setattr(м, "запрос", поддельный)


def test_исправная_цепочка_даёт_ноль(м, monkeypatch):
    _подменить(м, monkeypatch, {
        "https://x.example/robots.txt": ("200", 0.1, ROBOTS),
        "https://x.example/sitemap.xml": ("200", 0.1, ИНДЕКС),
        "https://x.example/sitemap/static.xml": ("200", 0.1, КАРТА),
        "https://x.example/sitemap/titles.xml": ("200", 1.2, КАРТА),
    })
    буфер = io.StringIO()
    with redirect_stdout(буфер):
        код = м.главное(["--domain", "x.example"])
    assert код == 0
    assert "замечаниями: 0 из 1" in буфер.getvalue()


def test_отказ_вложенной_карты_виден_и_валит_код(м, monkeypatch):
    """Индекс отдал 200, а титулы 504 — ровно то, что было на yummyani7."""
    _подменить(м, monkeypatch, {
        "https://x.example/robots.txt": ("200", 0.1, ROBOTS),
        "https://x.example/sitemap.xml": ("200", 0.1, ИНДЕКС),
        "https://x.example/sitemap/static.xml": ("200", 0.1, КАРТА),
        "https://x.example/sitemap/titles.xml": ("504", 30.0, ""),
    })
    буфер = io.StringIO()
    with redirect_stdout(буфер):
        код = м.главное(["--domain", "x.example"])
    assert код == 1
    вывод = буфер.getvalue()
    assert "titles.xml" in вывод and "504" in вывод


def test_успех_у_границы_таймаута_это_замечание(м, monkeypatch):
    """200 за 27 с — не зелёный результат: предел nginx 30 с рядом."""
    _подменить(м, monkeypatch, {
        "https://x.example/robots.txt": ("200", 0.1, ROBOTS),
        "https://x.example/sitemap.xml": ("200", 0.1, ИНДЕКС),
        "https://x.example/sitemap/static.xml": ("200", 0.1, КАРТА),
        "https://x.example/sitemap/titles.xml": ("200", 27.4, КАРТА),
    })
    буфер = io.StringIO()
    with redirect_stdout(буфер):
        код = м.главное(["--domain", "x.example"])
    assert код == 1
    assert "27 с" in буфер.getvalue()


def test_быстрый_ответ_замечанием_не_становится(м, monkeypatch):
    _подменить(м, monkeypatch, {
        "https://x.example/robots.txt": ("200", 0.1, ROBOTS),
        "https://x.example/sitemap.xml": ("200", 0.1, ИНДЕКС),
        "https://x.example/sitemap/static.xml": ("200", 0.1, КАРТА),
        "https://x.example/sitemap/titles.xml": ("200", 19.9, КАРТА),
    })
    буфер = io.StringIO()
    with redirect_stdout(буфер):
        assert м.главное(["--domain", "x.example"]) == 0


def test_домен_без_dns_не_считается_поломкой_карты(м, monkeypatch):
    """Четыре записи реестра без DNS не должны красить итог навсегда."""
    _подменить(м, monkeypatch, {
        "https://нет.example/robots.txt": ("dns", -1.0, ""),
    })
    буфер = io.StringIO()
    with redirect_stdout(буфер):
        код = м.главное(["--domain", "нет.example"])
    assert код == 0
    вывод = буфер.getvalue()
    assert "нет DNS" in вывод
    assert "без DNS (не опрошены): 1" in вывод


def test_пустая_карта_с_кодом_200_это_замечание(м, monkeypatch):
    """Карта, ответившая 200 без адресов, рабочей картой не является."""
    _подменить(м, monkeypatch, {
        "https://x.example/robots.txt": ("200", 0.1, ROBOTS),
        "https://x.example/sitemap.xml": ("200", 0.1, ИНДЕКС),
        "https://x.example/sitemap/static.xml": ("200", 0.1, ПУСТАЯ),
        "https://x.example/sitemap/titles.xml": ("200", 0.3, КАРТА),
    })
    буфер = io.StringIO()
    with redirect_stdout(буфер):
        код = м.главное(["--domain", "x.example"])
    assert код == 1
    assert "и пуста" in буфер.getvalue()


def test_обычная_карта_без_индекса_проверяется_сама(м, monkeypatch):
    _подменить(м, monkeypatch, {
        "https://x.example/robots.txt": ("200", 0.1, ROBOTS),
        "https://x.example/sitemap.xml": ("200", 0.4, КАРТА),
    })
    буфер = io.StringIO()
    with redirect_stdout(буфер):
        assert м.главное(["--domain", "x.example"]) == 0
    assert "2" in буфер.getvalue()


def test_пустая_карта_без_индекса_это_замечание(м, monkeypatch):
    _подменить(м, monkeypatch, {
        "https://x.example/robots.txt": ("200", 0.1, ROBOTS),
        "https://x.example/sitemap.xml": ("200", 0.4, ПУСТАЯ),
    })
    буфер = io.StringIO()
    with redirect_stdout(буфер):
        assert м.главное(["--domain", "x.example"]) == 1


def test_индекс_и_карта_не_путаются(м):
    """У индекса loc — это карты, у карты — страницы. Путаница скрыла бы отказ."""
    индекс, адреса = м.адреса_карты(ИНДЕКС)
    assert индекс is True and len(адреса) == 2
    карта, адреса2 = м.адреса_карты(КАРТА)
    assert карта is False and len(адреса2) == 2


def test_карты_из_robots_читаются(м):
    assert м.карты_из_robots(ROBOTS) == ["https://x.example/sitemap.xml"]
    assert м.карты_из_robots("User-agent: *\n") == []


def test_предел_числа_вложенных_назван_в_выводе(м, monkeypatch):
    """Опрошено меньше, чем перечислено, — об этом говорится прямо."""
    много = "".join(
        f"<sitemap><loc>https://x.example/s/{i}.xml</loc></sitemap>"
        for i in range(м.ПРЕДЕЛ_ВЛОЖЕННЫХ + 3))
    ответы = {
        "https://x.example/robots.txt": ("200", 0.1, ROBOTS),
        "https://x.example/sitemap.xml": (
            "200", 0.1, f"<sitemapindex>{много}</sitemapindex>"),
    }
    for i in range(м.ПРЕДЕЛ_ВЛОЖЕННЫХ + 3):
        ответы[f"https://x.example/s/{i}.xml"] = ("200", 0.1, КАРТА)
    _подменить(м, monkeypatch, ответы)
    буфер = io.StringIO()
    with redirect_stdout(буфер):
        код = м.главное(["--domain", "x.example"])
    assert код == 1
    assert f"опрошено {м.ПРЕДЕЛ_ВЛОЖЕННЫХ}" in буфер.getvalue()


def test_нечитаемый_реестр_это_отказ(м, tmp_path):
    assert м.главное(["--registry", str(tmp_path / "нет.json")]) == 2


def test_испытательные_имена_не_опрашиваются(м, tmp_path):
    """RFC 6761: такие имена публично не разрешаются, и молчание — их свойство."""
    реестр = tmp_path / "site-cells.json"
    реестр.write_text(json.dumps({"cells": [
        {"site_id": "a", "domain": "site-a.localhost"},
        {"site_id": "b", "domain": "pilot.localhost.test"},
        {"site_id": "c", "domain": "живой.example.com"},
    ]}), encoding="utf-8")
    assert м.домены(реестр) == ["живой.example.com"]


def test_json_вывод_разбирается(м, monkeypatch):
    _подменить(м, monkeypatch, {
        "https://x.example/robots.txt": ("200", 0.1, ROBOTS),
        "https://x.example/sitemap.xml": ("200", 0.1, ИНДЕКС),
        "https://x.example/sitemap/static.xml": ("200", 0.1, КАРТА),
        "https://x.example/sitemap/titles.xml": ("504", 30.0, ""),
    })
    буфер = io.StringIO()
    with redirect_stdout(буфер):
        м.главное(["--domain", "x.example", "--json"])
    данные = json.loads(буфер.getvalue())
    assert данные[0]["домен"] == "x.example"
    assert данные[0]["вложенные"][1]["код"] == "504"
