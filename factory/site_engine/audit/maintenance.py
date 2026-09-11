#!/usr/bin/env python3
"""Обслуживание журнала: инвентаризация, карантин, пересборка проекции.

Отдельная команда, а не часть HTTP-поверхности: решение о карантине принимает
человек, а не запрос извне. Через API такое решение можно было бы вызвать
случайно, и «непригодным для решений» оказалось бы то, что кто-то не так
отфильтровал.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

from . import ledger_store as store
from . import projection as proj
from . import quarantine as qr

ЖУРНАЛ = os.environ.get("AUDIT_LEDGER_DB",
                        "/srv/site-factory/audit-ledger/audit_ledger.sqlite3")
ДОКАЗАТЕЛЬСТВА = Path(os.environ.get(
    "AUDIT_EVIDENCE_DIR", "/srv/site-factory/audit-ledger/evidence"))


def _коммит() -> str:
    """SHA развёрнутого релиза: связывает решение с версией кода."""
    м = Path("/srv/site-factory/control-api/release-manifest.json")
    if м.is_file():
        try:
            return json.loads(м.read_text(encoding="utf-8"))["sha"]
        except (ValueError, KeyError):
            pass
    try:
        return subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True,
                              text=True, timeout=20).stdout.strip() or "UNKNOWN"
    except OSError:
        return "UNKNOWN"


def инвентаризация(соед) -> dict:
    кандидаты = qr.найти_кандидатов(соед)
    сводка = qr.проверить_однозначность(соед, кандидаты)
    return {"candidates": кандидаты, **сводка}


def карантин(соед, *, prompt_id: str, prompt_rev: str,
             ожидается: int | None, action_id: str) -> dict:
    итог = инвентаризация(соед)
    кандидаты = итог["candidates"]
    if не_однозначны := итог["ambiguous"]:
        raise qr.ClassificationError(
            f"{не_однозначны} событий нельзя отнести к тестовым доказательно: "
            f"{итог['ambiguous_detail'][:3]}")
    if итог["registry_events"]:
        raise qr.ClassificationError(
            f"среди кандидатов {итог['registry_events']} событий реестра")
    if ожидается is not None and len(кандидаты) != ожидается:
        # Расхождение с ожиданием — повод остановиться, а не подогнать число:
        # карантин по приблизительному фильтру хуже, чем его отсутствие.
        raise qr.ClassificationError(
            f"найдено {len(кандидаты)} событий, ожидалось {ожидается}")

    коммит = _коммит()
    файл = ДОКАЗАТЕЛЬСТВА / f"quarantine-{prompt_id}-{prompt_rev}.json"
    м = qr.собрать_манифест(кандидаты, файл, причина=qr.ПРИЧИНА_HARNESS,
                            prompt_id=prompt_id, prompt_rev=prompt_rev,
                            source_commit=коммит)
    данные = м["manifest"]
    событие = {
        "event_type": qr.СОБЫТИЕ_КАРАНТИН,
        "phase": "VERIFIED", "result": "SUCCESS", "scope": "FLEET",
        "environment": "control-plane",
        "resource_type": "ledger_event_set",
        "resource_id": f"{данные['first_ledger_seq']}-{данные['last_ledger_seq']}",
        "resource_owner": "architect",
        "correlation_id": f"{prompt_id.lower()}-{prompt_rev.lower()}",
        "action_id": action_id,
        "idempotency_key": f"quarantine-{prompt_id}-{prompt_rev}",
        "occurred_at": данные["classified_at"],
        "prompt_id": prompt_id, "prompt_rev": prompt_rev,
        "commit_sha": коммит,
        "summary": (
            f"{данные['event_count']} записей позиций "
            f"{данные['first_ledger_seq']}–{данные['last_ledger_seq']} "
            f"объявлены непригодными для рабочих решений: "
            f"{qr.ПРИЧИНА_HARNESS}. Записи не изменены и не удалены; "
            f"перечень — в манифесте {файл.name}."),
        "evidence_refs": [{
            "evidence_id": f"ev-quarantine-{prompt_id}-{prompt_rev}".lower(),
            "uri": м["path"], "checksum": м["sha256"],
            "media_type": "application/json", "size": м["size"],
            "created_at": данные["classified_at"], "producer": "architect",
            "retention_class": "PERMANENT"}],
    }
    записано = store.append(соед, событие, producer_service="architect",
                            actor_id="service:architect", actor_type="SERVICE",
                            authority="AUTHORIZE")
    store.checkpoint(соед)
    return {"quarantine_event_id": записано["event_id"],
            "ledger_seq": записано["ledger_seq"],
            "idempotent_replay": записано["idempotent_replay"],
            "manifest_path": м["path"], "manifest_sha256": м["sha256"],
            "event_count": данные["event_count"],
            "first_ledger_seq": данные["first_ledger_seq"],
            "last_ledger_seq": данные["last_ledger_seq"],
            "source_commit": коммит}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="обслуживание Audit Ledger")
    под = ap.add_subparsers(dest="команда", required=True)
    под.add_parser("inventory", help="перечислить события обвязки")
    к = под.add_parser("quarantine", help="объявить их непригодными")
    к.add_argument("--prompt-id", required=True)
    к.add_argument("--prompt-rev", required=True)
    к.add_argument("--expect", type=int, default=None,
                   help="ожидаемое число событий; расхождение — отказ")
    к.add_argument("--action-id", default=None)
    п = под.add_parser("projection-rebuild", help="пересобрать проекцию")
    п.add_argument("--shadow-only", action="store_true")
    под.add_parser("projection-status", help="состояние проекции")
    a = ap.parse_args(argv)

    соед = store.открыть(ЖУРНАЛ)
    proj.подготовить(соед)
    try:
        if a.команда == "inventory":
            итог = инвентаризация(соед)
            print(json.dumps({
                "candidates": len(итог["candidates"]),
                "ambiguous": итог["ambiguous"],
                "registry_events": итог["registry_events"],
                "production_events": итог["production_events"],
                "first_ledger_seq": min((c["ledger_seq"] for c in итог["candidates"]),
                                        default=None),
                "last_ledger_seq": max((c["ledger_seq"] for c in итог["candidates"]),
                                       default=None),
                "sample": [{k: c[k] for k in ("ledger_seq", "event_id",
                                              "event_type", "producer_service",
                                              "classification_reason")}
                           for c in итог["candidates"][:3]],
            }, ensure_ascii=False, indent=2))
            return 0
        if a.команда == "quarantine":
            итог = карантин(соед, prompt_id=a.prompt_id, prompt_rev=a.prompt_rev,
                            ожидается=a.expect,
                            action_id=a.action_id or
                            f"{a.prompt_id.lower()}-{a.prompt_rev.lower()}-quarantine")
            print(json.dumps(итог, ensure_ascii=False, indent=2))
            return 0
        if a.команда == "projection-rebuild":
            if a.shadow_only:
                print(json.dumps(proj.пересобрать_в_тени(соед, source_commit=_коммит()),
                                 ensure_ascii=False, indent=2))
            else:
                print(json.dumps(proj.пересобрать(соед, source_commit=_коммит()),
                                 ensure_ascii=False, indent=2))
            return 0
        сост = proj.состояние(соед) or {}
        print(json.dumps({"active_table": proj.активная(соед), **сост},
                         ensure_ascii=False, indent=2))
        return 0
    except qr.ClassificationError as ош:
        print(f"ОТКАЗ: {ош}", file=sys.stderr)
        return 2
    finally:
        соед.close()


if __name__ == "__main__":
    sys.exit(main())
