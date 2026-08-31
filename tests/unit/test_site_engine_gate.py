"""Архитектурный гейт обязан ловить именно то, что уже ломалось.

Каждый отрицательный случай ниже — не выдумка: это поломка, которая в этом
проекте уже случалась, и тест существует, чтобы она не повторилась на
следующем сайте.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from factory.site_engine import gate

ROOT = Path(__file__).resolve().parents[2]


def valid_profile() -> dict:
    """Настоящий профиль действующего сайта, а не выдуманный минимум."""
    return json.loads((ROOT / "config/site-profiles/lords-01.json").read_text(encoding="utf-8"))


class TestSixLiveProfiles:
    def test_every_live_profile_passes(self):
        ok, results, core = gate.run(ROOT)
        failed = {r.site_id: r.problems for r in results if not r.passed}
        assert failed == {}, failed
        assert core == []
        assert ok

    #: Домены, которые действительно отвечают в интернете.
    LIVE_DOMAINS = {
        "yummyani.site", "yummyani.org", "yummyani.biz",
        "lordfilm47.space", "lordserial33.biz", "1lordserials1.online",
    }

    def test_all_six_sites_have_a_profile(self):
        """Ни один действующий сайт не остался без профиля.

        Прежде проверка требовала ровно шести профилей. Это оказалось не тем
        свойством: появление профиля нового рода сайта (`demo-books`) ничего не
        говорит о шести действующих, а проверка падала. Считается теперь
        именно то, ради чего она писалась.
        """
        _, results, _ = gate.run(ROOT)
        assert {
            "yummyani-site", "yummyani-org", "yummyani-biz",
            "lords-01", "lords-02", "lords-03",
        } <= {r.site_id for r in results}

    def test_no_extra_profile_claims_a_live_domain(self):
        """Зубы прежней проверки сохранены: лишний профиль не заберёт домен.

        Пересечения доменов гейт запрещает и сам, но здесь проверяется другое —
        что демонстрационный профиль не притворяется действующим сайтом.
        """
        живые = {"yummyani-site", "yummyani-org", "yummyani-biz",
                 "lords-01", "lords-02", "lords-03"}
        for path in sorted((ROOT / "config/site-profiles").glob("*.json")):
            profile = json.loads(path.read_text(encoding="utf-8"))
            if profile["site_id"] in живые:
                continue
            assert not (set(profile["domains"]) & self.LIVE_DOMAINS), (
                f"{profile['site_id']} заявляет домен действующего сайта"
            )


class TestNewSiteType:
    def test_a_site_of_an_unknown_type_is_accepted(self):
        """Движок обязан принять новый род сайта без правки ядра.

        Если бы ядро знало про аниме и видеовитрины поимённо, каждый следующий
        проект начинался бы с правки общего кода.
        """
        profile = valid_profile()
        profile["site_id"] = "recipes-demo"
        profile["site_type"] = "recipe-catalog"
        profile["domains"] = ["recipes.example"]
        profile["content_directions"] = ["dessert", "main-course"]
        profile["content_providers"] = [
            {"adapter": "example-recipes-v1", "role": "primary", "credentials_ref": "example_api_token"}
        ]
        assert gate.check_profile(profile, ROOT).passed


class TestDeliberatelyBrokenProfiles:
    def test_missing_schema_version_is_refused(self):
        profile = valid_profile()
        del profile["schema_version"]
        result = gate.check_profile(profile, ROOT)
        assert not result.passed
        assert any("schema_version" in p for p in result.problems)

    def test_a_secret_in_the_profile_is_refused(self):
        """Профиль лежит в git: секрет здесь — это утечка."""
        profile = valid_profile()
        profile["content_providers"][0]["api_token"] = "a" * 40
        result = gate.check_profile(profile, ROOT)
        assert not result.passed
        assert any("секрет" in p for p in result.problems)

    def test_credentials_ref_is_not_mistaken_for_a_secret(self):
        """Ссылка на секрет — не секрет. Иначе гейт запретил бы правильное."""
        assert gate.check_profile(valid_profile(), ROOT).passed

    def test_missing_cache_policy_is_refused(self):
        profile = valid_profile()
        profile["cache_policy"] = {"schema_version": "1.0", "layers": {}, "invalidation": {"mode": "ttl-only"}}
        result = gate.check_profile(profile, ROOT)
        assert not result.passed
        assert any("кэш" in p for p in result.problems)

    def test_missing_render_strategy_is_refused(self):
        profile = valid_profile()
        profile["render_strategy"] = {}
        assert not gate.check_profile(profile, ROOT).passed

    def test_no_health_endpoint_is_refused(self):
        profile = valid_profile()
        del profile["health_endpoint"]
        result = gate.check_profile(profile, ROOT)
        assert any("health" in p for p in result.problems)

    def test_no_coverage_endpoint_is_refused(self):
        """Неполный каталог однажды прожил полтора месяца незамеченным."""
        profile = valid_profile()
        del profile["coverage_endpoint"]
        result = gate.check_profile(profile, ROOT)
        assert any("coverage" in p for p in result.problems)

    def test_full_invalidation_on_one_event_is_refused(self):
        """Пересборка каталога ради одной серии — это часы вместо секунды."""
        profile = valid_profile()
        profile["cache_policy"]["invalidation"]["event_map"]["EPISODE_ADDED"] = ["*"]
        result = gate.check_profile(profile, ROOT)
        assert not result.passed
        assert any("весь кэш" in p for p in result.problems)

    def test_seo_without_ingestion_is_refused(self):
        """SEO не владеет каталогом и не ходит к поставщику."""
        profile = valid_profile()
        profile["enabled_modules"] = [m for m in profile["enabled_modules"] if m != "content-ingestion"]
        result = gate.check_profile(profile, ROOT)
        assert any("SEO" in p for p in result.problems)

    def test_ui_without_provider_adapter_is_refused(self):
        """Витрина, ходящая в API поставщика напрямую, — это сотни запросов
        на открытие главной."""
        profile = valid_profile()
        profile["enabled_modules"] = [m for m in profile["enabled_modules"] if m != "provider-adapters"]
        result = gate.check_profile(profile, ROOT)
        assert any("provider-adapters" in p for p in result.problems)

    def test_single_release_leaves_nowhere_to_roll_back(self):
        profile = valid_profile()
        profile["release_policy"]["keep_releases"] = 1
        result = gate.check_profile(profile, ROOT)
        assert not result.passed

    def test_no_owners_is_refused(self):
        profile = valid_profile()
        profile["owners"] = {}
        assert not gate.check_profile(profile, ROOT).passed


class TestSchemaVersioning:
    @pytest.mark.parametrize("name", ["site-profile", "content-event", "cache-policy"])
    def test_every_schema_declares_a_version_field(self, name):
        schema = json.loads((ROOT / f"schemas/site-engine/{name}.schema.json").read_text(encoding="utf-8"))
        assert "schema_version" in schema["properties"]
        assert "schema_version" in schema["required"]

    def test_core_contains_no_site_specific_words(self):
        assert gate.check_core_neutrality(ROOT, ("factory/site_engine",)) == []


class TestNormalizedContentCapability:
    """SEO нужен нормализованный контент, а не собственный загрузчик.

    Прежнее правило требовало у сайта с SEO модуль `content-ingestion` и тем
    самым запрещало правильную схему: витрину, которая берёт готовый
    нормализованный контент из общего Site Engine API и ничего не загружает
    сама. Требование — способность, а не конкретный модуль.
    """

    def test_local_ingestion_satisfies_the_requirement(self):
        profile = valid_profile()
        assert "content-ingestion" in profile["enabled_modules"]
        assert gate.check_profile(profile, ROOT).passed

    def test_shared_engine_api_satisfies_the_requirement(self):
        """Сайт без собственного загрузчика, берущий контент из общего API."""
        profile = valid_profile()
        profile["site_id"] = "shared-consumer"
        profile["enabled_modules"] = [
            m for m in profile["enabled_modules"] if m != "content-ingestion"
        ]
        profile["normalized_content_source"] = {"kind": "site-engine-api", "ref": "site-engine/v1"}
        result = gate.check_profile(profile, ROOT)
        assert result.passed, result.problems

    def test_registered_adapter_satisfies_the_requirement(self):
        profile = valid_profile()
        profile["site_id"] = "adapter-consumer"
        profile["enabled_modules"] = [
            m for m in profile["enabled_modules"] if m != "content-ingestion"
        ]
        profile["normalized_content_source"] = {"kind": "adapter", "ref": "partner-catalog-v2"}
        result = gate.check_profile(profile, ROOT)
        assert result.passed, result.problems

    def test_seo_without_any_source_is_still_refused(self):
        """Ни одного из трёх — SEO пришлось бы добывать содержимое самому."""
        profile = valid_profile()
        profile["site_id"] = "no-source"
        profile["enabled_modules"] = [
            m for m in profile["enabled_modules"] if m != "content-ingestion"
        ]
        result = gate.check_profile(profile, ROOT)
        assert not result.passed
        assert any("нормализованн" in p.lower() for p in result.problems)

    def test_a_source_without_a_reference_is_refused(self):
        """Объявить источник и не назвать его — то же, что не объявить."""
        profile = valid_profile()
        profile["enabled_modules"] = [
            m for m in profile["enabled_modules"] if m != "content-ingestion"
        ]
        profile["normalized_content_source"] = {"kind": "site-engine-api"}
        assert not gate.check_profile(profile, ROOT).passed

    def test_an_unknown_kind_of_source_is_refused(self):
        profile = valid_profile()
        profile["enabled_modules"] = [
            m for m in profile["enabled_modules"] if m != "content-ingestion"
        ]
        profile["normalized_content_source"] = {"kind": "scraping", "ref": "somewhere"}
        assert not gate.check_profile(profile, ROOT).passed

    def test_a_site_without_seo_needs_no_content_source(self):
        """Требование идёт от SEO. Витрина без него под него не подпадает."""
        profile = valid_profile()
        profile["site_id"] = "no-seo"
        profile["enabled_modules"] = [
            m for m in profile["enabled_modules"]
            if m not in ("seo", "content-ingestion")
        ]
        profile["seo_profile"]["enabled"] = False
        assert gate.check_profile(profile, ROOT).passed
