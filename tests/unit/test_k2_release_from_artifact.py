"""REQ-K2-RELEASE-PROVENANCE: на витрину кладётся собранный артефакт.

Измерено 2026-10-18 на восьми витринах узла K2: в `/healthz` `release_id` =
`build_id` = `worktree-unbuilt`, а в `config/template-manifest.json` их
репозиториев это значение-заглушка, и `artifact_sha256`, `code_file_sha256`,
`source_commit`, `built_at` — пустые. В каталоге выложенного выпуска не было
`release-manifest.json`, хотя у исправно установленной ячейки Yummy он есть.

Причина: сценарий выпуска клонировал бандл прямо в каталог выпуска и никогда
не вызывал `tools/build_release.py`. Штамп манифеста ставит именно сборка, и
ставит его ВНУТРЬ артефакта — в рабочее дерево он не попадает.

Почему это дефект, а не особенность поля: происхождение выложенного кода
ничем не подтверждено, и `runtime_digest_match` в `/healthz` не может быть
верным — сравнивать нечего с чем. Связь «коммит → артефакт → живой сайт»
обрывалась на последнем звене.

Подсказку дала соседняя линия, у которой `worktree-unbuilt` — осознанная
заглушка несобранного дерева, а на живой витрине стоит настоящий
`<коммит>-<site_id>`.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

СЦЕНАРИЙ = (Path(__file__).resolve().parents[2] / "automation" / "host"
            / "k2-release-code.sh")
ТЕКСТ = СЦЕНАРИЙ.read_text(encoding="utf-8")


def место(кусок: str) -> int:
    и = ТЕКСТ.find(кусок)
    assert и >= 0, f"в сценарии нет {кусок!r}"
    return и


def test_выпуск_собирается_сборщиком_витрины():
    """Не копией логики штампа, а самим сборщиком.

    Копия разошлась бы со сборщиком при первой правке, и это ровно тот
    случай, когда проверка зеленеет, а витрина называет чужие цифры.
    """
    assert "tools/build_release.py" in ТЕКСТ
    assert "штамп" not in ТЕКСТ.split("tools/build_release.py")[0][-400:], (
        "перед сборкой появился самодельный штамп")


def test_в_выпуск_распаковывается_артефакт():
    assert 'tar -xzf "$art" -C "$release"' in ТЕКСТ
    assert "release-manifest.json" in ТЕКСТ, "опись выпуска не переносится"


def test_порядок_сборка_потом_переключение():
    """Собрать и проверить штамп обязано ДО подмены current."""
    assert (место("tools/build_release.py")
            < место('if [ -n "$stamp_problem" ]')
            < место('ln -sfn "$release" "$current_link"'))


def test_без_сборщика_выпуск_не_делается():
    """Отказ закрытый: бандл без сборщика — это выпуск без происхождения."""
    кусок = ТЕКСТ[место('if [ ! -f "$work/repo/tools/build_release.py" ]'):]
    кусок = кусок[:кусок.index("\n  fi\n")]
    assert "exit 1" in кусок


def test_непроставленный_штамп_останавливает_до_мутаций():
    кусок = ТЕКСТ[место('if [ -n "$stamp_problem" ]'):]
    кусок = кусок[:кусок.index("\n  fi\n")]
    assert "exit 1" in кусок
    assert "непрослеживаемый код на витрину не кладу" in кусок
    # Отрицательный контроль: отказ стоит ДО переключения ссылки, иначе
    # витрина осталась бы на непроверенном выпуске.
    assert место('if [ -n "$stamp_problem" ]') < место(
        'ln -sfn "$release" "$current_link"')


def test_временный_каталог_удаляется_только_свой():
    """`rm -rf` по переменной допустим лишь с проверкой её значения."""
    assert 'case "$work" in /tmp/*) rm -rf "$work" ;; esac' in ТЕКСТ


def test_плеер_по_прежнему_переносится_из_прежнего_выпуска():
    """Сборщик исключает config/player.json поимённо, и это важно сохранить:
    publisher_id в артефакт не попадает, а служба без файла не стартует."""
    assert место('player_src="$old_release/config/player.json"') > 0
    assert место("player_src") < место("tools/build_release.py")


@pytest.fixture(scope="module")
def проверка_штампа() -> str:
    """Python из heredoc сценария — тот же код, что исполняется на узле."""
    кусок = ТЕКСТ[место('stamp_problem="$(python3 -'):]
    начало = кусок.index("<<'PY'\n") + len("<<'PY'\n")
    конец = кусок.index("\nPY\n", начало)
    тело = кусок[начало:конец]
    assert "worktree-unbuilt" in тело, "извлёкся не тот кусок"
    return тело


def _запуск(код: str, манифест, tmp_path: Path) -> str:
    файл = tmp_path / "template-manifest.json"
    файл.write_text(манифест if isinstance(манифест, str)
                    else json.dumps(манифест, ensure_ascii=False),
                    encoding="utf-8")
    г = subprocess.run([sys.executable, "-", str(файл)], input=код,
                       capture_output=True, text=True)
    assert г.returncode == 0, г.stderr
    return г.stdout.strip()


ПОЛНЫЙ = {"build_id": "abc123abc123-lords-13",
          "artifact_sha256": "a" * 64,
          "code_file_sha256": "b" * 64,
          "source_commit": "c" * 40,
          "built_at": "2026-10-18T00:00:00+00:00"}


def test_полный_штамп_принимается(проверка_штампа, tmp_path):
    assert _запуск(проверка_штампа, ПОЛНЫЙ, tmp_path) == ""


def test_заглушка_не_принимается(проверка_штампа, tmp_path):
    """Тот случай, что измерен на живых витринах."""
    манифест = dict(ПОЛНЫЙ, build_id="worktree-unbuilt")
    assert "worktree-unbuilt" in _запуск(проверка_штампа, манифест, tmp_path)


@pytest.mark.parametrize("поле", sorted(ПОЛНЫЙ))
def test_пустое_поле_штампа_не_принимается(проверка_штампа, tmp_path, поле):
    манифест = dict(ПОЛНЫЙ, **{поле: ""})
    вывод = _запуск(проверка_штампа, манифест, tmp_path)
    assert поле in вывод, f"пустое {поле} прошло как проставленный штамп"


def test_нечитаемый_манифест_не_принимается(проверка_штампа, tmp_path):
    assert "не читается" in _запуск(проверка_штампа, "не json", tmp_path)
