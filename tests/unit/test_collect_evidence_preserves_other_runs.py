"""Сборщик доказательств не стирает доказательства чужого прогона.

Обнаружено в цикле SEO-CONTRACT-SAFE-6H-03: после обычного
`bash tests/run-all.sh` в дереве оказывались удалены восемь файлов
`artifacts/evidence/multisite-*.json`. Причина — сборщик стирал каталог
целиком и копировал только то, что произвёл текущий прогон. Доказательства
multisite производит другой набор; при обычном прогоне их источник
отсутствует, и файлы не возвращались.

Так исчезало доказательство состоявшейся проверки из-за того, что НЕ
запускалась другая. Репозиторий запрещает отчёт о непроведённой проверке;
молчаливое исчезновение доказательства проведённой — ошибка того же рода в
обратную сторону.

Тест работает в отдельном корне через `FACTORY_ROOT` и файлов репозитория не
трогает. Первая редакция писала синтетический файл прямо в
`artifacts/evidence/`: тест, мутирующий отслеживаемые файлы, сам является
дефектом, и повторять его нельзя.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

CARRIED = "multisite-restore-proof.json"


def _make_root(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    (root / "artifacts" / "jobs" / "pilot-local").mkdir(parents=True)
    (root / "artifacts" / "evidence").mkdir(parents=True)
    (root / "artifacts" / "jobs" / "pilot-local" / "job.json").write_text(
        json.dumps({"job_id": "job-1", "status": "DONE", "finished_at": "2026-08-30T00:00:00Z"}),
        encoding="utf-8",
    )
    # Доказательство прошлого прогона: источника для него в этом прогоне нет.
    (root / "artifacts" / "evidence" / CARRIED).write_text(
        json.dumps({"proof": "restore", "from": "предыдущий прогон"}), encoding="utf-8"
    )
    return root


def _run(root: Path, repo: Path) -> subprocess.CompletedProcess:
    env = dict(os.environ, FACTORY_ROOT=str(root))
    return subprocess.run(
        [sys.executable, str(repo / "tests" / "tools" / "collect_evidence.py"), "pilot-local"],
        cwd=repo, capture_output=True, text=True, env=env,
    )


def test_evidence_from_a_run_that_did_not_repeat_is_preserved(tmp_path):
    from factory.paths import PATHS

    root = _make_root(tmp_path)
    before = (root / "artifacts" / "evidence" / CARRIED).read_text(encoding="utf-8")

    result = _run(root, PATHS.root)
    assert result.returncode == 0, result.stderr

    survivor = root / "artifacts" / "evidence" / CARRIED
    assert survivor.exists(), "сборщик удалил доказательство прогона, который не повторялся"
    assert survivor.read_text(encoding="utf-8") == before, "содержимое подменено"


def test_manifest_separates_fresh_from_carried_over(tmp_path):
    from factory.paths import PATHS

    root = _make_root(tmp_path)
    result = _run(root, PATHS.root)
    assert result.returncode == 0, result.stderr

    manifest = json.loads(
        (root / "artifacts" / "evidence" / "MANIFEST.json").read_text(encoding="utf-8")
    )
    assert CARRIED in manifest["carried_over"], (
        f"перенесённый файл не отмечен в манифесте: {manifest}"
    )
    assert CARRIED not in manifest["refreshed"], "перенесённый файл выдан за свежий"
    assert "job-result.json" in manifest["refreshed"], "свежий файл не отмечен"
