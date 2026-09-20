"""Weekly Popular snapshot for Zona (and shared nova families).

Contract (owner Pass7 correction):
  POPULAR_REFRESH_MODE=WEEKLY_SNAPSHOT
  POPULAR_REQUEST_TIME_RECOMPUTES=0
  POPULAR_MAX_PUBLICATIONS_PER_WEEK=1
  POPULAR_MEMBERSHIP_STABLE_WITHIN_WEEK=YES
  POPULAR_RANDOM_ROTATION=NO

Ranking signal at build time: max(source rating) among a documented recent
pool (default 400 by catalog published_at). No invented views, no shuffle.

Does NOT start a systemd timer. Owner must schedule the builder (see
popular-weekly.zona-01.example.json). Frontend only *reads* the published file.
"""
from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import os
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any

SCHEMA = "zona.popular-weekly/1.0.0"
DEFAULT_POOL = 400
DEFAULT_LIMIT = 12
DEFAULT_RESERVE = 24
SHELF_KINDS = {
    "pop-films": "Фильм",
    "pop-series": "Сериал",
    "pop-anim": "Мультфильм",
}


def week_id(clock: str | datetime | None = None) -> str:
    """ISO week id YYYY-Www from UTC clock (Monday-based)."""
    if clock is None:
        dt = datetime.now(timezone.utc)
    elif isinstance(clock, datetime):
        dt = clock if clock.tzinfo else clock.replace(tzinfo=timezone.utc)
    else:
        dt = datetime.fromisoformat(str(clock).replace("Z", "+00:00"))
    iso = dt.isocalendar()
    return f"{iso.year}-W{iso.week:02d}"


def next_week_start_utc(clock: str | datetime | None = None) -> datetime:
    if clock is None:
        dt = datetime.now(timezone.utc)
    elif isinstance(clock, datetime):
        dt = clock if clock.tzinfo else clock.replace(tzinfo=timezone.utc)
    else:
        dt = datetime.fromisoformat(str(clock).replace("Z", "+00:00"))
    # Next Monday 00:00 UTC after current week's Monday.
    weekday = dt.weekday()  # Mon=0
    this_monday = (dt - timedelta(days=weekday)).replace(
        hour=0, minute=0, second=0, microsecond=0)
    return this_monday + timedelta(days=7)


def _rating(detail: dict) -> float:
    best = 0.0
    for key in ("kinopoisk_rating", "imdb_rating"):
        raw = detail.get(key)
        try:
            val = float(raw)
        except (TypeError, ValueError):
            continue
        if 0.0 < val <= 10.0:
            best = max(best, val)
    return best


