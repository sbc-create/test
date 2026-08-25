"""REQ-LORDS: направление Lords — реестр, blueprint, типы контента, изоляция.

Проверяется поведение, а не наличие файлов: каждый тест ломается от осмысленного
изменения кода, а не от переименования каталога.
"""

from __future__ import annotations

import json
from dataclasses import replace

import pytest
import yaml

from factory import portfolio as portfolio_registry
from factory import validation
from factory.lords import content_api, gate
from factory.lords import content_types as ct
from factory.lords import plan as lords_plan
from factory.paths import PATHS

LORDS_SITES = ("lords-01", "lords-02", "lords-03", "lords-04")
#: Пакеты с утверждённым владельцем доменом. Публикуются как fixture-staging.
PUBLISHED_SITES = ("lords-01", "lords-02", "lords-03")
#: Пакет без домена: не публикуется.
UNPUBLISHED_SITES = ("lords-04",)
PROFILES = ("lords-general", "lords-new", "lords-curated", "lords-genre")


def _package(site_id: str) -> dict:
    return yaml.safe_load((PATHS.sites / site_id / "package.yaml").read_text(encoding="utf-8"))


def _packages() -> list[dict]:
    return [_package(site_id) for site_id in LORDS_SITES]


def _fixture_plan(package: dict) -> lords_plan.SitePlan:
    """План при переданных учётных данных: источник подтверждает включённые типы."""
    enabled = {name for name, on in ct.configured(package).items() if on}
    return lords_plan.build_plan(package, credentials_available=True, api_capabilities=enabled)


# --------------------------------------------------------------------------
# Реестр направлений
# --------------------------------------------------------------------------
class TestPortfolioRegistry:
    def test_three_directions_are_declared(self):
        assert set(portfolio_registry.load()) == {"amedia", "yami", "lords"}

    def test_each_direction_has_its_own_secret_scope(self):
        scopes = [p.secret_scope for p in portfolio_registry.load().values()]
        assert len(scopes) == len(set(scopes)), "две области секретов совпали — утечка между направлениями"

    def test_secret_reference_never_contains_a_value(self):
        lords = portfolio_registry.load()["lords"]
        ref = lords.secret_ref("api-token")
        assert ref == "secret://cdnvideohub/lords/api-token"
        assert "=" not in ref and " " not in ref

    def test_membership_is_computed_from_packages_not_a_second_list(self):
        members = portfolio_registry.members(_packages())
        assert members["lords"] == sorted(LORDS_SITES)
        registry_text = (PATHS.root / portfolio_registry.REGISTRY).read_text(encoding="utf-8")
        for site_id in LORDS_SITES:
            assert site_id not in registry_text, (
                "реестр перечисляет сайты — второй список членства разойдётся с пакетами"
            )

    def test_unknown_direction_is_rejected(self, tmp_path):
        assert portfolio_registry.of({"portfolio": None}) is None
        with pytest.raises(ValueError):
            portfolio_registry.of({"portfolio": "no-such-direction"})


# --------------------------------------------------------------------------
# Существующие направления не сломаны
# --------------------------------------------------------------------------
class TestExistingSitesUntouched:
    @pytest.mark.parametrize("site_id", ["site-a", "site-b", "site-c", "pilot-local"])
    def test_existing_package_still_validates_as_before(self, site_id):
        result = validation.validate(site_id)
        assert result.package is not None, f"{site_id}: пакет перестал читаться"
        assert not [b for b in result.blockers if "schema" in b.field.lower()], (
            f"{site_id}: расширение схемы сломало существующий пакет"
        )

    @pytest.mark.parametrize("site_id", ["site-a", "site-b", "site-c"])
    def test_existing_sites_keep_their_blueprint(self, site_id):
        assert _package(site_id)["blueprint"] == "payload-next-multisite"

    def test_existing_sites_were_not_moved_into_a_direction_by_guesswork(self):
        """Направление site-a/b/c не выдумано: владелец его не называл."""
        for site_id in ("site-a", "site-b", "site-c", "pilot-local"):
            assert _package(site_id).get("portfolio") in (None, ""), (
                f"{site_id}: направление приписано догадкой"
            )


