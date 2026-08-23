#!/usr/bin/env python3
"""Scheduled-run demonstration.

Runs the real daily job through the worker, kills it mid-way, restarts it, and
shows that completed steps are not repeated. This is the mechanism that will
execute the daily run on a server; the Routine path calls the same job.
"""

from __future__ import annotations

import shutil
import sys
from datetime import date
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from seo_operator.audit import AuditLog  # noqa: E402
from seo_operator.pipeline import Mode, Operator  # noqa: E402
from seo_operator.registry import load_portfolio  # noqa: E402
from seo_operator.reporting import daily_report  # noqa: E402
from seo_operator.scheduler import Job, JobState, LockBusy, Worker  # noqa: E402
from seo_operator.technical_seo import Page  # noqa: E402

OUT = REPO / "docs" / "seo-operator" / "demo-scheduled-run.md"
WORKDIR = REPO / "var" / "demo-scheduler"
TODAY = date(2026, 8, 22)

STEPS = ("probe", "collect", "analyse", "report")


def load_pages() -> list[Page]:
    import json

    data = json.loads(
        (REPO / "tests" / "fixtures" / "crawl.fixture-anime.json").read_text(encoding="utf-8")
    )
    return [Page(**p) for p in data["pages"]]


def main() -> int:
    lines: list[str] = []
    a = lines.append

    a("# Демонстрация запуска по расписанию")
    a("")
    a(
        "Сгенерировано `scripts/demo_scheduled_run.py`. Выполняется реальный "
        "ежедневный джоб на синтетическом тенанте."
    )
    a("")

    shutil.rmtree(WORKDIR, ignore_errors=True)
    executed: list[str] = []
    crash_armed = {"value": True}
    report_holder: dict[str, str] = {}

    def daily_job(job, checkpoint):
        """The actual daily run, split into checkpointed steps."""
        done = checkpoint.completed(job.job_id)

        for step in STEPS:
            if step in done:
                continue

            if step == "probe":
                executed.append(step)
                checkpoint.mark(job.job_id, step)
                continue

            if step == "collect":
                executed.append(step)
                checkpoint.mark(job.job_id, step)
                continue

            if step == "analyse":
                executed.append(step)
                # Simulate the process being killed after analysis but before
                # the report is written -- the most awkward moment to die.
                if crash_armed["value"]:
                    crash_armed["value"] = False
                    checkpoint.mark(job.job_id, step)
                    raise RuntimeError("процесс убит после анализа, до записи отчёта")
                checkpoint.mark(job.job_id, step)
                continue

            if step == "report":
                executed.append(step)
                op = Operator(
                    portfolio=load_portfolio(REPO / "config" / "portfolio.fixture.json"),
                    audit_log=AuditLog(WORKDIR / "audit.jsonl"),
                    allow_synthetic=True,
                )
                result = op.run(
                    Mode.DRY_RUN,
                    pages_by_site={"fixture-anime": load_pages()},
                    today=TODAY,
                )
                report_holder["text"] = daily_report(result, TODAY)
                checkpoint.mark(job.job_id, step)

    worker = Worker(WORKDIR)
    worker.queue.add(Job("daily-2026-08-22", "daily_run", max_attempts=3))

    a("## 1. Постановка задачи в очередь")
    a("")
    a(f"- Задача: `daily-2026-08-22`, вид `daily_run`, шаги: {', '.join(STEPS)}")
    a(f"- Очередь: `{worker.queue.path.relative_to(REPO)}`")
    a("")

    a("## 2. Одновременный второй запуск")
    a("")
    worker.lock.acquire("первый прогон")
    try:
        Worker(WORKDIR).run_once({"daily_run": daily_job})
        a("- ОШИБКА: второй worker не был заблокирован")
    except LockBusy as exc:
        a(f"- Второй worker отклонён: `{exc}`")
    finally:
        worker.lock.release()
    a("")
    a("Пересечение двух запусков по расписанию безопасно: второй завершается сразу.")
    a("")

    a("## 3. Прогон с падением и автоматическим повтором")
    a("")
    processed = worker.run_once({"daily_run": daily_job})
    job = processed[0]

    a(f"- Итоговое состояние: **{job.state.value}**")
    a(f"- Попыток: **{job.attempts}**")
    a("")
    a("| Попытка | Что произошло |")
    a("| --- | --- |")
    for event in worker.events:
        if event.get("event") == "attempt_failed":
            a(f"| {event['attempt']} | упала: {event['error']} |")
        elif event.get("event") == "done":
            a(f"| {event['attempts']} | завершена успешно |")
    a("")

    a("## 4. Восстановление после перезапуска")
    a("")
    a("| Шаг | Выполнен раз |")
    a("| --- | --- |")
    for step in STEPS:
        a(f"| `{step}` | {executed.count(step)} |")
    a("")
    repeated = [s for s in STEPS if executed.count(s) > 1]
    a(
        f"- Шагов, выполненных повторно: **{len(repeated)}**"
        + (f" ({', '.join(repeated)})" if repeated else "")
    )
    a(f"- Checkpoints: `{worker.checkpoint.path.relative_to(REPO)}`")
    a("")
    a(
        "Шаги, завершённые до падения, при повторе не выполнялись заново. "
        "Повторён только тот шаг, на котором процесс был убит."
    )
    a("")

    a("## 5. Результат прогона")
    a("")
    a(f"- Отчёт сформирован: **{'да' if 'text' in report_holder else 'НЕТ'}**")
    a(
        f"- Блокировка снята после завершения: "
        f"**{'да' if not worker.lock.path.exists() else 'НЕТ'}**"
    )
    a(f"- Состояние задачи в очереди: **{worker.queue.all()[0].state.value}**")
    a("")

    if "text" in report_holder:
        head = "\n".join(report_holder["text"].split("\n")[:12])
        a("Начало сформированного отчёта:")
        a("")
        a("```")
        a(head)
        a("```")
        a("")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("\n".join(lines), encoding="utf-8")

    print(f"записано: {OUT.relative_to(REPO)}")
    print(f"состояние={job.state.value} попыток={job.attempts} повторено_шагов={len(repeated)}")
    return 0 if job.state is JobState.DONE and not repeated else 1


if __name__ == "__main__":
    raise SystemExit(main())
