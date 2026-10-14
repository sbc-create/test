#!/usr/bin/env python3
"""Подмена модели для приёмки B006: делает настоящую правку и коммит в рабочей копии из next.json.

FAKE_MODE=hang — зависнуть (проверка прерывания), иначе — правка + проверка + коммит.
"""
import json, os, subprocess, sys, time
from pathlib import Path
state = Path(os.environ["SEO_TECH_STATE"])
n = json.loads((state / "next.json").read_text(encoding="utf-8"))
if os.environ.get("FAKE_MODE") == "hang" or (state / "HANG").exists():
    time.sleep(3600)
wt = Path(n["worktree"]); check = n["task"]["check"]
(wt / check).parent.mkdir(parents=True, exist_ok=True)
(wt / check).write_text("import sys, pathlib\nt=(pathlib.Path(__file__).resolve().parents[1]/'page.html').read_text()\nsys.exit(0 if '<h1>' in t else 1)\n")
(wt / "page.html").write_text("<title>t</title><h1>t</h1>")
g = lambda *a: subprocess.run(["git", "-C", str(wt), "-c", "user.email=sim@local", "-c", "user.name=sim", *a], check=True, capture_output=True)
g("add", "."); g("commit", "-q", "-m", f"{n['task_id']}: правка (приёмка B006)")
print(json.dumps({"result": json.dumps({"run_id": n["run_id"], "task_id": n["task_id"], "outcome": "PREPARED"})}))