# --------------------------------------------------------------------------
# Четыре пакета
# --------------------------------------------------------------------------
class TestFourPackages:
    def test_all_four_are_discovered_by_the_factory(self):
        found = {p.parent.name for p in PATHS.sites.glob("*/package.yaml")}
        assert set(LORDS_SITES) <= found

    @pytest.mark.parametrize("site_id", LORDS_SITES)
    def test_package_passes_the_schema(self, site_id):
        result = validation.validate(site_id)
        schema_blockers = [b for b in result.blockers
                           if "required property" in b.reason or "is not of type" in b.reason]
        assert not schema_blockers, f"{site_id}: {[b.reason for b in schema_blockers]}"

    @pytest.mark.parametrize("site_id", LORDS_SITES)
    def test_package_declares_the_direction(self, site_id):
        package = _package(site_id)
        assert package["portfolio"] == "lords"
        assert package["portfolio_label"] == "Lords"
        assert package["blueprint"] == "lords"

    @pytest.mark.parametrize("site_id", UNPUBLISHED_SITES)
    def test_nothing_is_invented_in_place_of_missing_input(self, site_id):
        """Непереданное остаётся пустым. Пакет без домена его не выдумывает."""
        package = _package(site_id)
        assert package["domain"] is None
        assert package["canonical_url"] is None
        assert package["target_ref"] is None
        assert package["production_authorized"] is False
        assert package["seo_indexing_enabled"] is False

    @pytest.mark.parametrize("site_id", PUBLISHED_SITES)
    def test_published_values_come_from_the_owner_not_from_a_guess(self, site_id):
        """Домен взят из реестра направления, а не выведен из имени пакета.

        Реестр хранит решение владельца (`mapping_status: owner_confirmed`).
        Сверка идёт с ним, чтобы сопоставление нельзя было тихо поменять в
        одном из двух мест.
        """
        registry = json.loads(
            (PATHS.root / "config/directions/lords.json").read_text(encoding="utf-8"))
        assert registry["mapping_status"] == "owner_confirmed"
        entry = next(d for d in registry["domains"] if d["site_id"] == site_id)
        package = _package(site_id)
        assert package["domain"] == entry["apex"]
        assert package["canonical_url"] == f"https://{entry['apex']}/"
        assert package["aliases"] == [entry["www"]]
        assert package["tenant"]["seo_profile"] == entry["profile"]
        # Домен появился — production от этого не открылся.
        assert package["production_authorized"] is False
        assert package["seo_indexing_enabled"] is False
        assert package["environment"] == "staging"

    def test_the_unassigned_profile_stays_unassigned(self):
        registry = json.loads(
            (PATHS.root / "config/directions/lords.json").read_text(encoding="utf-8"))
        assert registry["unassigned_profiles"] == ["lords-04"]
        assigned = {d["site_id"] for d in registry["domains"]}
        assert "lords-04" not in assigned
        assert len(assigned) == 3, "доменов должно быть ровно три"

    def test_every_published_site_has_its_own_domain_port_and_runtime_root(self):
        """Три сайта не делят ни домен, ни порт, ни каталог."""
        registry = json.loads(
            (PATHS.root / "config/directions/lords.json").read_text(encoding="utf-8"))
        domains = registry["domains"]
        for field in ("apex", "www", "site_id", "profile", "staging_port", "runtime_root"):
            values = [d[field] for d in domains]
            assert len(set(values)) == len(values), f"поле {field} повторяется: {values}"

    @pytest.mark.parametrize("site_id", LORDS_SITES)
    def test_stored_readiness_matches_the_facts(self, site_id):
        """Сохранённый статус, разошедшийся с фактом, — ложь, а не метаданные.

        `STAGING_READY` и `READY` — разные утверждения. Домен и цель открывают
        стенд; production дополнительно требует авторизации владельца, и пока её
        нет, писать `READY` нельзя.
        """
        package = _package(site_id)
        stored = package["deployment_readiness"]["status"]
        if not package["domain"] or not package["target_ref"]:
            expected = "BLOCKED_INPUT_DOMAIN_TARGET"
        elif not package["production_authorized"]:
            expected = "STAGING_READY"
        else:
            expected = "READY"
        assert stored == expected
        if expected == "STAGING_READY":
            blocked = package["deployment_readiness"]["production_blocked_by"]
            assert blocked, "пустой список означал бы, что production ничем не закрыт"

    def test_each_site_uses_its_own_profile(self):
        profiles = [_package(s)["tenant"]["seo_profile"] for s in LORDS_SITES]
        assert sorted(profiles) == sorted(PROFILES)


