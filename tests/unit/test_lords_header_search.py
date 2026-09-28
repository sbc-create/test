"""REQ-LORDS-VISUAL: на витрине видна ровно одна форма поиска.

Измерено 2026-09-02 на живом lordfilm47.space: две формы поиска на 390, 768 и
1440, обе `action=/search/` с классом `header-search`. Соседние витрины того же
семейства показывали одну — разница шла от профиля: `lords-general` держит
`hero_search` в `home_blocks`, а форма в шапке рисовалась безусловно.

Проверяется главная (там сходятся обе формы) и внутренняя страница (там форма в
шапке обязана остаться — иначе поиск исчез бы со всех страниц, кроме первой).
"""

from __future__ import annotations

import re

from factory.lords import render as render_mod


def _forms(html: str) -> int:
    return len(re.findall(r'<form class="header-search"', html))


def _ctx(**over) -> dict:
    ctx = {
        "brand": "Витрина",
        "mark": "В",
        "nav": [],
        "_path": "/",
        "home_blocks": ["hero_search"],
    }
    ctx.update(over)
    return ctx


class TestОднаФормаПоиска:
    def test_на_главной_с_поиском_в_первом_экране_шапка_форму_не_дублирует(self):
        assert _forms(render_mod._header_search(_ctx())) == 0

    def test_на_внутренней_странице_форма_в_шапке_остаётся(self):
        assert _forms(render_mod._header_search(_ctx(_path="/films/"))) == 1

    def test_без_поиска_в_первом_экране_шапка_показывает_форму_и_на_главной(self):
        assert _forms(render_mod._header_search(_ctx(home_blocks=["latest_grid"]))) == 1

    def test_отсутствие_описания_блоков_не_убирает_поиск(self):
        # Пустой или отсутствующий список блоков не должен молча оставлять
        # витрину вовсе без поиска: это отказ хуже дубля.
        assert _forms(render_mod._header_search({"_path": "/"})) == 1
        assert _forms(render_mod._header_search({"_path": "/", "home_blocks": None})) == 1
