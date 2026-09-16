"""Адрес постера от поставщика проверяется по схеме, а не подставляется как есть.

`poster_url` приходит из ответа поставщика и попадает в `src` изображения.
Экранирование там есть — значение не вырвется из атрибута, — но схема адреса не
проверялась вовсе: `javascript:`, `data:`, `file:` и любой другой попали бы на
страницу такими, как пришли.

Исполняемым `<img src="javascript:…">` в нынешних браузерах не является, и
пугать этим не нужно. Существенно другое: непроверенное значение из внешнего
источника доходит до атрибута разметки, а тот же адрес завтра может
понадобиться в ссылке или `srcset`, где правила иные. И отдельно — каждый
посетитель делает запрос по этому адресу: подставив чужой хост, поставщик
получает обращение от каждого зрителя витрины.

Правило взято из данных, а не выдумано: в снимке боевого каталога 19 658
адресов, все — `https`, с пяти хостов. Относительный путь допускается тоже:
это собственная заглушка витрины.
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

    def test_пустой_адрес_даёт_заглушку(self):
        разметка = render_mod._poster(_карточка(None))
        assert _src(разметка) == []
        assert "card__poster-empty" in разметка


class TestНедопустимыеАдресаОтвергаются:
    @pytest.mark.parametrize("адрес", [
        "javascript:alert(1)",
        "data:text/html;base64,PHN2Zz48L3N2Zz4=",
        "file:///etc/passwd",
        "vbscript:msgbox(1)",
        "http://poster.cdnvideohub.com/a.jpg",
    ])
    def test_чужая_схема_не_попадает_в_разметку(self, адрес):
        разметка = render_mod._poster(_карточка(адрес))
        assert _src(разметка) == [], f"адрес со схемой из {адрес!r} попал в src"
        assert "card__poster-empty" in разметка, "заглушки на месте отвергнутого нет"

    def test_протокольно_относительный_адрес_отвергается(self):
        """`//чужой-хост/a.jpg` наследует схему страницы и уводит запрос."""
        assert _src(render_mod._poster(_карточка("//чужой.example/a.jpg"))) == []

    def test_пробелы_и_регистр_не_обходят_проверку(self):
        for адрес in ("  JavaScript:alert(1)", "\tjavascript:alert(1)",
                      "JAVASCRIPT:alert(1)"):
            assert _src(render_mod._poster(_карточка(адрес))) == [], адрес


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