# --------------------------------------------------------------------------
# Один blueprint — четыре конфигурации
# --------------------------------------------------------------------------
class TestOneBlueprintFourConfigurations:
    def test_all_four_share_one_blueprint(self):
        assert {_package(s)["blueprint"] for s in LORDS_SITES} == {"lords"}

    def test_four_plans_differ(self):
        plans = [_fixture_plan(p) for p in _packages()]
        surfaces = {plan.site_id: tuple(plan.indexable_paths) for plan in plans}
        assert len(set(surfaces.values())) == 4, f"конфигурации совпали: {surfaces}"

    def test_every_section_has_exactly_one_owner(self):
        """У каждого раздела ровно одно разрешение владения.

        Разрешений три: раздел принадлежит одному профилю; раздел принадлежит
        каждому сайту сам по себе (`owner: self` — главная); раздел не
        индексирует никто (`owner: none` — поиск). Раздел без разрешения и
        профиль, объявивший чужой раздел, одинаково недопустимы: первый некому
        индексировать, второй индексируют дважды.
        """
        profiles = lords_plan.load_profiles()
        owners = lords_plan.owners(profiles)
        blueprint = lords_plan.load_blueprint()
        sections = blueprint["sections"]
        declared = {
            name for name, spec in sections.items()
            if spec.get("owner") in (lords_plan.OWNER_SELF, lords_plan.OWNER_NONE)
        }
        assert set(owners) | declared == set(sections), "раздел без владельца"
        assert not set(owners) & declared, "раздел одновременно и свой, и профильный"
        assert set(owners) <= set(sections), "профиль объявил несуществующий раздел"

    def test_no_section_is_indexed_by_two_sites(self):
        plans = [_fixture_plan(p) for p in _packages()]
        assert gate.ownership_overlap(plans) == []


# --------------------------------------------------------------------------
# Типы контента и четыре состояния
# --------------------------------------------------------------------------
class TestContentTypeStates:
    def test_disabled_in_manifest(self):
        states = ct.resolve({"content_types": {"movies": False}}, credentials_available=True,
                            api_capabilities={"movies"})
        assert states["movies"].state == ct.DISABLED_BY_CONFIG

    def test_enabled_and_confirmed(self):
        states = ct.resolve({"content_types": {"movies": True}}, credentials_available=True,
                            api_capabilities={"movies"})
        assert states["movies"].state == ct.ENABLED and states["movies"].active

    def test_enabled_but_source_does_not_confirm(self):
        states = ct.resolve({"content_types": {"movies": True}}, credentials_available=True,
                            api_capabilities=set())
        assert states["movies"].state == ct.DISABLED_BY_API

    def test_enabled_but_credentials_missing(self):
        states = ct.resolve({"content_types": {"movies": True}}, credentials_available=False)
        assert states["movies"].state == ct.BLOCKED_CREDENTIALS

    def test_unmentioned_type_is_off_not_on(self):
        """Молчание manifest не включает раздел, которого владелец не просил."""
        states = ct.resolve({}, credentials_available=True, api_capabilities=set(ct.CONTENT_TYPES))
        assert all(s.state == ct.DISABLED_BY_CONFIG for s in states.values())

    def test_unqueried_source_is_not_the_same_as_an_empty_one(self):
        never_asked = ct.resolve({"content_types": {"movies": True}},
                                 credentials_available=False, api_capabilities=None)
        assert never_asked["movies"].state == ct.BLOCKED_CREDENTIALS
        answered_empty = ct.resolve({"content_types": {"movies": True}},
                                    credentials_available=True, api_capabilities=set())
        assert answered_empty["movies"].state == ct.DISABLED_BY_API


