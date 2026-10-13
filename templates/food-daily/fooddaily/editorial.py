"""Редакционные операции и снимок контента для сборки.

Снимок (data/content-snapshot.json) — единственный вход публичного сайта:
наш текст из текущей версии, факты (количества, порции, время источника),
атрибуция источника, даты. Исходных текстов шагов в нём нет.
Публичное чтение работает без БД, без Qwen и без внешних API.
"""

from __future__ import annotations

import argparse
import difflib
import json
import re
from pathlib import Path

from .pipeline import open_store
from .quality import publish_blockers
from .store import SITE_ID, Store, now

ROOT = Path(__file__).resolve().parents[1]
SNAPSHOT = ROOT / "data" / "content-snapshot.json"
# Рецензентом может быть только человек: машинный исполнитель редакторскую
# проверку не проходит и за неё не выдаётся.
MACHINE_ACTORS = re.compile(r"^(claude|qwen|food-daily-|anthropic|bot|ai)", re.I)


def publish_preview(st: Store, content_id: str, *, actor: str) -> dict:
    row = st.current(content_id)
    payload = json.loads(st.version(content_id)["payload_json"])
    blockers = publish_blockers(payload)
    if blockers:
        st.audit(
            actor,
            "publish_blocked",
            content_id=content_id,
            version=row["current_version"],
            blockers=blockers,
        )
        return {"content_id": content_id, "published": False, "blockers": blockers}
    st.set_publish(content_id, "preview", actor=actor)
    return {"content_id": content_id, "published": True, "version": row["current_version"]}


def review(st: Store, content_id: str, status: str, *, reviewer: str, version: int, note: str = "") -> None:
    if MACHINE_ACTORS.match(reviewer):
        raise PermissionError(f"рецензент {reviewer!r} — машинный исполнитель; редакторская проверка — только человек")
    st.set_review(content_id, status, reviewer=reviewer, version=version, note=note)


def diff(st: Store, content_id: str, a: int, b: int) -> str:
    va, vb = (json.loads(st.version(content_id, v)["payload_json"]) for v in (a, b))
    ta = json.dumps(va["draft"], ensure_ascii=False, indent=1).splitlines()
    tb = json.dumps(vb["draft"], ensure_ascii=False, indent=1).splitlines()
    return "\n".join(difflib.unified_diff(ta, tb, f"v{a}", f"v{b}", lineterm=""))


def snapshot(st: Store) -> dict:
    items = []
    for row in st.db.execute(
        "SELECT * FROM content WHERE site_id=? AND publish_status IN ('preview','published') "
        "ORDER BY published_at DESC, content_id",
        (SITE_ID,),
    ):
        v = st.version(row["content_id"])
        p = json.loads(v["payload_json"])
        media = [
            dict(m)
            for m in st.db.execute(
                "SELECT media_id, kind, status, path, recipe_version FROM media WHERE content_id=? AND status='ready' "
                "AND recipe_version=?",
                (row["content_id"], row["current_version"]),
            )
        ]
        items.append(
            {
                "content_id": row["content_id"],
                "slug": row["slug"],
                "version": row["current_version"],
                "published_at": row["published_at"],
                "updated_at": v["created_at"],
                "review_status": row["review_status"],
                "cooking_status": row["cooking_status"],
                "producer_mode": json.loads(v["producer_json"]).get("mode"),
                "draft": {k: val for k, val in p["draft"].items() if k != "editor_notes"},
                "facts": p["facts"],
                "source": {k: p["source"][k] for k in ("url", "host", "fetched_at")},
                "media": media,
            }
        )
    snap = {"site_id": SITE_ID, "schema_version": 1, "generated_at": now(), "items": items}
    SNAPSHOT.write_text(json.dumps(snap, ensure_ascii=False, indent=1) + "\n")
    return {"items": len(items), "path": str(SNAPSHOT.relative_to(ROOT))}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="food-daily editorial")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("publish-preview")
    p.add_argument("content_ids", nargs="*")
    p.add_argument("--all", action="store_true")
    u = sub.add_parser("unpublish")
    u.add_argument("content_id")
    r = sub.add_parser("rollback")
    r.add_argument("content_id")
    r.add_argument("--to", type=int, required=True)
    rv = sub.add_parser("review")
    rv.add_argument("content_id")
    rv.add_argument("--status", choices=["editor_approved", "editor_rejected"], required=True)
    rv.add_argument("--reviewer", required=True)
    rv.add_argument("--version", type=int, required=True)
    rv.add_argument("--note", default="")
    d = sub.add_parser("diff")
    d.add_argument("content_id")
    d.add_argument("a", type=int)
    d.add_argument("b", type=int)
    sub.add_parser("snapshot")
    sub.add_parser("status")
    a = ap.parse_args(argv)
    st = open_store()
    actor = "food-daily-editorial-cli"
    if a.cmd == "publish-preview":
        ids = (
            a.content_ids or [r[0] for r in st.db.execute("SELECT content_id FROM content ORDER BY created_at")]
            if a.all
            else a.content_ids
        )
        print(json.dumps([publish_preview(st, c, actor=actor) for c in ids], ensure_ascii=False, indent=1))
    elif a.cmd == "unpublish":
        st.set_publish(a.content_id, "hidden", actor=actor)
    elif a.cmd == "rollback":
        print(json.dumps({"new_version": st.rollback(a.content_id, a.to, actor=actor)}))
    elif a.cmd == "review":
        review(st, a.content_id, a.status, reviewer=a.reviewer, version=a.version, note=a.note)
    elif a.cmd == "diff":
        print(diff(st, a.content_id, a.a, a.b))
    elif a.cmd == "snapshot":
        print(json.dumps(snapshot(st)))
    else:
        print(
            json.dumps(
                {
                    "content": st.db.execute("SELECT count(*) FROM content").fetchone()[0],
                    "publish": dict(
                        st.db.execute("SELECT publish_status, count(*) FROM content GROUP BY 1").fetchall()
                    ),
                    "review": dict(st.db.execute("SELECT review_status, count(*) FROM content GROUP BY 1").fetchall()),
                    "cooking": dict(
                        st.db.execute("SELECT cooking_status, count(*) FROM content GROUP BY 1").fetchall()
                    ),
                },
                ensure_ascii=False,
            )
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
