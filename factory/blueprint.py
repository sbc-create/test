"""Blueprint DLE: профиль путей, cron-manifest, проверка готовности.

Профиль не заполняется догадкой. Пока он помечен source_required, установка DLE
возвращает BLOCKED_INPUT с точным указанием, что именно нужно получить.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml

from factory.errors import BlockedInput
from factory.paths import PATHS

REQUIRED_LISTS = ("writable_paths", "immutable_paths", "shared_paths", "installer_entrypoints", "public_deny_paths")


@dataclass
class BlueprintStatus:
    blueprint: str
    profile_path: Path
    ready: bool
    problems: list[str]

    def as_dict(self) -> dict:
        return {"blueprint": self.blueprint, "profile": str(self.profile_path), "ready": self.ready, "problems": self.problems}


def profile_path(blueprint: str = "dle20") -> Path:
    return PATHS.blueprints / blueprint / "profiles" / "paths.yaml"


def cron_manifest_path(blueprint: str = "dle20") -> Path:
    return PATHS.blueprints / blueprint / "cron" / "jobs.yaml"


def load_profile(blueprint: str = "dle20") -> dict | None:
    path = profile_path(blueprint)
    if not path.exists():
        return None
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def check(blueprint: str = "dle20") -> BlueprintStatus:
    path = profile_path(blueprint)
    problems: list[str] = []
    profile = load_profile(blueprint)
    if profile is None:
        problems.append(
            f"{path.relative_to(PATHS.root)} отсутствует. Скопируй paths.template.yaml и заполни значениями "
            "из официальной документации DLE 20.0 — угадывать пути запрещено (§3.8)."
        )
        return BlueprintStatus(blueprint, path, False, problems)
    if profile.get("source_required"):
        problems.append("Профиль помечен source_required: true — значения ещё не получены из официального источника.")
    if not profile.get("source_reference"):
        problems.append("Не указан source_reference: раздел официальной документации и дата обращения.")
    runtime = profile.get("runtime") or {}
    if not ((runtime.get("php") or {}).get("min_version")):
        problems.append("runtime.php.min_version не заполнен (системные требования DLE 20.0).")
    if not ((runtime.get("database") or {}).get("engine")):
        problems.append("runtime.database.engine не заполнен.")
    for key in REQUIRED_LISTS:
        if not profile.get(key):
            problems.append(f"{key}: пустой список — перечень обязан прийти из официальной документации.")
    perms = profile.get("permissions") or {}
    if str(perms.get("writable_mode", "")).endswith("777"):
        problems.append("permissions.writable_mode = 777 запрещён в production (§3.9).")
    return BlueprintStatus(blueprint, path, not problems, problems)


def require_ready(blueprint: str = "dle20") -> dict:
    status = check(blueprint)
    if not status.ready:
        raise BlockedInput(
            "Профиль blueprint DLE не готов: " + "; ".join(status.problems),
            field=f"blueprints/{blueprint}/profiles/paths.yaml",
            required_input="Официальная документация DLE 20.0: writable/immutable/shared пути, installer entrypoints, требования PHP/БД, plugin API",
            blocks_stage="STAGING_DEPLOY",
        )
    return load_profile(blueprint) or {}


def cron_jobs(blueprint: str = "dle20") -> list[dict]:
    path = cron_manifest_path(blueprint)
    if not path.exists():
        return []
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    jobs = data.get("jobs") or []
    seen: set[str] = set()
    for job in jobs:
        jid = job.get("id")
        if not jid or jid in seen:
            raise BlockedInput(
                f"Дублирующийся или пустой id cron-задачи: {jid!r}",
                field="blueprints/dle20/cron/jobs.yaml",
                required_input="Уникальные id задач с lock, timeout и логом",
                blocks_stage="STAGING_DEPLOY",
            )
        seen.add(jid)
        for required in ("schedule", "command", "lock", "timeout_seconds", "log"):
            if not job.get(required):
                raise BlockedInput(
                    f"Cron-задача «{jid}»: не заполнено {required}.",
                    field="blueprints/dle20/cron/jobs.yaml",
                    required_input="schedule, command, lock, timeout_seconds, log, max_retries",
                    blocks_stage="STAGING_DEPLOY",
                )
    return jobs