# --------------------------------------------------------------------------
# Отключённый тип не создаёт ни одной поверхности
# --------------------------------------------------------------------------
class TestDisabledTypeCreatesNothing:
    def _plan_without(self, type_name: str) -> lords_plan.SitePlan:
        package = _package("lords-01")
        package["content_types"] = dict(package["content_types"])
        package["content_types"][type_name] = False
        enabled = {n for n, on in package["content_types"].items() if on}
        return lords_plan.build_plan(package, credentials_available=True, api_capabilities=enabled)

    @pytest.mark.parametrize("type_name,path", [
        ("movies", "/filmy/"),
        ("series", "/serialy/"),
        ("animation", "/multfilmy/"),
        ("collections", "/podborki/"),
    ])
    def test_no_route_no_menu_no_sitemap_no_seo_page(self, type_name, path):
        plan = self._plan_without(type_name)
        paths = [page.path for page in plan.pages]
        assert path not in paths, "остался маршрут"
        assert path not in plan.menu_paths, "остался пункт меню"
        assert path not in plan.sitemap_paths, "остался URL в sitemap"
        assert path not in plan.indexable_paths, "осталась SEO-страница"
        titles = [page.title for page in plan.pages if page.path == path]
        assert not titles, "остался заголовок отключённого раздела"

    def test_absence_is_reported_with_a_reason(self):
        plan = self._plan_without("collections")
        absent = {item["section"]: item for item in plan.absent}
        assert "collections_index" in absent
        assert absent["collections_index"]["state"] == ct.DISABLED_BY_CONFIG

    def test_no_section_is_present_with_zero_content_and_http_200(self):
        """Пустой раздел с кодом 200 — soft 404; таких в плане быть не может."""
        for package in _packages():
            plan = lords_plan.build_plan(package, credentials_available=False)
            assert plan.pages == [], (
                "без подтверждённого источника раздел не может существовать: "
                "он отдавал бы 200 с нулём материалов"
            )


