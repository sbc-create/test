"""REQ-CONTENT-FROM-IMAGE: контентные скрипты исполняются из образа, не из дерева.

История. Контентные юниты YummyAnime запускали скрипты прямо из рабочего дерева
git: `ExecStart=/usr/bin/node /srv/sites/yummyani-staging/repo/scripts/…`.
Значит `git checkout` в этом каталоге молча менял поведение боевого контента —
без выкатки, без отката и без записи о работающей версии.

Измерено 2026-09-03 инструментом `check-unit-provenance.sh`: три таких юнита
исполнялись с ветки `claude/night-yummy-schedule-12`, отличной от той, из
которой собран боевой образ, и с незакоммиченной правкой в дереве. Веб-витрина
и контентный конвейер работали с разного кода, и ничто об этом не сообщало.

Проверяется форма команды и форма юнитов, а не работа docker: поднимать
настоящий контейнер в модульном тесте значит получить тест, который падает от
занятого демона.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
WRAPPER = REPO / "automation" / "host" / "yummy-content-run.sh"
UNITS = REPO / "automation" / "host" / "systemd"
YUMMY_UNITS = ("yummy-episode-watcher.service", "yummy-watchdog.service", "yummy-enrich.service")


@pytest.fixture
def fake_docker(tmp_path: Path) -> dict[str, str]:
    """Окружение, в котором `docker` — подставной и только печатает аргументы.

    Фикстура обязательна для КАЖДОГО вызова обёртки. Один тест, забывший её
    подставить, нашёл настоящий docker и поднял настоящий контейнер против
    боевого состояния: он упал на EACCES и ничего не испортил, но модульный
    тест не имеет права дотягиваться до production. Поэтому подстановка
    вынесена в фикстуру, а обёртка вызывается только через `run_wrapper`.
    """
    fake_bin = tmp_path / "fake-bin"
    fake_bin.mkdir()
    docker = fake_bin / "docker"
    docker.write_text('#!/bin/sh\nprintf "%s\\n" "$@"\n', encoding="utf-8")
    docker.chmod(0o755)
    return {**os.environ, "PATH": f"{fake_bin}:{os.environ['PATH']}"}


def run_wrapper(env: dict[str, str], *args: str, **extra: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["bash", str(WRAPPER), *args],
        capture_output=True, text=True, env={**env, **extra}, timeout=60,
    )


def test_wrapper_runs_the_image_not_a_host_path(fake_docker) -> None:
    result = run_wrapper(fake_docker, "scripts/episode-watcher.mjs")
    assert result.returncode == 0, result.stderr
    out = [a for a in result.stdout.split("\n") if a]
    assert "run" in out and "--rm" in out and "--no-deps" in out
    # Скрипт уходит в контейнер относительным путём: абсолютный означал бы
    # исполнение с диска хоста. Пути compose-файла и env-файла остаются
    # абсолютными законно — они описывают сервисы, а не исполняемый код.
    assert out[-1] == "scripts/episode-watcher.mjs", out
    assert not out[-1].startswith("/"), out


def test_absolute_script_path_is_refused(fake_docker) -> None:
    """Абсолютный путь — это возврат к исполнению из дерева хоста."""
    result = run_wrapper(fake_docker, "/srv/sites/yummyani-staging/repo/scripts/episode-watcher.mjs")
    assert result.returncode == 2
    assert "относительным" in result.stderr


def test_missing_argument_is_refused(fake_docker) -> None:
    assert run_wrapper(fake_docker).returncode == 2


def test_service_is_selectable_without_editing_the_script(fake_docker) -> None:
    result = run_wrapper(fake_docker, "scripts/watchdog-run.mjs", YUMMY_CONTENT_SERVICE="web-org")
    assert result.returncode == 0, result.stderr
    assert "web-org" in result.stdout.split("\n")


@pytest.mark.parametrize("unit", YUMMY_UNITS)
def test_unit_does_not_execute_from_a_working_tree(unit: str) -> None:
    """Главное свойство: ExecStart не указывает внутрь git-checkout."""
    text = (UNITS / unit).read_text(encoding="utf-8")
    exec_lines = [l for l in text.splitlines() if l.startswith("ExecStart=")]
    assert exec_lines, f"{unit}: нет ExecStart"
    for line in exec_lines:
        assert "/srv/sites/yummyani-staging/repo/" not in line, f"{unit}: исполняется из дерева"
        assert "/usr/bin/node " not in line, f"{unit}: запускает node по пути хоста"
        assert "yummy-content-run.sh" in line, f"{unit}: должен идти через обёртку"


@pytest.mark.parametrize("unit", YUMMY_UNITS)
def test_unit_is_oneshot_like_the_timers_expect(unit: str) -> None:
    text = (UNITS / unit).read_text(encoding="utf-8")
    assert "Type=oneshot" in text, f"{unit}: таймеры рассчитывают на oneshot"
