"""Токены Lords совпадают с закреплённым референсом, и только Lords.

Проверяется не «красиво стало», а два свойства: витрины Lords объявляют
значения, снятые с референса, а витрины других семейств — не объявляют
ничего и потому не меняются.

Замеры референса: `docs/product/LORDS-REFERENCE-MEASUREMENTS.md`,
sha256 9bae6162996ef857f11e8bbef12f10381bc6796993c910afd6122710e974809d.
Живой доступ к референсу закрыт профилем разрешений, поэтому пиксельное
сравнение недоступно — сравнимы числа, и сравниваются именно они.
"""
from __future__ import annotations

import hashlib
import pathlib

import pytest
import yaml

from factory.lords import theme

КОРЕНЬ = pathlib.Path(__file__).resolve().parents[2]
ПРОФИЛИ = КОРЕНЬ / "blueprints" / "lords" / "profiles"
ЭТАЛОН = КОРЕНЬ / "docs" / "product" / "LORDS-REFERENCE-MEASUREMENTS.md"

LORDS = ("lords-general", "lords-new", "lords-curated", "lords-genre")
ЧУЖИЕ = ("zona-cinema", "animedia-portal")

#: Значения из закреплённого замера. Не «выбранные красивые», а измеренные.
ЭТАЛОННЫЕ_ТОКЕНЫ = {
    "container": "1100px",     # contentWidth на 1440 и 1920 у всех трёх референсов
    "gutter": "5px",           # gutter на 390 и 768
    "gutter_wide": "12px",     # gutter на 1024
    "header_min_height": "70px",   # header.height 70 у lordfilm, 71 у lordserials
    "header_position": "relative",  # header.position у всех трёх
    "header_search": "inline",
    "gutter_mode": "margin",
    "button_size": "1rem",      # button 16px
    "button_weight": "600",
    "button_line_height": "40px",
}


def профиль(имя: str) -> dict:
    return yaml.safe_load((ПРОФИЛИ / f"{имя}.yaml").read_text(encoding="utf-8"))


def токены(имя: str) -> dict:
    return ((профиль(имя).get("theme") or {}).get("tokens") or {})


class TestЭталонЗакреплён:
    def test_файл_замеров_на_месте_и_не_изменён(self):
        assert ЭТАЛОН.is_file(), "замеров референса нет — сравнивать не с чем"
        отпечаток = hashlib.sha256(ЭТАЛОН.read_bytes()).hexdigest()
        assert отпечаток == (
            "9bae6162996ef857f11e8bbef12f10381bc6796993c910afd6122710e974809d"), (
            "замеры референса изменились: сверять парность с другим эталоном "
            "нельзя, не пересняв её")

    def test_замеры_называют_источник_и_время(self):
        т = ЭТАЛОН.read_text(encoding="utf-8")
        assert "lordfilm-hit.org" in т and "lordserials.fan" in т
        assert "2026-08-27" in т


class TestLordsОбъявляетЭталонныеЗначения:
    @pytest.mark.parametrize("имя", LORDS)
    def test_все_токены_совпадают_с_замером(self, имя):
        т = токены(имя)
        расхождения = {к: (т.get(к), v) for к, v in ЭТАЛОННЫЕ_ТОКЕНЫ.items()
                       if str(т.get(к)) != v}
        assert расхождения == {}, f"{имя}: токен не равен замеру {расхождения}"


class TestЧужиеСемействаНеТронуты:
    #: Токены, введённые работой над Lords. `container` сюда не входит: он
    #: существовал и раньше, и свои значения у Zona и Animedia собственные.
    ВВЕДЁННЫЕ = tuple(к for к in ЭТАЛОННЫЕ_ТОКЕНЫ if к != "container")

    @pytest.mark.parametrize("имя", ЧУЖИЕ)
    def test_новых_токенов_не_объявлено(self, имя):
        т = токены(имя)
        объявлены = [к for к in self.ВВЕДЁННЫЕ if к in т]
        assert объявлены == [], (
            f"{имя} объявляет токены Lords {объявлены}: значит его вид зависит "
            f"от работы над Lords, а это и есть регрессия по соседству")

    @pytest.mark.parametrize("имя", ЧУЖИЕ)
    def test_собственный_контейнер_сохранён(self, имя):
        """У чужих витрин своя ширина контейнера, и она не наша."""
        assert токены(имя).get("container") not in (None, "1100px")

    @pytest.mark.parametrize("имя", ЧУЖИЕ)
    def test_умолчания_повторяют_прежнее_поведение(self, имя):
        """Умолчания подобраны так, чтобы вид витрины не менялся."""
        css = theme.stylesheet(профиль(имя))
        assert "--gutter: 16px;" in css
        assert "--header-min-h: 60px;" in css
        # Кнопка прежде объявляла `font: inherit`; значения-умолчания обязаны
        # наследоваться, иначе кегль кнопки вырос бы с 14px до 16px.
        assert "--btn-size: inherit;" in css
        assert "--btn-weight: inherit;" in css


class TestРаскладкаШапкиВключаетсяТокеном:
    def test_у_lords_шапка_в_одну_строку(self):
        css = theme.stylesheet(профиль("lords-general"))
        assert ".header-row { padding-top: 0" in css
        assert "flex-wrap: nowrap" in css
        assert ".site-nav { flex: 1 1 0;" in css

    def test_у_чужих_раскладка_прежняя(self):
        css = theme.stylesheet(профиль("zona-cinema"))
        assert "padding-top: 0; padding-bottom: 0; flex-wrap: nowrap" not in css

    def test_боковой_отступ_полями_только_у_lords(self):
        лорды = theme.stylesheet(профиль("lords-general"))
        чужой = theme.stylesheet(профиль("zona-cinema"))
        assert "width: calc(100% - 2 * var(--gutter))" in лорды
        assert "width: calc(100% - 2 * var(--gutter))" not in чужой
