"""cards_media на collection_hub: карточки подборок с representative poster.

`/collections/` раньше отдавал текстовые `.card` без `.card__poster`.
Измеритель кандидата (`measure_candidate_tokens.js`) честно помечал
`card_aspect_ratio`/`cards_sampled` как unavailable — эталон их ждёт
на collection_hub. Правка в `_collections_index`: медиа берётся у первого
тайтла подборки через `Catalog.by_slug()`, без подмены fixture-данных и
без правок visual-scoring contract / reference packs.
"""

from __future__ import annotations

import re
from dataclasses import replace

from factory.lords import fixtures as fx
from factory.lords import preview as preview_mod
from factory.lords import render as render_mod

SITE_ID = "animedia-preview"


def _package():
    package, _ = preview_mod._package(SITE_ID)
    return package


def _hub_html(catalog: fx.Catalog) -> str:
    site = render_mod.render_site(_package(), catalog=catalog, environ={})
    page = site.pages.get("/collections/")
    assert page is not None, "profile without /collections/ — test fixture broken"
    return page.body


class _TitleWithPoster:
    """Minimal live-shaped title: fixture fields + poster_url for _poster()."""

    def __init__(self, title: fx.Title, poster_url: str):
        self._title = title
        self.poster_url = poster_url

    def __getattr__(self, name: str):
        return getattr(self._title, name)


class TestCollectionsIndexCardsCarryPosterMedia:
    def test_every_collection_card_has_card_poster(self):
        catalog = fx.build_catalog()
        assert catalog.collections, "fixture catalog must include collections"
        html = _hub_html(catalog)
        cards = re.findall(r'<article class="card".*?</article>', html, flags=re.S)
        assert len(cards) == len(catalog.collections)
        for card in cards:
            assert 'class="card__poster"' in card, (
                "collection_hub card missing .card__poster — cards_media stays unavailable"
            )
            assert f'href="' in card

    def test_poster_href_points_at_collection_not_title(self):
        catalog = fx.build_catalog()
        col = catalog.collections[0]
        html = _hub_html(catalog)
        assert (
            f'<a class="card__poster" href="{col.path}" tabindex="-1" aria-hidden="true">'
            in html
        )
        # Title path must not become the poster click target on the hub.
        title = catalog.by_slug(col.title_slugs[0])
        assert title is not None
        assert f'class="card__poster" href="{title.path}"' not in html

    def test_live_poster_url_is_surfaced_via_by_slug(self):
        """Representative media comes from Catalog.by_slug(title_slugs[0])."""
        base = fx.build_catalog()
        col = base.collections[0]
        slug = col.title_slugs[0]
        original = base.by_slug(slug)
        assert original is not None
        remote = "https://poster.cdnvideohub.com/collection-hub-rep.jpg"
        live_like = _TitleWithPoster(original, remote)
        titles = tuple(live_like if t.slug == slug else t for t in base.titles)
        catalog = fx.Catalog(
            titles=titles,
            collections=base.collections,
            _by_slug={t.slug: t for t in titles},
        )
        html = _hub_html(catalog)
        assert remote in html, "representative poster_url from by_slug() did not reach the card"

    def test_skips_missing_slugs_when_picking_representative(self):
        base = fx.build_catalog()
        col = base.collections[0]
        real_slug = col.title_slugs[0]
        original = base.by_slug(real_slug)
        assert original is not None
        remote = "https://poster.cdnvideohub.com/collection-hub-skip.jpg"
        live_like = _TitleWithPoster(original, remote)
        titles = tuple(live_like if t.slug == real_slug else t for t in base.titles)
        broken = replace(col, title_slugs=("no-such-slug", real_slug))
        catalog = fx.Catalog(
            titles=titles,
            collections=(broken,) + base.collections[1:],
            _by_slug={t.slug: t for t in titles},
        )
        html = _hub_html(catalog)
        assert remote in html

    def test_unresolvable_slugs_still_keep_poster_slot(self):
        """Empty/broken title_slugs must not drop .card__poster (measurement slot)."""
        base = fx.build_catalog()
        broken = replace(base.collections[0], title_slugs=("no-such-slug",))
        catalog = fx.Catalog(
            titles=base.titles,
            collections=(broken,) + base.collections[1:],
            _by_slug=dict(base._by_slug),
        )
        html = _hub_html(catalog)
        card = re.search(
            rf'<article class="card".*?{re.escape(broken.name)}.*?</article>',
            html,
            flags=re.S,
        )
        assert card, "broken collection card missing from hub"
        assert 'class="card__poster"' in card.group(0)
        assert "card__poster-empty" in card.group(0)
