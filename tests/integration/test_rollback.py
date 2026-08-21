"""REQ-ATOMIC: атомарные релизы и откат на предыдущий рабочий."""
import os

import pytest

from factory import build as build_mod, inventory
from factory.errors import DeployFailed
from factory.targets import build_target


@pytest.fixture
def target(pilot_package):
    return build_target(inventory.target(pilot_package["target_ref"]), pilot_package)


@pytest.mark.slow
def test_rollback_switches_to_previous_release(target):
    built = build_mod.build("pilot-local")
    target.deploy(built.output, built.build_id)
    current_before = target.current_release()
    previous = target._state().get("previous_release_id")
    if not previous:
        pytest.skip("на цели ещё нет предыдущего релиза")
    result = target.rollback()
    assert result.release_id == previous
    assert target.current_release() == previous
    assert target.current_release() != current_before
    ok, detail = target.health()
    assert ok, f"после отката сайт обязан отвечать: {detail}"
    # возвращаем цель в актуальное состояние
    target.deploy(built.output, built.build_id)


def test_current_is_a_symlink_to_a_release(target):
    assert os.path.islink(target.current)
    resolved = os.path.realpath(target.current)
    assert str(target.releases_dir) in resolved


def test_previous_release_is_kept(target):
    releases = target.releases()
    assert len(releases) >= 2, "предыдущий рабочий релиз обязан сохраняться"


def test_rollback_without_previous_release_fails_explicitly(target, monkeypatch):
    monkeypatch.setattr(target, "_state", lambda: {"port": 8081, "previous_release_id": None})
    with pytest.raises(DeployFailed) as exc:
        target.rollback()
    assert "откат невозможен" in exc.value.reason.lower()
