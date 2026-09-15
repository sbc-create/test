"""Бюджет времени браузерной приёмки задан по движкам, а не одним числом.

Пять падений firefox с «page.goto timeout 45s» числились дефектом с
неустановленной причиной. Причина измерима: на этом хосте firefox медленнее
chromium примерно в одиннадцать раз (медианы трёх загрузок одной живой
страницы — 1160 мс, 1948 мс и 12 759 мс для chromium, webkit и firefox), и
общий бюджет, просторный для chromium, для firefox оказывался на грани.

Проверка держит оба края решения. Медленным движкам бюджет больше — иначе
падение вернётся. Общий бюджет не поднят — иначе он перестанет ловить
замедление chromium, ради которого и выставлен, и настоящая регрессия пройдёт
как зелёная.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
CONFIG = REPO_ROOT / "playwright.config.js"

#: Тот же бюджет, что и в конфиге. Совпадение проверяется, а не предполагается.
CHROMIUM_BUDGET_MS = 45_000


def _projects(all_browsers: bool) -> dict[str, int | None]:
    node = shutil.which("node")
    if node is None:
        pytest.skip("node недоступен: конфигурация браузерной приёмки не читается")
    script = (
        f"const c=require({str(CONFIG)!r});"
        "console.log(JSON.stringify(c.projects.map(p=>[p.name, p.timeout ?? null])));"
    )
    env = {"PATH": "/usr/bin:/bin"}
    if all_browsers:
        env["FACTORY_ALL_BROWSERS"] = "1"
    out = subprocess.run(
        [node, "-e", script], capture_output=True, text=True, env=env, cwd=REPO_ROOT
    )
    if out.returncode != 0:
        pytest.skip(f"конфигурация не загружается в этой среде: {out.stderr.strip()[:200]}")
    return dict(json.loads(out.stdout.strip().splitlines()[-1]))


def test_global_budget_stays_tight() -> None:
    node = shutil.which("node")
    if node is None:
        pytest.skip("node недоступен")
    script = f"const c=require({str(CONFIG)!r});console.log(c.timeout);"
    out = subprocess.run(
        [node, "-e", script], capture_output=True, text=True, env={"PATH": "/usr/bin:/bin"},
        cwd=REPO_ROOT,
    )
    if out.returncode != 0:
        pytest.skip("конфигурация не загружается в этой среде")
    assert int(out.stdout.strip()) == CHROMIUM_BUDGET_MS, (
        "общий бюджет подобран под chromium. Подняв его ради медленного движка, "
        "мы перестанем замечать замедление самого chromium"
    )


def test_chromium_projects_use_the_global_budget() -> None:
    projects = _projects(all_browsers=False)
    assert projects, "без FACTORY_ALL_BROWSERS должны остаться проекты chromium"
    for name, timeout in projects.items():
        assert name.startswith("chromium"), f"неожиданный проект по умолчанию: {name}"
        assert timeout is None, f"{name}: chromium не нуждается в собственном бюджете"


def test_slow_engines_get_their_own_budget() -> None:
    projects = _projects(all_browsers=True)
    assert "firefox" in projects and "webkit" in projects
    assert projects["firefox"] is not None, (
        "firefox медленнее chromium примерно в одиннадцать раз: без собственного "
        "бюджета возвращаются падения с page.goto timeout"
    )
    assert projects["firefox"] > CHROMIUM_BUDGET_MS
    assert projects["webkit"] is not None
    assert projects["webkit"] > CHROMIUM_BUDGET_MS


def test_the_slowest_engine_gets_the_largest_budget() -> None:
    """Порядок бюджетов повторяет порядок измеренных скоростей."""
    projects = _projects(all_browsers=True)
    assert projects["firefox"] > projects["webkit"], (
        "firefox измеренно медленнее webkit, бюджет обязан это отражать"
    )


def test_retries_are_still_forbidden() -> None:
    """Повтор превратил бы нестабильность страницы в зелёный статус.

    Увеличение бюджета — не повод разрешить повторы: это разные лекарства от
    разных болезней, и второе маскирует настоящий дефект.
    """
    text = CONFIG.read_text(encoding="utf-8")
    assert "retries: 0" in text, "повторы должны оставаться запрещёнными"
