#!/usr/bin/env python3
"""Манифест доказательств: что измерено, чем и с каким отпечатком.

Числа в итоговом отчёте берутся отсюда, а не набираются руками. Каждое имеет
источник — файл прогона, снимок хранилища или вывод pytest, — и у каждого
файла записан sha256.

    python3 scripts/seo_content/build_evidence.py
"""
from __future__ import annotations

import hashlib
import json
import pathlib
import subprocess
import sys

КОРЕНЬ = pathlib.Path(__file__).resolve().parents[2]
ДОКАЗАТЕЛЬСТВА = КОРЕНЬ / "artifacts" / "evidence" / "fleet-seo-004"


def отпечаток(путь: pathlib.Path) -> dict:
    данные = путь.read_bytes()
    return {"path": str(путь.relative_to(КОРЕНЬ)),
            "sha256": hashlib.sha256(данные).hexdigest(),
            "bytes": len(данные)}


def прогон(имя: str) -> dict:
    return json.loads((ДОКАЗАТЕЛЬСТВА / имя).read_text("utf-8"))


def тесты() -> dict:
    """Полный прогон набора. Число берётся из вывода, а не из памяти."""
    итог = subprocess.run(
        [sys.executable, "-m", "pytest", "tests/seo_content/", "-q",
         "--tb=no"], cwd=КОРЕНЬ, capture_output=True, text=True, timeout=1800)
    хвост = [с for с in итог.stdout.strip().splitlines() if с.strip()][-1:]
    строка = хвост[0] if хвост else ""
    разбор = {"passed": 0, "failed": 0, "skipped": 0, "xfailed": 0,
              "error": 0}
    import re
    for ключ in разбор:
        м = re.search(rf"(\d+) {ключ}", строка)
        if м:
            разбор[ключ] = int(м.group(1))
    return {"command": "python3 -m pytest tests/seo_content/ -q",
            "exit_code": итог.returncode, "summary": строка, **разбор}


#: Каталоги, изменение которых означало бы касание production.
ЗАПРЕТНЫЕ_ПУТИ = (
    "blueprints/", "themes/", "plugins/", "sites/", "automation/",
    "deploy/", "inventory/", "knowledge/", "migrations/",
    "factory/lords/", "factory/site_engine/", "seo_operator/",
    "contracts/", ".github/", "queue/",
)


def изменённые_пути() -> dict:
    """Что ветка меняет на самом деле.

    Утверждение «production не тронут» проверяется списком путей, а не
    памятью: если бы правка шаблона, плеера или реестра случилась, она
    оказалась бы здесь.
    """
    база = subprocess.run(
        ["git", "merge-base", "HEAD", "origin/claude/arc-seo-canonical-proposal-003"],
        cwd=КОРЕНЬ, capture_output=True, text=True).stdout.strip()
    отслеженные = subprocess.run(
        ["git", "diff", "--name-only", база], cwd=КОРЕНЬ,
        capture_output=True, text=True).stdout.split()
    неотслеженные = subprocess.run(
        ["git", "ls-files", "--others", "--exclude-standard"], cwd=КОРЕНЬ,
        capture_output=True, text=True).stdout.split()
    пути = sorted(set(отслеженные) | set(неотслеженные))
    # Резервные копии, оставленные оснасткой сессии, к работе не относятся и
    # в ветку не входят.
    пути = [п for п in пути if ".bak." not in п]
    задетые = [п for п in пути if п.startswith(ЗАПРЕТНЫЕ_ПУТИ)]
    return {"base": база, "changed": пути,
            "production_paths_touched": задетые,
            "PRODUCTION_MUTATIONS": len(задетые)}


