"""Машиночитаемый результат задания по schemas/job-result.schema.json."""
from __future__ import annotations

import json
import time
from pathlib import Path

import jsonschema

from factory import audit, knowledge
from factory.paths import PATHS
from factory.redaction import redact_obj


def build_result(*, job_id: str, site_id: str, environment: str, status: str, started_at: str,
                 requested_action: str = "create", steps: list[dict] | None = None,
                 checks: list[dict] | None = None, artifacts: list[str] | None = None,
                 mutations: list[dict] | None = None, blockers: list[dict] | None = None,
                 backup: dict | None = None, build_id: str | None = None, release_id: str | None = None,
                 previous_release_id: str | None = None, seo_summary: dict | None = None,
                 notes: list[str] | None = None) -> dict:
    result = {
        "schema_version": 1,
        "job_id": job_id,
        "site_id": site_id,
        "environment": environment,
        "requested_action": requested_action,
        "status": status,
        "blockers": blockers or [],
        "started_at": started_at,
        "finished_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "factory_commit": audit.factory_commit(),
        "knowledge_freeze_version": knowledge.freeze_version(),
        "build_id": build_id,
        "release_id": release_id,
        "previous_release_id": previous_release_id,
        "steps": steps or [],
        "checks": checks or [],
        "artifacts": artifacts or [],
        "mutations": mutations or [],
        "backup": backup,
        "seo_summary": seo_summary,
        # Машиночитаемый признак: были ли выполнены все проверки приёмки.
        "acceptance_complete": all(c.get("passed") for c in (checks or [])) if checks else False,
        "notes": notes or [],
    }
    return redact_obj(result)


def validate_result(result: dict) -> list[str]:
    schema = json.loads((PATHS.schemas / "job-result.schema.json").read_text(encoding="utf-8"))
    validator = jsonschema.Draft202012Validator(schema)
    return [f"{'/'.join(str(p) for p in e.absolute_path) or '(root)'}: {e.message}"
            for e in sorted(validator.iter_errors(result), key=lambda e: list(e.absolute_path))]


def write_result(result: dict) -> Path:
    problems = validate_result(result)
    if problems:
        raise ValueError("Результат задания не соответствует схеме: " + "; ".join(problems[:5]))
    out = PATHS.artifact_dir("jobs", result["site_id"])
    path = out / f"{result['job_id']}.json"
    path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    return path
