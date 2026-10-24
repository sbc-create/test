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
import sqlite3
from pathlib import Path

from .pipeline import DB_PATH, open_store
from .quality import publish_blockers
from .store import SITE_ID, Store, VersionConflict, now

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


NUM = re.compile(r"\d+(?:[.,]\d+)?")
REVISABLE = {"title", "seo_title", "seo_description", "intro", "steps", "tips", "substitutions", "editor_notes"}


def _num(n: str) -> str:
    return str(float(n.replace(",", "."))).rstrip("0").rstrip(".")


TEXT_KEYS = {"title", "seo_title", "seo_description", "intro", "text", "readiness_cue", "note", "to"}


def _strings(value, key: str | None = None) -> list[str]:
    """Только читаемый текст черновика: служебные поля (индексы, ссылки на шаги) числами текста не считаются."""
    if isinstance(value, dict):
        return [s for k, v in value.items() for s in _strings(v, k)]
    if isinstance(value, list):
        return [s for v in value for s in _strings(v, key)]
    return [value] if isinstance(value, str) and key in TEXT_KEYS else []


def clone_db(src: Path, dst: Path = DB_PATH) -> dict:
    """Изолированная редакционная база варианта: консистентная копия (SQLite backup) базы, из которой собран
    снимок этого варианта. Отказ, если база уже есть или её текущие версии не совпадают со снимком."""
    if dst.exists():
        raise FileExistsError(f"{dst} уже есть — клонирование не перезаписывает базу")
    if not src.exists():
        raise FileNotFoundError(src)
    dst.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(f"file:{src}?mode=ro", uri=True) as a, sqlite3.connect(dst) as b:
        a.backup(b)
    st = Store(dst)
    snap = json.loads(SNAPSHOT.read_text())
    bad = []
    for it in snap["items"]:
        row = st.current(it["content_id"])
        if row is None or row["current_version"] != it["version"]:
            bad.append(it["slug"])
            continue
        draft = {
            k: v
            for k, v in json.loads(st.version(it["content_id"])["payload_json"])["draft"].items()
            if k != "editor_notes"
        }
        if draft != it["draft"] or row["publish_status"] not in ("preview", "published"):
            bad.append(it["slug"])
    if bad:
        raise ValueError(f"база не совпадает со снимком варианта: {bad}")
    st.audit("food-daily-editorial-cli", "db_cloned", source=str(src), items=len(snap["items"]))
    return {"db": str(dst), "items_checked": len(snap["items"])}


def revise(st: Store, content_id: str, changes: dict, *, base_version: int, actor: str, reason: str) -> dict:
    """Редакционная правка: новая версия с заменёнными полями черновика (через add_version — конфликт базы,
    история, аудит). Числа в новом тексте должны быть в полной записи источника; ворота публикации те же."""
    unknown = set(changes) - REVISABLE
    if unknown:
        raise ValueError(f"эти поля правкой не меняются: {sorted(unknown)}")
    cur = json.loads(st.version(content_id)["payload_json"])
    v = st.version(content_id)
    sources = json.loads(v["source_ids_json"])
    facts = " ".join(
        r[0]
        for r in st.db.execute(
            f"SELECT facts_json FROM records WHERE record_id IN ({','.join('?' * len(sources))})", sources
        )
    )
    allowed = {_num(n) for n in NUM.findall(facts)}
    new_text = " ".join(_strings({k: changes[k] for k in changes if k != "editor_notes"}))
    bad = sorted({n for n in NUM.findall(new_text) if _num(n) not in allowed})
    if bad:
        raise ValueError(f"числа без опоры в записи источника: {bad}")
    payload = {**cur, "draft": {**cur["draft"], **changes}}
    blockers = publish_blockers(payload)
    if blockers:
        raise ValueError(f"правка не проходит ворота публикации: {blockers}")
    new = st.add_version(
        content_id,
        payload,
        base_version=base_version,
        source_ids=sources,
        producer={"mode": "editorial_revision", "by": actor, "note": "правка в сессии фабрики; не проверка человеком"},
        actor=actor,
        reason=reason,
    )
    return {"content_id": content_id, "version": new, "base": base_version}