def главное() -> int:
    g, h = прогон("golden-run.json"), прогон("holdout-run.json")
    до = прогон("shared-store-before.json")
    после = прогон("shared-store-after.json")
    т = тесты()

    def виды(корпус_путь: str) -> dict:
        данные = json.loads((КОРЕНЬ / корпус_путь).read_text("utf-8"))
        счёт: dict[str, int] = {}
        рёбра = 0
        for с in данные["cases"]:
            счёт[с["kind"]] = счёт.get(с["kind"], 0) + 1
            теги = set(с["tags"])
            if с["kind"] == "negative" or теги & {
                    "edge", "boundary", "poor_factpack", "no_synopsis",
                    "duplicate", "injection", "identity", "sparse"}:
                рёбра += 1
        счёт["edge_or_negative"] = рёбра
        счёт["total"] = len(данные["cases"])
        return счёт

    сравнение = после.get("comparison", {})
    манифест = {
        "prompt_id": "FLEET-SEO-004-CONTENT-QUALITY",
        "prompt_rev": "R1",
        "corpus": {
            "golden": виды("tests/seo_content/fixtures/golden.json"),
            "holdout": виды("tests/seo_content/fixtures/holdout.json"),
        },
        "runs": {
            "golden": {"statuses": g["statuses"],
                       "expectation_mismatches": g["expectations"]["mismatches"],
                       "template_collisions_allowed":
                           g["expectations"]["template_collisions_allowed"],
                       "counters": g["counters"],
                       "accepted_counters": g["accepted_counters"],
                       "claim_verdicts": g["claim_verdicts"],
                       "corpus_patterns": {
                           k: v for k, v in g["corpus_patterns"].items()
                           if k not in ("top_openings", "top_endings",
                                        "top_frames")},
                       "blind_scores": g["blind_scores"],
                       "body_length": g["body_length"],
                       "store": g["store"], "writer": g["writer"],
                       "budget": g["budget"]},
            "holdout": {"statuses": h["statuses"],
                        "expectation_mismatches":
                            h["expectations"]["mismatches"],
                        "counters": h["counters"],
                        "accepted_counters": h["accepted_counters"],
                        "blind_scores": h["blind_scores"],
                        "store": h["store"], "writer": h["writer"]},
        },
        "tests": т,
        "repository": изменённые_пути(),
        "shared_store": {
            "mode": "READ_ONLY",
            "before": {"key_rows": до["changeset_store"]["key_rows"],
                       "outbox_rows": до["changeset_store"]["outbox_rows"],
                       "rows": до["changeset_store"]["rows"],
                       "audit_r4_tail": до["audit_ledger"]["r4_tail_events"],
                       "file_sha256": до["file"]["sha256"]},
            "after": {"key_rows": после["changeset_store"]["key_rows"],
                      "outbox_rows": после["changeset_store"]["outbox_rows"],
                      "rows": после["changeset_store"]["rows"],
                      "audit_r4_tail": после["audit_ledger"]["r4_tail_events"],
                      "file_sha256": после["file"]["sha256"]},
            "comparison": сравнение,
            "SHARED_STORE_WRITES": сравнение.get("SHARED_STORE_WRITES"),
            "SHARED_STORE_IDENTIFIER_DELTA":
                сравнение.get("SHARED_STORE_IDENTIFIER_DELTA"),
            "SHARED_STORE_CONTENT_HASH_DELTA":
                сравнение.get("SHARED_STORE_CONTENT_HASH_DELTA"),
            "OWNER_CLEANUP_STATUS": "PENDING",
            "cleanup_owner": "Changeset Store/Control Plane",
        },
        "not_evaluated": {
            "LIVE_QWEN_QUALITY": "живой Qwen не разрешён владельцем",
            "HUMAN_REVIEW_STATUS": "человеческой выборки не было",
            "SEMANTIC_SIMILARITY": "локальных embeddings нет; порог 0,92 не мерялся",
            "SPELLING": "LanguageTool отсутствует, публичный сервис не используется",
            "FULL_MORPHOLOGY": "pymorphy отсутствует; проверены только счётные формы",
            "RICH_RESULT_DISPLAY": "показ решает поисковая система, а не разметка",
            "FREE_SERVICE_LIMITS": "официальные источники недоступны (403)",
        },
        "artifacts": [отпечаток(п) for п in sorted(
            list(ДОКАЗАТЕЛЬСТВА.glob("*.json"))
            + list((КОРЕНЬ / "schemas").glob("seo-fact-pack.schema.json"))
            + list((КОРЕНЬ / "schemas").glob("seo-content-draft.schema.json"))
            + list((КОРЕНЬ / "schemas").glob("seo-editorial-note.schema.json"))
            + list((КОРЕНЬ / "tests/seo_content/fixtures").glob("*.json")))
            if п.name != "EVIDENCE-MANIFEST.json"],
    }
    путь = ДОКАЗАТЕЛЬСТВА / "EVIDENCE-MANIFEST.json"
    путь.write_text(json.dumps(манифест, ensure_ascii=False, indent=1),
                    encoding="utf-8")
    print(json.dumps({k: v for k, v in манифест.items()
                      if k in ("corpus", "tests", "shared_store")},
                     ensure_ascii=False, indent=1)[:2000])
    return 0


if __name__ == "__main__":
    sys.exit(главное())