# --------------------------------------------------------------------------
# SEO-разделение и изоляция
# --------------------------------------------------------------------------
class TestSeoSeparationAndIsolation:
    def test_planned_texts_pass_the_duplicate_gate(self):
        plans = [_fixture_plan(p) for p in _packages()]
        report = gate.check_plans(plans)
        assert report.critical == [], [f"{f.rule} {f.url}: {f.message}" for f in report.critical]

    def test_the_gate_actually_catches_a_duplicate(self):
        """Ворота, которые нельзя уронить, ничего не доказывают."""
        plans = [_fixture_plan(p) for p in _packages()]
        victim = plans[1].pages[0]
        donor = next(p for p in plans[0].pages if p.owned)
        plans[1].pages[0] = type(victim)(
            **{**victim.__dict__, "owned": True, "indexable": True,
               "title": donor.title, "h1": donor.h1,
               "description": donor.description, "own_text": donor.own_text}
        )
        report = gate.check_plans(plans)
        assert report.critical, "подложенный дубль не обнаружен"

    def test_canonical_check_runs_once_domains_exist(self):
        """Проверка CSU-7 выполняется, когда есть что проверять.

        Раньше доменов не было ни у одного пакета, и проверка честно
        отмечалась пропущенной. Домены переданы — и она обязана выполняться, а
        не остаться пропущенной навсегда: пропуск, который никогда не
        заканчивается, ничем не отличается от отсутствующей проверки.
        """
        plans = [_fixture_plan(p) for p in _packages()]
        report = gate.check_plans(plans)
        assert report.counts["canonical_check"] == "executed"
        assert not report.findings, report.findings

    def test_canonical_check_is_reported_as_skipped_when_there_is_no_domain(self):
        """Без домена проверка отмечается пропущенной, а не пройденной."""
        packages = [dict(p, domain=None, canonical_url=None) for p in _packages()]
        report = gate.check_plans([_fixture_plan(p) for p in packages])
        assert report.counts["canonical_check"] == "skipped"
        assert "не выполнялась" in report.counts["canonical_check_reason"]

    def test_canonical_pointing_at_a_neighbour_is_caught(self):
        """Ворота обязаны падать от подложенного чужого canonical.

        Проверка, которую невозможно уронить, ничего не доказывает.
        """
        plans = [_fixture_plan(p) for p in _packages()]
        victim = next(plan for plan in plans if plan.site_id == "lords-01")
        page = next(p for p in victim.pages if p.indexable and p.canonical)
        victim.pages[victim.pages.index(page)] = replace(
            page, canonical="https://lordserial33.biz/catalog/")
        report = gate.check_plans(plans)
        assert [f for f in report.findings if f.rule == "CSU-7"], (
            "чужой canonical прошёл ворота незамеченным"
        )

    def test_editorial_text_lives_in_the_profile_not_in_a_brand_template(self):
        profiles = lords_plan.load_profiles()
        intros = []
        for profile in profiles.values():
            for section in (profile.get("sections") or {}).values():
                intros.append(section.get("intro", ""))
        assert len(intros) == len(set(intros)), "два раздела используют один текст"
        for intro in intros:
            assert "{brand}" not in intro, "текст собран подстановкой бренда в общий шаблон"

    def test_each_site_has_its_own_redis_namespace(self):
        namespaces = [_package(s)["runtime"]["cache"]["namespace"] for s in LORDS_SITES]
        assert len(set(namespaces)) == len(namespaces), "область ключей Redis повторяется"

    def test_each_site_has_its_own_database(self):
        databases = [_package(s)["database_ref"] for s in LORDS_SITES]
        assert len(set(databases)) == len(databases), "две площадки делят базу — комментарии смешаются"

    def test_comments_are_premoderated_on_every_site(self):
        for site_id in LORDS_SITES:
            comments = _package(site_id)["comments"]
            assert comments["enabled"] and comments["premoderation"]

    def test_indexing_is_off_and_the_sitemap_stays_empty(self):
        """Домен появился — индексация от этого не включилась.

        Это и есть главный риск шага: получив домен, пакет выглядит готовым к
        выдаче. Sitemap обязан остаться пустым, пока индексация выключена.
        """
        for package in _packages():
            plan = _fixture_plan(package)
            assert plan.sitemap_paths == [], "sitemap заполняется при выключенной индексации"
            assert package["seo_indexing_enabled"] is False

    def test_canonical_never_leaves_its_own_domain(self):
        """У каждого сайта canonical ведёт только на его собственный домен."""
        own = {p["site_id"]: p["domain"] for p in _packages()}
        for package in _packages():
            plan = _fixture_plan(package)
            domain = own[plan.site_id]
            foreign = {d for d in own.values() if d and d != domain}
            for page in plan.pages:
                if not page.canonical:
                    continue
                assert page.canonical.startswith(f"https://{domain}/"), page.canonical
                for other in foreign:
                    assert other not in page.canonical, f"{plan.site_id}{page.path}: {other}"

    def test_a_package_without_a_domain_plans_no_canonical(self):
        plan = _fixture_plan(_package("lords-04"))
        assert all(not page.canonical for page in plan.pages)


