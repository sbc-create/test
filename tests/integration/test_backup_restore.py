"""REQ-BACKUP: восстановление проверяется, а не декларируется."""
import tarfile

import pytest

from factory import inventory
from factory.paths import PATHS
from factory.targets import build_target


@pytest.fixture
def target(pilot_package):
    return build_target(inventory.target(pilot_package["target_ref"]), pilot_package)


def test_backup_creates_readable_archive(target):
    backup = target.backup()
    assert backup["taken"] is True
    archive = PATHS.root / backup["ref"]
    assert archive.exists()
    with tarfile.open(archive, "r:gz") as tar:
        names = tar.getnames()
    assert any(name.startswith("shared") for name in names)


def test_backup_alone_is_not_proof_of_restore(target):
    backup = target.backup()
    assert backup["restore_verified"] is False, "наличие файла бэкапа не считается доказательством"


def test_restore_actually_restores_content(target, tmp_path):
    """Восстановление возвращает именно то содержимое, что было на момент бэкапа."""
    marker = target.shared_dir / "restore-marker.txt"
    target.shared_dir.mkdir(parents=True, exist_ok=True)
    marker.write_text("значение до бэкапа", encoding="utf-8")
    backup = target.backup()

    marker.write_text("значение после порчи", encoding="utf-8")
    destination = tmp_path / "restored"
    assert target.restore(backup["ref"], destination) is True
    restored = destination / "shared" / "restore-marker.txt"
    assert restored.exists()
    assert restored.read_text(encoding="utf-8") == "значение до бэкапа"
    marker.unlink(missing_ok=True)


def test_restore_detects_corrupted_archive(target, tmp_path):
    """Повреждённый архив не должен считаться восстановимым."""
    backup = target.backup()
    archive = PATHS.root / backup["ref"]
    corrupted = tmp_path / "corrupted.tar.gz"
    corrupted.write_bytes(archive.read_bytes()[: archive.stat().st_size // 3])
    relative = str(corrupted.relative_to(PATHS.root)) if str(corrupted).startswith(str(PATHS.root)) else None
    if relative is None:
        import shutil as _shutil
        target_copy = PATHS.backups / "corrupted-test.tar.gz"
        _shutil.copyfile(corrupted, target_copy)
        relative = str(target_copy.relative_to(PATHS.root))
    try:
        assert target.restore(relative, tmp_path / "out") is False
    finally:
        (PATHS.root / relative).unlink(missing_ok=True)


def test_restore_of_missing_archive_fails_honestly(target, tmp_path):
    assert target.restore("var/backups/does-not-exist.tar.gz", tmp_path / "x") is False


@pytest.mark.slow
def test_pipeline_verifies_restore(pilot_package):
    """Полный прогон обязан подтвердить восстановимость, а не только сделать архив."""
    import json

    from factory import pipeline
    outcome = pipeline.run_job("pilot-local", skip_browser=True)
    data = json.loads(outcome.result_path.read_text(encoding="utf-8"))
    assert data["backup"]["taken"] is True
    assert data["backup"]["restore_verified"] is True
    assert any(step["id"] == "restore_test" and step["status"] == "ok" for step in data["steps"])
