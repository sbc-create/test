"""Мост к пакетам фабрики: оператор видит сайты, но не выдумывает инвентарь.

Проверяется главное свойство: сайт становится доступен для работы с живыми
данными только когда переданы домен, права и авторизация production. Пока хоть
одно условие не выполнено, сайт виден, но заблокирован.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

from seo_operator.factory_bridge import (
    BLOCKED_DOMAIN_TARGET,
    BLOCKED_RIGHTS,
    READY,
    discover_packages,
    live_allowed,
    portfolio_view,
    readiness,
    to_portfolio_entry,
)

REPO_ROOT = Path(__file__).resolve().parents[2]


def _package(**overrides):
    base = {
        "site_id": "site-example",
        "domain": "example.test",
        "canonical_url": "https://example.test/",
        "fixture": False,
        "production_authorized": True,
        "brand": {"name": "site_example", "legal_name": None},
        "tenant": {"seo_profile": "catalog_authority", "owned_listings": ["/catalog/"]},
        "comments": {"premoderation": True},
        "content_source": {"rights_confirmed": True},
    }
    base.update(overrides)
    return base


class TestReadiness:
    def test_fully_supplied_site_is_ready(self):
        assert readiness(_package()) == READY

    def test_stand_domain_is_not_inventory(self):
        assert readiness(_package(domain="site-a.localhost")) == BLOCKED_DOMAIN_TARGET
        assert readiness(_package(domain="127.0.0.1")) == BLOCKED_DOMAIN_TARGET

    def test_missing_domain_blocks(self):
        assert readiness(_package(domain="")) == BLOCKED_DOMAIN_TARGET

    def test_fixture_package_is_never_live(self):
        """Фикстура остаётся фикстурой, даже если домен выглядит настоящим."""
        assert readiness(_package(fixture=True)) == BLOCKED_DOMAIN_TARGET

    def test_production_authorization_is_required(self):
        assert readiness(_package(production_authorized=False)) == BLOCKED_DOMAIN_TARGET

    def test_unconfirmed_rights_block_before_anything_else(self):
        """Права проверяются первыми: без них домен и авторизация не важны."""
        package = _package(content_source={"rights_confirmed": False})
        assert readiness(package) == BLOCKED_RIGHTS


class TestPortfolioEntry:
    def test_entry_matches_registry_schema(self):
        schema = json.loads(
            (REPO_ROOT / "schemas" / "portfolio-registry.schema.json").read_text(encoding="utf-8")
        )
        item_schema = schema["properties"]["sites"]["items"]
        entry = to_portfolio_entry(_package())
        for field in item_schema["required"]:
            assert field in entry, f"нет обязательного поля {field}"
        assert entry["risk_tier"] in item_schema["properties"]["risk_tier"]["enum"]
        assert entry["editorial_account"] in item_schema["properties"]["editorial_account"]["enum"]

    def test_public_name_is_not_invented(self):
        """Пока бренд не передан, показывается внутренний код сайта."""
        entry = to_portfolio_entry(_package(brand={"name": "site_d", "legal_name": None}))
        assert entry["name"] == "site_d"

    def test_stand_site_is_low_risk_and_synthetic(self):
        entry = to_portfolio_entry(_package(fixture=True, domain="site-a.localhost"))
        assert entry["risk_tier"] == "low"
        assert entry["synthetic"] is True

    def test_editorial_account_is_never_assigned_automatically(self):
        """Автоматический ответ невозможен, пока владелец не назначит аккаунт."""
        assert to_portfolio_entry(_package())["editorial_account"] is None


class TestPortfolioView:
    def test_view_reads_the_real_factory_packages(self):
        view = portfolio_view(REPO_ROOT)
        assert view["counts"]["total"] >= 1, "пакеты сайтов фабрики не найдены"
        ids = {site["site_id"] for site in view["sites"]}
        assert "pilot-local" in ids or any(i.startswith("site-") for i in ids)

    def test_every_factory_package_is_visible(self):
        """Оператор обязан видеть все пакеты, а не выборочные."""
        view = portfolio_view(REPO_ROOT)
        on_disk = {
            yaml.safe_load(p.read_text(encoding="utf-8"))["site_id"]
            for p in (REPO_ROOT / "sites").glob("*/package.yaml")
        }
        assert {site["site_id"] for site in view["sites"]} == on_disk

    def test_stand_sites_are_not_live_allowed(self):
        """Ни один стендовый сайт не попадает в список для живой работы."""
        assert live_allowed(REPO_ROOT) == []

    def test_view_does_not_touch_the_owner_registry(self):
        """Реальный реестр заполняет владелец: представление его не меняет."""
        registry = REPO_ROOT / "config" / "portfolio.json"
        before = registry.read_text(encoding="utf-8")
        portfolio_view(REPO_ROOT)
        assert registry.read_text(encoding="utf-8") == before


class TestDiscovery:
    def test_broken_package_is_reported_not_skipped(self, tmp_path):
        sites = tmp_path / "sites" / "broken"
        sites.mkdir(parents=True)
        (sites / "package.yaml").write_text("site_id: [unclosed\n", encoding="utf-8")
        with pytest.raises(ValueError):
            discover_packages(tmp_path)

    def test_missing_sites_directory_is_empty_not_an_error(self, tmp_path):
        assert discover_packages(tmp_path) == []
