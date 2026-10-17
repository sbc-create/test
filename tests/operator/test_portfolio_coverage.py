"""Сверка направлений Secret Hub с доменами реестров (INVENTORY_DRIFT)."""
import json
from pathlib import Path

import pytest
import yaml

from seo_operator import inventory as rec


def _write(root: Path, *, portfolio_sites=None, analytics_domains=(),
           directions=None, hub_portfolios=()) -> Path:
    (root / "config" / "directions").mkdir(parents=True, exist_ok=True)
    (root / "inventory").mkdir(exist_ok=True)

    (root / "config" / "portfolio.json").write_text(
        json.dumps({"version": 1, "sites": portfolio_sites or []}), encoding="utf-8")

    (root / "config" / "analytics.json").write_text(json.dumps({
        "version": 1, "seo_indexing_enabled": False,
        "properties": [{"domain": d, "counter_id": 100 + i, "webvisor": False,
                        "webmaster": {"host_id": None,
                                      "verification_status": "BLOCKED_DEPLOYMENT"}}
                       for i, d in enumerate(analytics_domains)]}), encoding="utf-8")

    if directions:
        (root / "config" / "directions" / "d.json").write_text(
            json.dumps(directions), encoding="utf-8")

    (root / "config" / "secret-hub.json").write_text(json.dumps({
        "version": 1, "provider": {"name": "cdnvideohub"},
        "portfolios": list(hub_portfolios)}), encoding="utf-8")

    (root / "inventory" / "targets.yaml").write_text(
        yaml.safe_dump({"schema_version": 1, "targets": []}), encoding="utf-8")
    return root


def test_unattributed_domains_are_reported_separately(tmp_path):
    """
    Домены есть, но поля portfolio нет ни в одном реестре — это дефект
    атрибуции, а не отсутствие доменов. Формулировки не должны смешиваться.
    """
    _write(tmp_path, analytics_domains=["a.example", "b.example"],
           hub_portfolios=[{"id": "yami", "enabled": True, "consumers": [{"id": "c"}]}])
    inv, _ = rec.build(repo_root=tmp_path, host_available=True)

    attribution = [d for d in inv.drift if "не имеют поля portfolio" in d.detail]
    assert len(attribution) == 1
    assert "a.example" in attribution[0].detail

    hub = [d for d in inv.drift if "объявлено в Secret Hub" in d.detail]
    assert len(hub) == 1
    assert "а не из-за отсутствия доменов" in hub[0].detail


def test_truly_missing_direction_is_named_plainly(tmp_path):
    """Когда атрибуция есть, а направления нет — формулировка прямая."""
    _write(tmp_path,
           directions={"direction": "lords", "mapping_status": "proposed_only",
                       "domains": [{"apex": "l.example", "launched": False}]},
           hub_portfolios=[{"id": "lords", "enabled": True, "consumers": []},
                           {"id": "amedia", "enabled": True, "consumers": []}])
    inv, _ = rec.build(repo_root=tmp_path, host_available=True)

    hub = [d for d in inv.drift if "объявлено в Secret Hub" in d.detail]
    assert len(hub) == 1, "направление lords имеет домен и флагом быть не должно"
    assert "amedia" in hub[0].detail
    assert "но ни одного его домена нет" in hub[0].detail


def test_disabled_hub_portfolio_is_not_flagged(tmp_path):
    _write(tmp_path, hub_portfolios=[{"id": "old", "enabled": False, "consumers": []}])
    inv, _ = rec.build(repo_root=tmp_path, host_available=True)
    assert not [d for d in inv.drift if "'old'" in d.detail]


def test_matching_portfolio_produces_no_coverage_drift(tmp_path):
    _write(tmp_path,
           directions={"direction": "lords", "domains": [{"apex": "l.example"}]},
           hub_portfolios=[{"id": "lords", "enabled": True, "consumers": []}])
    inv, _ = rec.build(repo_root=tmp_path, host_available=True)
    assert not [d for d in inv.drift if "объявлено в Secret Hub" in d.detail]
    assert not [d for d in inv.drift if "не имеют поля portfolio" in d.detail]


def test_secret_hub_source_never_carries_values(tmp_path):
    _write(tmp_path, hub_portfolios=[{"id": "yami", "enabled": True,
                                      "consumers": [{"id": "c1"}]}])
    _, extra = rec.build(repo_root=tmp_path, host_available=True)
    blob = json.dumps(extra["secret_hub"])
    for forbidden in ("api_token", "publisher_id", "fingerprint", "secret", "value"):
        assert forbidden not in blob
