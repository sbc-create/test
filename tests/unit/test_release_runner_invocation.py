"""Повторный запуск завершённого systemd oneshot действительно создаёт новую InvocationID.

Дефект LORDS-RELEASE-INVOCATION-REUSE-32. Release-runner читал InvocationID до
запуска, запускал юнит сборки и сравнивал значение после. У неактивного юнита
InvocationID пуст, а при `CollectMode=inactive` systemd выгружает юнит сразу
после завершения — поэтому «до» и «после» оказывались одинаково пустыми.
Runner объявлял, что сборка не запускалась, и выбрасывал готовый артефакт:
рендер отработал 173 минуты, выдал 61 733 страницы, а выкладка завершилась
отказом «юнит сборки не запускался заново».

Проверки идут на НАСТОЯЩЕМ systemd — на пользовательской шине, а не на
подделке. Подделка воспроизвела бы мои представления о поведении systemd, а
дефект состоял ровно в том, что представления были неверны.

Первая проверка воспроизводит дефект: она показывает, что сравнение «до и
после» не отличает состоявшийся прогон от несостоявшегося. Остальные
доказывают, что исправленная последовательность отличает.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import textwrap
import time
import uuid
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
LIB = ROOT / "automation" / "host" / "lords-unit-launch.sh"
USER_UNITS = Path.home() / ".config" / "systemd" / "user"


def _пользовательская_шина_доступна() -> bool:
    if shutil.which("systemctl") is None:
        return False
    if not os.environ.get("XDG_RUNTIME_DIR"):
        return False
    return subprocess.run(
        ["systemctl", "--user", "is-system-running"],
        capture_output=True, text=True).returncode in (0, 1)


pytestmark = pytest.mark.skipif(
    not _пользовательская_шина_доступна(),
    reason="пользовательская шина systemd недоступна: проверять нечем")


def _uctl(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["systemctl", "--user", *args],
                          capture_output=True, text=True)


def _показать(unit: str, свойство: str) -> str:
    return _uctl("show", "-p", свойство, "--value", unit).stdout.strip()


def _завести_юнит(имя: str, exec_start: str) -> str:
    """Одноразовый юнит с тем же устройством, что и юнит сборки Lords."""
    USER_UNITS.mkdir(parents=True, exist_ok=True)
    unit = f"{имя}.service"
    (USER_UNITS / unit).write_text(textwrap.dedent(f"""\
        [Unit]
        Description=проверка запуска oneshot ({имя})

        [Service]
        Type=oneshot
        RemainAfterExit=no
        CollectMode=inactive
        ExecStart={exec_start}
        """), encoding="utf-8")
    _uctl("daemon-reload")
    return unit


def _убрать_юнит(unit: str) -> None:
    _uctl("stop", unit)
    _uctl("reset-failed", unit)
    (USER_UNITS / unit).unlink(missing_ok=True)
    _uctl("daemon-reload")


@pytest.fixture()
def маркер(tmp_path: Path) -> Path:
    return tmp_path / "выполнено"


@pytest.fixture()
def юнит(маркер: Path):
    имя = f"lords-launch-probe-{uuid.uuid4().hex[:8]}"
    unit = _завести_юнит(
        имя, f"/bin/bash -c 'sleep 6; /usr/bin/touch {маркер}'")
    yield unit
    _убрать_юнит(unit)


def _запустить_библиотеку(скрипт: str) -> subprocess.CompletedProcess:
    """Прогон функций библиотеки на пользовательской шине."""
    полный = f'SYSTEMCTL="systemctl --user"\n. "{LIB}"\n{скрипт}\n'
    return subprocess.run(["bash", "-c", полный], capture_output=True, text=True)


class TestДефектВоспроизводится:
    def test_после_завершения_сравнение_до_и_после_ничего_не_доказывает(self, юнит, маркер):
        """Прежнее условие runner'а не отличает прогон от его отсутствия."""
        до = _показать(юнит, "InvocationID")
        assert до == "", "юнит должен начинать проверку неактивным и без InvocationID"

        assert _uctl("start", юнит).returncode == 0
        assert маркер.exists(), "ExecStart не выполнился — проверять нечего"

        после = _показать(юнит, "InvocationID")
        assert после == до, (
            "если InvocationID после завершения перестал быть пустым, "
            "дефект воспроизводится иначе и проверку нужно переписать")

    def test_result_и_статус_после_выгрузки_являются_значениями_по_умолчанию(self, юнит):
        """`Result=success` у ни разу не запускавшегося юнита — не свидетельство."""
        assert _показать(юнит, "Result") == "success"
        assert _показать(юнит, "ExecMainStatus") == "0"
        assert _показать(юнит, "ExecMainStartTimestamp") in ("n/a", "")


