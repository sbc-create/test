"""Проверка порядка запуска: правила не должны осуждать верное поведение.

Инструмент сделан потому, что правила расхода Actions нарушаются МОЛЧА: ни
один прогон не падает из-за того, что он лишний. Проверяются четыре вида
подмены, и первая уже случилась при первом же прогоне самого инструмента:

* **верное поведение за нарушение** — `deploy.yml` идёт только на `main` и
  публикует набор; `cancel-in-progress: false` там правильно, а правило
  записало его в нарушители. Теперь правило смотрит, покрывает ли процесс
  рабочие ветви;
* **нарушение за соблюдение** — отсутствие `concurrency` у процесса, который
  идёт по рабочим ветвям, обязано быть нарушением: 64,2 % минут квоты 13.10
  ушли в прогоны, вытесненные новым коммитом;
* **непонятное за безопасное** — нечитаемый YAML или отсутствие pyyaml дают
  `НЕ ИЗМЕРЕНО` и код 2, а не «соблюдено»;
* **редкое расписание за частое** — запись cron, которую разобрать нельзя,
  считается нарушением: ошибиться в сторону лишнего прогона дороже.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

КОРЕНЬ = Path(__file__).resolve().parents[2]
ИСТОЧНИК = КОРЕНЬ / "automation" / "local" / "workflow-policy-check.py"
pytest.importorskip("yaml")


def _модуль():
    спец = importlib.util.spec_from_file_location("workflow_policy", ИСТОЧНИК)
    м = importlib.util.module_from_spec(спец)
    sys.modules["workflow_policy"] = м
    спец.loader.exec_module(м)
    return м


@pytest.fixture(scope="module")
def пп():
    return _модуль()


ХОРОШИЙ = """
name: CI
on:
  push:
    branches: ['main', 'claude/**']
    paths-ignore: ['docs/**', '**/*.md']
  pull_request:
    types: [opened]
    paths-ignore: ['docs/**', '**/*.md']
concurrency:
  group: ci-${{ github.ref }}
  cancel-in-progress: ${{ github.ref != 'refs/heads/main' }}
jobs:
  verify:
    runs-on: ubuntu-latest
    timeout-minutes: 20
    steps: [{run: echo ok}]
"""

ТОЛЬКО_MAIN = """
name: Deploy
on:
  push:
    branches: [main]
    paths-ignore: ['docs/**', '**/*.md']
  workflow_dispatch:
concurrency:
  group: deploy-${{ github.ref }}
  cancel-in-progress: false
jobs:
  publish:
    runs-on: ubuntu-latest
    timeout-minutes: 20
    steps: [{run: echo ok}]
