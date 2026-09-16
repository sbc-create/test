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
    attempts: int = 0

    def as_dict(self) -> dict:
        return {"job_id": self.job_id, "site_id": self.site_id, "action": self.action,
                "environment": self.environment, "attempts": self.attempts,
                "path": str(self.path.relative_to(PATHS.root))}


def enqueue(site_id: str, *, action: str = "create", environment: str = "staging", job_id: str | None = None, traceparent: str | None = None) -> QueueItem:
    job_id = job_id or f"{site_id}-{action}-{time.strftime('%Y%m%dT%H%M%SZ', time.gmtime())}"
    payload = {"job_id": job_id, "site_id": site_id, "action": action, "environment": environment,
               # Контекст следа кладётся в само задание: исполнитель работает в
               # другом процессе и другим временем, и без переноса цепочка
               # обрывается ровно там, где начинается асинхронная часть.
               **({"traceparent": traceparent} if traceparent else {}),
               "enqueued_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
    path = stage_dir("inbox") / f"{job_id}.json"
    if path.exists():
        raise FileExistsError(f"Задание {job_id} уже в очереди: повторная постановка создала бы дубль.")
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return QueueItem(job_id, site_id, action, environment, path)


def _read(path: Path) -> QueueItem:
    data = json.loads(path.read_text(encoding="utf-8"))
    return QueueItem(data["job_id"], data["site_id"], data.get("action", "create"),
                     data.get("environment", "staging"), path, int(data.get("attempts", 0)))


def claim() -> QueueItem | None:
    """Атомарно забирает следующее задание из inbox в processing."""
    for path in sorted(stage_dir("inbox").glob("*.json")):
        target = stage_dir("processing") / path.name
        try:
            os.rename(path, target)     # атомарно в пределах одной ФС
        except OSError:
            continue                    # забрал другой worker
        _bump_attempts(target)
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


MAX_ATTEMPTS = 3


def attempts_of(path: Path) -> int:
    try:
        return int(json.loads(path.read_text(encoding="utf-8")).get("attempts", 0))
    except (OSError, json.JSONDecodeError, ValueError):
        return 0


def _bump_attempts(path: Path) -> int:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return 0
    payload["attempts"] = int(payload.get("attempts", 0)) + 1
    payload["last_claimed_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return payload["attempts"]


def requeue_stale(max_age_seconds: int = 3600, max_attempts: int = MAX_ATTEMPTS) -> dict[str, list[str]]:
    """Возвращает в inbox задания, зависшие в processing после падения worker'а.

    Задание, исчерпавшее попытки, уходит в quarantine: иначе «ядовитый» job
    бесконечно циркулирует processing → inbox и съедает каждый запуск worker'а.
    """
    moved: list[str] = []
    quarantined: list[str] = []
    now = time.time()
    for path in sorted(stage_dir("processing").glob("*.json")):
        if now - path.stat().st_mtime <= max_age_seconds:
            continue
        if attempts_of(path) >= max_attempts:
            payload = json.loads(path.read_text(encoding="utf-8"))
            payload["result_stage"] = "quarantine"
            payload["detail"] = f"Исчерпаны попытки обработки ({payload.get('attempts')}); требуется разбор оператором."
            (stage_dir("quarantine") / path.name).write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
            path.unlink(missing_ok=True)
            quarantined.append(path.name)
            continue
        os.rename(path, stage_dir("inbox") / path.name)
        moved.append(path.name)
    return {"requeued": moved, "quarantined": quarantined}


def requeue(item: QueueItem) -> Path:
    """Возвращает задание в inbox (например, при гонке за блокировку)."""
    target = stage_dir("inbox") / item.path.name
    os.rename(item.path, target)
    return target


def counts() -> dict[str, int]:
    return {stage: len(list(stage_dir(stage).glob("*.json"))) for stage in STAGES}
