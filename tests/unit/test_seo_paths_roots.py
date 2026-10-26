"""Корни путей служб (MOD-198): код из выпуска, состояние и живые реестры — отдельно.

Запуск, а не сверка: пакет seo_operator копируется в каталог «выпуска» без git
и импортируется оттуда отдельным процессом. Служба, которая читала бы живые
реестры из выпуска, обязана упасть RegistryRootError, а не тихо читать
замороженную копию очереди.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from seo_operator import paths

КОПИЯ = Path(__file__).resolve().parents[2]

ПРОБА = """
import json
from seo_operator import editor_run, notify, regular, tech_backlog, tech_run
print(json.dumps({
    "code": str(tech_run.paths.CODE_ROOT),
    "editor_state": str(editor_run.STATE),
    "tech_state": str(tech_run.STATE),
    "tech_queue": str(tech_run.QUEUE),
    "notify_state": str(notify.STATE),
    "regular_cells": str(regular.SOURCES["cells"]),
    "regular_ledger_runs": str(regular.SOURCES["changes_ledger_runs"]),
    "backlog_positions": str(tech_backlog.POSITIONS),
    "topvisor_measure_out": str(__import__("factory.topvisor.measure", fromlist=["x"]).ВЫХОД / "measure-latest.json"),
}))
"""


def _выпуск(tmp_path: Path) -> Path:
    выпуск = tmp_path / "release"
    shutil.copytree(КОПИЯ / "seo_operator", выпуск / "seo_operator",
                    ignore=shutil.ignore_patterns("__pycache__"))
    return выпуск


def _запустить(выпуск: Path, **env: str) -> subprocess.CompletedProcess:
    среда = {k: v for k, v in os.environ.items()
             if k not in ("SEO_STATE_ROOT", "SEO_REGISTRY_ROOT", "SEO_TECH_STATE",
                          "SEO_TECH_QUEUE", "SITE_CELLS_REGISTRY", "SEO_REGULAR_ROOT")}
    среда.update(env)
    # seo_operator — из выпуска, factory — из рабочей копии (как зависимость).
    среда["PYTHONPATH"] = f"{выпуск}{os.pathsep}{КОПИЯ}"
    return subprocess.run([sys.executable, "-c", ПРОБА], cwd=выпуск, env=среда,
                          capture_output=True, text=True, timeout=120)


def test_служба_из_выпуска_без_корня_реестров_падает(tmp_path):
    выпуск = _выпуск(tmp_path)
    r = _запустить(выпуск)
    assert r.returncode != 0
    assert "RegistryRootError" in r.stderr and "не рабочая копия под git" in r.stderr


def test_корни_разводят_код_состояние_и_реестры(tmp_path):
    выпуск = _выпуск(tmp_path)
    состояние = tmp_path / "state"
    r = _запустить(выпуск, SEO_STATE_ROOT=str(состояние), SEO_REGISTRY_ROOT=str(КОПИЯ))
    assert r.returncode == 0, r.stderr
    п = json.loads(r.stdout)
    assert п["code"] == str(выпуск)
    # Писатели и читатели состояния — под одним корнем.
    for ключ in ("editor_state", "tech_state", "notify_state", "regular_ledger_runs", "backlog_positions"):
        assert п[ключ].startswith(str(состояние) + os.sep), ключ
    # Пара «писатель — читатель»: Топвизор пишет измерение туда, где его ищет техочередь.
    assert п["topvisor_measure_out"] == п["backlog_positions"]
    # Живые реестры — из рабочей копии, не из выпуска.
    for ключ in ("tech_queue", "regular_cells"):
        assert п[ключ].startswith(str(КОПИЯ) + os.sep) and not п[ключ].startswith(str(выпуск)), ключ


def test_без_переменных_поведение_прежнее(monkeypatch):
    monkeypatch.delenv("SEO_STATE_ROOT", raising=False)
    monkeypatch.delenv("SEO_REGISTRY_ROOT", raising=False)
    assert paths.state("var") == paths.CODE_ROOT / "var"
    assert paths.registry("config") == paths.CODE_ROOT / "config"


def test_корень_реестров_не_под_git_отвергается(monkeypatch, tmp_path):
    monkeypatch.setenv("SEO_REGISTRY_ROOT", str(tmp_path))
    with pytest.raises(paths.RegistryRootError):
        paths.registry("config", "seo-tech-queue.json")


@pytest.mark.parametrize("обёртка, задание, каталог", [
    ("automation/host/editor/editor-run.sh", "docs/editor/EDITOR_RUN_PROMPT.md", "var/editor-runs"),
    ("automation/host/editor/seo-tech-run.sh", "docs/seo-tech/SEO_TECH_RUN_PROMPT.md", "var/seo-tech"),
])
def test_задание_модели_получает_фактический_каталог_состояния(обёртка, задание, каталог, tmp_path):
    """Модель идёт по пути из текста задания: в нём должен стоять каталог
    состояния обёртки, а не путь от корня копии (иначе перенос уводит запись)."""
    import re as _re
    строка = next(s for s in (КОПИЯ / обёртка).read_text(encoding="utf-8").splitlines()
                  if s.startswith('PROMPT="$(sed'))
    assert каталог in (КОПИЯ / задание).read_text(encoding="utf-8")
    состояние = tmp_path / "state"
    r = subprocess.run(["bash", "-c", f'{строка}\nprintf "%s" "$PROMPT"'], cwd=КОПИЯ,
                       env={**os.environ, "RUN_ID": "R1", "REPO": str(КОПИЯ),
                            "STATE": str(состояние / каталог), "SEO_STATE_ROOT": str(состояние)},
                       capture_output=True, text=True, timeout=30)
    assert r.returncode == 0, r.stderr
    текст = r.stdout
    assert str(состояние / каталог) in текст
    assert not _re.search(r"(?<![/\w])" + _re.escape(каталог), текст), "в задании остался путь от корня копии"


@pytest.mark.parametrize("обёртка, задание", [
    ("automation/host/editor/editor-run.sh", "docs/editor/EDITOR_RUN_PROMPT.md"),
    ("automation/host/editor/seo-tech-run.sh", "docs/seo-tech/SEO_TECH_RUN_PROMPT.md"),
])
def test_обёртка_берёт_код_и_задание_из_выпуска_а_состояние_из_копии(обёртка, задание, tmp_path):
    """SEO_CODE_ROOT: cd в каталог выпуска, задание — оттуда же; состояние и
    реестры без своих переменных остаются в рабочей копии и передаются Python."""
    строки = (КОПИЯ / обёртка).read_text(encoding="utf-8").splitlines()
    начало = строки.index("WORKTREE=/home/claude/wt-portable-site-cell-01")
    корни = строки[начало:начало + 4]
    состояние = next(s for s in строки if s.startswith("STATE="))
    подстановка = next(s for s in строки if s.startswith('PROMPT="$(sed'))
    выпуск = tmp_path / "release"
    (выпуск / задание).parent.mkdir(parents=True)
    (выпуск / задание).write_text("МЕТКА-ВЫПУСКА var/editor-runs var/seo-tech\n", encoding="utf-8")
    сценарий = "\n".join([*корни, состояние, 'cd "$REPO" || exit 9', подстановка,
                          'printf "%s|%s|%s|%s" "$PWD" "$SEO_STATE_ROOT" "$SEO_REGISTRY_ROOT" "$PROMPT"'])
    среда = {k: v for k, v in os.environ.items()
             if k not in ("SEO_STATE_ROOT", "SEO_REGISTRY_ROOT", "SEO_TECH_STATE")}
    r = subprocess.run(["bash", "-c", сценарий], env={**среда, "SEO_CODE_ROOT": str(выпуск), "RUN_ID": "R1"},
                       capture_output=True, text=True, timeout=30)
    assert r.returncode == 0, r.stderr
    кат, сост, реестр, текст = r.stdout.split("|", 3)
    assert Path(кат) == выпуск
    assert "МЕТКА-ВЫПУСКА" in текст, "задание читается не из каталога выпуска"
    копия = "/home/claude/wt-portable-site-cell-01"
    assert сост == копия and реестр == копия
    assert f"{копия}/var/" in текст and str(выпуск) + "/var" not in текст
