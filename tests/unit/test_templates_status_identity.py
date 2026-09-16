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

        # Пересчёт идёт по содержимому ревизии кандидата и её же кодом.
        #
        # И то, и другое существенно. По рабочему дереву считать нельзя: в
        # ветке доработок отпечаток другой, и сравнение с ней ничего бы не
        # доказало. Но и алгоритмом рабочего дерева считать нельзя тоже, а
        # именно так проверка и делала — и сломалась, как только состав
        # отпечатка расширили с 21 файла до 28.
        #
        # Состав — часть алгоритма, а не его настройка. Меняя состав, мы
        # задним числом меняем отпечаток каждой прошлой ревизии, и удостоверение
        # кандидата становится непроверяемым. Соблазн здесь один: переписать
        # объявленное кандидатом число под новый код. Это подделка удостоверения
        # задним числом, а не починка проверки.
        #
        # Поэтому удостоверение сверяется тем алгоритмом, которым выдано.
        # Отдельным процессом — чтобы код ревизии не смешивался с рабочим
        # деревом через уже загруженные модули.
        probe = (
            "import json, sys; sys.path.insert(0, %r);"
            "from factory.templates import digest;"
            "print(json.dumps(digest.compute()))" % str(tree)
        )
        computed = subprocess.run([sys.executable, "-c", probe],
                                  capture_output=True, text=True, cwd=str(tree), timeout=600)
        assert computed.returncode == 0, computed.stderr[-2000:]
        actual = json.loads(computed.stdout.strip().splitlines()[-1])

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
