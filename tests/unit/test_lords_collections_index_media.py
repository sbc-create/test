"""cards_media и состав карточек на collection_hub.

`/collections/` обязан отдавать измеримые `.card__poster`, ссылки на реальные
маршруты подборок, честный счётчик и representative-медиа через
`Catalog.by_slug()` с тем же фильтром типов, что и detail-страница.
Fixture-данные и visual-scoring contract/reference packs не подменяются.
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


def _site(catalog: fx.Catalog):
    return render_mod.render_site(_package(), catalog=catalog, environ={})


def _hub_html(catalog: fx.Catalog) -> str:
    page = _site(catalog).pages.get("/collections/")
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

    def test_poster_href_points_at_collection_not_title(self):
        catalog = fx.build_catalog()
        col = catalog.collections[0]
        html = _hub_html(catalog)
        assert (
            f'<a class="card__poster" href="{col.path}" tabindex="-1" aria-hidden="true">'
            in html
        )
        title = catalog.by_slug(col.title_slugs[0])
        assert title is not None
        assert f'class="card__poster" href="{title.path}"' not in html

    def test_live_poster_url_is_surfaced_via_by_slug(self):
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


class TestCollectionsIndexRespectsActiveKinds:
    """animedia-preview держит dorama=false — хаб не должен брать медиа из неё."""

    def test_representative_skips_inactive_content_types(self):
        base = fx.build_catalog()
        dorama = next(t for t in base.titles if t.content_type == fx.DORAMA)
        movie = next(t for t in base.titles if t.content_type == fx.MOVIES)
        included = "https://poster.cdnvideohub.com/kinds-included.jpg"
        excluded = "https://poster.cdnvideohub.com/kinds-excluded.jpg"
        titles = tuple(
            _TitleWithPoster(t, excluded) if t.slug == dorama.slug
            else _TitleWithPoster(t, included) if t.slug == movie.slug
            else t
            for t in base.titles
        )
        col = replace(base.collections[0], title_slugs=(dorama.slug, movie.slug))
        catalog = fx.Catalog(
            titles=titles,
            collections=(col,) + base.collections[1:],
            _by_slug={t.slug: t for t in titles},
        )
        html = _hub_html(catalog)
        assert included in html
        assert excluded not in html

    def test_record_count_matches_resolved_visible_titles_not_slug_list(self):
        base = fx.build_catalog()
        dorama = next(t for t in base.titles if t.content_type == fx.DORAMA)
        movie = next(t for t in base.titles if t.content_type == fx.MOVIES)
        col = replace(
            base.collections[0],
            title_slugs=(dorama.slug, movie.slug, "ghost-slug"),
        )
        catalog = fx.Catalog(
            titles=base.titles,
            collections=(col,) + base.collections[1:],
            _by_slug=dict(base._by_slug),
        )
        html = _hub_html(catalog)
        card = re.search(
            rf'<article class="card".*?{re.escape(col.name)}.*?</article>',
            html,
            flags=re.S,
        )
        assert card
        assert '<span class="card__meta">1 записей</span>' in card.group(0)
        assert f'{len(col.title_slugs)} записей' not in card.group(0)


class TestCollectionsIndexRoutesAndOrder:
    def test_hub_card_links_resolve_to_collection_detail_pages(self):
        catalog = fx.build_catalog()
        site = _site(catalog)
        html = site.pages["/collections/"].body
        for col in catalog.collections:
            assert col.path in site.pages, f"hub links to missing {col.path}"
            assert f'href="{col.path}"' in html
            detail = site.pages[col.path].body
            assert f"<h1>{col.name}</h1>" in detail

    def test_card_order_and_count_match_catalog_collections(self):
        catalog = fx.build_catalog()
        html = _hub_html(catalog)
        names = re.findall(r'<a class="card__title" href="[^"]+">([^<]+)</a>', html)
        assert names == [col.name for col in catalog.collections]

    def test_empty_collection_keeps_poster_slot_count_and_detail_route(self):
        base = fx.build_catalog()
        empty = replace(base.collections[0], title_slugs=())
        catalog = fx.Catalog(
            titles=base.titles,
            collections=(empty,) + base.collections[1:],
            _by_slug=dict(base._by_slug),
        )
        site = _site(catalog)
        assert empty.path in site.pages
        html = site.pages["/collections/"].body
        card = re.search(
            rf'<article class="card".*?{re.escape(empty.name)}.*?</article>',
            html,
            flags=re.S,
        )
        assert card, "empty collection disappeared from hub"
        assert 'class="card__poster"' in card.group(0)
        assert "card__poster-empty" in card.group(0)
        assert '<span class="card__meta">0 записей</span>' in card.group(0)
        assert f'href="{empty.path}"' in card.group(0)
        detail = site.pages[empty.path].body
        assert "По выбранным условиям в каталоге ничего нет" in detail


class TestCollectionDetailTitleCardsLinkToTitles:
    def test_detail_grid_cards_point_at_title_routes(self):
        package = _package()
        kinds = [
            name for name, enabled in (package.get("content_types") or {}).items()
            if enabled and name in {
                fx.MOVIES, fx.SERIES, fx.ANIMATION, fx.ANIME, fx.DORAMA,
            }
        ]
        catalog = fx.build_catalog()
        site = _site(catalog)
        col = catalog.collections[0]
        visible = render_mod._collection_titles(catalog, col, kinds)
        assert visible, "fixture collection must resolve at least one active title"
        detail = site.pages[col.path].body
        for title in visible[:3]:
            assert f'href="{title.path}"' in detail
            assert title.path in site.pages
