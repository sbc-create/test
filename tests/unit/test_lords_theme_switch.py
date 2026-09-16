"""REQ-LORDS-THEME: тема переключается и запоминается, когда есть что переключать.

На боевой витрине переключателя тем нет вовсе: в разметке нет ни `data-theme`,
ни `prefers-color-scheme`, ни элемента управления. Витрина отдаёт одну палитру
и не считается с системной настройкой посетителя.

Здесь проверяется механизм и его отказ. Отказ важнее: витрина, объявившая одну
палитру, переключателя не получает. Кнопка, которая ничего не меняет, хуже её
отсутствия — посетитель считает её сломанной, а не отсутствующей.
"""

from __future__ import annotations

import pytest

from factory.lords import theme

ТЁМНЫЙ = {"profile": "lords-new", "theme": {"tokens": {"bg": "#111111", "text": "#e6e6e6"}}}
С_ПАЛИТРОЙ = {
    "profile": "lords-new",
    "theme": {
        "tokens": {"bg": "#111111", "text": "#e6e6e6"},
        "tokens_alt": {"bg": "#ffffff", "surface": "#f4f4f4", "text": "#141414",
                       "muted": "#5a5a5a", "border": "#d8d8d8"},
        "alt_scheme": "light",
    },
}


def test_без_второй_палитры_переключателя_нет():
    assert theme.theme_switch_available(ТЁМНЫЙ) is False
    assert theme.alt_blocks(ТЁМНЫЙ) == ""
    css = theme.stylesheet(ТЁМНЫЙ)
    assert "prefers-color-scheme" not in css
    assert "data-theme" not in css


def test_палитра_без_объявленной_схемы_не_включается():
    # «Светлая» палитра, о которой не сказано, что она светлая, включилась бы
    # по системной тёмной — то есть ровно наоборот.
    профиль = {"theme": {"tokens_alt": {"bg": "#ffffff"}}}
    assert theme.alt_tokens_of(профиль) is None
    профиль_с_мусором = {"theme": {"tokens_alt": {"bg": "#fff"}, "alt_scheme": "яркая"}}
    assert theme.alt_tokens_of(профиль_с_мусором) is None


def test_системная_тема_работает_без_выбора():
    css = theme.stylesheet(С_ПАЛИТРОЙ)
    assert "@media (prefers-color-scheme: light)" in css
    # Явный выбор не отменяется системной настройкой.
    assert ':root:not([data-theme="dark"])' in css


def test_явный_выбор_работает_в_обе_стороны():
    css = theme.stylesheet(С_ПАЛИТРОЙ)
    assert ':root[data-theme="light"]' in css
    assert ':root[data-theme="dark"]' in css


def test_вторая_палитра_наследует_недостающие_токены():
    схема, токены = theme.alt_tokens_of(С_ПАЛИТРОЙ)
    assert схема == "light"
    assert токены["bg"] == "#ffffff"
    # Акцент во второй палитре не объявлен — берётся из основной, а не пустеет.
    assert токены["accent"]


def test_правила_второй_палитры_идут_после_основных():
    css = theme.stylesheet(С_ПАЛИТРОЙ)
    assert css.index(":root {") < css.index('[data-theme="light"]'), (
        "правила второй палитры выше основных — они будут перекрыты, "
        "и переключение перестанет действовать")


@pytest.mark.parametrize("токен", ["--bg", "--text", "--surface", "--border"])
def test_вторая_палитра_переопределяет_ключевые_токены(токен):
    блок = theme.alt_blocks(С_ПАЛИТРОЙ)
    assert блок.count(токен) >= 2, f"{токен} не переопределён в обеих ветках выбора"