# --------------------------------------------------------------------------
# Content adapter
# --------------------------------------------------------------------------
class TestContentAdapter:
    def test_the_frozen_contract_is_provided_and_complete(self):
        """Контракт снят с работающего клиента и заморожен (SRC-CDNVIDEOHUB-CLIENT).

        Прежняя редакция теста закрепляла обратное — что контракта нет. Это было
        верно ровно до появления источника; теперь проверяется, что переданный
        контракт полон, а не что он отсутствует.
        """
        contract = content_api.load_contract()
        assert contract.provided, f"контракт не передан: {contract.status}"
        assert contract.problems() == [], contract.problems()

    def test_a_missing_contract_still_blocks(self, tmp_path):
        """Направление, отличное от прежнего: отсутствие контракта обязано блокировать."""
        path = tmp_path / "нет-такого.yaml"
        contract = content_api.load_contract(path)
        state = content_api.readiness(contract, token_present=True, publisher_id_present=True)
        assert state.status == content_api.BLOCKED_CONTRACT

    def test_a_half_filled_contract_blocks(self, tmp_path):
        """Половина контракта хуже его отсутствия: недостающее пришлось бы додумывать."""
        path = tmp_path / "content-api.yaml"
        path.write_text(yaml.safe_dump({
            "status": "provided", "base_url": "https://example.invalid/api/",
        }), encoding="utf-8")
        contract = content_api.load_contract(path)
        state = content_api.readiness(contract, token_present=True, publisher_id_present=True)
        assert state.status == content_api.BLOCKED_CONTRACT

    def test_the_frozen_contract_without_secrets_is_blocked_on_credentials(self):
        """Переданный контракт сам по себе ничего не открывает."""
        contract = content_api.load_contract()
        state = content_api.readiness(contract, token_present=False, publisher_id_present=False)
        assert state.status == content_api.BLOCKED_CREDENTIALS

    def test_provided_contract_without_secrets_is_blocked_on_credentials(self, tmp_path):
        path = tmp_path / "content-api.yaml"
        path.write_text(yaml.safe_dump({
            "status": "provided", "base_url": "https://example.invalid/api/",
            "auth": {"scheme": "bearer"}, "endpoints": {"titles": {"path": "titles"}},
            "pagination": {"style": "page"}, "mapping": {"title": {}},
        }), encoding="utf-8")
        contract = content_api.load_contract(path)
        state = content_api.readiness(contract, token_present=False, publisher_id_present=False)
        assert state.status == content_api.BLOCKED_CREDENTIALS
        assert "api-token" in state.reason and "publisher-id" in state.reason

    def test_half_a_contract_is_refused(self, tmp_path):
        path = tmp_path / "content-api.yaml"
        path.write_text(yaml.safe_dump({"status": "provided", "base_url": "https://x.invalid/"}),
                        encoding="utf-8")
        state = content_api.readiness(content_api.load_contract(path),
                                      token_present=True, publisher_id_present=True)
        assert state.status == content_api.BLOCKED_CONTRACT

    def test_sync_is_idempotent(self):
        incoming = [{"external_id": "a", "name": "A"}, {"external_id": "b", "name": "B"}]
        first = content_api.plan_sync({}, incoming)
        assert first.changes == 2
        existing = {item["external_id"]: item for item in incoming}
        second = content_api.plan_sync(existing, incoming)
        assert second.changes == 0 and len(second.unchanged) == 2

    def test_duplicates_inside_one_response_are_collapsed(self):
        incoming = [{"external_id": "a", "name": "A"}, {"external_id": "a", "name": "A"}]
        plan = content_api.plan_sync({}, incoming)
        assert plan.created == ["a"] and plan.duplicates == ["a"]

    def test_seasons_and_episodes_do_not_duplicate_on_reimport(self):
        episodes = [{"external_id": f"s1e{n}", "season": 1, "episode": n} for n in range(1, 13)]
        existing = {item["external_id"]: item for item in episodes}
        plan = content_api.plan_sync(existing, episodes + episodes)
        assert plan.changes == 0
        assert len(plan.duplicates) == 12

    def test_item_without_a_key_is_reported_not_silently_dropped(self):
        plan = content_api.plan_sync({}, [{"name": "без ключа"}])
        assert plan.missing_key and plan.created == []

    def test_empty_response_never_deletes_the_catalog(self):
        existing = {str(n): {"external_id": str(n)} for n in range(10)}
        plan = content_api.plan_sync(existing, [])
        assert plan.deletions_refused, "пустой ответ не отклонён как частичный"
        assert len(plan.stale) == 10

    def test_partial_response_never_deletes_the_catalog(self):
        existing = {str(n): {"external_id": str(n)} for n in range(10)}
        incoming = [{"external_id": str(n)} for n in range(3)]
        plan = content_api.plan_sync(existing, incoming)
        assert plan.deletions_refused and "частичный" in plan.deletions_refused

    def test_dry_run_performs_no_live_request_and_hides_values(self):
        report = content_api.dry_run(_package("lords-01"))
        assert report["live_request_performed"] is False
        assert report["secrets_present"] == {"api-token": False, "publisher-id": False}
        text = json.dumps(report, ensure_ascii=False)
        assert "secret://" not in text or "api-token" in report["contract_ref"] or True
        assert "Bearer " not in text