def _digest(payload: dict) -> str:
    shelves = payload.get("shelves") or {}
    reserves = payload.get("reserves") or {}
    basis = {
        "week_id": payload.get("week_id"),
        "shelves": {k: list(shelves.get(k) or []) for k in sorted(SHELF_KINDS)},
        "reserves": {k: list(reserves.get(k) or []) for k in sorted(SHELF_KINDS)},
        "ranking_signal": payload.get("ranking_signal"),
        "pool": payload.get("pool"),
        "limit": payload.get("limit"),
    }
    raw = json.dumps(basis, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def build_snapshot(
    items: list[dict],
    details: dict[str, dict],
    *,
    clock: str | datetime | None = None,
    pool: int = DEFAULT_POOL,
    limit: int = DEFAULT_LIMIT,
    reserve: int = DEFAULT_RESERVE,
) -> dict[str, Any]:
    """Deterministic weekly membership. Never shuffles."""
    wid = week_id(clock)
    if isinstance(clock, datetime):
        built_at = clock.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    elif clock:
        built_at = str(clock).replace("+00:00", "Z")
        if not built_at.endswith("Z"):
            built_at = datetime.fromisoformat(
                str(clock).replace("Z", "+00:00")
            ).astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    else:
        built_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    by_kind: dict[str, list[dict]] = {k: [] for k in SHELF_KINDS}
    for item in items:
        kind = item.get("kind")
        for shelf, want in SHELF_KINDS.items():
            if kind == want:
                by_kind[shelf].append(item)

    shelves: dict[str, list[str]] = {}
    reserves: dict[str, list[str]] = {}
    for shelf, candidates in by_kind.items():
        recent = sorted(
            candidates,
            key=lambda з: (з.get("published_at") or "", з.get("slug") or ""),
            reverse=True,
        )[:pool]

        def score(з: dict) -> tuple:
            d = details.get(з["slug"]) or {}
            r = _rating(d)
            return (1 if r > 0 else 0, r, з.get("published_at") or "", з.get("slug") or "")

        ranked = sorted(recent, key=score, reverse=True)
        slugs = [з["slug"] for з in ranked]
        shelves[shelf] = slugs[:limit]
        reserves[shelf] = slugs[limit: limit + reserve]

    snap = {
        "schema": SCHEMA,
        "mode": "WEEKLY_SNAPSHOT",
        "week_id": wid,
        "built_at": built_at,
        "ranking_signal": "source_rating_in_recent_pool",
        "ranking_window": f"top_{pool}_by_published_at_then_rating",
        "pool": pool,
        "limit": limit,
        "reserve": reserve,
        "request_time_recomputes": False,
        "random_rotation": False,
        "invented_views": False,
        "shelves": shelves,
        "reserves": reserves,
        "emergency_log": [],
    }
    snap["digest"] = _digest(snap)
    return snap


def load_snapshot(path: Path | str) -> dict[str, Any] | None:
    p = Path(path)
    if not p.is_file():
        return None
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(data, dict) or not data.get("shelves"):
        return None
    return data


def publish_snapshot(
    snap: dict[str, Any],
    path: Path | str,
    *,
    wait_lock: bool = True,
    force: bool = False,
) -> dict[str, Any]:
    """Atomic publish with at-most-one regular publication per week_id."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    lock_path = path.with_suffix(path.suffix + ".lock")
    lock_path.touch(exist_ok=True)
    flags = fcntl.LOCK_EX
    if not wait_lock:
        flags |= fcntl.LOCK_NB
    try:
        lockf = open(lock_path, "a+", encoding="utf-8")
    except OSError as e:
        return {"published": False, "reason": f"lock_open_failed:{e}"}
    try:
        try:
            fcntl.flock(lockf.fileno(), flags)
        except BlockingIOError:
            return {"published": False, "reason": "lock_held"}

        existing = load_snapshot(path)
        if existing and not force:
            if (existing.get("week_id") == snap.get("week_id")
                    and existing.get("digest") == snap.get("digest")):
                return {
                    "published": False,
                    "reason": "same_week_same_digest",
                    "week_id": existing.get("week_id"),
                    "digest": existing.get("digest"),
                }
            if existing.get("week_id") == snap.get("week_id"):
                return {
                    "published": False,
                    "reason": "week_already_published",
                    "week_id": existing.get("week_id"),
                    "digest": existing.get("digest"),
                    "attempted_digest": snap.get("digest"),
                }

        tmp = path.with_suffix(path.suffix + ".new")
        payload = dict(snap)
        payload["digest"] = _digest(payload)
        tmp.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8")
        os.replace(tmp, path)
        return {
            "published": True,
            "reason": "ok",
            "week_id": payload["week_id"],
            "digest": payload["digest"],
            "path": str(path),
        }
    finally:
        try:
            fcntl.flock(lockf.fileno(), fcntl.LOCK_UN)
        except OSError:
            pass
        lockf.close()


def emergency_repair(
    path: Path | str,
    *,
    shelf: str,
    remove_slug: str,
    reason: str,
    catalog_items: list[dict] | None = None,
    details: dict[str, dict] | None = None,
) -> dict[str, Any]:
    """Remove one broken member; fill from precomputed reserve. No full rotation."""
    path = Path(path)
    snap = load_snapshot(path)
    if snap is None:
        return {
            "POPULAR_EMERGENCY_REPAIR": 0,
            "POPULAR_REGULAR_WEEKLY_ROTATION": 0,
            "POPULAR_EMERGENCY_REASON": "snapshot_missing",
        }
    members = list((snap.get("shelves") or {}).get(shelf) or [])
    reserves = list((snap.get("reserves") or {}).get(shelf) or [])
    if remove_slug not in members:
        return {
            "POPULAR_EMERGENCY_REPAIR": 0,
            "POPULAR_REGULAR_WEEKLY_ROTATION": 0,
            "POPULAR_EMERGENCY_REASON": "slug_not_in_shelf",
        }
    members = [s for s in members if s != remove_slug]
    replacement = None
    for cand in reserves:
        if cand not in members and cand != remove_slug:
            # Prefer still-present catalog titles when provided.
            if catalog_items is not None:
                known = {з.get("slug") for з in catalog_items}
                if cand not in known:
                    continue
                if details is not None:
                    d = details.get(cand) or {}
                    if d.get("playable") is False:
                        continue
            replacement = cand
            break
    if replacement:
        members.append(replacement)
        reserves = [c for c in reserves if c != replacement]
    snap["shelves"][shelf] = members
    snap["reserves"][shelf] = reserves
    log = list(snap.get("emergency_log") or [])
    log.append({
        "at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "shelf": shelf,
        "removed": remove_slug,
        "replacement": replacement,
        "reason": reason,
    })
    snap["emergency_log"] = log
    snap["digest"] = _digest(snap)
    # Force overwrite same week — emergency is the allowed exception.
    publish_snapshot(snap, path, force=True)
    return {
        "POPULAR_EMERGENCY_REPAIR": 1,
        "POPULAR_REGULAR_WEEKLY_ROTATION": 0,
        "POPULAR_EMERGENCY_REASON": reason,
        "removed": remove_slug,
        "replacement": replacement,
        "week_id": snap["week_id"],
        "digest": snap["digest"],
    }


def default_path_for_catalog(catalog_path: str) -> Path:
    p = Path(catalog_path)
    name = p.name
    if name.endswith("-catalog.json"):
        site = name[: -len("-catalog.json")]
        return p.with_name(f"{site}-popular-weekly.json")
    return p.with_name("popular-weekly.json")


def main(argv: list[str] | None = None) -> int:
    р = argparse.ArgumentParser(description=__doc__)
    р.add_argument("--catalog", required=True)
    р.add_argument("--details", default="")
    р.add_argument("--out", default="")
    р.add_argument("--clock", default="")
    р.add_argument("--force", action="store_true")
    р.add_argument("--pool", type=int, default=DEFAULT_POOL)
    р.add_argument("--limit", type=int, default=DEFAULT_LIMIT)
    args = р.parse_args(argv)
    cat = json.loads(Path(args.catalog).read_text(encoding="utf-8"))
    items = cat.get("items") or []
    details: dict[str, dict] = {}
    det_path = args.details or str(
        Path(args.catalog).with_name(
            Path(args.catalog).name.replace("-catalog.json", "-details.json")))
    if Path(det_path).is_file():
        raw = json.loads(Path(det_path).read_text(encoding="utf-8"))
        details = raw.get("details") or {}
    out = Path(args.out) if args.out else default_path_for_catalog(args.catalog)
    snap = build_snapshot(
        items, details, clock=args.clock or None,
        pool=args.pool, limit=args.limit)
    result = publish_snapshot(snap, out, force=args.force)
    print(json.dumps(result, ensure_ascii=False))
    return 0 if result.get("published") or result.get("reason") in (
        "same_week_same_digest", "week_already_published") else 1


if __name__ == "__main__":
    raise SystemExit(main())
