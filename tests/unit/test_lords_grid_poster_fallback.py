"""Карточка списка обязана показывать картинку, а не только букву.

`_poster()` (карточка списков/главной) читала сырой атрибут `poster_url`.
У фикстурной записи (`fx.Title`) такого атрибута нет вовсе — `getattr(...,
"poster_url", None)` тихо возвращал `None`, и каждая карточка стенда рисовала
одну только заглушку-букву, хотя для каждой записи уже собирался и
выкладывался настоящий файл заглушки (`poster_svg`, `/assets/posters/<slug>.svg`)
— просто карточка на него не ссылалась. То же расширяется до боевого каталога:
запись без `poster_url` или с небезопасным адресом (`http://`, `javascript:`)
получала только букву вместо ссылки на уже подготовленный локальный fallback.

Правило теста: у карточки всегда есть либо проверенный адрес поставщика, либо
локальная заглушка — и никогда только текст без изображения, пока для записи
можно построить путь заглушки (`poster_path` есть всегда, у обоих классов
записи).
"""
from __future__ import annotations

from factory.lords import fixtures as fx
from factory.lords import live_catalog as lc
from factory.lords import render as render_mod


def _live(poster_url=None, **over) -> lc.LiveTitle:
    entry = {
        "external_id": "x1", "name": "Запись", "type": "movie", "is_series": False,
        "year": 2020, "tags": [], "external_ids": {}, "poster_url": poster_url,
    }
    entry.update(over)
    return lc.title_from_item(entry)


class TestКарточкаФикстуры:
    def test_у_фикстурной_записи_карточка_несёт_картинку(self):
        catalog = fx.build_catalog()
        title = catalog.titles[0]
        html = render_mod._poster(title)
        assert "<img" in html, "карточка стенда не ссылается ни на одно изображение"
        assert title.poster_path in html

    def test_картинка_карточки_это_собственный_локальный_маршрут(self):
        catalog = fx.build_catalog()
        title = catalog.titles[0]
        html = render_mod._poster(title)
        assert f'src="{title.poster_path}"' in html

    def test_буква_остаётся_под_картинкой_на_случай_onerror(self):
        catalog = fx.build_catalog()
        html = render_mod._poster(catalog.titles[0])
        assert "card__poster-empty" in html, "onerror снимет img — под ним должна остаться буква"
        assert "onerror=" in html


class TestКарточкаЖивойЗаписи:
    def test_безопасный_адрес_источника_используется_как_есть(self):
        title = _live(poster_url="https://cdn.example/poster.webp")
        html = render_mod._poster(title)
        assert 'src="https://cdn.example/poster.webp"' in html

    def test_отсутствующий_постер_даёт_локальную_заглушку_а_не_только_букву(self):
        title = _live(poster_url=None)
        html = render_mod._poster(title)
        assert "<img" in html, "запись без poster_url осталась без ссылки на локальный fallback"
        assert title.poster_path in html

    def test_небезопасный_адрес_не_проходит_и_не_ломает_карточку(self):
        for unsafe in ("javascript:alert(1)", "http://insecure.example/x.jpg", "//evil.example/x.jpg"):
            title = _live(poster_url=unsafe)
            html = render_mod._poster(title)
            assert unsafe not in html, f"небезопасный адрес {unsafe!r} просочился в разметку"
            assert "<img" in html, f"небезопасный адрес {unsafe!r} оставил карточку без изображения"
            assert title.poster_path in html


class TestЗаглушкаНазываетПроисхождениеЧестно:
    def test_фикстурная_заглушка_помечена_тестовой(self):
        catalog = fx.build_catalog()
        svg = render_mod.poster_svg(catalog.titles[0])
        assert "FIXTURE" in svg
        assert "тестовая заглушка" in svg

    def test_живая_запись_без_постера_не_помечена_фикстурой(self):
        # Прежде poster_svg подписывал любую запись без разбора: живая запись
        # без постера у источника получала на своей странице «FIXTURE» — то
        # есть утверждение о происхождении, которое для неё неверно.
        title = _live(poster_url=None)
        svg = render_mod.poster_svg(title)
        assert "FIXTURE" not in svg
        assert "тестовая заглушка" not in svg
        assert "постер недоступен" in svg


class TestКарусельНеТеряетЗаглушкуНаНебезопасномАдресе:
    def test_признаки_карусели_несут_безопасный_или_локальный_постер(self):
        from factory.lords import recommend as recommend_mod

        title = _live(poster_url="http://insecure.example/x.jpg")
        features = recommend_mod.features_from_title(title)
        assert features.poster == title.poster_path, (
            "небезопасный адрес поставщика ушёл в признаки ранжировщика как есть"
        )
