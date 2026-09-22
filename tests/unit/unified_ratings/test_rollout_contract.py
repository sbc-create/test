"""Раскатка по площадкам: реестр решает, кто получает оценки.

Проверяется не «код запускается», а три обещания контракта: неизвестная
площадка не публикуется молча, неавторизованная не публикуется даже по
прямому указанию, а умолчания показа выключены.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

from factory.unified_ratings.site_projection import build_flags
from factory.unified_ratings.titles import TitleRegistry

REPO = Path(__file__).resolve().parents[3]
REGISTRY_PATH = REPO / "config" / "unified-ratings-tenants.json"


def _load_tool():
    spec = importlib.util.spec_from_file_location(
        "ur_publish", REPO / "tools" / "unified_ratings_publish.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class _Args:
    def __init__(self, **kw):
        self.public_read = kw.get("public_read", False)
        self.public_write = kw.get("public_write", False)
        self.kill_switch = kw.get("kill_switch", False)
        self.dry_run = kw.get("dry_run", False)


def test_registry_is_valid_json_and_declares_every_field():
    data = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
    assert data["schema"] == "unified.ratings.tenants/1.0.0"
    for tenant_id, spec in data["tenants"].items():
        for field in ("space", "family", "details", "provider", "projection", "flags",
                      "authorized", "stage"):
            assert field in spec, f"{tenant_id}: нет поля {field}"
        if not spec["authorized"]:
            assert spec.get("blocker"), f"{tenant_id}: неавторизован без причины"


def test_only_animedia_icu_is_authorized():
    """Разрешение живёт в реестре. Второй домен туда не попадает сам."""
    data = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
    authorized = {t for t, s in data["tenants"].items() if s["authorized"]}
    assert authorized == {"animedia-01"}
    assert data["tenants"]["animedia-02"]["domain"] == "animedia.space"
    assert data["tenants"]["animedia-02"]["authorized"] is False


def test_unauthorized_tenant_is_refused_not_published(store, tmp_path):
    tool = _load_tool()
    spec = {
        "space": "other", "details": str(tmp_path / "nope.json"), "provider": "nova",
        "projection": str(tmp_path / "p.json"), "flags": str(tmp_path / "f.json"),
        "authorized": False, "blocker": "домен вне задания",
    }
    out = tool.publish("other-01", spec, store, _Args())
    assert out["status"] == "BLOCKED_AUTHORIZATION"
    assert not (tmp_path / "p.json").exists()
    assert not (tmp_path / "f.json").exists()


def test_authorized_tenant_without_details_is_blocked_input(store, tmp_path):
    tool = _load_tool()
    spec = {
        "space": "other", "details": str(tmp_path / "missing.json"), "provider": "nova",
        "projection": str(tmp_path / "p.json"), "flags": str(tmp_path / "f.json"),
        "authorized": True,
    }
    out = tool.publish("other-01", spec, store, _Args())
    assert out["status"] == "BLOCKED_INPUT"
    assert not (tmp_path / "p.json").exists()


def test_publish_is_tenant_agnostic(store, registry: TitleRegistry, sample_titles, tmp_path):
    """Модуль не знает названий витрин: новая площадка — запись в реестре."""
    registry.upsert_many(sample_titles)
    details = tmp_path / "details.json"
    details.write_text(
        json.dumps({"details": {"a": {"id": "t-001"}, "b": {"id": "t-002"}}}),
        encoding="utf-8",
    )
    tool = _load_tool()
    spec = {
        "space": "brandnew", "details": str(details), "provider": "nova",
        "projection": str(tmp_path / "p.json"), "flags": str(tmp_path / "f.json"),
        "authorized": True,
    }
    out = tool.publish("brandnew-01", spec, store, _Args())
    assert out["status"] == "PUBLISHED"
    flags = json.loads((tmp_path / "f.json").read_text(encoding="utf-8"))
    assert flags["space"] == "brandnew"
    assert flags["RATINGS_PUBLIC_READ_BRANDNEW"] == 0
    assert flags["RATINGS_PUBLIC_WRITE_BRANDNEW"] == 0


@pytest.mark.parametrize("space", ["animedia", "brandnew", "zona"])
def test_rollout_defaults_are_off_for_any_space(space):
    flags = build_flags(space=space, cohort=set(), public_read=False, public_write=False)
    assert flags[f"RATINGS_PUBLIC_READ_{space.upper()}"] == 0
    assert flags[f"RATINGS_PUBLIC_WRITE_{space.upper()}"] == 0
    assert flags["PUBLIC_WRITE_ROLLOUT_PERCENT"] == 0
    assert flags["allowlist"][space] == []
    assert flags["owner_test_access_only"] is True


def test_readiness_names_the_blocker_instead_of_a_blank(store, tmp_path):
    tool = _load_tool()
    row = tool.readiness(
        "ghost-01",
        {"space": "ghost", "details": "", "provider": "nova", "authorized": False,
         "stage": "NOT_AUTHORIZED"},
        store,
    )
    assert row["details_present"] is False
    assert row["coverage_percent"] is None
    assert row["blocker"]
