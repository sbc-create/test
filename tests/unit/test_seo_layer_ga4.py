"""seo_layer: тег GA4 рядом с Метрикой — один config, один page_view, нет ID — нет тега."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
спец = importlib.util.spec_from_file_location("seo_layer_ga4", ROOT / "automation" / "host" / "seo_layer.py")
слой = importlib.util.module_from_spec(спец)
спец.loader.exec_module(слой)

ID = "G-TESTSTREAM1"  # синтетический, формат потока; реальных ID в тестах нет
СТРАНИЦА = b"<html><head><title>t</title></head><body><h1>t</h1></body></html>"


def _отдать(тело=СТРАНИЦА, **к) -> str:
    return слой.обогатить(тело, "text/html; charset=utf-8", хост="example.test", путь="/", counter="12345678",
                          **к).decode("utf-8")


def test_one_config_and_no_explicit_page_view():
    т = _отдать(ga4=ID)
    assert т.count("gtag('config'") == 1
    assert т.count(слой.МЕТКА_GA4) == 1
    # page_view шлёт сам config; явное событие задвоило бы просмотр.
    assert "page_view" not in т
    assert т.count(слой.МЕТКА_МЕТРИКИ) == 1


@pytest.mark.parametrize("плохой", ["", "   ", "UA-1234-1", "G-", "G-abc def", "12345678", "G-X'Y"])
def test_no_valid_id_no_tag(плохой):
    т = _отдать(ga4=плохой)
    assert "googletagmanager" not in т and "gtag(" not in т
    assert т.count(слой.МЕТКА_МЕТРИКИ) == 1  # Метрика не задета


def test_second_pass_does_not_duplicate():
    раз = _отдать(ga4=ID).encode("utf-8")
    два = _отдать(раз, ga4=ID)
    assert два.count("gtag('config'") == 1
    assert два.count(слой.МЕТКА_МЕТРИКИ) == 1


def test_id_from_environment(monkeypatch):
    monkeypatch.setenv(слой.ПЕРЕМЕННАЯ_GA4, ID)
    assert _отдать().count(f"gtag('config','{ID}')") == 1
    monkeypatch.delenv(слой.ПЕРЕМЕННАЯ_GA4)
    assert "gtag(" not in _отдать()


def test_explicit_empty_beats_environment(monkeypatch):
    monkeypatch.setenv(слой.ПЕРЕМЕННАЯ_GA4, ID)
    assert "gtag(" not in _отдать(ga4="")


def test_non_html_untouched():
    тело = b'{"a":"</head>"}'
    assert слой.обогатить(тело, "application/json", ga4=ID) == тело


спец_пробы = importlib.util.spec_from_file_location("ga4_audit", ROOT / "automation" / "local" / "ga4-tag-audit.py")
проба = importlib.util.module_from_spec(спец_пробы)
спец_пробы.loader.exec_module(проба)


def _снимок(тело: str) -> dict:
    return {"код": 200, **проба.разобрать(тело)}


def test_audit_discriminates_patched_and_unpatched():
    с_тегом, без_тега = _снимок(_отдать(ga4=ID)), _снимок(_отдать(ga4=""))
    assert проба.беды_пробы(с_тегом, ID) == []
    assert проба.беды_пробы(без_тега, None) == []
    assert проба.беды_пробы(без_тега, ID)          # ожидали тег — его нет
    assert проба.беды_пробы(с_тегом, None)         # тег без ID в site.json
    assert проба.беды_пробы(с_тегом, "G-OTHER0001")  # чужой ID


def test_audit_catches_duplicates():
    двойной = _отдать(ga4=ID).replace("</head>", "<script>gtag('config','" + ID + "');"
                                       "gtag('event','page_view');</script></head>")
    assert any("config" in б for б in проба.беды_пробы(_снимок(двойной), ID))
    assert any("page_view" in б for б in проба.беды_пробы(_снимок(двойной), ID))
    две_метрики = _отдать(ga4=ID).replace("</head>", слой.тег_метрики("12345678") + "</head>")
    assert any("Метрика" in б for б in проба.беды_пробы(_снимок(две_метрики), ID))


@pytest.mark.parametrize("плохой", ["G-abc", " ", "G-", "UA-1234-1"])
def test_audit_names_malformed_expected_id(плохой):
    # Слой с таким ID тега не ставит; проба это подтверждает И называет вход.
    без_тега = _снимок(_отдать(ga4=плохой))
    б = проба.беды_пробы(без_тега, плохой)
    assert б and all("BLOCKED_INPUT" in х for х in б)
    # а если тег всё же стоит — это отдельное нарушение
    assert any("без ID" in х for х in проба.беды_пробы(_снимок(_отдать(ga4=ID)), плохой))


def test_audit_catches_duplicate_marker_without_second_config():
    т = _отдать(ga4=ID).replace("</head>", f'<script {слой.МЕТКА_GA4}"{ID}"></script></head>')
    assert т.count("gtag('config'") == 1
    assert any("метка data-ga4-id: 2" in б for б in проба.беды_пробы(_снимок(т), ID))


def test_layer_and_audit_share_id_form():
    assert слой._ФОРМАТ_GA4.pattern == проба.ФОРМА_ID.pattern
