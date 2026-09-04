"""REQ-REGISTRY-DERIVED: производный артефакт проверяется, но не требуется.

История отказа. `site-factory-selfcheck` падал ежедневно на строке
`SITE-MATRIX.json: реестр не сопоставлен ни одной схеме`. Файл производный —
он порождается из `config/site-profiles/*.json` и присутствует не во всех
ветках. Записать его в обычное сопоставление нельзя: там отсутствие файла само
по себе провал, и проверка сломалась бы в ветках без генератора. Просто
исключить — значит вернуть дыру, ради закрытия которой сопоставление сделано
явным: файл, не сопоставленный ни одной схеме, не проверяется никем.

Поэтому проверяются три свойства сразу: отсутствие разрешено, присутствие
обязано пройти схему, а посторонний файл по-прежнему валит проверку.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REAL_REPO = Path(__file__).resolve().parents[2]
SCRIPT_NAME = "validate_registries.py"


def build_repo(tmp_path: Path) -> Path:
    """Минимальное дерево: сам скрипт, схемы и пустой config."""
    (tmp_path / "scripts").mkdir()
    shutil.copy(REAL_REPO / "scripts" / SCRIPT_NAME, tmp_path / "scripts" / SCRIPT_NAME)
    shutil.copytree(REAL_REPO / "schemas", tmp_path / "schemas")
    (tmp_path / "config").mkdir()
    return tmp_path


def required_registries(repo: Path) -> None:
    """Обязательные реестры копируются из настоящего репозитория как есть."""
    for src in (REAL_REPO / "config").glob("*.json"):
        if src.name != "SITE-MATRIX.json":
            shutil.copy(src, repo / "config" / src.name)


def run(repo: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(repo / "scripts" / SCRIPT_NAME)],
        capture_output=True, text=True, timeout=120,
    )


def valid_matrix() -> dict:
    return {
        "schema_version": "1.0",
        "generated_from": "config/site-profiles/*.json",
        "note": "Файл производный.",
        "sites": [
            {
                "site_id": "lords-01",
                "site_type": "video-showcase",
                "domains": ["lordfilm47.space"],
                "locale": "ru-RU",
                "timezone": "Europe/Moscow",
                "theme": {"name": "lords-showcase"},
                "directions": ["movie"],
                "providers": ["cdnvideohub-public-v1"],
                "render_mode": "static",
                "modules": ["seo"],
                "seo": {"enabled": True, "indexing_enabled": False, "canonical_host": "lordfilm47.space"},
                "normalized_content_source": {"kind": "content-ingestion", "ref": "local"},
                "keep_releases": 2,
                "health_endpoint": "/healthz",
                "coverage_endpoint": "/api/v1/coverage",
            }
        ],
    }


def test_absent_derived_artifact_is_allowed(tmp_path: Path) -> None:
    """Ветка без генератора не должна валить ежедневную самопроверку."""
    repo = build_repo(tmp_path)
    required_registries(repo)

    result = run(repo)

    assert result.returncode == 0, result.stderr
    assert "SITE-MATRIX.json" in result.stdout
    assert "SKIP" in result.stdout


def test_present_derived_artifact_must_pass_its_schema(tmp_path: Path) -> None:
    repo = build_repo(tmp_path)
    required_registries(repo)
    (repo / "config" / "SITE-MATRIX.json").write_text(
        json.dumps(valid_matrix(), ensure_ascii=False), encoding="utf-8"
    )

    result = run(repo)

    assert result.returncode == 0, result.stderr + result.stdout
    assert "OK: config/SITE-MATRIX.json" in result.stdout


def test_corrupted_derived_artifact_fails(tmp_path: Path) -> None:
    """Ради этого свойства артефакт и вносится в проверку, а не в исключения."""
    repo = build_repo(tmp_path)
    required_registries(repo)
    broken = valid_matrix()
    del broken["sites"][0]["seo"]
    (repo / "config" / "SITE-MATRIX.json").write_text(
        json.dumps(broken, ensure_ascii=False), encoding="utf-8"
    )

    result = run(repo)

    assert result.returncode == 1
    assert "SITE-MATRIX.json" in result.stderr


def test_unknown_file_still_fails_closed(tmp_path: Path) -> None:
    """Главное свойство исходной проверки не должно быть ослаблено."""
    repo = build_repo(tmp_path)
    required_registries(repo)
    (repo / "config" / "postoronniy.json").write_text("{}", encoding="utf-8")

    result = run(repo)

    assert result.returncode == 1
    assert "не сопоставлен ни одной схеме" in result.stderr
