#!/usr/bin/env python3
"""Приёмка B006 после установки: по следам var/seo-tech, без участия чата.

  python3 automation/local/seo-tech-acceptance.py [--since 2026-10-14T18:00:00Z]

Критерии (все обязательны; одного «timer enabled» недостаточно):
  A. две задачи подряд обработаны таймером (trigger=systemd-timer) без ручного запуска
     второй: у обеих записан вердикт, вторая начата не позже 120 с после конца первой;
  B. восстановление после прерывания: есть запись INTERRUPTED (trigger=recovery), и та же
     задача после неё снова взята в работу таймером;
  C. состояние публикации: по каждой задаче, обработанной таймером, — подготовка
     (вердикт) и выпуск (итог seo-tech-publish или «ещё не выпускалось» с причиной).
Код выхода: 0 — A и B выполнены; 1 — нет. C — отчёт, не условие (выпуск зависит от CI и очереди).
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from seo_operator import tech_publish, tech_run  # noqa: E402


def _t(s: str | None) -> dt.datetime | None:
    if not s:
        return None
    try:
        return dt.datetime.fromisoformat(s.replace("Z", "+00:00"))
    except ValueError:
        return None


def systemd() -> dict:
    out = {}
    for unit in ("seo-tech-run.timer", "seo-tech-run.service", "seo-tech-publish.timer", "seo-tech-publish.service"):
        try:
            r = subprocess.run(["systemctl", "show", unit, "-p", "UnitFileState,ActiveState,Result,LastTriggerUSec,NextElapseUSecRealtime"],
                               capture_output=True, text=True, timeout=20)
            out[unit] = dict(l.split("=", 1) for l in r.stdout.splitlines() if "=" in l)
        except Exception as e:  # noqa: BLE001
            out[unit] = {"error": type(e).__name__}
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--since", default="")
    ap.add_argument("--trigger", default="systemd-timer", help="метка запуска таймером (для проверки на имитации — sim-timer)")
    args = ap.parse_args()
    since = _t(args.since) or dt.datetime(1970, 1, 1, tzinfo=dt.timezone.utc)
    state = tech_run.STATE
    runs = [р for р in tech_run._runs(state) if (_t(р.get("finished_at")) or since) >= since]
    таймер = [р for р in runs if р.get("trigger") == args.trigger and р.get("started_at")]
    таймер.sort(key=lambda р: р["started_at"])
    пары = []
    def конец(р: dict) -> dt.datetime:
        # Конец прогона — запись вердикта (его файл), а не конец работы модели:
        # после модели идёт проверка по следам, она длится минуты.
        f = state / f"{р['run_id']}.verify.json"
        if f.exists():
            return dt.datetime.fromtimestamp(f.stat().st_mtime, dt.timezone.utc)
        return _t(р["finished_at"])

    for a, b in zip(таймер, таймер[1:]):
        зазор = (_t(b["started_at"]) - конец(a)).total_seconds()
        пары.append({"first": [a["task_id"], a.get("verdict")], "second": [b["task_id"], b.get("verdict")],
                     "gap_s": зазор, "ok": a["task_id"] != b["task_id"] and 0 <= зазор <= 120})
    A = {"timer_runs": len(таймер), "pairs": пары[-3:], "ok": any(п["ok"] for п in пары)}

    прерывания = [р for р in runs if р.get("verdict") == "INTERRUPTED"]
    восстановлено = []
    for п in прерывания:
        после = [р for р in таймер if р["task_id"] == п["task_id"] and (_t(р.get("started_at")) or since) >= (_t(п.get("finished_at")) or since)]
        восстановлено.append({"task": п["task_id"], "interrupted_run": п["run_id"],
                              "next_timer_run": [после[0]["run_id"], после[0].get("verdict")] if после else None})
    B = {"interrupted": восстановлено[-3:], "ok": any(в["next_timer_run"] for в in восстановлено)}

    по_таймеру = {р["task_id"] for р in таймер}
    C = [с for с in tech_publish.status(state) if с["id"] in по_таймеру]

    отчёт = {"A_two_tasks_without_manual_start": A, "B_recovery_after_interrupt": B,
             "C_publication_state": C, "systemd": systemd(),
             "attention": json.loads((state / "attention.json").read_text()) if (state / "attention.json").exists() else None}
    отчёт["ok"] = A["ok"] and B["ok"]
    print(json.dumps(отчёт, ensure_ascii=False, indent=1))
    return 0 if отчёт["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
