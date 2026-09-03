"""REQ-UNIT-PROVENANCE: видно, какие службы исполняются из рабочего дерева.

Юнит, чей `ExecStart` указывает внутрь git-checkout, исполняет то, что там
сейчас лежит. `git checkout` в этом каталоге молча меняет поведение боевой
службы: ни выкатки, ни отката, ни записи о работающей версии. Установщик
unit'ов предупреждает об этом словами — «служба запускается и молча исполняет
чужой код», — но узнать, случилось ли это, было нечем.

Измерено 2026-09-03: пять служб парка исполнялись из рабочих деревьев, и три из
них — контентные юниты YummyAnime — из дерева на ветке, отличной от той, из
которой собран боевой образ, да ещё с незакоммиченной правкой.

Отдельно закреплён случай, на котором инструмент был пойман при первом прогоне:
`ExecStart` вида `/usr/bin/node /путь/script.mjs`. Если смотреть только на
первый аргумент, ответом будет «из артефакта» — интерпретатор лежит в /usr/bin.
Ложно-безопасный ответ хуже отсутствия проверки: он закрывает вопрос неверно.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
SCRIPT = REPO / "automation" / "host" / "check-unit-provenance.sh"


def run(*args: str) -> subprocess.CompletedProcess[str]:
    assert SCRIPT.exists(), f"нет скрипта: {SCRIPT}"
    return subprocess.run(
        ["bash", str(SCRIPT), *args], capture_output=True, text=True, timeout=60
    )


def make_worktree(tmp_path: Path, name: str, branch: str = "master") -> Path:
    root = tmp_path / name
    (root / "scripts").mkdir(parents=True)
    script = root / "scripts" / "run.mjs"
    script.write_text("console.log('x');", encoding="utf-8")
    subprocess.run(["git", "init", "-q", "-b", branch, str(root)], check=True, timeout=60)
    return script


def make_plain(tmp_path: Path, name: str) -> Path:
    root = tmp_path / name
    root.mkdir(parents=True)
    binary = root / "tool"
    binary.write_text("#!/bin/sh\n", encoding="utf-8")
    return binary


def test_path_inside_worktree_is_reported(tmp_path: Path) -> None:
    script = make_worktree(tmp_path, "repo")
    result = run(str(script))
    assert result.returncode == 1
    assert "ИЗ ДЕРЕВА" in result.stdout
    assert "ветка" in result.stdout


def test_path_outside_any_worktree_is_clean(tmp_path: Path) -> None:
    binary = make_plain(tmp_path, "opt")
    result = run(str(binary))
    assert result.returncode == 0
    assert "ИЗ АРТЕФАКТА" in result.stdout


def test_interpreter_plus_script_checks_the_script_too(tmp_path: Path) -> None:
    """Тот случай, на котором инструмент был пойман: смотреть надо все пути."""
    script = make_worktree(tmp_path, "repo")
    interpreter = make_plain(tmp_path, "usr-bin")

    result = run(str(interpreter), str(script))

    assert result.returncode == 1, "скрипт из дерева не замечен за интерпретатором"
    assert "ИЗ АРТЕФАКТА" in result.stdout
    assert "ИЗ ДЕРЕВА" in result.stdout


def test_exit_code_counts_mutable_paths(tmp_path: Path) -> None:
    first = make_worktree(tmp_path, "one")
    second = make_worktree(tmp_path, "two")
    assert run(str(first), str(second)).returncode == 2


def test_non_path_arguments_are_ignored(tmp_path: Path) -> None:
    """ExecStart несёт и флаги: сообщение о каждом утопило бы находки."""
    binary = make_plain(tmp_path, "opt")
    result = run(str(binary), "--flag", "value", "-T")
    assert result.returncode == 0
    assert result.stdout.count("ИЗ АРТЕФАКТА") == 1


def test_missing_path_is_named_not_silently_ignored(tmp_path: Path) -> None:
    result = run(str(tmp_path / "нет-такого"))
    assert "ОТСУТСТВУЕТ" in result.stdout


def test_arguments_without_any_path_do_not_claim_safety(tmp_path: Path) -> None:
    """Пустая проверка не должна выглядеть как пройденная проверка."""
    result = run("--only", "flags")
    assert result.returncode == 0
    assert "проверять нечего" in result.stderr
