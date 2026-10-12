"""Норма приёмки крошек: где ложь, где упущение, а где правильная пустота.

Эта норма тонкая, и я ошибся в ней четыре раза подряд на живых витринах:
принял отсутствие разметки за дефект, не нашёл контейнер по семантической
метке, не увидел последнее звено, выведенное простым текстом, и отбросил все
карточки Yummy фильтром по числу символов «/». Каждая ошибка выглядела как
факт о витрине. Поэтому матрица исходов закреплена тестами целиком.

Сеть не нужна: ответы подставляются вместо `достать`.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

КОРЕНЬ = Path(__file__).resolve().parents[2]
ИСТОЧНИК = КОРЕНЬ / "automation" / "local" / "breadcrumb-acceptance.py"

КАТАЛОГ = '<a href="/title/kino/">Кино</a>'

ЦЕПОЧКА = """<script type="application/ld+json">
{"@context":"https://schema.org","@type":"BreadcrumbList","itemListElement":[
 {"@type":"ListItem","position":1,"name":"Сайт","item":"https://x/"},
 {"@type":"ListItem","position":2,"name":"Сериалы","item":"https://x/s/"},
 {"@type":"ListItem","position":3,"name":"Кино 2"}]}</script>"""


def _модуль():
    спец = importlib.util.spec_from_file_location("crumbs", ИСТОЧНИК)
    м = importlib.util.module_from_spec(спец)
    спец.loader.exec_module(м)
    return м


@pytest.fixture(scope="module")
def м():
    return _модуль()


def подставить(м, monkeypatch, страницы: dict[str, str]) -> None:
    """`достать` отвечает из словаря; адрес без записи — не ответил."""
    def достать(url):
        for ключ, тело in страницы.items():
            if url.endswith(ключ):
                return 200, тело, ""
        return None, "", "нет такой страницы на стенде"
    monkeypatch.setattr(м, "достать", достать)


def проверить(м, monkeypatch, страница_карточки: str, каталог: str = КАТАЛОГ):
    подставить(м, monkeypatch, {"/catalog/": каталог,
                                "/title/kino/": страница_карточки})
    return м.проверить("пример.invalid")


def test_разметка_совпадает_с_видимыми(м, monkeypatch):
    знак, подробно = проверить(м, monkeypatch, ЦЕПОЧКА + (
        '<nav class="breadcrumbs"><a>Сайт</a> › <a>Сериалы</a> › Кино 2</nav>'))
    assert знак == "ок ", подробно


def test_звено_которого_нет_на_странице_это_ложь(м, monkeypatch):
    """Тот самый дефект: цепочка построена из заголовка, а не из крошек."""
    знак, подробно = проверить(м, monkeypatch, ЦЕПОЧКА + (
        '<nav class="breadcrumbs"><a>Сайт</a> › <a>Сериалы</a></nav>'))
    assert знак == "НЕТ"
    assert "Кино 2" in подробно


def test_ни_разметки_ни_крошек_это_правильно(м, monkeypatch):
    """Правило «только из видимых крошек» требует именно этого исхода."""
    знак, подробно = проверить(м, monkeypatch, "<p>страница без крошек</p>")
    assert знак == "ок ", подробно
    assert "выдумывать нечего" in подробно


def test_крошки_без_разметки_это_замечание(м, monkeypatch):
    """Страница не обманывает — она просто не рассказывает. Это не расхождение."""
    знак, подробно = проверить(м, monkeypatch,
                               '<nav class="breadcrumbs"><a>Сайт</a> › Кино 2</nav>')
    assert знак == "зам"
    assert "лжи нет" in подробно


def test_контейнер_находится_по_семантической_метке(м, monkeypatch):
    """У Animedia класс `zcr` — ни «crumb», ни «крошк». Метка и спасает."""
    знак, подробно = проверить(м, monkeypatch, ЦЕПОЧКА + (
        '<nav class="zcr" aria-label="Хлебные крошки">'
        '<a>Сайт</a> › <a>Сериалы</a> › Кино 2</nav>'))
    assert знак == "ок ", подробно


def test_последнее_звено_простым_текстом_считается_видимым(м, monkeypatch):
    """У Lords и Zona текущая страница выводится текстом, а не ссылкой."""
    _звенья, весь = м.видимые_крошки(
        '<nav class="breadcrumbs"><a>Сайт</a> › <a>Сериалы</a> › Кино 2</nav>')
    assert "Кино 2" in весь


def test_порядок_звеньев_сверяется(м, monkeypatch):
    знак, подробно = проверить(м, monkeypatch, ЦЕПОЧКА + (
        '<nav class="breadcrumbs">Кино 2 › <a>Сериалы</a> › <a>Сайт</a></nav>'))
    assert знак == "НЕТ"
    assert "порядок" in подробно


def test_две_цепочки_на_странице_это_расхождение(м, monkeypatch):
    знак, подробно = проверить(м, monkeypatch, ЦЕПОЧКА + ЦЕПОЧКА + (
        '<nav class="breadcrumbs"><a>Сайт</a> › <a>Сериалы</a> › Кино 2</nav>'))
    assert знак == "НЕТ"
    assert "не один" in подробно


def test_страница_не_ответила_это_не_измерено(м, monkeypatch):
    подставить(м, monkeypatch, {"/catalog/": КАТАЛОГ})
    знак, подробно = м.проверить("пример.invalid")
    assert знак == "—  "
    assert "не ответила" in подробно


def test_карточку_не_нашли_это_не_измерено(м, monkeypatch):
    подставить(м, monkeypatch, {"/catalog/": "<p>пусто</p>"})
    знак, подробно = м.проверить("пример.invalid")
    assert знак == "—  "
    assert "карточку не нашли" in подробно


def test_ссылка_без_завершающего_слеша_годится(м, monkeypatch):
    """У Yummy ссылки идут как /anime/<слаг> — без слеша в конце."""
    подставить(м, monkeypatch, {
        "/catalog/": '<a href="/anime/tayna">Тайна</a>',
        "/anime/tayna": ЦЕПОЧКА + '<nav class="breadcrumbs">'
                        '<a>Сайт</a> › <a>Сериалы</a> › Кино 2</nav>'})
    знак, подробно = м.проверить("пример.invalid")
    assert знак == "ок ", подробно


def test_карточка_предпочтительнее_раздела(м, monkeypatch):
    """В разделе цепочка короче, и дефект «звено из заголовка» там не виден."""
    подставить(м, monkeypatch, {
        "/catalog/": '<a href="/catalog/ongoing">Онгоинги</a>'
                     '<a href="/anime/tayna">Тайна</a>'})
    адрес, _причина = м.карточка("пример.invalid")
    assert адрес.endswith("/anime/tayna"), адрес


def test_путь_печатается_целиком_а_не_слагом(м, monkeypatch):
    """По одному слагу я сам проверил не тот адрес и получил 404."""
    знак, подробно = проверить(м, monkeypatch, "<p>без крошек</p>")
    assert подробно.startswith("title/kino/"), подробно


def test_308_следуется(м):
    """Python 3.10 сам его не следует, а `/catalog/` у Yummy отвечает именно так."""
    assert hasattr(м._Перенаправления, "http_error_308")


def test_домены_только_из_реестра(м, tmp_path):
    """Адреса не придумываются: нет ячейки — нет и цели."""
    реестр = tmp_path / "р.json"
    реестр.write_text('{"cells": [{"site_id": "a", "domain": "a.invalid"}]}',
                      encoding="utf-8")
    assert м.домены(реестр, ["нет-такой"]) == []
    assert м.домены(реестр, []) == [("a", "a.invalid")]
