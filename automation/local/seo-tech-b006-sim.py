#!/usr/bin/env python3
"""Приёмка B006 до установки таймера: настоящая обёртка seo-tech-run.sh на отдельном состоянии.

Модель подменена (automation/local/seo-tech-b006-fake-claude.py делает настоящую правку и коммит),
всё остальное — штатное: блокировка, предполётная проверка, захват, вердикт по следам.

Проверяется:
  A. две задачи подряд — вторая начинается без ручного запуска, через минуту после
     завершения первой (эмуляция OnUnitInactiveSec=1min таймера);
  B. прерывание — обёртку убивают SIGKILL посреди работы модели; следующий запуск
     закрывает захват как INTERRUPTED (попытка засчитана) и доводит задачу до VERIFIED;
  C. пустая очередь — выход 0 без вызова модели.

Пишет только в var/test-seo-tech/sim/. Итог — JSON в stdout и var/test-seo-tech/sim/<id>/report.json.
"""
from __future__ import annotations

import json
import os
import signal
import subprocess
import sys
import time
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WRAPPER = ROOT / "automation" / "host" / "editor" / "seo-tech-run.sh"
SIM = ROOT / "var" / "test-seo-tech" / "sim"
ПАУЗА = int(os.environ.get("SIM_INACTIVE_S", "60"))


def git(репо: Path, *a: str) -> None:
    subprocess.run(["git", "-C", str(репо), "-c", "user.email=sim@local", "-c", "user.name=sim", *a],
                   check=True, capture_output=True)


def main() -> int:
    ид = time.strftime("%Y%m%dT%H%M%S") + "-" + uuid.uuid4().hex[:4]
    база = SIM / ид
    репо = база / "repo"
    (репо / "checks").mkdir(parents=True)
    (репо / "page.html").write_text("<title>t</title>")
    (репо / "checks" / "run.sh").write_text("exit 0\n")
    git(репо, "init", "-q", "-b", "main")
    git(репо, "add", ".")
    git(репо, "commit", "-q", "-m", "база")
    rel = str(репо.relative_to(ROOT))
    задачи = [{"id": f"T99{i}", "site": "sim.local", "repo": rel, "status": "queued", "problem": "нет H1",
               "check": f"checks/sim_h1_{i}.py", "direction": "network"} for i in (1, 2, 3)]
    очередь = база / "queue.json"
    очередь.write_text(json.dumps({"schema_version": "1", "tasks": задачи}, ensure_ascii=False))
    state = база / "state"
    env = {**os.environ, "SEO_TECH_STATE": str(state), "SEO_TECH_QUEUE": str(очередь),
           "CLAUDE_BIN": str(ROOT / "automation" / "local" / "seo-tech-b006-fake-claude.py"), "SEO_TECH_TRIGGER": "sim-timer",
           "SEO_TECH_BACKLOG": "0", "SEO_TECH_TIMEOUT": "120", "SEO_TECH_GRACE": "5"}
    журнал: list[dict] = []

    def прогон(доп: dict | None = None) -> dict:
        t0 = time.time()
        r = subprocess.run(["bash", str(WRAPPER)], env={**env, **(доп or {})}, capture_output=True, text=True, timeout=900)
        з = {"start": t0, "end": time.time(), "rc": r.returncode, "stderr": r.stderr.strip()[-200:]}
        журнал.append(з)
        return з

    def runs() -> list[dict]:
        f = state / "runs.jsonl"
        return [json.loads(с) for с in f.read_text().splitlines()] if f.exists() else []

    # A. Две задачи подряд, «таймер» перезапускает через ПАУЗА секунд после завершения.
    a1 = прогон()
    time.sleep(ПАУЗА)
    a2 = прогон()
    после_a = runs()

    # B. Прерывание: третья задача, модель «зависает», обёртку убивают SIGKILL всей группой.
    (state / "HANG").write_text("1")
    п = subprocess.Popen(["bash", str(WRAPPER)], env=env, start_new_session=True,
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    for _ in range(120):
        if (state / "claims" / "T993.claim").exists():
            break
        time.sleep(0.5)
    time.sleep(2)
    # Как systemd при остановке, тайм-ауте или OOM юнита (KillMode=control-group): убить ВСЕ
    # процессы прогона. `timeout` уводит модель в свою группу процессов, поэтому killpg мало —
    # убиваются все процессы сеанса обёртки.
    for proc in Path("/proc").iterdir():
        if not proc.name.isdigit():
            continue
        try:
            поля = (proc / "stat").read_text().rsplit(")", 1)[-1].split()
        except OSError:
            continue
        if int(поля[3]) == п.pid:  # поле 6 stat — идентификатор сеанса
            try:
                os.kill(int(proc.name), signal.SIGKILL)
            except ProcessLookupError:
                pass
    п.wait()
    (state / "HANG").unlink()
    захват_после_убийства = (state / "claims" / "T993.claim").exists()
    time.sleep(ПАУЗА)
    b = прогон()
    после_b = runs()

    # C. Пустая очередь — выход 0, новых записей прогона нет.
    до = len(runs())
    c = прогон()
    после_c = len(runs())

    вердикты = [(р["task_id"], р["verdict"], р.get("trigger")) for р in после_b]
    отчёт = {
        "sim": ид,
        "A_two_tasks_back_to_back": {
            "runs": [(р["task_id"], р["verdict"]) for р in после_a],
            "rc": [a1["rc"], a2["rc"]],
            "gap_s": round(a2["start"] - a1["end"], 1),
            "ok": [(р["task_id"], р["verdict"]) for р in после_a] == [("T991", "VERIFIED"), ("T992", "VERIFIED")],
        },
        "B_interrupt_recovery": {
            "claim_left_after_kill": захват_после_убийства,
            "verdicts": вердикты[2:],
            "rc": b["rc"],
            "ok": any(v == ("T993", "INTERRUPTED", "recovery") for v in вердикты)
                  and вердикты[-1][:2] == ("T993", "VERIFIED"),
        },
        "C_empty_queue_no_model": {"rc": c["rc"], "new_runs": после_c - до, "ok": c["rc"] == 0 and после_c == до},
        "wrapper_runs": журнал,
    }
    отчёт["ok"] = all(отчёт[k]["ok"] for k in ("A_two_tasks_back_to_back", "B_interrupt_recovery", "C_empty_queue_no_model"))
    (база / "report.json").write_text(json.dumps(отчёт, ensure_ascii=False, indent=1))
    print(json.dumps({k: v for k, v in отчёт.items() if k != "wrapper_runs"}, ensure_ascii=False, indent=1))
    return 0 if отчёт["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
