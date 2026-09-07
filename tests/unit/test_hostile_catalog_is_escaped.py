"""Данные поставщика не становятся разметкой.

Каталог приходит извне: названия, описания, жанры, студии, озвучки — всё это
чужой текст, и ни одно значение в нём не обязано быть безопасным. Экранирование
в рендерере есть, но применяется вручную, в каждом месте отдельно; забыть его в
одной вставке из ста — вопрос одной строки, а следствие — сохранённый XSS сразу
на всех витринах.

Поэтому проверка не читает код, а собирает витрину на каталоге, каждое поле
которого враждебно, и ищет в готовых страницах то, чего там быть не может:
исполняемый тег, обработчик события, вышедшую наружу кавычку атрибута.

Значения подобраны так, чтобы отличать экранирование от вырезания: `<` обязан
превратиться в `&lt;`, а не исчезнуть. Исчезнувший символ — тоже потеря данных,
просто менее заметная.
"""

from __future__ import annotations

import dataclasses
import re
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from factory.lords import fixtures as fx  # noqa: E402
from factory.lords import render as render_mod  # noqa: E402
from factory.paths import PATHS  # noqa: E402

ВРАЖДЕБНОЕ = '<script>alert(1)</script>"\'><img src=x onerror=alert(2)>'

#: Поля, которые попадают на страницу как текст. Структурные — `slug`,
#: `content_type`, `country_slug`, `genre_slugs`, `created_at` — не портятся
#: намеренно: они управляют разделами и адресами, и витрина на испорченных
#: значениях просто не соберётся. Первая редакция портила и их: страниц вышло
#: почти ноль, и три проверки упали, не сказав об экранировании ничего.
ОТОБРАЖАЕМЫЕ = ("name", "original_name", "country", "studio", "age_rating",
                "summary", "genres")

#: Обработчики, которые рендерер ставит сам и осознанно. Список закрытый:
#: проверка ищет не наличие обработчиков вообще, а появление чужого. Пустой
#: список был бы неверен — `onerror="this.remove()"` снимает не загрузившийся
#: постер и оставляет заглушку, и это нужное поведение, а не упущение.
СВОИ_ОБРАБОТЧИКИ = {"this.remove()"}


@pytest.fixture(scope="module")
def страницы() -> str:
    """Все страницы витрины, собранной на враждебном каталоге, одной строкой."""
    каталог = fx.build_catalog()
    испорченные = []
    for title in каталог.titles:
        замены = {}
        for поле in ОТОБРАЖАЕМЫЕ:
            значение = getattr(title, поле, None)
            if isinstance(значение, str) and значение:
                замены[поле] = f"{значение} {ВРАЖДЕБНОЕ}"
            elif isinstance(значение, tuple) and значение and all(
                    isinstance(v, str) for v in значение):
                замены[поле] = tuple(f"{v} {ВРАЖДЕБНОЕ}" for v in значение)
        испорченные.append(dataclasses.replace(title, **замены))

    испорченный = dataclasses.replace(каталог, titles=tuple(испорченные))
    пакет = yaml.safe_load(PATHS.site_package("lords-02").read_text(encoding="utf-8"))
    site = render_mod.render_site(пакет, catalog=испорченный, environ={}, publisher_id="1")
    return "\n".join(page.body for page in site.pages.values()
                     if page.content_type.startswith("text/html"))


class TestИсполняемогоНеПоявилось:
    def test_нет_тега_script_из_данных(self, страницы):
        assert "<script>alert(1)</script>" not in страницы, (
            "значение поставщика стало исполняемым тегом: сохранённый XSS")

    def test_нет_тега_img_с_обработчиком(self, страницы):
        assert "<img src=x onerror=" not in страницы

    def test_нет_обработчика_события_из_данных(self, страницы):
        """Имя атрибута, а не буквы в тексте.

        Подстрока `onerror=alert` встречается внутри экранированного
        `alt="… &lt;img src=x onerror=alert(1)&gt;"`, где она безвредна.
        Проверка на подстроке падала бы на верно экранированной странице.
        """
        from html.parser import HTMLParser

        class Сборщик(HTMLParser):
            def __init__(self):
                super().__init__(convert_charrefs=True)
                self.найдены: list[str] = []

            def handle_starttag(self, tag, attrs):
                for имя, значение in attrs:
                    if имя and имя.lower().startswith("on"):
                        self.найдены.append((tag, имя, значение))

        сборщик = Сборщик()
        сборщик.feed(страницы)
        чужие = [н for н in сборщик.найдены if н[2] not in СВОИ_ОБРАБОТЧИКИ]
        assert чужие == [], f"обработчик события не из наших: {чужие[:3]}"


class TestЭкранированиеАНеВырезание:
    def test_угловая_скобка_превращена_в_мнемонику(self, страницы):
        assert "&lt;script&gt;" in страницы, (
            "враждебное значение не найдено даже в экранированном виде: "
            "либо его вырезали — это потеря данных, — либо страницы собраны "
            "не из того каталога, и проверка ничего не проверяет")

    def test_кавычка_не_выходит_из_атрибута(self, страницы):
        """`"` внутри значения атрибута обязан быть мнемоникой."""
        for атрибут in re.findall(r'(?:title|aria-label|alt|content)="([^"]*)"', страницы):
            assert "<script" not in атрибут


class TestПроверкаНеПуста:
    def test_страницы_собраны(self, страницы):
        assert len(страницы) > 50_000, "витрина не собралась, проверять нечего"

    def test_враждебное_значение_дошло_до_страниц(self, страницы):
        """Иначе всё выше проходит на пустом месте."""
        assert "alert(1)" in страницы, (
            "враждебного значения нет в страницах ни в каком виде — "
            "каталог до рендерера не дошёл")
