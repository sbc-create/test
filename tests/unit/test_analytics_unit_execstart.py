"""REQ-SYSTEMD-EXEC: команда в unit'е действительно исполнима.

Два дефекта, найденные на боевом запуске, — оба такого рода, что
`systemd-analyze verify` их не видит, а служба падает уже в проде:

1. `--json` объявлен на корневом парсере фабрики и обязан стоять ДО имени
   подкоманды. В форме `... analytics apply --confirm-writes --json` argparse
   отвечает «unrecognized arguments» и выходит с кодом 2.
2. `ExecStart=/usr/bin/python3 …` работал случайно: ровно там, где jsonschema и
   PyYAML оказались установлены системно. На чистом хосте служба упала бы на
   ImportError, объявив себя перед этим настроенной.

Проверяется не текст строки, а поведение: разбор аргументов настоящим парсером
фабрики и отказ обёртки без подготовленного окружения.
"""
from __future__ import annotations

import os
import re
import shlex
import subprocess

import pytest

from factory.paths import PATHS

UNIT_DIR = PATHS.automation / "host" / "systemd"
UNITS = sorted(UNIT_DIR.glob("*.service"))


def _exec_lines(unit) -> list[str]:
    text = unit.read_text(encoding="utf-8")
    return [line.split("=", 1)[1] for line in text.splitlines() if line.startswith("ExecStart=")]


def _factory_argv(command: str) -> list[str] | None:
    """Аргументы `factory`, если строка запускает именно его."""
    tokens = shlex.split(command)
    for index, token in enumerate(tokens):
        if token.endswith("bin/factory"):
            return tokens[index + 1:]
        if token == "-m" and index + 1 < len(tokens) and tokens[index + 1] == "factory":
            return tokens[index + 2:]
    return None


@pytest.mark.parametrize("unit", UNITS, ids=lambda p: p.name)
def test_factory_arguments_actually_parse(unit) -> None:
    """Строку ExecStart разбирает настоящий парсер фабрики, а не глазомер."""
    from factory.cli import main

    for command in _exec_lines(unit):
        argv = _factory_argv(command)
        if argv is None:
            continue
        # `--help` печатает и выходит; нам нужен только разбор, поэтому
        # проверяем через сам парсер, не выполняя команду.
        import argparse
        import contextlib
        import io

        with contextlib.redirect_stderr(io.StringIO()) as err:
            try:
                # SystemExit(2) — это и есть «аргументы не разобрались».
                main([*argv, "--help"])
            except SystemExit as exc:
                assert exc.code != 2, (
                    f"{unit.name}: argparse отверг «{' '.join(argv)}»: {err.getvalue().strip()[-200:]}"
                )
            except argparse.ArgumentError as exc:  # pragma: no cover
                pytest.fail(f"{unit.name}: {exc}")


@pytest.mark.parametrize("unit", UNITS, ids=lambda p: p.name)
def test_global_json_flag_precedes_the_subcommand(unit) -> None:
    """`--json` глобальный: после имени подкоманды он не распознаётся."""
    for command in _exec_lines(unit):
        argv = _factory_argv(command)
        if argv is None or "--json" not in argv:
            continue
        json_at = argv.index("--json")
        subcommands = {"analytics", "validate", "plan", "build", "verify", "status", "report"}
        first_sub = next((i for i, a in enumerate(argv) if a in subcommands), len(argv))
        assert json_at < first_sub, (
            f"{unit.name}: --json стоит после подкоманды — argparse ответит "
            f"«unrecognized arguments: --json». Строка: {' '.join(argv)}"
        )


def test_the_broken_argument_order_really_fails() -> None:
    """Доказательство, что проверка выше стережёт настоящий отказ, а не фантом."""
    import contextlib
    import io

    from factory.cli import main

    with contextlib.redirect_stderr(io.StringIO()) as err, pytest.raises(SystemExit) as excinfo:
        main(["analytics", "status", "--json"])
    assert excinfo.value.code == 2
    assert "unrecognized arguments" in err.getvalue()


def test_the_correct_argument_order_parses() -> None:
    import contextlib
    import io

    from factory.cli import main

    with contextlib.redirect_stdout(io.StringIO()), pytest.raises(SystemExit) as excinfo:
        main(["--json", "analytics", "status", "--help"])
    assert excinfo.value.code == 0


@pytest.mark.parametrize("unit", UNITS, ids=lambda p: p.name)
def test_units_never_run_a_bare_system_interpreter(unit) -> None:
    """Служба запускается подготовленным окружением, а не тем, что нашлось в PATH."""
    for command in _exec_lines(unit):
        assert not re.match(r"^/usr/bin/python3?\b", command), (
            f"{unit.name}: ExecStart идёт через системный python. Нужен bin/factory "
            f"или bin/seo-operator — они берут интерпретатор из .venv. Строка: {command}"
        )
        assert not command.startswith("python"), f"{unit.name}: {command}"


@pytest.mark.parametrize("unit", UNITS, ids=lambda p: p.name)
def test_units_forbid_falling_back_to_system_python(unit) -> None:
    text = unit.read_text(encoding="utf-8")
    if not any(w in text for w in ("bin/factory", "bin/seo-operator")):
        return
    assert "Environment=FACTORY_REQUIRE_VENV=1" in text, (
        f"{unit.name}: без FACTORY_REQUIRE_VENV=1 обёртка молча откатится на системный python"
    )


