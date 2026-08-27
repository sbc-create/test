"""REQ-LORDS-PLAYER-LIVE: посетитель получает плеер, а не внутренний код отказа.

История регрессии. Живые данные Lords раньше выкладывал черновой сборщик, и он
же собирал настоящий плеер: `<video-player>` с агрегатором, идентификатором
тайтла и Publisher ID. Переключение на полноценный рендерер вернуло сайту
навигацию, пагинацию и разделы — но не плеер: в `_title_page` был подключён
только путь-заглушка. Настоящая разметка плеера в модуле была, до неё просто
никто не доходил.

Наружу это вышло хуже, чем «плеера нет». На публичной странице фильма посетитель
читал служебный текст про передачу контракта, Publisher ID и код
`BLOCKED_INPUT_CDNVIDEOHUB_CREDENTIALS`. Внутренние коды, имена секретов и
инструкции владельцу не должны попадать в выдачу ни при каком состоянии сборки.

Поэтому проверяется два разных факта, и оба нужны:
  * тайтл с подтверждённым источником воспроизведения получает настоящий плеер;
  * тайтл без него получает нейтральную фразу, а не диагностику.
"""

from __future__ import annotations

import re

import yaml

from factory.lords import live_catalog
from factory.lords import render as render_mod
from factory.paths import PATHS

#: Строки, которых не должно быть в публичной разметке ни при каких условиях.
FORBIDDEN_IN_PUBLIC_HTML = (
    "BLOCKED_INPUT",
    "CDNVIDEOHUB_CREDENTIALS",
    "учётных данных",
    "Publisher",
    "Secret Hub",
    "CREDENTIALS_DIRECTORY",
)

PUBLISHER_ID = "10238"


def item(index: int, *, playback: dict | None) -> dict:
    return {
        "external_id": f"01a0-{index:05d}",
        "name": f"Тайтл {index}",
        "type": "movie",
        "is_series": False,
        "year": 2023,
        "poster_url": f"https://poster.cdnvideohub.com/p/{index}.jpg",
        "tags": ["Драма"],
        "kinopoisk_rating": 7.5,
        "imdb_rating": 6.8,
        "external_ids": {},
        "playback": playback,
        "created_at": "2026-08-20T10:00:00Z",
        "updated_at": "2026-08-21T10:00:00Z",
    }


def render(items, *, publisher_id: str | None = PUBLISHER_ID):
    catalog = live_catalog.catalog_from_live(items)
    package = yaml.safe_load(PATHS.site_package("lords-01").read_text(encoding="utf-8"))
    site = render_mod.render_site(
        package, catalog=catalog, environ={}, publisher_id=publisher_id)
    pages = site.pages
    return dict(pages) if isinstance(pages, dict) else {p.path: p for p in pages}


def body(page) -> str:
    return page.body if hasattr(page, "body") else str(page)


def title_html(pages, slug_fragment: str = "") -> str:
    for path, page in pages.items():
        if path.startswith("/title/") and slug_fragment in path:
            return body(page)
    raise AssertionError("страница тайтла не найдена")


class TestPlayableTitleGetsARealPlayer:
    def test_video_player_element_is_rendered(self):
        pages = render([item(1, playback={"aggregator": "kp", "title_id": "5072746"})])
        html = title_html(pages)
        assert "<video-player" in html, "настоящего плеера на странице нет"

    def test_player_carries_the_titles_own_identifiers(self):
        pages = render([item(1, playback={"aggregator": "kp", "title_id": "5072746"})])
        html = title_html(pages)
        assert 'data-aggregator="kp"' in html
        assert 'data-title-id="5072746"' in html
        assert f'data-publisher-id="{PUBLISHER_ID}"' in html

    def test_provider_script_is_attached(self):
        pages = render([item(1, playback={"aggregator": "kp", "title_id": "5072746"})])
        html = title_html(pages)
        assert "player.cdnvideohub.com" in html
        assert "data-player-script" in html

    def test_each_title_gets_its_own_player_id(self):
        """Общий ident склеил бы два плеера на соседних страницах в один."""
        pages = render([
            item(1, playback={"aggregator": "kp", "title_id": "111"}),
            item(2, playback={"aggregator": "kp", "title_id": "222"}),
        ])
        idents = set()
        for path, page in pages.items():
            if path.startswith("/title/"):
                found = re.findall(r'ident="([^"]+)"', body(page))
                idents.update(found)
        assert len(idents) >= 2, f"идентификаторы плееров повторяются: {idents}"


class TestUnplayableTitleStaysPolite:
    def test_no_internal_diagnostics_reach_the_page(self):
        pages = render([item(1, playback=None)])
        html = title_html(pages)
        for needle in FORBIDDEN_IN_PUBLIC_HTML:
            assert needle not in html, f"в публичной разметке служебная строка {needle!r}"

    def test_visitor_sees_a_plain_sentence(self):
        pages = render([item(1, playback=None)])
        html = title_html(pages)
        assert "временно недоступно" in html, "нет нейтрального пользовательского текста"

    def test_one_unplayable_title_does_not_disable_the_others(self):
        pages = render([
            item(1, playback=None),
            item(2, playback={"aggregator": "kp", "title_id": "222"}),
        ])
        playable = [body(p) for path, p in pages.items()
                    if path.startswith("/title/") and "<video-player" in body(p)]
        assert playable, "рабочий тайтл потерял плеер из-за соседнего без источника"


class TestWholeSiteNeverLeaksDiagnostics:
    def test_no_page_of_the_site_contains_an_internal_code(self):
        pages = render([
            item(i, playback={"aggregator": "kp", "title_id": str(i)} if i % 2 else None)
            for i in range(1, 13)
        ])
        for path, page in pages.items():
            html = body(page)
            for needle in ("BLOCKED_INPUT", "CDNVIDEOHUB_CREDENTIALS"):
                assert needle not in html, f"{path} содержит {needle}"

    def test_missing_publisher_id_still_never_leaks(self):
        """Даже без Publisher ID страница обязана молчать о причинах."""
        pages = render([item(1, playback={"aggregator": "kp", "title_id": "1"})],
                       publisher_id=None)
        html = title_html(pages)
        for needle in FORBIDDEN_IN_PUBLIC_HTML:
            assert needle not in html, f"в разметке служебная строка {needle!r}"
