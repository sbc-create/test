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

import os
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
    """Пустая проверка не должна выглядеть как пройденная проверка.

    Прежде тест утверждал ровно обратное тому, что обещает его имя: код 0 —
    это и есть код пройденной проверки. Имя заявляло свойство, а проверка
    закрепляла его нарушение, и дефект дожил до вызова на настоящем юните.
    """
    result = run("--only", "flags")
    assert result.returncode == 64
    assert "проверка не выполнена" in result.stderr


def run_with_path(extra_bin: Path, *args: str) -> subprocess.CompletedProcess[str]:
    env = dict(os.environ)
    env["PATH"] = f"{extra_bin}:{env['PATH']}"
    return subprocess.run(
        ["bash", str(SCRIPT), *args],
        capture_output=True,
        text=True,
        timeout=60,
        env=env,
    )


def fake_systemctl(tmp_path: Path, unit: str, exec_start: str) -> Path:
    """systemctl, отдающий заданный ExecStart на `systemctl cat <unit>`."""
    binn = tmp_path / "bin"
    binn.mkdir(exist_ok=True)
    sc = binn / "systemctl"
    sc.write_text(
        "#!/usr/bin/env bash\n"
        'if [ "$1" = "cat" ] && [ "$2" = "%s" ]; then\n'
        '  echo "[Service]"\n'
        '  echo "ExecStart=%s"\n'
        "  exit 0\n"
        "fi\n"
        "exit 1\n" % (unit, exec_start),
        encoding="utf-8",
    )
    sc.chmod(0o755)
    return binn


def test_unit_name_is_resolved_not_treated_as_a_non_path(tmp_path: Path) -> None:
    """Вызов с именем юнита — самый естественный, и он обязан работать.

    Пока принималась только строка ExecStart, такой вызов не падал, а отвечал
    «проверять нечего» с кодом 0. Поймано 2026-09-04 на
    site-factory-backup.service, который исполняется из /srv/site-factory/repo.
    """
    script = make_worktree(tmp_path, "repo", branch="deploy/day05")
    binn = fake_systemctl(tmp_path, "demo.service", str(script))
    result = run_with_path(binn, "demo.service")
    assert result.returncode == 1
    assert "ИЗ ДЕРЕВА" in result.stdout
    assert "deploy/day05" in result.stdout


def test_unknown_unit_is_an_error_not_a_clean_result(tmp_path: Path) -> None:
    binn = fake_systemctl(tmp_path, "demo.service", "/bin/true")
    result = run_with_path(binn, "нет-такого.service")
    assert result.returncode == 65
    assert "НЕТ ЮНИТА" in result.stderr
