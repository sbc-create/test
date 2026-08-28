"""Шаблон Lords: маршруты, вид, SEO, плеер, рантайм и ворота production.

Проверяется собранный сайт, а не намерение его собрать. Поэтому почти все тесты
работают с готовыми документами: план можно написать правильно и всё равно
отдать пустую страницу.
"""

from __future__ import annotations

import json
import re

import pytest
import yaml

from factory.lords import bundle as bundle_mod
from factory.lords import content_types as ct
from factory.lords import fixtures as fx
from factory.lords import gates
from factory.lords import plan as plan_mod
from factory.lords import player as player_mod
from factory.lords import preview as preview_mod
from factory.lords import render as render_mod
from factory.lords import serve as serve_mod
from factory.lords import theme as theme_mod
from factory.paths import PATHS

SITES = ("lords-01", "lords-02", "lords-03", "lords-04")

#: Пакеты с утверждённым доменом: публикуются как fixture-staging.
PUBLISHED = ("lords-01", "lords-02", "lords-03")
#: Пакет без домена: не публикуется и остаётся закрыт воротами целиком.
UNPUBLISHED = ("lords-04",)

#: Домен каждого опубликованного пакета. Второй копии сопоставления в тестах
#: нет: она берётся из реестра направления и сверяется с manifest.
def registry() -> dict:
    import json
    data = json.loads((PATHS.root / "config/directions/lords.json").read_text(encoding="utf-8"))
    return {d["site_id"]: d for d in data["domains"]}


