#!/usr/bin/env python3
"""Genesis и честный bootstrap журнала.

Ретроспективная история не выдумывается. Первой записью становится граница
достоверного наблюдения: всё, что было до неё, в журнал попадает только как
ИМПОРТ с фактическим `imported_at`, и выдавать это время за исходное
`occurred_at` нельзя — иначе журнал начнёт утверждать, что наблюдал то, чего
не видел.
"""
from __future__ import annotations

import hashlib, json, os, sqlite3, sys, uuid
from pathlib import Path

from . import ledger_store as store

БД = os.environ.get("AUDIT_LEDGER_DB",
                    "/srv/site-factory/audit-ledger/audit_ledger.sqlite3")
РЕЕСТР = "/srv/site-factory/registry-core/registry.sqlite3"
ДОЛГ = ["synthetic-http-b4e4f1", "synthetic-npo-1c85d0bd",
        "synthetic-npo-30c9237d"]
ОТЧЁТЫ = Path("/srv/site-factory/control-plane-contracts/evidence")


def как(соед, событие, служба="architect", полномочие="OBSERVE",
        тип="SERVICE"):
    return store.append(соед, событие, producer_service=служба,
                        actor_id=f"service:{служба}", actor_type=тип,
                        authority=полномочие, известные_сайты=None)


def доказательство(п: Path) -> dict | None:
    if not п.is_file():
        return None
    b = п.read_bytes()
    return {"evidence_id": "ev-" + hashlib.sha256(str(п).encode()).hexdigest()[:12],
            "uri": str(п), "checksum": hashlib.sha256(b).hexdigest(),
            "media_type": "application/json", "size": len(b),
            "created_at": store.сейчас(), "producer": "architect",
            "retention_class": "AUDIT"}


def main() -> int:
    соед = store.открыть(БД)
    есть = соед.execute("SELECT count(*) c FROM ledger_event").fetchone()["c"]
    if есть:
        print(f"  журнал уже содержит {есть} событий; genesis не повторяется")
        return 0

    r = sqlite3.connect(f"file:{РЕЕСТР}?mode=ro", uri=True)
    r.row_factory = sqlite3.Row
    все = [dict(x) for x in r.execute("SELECT * FROM site")]
    prod = [x for x in все if x["environment"] == "production"
            and x["lifecycle_state"] == "ACTIVE"]
    ids = sorted(x["site_id"] for x in все)
    H = hashlib.sha256(json.dumps(ids, ensure_ascii=False).encode()).hexdigest()
    версия = r.execute("SELECT version FROM registry_version").fetchone()["version"]
    r.close()

    корр = "genesis-" + uuid.uuid4().hex[:8]
    g = как(соед, {
        "event_type": "ledger.genesis.v1", "phase": "GENESIS",
        "result": "SUCCESS", "scope": "FLEET", "environment": "control-plane",
        "correlation_id": корр, "idempotency_key": "ledger-genesis",
        "prompt_id": "FLEET-CORE-002-AUDIT-LEDGER", "prompt_rev": "R1",
        "summary": ("начало достоверного наблюдения: всё, что случилось "
                    "раньше, попадает в журнал только как импорт"),
        "resource_type": "ledger", "resource_id": "audit-ledger",
        "resource_owner": "architect",
        "commit_sha": "d158064",
        "evidence_refs": [e for e in [доказательство(ОТЧЁТЫ / "r3-baseline.json")] if e],
    })
    print("  GENESIS:", g["event_id"], "seq", g["ledger_seq"])

    как(соед, {
        "event_type": "registry.baseline.observed.v1", "phase": "OBSERVED",
        "result": "SUCCESS", "scope": "FLEET", "correlation_id": корр,
        "causation_id": g["event_id"],
        "idempotency_key": "bootstrap-registry-baseline",
        "resource_type": "site_registry", "resource_id": "registry",
        "resource_owner": "architect",
        "summary": (f"реестр: всего {len(все)}, production ACTIVE {len(prod)}, "
                    f"demo 1, исторических synthetic {len(ДОЛГ)}; "
                    f"registry_version {версия}, checksum {H[:16]}"),
        "after_hash": H, "prompt_id": "FLEET-CORE-002-AUDIT-LEDGER",
    })

    for sid in ДОЛГ:
        как(соед, {
            "event_type": "technical.debt.observed.v1", "phase": "OBSERVED",
            "result": "NOT_APPLICABLE", "scope": "SITE", "site_id": sid,
            "correlation_id": корр, "causation_id": g["event_id"],
            "idempotency_key": f"bootstrap-debt-{sid}",
            "resource_type": "site", "resource_id": sid,
            "resource_owner": "architect",
            "summary": ("исторический технический долг: синтетическая запись "
                        "прошлых прогонов N+1; происхождение доказано "
                        "косвенно, полей created_by и test_run_id в схеме "
                        "нет; hard delete запрещён без разрешения владельца"),
            "prompt_id": "FLEET-CORE-002-AUDIT-LEDGER",
        })

    for пид, рев, ком in (("FLEET-ARC-001", "R1", "4d8cb5a"),
                          ("FLEET-CORE-001-CONTROL-PLANE-CONTRACTS", "R1", "c9a643f"),
                          ("FLEET-CORE-001-CONTROL-PLANE-CONTRACTS", "R2", "cd1cd8b"),
                          ("FLEET-CORE-001-CONTROL-PLANE-CONTRACTS", "R3", "d158064")):
        как(соед, {
            "event_type": "prompt.result.imported.v1", "phase": "OBSERVED",
            "result": "SUCCESS", "scope": "FLEET", "correlation_id": корр,
            "causation_id": g["event_id"],
            "idempotency_key": f"bootstrap-import-{пид}-{рев}",
            "resource_type": "prompt", "resource_id": f"{пид}:{рев}",
            "resource_owner": "architect", "commit_sha": ком,
            "prompt_id": пид, "prompt_rev": рев,
            # imported_at — это `received_at`, назначенный сервером сейчас.
            # Исходное время прогона журналом не наблюдалось и не
            # подставляется: у импорта нет occurred_at.
            "summary": (f"результат {пид}.{рев} импортирован как evidence; "
                        f"исходное время прогона журналом не наблюдалось"),
        })

    как(соед, {
        "event_type": "unverified.observation.v1", "phase": "OBSERVED",
        "result": "PENDING", "scope": "FLEET", "correlation_id": корр,
        "causation_id": g["event_id"],
        "idempotency_key": "bootstrap-unverified-yummy-latency",
        "resource_type": "observation", "resource_id": "yummy-latency",
        "resource_owner": "monitoring",
        "error_code": "UNVERIFIED",
        "summary": ("один домен Yummy требовал повтора либо отвечал за 6–7 с. "
                    "Отчёты расходятся: в одном месте назван yummyani.site, в "
                    "другом yummyani.org. Конкретный домен НЕ объявляется "
                    "неисправным до измерения; владелец — MONITORING, "
                    "verified=false"),
    })

    n = соед.execute("SELECT count(*) c FROM ledger_event").fetchone()["c"]
    cp = store.checkpoint(соед)
    print(f"  bootstrap завершён: событий {n}")
    print(f"  checkpoint {cp['checkpoint_id']} seq {cp['ledger_seq']} "
          f"root {cp['chain_root'][:16]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
