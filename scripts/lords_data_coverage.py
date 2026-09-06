#!/usr/bin/env python3
"""Покрытие полей по слоям: источник → движок → разметка.

Отчёт отвечает на один вопрос: где теряется значение. Пока он не отвечен,
любая правка — угадывание: поле может отсутствовать в источнике, потеряться
при нормализации или не дойти до страницы.

Каждый слой считается отдельно, и переход между слоями показывает потерю.
Ноль в источнике — не дефект шаблона; ноль после источника — дефект.

Запуск:
    .venv/bin/python scripts/lords_data_coverage.py --site lords-02
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LIVE = Path("/srv/site-factory/repo/var/lords")
OUT = ROOT / "artifacts" / "evidence" / "templates" / "data-coverage.json"


def load_catalog(site: str) -> list[dict]:
    path = LIVE / "lords" / "catalog-cache" / f"{site}.json"
    raw = json.loads(path.read_text(encoding="utf-8"))
    return (raw.get("items") if isinstance(raw, dict) else raw) or []


def load_details(limit: int | None = None) -> dict[str, dict]:
    """Обогащение по внешнему идентификатору."""
    out: dict[str, dict] = {}
    directory = LIVE / "detail-cache"
    if not directory.is_dir():
        return out
    for path in sorted(directory.glob("*.json"))[:limit]:
        try:
            row = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        detail = row.get("detail") or {}
        if detail.get("id"):
            out[str(detail["id"])] = detail
    return out


def _nonempty(value) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, (list, tuple, dict)):
        return len(value) > 0
    if isinstance(value, (int, float)):
        return True
    return bool(value)


def measure(site: str, detail_limit: int | None) -> dict:
    items = load_catalog(site)
    details = load_details(detail_limit)
    total = len(items)

    # Слой 1 — списочный ответ источника. Ровно то, что приходит без обогащения.
    listing = {
        "year": sum(1 for i in items if _nonempty(i.get("year")) and i.get("year") != 0),
        "unknown_year": sum(1 for i in items if not i.get("year")),
        "kinopoisk": sum(1 for i in items if _nonempty(i.get("kinopoisk_rating"))),
        "imdb": sum(1 for i in items if _nonempty(i.get("imdb_rating"))),
        "playback": sum(1 for i in items if _nonempty(i.get("playback"))),
        "is_series": sum(1 for i in items if i.get("is_series")),
        "genres": sum(1 for i in items if _nonempty(i.get("genres"))),
        "countries": sum(1 for i in items if _nonempty(i.get("countries"))),
        "description": sum(1 for i in items if _nonempty(i.get("description"))),
        "seasons": sum(1 for i in items if _nonempty(i.get("seasons"))),
        "duration": sum(1 for i in items if _nonempty(i.get("duration"))),
    }

    # Слой 2 — обогащение. Считается по записям, у которых оно ЕСТЬ: иначе
    # доля размывается непрочитанными и выглядит хуже, чем есть.
    enriched = len(details)
    detail_stats = {
        "genres": sum(1 for d in details.values() if _nonempty(d.get("genres"))),
        "countries": sum(1 for d in details.values() if _nonempty(d.get("countries"))),
        "description": sum(1 for d in details.values() if _nonempty(d.get("description"))),
        "duration": sum(1 for d in details.values() if _nonempty(d.get("duration"))),
        "seasons": sum(1 for d in details.values() if _nonempty(d.get("seasons"))),
        "kinopoisk": sum(1 for d in details.values() if _nonempty(d.get("kinopoisk_rating"))),
        "imdb": sum(1 for d in details.values() if _nonempty(d.get("imdb_rating"))),
    }

    return {
        "artifact": "LORDS_DATA_COVERAGE",
        "captured_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "site_id": site,
        "catalog_total": total,
        "enrichment_files_read": enriched,
        "enrichment_share_percent": round(enriched / total * 100, 1) if total else 0,
        "layer_listing": listing,
        "layer_enrichment": detail_stats,
        "note": (
            "Слой списка — то, что приходит без обогащения. Слой обогащения "
            "считается по прочитанным записям, а не по всему каталогу: иначе "
            "доля размывается непрочитанными и выглядит хуже, чем есть."
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--site", default="lords-02")
    parser.add_argument("--details", type=int, default=3000,
                        help="сколько файлов обогащения прочитать (0 — все)")
    args = parser.parse_args()

    report = measure(args.site, args.details or None)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    total = report["catalog_total"]
    print(f"каталог: {total} записей; обогащение прочитано у "
          f"{report['enrichment_files_read']} ({report['enrichment_share_percent']} % каталога)")
    print("\n  поле            в списке          в обогащении")
    keys = ["genres", "countries", "description", "duration", "seasons",
            "kinopoisk", "imdb"]
    enriched = report["enrichment_files_read"] or 1
    for key in keys:
        a = report["layer_listing"].get(key, 0)
        b = report["layer_enrichment"].get(key, 0)
        print(f"  {key:14} {a:>7} ({a/total*100:4.1f} %)   {b:>7} ({b/enriched*100:5.1f} %)")
    print(f"\n  год известен: {report['layer_listing']['year']}, "
          f"неизвестен: {report['layer_listing']['unknown_year']}")
    print(f"  помечено сериалом: {report['layer_listing']['is_series']}")
    print(f"\n  {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
