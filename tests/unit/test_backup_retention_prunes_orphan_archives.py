"""REQ-BACKUP-RETENTION: архив упавшего прогона не остаётся на диске навсегда.

История отказа, ради которой этот файл существует. Удержание в
`site-factory-backup.sh` перебирало только `host-*.verified.json` и удаляло
пару «архив + запись». Прогон, упавший на шаге доказательства восстановления,
записи не создаёт — значит его архив не попадал ни в один список удаления
никогда.

2026-09-03 это замкнулось в цепочку: диск заполнился на 90 %, распаковка для
проверки упала на `No space left on device`, запись не создалась, архив на
1.13 GB остался лежать, `site-factory-health` начал падать каждые 15 минут по
возрасту подтверждённой копии — а следующий прогон получил на диске ещё меньше
места, чем предыдущий. Каждый провал делал следующий вероятнее.

Проверяется поведение, а не наличие слов в скрипте: на подставном каталоге
раскладываются настоящие файлы с настоящими временами изменения, скрипт
удержания прогоняется целиком, и проверяется, что осталось на диске.

Отдельно закреплены два предохранителя, потому что оба неочевидны и оба
опаснее самой утечки:

* архив идущего прямо сейчас прогона тоже не имеет записи о проверке —
  удалить его значило бы сломать живой бэкап, поэтому у правила есть возраст;
* если подтверждённых копий нет вовсе, неподтверждённый архив — единственное,
  что есть у оператора, и он сохраняется даже старым.
"""

from __future__ import annotations

import json
import os
import subprocess
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SCRIPT = REPO / "automation" / "host" / "backup-retention.sh"

HOUR = 3600


def _archive(directory: Path, stamp: str, *, age_hours: float) -> Path:
    path = directory / f"host-{stamp}.tar.gz"
    path.write_bytes(b"archive")
    when = time.time() - age_hours * HOUR
    os.utime(path, (when, when))
    return path


def _record(directory: Path, stamp: str, *, age_hours: float) -> Path:
    path = directory / f"host-{stamp}.verified.json"
    path.write_text(json.dumps({"backup": "control-host", "restore_verified": True}))
    when = time.time() - age_hours * HOUR
    os.utime(path, (when, when))
    return path


def _verified(directory: Path, stamp: str, *, age_hours: float) -> tuple[Path, Path]:
    return (
        _archive(directory, stamp, age_hours=age_hours),
        _record(directory, stamp, age_hours=age_hours),
    )


def run_retention(directory: Path, **env: str) -> subprocess.CompletedProcess[str]:
    assert SCRIPT.exists(), f"нет скрипта удержания: {SCRIPT}"
    result = subprocess.run(
        ["bash", str(SCRIPT), str(directory)],
        capture_output=True,
        text=True,
        env={**os.environ, **env},
        timeout=60,
    )
    assert result.returncode == 0, f"удержание упало: {result.stderr}"
    return result


def test_orphan_archive_is_pruned(tmp_path: Path) -> None:
    """Архив без записи о проверке и старше порога — удаляется."""
    _verified(tmp_path, "20260901T000000Z", age_hours=48)
    orphan = _archive(tmp_path, "20260903T032419Z", age_hours=36)

    run_retention(tmp_path)

    assert not orphan.exists(), "осиротевший архив упавшего прогона остался на диске"


def test_verified_triple_survives_the_orphan_rule(tmp_path: Path) -> None:
    """Правило сирот не имеет права трогать подтверждённую копию."""
    archive, record = _verified(tmp_path, "20260901T000000Z", age_hours=48)

    run_retention(tmp_path)

    assert archive.exists() and record.exists(), "подтверждённая копия удалена правилом сирот"


def test_archive_of_a_running_backup_is_kept(tmp_path: Path) -> None:
    """Прогон, идущий прямо сейчас, ещё не имеет записи — его архив не трогаем."""
    _verified(tmp_path, "20260901T000000Z", age_hours=48)
    in_flight = _archive(tmp_path, "20260903T140000Z", age_hours=0)

    run_retention(tmp_path)

    assert in_flight.exists(), "удалён архив прогона, который ещё выполняется"


def test_orphan_is_kept_when_nothing_is_verified(tmp_path: Path) -> None:
    """Без подтверждённых копий неподтверждённый архив — последнее, что есть."""
    only = _archive(tmp_path, "20260903T032419Z", age_hours=72)

    run_retention(tmp_path)

    assert only.exists(), "удалён единственный архив при отсутствии подтверждённых копий"


def test_verified_triples_beyond_keep_are_pruned_oldest_first(tmp_path: Path) -> None:
    """Прежнее поведение сохранено: сверх KEEP удаляются самые старые."""
    stamps = [f"2026090{i}T000000Z" for i in range(1, 6)]
    for index, stamp in enumerate(stamps):
        _verified(tmp_path, stamp, age_hours=(len(stamps) - index) * 24)

    run_retention(
        tmp_path,
        SITE_FACTORY_BACKUP_KEEP="3",
        SITE_FACTORY_BACKUP_KEEP_FLOOR="3",
    )

    survivors = sorted(p.name for p in tmp_path.glob("host-*.verified.json"))
    assert survivors == [f"host-{s}.verified.json" for s in stamps[2:]], survivors
    for stamp in stamps[:2]:
        assert not (tmp_path / f"host-{stamp}.tar.gz").exists(), f"архив {stamp} не удалён вместе с записью"


def test_keep_floor_is_never_crossed(tmp_path: Path) -> None:
    """Пол подтверждённых копий сильнее KEEP: ниже него удержание не опускается."""
    stamps = [f"2026090{i}T000000Z" for i in range(1, 5)]
    for index, stamp in enumerate(stamps):
        _verified(tmp_path, stamp, age_hours=(len(stamps) - index) * 24)

    run_retention(
        tmp_path,
        SITE_FACTORY_BACKUP_KEEP="1",
        SITE_FACTORY_BACKUP_KEEP_FLOOR="3",
    )

    assert len(list(tmp_path.glob("host-*.verified.json"))) == 3