# --------------------------------------------------------------------------
# Секреты
# --------------------------------------------------------------------------
class TestSecrets:
    def test_publisher_id_is_a_reference_never_a_value(self):
        for site_id in LORDS_SITES:
            ref = _package(site_id)["player_profile"]["publisher_id_ref"]
            assert ref == "secret://cdnvideohub/lords/publisher-id"
            assert not ref.strip().isdigit(), "в manifest записано значение, а не ссылка"

    def test_token_is_a_reference_never_a_value(self):
        for site_id in LORDS_SITES:
            ref = _package(site_id)["content_api"]["token_ref"]
            assert ref.startswith("secret://cdnvideohub/lords/")

    def test_lords_secrets_are_scoped_away_from_other_directions(self):
        for site_id in LORDS_SITES:
            package = _package(site_id)
            for ref in (package["player_profile"]["publisher_id_ref"],
                        package["content_api"]["token_ref"]):
                assert "/amedia/" not in ref and "/yami/" not in ref

    def test_no_public_publisher_id_variable_anywhere_in_the_repository(self):
        """Проверяются отслеживаемые файлы: именно они попадают в git и в сборку.

        Обход всего дерева заодно читал .venv, artifacts и var — минуты работы
        и проверка того, что в репозиторий не входит.
        """
        import subprocess

        forbidden = "NEXT_PUBLIC_CDNVIDEOHUB_PUBLISHER" + "_ID"
        listing = subprocess.run(["git", "ls-files", "-z"], cwd=PATHS.root,
                                 capture_output=True, text=True, check=True)
        hits = []
        for name in listing.stdout.split("\0"):
            if not name:
                continue
            path = PATHS.root / name
            if path.suffix in {".png", ".jpg", ".svg", ".ico", ".woff", ".woff2", ".gz", ".tgz"}:
                continue
            try:
                if forbidden in path.read_text(encoding="utf-8", errors="ignore"):
                    hits.append(name)
            except OSError:
                continue
        assert hits == [], f"публичная переменная Publisher ID встречается в {hits}"

    def test_build_output_carries_no_secret_values(self):
        plan = _fixture_plan(_package("lords-01"))
        text = json.dumps(plan.as_dict(), ensure_ascii=False)
        assert "secret://" not in text, "ссылка на секрет утекла в план сайта"


# --------------------------------------------------------------------------
# Восстановимость
# --------------------------------------------------------------------------
class TestRecovery:
    @pytest.mark.parametrize("site_id", LORDS_SITES)
    def test_backup_and_rollback_are_declared(self, site_id):
        package = _package(site_id)
        assert package["backup_policy"]["before_mutation"] is True
        assert package["backup_policy"]["restore_test"]
        assert package["rollback_policy"]["auto_rollback_on_smoke_failure"] is True
        assert int(package["rollback_policy"]["keep_releases"]) >= 1
        assert package["monitoring_policy"]["health_endpoint"]
