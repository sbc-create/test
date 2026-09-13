"""Lords и Zona — разные шаблоны, а не один с другим акцентом.

Проверяется не название в манифесте, а наблюдаемые свойства: раскладочные
токены, состав главной, объявленный состав страницы произведения и таблица
стилей. Различие только в цвете двумя шаблонами не делает: перекрашенная
копия — копия.

Что этот набор НЕ утверждает: что страница произведения выглядит по-разному у
любой записи. Объявленный состав у семейств разный, но при пустом вводном
тексте раздел «о произведении» не рисуется, и порядок становится
ненаблюдаемым. Это записано явно, чтобы никто не принял объявление за
наблюдение.
"""
from __future__ import annotations

import pathlib
import re

import pytest
import yaml

from factory.lords import theme as theme_mod

КОРЕНЬ = pathlib.Path(__file__).resolve().parents[2]
ПРОФИЛИ = КОРЕНЬ / "blueprints" / "lords" / "profiles"

#: Токены, различие которых само по себе НЕ делает шаблоны разными.
ТОЛЬКО_ЦВЕТ = {"bg", "surface", "surface_alt", "text", "muted", "accent",
               "accent_text", "border"}


def профиль(имя: str) -> dict:
    return yaml.safe_load((ПРОФИЛИ / f"{имя}.yaml").read_text(encoding="utf-8"))


def токены(имя: str) -> dict:
    return ((профиль(имя).get("theme") or {}).get("tokens") or {})


class TestРаскладкаРазная:
    def test_различия_не_только_в_цвете(self):
        л, z = токены("lords-general"), токены("zona-cinema")
        ключи = set(л) | set(z)
        раскладочные = {к for к in ключи if к not in ТОЛЬКО_ЦВЕТ}
        различия = {к for к in раскладочные if л.get(к) != z.get(к)}
        assert различия, (
            "Lords и Zona отличаются только цветом — это один шаблон в двух "
            "красках, а не два шаблона")

    def test_ширина_контейнера_разная(self):
        assert токены("lords-general").get("container") != токены("zona-cinema").get("container")

    def test_шкала_заголовков_разная(self):
        assert токены("lords-general").get("h1_size") != токены("zona-cinema").get("h1_size")

    def test_таблицы_стилей_не_совпадают(self):
        л = theme_mod.stylesheet(профиль("lords-general"))
        z = theme_mod.stylesheet(профиль("zona-cinema"))
        assert л != z
        # И не совпадают после вычёркивания цветов: иначе различие косметическое.
        убрать = lambda с: re.sub(r"#[0-9a-fA-F]{3,8}", "#цвет", с)
        assert убрать(л) != убрать(z), (
            "после вычёркивания цветов таблицы стилей совпали: различие "
            "косметическое")


class TestСоставСтраницыОбъявленСемейством:
    """Страница произведения не наследуется молча от другого семейства."""

    def test_оба_семейства_объявляют_состав(self):
        for имя in ("lords-general", "zona-cinema"):
            блок = профиль(имя).get("title_page")
            assert блок, f"{имя}: блок страницы произведения не объявлен"
            assert блок.get("sections"), f"{имя}: состав разделов не объявлен"

    def test_состав_различается(self):
        л = профиль("lords-general")["title_page"]["sections"]
        z = профиль("zona-cinema")["title_page"]["sections"]
        assert л != z, ("состав страницы произведения совпадает: композиция "
                        "у семейств одна и та же")

    def test_состав_из_допустимых_разделов(self):
        допустимо = {"player", "seasons", "about", "related", "comments"}
        for имя in ("lords-general", "zona-cinema"):
            состав = профиль(имя)["title_page"]["sections"]
            assert set(состав) <= допустимо, состав
            assert len(состав) == len(set(состав)), "раздел объявлен дважды"

    def test_плеер_первым_у_обоих(self):
        """Общее требование продукта, а не признак копии."""
        for имя in ("lords-general", "zona-cinema"):
            assert профиль(имя)["title_page"]["sections"][0] == "player"


class TestГлавнаяРазная:
    def test_состав_главной_различается(self):
        л = профиль("lords-general").get("sections") or {}
        z = профиль("zona-cinema").get("sections") or {}
        assert л != z, "состав главной совпадает у обоих семейств"


class TestЧегоНеУтверждаем:
    """Явно зафиксированные границы этой проверки."""

    def test_состав_объявлен_но_может_быть_ненаблюдаем(self):
        """При пустом вводном тексте раздел «о произведении» не рисуется.

        Тогда объявленный порядок `player, about, seasons` и
        `player, seasons, about` дают одинаковую страницу. Объявление есть,
        наблюдение — нет, и выдавать одно за другое нельзя.
        """
        z = профиль("zona-cinema")["title_page"]
        assert z.get("intro") == "", (
            "у Zona появился вводный текст: различие состава стало "
            "наблюдаемым, и проверку нужно расширить наблюдением, а не "
            "оставлять как есть")
