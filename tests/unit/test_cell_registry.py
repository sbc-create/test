"""Реестр ячеек: задача попадает в нужный проект или никуда.

Доказывает: REQ-CELL-ROUTING, REQ-CELL-PUBID.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from factory.cell import registry
from factory.cell.registry import (
    AmbiguousCell,
    Cell,
    RegistryError,
    RetiredPublisherId,
    UnknownCell,
)


def _cell(site_id: str, domain: str, **kw) -> Cell:
    base = {
        "site_id": site_id, "domain": domain, "aliases": (),
        "repo": {"kind": "local", "path": f"var/site-repos/{site_id}"},
        "template": {"template_id": "lords-general", "order_id": "o-1"},
        "pins": {"common_core": "abc123", "template": "1.0"},
        "deploy_target": {"ref": "local-disposable", "server": None},
        "publisher": {"provider": "cdnvideohub", "publisher_id_ref": "secret://x"},
        "data": {"database": "data/site.sqlite3"},
    }
    base.update(kw)
    return Cell(**base)


@pytest.fixture()
def reg(tmp_path: Path) -> Path:
    return tmp_path / "site-cells.json"


def test_resolves_by_site_id_and_by_domain(reg: Path):
    registry.register(_cell("alpha", "alpha.test"), path=reg)
    assert registry.resolve("alpha", path=reg).site_id == "alpha"
    assert registry.resolve("alpha.test", path=reg).site_id == "alpha"


def test_alias_resolves_to_the_same_cell(reg: Path):
    registry.register(_cell("alpha", "alpha.test", aliases=("www.alpha.test",)), path=reg)
    assert registry.resolve("www.alpha.test", path=reg).site_id == "alpha"


def test_unknown_name_is_refused_and_never_guessed(reg: Path):
    registry.register(_cell("animedia-01", "animedia.icu"), path=reg)
    registry.register(_cell("animedia-02", "animedia.space"), path=reg)
    with pytest.raises(UnknownCell) as exc:
        registry.resolve("animedia", path=reg)
    # Похожие названы, но выбор не сделан: угадывать сайт нельзя.
    assert "animedia-01" in str(exc.value)
    assert "animedia-02" in str(exc.value)


def test_ambiguity_stops_instead_of_picking_the_first(reg: Path, tmp_path: Path):
    import json
    reg.write_text(json.dumps({"schema_version": "1.0", "cells": [
        _cell("one", "shared.test").to_dict(),
        _cell("two", "other.test", aliases=("shared.test",)).to_dict(),
    ]}, ensure_ascii=False), encoding="utf-8")
    with pytest.raises(AmbiguousCell):
        registry.resolve("shared.test", path=reg)


def test_one_domain_belongs_to_exactly_one_cell(reg: Path):
    registry.register(_cell("alpha", "alpha.test"), path=reg)
    with pytest.raises(RegistryError, match="один домен — один сайт"):
        registry.register(_cell("beta", "alpha.test"), path=reg)


def test_alias_cannot_steal_another_cells_domain(reg: Path):
    registry.register(_cell("alpha", "alpha.test"), path=reg)
    with pytest.raises(RegistryError, match="один домен — один сайт"):
        registry.register(_cell("beta", "beta.test", aliases=("alpha.test",)), path=reg)


def test_re_registering_requires_explicit_replace(reg: Path):
    registry.register(_cell("alpha", "alpha.test"), path=reg)
    with pytest.raises(RegistryError, match="уже зарегистрирована"):
        registry.register(_cell("alpha", "alpha.test"), path=reg)
    registry.register(_cell("alpha", "alpha.test"), path=reg, replace=True)


@pytest.mark.parametrize("retired", ["10331", "10332", "10333"])
def test_retired_publisher_id_is_refused(reg: Path, retired: str):
    with pytest.raises(RetiredPublisherId):
        registry.register(
            _cell("alpha", "alpha.test",
                  publisher={"provider": "cdnvideohub", "publisher_id": retired}),
            path=reg)


@pytest.mark.parametrize("allowed", ["10252", "10238"])
def test_named_publisher_ids_pass(reg: Path, allowed: str):
    cell = _cell("alpha", "alpha.test",
                 publisher={"provider": "cdnvideohub", "publisher_id": allowed})
    registry.register(cell, path=reg)
    assert registry.resolve("alpha", path=reg).publisher["publisher_id"] == allowed


def test_empty_publisher_id_is_blocked_not_defaulted():
    with pytest.raises(RegistryError, match="подставлять значение"):
        registry.check_publisher_id("")


def test_route_gives_the_executor_exactly_the_destination(reg: Path):
    registry.register(_cell("alpha", "alpha.test"), path=reg)
    r = registry.route("alpha.test", path=reg)
    assert r["site_id"] == "alpha"
    assert r["repo"] == "var/site-repos/alpha"
    assert r["template_id"] == "lords-general"
    assert r["deploy_target"] == "local-disposable"


def test_update_touches_only_named_fields(reg: Path):
    registry.register(_cell("alpha", "alpha.test"), path=reg)
    updated = registry.update("alpha", {"deployed": {"release_digest": "sha256:aa"}}, path=reg)
    assert updated.deployed["release_digest"] == "sha256:aa"
    assert updated.template["template_id"] == "lords-general"
    with pytest.raises(RegistryError, match="не обновляются"):
        registry.update("alpha", {"site_id": "beta"}, path=reg)


def test_update_of_missing_cell_is_an_error_not_a_create(reg: Path):
    with pytest.raises(UnknownCell):
        registry.update("ghost", {"status": "live"}, path=reg)
