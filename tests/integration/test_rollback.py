"""REQ-ATOMIC: атомарные релизы и откат на предыдущий рабочий."""
import os

import pytest

from factory import build as build_mod
from factory import inventory
from factory.errors import DeployFailed
from factory.targets import build_target


@pytest.fixture
def target(pilot_package):
    """Цель с гарантированно двумя релизами: тест не должен зависеть от прогретого окружения."""
    target = build_target(inventory.target(pilot_package["target_ref"]), pilot_package)
    built = build_mod.build("pilot-local")
    target.deploy(built.output, built.build_id)
    if len(target.releases()) < 2 or target._state().get("previous_release_id") in (None, built.build_id):
        # Готовим второй релиз, отличающийся содержимым, чтобы точка отката была реальной.
        import shutil
        synthetic = target.releases_dir / "synthetic-previous"
        shutil.rmtree(synthetic, ignore_errors=True)
        shutil.copytree(built.output, synthetic)
        (synthetic / ".complete").write_text("synthetic", encoding="utf-8")
        target._save_state(previous_release_id="synthetic-previous")
    return target


@pytest.mark.slow
def test_rollback_switches_to_previous_release(target):
    built = build_mod.build("pilot-local")
    current_before = target.current_release()
    previous = target._state().get("previous_release_id")
    assert previous and previous != current_before, "фикстура обязана подготовить настоящую точку отката"
    result = target.rollback()
    assert result.release_id == previous
    assert target.current_release() == previous
    assert target.current_release() != current_before
    ok, detail = target.health()
    assert ok, f"после отката сайт обязан отвечать: {detail}"
    # возвращаем цель в актуальное состояние
    target.deploy(built.output, built.build_id)


@pytest.mark.slow
def test_current_is_a_symlink_to_a_release(target):
    assert os.path.islink(target.current)
    resolved = os.path.realpath(target.current)
    assert str(target.releases_dir) in resolved


@pytest.mark.slow
def test_previous_release_is_kept(target):
    releases = target.releases()
    assert len(releases) >= 2, "предыдущий рабочий релиз обязан сохраняться"
    assert target._state().get("previous_release_id") in releases


@pytest.mark.slow
def test_rollback_without_previous_release_fails_explicitly(target, monkeypatch):
    monkeypatch.setattr(target, "_state", lambda: {"port": 8081, "previous_release_id": None})
    with pytest.raises(DeployFailed) as exc:
        target.rollback()
    assert "откат невозможен" in exc.value.reason.lower()


@pytest.mark.slow
def test_previous_release_is_not_overwritten_by_itself(target, monkeypatch, tmp_path):
    """Регрессия: повторный деплой того же релиза затирал точку отката самим собой,
    после чего rollback «успешно» переключался на текущий релиз."""
    from factory import build as build_mod
    built = build_mod.build("pilot-local")
    target.deploy(built.output, built.build_id)
    first_previous = target._state().get("previous_release_id")
    target.deploy(built.output, built.build_id)
    assert target._state().get("previous_release_id") == first_previous
    assert target._state().get("previous_release_id") != target.current_release() or first_previous is None


@pytest.mark.slow
def test_rollback_refuses_when_previous_equals_current(target, monkeypatch):
    """Если точка отката совпадает с текущим релизом, откат обязан отказать, а не
    имитировать успех переключением на то же самое."""
    current = target.current_release()
    monkeypatch.setattr(target, "_state", lambda: {"port": 8082, "previous_release_id": current})
    with pytest.raises(DeployFailed):
        target.rollback()
