"""Отдельный репозиторий обязателен для каждого нового сайта.

Доказывает: REQ-CELL-OWNREPO.
"""
from __future__ import annotations

import pytest

from factory.cell import onboarding, registry, transfer
from factory.cell.onboarding import Order, StageBlocked
from factory.cell.registry import Cell, OwnRepositoryMissing


def _order(**kw) -> Order:
    base = {"order_id": "o-1", "site_id": "example-02", "domain": "example.space",
            "family": "animedia", "content_profile": "video-showcase",
            "deploy_target": "host-01"}
    base.update(kw)
    return Order(**base)


def _cell(site_id="example-02", domain="example.space", remote=None) -> Cell:
    return Cell(site_id=site_id, domain=domain, aliases=(),
                repo={"kind": "remote", "path": f"var/site-repos/{site_id}",
                      "remote": remote},
                template={"template_id": "t", "order_id": "o-1"},
                pins={"common_core": "abc"},
                deploy_target={"ref": "host-01", "server": None},
                publisher={"publisher_id": "10252"},
                data={})


# ------------------------------------------------------- имя репозитория
def test_repo_name_is_derived_from_domain_not_invented():
    a = onboarding.repo_name_for("example-02", "example.space")
    b = onboarding.repo_name_for("example-02", "example.space")
    assert a == b == "site-example-space"


def test_repo_name_is_stable_across_repeats():
    """Иначе повтор заказа завёл бы второй проект на тот же сайт."""
    имена = {onboarding.repo_name_for("s", "animedia.space") for _ in range(5)}
    assert len(имена) == 1


# --------------------------------------------------- идемпотентность
def test_existing_repository_is_reused_not_created_again():
    вызовы = []

    def runner(cmd):
        вызовы.append(cmd)
        if cmd[:2] == ["gh", "api"]:
            return 0, "sbc-create/site-example-space\ntrue\n"
        raise AssertionError("создание не должно вызываться: репозиторий есть")

    r = onboarding.create_repo_step(_order(), runner=runner)
    assert r["reused"] is True
    assert r["created"] is False
    assert not any(c[:3] == ["gh", "repo", "create"] for c in вызовы)


def test_missing_repository_is_created_once():
    вызовы = []

    def runner(cmd):
        вызовы.append(cmd)
        if cmd[:2] == ["gh", "api"]:
            return 1, "gh: Not Found"
        return 0, "https://github.com/sbc-create/site-example-space"

    r = onboarding.create_repo_step(_order(), runner=runner)
    assert r["created"] is True
    создания = [c for c in вызовы if c[:3] == ["gh", "repo", "create"]]
    assert len(создания) == 1
    assert "--private" in создания[0]


def test_public_repository_is_refused():
    def runner(cmd):
        if cmd[:2] == ["gh", "api"]:
            return 0, "sbc-create/site-example-space\nfalse\n"
        raise AssertionError("не должно дойти до создания")

    with pytest.raises(StageBlocked, match="не приватный"):
        onboarding.create_repo_step(_order(), runner=runner)


def test_failed_creation_is_blocked_not_swallowed():
    def runner(cmd):
        if cmd[:2] == ["gh", "api"]:
            return 1, "Not Found"
        return 1, "HTTP 403: quota exceeded"

    with pytest.raises(StageBlocked, match="монорепозитория"):
        onboarding.create_repo_step(_order(), runner=runner)


# ------------------------------------------- запрет выпуска из монорепо
def test_cell_without_own_repo_is_refused():
    with pytest.raises(OwnRepositoryMissing, match="repo.remote пуст"):
        registry.require_own_repo(_cell(remote=None))


@pytest.mark.parametrize("remote", [
    "https://github.com/sbc-create/test.git",
    "https://github.com/sbc-create/test",
    "git@github.com:sbc-create/site-factory",
])
def test_monorepo_remote_is_refused(remote):
    with pytest.raises(OwnRepositoryMissing, match="монорепозитор"):
        registry.require_own_repo(_cell(remote=remote))


def test_own_repo_is_accepted():
    assert registry.require_own_repo(
        _cell(remote="https://github.com/sbc-create/site-example-space"))


def test_install_refuses_a_site_absent_from_the_registry(tmp_path):
    """Сорвавшееся создание репозитория не должно кончиться публикацией."""
    layout = transfer.Layout(root=tmp_path / "host").ensure()
    artifact = tmp_path / "a.tar.gz"
    artifact.write_bytes(b"x")
    manifest = {"site_id": "no-such-site", "digest": "sha256:" + "0" * 64,
                "source_commit": "abc", "contains": {}}
    with pytest.raises(transfer.TransferError, match="реестре ячеек"):
        transfer.install(site_id="no-such-site", artifact=artifact,
                         manifest=manifest, layout=layout)


def test_onboarding_orders_repo_before_release():
    """Репозиторий заводится раньше сборки — иначе собирать неоткуда."""
    stages = list(onboarding.STAGES)
    assert stages.index("repo_created") < stages.index("release_ready")
    assert stages.index("repo_pushed") < stages.index("release_ready")
    assert stages.index("ci_verified") < stages.index("deployed")
    assert stages.index("deployed") < stages.index("publicly_accepted")


def test_stages_requiring_evidence_are_named():
    for stage in onboarding.STAGES_REQUIRING_EVIDENCE:
        assert stage in onboarding.STAGES
