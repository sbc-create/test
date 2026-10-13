"""Метка происхождения в паспорте проверяема, и сведение обязано её проверять.

Было: при `status: "not_extracted"` и подтверждённых активациях инструмент
печатал «происхождение и жизнь расходятся, решает человек». Это честно и
НЕ является проверкой: «выделен» считается из `repo.remote` функцией
`registry.extracted_sites()` — той же, на которой стоит `require_not_extracted`.
Значит ответ измеряется, а человека звали решать то, что можно измерить.

Замер 13.10 на живом реестре: обе ячейки (`lords-02`, `lords-03`) в выделенных,
то есть метка ложна, а не спорна. Эти проверки держат оба исхода: ложную метку
и верную — иначе инструмент печатал бы один вывод на любой вход (D205).
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

КОРЕНЬ = Path(__file__).resolve().parents[2]
ИНСТРУМЕНТ = КОРЕНЬ / "automation" / "local" / "cell-status-reconcile.py"


def _реестр(путь: Path, *, remote: str | None) -> None:
    ячейка = {
        "site_id": "проба-01",
        "domain": "проба.localhost.test",
        "status": "not_extracted",
        "template": {"template_id": "проба"},
        "runtime": {"unit": "nova-проба.service", "account": "проба",
                    "app_dir": "/srv/проба/app", "data_dir": "/srv/проба/data",
                    "port": 9999},
        "repo": {"kind": "remote", "path": "var/site-repos/проба"},
    }
    if remote:
        ячейка["repo"]["remote"] = remote
    путь.write_text(json.dumps({"version": 1, "cells": [ячейка]},
                               ensure_ascii=False), encoding="utf-8")


def _следы(каталог: Path, сколько: int) -> None:
    каталог.mkdir(parents=True, exist_ok=True)
    for i in range(сколько):
        (каталог / f"проба-01-act-{i}.json").write_text(json.dumps({
            "site_id": "проба-01", "operation": "activate", "status": "ok",
            "dry_run": False, "finished_at": f"2026-10-13T00:0{i}:00+00:00",
            "outcome": {"status": "activated", "stage": "activated"},
        }, ensure_ascii=False), encoding="utf-8")


def _прогон(tmp_path: Path, *, remote: str | None):
    реестр = tmp_path / "site-cells.json"
    следы = tmp_path / "results"
    _реестр(реестр, remote=remote)
    _следы(следы, 3)
    return subprocess.run(
        [sys.executable, str(ИНСТРУМЕНТ), "--registry", str(реестр),
         "--results", str(следы)],
        capture_output=True, text=True, timeout=180, cwd=str(КОРЕНЬ))


def test_ложная_метка_происхождения_называется_ложной(tmp_path):
    г = _прогон(tmp_path, remote="https://example.invalid/site-проба")
    assert "метка ЛОЖНА" in г.stdout, г.stdout + г.stderr
    # Называется и источник истины, и то, откуда он берётся: без этого вывод
    # нечем проверить.
    assert "repo.remote" in г.stdout
    assert "extracted_sites" in г.stdout
    assert "https://example.invalid/site-проба" in г.stdout


def test_верная_метка_не_объявляется_ложной(tmp_path):
    """Обратная сторона: без неё вывод был бы один на любой вход.

    Ячейка без `repo.remote` действительно не выделена, и тогда расходится
    только жизнь — это и есть случай, который решает человек.
    """
    г = _прогон(tmp_path, remote=None)
    assert "метка верна" in г.stdout, г.stdout + г.stderr
    assert "метка ЛОЖНА" not in г.stdout
    assert "решает человек" in г.stdout


def test_статус_не_перезаписывается_ни_в_одном_из_случаев(tmp_path):
    """Находка не даёт права на запись: `not_extracted` не трогается.

    Инструмент умеет ставить только `live` и только по следам; метка
    происхождения — вход владельца, и измерение этого не меняет.
    """
    г = _прогон(tmp_path, remote="https://example.invalid/site-проба")
    assert "ничего не записано" in г.stdout, г.stdout
    assert "к переводу 0" in г.stdout, г.stdout