"""


def _исход(строки, правило: str) -> tuple[str, str]:
    for п, и, пояснение in строки:
        if п == правило:
            return и, пояснение
    raise AssertionError(f"правило {правило} не проверялось")


def test_хороший_процесс_проходит_все_правила(пп):
    строки = пп.проверить(ХОРОШИЙ)
    нарушения = [(п, т) for п, и, т in строки if и != пп.СОБЛЮДЕНО]
    assert not нарушения, f"ложные нарушения: {нарушения}"


def test_процесс_только_на_main_не_обязан_отменять(пп):
    """Та самая ошибка: публикацию на main обрывать нельзя."""
    исход, пояснение = _исход(пп.проверить(ТОЛЬКО_MAIN), "ОТМЕНА")
    assert исход == пп.СОБЛЮДЕНО, f"верное поведение названо нарушением: {пояснение}"
    assert "только на main" in пояснение


def test_отсутствие_отмены_на_рабочих_ветвях_это_нарушение(пп):
    текст = ХОРОШИЙ.replace(
        "  cancel-in-progress: ${{ github.ref != 'refs/heads/main' }}",
        "  cancel-in-progress: false")
    исход, пояснение = _исход(пп.проверить(текст), "ОТМЕНА")
    assert исход == пп.НАРУШЕНО
    assert "рабочих" in пояснение


def test_отмена_включённая_и_на_main_это_нарушение(пп):
    текст = ХОРОШИЙ.replace(
        "  cancel-in-progress: ${{ github.ref != 'refs/heads/main' }}",
        "  cancel-in-progress: true")
    исход, пояснение = _исход(пп.проверить(текст), "ОТМЕНА")
    assert исход == пп.НАРУШЕНО
    assert "main" in пояснение


def test_группа_без_ветви_это_нарушение(пп):
    текст = ХОРОШИЙ.replace("  group: ci-${{ github.ref }}", "  group: ci")
    исход, пояснение = _исход(пп.проверить(текст), "ОТМЕНА")
    assert исход == пп.НАРУШЕНО
    assert "ветвь" in пояснение


def test_без_paths_ignore_правка_документации_стоит_прогона(пп):
    текст = ХОРОШИЙ.replace("    paths-ignore: ['docs/**', '**/*.md']\n", "", 1)
    исход, пояснение = _исход(пп.проверить(текст), "ДОКУМЕНТЫ")
    assert исход == пп.НАРУШЕНО
    assert "docs/**" in пояснение


def test_белый_список_путей_документацию_уже_исключает(пп):
    текст = ХОРОШИЙ.replace("    paths-ignore: ['docs/**', '**/*.md']",
                            "    paths: ['src/**']")
    исход, _ = _исход(пп.проверить(текст), "ДОКУМЕНТЫ")
    assert исход == пп.СОБЛЮДЕНО, "белый список путей не зачтён"


def test_без_предела_времени_нарушение(пп):
    текст = ХОРОШИЙ.replace("    timeout-minutes: 20\n", "")
    исход, пояснение = _исход(пп.проверить(текст), "ПРЕДЕЛ")
    assert исход == пп.НАРУШЕНО
    assert "verify" in пояснение


def test_pull_request_без_types_при_push_на_рабочие_это_дубль(пп):
    текст = ХОРОШИЙ.replace("    types: [opened]\n", "")
    исход, пояснение = _исход(пп.проверить(текст), "ДУБЛЬ")
    assert исход == пп.НАРУШЕНО
    assert "дважды" in пояснение


def test_synchronize_это_дубль(пп):
    текст = ХОРОШИЙ.replace("    types: [opened]",
                            "    types: [opened, synchronize]")
    исход, пояснение = _исход(пп.проверить(текст), "ДУБЛЬ")
    assert исход == пп.НАРУШЕНО
    assert "synchronize" in пояснение


def test_тяжёлое_задание_по_коммиту_это_нарушение(пп):
    текст = ХОРОШИЙ.replace("""  verify:
    runs-on: ubuntu-latest
    timeout-minutes: 20
    steps: [{run: echo ok}]""",
                            """  verify:
    runs-on: ubuntu-latest
    timeout-minutes: 20
    steps: [{run: echo ok}]
  emulator:
    runs-on: ubuntu-latest
    timeout-minutes: 45
    steps: [{run: bash tools/e2e/run_device.sh phone}]""")
    исход, пояснение = _исход(пп.проверить(текст), "ТЯЖЁЛОЕ")
    assert исход == пп.НАРУШЕНО
    assert "emulator" in пояснение


def test_тяжёлое_задание_по_условию_ручного_запуска_допустимо(пп):
    текст = ХОРОШИЙ.replace("""  verify:
    runs-on: ubuntu-latest
    timeout-minutes: 20
    steps: [{run: echo ok}]""",
                            """  verify:
    runs-on: ubuntu-latest
    timeout-minutes: 20
    steps: [{run: echo ok}]
  emulator:
    if: github.event_name == 'workflow_dispatch' && inputs.e2e
    runs-on: ubuntu-latest
    timeout-minutes: 45
    steps: [{run: bash tools/e2e/run_device.sh phone}]""")
    исход, пояснение = _исход(пп.проверить(текст), "ТЯЖЁЛОЕ")
    assert исход == пп.СОБЛЮДЕНО, пояснение


def test_расписание_чаще_суток_это_нарушение(пп):
    текст = ХОРОШИЙ.replace("on:\n", "on:\n  schedule:\n    - cron: '*/20 * * * *'\n")
    текст = текст.replace("""  verify:
    runs-on: ubuntu-latest
    timeout-minutes: 20
    steps: [{run: echo ok}]""",
                          """  verify:
    runs-on: ubuntu-latest
    timeout-minutes: 20
    steps: [{run: bash tools/e2e/run_device.sh phone}]""")
    исход, пояснение = _исход(пп.проверить(текст), "ТЯЖЁЛОЕ")
    assert исход == пп.НАРУШЕНО
    assert "чаще раза в сутки" in пояснение


def test_суточное_расписание_допустимо(пп):
    assert пп._не_чаще_суток("17 6 * * *") is True
    assert пп._не_чаще_суток("0 7 * * *") is True
    assert пп._не_чаще_суток("*/20 * * * *") is False
    assert пп._не_чаще_суток("0 */2 * * *") is False
    assert пп._не_чаще_суток("0 7,19 * * *") is False
    assert пп._не_чаще_суток("непонятно") is False, (
        "неразобранная запись должна считаться нарушением, а не «наверное, редко»")


def test_битый_yaml_это_не_соблюдено(пп):
    строки = пп.проверить("name: [незакрытая\n  скобка")
    assert all(и == пп.НЕ_ИЗМЕРЕНО for _, и, _ in строки)


def test_не_похоже_на_процесс_это_не_соблюдено(пп):
    строки = пп.проверить("- просто\n- список\n")
    assert all(и == пп.НЕ_ИЗМЕРЕНО for _, и, _ in строки)


def test_шаблон_ячейки_правила_соблюдает(пп):
    """Шаблон, по которому заводятся все ячейки, обязан быть образцом."""
    строки = пп.проверить(пп.шаблон_ячейки())
    нарушения = [(п, т) for п, и, т in строки if и != пп.СОБЛЮДЕНО]
    assert not нарушения, f"шаблон ячейки нарушает правила: {нарушения}"


def test_свои_рабочие_процессы_правила_соблюдают(пп):
    """Инструмент применяется и к самому репозиторию, а не только к чужим."""
    for файл in sorted((КОРЕНЬ / ".github" / "workflows").glob("*.yml")):
        строки = пп.проверить(файл.read_text(encoding="utf-8"))
        нарушения = [(п, т) for п, и, т in строки if и != пп.СОБЛЮДЕНО]
        assert not нарушения, f"{файл.name}: {нарушения}"


def test_код_возврата_различает_три_исхода(пп, tmp_path, capsys):
    хороший = tmp_path / "ok.yml"
    хороший.write_text(ХОРОШИЙ, encoding="utf-8")
    assert пп.главная(["--file", str(хороший)]) == 0
    плохой = tmp_path / "bad.yml"
    плохой.write_text(ХОРОШИЙ.replace("    timeout-minutes: 20\n", ""),
                      encoding="utf-8")
    assert пп.главная(["--file", str(плохой)]) == 1
    битый = tmp_path / "broken.yml"
    битый.write_text("name: [незакрытая", encoding="utf-8")
    assert пп.главная(["--file", str(битый)]) == 2
    capsys.readouterr()
