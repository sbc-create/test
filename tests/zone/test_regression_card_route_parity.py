"""Падающий регрессионный тест: карточка ведёт туда, чего в релизе нет.

Цепочка проверяется целиком: сущность каталога → сгенерированный href
карточки → канонический перечень маршрутов → разрешение маршрута рантаймом.
Проверять звенья по отдельности бессмысленно: каждое из них по-своему
исправно, а рассогласование живёт на стыке.
"""
from __future__ import annotations

import re

import pytest

from factory.lords import fixtures as fx
from factory.lords import preview as preview_mod
from factory.lords import render as render_mod

#: Адрес карточки в разметке. Символы кавычек, плюса и скобок исключены
#: намеренно: в виджете поиска есть JS-шаблон `"/title/" + encodeURIComponent(...)`,
#: и он не является ссылкой страницы. Считать его карточкой значило бы
#: объявить дефектом собственный скрипт.
ССЫЛКА = re.compile(r'href="(/title/[a-z0-9\-/]*)"')
ПАКЕТ = "zona-cinema-preview"


def нормализовать(цель: str) -> str:
    ц = (цель or "/").split("#")[0].split("?")[0].lower()
    while "//" in ц:
        ц = ц.replace("//", "/")
    if ц != "/" and "." not in ц.rsplit("/", 1)[-1] and not ц.endswith("/"):
        ц += "/"
    return ц


def собрать(only_title_slugs, *, ограничить_карточки: bool = False):
    package, _ = preview_mod._package(ПАКЕТ)
    catalog = fx.build_catalog()
    сайт = render_mod.render_site(package, catalog=catalog, environ={},
                                  publisher_id="1",
                                  only_title_slugs=only_title_slugs,
                                  restrict_cards_to_rendered=ограничить_карточки)
    цели, маршруты = set(), set()
    for адрес, страница in сайт.pages.items():
        путь = нормализовать(адрес)
        if путь.startswith("/title/"):
            маршруты.add(путь)
        текст = страница.body
        if isinstance(текст, bytes):
            текст = текст.decode("utf-8", "replace")
        for сырой in ССЫЛКА.findall(текст):
            цели.add(нормализовать(сырой))
    return {"catalog": catalog, "цели": цели, "маршруты": маршруты}


class TestПаритетКарточекИМаршрутов:
    def test_полная_сборка_согласована(self):
        """Контроль: при полной отрисовке рассогласования нет."""
        итог = собрать(None)
        осиротевшие = итог["цели"] - итог["маршруты"]
        assert осиротевшие == set(), (
            f"карточки ведут на {len(осиротевшие)} несуществующих маршрутов")

    def test_частичная_сборка_не_оставляет_осиротевших_карточек(self):
        """Так и собирались Zona и Animedia: список по всему каталогу,
        страницы — по выборке. Карточка обязана вести на существующий маршрут
        независимо от того, сколько страниц решено отрисовать."""
        каталог = fx.build_catalog()
        выборка = frozenset(sorted(t.slug for t in каталог.titles)[:5])
        итог = собрать(выборка, ограничить_карточки=True)
        осиротевшие = итог["цели"] - итог["маршруты"]
        assert осиротевшие == set(), (
            f"частичная сборка оставила {len(осиротевшие)} карточек без "
            f"маршрута; пример: {sorted(осиротевшие)[:3]}")

    def test_каждый_маршрут_имеет_ровно_один_адрес(self):
        итог = собрать(None)
        assert len(итог["маршруты"]) == len(set(итог["маршруты"]))
