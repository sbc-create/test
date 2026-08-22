"""REQ-STATUS: список статусов один и тот же в коде, схеме и требованиях.

Расхождение здесь означает, что статус либо невозможно записать в результат
задания (схема отвергнет), либо он объявлен и никем не используется.
"""
from __future__ import annotations

import json
from pathlib import Path

from factory.errors import ALL_STATES, FAILURE_STATES, NON_RETRYABLE
from factory.state import TRANSITIONS

ROOT = Path(__file__).resolve().parents[2]


def _enums(node, found=None):
    found = found if found is not None else []
    if isinstance(node, dict):
        for key, value in node.items():
            if key == "enum" and isinstance(value, list):
                found.append(value)
            else:
                _enums(value, found)
    elif isinstance(node, list):
        for item in node:
            _enums(item, found)
    return found


def test_job_result_schema_knows_every_status():
    schema = json.loads((ROOT / "schemas/job-result.schema.json").read_text(encoding="utf-8"))
    enums = [set(values) for values in _enums(schema) if "BLOCKED_SEO" in values]
    assert enums, "в схеме результата нет перечисления статусов"
    for values in enums:
        missing = set(FAILURE_STATES) - values
        assert not missing, f"схема не знает статусов: {sorted(missing)}"


def test_every_status_is_reachable_in_code():
    """Статус, который никто не выставляет, — это обещание, а не поведение."""
    sources = [
        (ROOT / "factory" / name).read_text(encoding="utf-8")
        for name in ("pipeline.py", "validation.py", "errors.py", "verify.py", "build.py")
    ]
    sources.append((ROOT / "factory" / "targets" / "payload_multisite.py").read_text(encoding="utf-8"))
    haystack = "\n".join(sources)
    for status in FAILURE_STATES:
        # errors.py объявляет статус; требуем ещё хотя бы одно упоминание вне объявления.
        assert haystack.count(status) >= 2, f"статус {status} объявлен, но нигде не выставляется"


def test_transitions_cover_all_states():
    assert set(TRANSITIONS) == set(ALL_STATES)


def test_new_statuses_are_not_retried():
    for status in ("BLOCKED_SEO_DUPLICATE", "BLOCKED_CONTENT_RIGHTS", "BLOCKED_PLAYER_CONTRACT"):
        assert status in NON_RETRYABLE, f"{status} исправляется входными данными, повтор бессмыслен"
