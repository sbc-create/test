"""Файловая очередь заданий.

Один job обрабатывается семантически ровно один раз даже после restart: переход
inbox → processing атомарен (rename), а фактическое состояние живёт в var/state.
"""
from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from pathlib import Path

from factory.paths import PATHS

STAGES = ("inbox", "processing", "done", "failed", "quarantine")


def stage_dir(stage: str) -> Path:
    path = PATHS.queue / stage
    path.mkdir(parents=True, exist_ok=True)
    return path


@dataclass
class QueueItem:
    job_id: str
    site_id: str
    action: str
    environment: str
    path: Path

    def as_dict(self) -> dict:
        return {"job_id": self.job_id, "site_id": self.site_id, "action": self.action,
                "environment": self.environment, "path": str(self.path.relative_to(PATHS.root))}


def enqueue(site_id: str, *, action: str = "create", environment: str = "staging", job_id: str | None = None) -> QueueItem:
    job_id = job_id or f"{site_id}-{action}-{time.strftime('%Y%m%dT%H%M%SZ', time.gmtime())}"
    payload = {"job_id": job_id, "site_id": site_id, "action": action, "environment": environment,
               "enqueued_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
    path = stage_dir("inbox") / f"{job_id}.json"
    if path.exists():
        raise FileExistsError(f"Задание {job_id} уже в очереди: повторная постановка создала бы дубль.")
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return QueueItem(job_id, site_id, action, environment, path)


def _read(path: Path) -> QueueItem:
    data = json.loads(path.read_text(encoding="utf-8"))
    return QueueItem(data["job_id"], data["site_id"], data.get("action", "create"),
                     data.get("environment", "staging"), path)


def claim() -> QueueItem | None:
    """Атомарно забирает следующее задание из inbox в processing."""
    for path in sorted(stage_dir("inbox").glob("*.json")):
        target = stage_dir("processing") / path.name
        try:
            os.rename(path, target)     # атомарно в пределах одной ФС
        except OSError:
            continue                    # забрал другой worker
        return _read(target)
    return None


def finish(item: QueueItem, stage: str, *, detail: str = "") -> Path:
    if stage not in ("done", "failed", "quarantine"):
        raise ValueError(f"Недопустимая стадия завершения: {stage}")
    payload = json.loads(item.path.read_text(encoding="utf-8"))
    payload["finished_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    payload["result_stage"] = stage
    if detail:
        payload["detail"] = detail
    target = stage_dir(stage) / item.path.name
    target.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    item.path.unlink(missing_ok=True)
    return target


def requeue_stale(max_age_seconds: int = 3600) -> list[str]:
    """Возвращает в inbox задания, зависшие в processing после падения worker'а."""
    moved: list[str] = []
    now = time.time()
    for path in sorted(stage_dir("processing").glob("*.json")):
        if now - path.stat().st_mtime > max_age_seconds:
            os.rename(path, stage_dir("inbox") / path.name)
            moved.append(path.name)
    return moved


def counts() -> dict[str, int]:
    return {stage: len(list(stage_dir(stage).glob("*.json"))) for stage in STAGES}
