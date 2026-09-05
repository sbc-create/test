"""Личность замороженного кандидата в status/templates.json — проверяемая.

Тест появился после того, как в `FROZEN_CANDIDATE` был записан полный SHA,
набранный по памяти от короткого `cd2f718`: сокращение было настоящим, а
остальные тридцать два знака — выдуманными. Такой идентификатор выглядит
безупречно и не указывает никуда.

Проверяются две вещи, и обе — против фактов, а не против самих себя:
ревизия существует в репозитории, а отпечаток совпадает с тем, что даёт
пересчёт по этой ревизии.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

import templates_status  # noqa: E402

STATUS = ROOT / "status" / "templates.json"


def _git(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", "-C", str(ROOT), *args], capture_output=True, text=True)


class TestЛичностьКандидата:
    def test_ревизия_кандидата_существует_в_репозитории(self):
        sha = templates_status.FROZEN_CANDIDATE["head"]
        assert len(sha) == 40, f"SHA должен быть полным, получено {len(sha)} знаков"
        result = _git("cat-file", "-t", sha)
        assert result.stdout.strip() == "commit", (
            f"ревизия {sha} в репозитории не найдена: {result.stderr.strip()}")

    def test_отпечаток_кандидата_совпадает_с_пересчётом_по_его_ревизии(self, tmp_path):
        sha = templates_status.FROZEN_CANDIDATE["head"]
        archive = tmp_path / "candidate.tar"
        made = subprocess.run(
            ["git", "-C", str(ROOT), "archive", "--format=tar", "-o", str(archive), sha],
            capture_output=True, text=True)
        if made.returncode != 0:
            pytest.skip(f"дерево ревизии недоступно: {made.stderr.strip()}")
        tree = tmp_path / "tree"
        tree.mkdir()
        subprocess.run(["tar", "-xf", str(archive), "-C", str(tree)], check=True)

        # Пересчёт идёт по содержимому ревизии кандидата, а не по рабочему
        # дереву: в post-release ветке отпечаток другой, и сравнение с ней
        # ничего бы не доказало.
        from factory.templates import digest as digest_mod
        actual = digest_mod.compute(tree)
        assert actual["template_digest"] == templates_status.FROZEN_CANDIDATE["template_digest"], (
            f"ревизия {sha[:12]} даёт отпечаток {actual['template_digest'][:16]}, "
            f"а кандидат объявляет "
            f"{templates_status.FROZEN_CANDIDATE['template_digest'][:16]}")
        assert actual["files"] == templates_status.FROZEN_CANDIDATE["template_digest_files"]

    def test_статус_не_выдаёт_ветку_доработок_за_кандидата(self):
        if not STATUS.exists():
            pytest.skip("status/templates.json ещё не собран")
        data = json.loads(STATUS.read_text(encoding="utf-8"))
        assert data["template_digest"] == templates_status.FROZEN_CANDIDATE["template_digest"]
        assert data["template_digest_files"] == 19
        recomputed = data.get("recomputed_from")
        assert recomputed, "статус обязан называть, откуда он пересчитан"
        if not recomputed["matches_candidate"]:
            assert "не входит" in recomputed["note"], (
                "расхождение отпечатков обязано быть названо, а не спрятано")
