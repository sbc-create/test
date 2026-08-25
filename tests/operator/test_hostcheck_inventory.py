"""Проверка целевого хоста (BLOCKED_WRONG_HOST) и сборка инвентаря из нескольких источников."""
import json
from pathlib import Path

import pytest
import yaml

from seo_operator import hostcheck
from seo_operator import inventory as rec


# ============================ Host check ============================

def test_wrong_hostname_blocks():
    check = hostcheck.HostCheck(
        expected=hostcheck.EXPECTED_HOST, actual_hostname="vm",
        actual_ipv4=["192.0.2.2"], repo_path_exists=False,
        mismatches=["hostname mismatch"])
    assert not check.passed
    assert check.status == "BLOCKED_WRONG_HOST"


def test_matching_host_passes():
    check = hostcheck.HostCheck(
        expected=hostcheck.EXPECTED_HOST, actual_hostname="claude-control-01",
        actual_ipv4=["45.131.182.225"], repo_path_exists=True)
    assert check.passed and check.status == "pass"


def test_check_on_this_container_detects_mismatch():
    """Фактический прогон в текущем окружении: он обязан провалиться."""
    check = hostcheck.check(hostcheck.EXPECTED_HOST)
    assert not check.passed
    assert any("hostname" in m for m in check.mismatches)
    assert any("/srv/site-factory/repo" in m for m in check.mismatches)


def test_render_names_all_three_mismatches():
    check = hostcheck.check(hostcheck.EXPECTED_HOST)
    text = check.render()
    assert "BLOCKED_WRONG_HOST" in text
    assert "claude-control-01" in text and "45.131.182.225" in text


@pytest.mark.parametrize("addresses,ephemeral", [
    (["192.0.2.2", "127.0.0.1"], True),
    (["10.0.0.5"], True),
    (["45.131.182.225"], False),
    ([], True),
])
def test_ephemeral_addressing_detection(addresses, ephemeral):
    assert hostcheck.looks_like_ephemeral(addresses) is ephemeral


def test_hostname_is_read_from_proc():
    assert hostcheck.read_hostname()


def test_expected_host_matches_spec():
    assert hostcheck.EXPECTED_HOST.hostname == "claude-control-01"
    assert hostcheck.EXPECTED_HOST.ipv4 == "45.131.182.225"
    assert hostcheck.EXPECTED_HOST.repo_path == "/srv/site-factory/repo"


# ============================ Inventory ============================

YAMI = ["yummyani.site", "yummyani.org", "yummyani.biz"]
LORDS = ["lordserial33.biz", "lordfilm47.space", "1lordserials1.online"]


@pytest.fixture()
def repo(tmp_path: Path) -> Path:
    """Воспроизводит фактическую структуру источников из main."""
    (tmp_path / "config" / "directions").mkdir(parents=True)
    (tmp_path / "inventory").mkdir()

    # portfolio.json пуст — как в main на 2026-08-24.
    (tmp_path / "config" / "portfolio.json").write_text(
        json.dumps({"version": 1, "sites": []}), encoding="utf-8")

    (tmp_path / "config" / "analytics.json").write_text(json.dumps({
        "version": 1, "seo_indexing_enabled": False,
        "properties": [
            {"domain": d, "counter_id": cid, "counter_state": "reused",
             "analytics_enabled": True, "webvisor": False,
             "webmaster": {"enabled": True, "host_id": None,
                           "verification_status": "BLOCKED_DEPLOYMENT"},
             "seo_indexing_enabled": False}
            for d, cid in zip(YAMI, [111881037, 111881038, 111881039])]
    }), encoding="utf-8")

    (tmp_path / "config" / "directions" / "lords.json").write_text(json.dumps({
        "version": 1, "direction": "lords", "status": "dns_verified_not_launched",
        "mapping_status": "proposed_only",
        "domains": [{"apex": d, "a_apex": "45.131.182.225",
                     "proposed_profile": f"lords-0{i+1}", "launched": False}
                    for i, d in enumerate(LORDS)]
    }), encoding="utf-8")

    (tmp_path / "config" / "secret-hub.json").write_text(json.dumps({
        "version": 1, "store_dir": "/var/lib/site-factory-secret-hub",
        "provider": {"name": "cdnvideohub"},
        "portfolios": [{"id": "yami", "enabled": True,
                        "consumers": [{"id": "yami-staging-compose"}]}]
    }), encoding="utf-8")

    (tmp_path / "inventory" / "targets.yaml").write_text(yaml.safe_dump({
        "schema_version": 1,
        "targets": [{"ref": "local-disposable", "production_capable": False},
                    {"ref": "payload-local", "production_capable": False}]
    }), encoding="utf-8")
    return tmp_path


def test_all_six_domains_discovered(repo):
    inv, _ = rec.build(repo_root=repo, host_available=False)
    assert inv.total == 6
    assert set(inv.domains) == set(YAMI) | set(LORDS)


def test_single_registry_would_have_reported_zero(repo):
    """Именно из-за чтения одного файла предыдущий аудит дал неверный итог."""
    inv = rec.Inventory()
    rec.read_portfolio_registry(repo / "config" / "portfolio.json", inv)
    assert inv.total == 0, "portfolio.json действительно пуст — но это не весь портфель"


def test_yami_counters_are_discovered_from_analytics(repo):
    inv, _ = rec.build(repo_root=repo, host_available=False)
    assert inv.domains["yummyani.site"].value("metrika_counter_id") == 111881037
    assert inv.domains["yummyani.org"].value("metrika_counter_id") == 111881038
    assert inv.domains["yummyani.biz"].value("metrika_counter_id") == 111881039


