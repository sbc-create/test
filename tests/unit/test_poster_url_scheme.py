"""Адрес постера от поставщика проверяется по схеме, а не подставляется как есть.

`poster_url` приходит из ответа поставщика и попадает в `src` изображения.
Экранирование там есть — значение не вырвется из атрибута, — но одного
экранирования недостаточно: непроверенная схема (`javascript:`, `data:`,
`file:` и любая другая) отображалась бы такой, как пришла.

Контракт — безопасный локальный fallback, а не пустая карточка. У каждой
записи уже есть подготовленный локальный SVG (`poster_path`,
`/assets/posters/<slug>.svg`, см. `knowledge/DECISIONS.md` D139 и
`tests/unit/test_lords_grid_poster_fallback.py`): карточка списка обязана
показывать картинку всегда, а не только букву, пока путь заглушки можно
построить — он есть у обоих классов записи. Поэтому отсутствующий или
недоверенный адрес не даёт пустую карточку: `title.poster_src` откатывается
на `poster_path`, и в `src` идёт он. Правило теста — не «пусто при отказе», а
«никогда чужая схема, всегда локальный путь при отказе».

Разрешённая схема взята из данных, а не выдумана: в снимке боевого каталога
19 658 адресов, все — `https`, с пяти хостов. Относительный путь допускается
тоже: это собственная заглушка витрины, не внешний адрес.
"""

from __future__ import annotations

import dataclasses
import sys
from html.parser import HTMLParser
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from factory.lords import fixtures as fx  # noqa: E402
from factory.lords import live_catalog as lc  # noqa: E402
from factory.lords import render as render_mod  # noqa: E402


def _src(разметка: str) -> list[str]:
    собранные: list[str] = []

    class Сборщик(HTMLParser):
        def handle_starttag(self, tag, attrs):
            if tag == "img":
                собранные.extend(v for k, v in attrs if k == "src" and v)

    Сборщик().feed(разметка)
    return собранные


def _обработчики_событий(разметка: str) -> list[str]:
    """Имена `on*`-атрибутов настоящих тегов — использовано для доказательства
    отсутствия breakout: подстрока `onerror=` в экранированном значении не в счёт,
    разбирает атрибуты тегов только html.parser."""
    найдены: list[str] = []

    class Сборщик(HTMLParser):
        def handle_starttag(self, tag, attrs):
            for имя, _ in attrs:
                if имя and имя.lower().startswith("on"):
                    найдены.append(f"<{tag} {имя}=…>")

    Сборщик().feed(разметка)
    return найдены


def _тегов(разметка: str, имя: str) -> int:
    счёт = 0

    class Сборщик(HTMLParser):
        def handle_starttag(self, tag, attrs):
            nonlocal счёт
            if tag == имя:
                счёт += 1

    Сборщик().feed(разметка)
    return счёт


def _карточка(poster_url: str | None):
    базовый = fx.build_catalog().titles[0]
    поля = {f.name: getattr(базовый, f.name) for f in dataclasses.fields(базовый)}
    свои = {f.name for f in dataclasses.fields(lc.LiveTitle)}
    поля = {k: v for k, v in поля.items() if k in свои}
    поля["poster_url"] = poster_url
    return lc.LiveTitle(**поля)


class TestДопустимыеАдресаПроходят:
    def test_https_остаётся(self):
        адрес = "https://poster.cdnvideohub.com/a/b.jpg"
        assert _src(render_mod._poster(_карточка(адрес))) == [адрес]

    def test_пустой_адрес_даёт_локальную_заглушку_а_не_пустую_карточку(self):
        карточка = _карточка(None)
        разметка = render_mod._poster(карточка)
        assert _src(разметка) == [карточка.poster_path]
        assert "card__poster-empty" in разметка, "буква под картинкой должна остаться"


class TestНедопустимыеАдресаОткатываютсяНаЛокальнуюЗаглушку:
    """Отвергнутый адрес не значит пустую карточку: `src` — всегда
    `poster_path`, никогда чужой хост и никогда сырое значение поставщика."""

    @pytest.mark.parametrize("адрес", [
        "javascript:alert(1)",
        "data:text/html;base64,PHN2Zz48L3N2Zz4=",
        "file:///etc/passwd",
        "vbscript:msgbox(1)",
        "http://poster.cdnvideohub.com/a.jpg",
    ])
    def test_чужая_схема_не_попадает_в_src(self, адрес):
        карточка = _карточка(адрес)
        разметка = render_mod._poster(карточка)
        assert _src(разметка) == [карточка.poster_path], (
            f"адрес со схемой из {адрес!r} должен уступить место локальной заглушке")
        assert адрес not in разметка, f"сырой адрес {адрес!r} просочился в разметку"

    def test_протокольно_относительный_адрес_отвергается(self):
        """`//чужой-хост/a.jpg` наследует схему страницы и уводит запрос."""
        карточка = _карточка("//чужой.example/a.jpg")
        assert _src(render_mod._poster(карточка)) == [карточка.poster_path]

    def test_пробелы_и_регистр_не_обходят_проверку(self):
        for адрес in ("  JavaScript:alert(1)", "\tjavascript:alert(1)",
                      "JAVASCRIPT:alert(1)", "\njavascript:alert(1)",
                      " \t javascript:alert(1)"):
            карточка = _карточка(адрес)
            assert _src(render_mod._poster(карточка)) == [карточка.poster_path], адрес


