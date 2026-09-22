#!/usr/bin/env python3
"""Публикация проекции оценок для площадки из реестра арендаторов.

Инструмент намеренно не знает ни одного названия витрины. Он знает
арендатора: у арендатора есть каталог, пространство имён и два пути на
диске. Поэтому подключение второй площадки — это запись в
`config/unified-ratings-tenants.json`, а не копия этого файла с
заменёнными строками.

Площадка, у которой в реестре `authorized: false`, не публикуется даже
по прямому указанию ключом: разрешение живёт в реестре, а не в строке
запуска. Иначе достаточно опечатки, чтобы выложить оценки на домен,
которого задание не касалось.

Ничего не перезапускает и не трогает релизы: проекция и флаги — это
данные, которые витрина читает на каждом запросе.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from factory.unified_ratings.coverage import (  # noqa: E402
    CoverageReporter,
    load_site_title_ids,
)
from factory.unified_ratings.site_projection import (  # noqa: E402
    build_flags,
    build_projection,
    write_projection,
)
from factory.unified_ratings.store import UnifiedStore  # noqa: E402

REGISTRY = REPO / "config" / "unified-ratings-tenants.json"


def utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def load_registry(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))["tenants"]


def readiness(tenant_id: str, spec: dict, store: UnifiedStore | None) -> dict:
    """Строка матрицы готовности: что мешает именно этой площадке."""
    row = {
        "tenant": tenant_id,
        "space": spec.get("space", ""),
        "domain": spec.get("domain"),
        "authorized": bool(spec.get("authorized")),
        "stage": spec.get("stage", ""),
        "blocker": spec.get("blocker", ""),
        "details_present": False,
        "catalog_size": 0,
        "titles_known": 0,
        "coverage_percent": None,
    }
    details = spec.get("details") or ""
    if details and Path(details).is_file():
        row["details_present"] = True
        if store is not None:
            ids = load_site_title_ids(details, provider=spec.get("provider", "nova"))
            known = {r["title_id"] for r in store.query("SELECT title_id FROM unified_titles")}
            row["catalog_size"] = len(ids)
            row["titles_known"] = len(ids & known)
            sl = CoverageReporter(store).slice_for(
                name=tenant_id, denominator_label=str(spec.get("domain") or tenant_id),
                title_ids=ids & known,
            )
            row["coverage_percent"] = sl.percent(sl.titles_with_any_rating)
    elif not row["blocker"]:
        row["blocker"] = f"details-снимок не найден: {details or 'путь не задан'}"
    return row


def publish(tenant_id: str, spec: dict, store: UnifiedStore, args) -> dict:
    if not spec.get("authorized"):
        return {
            "tenant": tenant_id,
            "status": "BLOCKED_AUTHORIZATION",
            "reason": spec.get("blocker") or "площадка не авторизована в реестре",
        }
    details = spec.get("details") or ""
    if not Path(details).is_file():
        return {"tenant": tenant_id, "status": "BLOCKED_INPUT",
                "reason": f"нет details-снимка: {details or 'путь не задан'}"}

    known = {r["title_id"] for r in store.query("SELECT title_id FROM unified_titles")}
    title_ids = load_site_title_ids(details, provider=spec.get("provider", "nova")) & known

    projection = build_projection(store, space=spec["space"], title_ids=title_ids)
    flags = build_flags(
        space=spec["space"],
        cohort=title_ids,
        public_read=args.public_read,
        public_write=args.public_write,
        kill_switch=args.kill_switch,
    )
    if args.dry_run:
        return {
            "tenant": tenant_id, "status": "DRY_RUN",
            "titles_in_projection": projection["stats"]["titles_in_projection"],
            "stats": projection["stats"],
        }
    written = write_projection(projection, spec["projection"])
    Path(spec["flags"]).write_text(
        json.dumps(flags, ensure_ascii=False, sort_keys=True, indent=1) + "\n",
        encoding="utf-8",
    )
    return {
        "tenant": tenant_id,
        "status": "PUBLISHED",
        "projection": written,
        "flags_path": spec["flags"],
        "public_read": args.public_read,
        "public_write": args.public_write,
        "stats": projection["stats"],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", required=True)
    parser.add_argument("--registry", default=str(REGISTRY))
    parser.add_argument("--tenant", default="", help="пусто = только матрица готовности")
    parser.add_argument("--matrix", action="store_true", help="матрица готовности по всем")
    parser.add_argument("--public-read", action="store_true")
    parser.add_argument("--public-write", action="store_true")
    parser.add_argument("--kill-switch", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--evidence", default="")
    args = parser.parse_args()

    tenants = load_registry(Path(args.registry))
    store = UnifiedStore(args.db, apply_migration=False)

    payload: dict = {"built_at": utc(), "registry": args.registry}
    if args.matrix or not args.tenant:
        payload["matrix"] = [readiness(t, s, store) for t, s in tenants.items()]
    if args.tenant:
        if args.tenant not in tenants:
            payload["published"] = {
                "tenant": args.tenant, "status": "BLOCKED_INPUT",
                "reason": "площадки нет в реестре; пустое поле — не разрешение подставить умолчание",
            }
        else:
            payload["published"] = publish(args.tenant, tenants[args.tenant], store, args)

    if args.evidence:
        Path(args.evidence).parent.mkdir(parents=True, exist_ok=True)
        Path(args.evidence).write_text(
            json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    store.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