def package(site_id: str) -> dict:
    return yaml.safe_load(PATHS.site_package(site_id).read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def catalog():
    return fx.build_catalog()


@pytest.fixture(scope="module")
def sites(catalog):
    return {
        site_id: render_mod.render_site(package(site_id), catalog=catalog, environ={})
        for site_id in SITES
    }


# ---------------------------------------------------------------------------
# Синтетический каталог
# ---------------------------------------------------------------------------
class TestFixtureCatalog:
    def test_catalog_is_deterministic(self):
        first, second = fx.build_catalog(), fx.build_catalog()
        assert [t.as_dict() for t in first.titles] == [t.as_dict() for t in second.titles]

    def test_every_record_is_marked_as_test_data(self, catalog):
        assert all(t.source == fx.SOURCE and t.fixture for t in catalog.titles)
        assert all(c.source == fx.SOURCE for c in catalog.collections)

    def test_slugs_are_unique(self, catalog):
        slugs = [t.slug for t in catalog.titles]
        assert len(set(slugs)) == len(slugs)

    def test_no_ratings_and_no_rights_holders(self, catalog):
        """Оценок и правообладателей нет как полей, а не как пустых значений."""
        record = catalog.titles[0].as_dict()
        forbidden = {"rating", "ratings", "votes", "score", "rights_holder", "copyright_holder"}
        assert not forbidden & set(record)

    def test_catalog_shows_every_required_shape(self, catalog):
        """Стенд обязан показать все формы, ради которых он существует."""
        assert catalog.of_type(fx.MOVIES) and catalog.of_type(fx.SERIES)
        assert catalog.of_type(fx.ANIMATION) and catalog.of_type(fx.ANIME)
        assert catalog.of_type(fx.DORAMA) and catalog.collections
        assert any(t.episodic for t in catalog.of_type(fx.SERIES))
        assert all(not t.episodic for t in catalog.of_type(fx.MOVIES))
        assert len(catalog.genres()) >= 5
        assert len(catalog.titles) > 24, "меньше страницы — пагинацию не показать"

    def test_posters_are_local_svg_without_external_requests(self, catalog):
        svg = render_mod.poster_svg(catalog.titles[0])
        assert svg.startswith("<svg") and "FIXTURE" in svg
        # xmlns — идентификатор пространства имён, а не адрес, по которому
        # что-то загружается. Всё остальное внешним быть не может.
        body = svg.replace('xmlns="http://www.w3.org/2000/svg"', "")
        assert "http://" not in body and "https://" not in body


# ---------------------------------------------------------------------------
# Маршруты
# ---------------------------------------------------------------------------
class TestRoutes:
    REQUIRED = ("/", "/catalog/", "/movies/", "/series/", "/new/", "/genres/",
                "/search/", "/robots.txt", "/sitemap.xml")

    @pytest.mark.parametrize("site_id", SITES)
    def test_required_routes_exist(self, sites, site_id):
        paths = sites[site_id].pages
        for route in self.REQUIRED:
            assert route in paths, f"{site_id}: нет {route}"

    @pytest.mark.parametrize("site_id", SITES)
    def test_detail_routes_exist(self, sites, site_id, catalog):
        site = sites[site_id]
        assert any(p.startswith("/genres/") and p != "/genres/" for p in site.pages)
        assert any(p.startswith("/years/") and p != "/years/" for p in site.pages)
        assert any(p.startswith("/countries/") and p != "/countries/" for p in site.pages)
        assert any(p.startswith("/title/") for p in site.pages)

    @pytest.mark.parametrize("site_id", SITES)
    def test_disabled_type_gets_no_surface_at_all(self, sites, site_id):
        """Выключенный тип не создаёт ни маршрута, ни ссылки, ни пункта меню."""
        site = sites[site_id]
        states = site.plan.type_states
        for name, state in states.items():
            if state.active or name == "collections":
                continue
            path = {"movies": "/movies/", "series": "/series/", "animation": "/animation/",
                    "anime": "/anime/", "dorama": "/dorama/"}.get(name)
            if not path:
                continue
            assert path not in site.pages, f"{site_id}: {name} выключен, но {path} есть"
            for page in site.pages.values():
                if page.content_type.startswith("text/html"):
                    assert f'href="{path}"' not in page.body, f"{site_id}: ссылка на {path}"

    @pytest.mark.parametrize("site_id", SITES)
    def test_disabled_type_answers_404_not_empty_200(self, sites, site_id):
        site = sites[site_id]
        app = serve_mod.Application(site)
        for name, state in site.plan.type_states.items():
            path = {"movies": "/movies/", "series": "/series/", "animation": "/animation/",
                    "anime": "/anime/", "dorama": "/dorama/"}.get(name)
            if not path or state.active:
                continue
            assert app.handle("GET", path).status == 404

    @pytest.mark.parametrize("site_id", SITES)
    def test_no_listing_answers_200_with_nothing_in_it(self, sites, site_id):
        """Пустая двухсотка — soft 404. Её быть не должно ни на одной странице."""
        for path, page in sites[site_id].pages.items():
            if not page.content_type.startswith("text/html"):
                continue
            if 'class="grid"' not in page.body:
                continue
            has_cards = 'class="card"' in page.body
            is_search = path == "/search/"
            assert has_cards or is_search, f"{site_id}{path}: сетка без единой карточки"

    @pytest.mark.parametrize("site_id", SITES)
    def test_pagination_exists_where_the_list_is_long(self, sites, site_id):
        site = sites[site_id]
        assert "/catalog/page/2/" in site.pages
        assert 'rel="next"' in site.pages["/catalog/"].body

    @pytest.mark.parametrize("path,expected", [
        ("/catalog", "/catalog/"),
        ("/Catalog/", "/catalog/"),
        ("//movies//", "/movies/"),
        ("/GENRES/Drama/", "/genres/drama/"),
    ])
    def test_url_normalisation_answers_308(self, sites, path, expected):
        app = serve_mod.Application(sites["lords-01"])
        response = app.handle("GET", path)
        assert response.status == 308
        assert dict(response.headers)["Location"] == expected

    def test_unknown_address_answers_404_with_a_page(self, sites):
        app = serve_mod.Application(sites["lords-01"])
        response = app.handle("GET", "/no-such-thing/")
        assert response.status == 404
        assert "Страница не найдена" in response.body.decode("utf-8")

    def test_probes_answer(self, sites):
        app = serve_mod.Application(sites["lords-01"])
        for path in (serve_mod.HEALTH_PATH, serve_mod.READY_PATH):
            response = app.handle("GET", path)
            assert response.status == 200
            assert json.loads(response.body)["status"] == "ok"

    def test_every_response_carries_the_noindex_header(self, sites):
        app = serve_mod.Application(sites["lords-01"])
        for path in ("/", "/catalog/", "/nope/", "/assets/site.css", "/robots.txt"):
            headers = dict(app.handle("GET", path).headers)
            assert headers["X-Robots-Tag"] == "noindex, nofollow"


# ---------------------------------------------------------------------------
# Четыре профиля — одно приложение
# ---------------------------------------------------------------------------
class TestProfiles:
    def test_one_blueprint_serves_all_four(self):
        packages = [package(site_id) for site_id in SITES]
        assert {p["blueprint"] for p in packages} == {"lords"}
        assert len({p["tenant"]["seo_profile"] for p in packages}) == 4

    def test_themes_differ_in_more_than_colour(self):
        profiles = plan_mod.load_profiles()
        tokens = {n: theme_mod.tokens_of(p) for n, p in profiles.items()}
        layouts = {n: theme_mod.layout_of(p) for n, p in profiles.items()}
        assert len({t["accent"] for t in tokens.values()}) == 4
        # Подложка больше не различает все четыре профиля, и это осознанно:
        # три продуктовых домена приведены к одному тёмному семейству, потому
        # что владелец смотрит на них вместе. Проверяется то, ради чего тест
        # написан, — что профили не превратились в копии друг друга.
        assert len({layout["density"] for layout in layouts.values()}) == 4
        assert len({layout["hero"] for layout in layouts.values()}) == 4
        # Плотность сетки постеров из этого перечня ушла: она перестала быть
        # стилевой ручкой профиля. Каталог фильмов узнаётся по плотному ряду
        # обложек, и три-четыре карточки шириной в треть экрана читались как
        # служебный шаблон, а не как витрина. Общая плотность закреплена
        # ниже — как уговор, а не как случайное совпадение.

    def test_the_three_product_domains_share_one_family(self):
        """Общая подложка у продуктовых профилей — решение, а не совпадение.

        Если один профиль случайно перезапишет другой, различия исчезнут не
        только в подложке, и это поймает соседний тест. Здесь фиксируется сам
        уговор: три домена выглядят как одно семейство, а акцент у каждого свой.
        """
        profiles = plan_mod.load_profiles()
        product = ["lords-general", "lords-new", "lords-curated"]
        tokens = {n: theme_mod.tokens_of(profiles[n]) for n in product}
        assert len({t["bg"] for t in tokens.values()}) == 1
        assert len({t["accent"] for t in tokens.values()}) == 3
        assert all(t["heading_font"] == tokens[product[0]]["heading_font"]
                   for t in tokens.values())

        # Плотный ряд обложек — требование продукта, одинаковое для трёх
        # доменов: это то, по чему каталог фильмов узнаётся с первого взгляда.
        layouts = {n: theme_mod.layout_of(profiles[n]) for n in product}
        assert len({tuple(sorted(lay["columns"].items())) for lay in layouts.values()}) == 1
        assert all(lay["columns"]["desktop"] >= 6 for lay in layouts.values())
        assert all(lay["columns"]["mobile"] >= 2 for lay in layouts.values())

    def test_profiles_still_differ_where_it_matters(self):
        """Уговор про общий вид не должен превратить профили в копии.

        Состав главной, геройский блок и плотность подачи остаются своими у
        каждого — иначе три домена стали бы одним сайтом под тремя адресами.
        """
        profiles = plan_mod.load_profiles()
        layouts = {n: theme_mod.layout_of(p) for n, p in profiles.items()}
        assert len({tuple(lay["home_blocks"]) for lay in layouts.values()}) == 4
        assert len({lay["hero"] for lay in layouts.values()}) == 4
        assert len({lay["density"] for lay in layouts.values()}) == 4

    def test_stylesheets_differ(self):
        profiles = plan_mod.load_profiles()
        sheets = {n: theme_mod.stylesheet(p) for n, p in profiles.items()}
        assert len(set(sheets.values())) == 4

    def test_configuration_of_one_profile_does_not_leak_into_another(self, sites):
        """Настройка соседа не должна встречаться в разметке сайта."""
        profiles = plan_mod.load_profiles()
        by_site = {site_id: sites[site_id].profile for site_id in SITES}
        for site_id, own in by_site.items():
            css = sites[site_id].pages["/assets/site.css"].body
            own_accent = theme_mod.tokens_of(profiles[own])["accent"]
            assert own_accent in css
            for other, profile in profiles.items():
                if other == own:
                    continue
                foreign = theme_mod.tokens_of(profile)["accent"]
                assert foreign not in css, f"{site_id}: цвет профиля {other} в своей теме"
                assert profile["label"] not in sites[site_id].pages["/"].body

    def test_each_owner_writes_its_own_texts(self, sites):
        """Заголовки и вступления владельцев не совпадают между сайтами."""
        homes = {site_id: sites[site_id].pages["/"].body for site_id in SITES}
        h1s = [re.search(r"<h1>(.*?)</h1>", body).group(1) for body in homes.values()]
        assert len(set(h1s)) == 4
        titles = [re.search(r"<title>(.*?)</title>", body).group(1) for body in homes.values()]
        assert len(set(titles)) == 4


# ---------------------------------------------------------------------------
# SEO без домена
# ---------------------------------------------------------------------------
class TestSeoWithoutDomain:
    @pytest.mark.parametrize("site_id", SITES)
    def test_every_page_is_closed_from_indexing(self, sites, site_id):
        for path, page in sites[site_id].pages.items():
            if not page.content_type.startswith("text/html"):
                continue
            assert '<meta name="robots" content="noindex, nofollow">' in page.body, path

    @pytest.mark.parametrize("site_id", UNPUBLISHED)
    def test_canonical_is_absent_without_a_domain_and_says_why(self, sites, site_id):
        for path, page in sites[site_id].pages.items():
            if not page.content_type.startswith("text/html"):
                continue
            assert 'rel="canonical"' not in page.body, path
            assert render_mod.CANONICAL_ABSENT in page.body, path

    @pytest.mark.parametrize("site_id", PUBLISHED)
    def test_canonical_points_at_its_own_domain(self, sites, site_id):
        """Canonical ведёт на свой адрес — и только на свой.

        Canonical и индексация решаются порознь: адрес известен, поэтому
        canonical осмыслен, а `noindex` рядом с ним закрывает стенд от выдачи.
        """
        own = registry()[site_id]["apex"]
        foreign = {d["apex"] for d in registry().values()} - {own}
        for path, page in sites[site_id].pages.items():
            if not page.content_type.startswith("text/html"):
                continue
            found = re.findall(r'<link rel="canonical" href="([^"]+)"', page.body)
            if path == "/search/":
                assert not found, "выдача поиска канонического адреса не получает"
                continue
            assert len(found) == 1, f"{site_id}{path}: canonical не один"
            assert found[0] == f"https://{own}{path}", f"{site_id}{path}: {found[0]}"
            for other in foreign:
                assert other not in page.body, f"{site_id}{path}: чужой домен {other}"

    @pytest.mark.parametrize("site_id", PUBLISHED)
    def test_canonical_matches_the_registry(self, site_id):
        """Домен в manifest и домен в реестре направления — одно и то же."""
        entry = registry()[site_id]
        pkg = package(site_id)
        assert pkg["domain"] == entry["apex"]
        assert pkg["canonical_url"] == f"https://{entry['apex']}/"
        assert pkg["aliases"] == [entry["www"]]
        assert pkg["tenant"]["seo_profile"] == entry["profile"]

    @pytest.mark.parametrize("site_id", SITES)
    def test_robots_closes_the_whole_site(self, sites, site_id):
        body = sites[site_id].pages["/robots.txt"].body
        assert "Disallow: /" in body
        assert "Sitemap:" not in body

    @pytest.mark.parametrize("site_id", SITES)
    def test_sitemap_has_no_addresses_while_there_is_no_domain(self, sites, site_id):
        body = sites[site_id].pages["/sitemap.xml"].body
        assert "<loc>" not in body
        assert "http://" not in body.replace(
            'xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"', "")
        assert sites[site_id].report["sitemap_urls"] == 0

    @pytest.mark.parametrize("site_id", SITES)
    def test_metadata_is_complete(self, sites, site_id):
        home = sites[site_id].pages["/"].body
        for marker in ('<meta name="description"', 'property="og:title"',
                       'property="og:description"', 'property="og:site_name"',
                       '"@type":"WebSite"'):
            assert marker in home, f"{site_id}: нет {marker}"

    @pytest.mark.parametrize("site_id", SITES)
    def test_title_pages_carry_breadcrumbs_and_entity_markup(self, sites, site_id):
        page = next(p for path, p in sites[site_id].pages.items() if path.startswith("/title/"))
        assert '"@type":"BreadcrumbList"' in page.body
        assert ('"@type":"Movie"' in page.body) or ('"@type":"TVSeries"' in page.body)
        assert 'class="breadcrumbs"' in page.body

    def test_exactly_one_site_indexes_each_owned_section(self, sites):
        """Индексируемая версия раздела принадлежит ровно одному сайту."""
        owners: dict = {}
        for site_id in SITES:
            for path, page in sites[site_id].pages.items():
                if page.indexable and page.content_type.startswith("text/html"):
                    owners.setdefault(path, []).append(site_id)
        shared = {path: who for path, who in owners.items() if len(who) > 1 and path != "/"}
        assert not shared, f"раздел индексируют несколько сайтов: {shared}"

    def test_search_results_are_never_indexable(self, sites):
        for site_id in SITES:
            assert sites[site_id].pages["/search/"].indexable is False

    def test_pagination_beyond_the_first_page_is_not_indexable(self, sites):
        for site_id in SITES:
            for path, page in sites[site_id].pages.items():
                if "/page/" in path:
                    assert page.indexable is False, f"{site_id}{path}"


# ---------------------------------------------------------------------------
# Плеер и секреты
# ---------------------------------------------------------------------------
class TestPlayerAndSecrets:
    def test_diagnostic_status_belongs_to_the_report_not_to_the_page(self, sites):
        """Причину отказа читает оператор, а не посетитель.

        Раньше тест требовал обратного — чтобы код `BLOCKED_INPUT_...` стоял
        прямо в разметке страницы тайтла. Требование дожило до публичных
        доменов: на странице фильма посетитель читал служебный текст про
        передачу учётных данных и Publisher ID. Диагностика никуда не делась,
        она переехала туда, где ей место, — в отчёт сборки.
        """
        site = sites["lords-01"]
        page = next(p for path, p in site.pages.items() if path.startswith("/title/"))
        assert "player__frame" in page.body, "область плеера пропала со страницы"
        assert player_mod.BLOCKED_STATUS not in page.body, (
            "внутренний код отказа снова попал в публичную разметку"
        )
        assert "учётных данных" not in page.body
        assert "Publisher" not in page.body
        assert site.report["player"]["status"] == player_mod.BLOCKED_STATUS, (
            "отчёт сборки перестал называть причину — теперь её негде прочитать"
        )

    def test_placeholder_is_not_a_passed_contract_check(self):
        state = player_mod.state({})
        check = player_mod.contract_check(state)
        assert check["passed"] is False
        assert check["status"] == player_mod.BLOCKED_STATUS

    def test_public_publisher_id_is_refused(self):
        with pytest.raises(player_mod.PublicPublisherIdError):
            player_mod.state({player_mod.FORBIDDEN_PUBLIC_ENV: "12345"})

    def test_publisher_id_never_reaches_the_markup(self, sites):
        for site_id in SITES:
            for page in sites[site_id].pages.values():
                assert "NEXT_PUBLIC" not in page.body
                assert player_mod.PUBLISHER_ENV not in page.body
                assert player_mod.TOKEN_ENV not in page.body

    def test_no_secret_reference_leaks_into_any_document(self, sites):
        for site_id in SITES:
            for path, page in sites[site_id].pages.items():
                assert "secret://" not in page.body, f"{site_id}{path}"

    def test_nothing_is_fetched_from_outside(self, sites):
        """Ни один подресурс не грузится извне: ни шрифт, ни скрипт, ни картинка.

        Проверяются именно загружаемые адреса, а не любое упоминание строки
        `https://`. Canonical и Open Graph называют собственный домен сайта и
        ничего не загружают; запрещать их значило бы запретить сам canonical.
        """
        loaders = re.compile(
            r'<script[^>]+src="([^"]+)"'
            r'|<img[^>]+src="([^"]+)"'
            r'|<link[^>]+rel="stylesheet"[^>]+href="([^"]+)"'
            r'|url\(([^)]+)\)'
        )
        for site_id in SITES:
            for path, page in sites[site_id].pages.items():
                for match in loaders.finditer(page.body):
                    href = next(g for g in match.groups() if g)
                    assert not href.startswith(("http://", "https://", "//")), \
                        f"{site_id}{path}: внешний подресурс {href}"

    def test_only_the_sites_own_domain_appears_in_its_documents(self, sites):
        """Чужого домена в разметке сайта нет — ни в canonical, ни в ссылке."""
        by_site = registry()
        for site_id in PUBLISHED:
            foreign = {d["apex"] for d in by_site.values()} - {by_site[site_id]["apex"]}
            for path, page in sites[site_id].pages.items():
                for other in foreign:
                    assert other not in page.body, f"{site_id}{path}: {other}"

    def test_no_material_from_the_reference_sites(self, sites):
        """Материалов референсов нет.

        Проверяются именно хосты референсов. Подстрока «lordfilm» для этого не
        годится: собственные домены направления — `lordfilm47.space` и
        `lordserial33.biz`, и запрет по подстроке запретил бы сайту называть
        сам себя.
        """
        forbidden = ("lordserials.fan", "lordfilm-hit.org")
        for site_id in SITES:
            for path, page in sites[site_id].pages.items():
                lowered = page.body.lower()
                for marker in forbidden:
                    assert marker not in lowered, f"{site_id}{path}: {marker}"


# ---------------------------------------------------------------------------
# Ворота production
# ---------------------------------------------------------------------------
class TestProductionGates:
    """Шесть операций, которые отсутствующие данные делают невозможными.

    Проверяется не сообщение об ошибке, а сама невозможность: каждая попытка
    выполняется через ту же функцию, что стоит на пути настоящей операции.
    """

    @pytest.mark.parametrize("site_id", UNPUBLISHED)
    def test_package_without_domain_target_and_canonical_cannot_be_ready(self, site_id):
        ok, missing = gates.ready_for_deployment(package(site_id))
        assert ok is False
        assert set(missing) == {"domain", "canonical_url", "target_ref"}

    @pytest.mark.parametrize("site_id", UNPUBLISHED)
    def test_indexing_cannot_be_enabled_without_a_domain(self, site_id):
        from factory.errors import BlockedSeo
        pkg = package(site_id) | {"seo_indexing_enabled": True}
        with pytest.raises(BlockedSeo) as exc:
            gates.check_indexing(pkg)
        assert "домен" in str(exc.value)

    def test_indexing_cannot_be_enabled_with_a_domain_but_no_canonical(self):
        from factory.errors import BlockedSeo
        pkg = package("lords-01") | {
            "seo_indexing_enabled": True, "domain": "example.test", "canonical_url": None,
        }
        with pytest.raises(BlockedSeo) as exc:
            gates.check_indexing(pkg)
        assert "canonical_url" in str(exc.value)

    @pytest.mark.parametrize("site_id", UNPUBLISHED)
    def test_production_sitemap_cannot_be_built_without_a_domain(self, site_id):
        from factory.errors import BlockedInput
        pkg = package(site_id) | {"environment": "production"}
        with pytest.raises(BlockedInput):
            gates.check_production_sitemap(pkg)

    @pytest.mark.parametrize("site_id", UNPUBLISHED)
    def test_production_deploy_is_impossible_without_a_target(self, site_id):
        from factory.errors import BlockedAccess
        with pytest.raises(BlockedAccess) as exc:
            gates.check_production_deploy(package(site_id))
        assert "цель выката" in str(exc.value)

    @pytest.mark.parametrize("site_id", UNPUBLISHED)
    def test_tls_cannot_be_issued_without_a_domain(self, site_id):
        from factory.errors import BlockedInput
        with pytest.raises(BlockedInput) as exc:
            gates.check_tls_certificate(package(site_id))
        assert "домен" in str(exc.value)

    @pytest.mark.parametrize("site_id", UNPUBLISHED)
    def test_metrica_and_webmaster_cannot_be_created_without_a_domain(self, site_id):
        from factory.errors import BlockedAnalyticsAccess
        pkg = package(site_id)
        with pytest.raises(BlockedAnalyticsAccess):
            gates.check_analytics_account(pkg)
        with pytest.raises(BlockedAnalyticsAccess):
            gates.check_webmaster_account(pkg)

    def test_an_old_format_manifest_does_not_slip_past_the_gates(self):
        """Пакет без новых полей проверяется теми же воротами.

        Ворота смотрят на `domain`, `canonical_url` и `target_ref` — поля, что
        есть в manifest любого поколения. Пакет, где новых полей просто нет,
        поэтому не «совместим», а закрыт ровно так же.
        """
        legacy = {
            "schema_version": 1,
            "site_id": "legacy-01",
            "environment": "production",
            "seo_indexing_enabled": True,
            "domain": None,
            "canonical_url": None,
            "target_ref": None,
        }
        assert set(gates.blocked_operations(legacy)) == set(gates.OPERATIONS)
        assert gates.ready_for_deployment(legacy)[0] is False

    def test_a_declared_readiness_status_does_not_open_the_gates(self):
        """Пакет не выдаёт разрешение сам себе."""
        forged = package("lords-04") | {
            "deployment_readiness": {"status": "READY", "reason": "готов"},
            "production_authorized": True,
        }
        from factory.errors import BlockedAccess
        assert gates.ready_for_deployment(forged)[0] is False
        with pytest.raises(BlockedAccess):
            gates.check_production_deploy(forged)

    @pytest.mark.parametrize("site_id", PUBLISHED)
    def test_a_published_package_is_still_closed_for_production(self, site_id):
        """Домен и цель открыли staging — и только staging.

        Это главный риск этого этапа: получив домен, пакет выглядит «готовым», и
        отличить готовность к стенду от готовности к production становится
        некому. Поэтому проверяется отдельно, что production закрыт по-прежнему,
        причём не одним условием, а тремя независимыми.
        """
        from factory.errors import BlockedAccess, BlockedSeo
        pkg = package(site_id)
        assert pkg["production_authorized"] is False
        assert pkg["environment"] == "staging"
        assert pkg["seo_indexing_enabled"] is False
        # 1. Выкат в production невозможен: авторизации владельца нет.
        with pytest.raises(BlockedAccess) as exc:
            gates.check_production_deploy(pkg)
        assert "production_authorized" in str(exc.value)
        # 2. Индексацию не включить: возражают три независимых условия —
        #    окружение, авторизация владельца и права в Вебмастере.
        from factory import validation
        forged = dict(pkg)
        forged["seo_indexing_enabled"] = True
        blockers: list = []
        validation._check_analytics(forged, blockers, [])
        reasons = [b.reason for b in blockers if b.field == "seo_indexing_enabled"]
        assert len(reasons) >= 3, f"индексацию закрывает слишком мало условий: {reasons}"
        # 3. Ворота домена при этом молчат — домен действительно есть.
        gates.check_indexing({**pkg, "seo_indexing_enabled": False})
        with pytest.raises(BlockedSeo):
            gates.check_indexing({**pkg, "seo_indexing_enabled": True,
                                  "canonical_url": None})

    @pytest.mark.parametrize("site_id", PUBLISHED)
    def test_a_published_package_is_ready_for_staging_only(self, site_id):
        ok, missing = gates.ready_for_deployment(package(site_id))
        assert ok is True and missing == []
        target = package(site_id)["target_ref"]
        from factory import inventory
        entry = inventory.target(target)
        assert entry["environments"] == ["staging"]
        assert entry["production_capable"] is False

    def test_validation_reports_the_gates_it_owns(self):
        from factory import validation
        # Пакет без домена и цели закрыт по цели выката.
        unpublished = validation.validate("lords-04")
        assert unpublished.ok is False
        assert any(b.field == "target_ref" for b in unpublished.blockers)
        # Пакет с доменом и целью закрыт правами на контент, а не отсутствием цели.
        published = validation.validate("lords-01")
        assert published.ok is False
        assert not [b for b in published.blockers if b.field == "target_ref"]
        assert any("rights" in b.field for b in published.blockers)

    def test_fixture_catalog_cannot_reach_production(self):
        """Стенд отказывается собираться для production по самому окружению."""
        from factory.errors import BlockedInput
        with pytest.raises(BlockedInput):
            preview_mod.build_preview("site-a")


# ---------------------------------------------------------------------------
# Стенд и переносимый пакет
# ---------------------------------------------------------------------------
class TestPreviewAndBundle:
    def test_preview_is_reproducible(self, tmp_path):
        first = preview_mod.build_preview("lords-01", output=tmp_path / "one")
        second = preview_mod.build_preview("lords-01", output=tmp_path / "two")
        assert first.report["digest"] == second.report["digest"]
        assert first.report["documents"] == second.report["documents"]

    def test_preview_refuses_a_package_with_a_real_source(self):
        from factory.errors import BlockedInput
        with pytest.raises(BlockedInput):
            preview_mod._assert_no_real_source(
                package("lords-01") | {"content_api": {"mode": "live"}})
        with pytest.raises(BlockedInput):
            preview_mod._assert_no_real_source(
                package("lords-01") | {"content_source": {"rights_confirmed": True}})

    def test_bundle_is_byte_identical_on_a_repeat_build(self, tmp_path):
        first = bundle_mod.build_bundle("lords-02", output=tmp_path / "one")
        second = bundle_mod.build_bundle("lords-02", output=tmp_path / "two")
        assert first["sha256"] == second["sha256"]

    def test_bundle_carries_a_runtime_and_a_rollback_artifact(self, tmp_path):
        result = bundle_mod.build_bundle("lords-03", output=tmp_path)
        import tarfile
        with tarfile.open(result["archive"]) as archive:
            names = set(archive.getnames())
        assert {"serve.py", "Dockerfile", "README.md",
                "bundle-manifest.json", "rollback.json"} <= names
        rollback = json.loads((tmp_path / "lords-03.rollback.json").read_text(encoding="utf-8"))
        assert rollback["release"] == result["release"]
        assert rollback["procedure"], "процедура отката пуста"

    def test_bundle_runtime_installs_nothing_at_start(self):
        runtime = bundle_mod.RUNTIME
        for forbidden in ("pip install", "pip3 install", "requests", "urllib.request.urlopen("):
            assert forbidden not in runtime
        assert "pip install" not in bundle_mod.DOCKERFILE

    def test_bundle_runtime_normalises_addresses_like_the_factory_runtime(self):
        """Две реализации нормализации обязаны совпадать на общей таблице."""
        from urllib.parse import unquote
        head, _, tail = bundle_mod.RUNTIME.partition("def normalize(")
        source = "def normalize(" + tail.split("\ndef resolve(")[0]
        namespace: dict = {"unquote": unquote}
        exec(compile(source, "runtime", "exec"), namespace)  # noqa: S102 — свой же текст
        for path in ("/", "/catalog", "/Catalog/", "//movies//", "/GENRES/Drama/",
                     "/robots.txt", "/title/x/", "/a//b"):
            assert namespace["normalize"](path) == serve_mod.normalize(path), path

    def test_bundle_manifest_says_it_is_not_deployable(self, tmp_path):
        result = bundle_mod.build_bundle("lords-04", output=tmp_path)
        assert result["manifest"]["deployable"] is False
        assert result["manifest"]["indexing"] == "disabled"
        assert result["manifest"]["player"]["passed"] is False

    def test_bundle_contains_no_secret_values(self, tmp_path):
        import tarfile
        result = bundle_mod.build_bundle("lords-01", output=tmp_path)
        with tarfile.open(result["archive"]) as archive:
            for member in archive.getmembers():
                if not member.isfile():
                    continue
                blob = archive.extractfile(member).read().decode("utf-8", "replace")
                assert "secret://" not in blob, member.name
                assert "NEXT_PUBLIC" not in blob, member.name


# ---------------------------------------------------------------------------
# Непересекаемость четырёх сайтов
# ---------------------------------------------------------------------------
class TestCrossSiteIsolation:
    def test_uniqueness_gate_finds_nothing(self, catalog):
        from factory.lords import gate as lords_gate
        plans = []
        for site_id in SITES:
            plans.append(plan_mod.build_plan(
                package(site_id), credentials_available=True,
                api_capabilities=catalog.capabilities()))
        report = lords_gate.check_plans(plans)
        assert report.findings == [], report.findings
        assert lords_gate.ownership_overlap(plans) == []

    def test_no_section_has_two_owners(self):
        profiles = plan_mod.load_profiles()
        plan_mod.owners(profiles)  # поднимет ValueError при двойном владении

    def test_type_states_cover_every_declared_type(self):
        for site_id in SITES:
            states = ct.resolve(package(site_id), credentials_available=False)
            assert set(states) == set(ct.CONTENT_TYPES)
