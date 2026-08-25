"""REQ-LORDS-STAGING: встроенные Python-фрагменты root-сценария исполнимы на хосте.

Фрагменты внутри `automation/host/lords-staging-apply.sh` не видит ни один
обычный прогон: `bash -n` разбирает только оболочку, а pytest импортирует
модули фабрики, но не строки, которые сценарий передаёт интерпретатору через
`-c`. Из-за этого синтаксическая ошибка в них доживала до root-запуска.

Так и вышло: `f"{s[\"site_id\"]}"` — обратный слеш внутри выражения f-string, а
это `SyntaxError` вплоть до Python 3.11 включительно. Разрешено оно только с
3.12 (PEP 701), тогда как systemd на хосте запускает `/usr/bin/python3`.

Поэтому тест не читает текст и не проверяет `bash -n`, а **исполняет** каждый
фрагмент: сначала компилирует его тем же интерпретатором, что стоит в
`ExecStart` юнита, затем скармливает настоящий `staging.json` и сверяет вывод
с тем, что сценарий от него ждёт.
"""

from __future__ import annotations

import re
import shutil
import subprocess
import sys

import pytest

from factory.lords import staging as staging_mod
from factory.paths import PATHS

SCRIPT = PATHS.root / "automation/host/lords-staging-apply.sh"

# Интерпретатор из ExecStart юнита. Он, а не интерпретатор тестов, решает,
# исполним ли фрагмент на хосте.
HOST_PYTHON = "/usr/bin/python3"

# Фрагмент — это то, что стоит между `"${PY}" -c '` и закрывающей кавычкой.
FRAGMENT = re.compile(r"""\$\{PY\}"\s+-c\s+'(.*?)^'""", re.S | re.M)


def fragments() -> list[str]:
    return FRAGMENT.findall(SCRIPT.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def staging(tmp_path_factory):
    """Настоящая конфигурация стенда, собранная фабрикой, а не заглушка.

    Возвращает путь к staging.json и его содержимое: сценарий читает именно
    этот файл, и проверять фрагменты имеет смысл на нём.
    """
    directory = tmp_path_factory.mktemp("staging")
    summary = staging_mod.build_staging(output=directory)
    target = directory / "staging.json"
    assert target.is_file(), "build_staging не создал staging.json"
    return target, summary


def test_the_script_still_has_embedded_fragments():
    """Если фрагменты убрали, тест обязан это заметить, а не тихо опустеть."""
    assert len(fragments()) == 2, f"ожидалось два фрагмента, найдено {len(fragments())}"


def test_the_host_interpreter_is_present():
    assert shutil.which(HOST_PYTHON), f"на хосте нет {HOST_PYTHON}"


@pytest.mark.parametrize("index", range(2))
def test_fragment_compiles_under_the_host_interpreter(index):
    """Компиляция тем же python3, что стоит в ExecStart."""
    source = fragments()[index]
    result = subprocess.run(
        [HOST_PYTHON, "-c", "import sys; compile(sys.stdin.read(), '<fragment>', 'exec')"],
        input=source, capture_output=True, text=True, timeout=60,
    )
    assert result.returncode == 0, (
        f"фрагмент {index} не компилируется на {HOST_PYTHON}:\n{result.stderr}"
    )


@pytest.mark.parametrize("index", range(2))
def test_fragment_runs_under_the_host_interpreter(index, staging):
    """Фрагмент исполняется целиком и на настоящих данных."""
    source = fragments()[index]
    result = subprocess.run(
        [HOST_PYTHON, "-c", source, str(staging[0])],
        capture_output=True, text=True, timeout=60,
    )
    assert result.returncode == 0, (
        f"фрагмент {index} не исполняется на {HOST_PYTHON}:\n{result.stderr}"
    )
    assert result.stdout.strip(), f"фрагмент {index} ничего не напечатал"


def test_no_fragment_puts_a_backslash_inside_an_f_string_expression():
    """Прямой запрет на конструкцию, которая и сломала запуск.

    Проверяется не наличие подстроки, а сам разбор: экранированная кавычка
    внутри `{...}` в f-string — это ошибка синтаксиса до 3.12.
    """
    for index, source in enumerate(fragments()):
        for line in source.splitlines():
            if 'f"' not in line and "f'" not in line:
                continue
            for expression in re.findall(r"\{([^{}]*)\}", line):
                assert "\\" not in expression, (
                    f"фрагмент {index}: обратный слеш в выражении f-string: {expression!r}"
                )


def test_the_first_fragment_yields_the_rows_the_script_reads(staging):
    """Сценарий разбирает вывод через `IFS=$'\\t' read` на шесть полей."""
    source = fragments()[0]
    result = subprocess.run(
        [HOST_PYTHON, "-c", source, str(staging[0])],
        capture_output=True, text=True, timeout=60,
    )
    assert result.returncode == 0, result.stderr

    rows = [line for line in result.stdout.splitlines() if line]
    assert len(rows) == 3, f"сценарий ждёт три сайта, получено {len(rows)}"

    expected = staging[1]["sites"]
    for row, site in zip(rows, expected, strict=True):
        fields = row.split("\t")
        assert len(fields) == 6, f"ожидалось шесть полей, получено {len(fields)}: {row!r}"
        site_id, apex, www, port, unit, runtime_root = fields
        assert site_id == site["site_id"]
        assert apex == site["apex"]
        assert www == site["www"]
        assert port == str(site["port"])
        assert unit == site["unit"]
        assert runtime_root == site["runtime_root"]


def test_the_second_fragment_prints_one_readable_line_per_site(staging):
    source = fragments()[1]
    result = subprocess.run(
        [HOST_PYTHON, "-c", source, str(staging[0])],
        capture_output=True, text=True, timeout=60,
    )
    assert result.returncode == 0, result.stderr

    lines = [line for line in result.stdout.splitlines() if line.strip()]
    assert len(lines) == 3
    for line, site in zip(lines, staging[1]["sites"], strict=True):
        assert site["url"] in line
        assert site["site_id"] in line
        assert site["profile"] in line
        assert f":{site['port']}" in line


@pytest.mark.skipif(
    sys.version_info[:2] == (3, 10),
    reason="интерпретатор тестов и так 3.10 — сравнивать не с чем",
)
@pytest.mark.parametrize("index", range(2))
def test_fragment_also_runs_under_the_test_interpreter(index, staging):
    """Фрагмент не должен зависеть от версии: он обязан работать и здесь."""
    source = fragments()[index]
    result = subprocess.run(
        [sys.executable, "-c", source, str(staging[0])],
        capture_output=True, text=True, timeout=60,
    )
    assert result.returncode == 0, (
        f"фрагмент {index} не исполняется на {sys.executable}:\n{result.stderr}"
    )
