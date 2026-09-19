#!/usr/bin/env python3
"""Собрать SEO-снимок Lords с живого localhost после готовности /healthz.

Не открывает индексацию. Читает template-manifest + catalog/details и
HTTP-ответы обязательных маршрутов. Fail-closed: неполный снимок → exit 2.
"""

from __future__ import annotations

import argparse
import html as html_lib
import json
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from factory.lords import seo_snapshot as ss  # noqa: E402

_TITLE = re.compile(r"<title>(.*?)</title>", re.I | re.S)
_DESC = re.compile(
    r'<meta[^>]+name=["\']description["\'][^>]+content=["\'](.*?)["\']',
    re.I,
)
_DESC2 = re.compile(
    r'<meta[^>]+content=["\'](.*?)["\'][^>]+name=["\']description["\']',
    re.I,
)
_CANON = re.compile(
    r'<link[^>]+rel=["\']canonical["\'][^>]+href=["\'](.*?)["\']',
    re.I,
)
_H1 = re.compile(r"<h1[^>]*>(.*?)</h1>", re.I | re.S)
_ROBOTS = re.compile(
    r'<meta[^>]+name=["\']robots["\'][^>]+content=["\'](.*?)["\']',
    re.I,
)
_HREF_COLLECTION = re.compile(r'href="(/collection/[a-z0-9_]+/)"')


def _clean(m: re.Match | None) -> str:
    if not m:
        return ""
    text = re.sub(r"<[^>]+>", "", m.group(1))
    return html_lib.unescape(re.sub(r"\s+", " ", text).strip())


def _fetch(base: str, host: str, path: str) -> tuple[int, str, dict]:
    req = urllib.request.Request(
        base.rstrip("/") + path,
        headers={"Host": host, "User-Agent": "lords-seo-snapshot/1.0"},
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        body = resp.read().decode("utf-8", "replace")
        return int(resp.status), body, dict(resp.headers)


def _observe(path: str, page_type: str, status: int, body: str, headers: dict) -> dict:
    if status != 200:
        raise ss.SeoSnapshotError(f"{path}: HTTP {status}")
    title = _clean(_TITLE.search(body))
    desc_m = _DESC.search(body) or _DESC2.search(body)
    description = _clean(desc_m) if desc_m else ""
    canonical = _clean(_CANON.search(body))
    h1 = _clean(_H1.search(body))
    robots = _clean(_ROBOTS.search(body))
    xrobots = (headers.get("X-Robots-Tag") or headers.get("x-robots-tag") or "").strip()
    if "noindex" not in robots.lower():
        raise ss.SeoSnapshotError(f"{path}: meta robots без noindex ({robots!r})")
    if "noindex" not in xrobots.lower():
        raise ss.SeoSnapshotError(f"{path}: X-Robots-Tag без noindex ({xrobots!r})")
    return {
        "path": path,
        "page_type": page_type,
        "title": title,
        "description": description,
        "h1": h1,
        "canonical": canonical,
        "indexable": False,
    }


def _pick_routes(catalog: Path, base: str, host: str) -> list[tuple[str, str]]:
    routes = [(p, t) for p, t in ss.STATIC_PATH_TYPES.items()]
    items = json.loads(catalog.read_text(encoding="utf-8")).get("items") or []
    series = next((it for it in items if it.get("kind") == "Сериал" and it.get("slug")), None)
    if not series:
        raise ss.SeoSnapshotError("в каталоге нет сериала для title/season/episode")
    slug = series["slug"]
    routes.append((f"/title/{slug}/", "title"))
    routes.append((f"/title/{slug}/season-1/", "season"))
    routes.append((f"/title/{slug}/season-1/episode-1/", "episode"))

    st, body, _ = _fetch(base, host, "/collections/")
    if st != 200:
        raise ss.SeoSnapshotError(f"/collections/: HTTP {st}")
    m = _HREF_COLLECTION.search(body)
    if not m:
        raise ss.SeoSnapshotError("нет ссылки /collection/<key>/ на хабе подборок")
    routes.append((m.group(1), "collection"))
    return routes


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--site", required=True)
    ap.add_argument("--domain", required=True)
    ap.add_argument("--port", type=int, required=True)
    ap.add_argument("--front", default="/srv/lords/.frontend")
    ap.add_argument("--out", default="")
    args = ap.parse_args()

    front = Path(args.front)
    manifest_path = front / f"template-manifest-{args.site}.json"
    catalog = front / f"{args.site}-catalog.json"
    details = front / f"{args.site}-details.json"
    if not manifest_path.is_file():
        print(f"[seo-snapshot] нет {manifest_path}", file=sys.stderr)
        return 2
    if not catalog.is_file():
        print(f"[seo-snapshot] нет {catalog}", file=sys.stderr)
        return 2

    provenance = json.loads(manifest_path.read_text(encoding="utf-8"))
    base = f"http://127.0.0.1:{args.port}"
    # readiness already gated by deploy; cheap re-check
    try:
        st, body, _ = _fetch(base, args.domain, "/healthz")
        if st != 200 or '"ok"' not in body:
            print(f"[seo-snapshot] /healthz не готов: {st} {body[:80]}", file=sys.stderr)
            return 2
    except (urllib.error.URLError, TimeoutError) as exc:
        print(f"[seo-snapshot] /healthz недоступен: {exc}", file=sys.stderr)
        return 2

    pages = []
    try:
        for path, page_type in _pick_routes(catalog, base, args.domain):
            st, body, hdr = _fetch(base, args.domain, path)
            pages.append(_observe(path, page_type, st, body, hdr))
        doc = ss.собрать(
            provenance=provenance,
            catalog=catalog,
            details=details if details.is_file() else None,
            pages=pages,
            domain=args.domain,
            site_id=args.site,
        )
    except ss.SeoSnapshotError as exc:
        print(f"[seo-snapshot] ОТКАЗ: {exc}", file=sys.stderr)
        return 2

    out = Path(args.out) if args.out else front / f"seo-snapshot-{args.site}.json"
    ss.записать(out, doc)
    print(
        f"[seo-snapshot] {args.site}: pages={len(doc['pages'])} "
        f"build={doc['build_id']} content_snapshot_id={doc['content_snapshot_id'][:16]}… "
        f"→ {out}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
