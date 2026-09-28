"""REQ-SITE-BACKUP-RETENTION: ежедневные копии баз не заполняют диск.

`deploy/staging/backup.sh` живёт в репозитории сайта и удержания не имеет:
каждый прогон создаёт новый каталог, старые не удаляются никогда. Пока копии
снимались только при выкатке, наборов накопилось шесть — незаметно. Ежедневный
таймер сделает рост постоянным, а этот диск уже ломался ровно на неограниченном
росте бэкапов: 2026-09-03 host-бэкап упал с `No space left on device`.

Дописывать удаление файлов в чужой скрипт мимоходом нельзя, поэтому удержание
вынесено отдельно и вызывается таймером после копирования.

Главный предохранитель проверяется первым: набор, на который указывает `latest`,
не удаляется никогда. Именно его берёт откат, и удалить его значило бы оставить
откат без данных — то есть сломать восстановление ровно тем средством, которое
призвано беречь место.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SCRIPT = REPO / "automation" / "host" / "site-backup-retention.sh"


def make_sets(root: Path, names: list[str], latest: str | None = None) -> None:
    for name in names:
        (root / name).mkdir(parents=True)
        (root / name / "site.sql").write_text("dump", encoding="utf-8")
    if latest:
        (root / "latest").symlink_to(latest)


def run(root: Path, **env: str) -> subprocess.CompletedProcess[str]:
    assert SCRIPT.exists(), f"нет скрипта удержания: {SCRIPT}"
    return subprocess.run(
        ["bash", str(SCRIPT), str(root)],
        capture_output=True, text=True, timeout=60, env={**os.environ, **env},
    )


def sets_in(root: Path) -> list[str]:
    return sorted(p.name for p in root.iterdir() if p.is_dir() and not p.is_symlink())


def test_set_referenced_by_latest_is_never_deleted(tmp_path: Path) -> None:
    """Главный предохранитель: откат берёт именно этот набор."""
    names = [f"2026082{i}T000000Z" for i in range(1, 6)]
    make_sets(tmp_path, names, latest=names[0])

    result = run(tmp_path, SITE_BACKUP_KEEP="2", SITE_BACKUP_KEEP_FLOOR="2")

    assert names[0] in sets_in(tmp_path), "удалён набор, на который указывает latest"
    assert "пропущен" in result.stdout
    assert (tmp_path / "latest").is_symlink(), "ссылка latest должна уцелеть"


def test_oldest_sets_beyond_keep_are_removed(tmp_path: Path) -> None:
    names = [f"2026082{i}T000000Z" for i in range(1, 6)]
    make_sets(tmp_path, names)

    run(tmp_path, SITE_BACKUP_KEEP="3", SITE_BACKUP_KEEP_FLOOR="2")

    assert sets_in(tmp_path) == names[2:], sets_in(tmp_path)


def test_floor_is_never_crossed(tmp_path: Path) -> None:
    names = [f"2026082{i}T000000Z" for i in range(1, 6)]
    make_sets(tmp_path, names)

    run(tmp_path, SITE_BACKUP_KEEP="1", SITE_BACKUP_KEEP_FLOOR="3")

    assert len(sets_in(tmp_path)) == 3


def test_nothing_to_do_is_reported_not_silent(tmp_path: Path) -> None:
    make_sets(tmp_path, ["20260821T000000Z", "20260822T000000Z"])
    result = run(tmp_path, SITE_BACKUP_KEEP="14")
    assert "удалять нечего" in result.stdout
    assert len(sets_in(tmp_path)) == 2


def test_foreign_entries_are_left_alone(tmp_path: Path) -> None:
    """Правило знает только про метки времени: чужой файл не его дело."""
    names = [f"2026082{i}T000000Z" for i in range(1, 6)]
    make_sets(tmp_path, names)
    (tmp_path / "README.txt").write_text("не трогать", encoding="utf-8")
    (tmp_path / "черновик").mkdir()

    run(tmp_path, SITE_BACKUP_KEEP="2", SITE_BACKUP_KEEP_FLOOR="2")

    assert (tmp_path / "README.txt").exists()
    assert (tmp_path / "черновик").exists(), "каталог не с меткой времени удалён"


def test_missing_root_is_not_an_error(tmp_path: Path) -> None:
    result = run(tmp_path / "нет-такого")
    assert result.returncode == 0


def test_service_unit_runs_retention_after_the_backup() -> None:
    """Порядок важен: удерживать нечего, пока новая копия не снята."""
    unit = (REPO / "automation" / "host" / "systemd" / "yummy-site-backup.service").read_text(
        encoding="utf-8"
    )
    lines = [ln for ln in unit.splitlines() if ln.startswith("ExecStart")]
    assert len(lines) == 2, f"ожидались копирование и удержание, найдено: {lines}"
    assert "backup.sh" in lines[0]
    assert "site-backup-retention.sh" in lines[1]
