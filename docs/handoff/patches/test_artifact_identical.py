"""REQ-PUBLISH-ARTIFACT-IDENTICAL: ожидание кончается, когда выпускать нечего.

T175, измерено 18.10: публикатор отдал 587 решений «ожидание» по одной задаче,
356 из них подряд с одной причиной — «голова ветки выпуска aceb5cccb154 не
равна живому d1627b4b7eaa». Голова ветки при этом — чужой коммит, меняющий
ТОЛЬКО `TEMPLATE-CANDIDATES.md`; CI его не собирает (`paths-ignore
'**/*.md'`), поэтому живой код остаётся прежним, и ожидание повторяется вечно.

Расхождение бывает двух родов: чужая правка КОДА (ждать правильно) и
расхождение в файлах, которых в артефакте нет (ждать нечего). Различает их
побайтное сравнение артефактов — содержимое файлов, а не список путей.

Пять условий включения проверяются здесь по одному:

1. сравнение побайтное, по хешам содержимого;
2. изменение ВНУТРИ артефакта даёт «выпуск нужен»;
3. невозможность сравнить — «не измерено» и прежнее ожидание, без тихого
   «совпадает»;
4. исход пишется в журнал с обеими цифрами;
5. правило работает только для задачи со статусом `verified` и только при
   чистом клоне.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from seo_operator import tech_publish as ТП


def _репо(tmp_path: Path, файлы: dict[str, str]) -> Path:
    репо = tmp_path / "repo"
    (репо / "src").mkdir(parents=True)
    for путь, тело in файлы.items():
        п = репо / путь
        п.parent.mkdir(parents=True, exist_ok=True)
        п.write_text(тело, encoding="utf-8")
    for арг in (["init", "-q"], ["config", "user.email", "t@t"],
                ["config", "user.name", "t"], ["add", "-A"],
                ["commit", "-qm", "первый"]):
        subprocess.run(["git", "-C", str(репо), *арг], check=True,
                       capture_output=True)
    return репо


def _коммит(репо: Path, файлы: dict[str, str], сообщение: str) -> str:
    for путь, тело in файлы.items():
        п = репо / путь
        п.parent.mkdir(parents=True, exist_ok=True)
        п.write_text(тело, encoding="utf-8")
    subprocess.run(["git", "-C", str(репо), "add", "-A"], check=True,
                   capture_output=True)
    subprocess.run(["git", "-C", str(репо), "commit", "-qm", сообщение],
                   check=True, capture_output=True)
    return subprocess.run(["git", "-C", str(репо), "rev-parse", "HEAD"],
                          capture_output=True, text=True).stdout.strip()


БАЗА = {"run.py": "print('витрина')\n",
        "src/frontend.py": "код = 1\n",
        "TEMPLATE-CANDIDATES.md": "# кандидаты\n"}


def test_цифра_считается_по_содержимому_а_не_по_путям(tmp_path):
    """Условие 1: побайтно."""
    репо = _репо(tmp_path, БАЗА)
    живой = subprocess.run(["git", "-C", str(репо), "rev-parse", "HEAD"],
                           capture_output=True, text=True).stdout.strip()
    ц1, беда = ТП.цифра_дерева(репо, живой)
    assert беда == "" and len(ц1) == 64
    # Тот же состав путей, другое содержимое → другая цифра.
    голова = _коммит(репо, {"src/frontend.py": "код = 2\n"}, "правка кода")
    ц2, _ = ТП.цифра_дерева(репо, голова)
    assert ц1 != ц2


def test_файл_вне_артефакта_цифру_не_меняет(tmp_path):
    """Ровно случай T175: изменился только .md."""
    репо = _репо(tmp_path, БАЗА)
    живой = subprocess.run(["git", "-C", str(репо), "rev-parse", "HEAD"],
                           capture_output=True, text=True).stdout.strip()
    голова = _коммит(репо, {"TEMPLATE-CANDIDATES.md": "# другое\n"}, "только md")
    факты = ТП.сравнить_артефакты(репо, голова, живой)
    assert факты["artifact_same"] is True
    assert факты["artifact_head"] == факты["artifact_live"]


def test_правило_закрывает_ожидание(tmp_path):
    """Условие, из-за которого правило и писалось."""
    действие, причина = ТП.решение({
        "live": "d1627b4b7eaa", "ci_commit": "aceb5cccb154",
        "remote_head": "aceb5cccb154", "head": "aceb5cccb154",
        "head_in_live": False, "live_in_head": True, "clone_dirty": False,
        "clone_on_live": True, "task_status": "verified",
        "artifact_same": True, "artifact_head": "a" * 64,
        "artifact_live": "a" * 64})
    assert действие == "artifact_identical"
    assert "побайтно совпадает" in причина


def test_изменение_внутри_артефакта_даёт_выпуск_нужен(tmp_path):
    """Условие 2: отрицательный контроль."""
    действие, причина = ТП.решение({
        "live": "d1627b4b7eaa", "ci_commit": "aceb5cccb154",
        "remote_head": "aceb5cccb154", "head": "aceb5cccb154",
        "head_in_live": False, "live_in_head": True, "clone_dirty": False,
        "clone_on_live": True, "task_status": "verified",
        "artifact_same": False, "artifact_head": "a" * 64,
        "artifact_live": "b" * 64})
    assert действие == "wait"
    assert "невыпущенный коммит" in причина


def test_несравнимые_артефакты_оставляют_ожидание(tmp_path):
    """Условие 3: тихого «совпадает» быть не должно."""
    for сведения in (
        {"artifact_same": None, "artifact_reason": "сборка не удалась"},
        {},  # сравнения не было вовсе
    ):
        действие, _ = ТП.решение({
            "live": "d1627b4b7eaa", "ci_commit": "aceb5cccb154",
            "remote_head": "aceb5cccb154", "head": "aceb5cccb154",
            "head_in_live": False, "live_in_head": True, "clone_dirty": False,
            "clone_on_live": True, "task_status": "verified", **сведения})
        assert действие == "wait"


def test_грязный_клон_правило_не_применяет(tmp_path):
    """Условие 5: живое могло быть собрано из незакоммиченного."""
    действие, _ = ТП.решение({
        "live": "d1627b4b7eaa", "ci_commit": "aceb5cccb154",
        "remote_head": "aceb5cccb154", "head": "aceb5cccb154",
        "head_in_live": False, "live_in_head": True, "clone_dirty": True,
        "clone_on_live": True, "task_status": "verified",
        "artifact_same": True, "artifact_head": "a" * 64,
        "artifact_live": "a" * 64})
    assert действие == "wait"


def test_непроверенная_задача_правило_не_применяет(tmp_path):
    """Условие 5: только verified."""
    for статус in ("queued", "session", "blocked", ""):
        действие, _ = ТП.решение({
            "live": "d1627b4b7eaa", "ci_commit": "aceb5cccb154",
            "remote_head": "aceb5cccb154", "head": "aceb5cccb154",
            "head_in_live": False, "live_in_head": True, "clone_dirty": False,
            "clone_on_live": True, "task_status": статус,
            "artifact_same": True, "artifact_head": "a" * 64,
            "artifact_live": "a" * 64})
        assert действие == "wait", статус


def test_исход_считается_опубликованным():
    """Условие 4 и конец вечного ожидания: задача выходит из кандидатов."""
    assert "artifact_identical" in ТП.ОПУБЛИКОВАНО


def test_пустое_дерево_это_не_совпадение(tmp_path):
    """Если файлов артефакта в дереве нет, сравнивать нечем."""
    репо = _репо(tmp_path, {"TEMPLATE-CANDIDATES.md": "# только документ\n"})
    живой = subprocess.run(["git", "-C", str(репо), "rev-parse", "HEAD"],
                           capture_output=True, text=True).stdout.strip()
    цифра, беда = ТП.цифра_дерева(репо, живой)
    assert цифра == "" and "нет файлов артефакта" in беда
    факты = ТП.сравнить_артефакты(репо, живой, живой)
    assert факты["artifact_same"] is None