class TestИсправленныйЗапуск:
    def test_новая_invocation_доказывается_во_время_работы(self, юнит, маркер):
        r = _запустить_библиотеку(
            f'unit_start_confirmed "{юнит}" 60 || exit 1\n'
            'printf "RUN_ID=%s\\n" "${UNIT_RUN_ID}"')
        assert r.returncode == 0, r.stderr
        run_id = r.stdout.strip().split("RUN_ID=", 1)[-1].strip()
        assert len(run_id) == 32, f"InvocationID не получен: {r.stdout!r} {r.stderr!r}"

        # Тот же прогон обязан довести дело до конца и оставить след.
        r2 = _запустить_библиотеку(f'unit_wait "{юнит}" 120 30 ""')
        assert r2.returncode == 0, r2.stderr
        assert маркер.exists(), "юнит завершился, но ExecStart следа не оставил"

    def test_повторный_запуск_даёт_другую_invocation(self, юнит):
        первый = _запустить_библиотеку(
            f'unit_start_confirmed "{юнит}" 60 && printf "%s" "${{UNIT_RUN_ID}}"')
        assert первый.returncode == 0, первый.stderr
        _запустить_библиотеку(f'unit_wait "{юнит}" 120 30 ""')

        второй = _запустить_библиотеку(
            f'unit_start_confirmed "{юнит}" 60 && printf "%s" "${{UNIT_RUN_ID}}"')
        assert второй.returncode == 0, второй.stderr
        _запустить_библиотеку(f'unit_wait "{юнит}" 120 30 ""')

        assert первый.stdout.strip() and второй.stdout.strip()
        assert первый.stdout.strip() != второй.stdout.strip(), (
            "второй запуск получил ту же InvocationID: нового прогона не было")

    def test_запуск_поверх_работающего_юнита_проходит(self, юнит):
        """restart вместо start: уже работающий юнит не должен ронять попытку."""
        assert _uctl("--no-block", "start", юнит).returncode == 0
        time.sleep(2)
        r = _запустить_библиотеку(
            f'unit_start_confirmed "{юнит}" 60 && printf "%s" "${{UNIT_RUN_ID}}"')
        assert r.returncode == 0, r.stderr
        assert len(r.stdout.strip()) == 32
        _запустить_библиотеку(f'unit_wait "{юнит}" 120 30 ""')


class TestОтказНаступаетБыстро:
    """Три часа ожидания вместо минуты — это и был способ потерять сутки.

    Граница здесь проходит не там, где я её сперва провёл. Юнит с
    несуществующим `ExecStart` СОЗДАЁТСЯ: systemd выдаёт ему InvocationID и
    только потом переводит в failed. Значит `unit_start_confirmed` обязан
    сообщить об успехе — процесс действительно начат, — а отказ обнаруживает
    `unit_wait`. Проверка написана по этому факту, а не по моему исходному
    представлению: первая редакция ждала отказа от `unit_start_confirmed` и
    падала на настоящем systemd.
    """

    def test_упавший_процесс_ловится_ожиданием_а_не_запуском(self):
        имя = f"lords-launch-fail-{uuid.uuid4().hex[:8]}"
        unit = _завести_юнит(имя, "/nonexistent/binary")
        try:
            начало = time.monotonic()
            r = _запустить_библиотеку(
                f'unit_start_confirmed "{unit}" 60 || exit 2\n'
                f'unit_wait "{unit}" 120 30 "" || {{ printf "RESULT=%s\\n" "${{UNIT_RESULT}}"; exit 1; }}')
            прошло = time.monotonic() - начало
            assert r.returncode == 1, (
                f"ожидание не отличило упавший процесс: код {r.returncode}, {r.stderr}")
            assert "RESULT=" in r.stdout and "RESULT=success" not in r.stdout, r.stdout
            assert прошло < 60, f"отказ обнаружен за {прошло:.0f} с"
        finally:
            _убрать_юнит(unit)

    def test_несостоявшийся_запуск_обнаруживается_за_минуту(self):
        """Юнита нет вовсе: нового процесса не будет никогда."""
        начало = time.monotonic()
        r = _запустить_библиотеку(
            f'unit_start_confirmed "lords-нет-такого-{uuid.uuid4().hex[:8]}.service" 60')
        прошло = time.monotonic() - начало
        assert r.returncode != 0, "запуск несуществующего юнита объявлен состоявшимся"
        assert прошло < 60, f"отказ обнаружен за {прошло:.0f} с"
        assert r.stderr.strip(), "отказ без диагностики"

    def test_упавший_юнит_сбрасывается_перед_новым_запуском(self):
        имя = f"lords-launch-reset-{uuid.uuid4().hex[:8]}"
        unit = _завести_юнит(имя, "/bin/false")
        try:
            _uctl("start", unit)
            assert _показать(unit, "ActiveState") == "failed"
            r = _запустить_библиотеку(f'unit_stop_and_reset "{unit}" 60')
            assert r.returncode == 0, r.stderr
            assert _показать(unit, "ActiveState") != "failed", (
                "reset-failed не выполнен: следующий запуск упрётся в прежний отказ")
        finally:
            _убрать_юнит(unit)