class TestBreakoutИЭкранирование:
    """Разрешённая схема — не индульгенция: даже `https://`-адрес, который
    содержит попытку вырваться из атрибута или из тега, обязан остаться
    данными, а не стать разметкой. Проверяется структурно (`html.parser`),
    а не подстрокой: подстрока `onerror=` встречается и внутри безобидного
    экранированного текста."""

    ПОПЫТКИ_ВЫРВАТЬСЯ_ИЗ_АТРИБУТА = [
        'https://evil.example/a.jpg" onerror="alert(1)',
        "https://evil.example/a.jpg' onerror='alert(1)",
        'https://evil.example/a.jpg"><script>alert(1)</script>',
        'https://evil.example/a.jpg"><img src=x onerror=alert(1)>',
        "https://evil.example/a.jpg\" autofocus onfocus=\"alert(1)",
    ]

    @pytest.mark.parametrize("адрес", ПОПЫТКИ_ВЫРВАТЬСЯ_ИЗ_АТРИБУТА)
    def test_кавычка_или_тег_в_https_адресе_не_создают_обработчик(self, адрес):
        разметка = render_mod._poster(_карточка(адрес))
        assert _обработчики_событий(разметка) == [], (
            f"адрес {адрес!r} породил атрибут события в разметке")
        assert _тегов(разметка, "script") == 0, (
            f"адрес {адрес!r} ввёл посторонний тег <script>")
        assert _тегов(разметка, "img") == 1, (
            f"адрес {адрес!r} должен остаться данными одного <img>, а не новой разметкой")

    @pytest.mark.parametrize("адрес", [
        'javascript:alert(1)"><script>alert(1)</script>',
        'data:text/html,<script>alert(1)</script>',
        '"><script>alert(document.cookie)</script>',
        "'><svg onload=alert(1)>",
    ])
    def test_небезопасная_схема_с_разметкой_внутри_тоже_откатывается(self, адрес):
        карточка = _карточка(адрес)
        разметка = render_mod._poster(карточка)
        assert _src(разметка) == [карточка.poster_path]
        assert _обработчики_событий(разметка) == []
        assert _тегов(разметка, "script") == 0
        assert _тегов(разметка, "svg") == 0


class TestПравилоВзятоИзДанных:
    def test_разрешена_ровно_одна_схема(self):
        assert fx.SAFE_POSTER_SCHEMES == ("https://",)

    def test_относительный_путь_витрины_проходит(self):
        """Собственная заглушка — не внешний адрес, и схемой не проверяется."""
        assert fx.safe_poster_src("/assets/posters/x.svg") == "/assets/posters/x.svg"


class TestВсеПотребителиЗакрыты:
    """Проверка стоит у источника, а не в одной из четырёх точек вставки.

    Адрес постера доходит до разметки четырьмя путями: карточка, карусель,
    главный постер страницы произведения и указатель для поиска, который
    читает клиентский сценарий. Проверка в одной точке закрыла бы одну.
    """

    def test_свойство_карточки_проверяет_схему(self):
        assert _карточка("javascript:alert(1)").poster_src.startswith("/assets/")

    def test_данные_каталога_не_несут_чужой_схемы(self):
        """`_dataset` вкладывает адрес постера в JSON, который читает браузер.

        Первая редакция проверки смотрела `/search-index.json`: постеров он не
        несёт вовсе — только название, год и тип, — и проверка падала на том,
        что искала не там.
        """
        import yaml

        from factory.paths import PATHS

        каталог = fx.build_catalog()
        первый = каталог.titles[0]
        свои = {f.name for f in dataclasses.fields(lc.LiveTitle)}
        поля = {f.name: getattr(первый, f.name)
                for f in dataclasses.fields(первый) if f.name in свои}
        поля["poster_url"] = "javascript:alert(1)"
        живой = lc.LiveTitle(**поля)
        испорченный = dataclasses.replace(каталог, titles=(живой,) + каталог.titles[1:])
        пакет = yaml.safe_load(PATHS.site_package("lords-02").read_text(encoding="utf-8"))
        site = render_mod.render_site(пакет, catalog=испорченный, environ={},
                                      publisher_id="1")
        каталожные = [p for путь, p in site.pages.items()
                      if путь.startswith("/catalog/") and "listing-data" in p.body]
        assert каталожные, "страниц каталога с данными нет — проверять нечего"
        for страница in каталожные:
            assert "javascript:" not in страница.body, (
                "адрес со схемой javascript дошёл до данных, которые читает "
                "клиентский сценарий")

    def test_главный_постер_страницы_проверяет_схему(self):
        import yaml

        from factory.paths import PATHS

        каталог = fx.build_catalog()
        первый = каталог.titles[0]
        свои = {f.name for f in dataclasses.fields(lc.LiveTitle)}
        поля = {f.name: getattr(первый, f.name)
                for f in dataclasses.fields(первый) if f.name in свои}
        поля["poster_url"] = "javascript:alert(1)"
        живой = lc.LiveTitle(**поля)
        испорченный = dataclasses.replace(каталог, titles=(живой,) + каталог.titles[1:])
        пакет = yaml.safe_load(PATHS.site_package("lords-02").read_text(encoding="utf-8"))
        site = render_mod.render_site(пакет, catalog=испорченный, environ={},
                                      publisher_id="1")
        страница = site.pages[f"/title/{живой.slug}/"].body
        assert "javascript:" not in страница
