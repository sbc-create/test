"""Разметка Schema.org не может вырваться из своего блока.

`json.dumps` экранирует то, что мешает JSON: кавычки, обратную косую, перевод
строки. Символы `<` и `>` ему не мешают, и он их не трогает — правильно для
JSON и опасно внутри HTML.

Блок `<script type="application/ld+json">` заканчивается первой же
последовательностью `</script>` в его содержимом. Название произведения,
пришедшее от поставщика и содержащее `</script><img src=x onerror=…>`,
закрывает блок и продолжается как разметка страницы. Это сохранённый XSS на
каждой витрине, и вносится он данными, а не кодом.

Найдено сборкой витрины на каталоге, каждое отображаемое поле которого
враждебно: остальные вставки экранированы, а эта — нет, потому что шла мимо
`escape()` по совершенно верной причине — там нужен JSON, а не HTML.

Мера — юникодные экранирования `\\u003c`, `\\u003e`, `\\u0026`. JSON остаётся
валидным и разбирается как прежде, а последовательности `</script>` в тексте
не возникает.
"""

from __future__ import annotations

import json
import re
import sys
from html.parser import HTMLParser
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from factory.lords import render as render_mod  # noqa: E402

ЗЛОЕ = '</script><img src=x onerror=alert(1)><script>'


class _Сборщик(HTMLParser):
    """Имена атрибутов настоящих тегов — и только они.

    Выражением это не решается. `alt="… onerror=alert(1) …"` содержит те же
    буквы внутри **значения**, где они экранированы и безвредны; проверка на
    подстроке падала на верно экранированной странице, то есть уводила правку
    в никуда. Разборщик отличает имя атрибута от текста в значении, потому что
    именно это он и делает.
    """

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.обработчики: list[str] = []
        self.теги: list[str] = []

    def handle_starttag(self, tag, attrs):
        self.теги.append(tag)
        for имя, _ in attrs:
            if имя and имя.lower().startswith("on"):
                self.обработчики.append(f"<{tag} {имя}=…>")


def _обработчики(разметка: str) -> list[str]:
    сборщик = _Сборщик()
    сборщик.feed(разметка)
    return сборщик.обработчики


class TestВыходИзБлокаНевозможен:
    def test_закрывающий_тег_не_появляется(self):
        разметка = render_mod._json_ld_script({"name": ЗЛОЕ})
        внутри = разметка[разметка.index(">") + 1:разметка.rindex("</script>")]
        assert "</script" not in внутри.lower(), (
            "содержимое закрывает собственный блок: данные становятся разметкой")

    def test_угловые_скобки_экранированы(self):
        разметка = render_mod._json_ld_script({"name": ЗЛОЕ})
        assert "\\u003c" in разметка and "\\u003e" in разметка

    def test_амперсанд_экранирован(self):
        """`&` в HTML начинает мнемонику; в JSON он безобиден, вместе — нет."""
        assert "\\u0026" in render_mod._json_ld_script({"name": "а & б"})

    def test_блоков_ровно_один(self):
        разметка = render_mod._json_ld_script({"name": ЗЛОЕ})
        assert разметка.count("<script") == 1
        assert разметка.count("</script>") == 1


class TestДанныеНеИспорчены:
    def test_json_остаётся_разбираемым(self):
        разметка = render_mod._json_ld_script({"name": ЗЛОЕ, "n": 1})
        тело = разметка[разметка.index(">") + 1:разметка.rindex("</script>")]
        assert json.loads(тело) == {"name": ЗЛОЕ, "n": 1}, (
            "экранирование изменило данные: потребитель разметки получит не то, "
            "что мы описали")

    def test_кириллица_не_превращается_в_коды(self):
        """`ensure_ascii=False` сохранён: коды раздували бы страницу впустую."""
        разметка = render_mod._json_ld_script({"name": "Бумажный циферблат"})
        assert "Бумажный циферблат" in разметка

    def test_разделители_без_пробелов(self):
        assert '","' in render_mod._json_ld_script({"a": "1", "b": "2"})


class TestСтраницаПроизведения:
    @pytest.fixture(scope="class")
    def страница(self):
        import dataclasses

        import yaml

        from factory.lords import fixtures as fx
        from factory.paths import PATHS

        каталог = fx.build_catalog()
        первый = dataclasses.replace(каталог.titles[0],
                                     name=f"{каталог.titles[0].name} {ЗЛОЕ}")
        испорченный = dataclasses.replace(каталог, titles=(первый,) + каталог.titles[1:])
        пакет = yaml.safe_load(PATHS.site_package("lords-02").read_text(encoding="utf-8"))
        site = render_mod.render_site(пакет, catalog=испорченный, environ={},
                                      publisher_id="1")
        путь = f"/title/{первый.slug}/"
        return site.pages[путь].body

    def test_обработчик_не_появился(self, страница):
        """Опасен атрибут внутри тега, а не буквы в тексте.

        Первая редакция искала подстроку `onerror=alert` где угодно и находила
        её внутри экранированного `&lt;img src=x onerror=alert(1)&gt;` — то
        есть падала на верно экранированной странице. Проверка, падающая на
        исправном коде, уводит правку в никуда.
        """
        assert _обработчики(страница) == [], (
            f"обработчик события в разметке: {_обработчики(страница)[:2]}")

    def test_злое_значение_дошло_до_страницы(self, страница):
        """Иначе проверка выше проходит на пустом месте."""
        assert "onerror" in страница or "\\u003c" in страница

    def test_блоки_разметки_закрыты_правильно(self, страница):
        assert страница.count('<script type="application/ld+json">') == \
               len(re.findall(r'<script type="application/ld\+json">.*?</script>',
                              страница, re.S))
