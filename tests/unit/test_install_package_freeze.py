"""Процесс выпуска: пакет фиксируется ДО установки и не меняется во время неё.

Проверка появилась после разбора 26.09: установка «выполнилась», а результата не
дала, потому что обязательные части пакета дописывались после её запуска. Тест
закрепляет ровно те свойства, отсутствие которых это допустило.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

КОРЕНЬ = Path(__file__).resolve().parents[2]
ХОСТ = КОРЕНЬ / "automation" / "host"
ФИКСАТОР = ХОСТ / "freeze-package.py"


def прогнать(*арг: str, cwd: Path) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, *арг], cwd=str(cwd),
                          capture_output=True, text=True)


@pytest.fixture()
def репо(tmp_path: Path) -> Path:
    """Маленький репозиторий той же формы: фиксатор ищет корень по себе."""
    к = tmp_path / "repo"
    (к / "factory" / "cell").mkdir(parents=True)
    (к / "factory" / "cell" / "executor.py").write_text("# исполнитель\n", encoding="utf-8")
    (к / "schemas").mkdir()
    (к / "schemas" / "s.json").write_text("{}\n", encoding="utf-8")
    (к / "config").mkdir()
    (к / "config" / "c.json").write_text('{"a": 1}\n', encoding="utf-8")
    (к / "automation" / "host").mkdir(parents=True)
    shutil.copy2(ФИКСАТОР, к / "automation" / "host" / "freeze-package.py")
    окр = {**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t",
           "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t"}
    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=к, check=True, env=окр)
    subprocess.run(["git", "add", "-A"], cwd=к, check=True, env=окр)
    subprocess.run(["git", "commit", "-qm", "первый"], cwd=к, check=True, env=окр)
    return к


ФИКС = "automation/host/freeze-package.py"


def test_фиксация_даёт_опись_с_суммами(репо: Path) -> None:
    гот = прогнать(ФИКС, cwd=репо)
    assert гот.returncode == 0, гот.stderr
    пакеты = list((репо / "var" / "install-packages").glob("pkg-*"))
    assert len(пакеты) == 1
    опись = json.loads((пакеты[0] / "manifest.json").read_text(encoding="utf-8"))
    assert опись["commit"] and len(опись["commit"]) == 40
    assert опись["digest"] and len(опись["digest"]) == 64
    assert опись["package_id"] == "pkg-" + опись["digest"][:12]
    assert "factory/cell/executor.py" in опись["files"]
    assert опись["file_count"] == len(опись["files"])
    # Корень рабочих копий репозиториев объявлен в описи, а не выводится из
    # места установщика: раньше одно подменяло другое.
    assert опись["site_repos_root"] == str(репо)


def test_незакоммиченное_фиксировать_нельзя(репо: Path) -> None:
    """Это и есть ошибка 26.09: обязательная часть дописана после фиксации."""
    (репо / "factory" / "cell" / "новое.py").write_text("x = 1\n", encoding="utf-8")
    гот = прогнать(ФИКС, cwd=репо)
    assert гот.returncode == 2
    assert "ОТКАЗ" in гот.stdout
    assert "не в git: factory/cell/новое.py" in гот.stdout
    assert not (репо / "var" / "install-packages").exists()


def test_изменение_файла_тоже_отказ(репо: Path) -> None:
    (репо / "config" / "c.json").write_text('{"a": 2}\n', encoding="utf-8")
    гот = прогнать(ФИКС, cwd=репо)
    assert гот.returncode == 2
    assert "изменён: config/c.json" in гот.stdout


def test_сверка_замечает_подмену_в_пакете(репо: Path) -> None:
    assert прогнать(ФИКС, cwd=репо).returncode == 0
    пакет = next((репо / "var" / "install-packages").glob("pkg-*"))
    цель = пакет / "tree" / "config" / "c.json"
    цель.chmod(0o644)
    цель.write_text('{"a": 999}\n', encoding="utf-8")
    гот = прогнать(ФИКС, "--check", str(пакет), cwd=репо)
    assert гот.returncode == 1
    assert "СОСТАВ ИЗМЕНИЛСЯ" in гот.stdout
    assert "config/c.json" in гот.stdout


def test_дерево_пакета_только_для_чтения(репо: Path) -> None:
    assert прогнать(ФИКС, cwd=репо).returncode == 0
    пакет = next((репо / "var" / "install-packages").glob("pkg-*"))
    файл = пакет / "tree" / "config" / "c.json"
    assert not (файл.stat().st_mode & 0o222), "файл пакета доступен на запись"


def test_одинаковый_состав_даёт_тот_же_идентификатор(репо: Path) -> None:
    assert прогнать(ФИКС, cwd=репо).returncode == 0
    первый = next((репо / "var" / "install-packages").glob("pkg-*")).name
    assert прогнать(ФИКС, cwd=репо).returncode == 0
    пакеты = {п.name for п in (репо / "var" / "install-packages").glob("pkg-*")}
    assert пакеты == {первый}, "повторная фиксация того же коммита развела пакеты"


# --- свойства установщика, проверяемые по тексту ------------------------------
# Запускать установщик в тесте нельзя: он требует root и меняет хост. Поэтому
# проверяются его обязательные свойства, каждое из которых 26.09 отсутствовало.

def test_установщик_без_пакета_отказывает() -> None:
    т = (ХОСТ / "unblock-transfer.sh").read_text(encoding="utf-8")
    assert "freeze-package.py" in т, "установщик не сверяет пакет"
    assert т.count("--check") >= 2, "digest сверяется не до и после, а один раз"
    assert "exit 2" in т and "NOPKG" in т, "запуск без пакета не отказывает"
    assert "СОСТАВ ПАКЕТА ИЗМЕНИЛСЯ ВО ВРЕМЯ УСТАНОВКИ" in т


def test_установщик_переносит_пакет_под_root() -> None:
    т = (ХОСТ / "unblock-transfer.sh").read_text(encoding="utf-8")
    assert "chown -R root:root" in т
    assert "CELL_PKG_STAGED" in т, "нет защиты от бесконечного перезапуска"
    assert "exec bash" in т, "установщик не перезапускается из root-копии"


def test_установка_записывает_идентификатор_пакета() -> None:
    т = (ХОСТ / "install-cell-executor.sh").read_text(encoding="utf-8")
    for поле in ("package_id", "package_digest", "package_commit"):
        assert поле in т, f"cell-install.json не записывает {поле}"
    assert "site_repos_root" in т


def test_проверка_различает_четыре_исхода() -> None:
    т = (ХОСТ / "check-installed.py").read_text(encoding="utf-8")
    for исход in ("совпадает", "отличается", "отсутствует", "не удалось проверить"):
        assert исход in т, f"нет исхода «{исход}»"
    assert "PermissionError" in т, "нет прав и различие содержимого не разделены"


def test_сверка_идёт_с_пакетом_а_не_с_рабочей_веткой() -> None:
    т = (ХОСТ / "check-installed.py").read_text(encoding="utf-8")
    assert "manifest.json" in т
    assert 'опись["files"]' in т


def test_реестр_читается_по_абсолютному_пути() -> None:
    """Относительный путь падал бы с сообщением не о той причине."""
    т = (ХОСТ / "launch-new-site.sh").read_text(encoding="utf-8")
    assert 'Path("config/site-cells.json")' not in т
    assert 'Path(sys.argv[1]) / "config" / "site-cells.json"' in т


def test_первый_запуск_домена_не_ослабляет_проверку_действующего() -> None:
    т = (ХОСТ / "install-site-nginx.sh").read_text(encoding="utf-8")
    assert "--new-site" in т
    # Исключение обязано быть обставлено всеми четырьмя условиями.
    assert "уже есть, это не первый запуск" in т or "это не первый запуск" in т
    assert "уже заполнен" in т
    assert "'planned'" in т or "planned" in т
    assert "/healthz" in т, "проверка отклика для действующих витрин удалена"
