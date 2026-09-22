#!/usr/bin/env python3
"""Снимок состояния плеера витрины: до выкладки и после, одним и тем же способом.

Плеер — контур, который нельзя чинить задним числом: если после выкладки число
записей с просмотром упало, узнать об этом нужно из сравнения чисел, а не из
жалобы. Поэтому снимок снимается одинаково с обеих сторон и сравнивается
механически.

Что считается:

* сколько записей каталога помечены доступными к просмотру (`playable`);
* сколько записей имеют хотя бы один источник (`sources`);
* контрольная выборка привязок — фиксированный, детерминированный отбор по
  порядку идентификаторов, а не «несколько наугад»: случайная выборка каждый
  раз своя и сравнивать её не с чем;
* живое состояние блока плеера у нескольких фильмов, сериалов и серий.

Читает. Ничего не меняет.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ФРОНТ = Path("/srv/lords/.frontend")
ВЫБОРКА = 40


def загрузить(site_id: str) -> tuple[dict, dict]:
    каталог = json.loads((ФРОНТ / f"{site_id}-catalog.json").read_text(encoding="utf-8"))
    подробности = json.loads((ФРОНТ / f"{site_id}-details.json").read_text(encoding="utf-8"))
    return каталог, подробности


def привязки(подробности: dict) -> dict:
    записи = подробности.get("details") or {}
    playable, со_источником, всего = 0, 0, 0
    по_виду: dict[str, dict[str, int]] = {}
    for slug, деталь in записи.items():
        всего += 1
        вид = str(деталь.get("type") or "?")
        строка = по_виду.setdefault(вид, {"total": 0, "playable": 0, "with_sources": 0})
        строка["total"] += 1
        if деталь.get("playable"):
            playable += 1
            строка["playable"] += 1
        if деталь.get("sources"):
            со_источником += 1
            строка["with_sources"] += 1
    return {"total": всего, "playable": playable, "with_sources": со_источником,
            "by_kind": по_виду}


def контрольная_выборка(подробности: dict, сколько: int = ВЫБОРКА) -> dict:
    """Детерминированный отбор: первые N доступных к просмотру по порядку slug.

    Порядок фиксирован, значит «та же выборка» — это факт, а не надежда.
    """
    записи = подробности.get("details") or {}
    выбранные = {}
    for slug in sorted(записи):
        деталь = записи[slug]
        if not деталь.get("playable"):
            continue
        источники = деталь.get("sources") or []
        отпечаток = hashlib.sha256(
            json.dumps(источники, ensure_ascii=False, sort_keys=True).encode("utf-8")
        ).hexdigest()[:16]
        выбранные[slug] = {"type": деталь.get("type"), "sources": len(источники),
                           "binding_sha256": отпечаток}
        if len(выбранные) >= сколько:
            break
    return выбранные


def живое(origin: str, host: str, slugs: list[str]) -> dict:
    итог = {}
    for slug in slugs:
        путь = f"/title/{urllib.parse.quote(slug)}/"
        запрос = urllib.request.Request(origin + путь, headers={"Host": host})
        try:
            with urllib.request.urlopen(запрос, timeout=45) as r:
                тело = r.read().decode("utf-8", "replace")
                код = r.status
        except urllib.error.HTTPError as e:
            тело, код = e.read().decode("utf-8", "replace"), e.code
        except Exception as e:
            итог[slug] = {"error": f"{type(e).__name__}: {e}"}
            continue
        import re
        состояние = (re.findall(r'data-player[^>]*data-state="([a-z]+)"', тело)
                     or re.findall(r'data-state="([a-z]+)"[^>]*data-player', тело))
        кадры = re.findall(r"<iframe[^>]*>", тело)
        src = re.findall(r'<iframe[^>]*src="([^"]*)"', тело)
        итог[slug] = {
            "status": код,
            "player_state": состояние[0] if состояние else None,
            "iframes": len(кадры),
            "iframe_with_src": len([s for s in src if s]),
            "has_player_block": bool(состояние),
        }
    return итог


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--site", required=True)
    parser.add_argument("--origin", default=None, help="если задан, снимается и живое состояние")
    parser.add_argument("--host", default=None)
    parser.add_argument("--out", required=True)
    parser.add_argument("--live-sample", type=int, default=8)
    args = parser.parse_args()

    каталог, подробности = загрузить(args.site)
    снимок = {
        "site": args.site,
        "taken_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "catalog_revision": каталог.get("revision"),
        "catalog_built_at": каталог.get("builtAt"),
        "catalog_items": каталог.get("count") or len(каталог.get("items") or []),
        "bindings": привязки(подробности),
    }
    выборка = контрольная_выборка(подробности)
    снимок["control_sample"] = выборка
    снимок["control_sample_digest"] = hashlib.sha256(
        json.dumps(выборка, ensure_ascii=False, sort_keys=True).encode("utf-8")
    ).hexdigest()

    if args.origin:
        slugs = list(выборка)[: args.live_sample]
        снимок["live"] = живое(args.origin, args.host or args.site, slugs)
        состояния: dict[str, int] = {}
        for v in снимок["live"].values():
            ключ = v.get("player_state") or v.get("error") or "нет-блока"
            состояния[ключ] = состояния.get(ключ, 0) + 1
        снимок["live_states"] = состояния

    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(снимок, ensure_ascii=False, indent=2),
                              encoding="utf-8")
    печать = {k: снимок[k] for k in ("site", "catalog_items", "control_sample_digest")}
    печать["bindings"] = {k: v for k, v in снимок["bindings"].items() if k != "by_kind"}
    печать["by_kind"] = снимок["bindings"]["by_kind"]
    печать["live_states"] = снимок.get("live_states")
    print(json.dumps(печать, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