def test_lords_have_no_counters(repo):
    inv, _ = rec.build(repo_root=repo, host_available=False)
    for d in LORDS:
        assert inv.domains[d].value("metrika_counter_id") is None


def test_webvisor_is_off_for_all_yami(repo):
    inv, _ = rec.build(repo_root=repo, host_available=False)
    assert all(inv.domains[d].value("webvisor") is False for d in YAMI)


def test_indexing_disabled_everywhere(repo):
    inv, _ = rec.build(repo_root=repo, host_available=False)
    assert all(inv.domains[d].value("indexing_enabled") is False for d in YAMI)


def test_webmaster_hosts_not_added(repo):
    inv, _ = rec.build(repo_root=repo, host_available=False)
    for d in YAMI:
        assert inv.domains[d].value("webmaster_host_id") is None
        assert inv.domains[d].value("webmaster_verification_status") == "BLOCKED_DEPLOYMENT"


def test_orphan_drift_reported_for_every_domain(repo):
    """Каждый домен известен ровно одному источнику — это шесть ORPHAN."""
    inv, _ = rec.build(repo_root=repo, host_available=False)
    orphans = [d for d in inv.drift if d.kind is rec.DriftKind.ORPHAN]
    assert len(orphans) == 6
    assert all(d.domain in set(YAMI) | set(LORDS) for d in orphans)


def test_unreachable_host_sources_are_distinguished_from_empty(repo):
    """«Источник не читался» и «в источнике пусто» — разные утверждения."""
    inv, _ = rec.build(repo_root=repo, host_available=False,
                       host_unavailable_reason="BLOCKED_WRONG_HOST")
    unreachable = [d for d in inv.drift if d.kind is rec.DriftKind.UNREACHABLE_SOURCE]
    kinds = {s for d in unreachable for s in d.sources}
    assert {"nginx", "systemd", "deployment_manifest", "live_https"} <= kinds
    assert all(d.blocking for d in unreachable)


def test_host_sources_not_flagged_when_host_available(repo):
    inv, _ = rec.build(repo_root=repo, host_available=True)
    unreachable = [d for d in inv.drift if d.kind is rec.DriftKind.UNREACHABLE_SOURCE
                   and set(d.sources) & {"nginx", "systemd", "live_https"}]
    assert not unreachable


def test_field_conflict_is_detected_and_blocking():
    inv = rec.Inventory()
    inv.add_facts("x.example", [
        rec.Fact("metrika_counter_id", 1, rec.SourceKind.ANALYTICS_REGISTRY, "a.json"),
        rec.Fact("metrika_counter_id", 2, rec.SourceKind.PORTFOLIO_REGISTRY, "b.json"),
    ])
    drift = inv.detect_drift()
    conflicts = [d for d in drift if d.kind is rec.DriftKind.FIELD_CONFLICT]
    assert len(conflicts) == 1 and conflicts[0].blocking
    assert inv.domains["x.example"].value("metrika_counter_id") is rec.CONFLICT


def test_explicit_null_is_not_a_conflict(repo):
    """webmaster_host_id=None — это факт «хост не подтверждён», а не расхождение."""
    inv, _ = rec.build(repo_root=repo, host_available=False)
    rendered = inv.domains["yummyani.site"].render_field("webmaster_host_id")
    assert rendered.startswith("null ")
    assert "CONFLICT" not in rendered
    assert inv.domains["yummyani.site"].value("webmaster_host_id") is None


def test_conflicting_field_renders_both_sources():
    inv = rec.Inventory()
    inv.add_facts("x.example", [
        rec.Fact("environment", "staging", rec.SourceKind.ANALYTICS_REGISTRY, "a.json"),
        rec.Fact("environment", "production", rec.SourceKind.NGINX, "/etc/nginx/x.conf"),
    ])
    rendered = inv.domains["x.example"].render_field("environment")
    assert rendered.startswith("CONFLICT:")
    assert "staging" in rendered and "production" in rendered


def test_absent_field_is_not_measured_not_empty(repo):
    inv, _ = rec.build(repo_root=repo, host_available=False)
    assert inv.domains["yummyani.site"].render_field("live_url") == "NOT_MEASURED"


def test_no_production_target_is_a_fact_from_targets(repo):
    _, extra = rec.build(repo_root=repo, host_available=False)
    assert extra["targets"]["has_production_target"] is False
    assert extra["targets"]["total"] == 2


def test_secret_hub_status_carries_no_values(repo):
    _, extra = rec.build(repo_root=repo, host_available=False)
    blob = json.dumps(extra["secret_hub"])
    for forbidden in ("api_token", "publisher_id", "fingerprint", "value"):
        assert forbidden not in blob
    assert extra["secret_hub"]["portfolios"][0]["id"] == "yami"


def test_portfolios_are_separable(repo):
    inv, _ = rec.build(repo_root=repo, host_available=False)
    assert len(inv.by_portfolio("lords")) == 3


def test_table_lists_every_required_field(repo):
    inv, _ = rec.build(repo_root=repo, host_available=False)
    table = rec.render_table(inv)
    for label in ("portfolio", "профиль", "repository", "deployment target", "environment",
                  "HTTPS", "Metrika counter", "Webmaster host", "indexing",
                  "analytics data", "content", "фактический URL"):
        assert label in table
    for d in YAMI + LORDS:
        assert d in table


def test_missing_source_file_is_recorded_not_silently_skipped(tmp_path):
    inv, _ = rec.build(repo_root=tmp_path, host_available=True)
    assert rec.SourceKind.PORTFOLIO_REGISTRY in inv.sources_unavailable
    assert rec.SourceKind.ANALYTICS_REGISTRY in inv.sources_unavailable
    assert any(d.kind is rec.DriftKind.UNREACHABLE_SOURCE for d in inv.drift)
