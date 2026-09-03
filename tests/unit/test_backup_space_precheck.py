"""REQ-BACKUP-SPACE: нехватка места видна до упаковки, а не после.

История отказа, ради которой этот файл существует. `site-factory-backup.sh`
собирает staging, пакует его в архив и затем **распаковывает архив второй раз**,
чтобы сверить контрольные суммы: доказательство восстановления — часть контракта.
Значит на диске одновременно живут staging, архив и распакованная копия.

2026-09-03 прогон дошёл до последнего шага и упал:
`tar: ... Cannot create symlink ...: No space left on device`, затем
`BACKUP FAILED: архив не распаковывается`. К этому моменту были потрачены три с
половиной минуты процессорного времени и записан архив на 1.13 GB, который потом
остался на диске сиротой. Отказ был предсказуем на первом шаге: диск стоял на
90 %.

Проверяется политика на числах, а не заполнение настоящего диска: измерение
(`du`, `df`) живёт в вызывающем скрипте, а решение здесь.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
SCRIPT = REPO / "automation" / "host" / "backup-space-precheck.sh"

GB = 1024 * 1024  # килобайт в гигабайте


def check(stage_kb: int, work_avail_kb: int, backup_avail_kb: int, same_fs: int = 0, **env: str):
    assert SCRIPT.exists(), f"нет скрипта проверки места: {SCRIPT}"
    import os

    return subprocess.run(
        ["bash", str(SCRIPT), str(stage_kb), str(work_avail_kb), str(backup_avail_kb), str(same_fs)],
        capture_output=True,
        text=True,
        env={**os.environ, **env},
        timeout=60,
    )


def test_enough_space_passes() -> None:
    result = check(1 * GB, 10 * GB, 10 * GB)
    assert result.returncode == 0, result.stderr


def test_work_filesystem_must_hold_archive_and_restored_copy() -> None:
    """Двух гигабайт под staging на гигабайт не хватает: нужен ещё и распакованный."""
    result = check(1 * GB, 2 * GB, 10 * GB)
    assert result.returncode == 1
    assert "доказательства восстановления" in result.stderr


def test_backup_directory_must_hold_the_archive() -> None:
    result = check(1 * GB, 10 * GB, 1 * GB)
    assert result.returncode == 1
    assert "под архив" in result.stderr


def test_the_2026_09_03_incident_would_have_been_refused_before_packing() -> None:
    """Числа того отказа: staging ~3 GB при ~7.1 GB свободного места.

    Прогон тогда собрал архив и упал на распаковке. Проверка обязана отказать
    заранее: 3 GB staging требуют 3 GB архива плюс 3 GB распакованной копии плюс
    запас — больше, чем было свободно.
    """
    result = check(3 * GB, int(7.1 * GB), int(7.1 * GB))
    assert result.returncode == 1, (
        "проверка пропустила ровно ту конфигурацию, на которой прогон упал: " + result.stdout
    )
    assert "No space" not in result.stderr, "отказ должен быть объяснён, а не пересказан из tar"
    assert "запас" in result.stderr


def test_margin_is_configurable() -> None:
    """Без запаса та же раскладка проходит — значит отказ даёт именно запас."""
    tight = check(3 * GB, int(6.2 * GB), int(6.2 * GB), SITE_FACTORY_BACKUP_SPACE_MARGIN_PCT="0")
    assert tight.returncode == 0, tight.stderr
    with_margin = check(3 * GB, int(6.2 * GB), int(6.2 * GB), SITE_FACTORY_BACKUP_SPACE_MARGIN_PCT="20")
    assert with_margin.returncode == 1


def test_failure_message_names_what_is_missing_and_how_much() -> None:
    """Оператору нужен размер и адрес нехватки, а не «недостаточно места»."""
    result = check(5 * GB, 1 * GB, 1 * GB)
    assert result.returncode == 1
    for expected in ("GB", "staging", "свободно"):
        assert expected in result.stderr, f"в сообщении нет {expected}: {result.stderr}"


def test_one_filesystem_sums_both_requirements() -> None:
    """Общая ФС: требования складываются, а не проверяются порознь.

    Первая версия этой проверки сравнивала два требования с двумя запасами
    независимо и на этом хосте была бы бесполезна ровно там, где нужна:
    `/tmp` и `/srv/backups` лежат на одном `/`, свободное место у них общее.
    Порознь 7.2 GB и 3.6 GB проходят при 8.1 GB свободного — а вместе требуют
    10.8 GB, которых нет. Тест закрепляет именно это различие.
    """
    stage, avail = 3 * GB, int(8.1 * GB)

    apart = check(stage, avail, avail, same_fs=0)
    assert apart.returncode == 0, "порознь эта раскладка обязана проходить — иначе тест ничего не различает"

    together = check(stage, avail, avail, same_fs=1)
    assert together.returncode == 1, "на одной ФС та же раскладка обязана быть отклонена"
    assert "одной файловой системе" in together.stderr


def test_one_filesystem_passes_when_there_is_genuinely_room() -> None:
    """Складывание требований не должно запрещать заведомо достаточный диск."""
    result = check(1 * GB, 20 * GB, 20 * GB, same_fs=1)
    assert result.returncode == 0, result.stderr