REDIRECTS = ROOT / "data" / "redirects.json"
SLUG = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*")


def rename(st: Store, content_id: str, new_slug: str, *, base_version: int, actor: str, reason: str) -> dict:
    """Новый адрес рецепта: версия черновика с новым slug, переименование в базе и постоянный (301) редирект
    со старого адреса; цепочки редиректов схлопываются, чтобы старые ссылки вели сразу на новый адрес."""
    if not SLUG.fullmatch(new_slug) or len(new_slug) > 80:
        raise ValueError(f"недопустимый адрес {new_slug!r}")
    cur = json.loads(st.version(content_id)["payload_json"])
    old = st.current(content_id)["slug"]
    if old == new_slug:
        raise ValueError("адрес не меняется")
    if st.db.execute("SELECT 1 FROM content WHERE slug=?", (new_slug,)).fetchone():
        raise ValueError(f"адрес {new_slug!r} уже занят")
    payload = {**cur, "draft": {**cur["draft"], "slug": new_slug}}
    v = st.version(content_id)
    new = st.add_version(
        content_id,
        payload,
        base_version=base_version,
        source_ids=json.loads(v["source_ids_json"]),
        producer={"mode": "editorial_revision", "by": actor, "note": "смена адреса; не проверка человеком"},
        actor=actor,
        reason=reason,
    )
    st.rename_slug(content_id, new_slug, actor=actor)
    red = json.loads(REDIRECTS.read_text()) if REDIRECTS.exists() else {}
    old_path, new_path = f"/recept/{old}/", f"/recept/{new_slug}/"
    red = {k: (new_path if v == old_path else v) for k, v in red.items()}
    red[old_path] = new_path
    REDIRECTS.write_text(json.dumps(dict(sorted(red.items())), ensure_ascii=False, indent=1) + "\n")
    return {"content_id": content_id, "version": new, "old": old_path, "new": new_path}


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
    c = sub.add_parser("clone-db", help="изолированная база варианта из базы, по которой собран его снимок")
    c.add_argument("--from", dest="src", required=True)
    rv2 = sub.add_parser("revise", help="правка черновика новой версией")
    rv2.add_argument("content_id")
    rv2.add_argument("--base", type=int, required=True)
    rv2.add_argument("--draft-file", required=True, help="JSON: поля черновика, которые заменяются целиком")
    rv2.add_argument("--reason", required=True)
    rv2.add_argument("--actor", default="food-daily-editorial-cli")
    rn = sub.add_parser("rename", help="новый адрес рецепта с постоянным редиректом со старого")
    rn.add_argument("content_id")
    rn.add_argument("--base", type=int, required=True)
    rn.add_argument("--to", dest="new_slug", required=True)
    rn.add_argument("--reason", required=True)
    rn.add_argument("--actor", default="food-daily-editorial-cli")
    a = ap.parse_args(argv)
    if a.cmd == "clone-db":
        try:
            print(json.dumps(clone_db(Path(a.src)), ensure_ascii=False))
        except (FileExistsError, FileNotFoundError, ValueError) as e:
            print(json.dumps({"error": str(e)}, ensure_ascii=False))
            return 2
        return 0
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
    elif a.cmd == "revise":
        try:
            out = revise(
                st,
                a.content_id,
                json.loads(Path(a.draft_file).read_text()),
                base_version=a.base,
                actor=a.actor,
                reason=a.reason,
            )
        except (ValueError, VersionConflict) as e:
            print(json.dumps({"error": str(e)}, ensure_ascii=False))
            return 2
        print(json.dumps(out, ensure_ascii=False))
    elif a.cmd == "rename":
        try:
            out = rename(st, a.content_id, a.new_slug, base_version=a.base, actor=a.actor, reason=a.reason)
        except (ValueError, VersionConflict) as e:
            print(json.dumps({"error": str(e)}, ensure_ascii=False))
            return 2
        print(json.dumps(out, ensure_ascii=False))
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
