"""REQ-TEMPLATES-SCREEN: отвергнутый пакет виден рядом с годными.

Список только годных выглядит как полный. Тот, кто добавлял пакет, не узнает,
почему его там нет, и решит, что не сохранилось — а на деле запись отвергнута
с причиной.
"""

from __future__ import annotations

from factory.site_engine.admin import ui

ГОДНЫЙ = {
    "family": "family_a", "version": "2.0.0", "digest": "a" * 64,
    "rendererRevision": "b" * 40, "contract": "site-template/1.0.0",
    "capabilities": ["pagination", "player"],
    "contractTests": {"passed": True, "at": "2026-09-06T10:00:00Z", "suite": "unit"},
    "rollbackCompatibleWith": ["1.0.0"], "preview": "https://example.test/", "notes": "",
}


def _страница(реестр):
    return ui.templates(реестр, flash=None, session_label="кто-то", csrf="t")


def test_годный_пакет_показан_со_всем_нужным():
    html = _страница({"templates": [ГОДНЫЙ], "rejected": [], "registryError": ""})
    assert "family_a" in html and "2.0.0" in html
    assert "a" * 16 in html, "отпечатка не видно — сверять нечем"
    assert "pagination" in html
    assert "пройдены" in html and "2026-09-06" in html, "«проверено» без даты"
    assert "1.0.0" in html, "не видно, куда откатываться"


def test_отвергнутый_показан_с_причиной():
    html = _страница({"templates": [], "rejected": [
        {"family": "family_b", "version": "1.0.0", "reason": "нет поля digest"}],
        "registryError": ""})
    assert "family_b" in html
    assert "нет поля digest" in html, "причина отказа скрыта"


def test_непройденные_проверки_названы():
    плохой = {**ГОДНЫЙ, "contractTests": {"passed": False, "at": "2026-09-06T10:00:00Z",
                                          "suite": "unit"}}
    html = _страница({"templates": [плохой], "rejected": [], "registryError": ""})
    assert "не пройдены" in html


def test_пакет_без_проверок_не_выдаётся_за_проверенный():
    без = {**ГОДНЫЙ, "contractTests": {}}
    html = _страница({"templates": [без], "rejected": [], "registryError": ""})
    assert "не проверялся" in html


def test_отсутствие_отката_названо_словом():
    первый = {**ГОДНЫЙ, "rollbackCompatibleWith": []}
    html = _страница({"templates": [первый], "rejected": [], "registryError": ""})
    assert "некуда" in html, "пустая ячейка читалась бы как «откат есть»"


def test_ошибка_чтения_реестра_видна():
    html = _страница({"templates": [], "rejected": [], "registryError": "реестра нет"})
    assert "реестра нет" in html


def test_пустой_реестр_не_выглядит_ошибкой():
    html = _страница({"templates": [], "rejected": [], "registryError": ""})
    assert "Зарегистрированных пакетов нет" in html
