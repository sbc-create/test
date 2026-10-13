"""B021: вкладка «SEO — ОТЧЁТ» поднимается сама, если окна нет, и не дублируется.

ExecStart берётся из самого юнита и выполняется с поддельным tmux в PATH.
"""
from __future__ import annotations

import os
import re
import shlex
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
UNIT = ROOT / "automation" / "local" / "systemd-user" / "seo-report-view.service"
TIMER = ROOT / "automation" / "local" / "systemd-user" / "seo-report-view.timer"
VIEWER = ROOT / "automation" / "local" / "seo-report-view.py"


def _exec_start() -> list[str]:
    line = re.search(r"(?m)^ExecStart=(.+)$", UNIT.read_text(encoding="utf-8")).group(1)
    return shlex.split(line)


def _run(tmp_path: Path, session_exists: bool) -> list[str]:
    log = tmp_path / "calls.log"
    fake = tmp_path / "tmux"
    fake.write_text(
        "#!/bin/sh\n"
        f'echo "$*" >> {log}\n'
        f'[ "$1" = has-session ] && exit {0 if session_exists else 1}\n'
        "exit 0\n",
        encoding="utf-8",
    )
    fake.chmod(0o755)
    env = {**os.environ, "PATH": f"{tmp_path}:{os.environ['PATH']}"}
    subprocess.run(_exec_start(), env=env, check=True, timeout=30)
    return log.read_text(encoding="utf-8").splitlines()


def test_missing_tab_is_started_with_the_viewer(tmp_path):
    calls = _run(tmp_path, session_exists=False)
    assert calls[0] == "has-session -t seo-report"
    assert calls[1].startswith("new-session -d -s seo-report -n SEO — ОТЧЁТ ")
    assert str(VIEWER) in calls[1] and VIEWER.is_file()


def test_running_tab_is_not_duplicated(tmp_path):
    assert _run(tmp_path, session_exists=True) == ["has-session -t seo-report"]


def test_watchdog_period_and_tmux_server_survive():
    unit = UNIT.read_text(encoding="utf-8")
    assert "KillMode=process" in unit and "Type=oneshot" in unit
    timer = TIMER.read_text(encoding="utf-8")
    assert "OnUnitActiveSec=5min" in timer and "Unit=seo-report-view.service" in timer