@pytest.mark.parametrize("wrapper", ["bin/factory", "bin/seo-operator"], ids=lambda w: w)
def test_wrapper_refuses_to_fall_back_when_required(wrapper) -> None:
    """Обёртка обязана отказаться, а не «как-нибудь запуститься»."""
    path = PATHS.root / wrapper
    assert os.access(path, os.X_OK), f"{wrapper} не исполняемый"
    result = subprocess.run(
        [str(path), "--help"],
        env={**os.environ, "PY": "/nonexistent/python", "FACTORY_REQUIRE_VENV": "1"},
        capture_output=True, text=True, timeout=60, check=False,
    )
    assert result.returncode == 78, result.stderr[-300:]
    assert "FACTORY_REQUIRE_VENV" in result.stderr


@pytest.mark.parametrize("wrapper", ["bin/factory", "bin/seo-operator"], ids=lambda w: w)
def test_wrapper_falls_back_instead_of_refusing_without_the_flag(wrapper) -> None:
    """Без флага обёртка не отказывается, а пробует системный интерпретатор.

    Проверяется именно решение обёртки, а не то, что найденный интерпретатор
    доедет до конца. Первая версия теста требовала returncode == 0 и проходила
    локально ровно потому, что jsonschema и PyYAML стояли системно — то есть
    закрепляла ту самую случайность, против которой написан весь этот код.
    На CI, где зависимости живут в .venv, она сразу покраснела.
    """
    result = subprocess.run(
        [str(PATHS.root / wrapper), "--help"],
        env={k: v for k, v in os.environ.items() if k not in {"FACTORY_REQUIRE_VENV"}}
        | {"PY": "/nonexistent/python"},
        capture_output=True, text=True, timeout=60, check=False,
    )
    assert result.returncode != 78, (
        "без FACTORY_REQUIRE_VENV обёртка не должна отказываться с EX_CONFIG"
    )
    assert "FACTORY_REQUIRE_VENV" not in result.stderr


@pytest.mark.parametrize("wrapper", ["bin/factory", "bin/seo-operator"], ids=lambda w: w)
def test_wrapper_uses_the_virtualenv_when_it_exists(wrapper) -> None:
    """Нормальный путь: есть .venv — обёртка запускается и доходит до конца."""
    venv_python = PATHS.root / ".venv" / "bin" / "python"
    if not os.access(venv_python, os.X_OK):
        pytest.skip("в этом дереве нет .venv")
    result = subprocess.run(
        [str(PATHS.root / wrapper), "--help"],
        env={k: v for k, v in os.environ.items() if k not in {"FACTORY_REQUIRE_VENV", "PY"}},
        capture_output=True, text=True, timeout=60, check=False,
    )
    assert result.returncode == 0, result.stderr[-300:]


# --------------------------------------------------------------------------
# Пути внутри unit'а обязаны указывать в одно дерево
# --------------------------------------------------------------------------
ROOT_RE = re.compile(r"/srv/site-factory/[A-Za-z0-9._-]+")


@pytest.mark.parametrize("unit", UNITS, ids=lambda p: p.name)
def test_all_paths_inside_a_unit_share_one_root(unit) -> None:
    """WorkingDirectory, ExecStart и ReadWritePaths — одно дерево, а не разные.

    Расхождение не приводит к отказу: служба запускается и молча исполняет код
    из чужого worktree, который обычно стоит на другой ветке. Такой сбой
    выглядит как «аналитика работает неправильно», а не как ошибка установки.
    """
    text = unit.read_text(encoding="utf-8")
    roots = set()
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("#") or "=" not in stripped:
            continue
        key = stripped.split("=", 1)[0]
        if key not in {"WorkingDirectory", "ExecStart", "ExecStop", "ReadWritePaths"}:
            continue
        roots.update(ROOT_RE.findall(stripped))
    assert len(roots) <= 1, (
        f"{unit.name}: пути ведут в разные деревья {sorted(roots)} — служба будет "
        "исполнять код не из того worktree, из которого её ставили"
    )


def test_installer_substitutes_the_actual_repository_root() -> None:
    """Шаблоны зашивают канонический путь; установщик обязан его подменять.

    Без подмены установка из review-worktree даёт unit, у которого
    WorkingDirectory указывает в одно дерево, а ExecStart — в другое.
    """
    installer = (PATHS.automation / "host" / "install-units.sh").read_text(encoding="utf-8")
    assert "REPO_ROOT=" in installer
    assert "TEMPLATE_ROOT=" in installer
    assert re.search(r"sed\s+\"s#\$\{TEMPLATE_ROOT\}#\$\{REPO_ROOT\}#g\"", installer), (
        "установщик копирует unit'ы дословно — пути шаблона останутся зашитыми"
    )


def test_installer_refuses_without_a_virtualenv() -> None:
    """Unit'ы требуют .venv; установщик обязан сказать об этом до установки."""
    installer = (PATHS.automation / "host" / "install-units.sh").read_text(encoding="utf-8")
    assert ".venv/bin/python" in installer
    assert "exit 78" in installer
