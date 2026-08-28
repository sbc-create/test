from __future__ import annotations

import argparse
import html
import json
import os
import re
import shutil
import tarfile
import tempfile
from pathlib import Path

from factory.lords import player

_SAFE_SLUG = re.compile(r"^[A-Za-z0-9._-]+$")


def _page(title: str, body: str) -> str:
    return f"""<!doctype html>
<html lang=\"ru\"><head><meta charset=\"utf-8\">
<meta name=\"robots\" content=\"noindex, nofollow\">
<meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">
<title>{html.escape(title)}</title>
<style>body{{font:16px system-ui;background:#101218;color:#eee;margin:0}}main{{max-width:1100px;margin:auto;padding:24px}}a{{color:#9bc3ff}}.grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(180px,1fr));gap:18px}}article{{background:#1b1f2a;padding:14px;border-radius:12px}}img{{width:100%;aspect-ratio:2/3;object-fit:cover;border-radius:8px}}video-player{{display:block;min-height:360px}}</style>
</head><body><main>{body}</main></body></html>"""


def _valid_items(items: list[dict]) -> list[dict]:
    result = []
    for item in items:
        slug = str(item.get("external_id") or "")
        playback = item.get("playback") or {}
        if not _SAFE_SLUG.fullmatch(slug):
            continue
        if not playback.get("aggregator") or not playback.get("title_id"):
            continue
        result.append(item)
    return result


def _write_site(site: Path, items: list[dict], publisher_id: str) -> dict:
    playable = _valid_items(items)
    if not playable:
        raise RuntimeError("живой каталог не содержит воспроизводимых записей")
    cards = []
    sample_series = ""
    sample_movie = ""
    for item in playable:
        slug = str(item["external_id"])
        name = str(item.get("name") or slug)
        poster = html.escape(str(item.get("poster_url") or ""), quote=True)
        kind = "Сериал" if item.get("is_series") else "Фильм"
        cards.append(f'<article><a href="/title/{slug}/"><img src="{poster}" alt=""><h2>{html.escape(name)}</h2></a><p>{kind}</p></article>')
        playback = item["playback"]
        live_player = player.render_live(
            publisher_id=publisher_id,
            aggregator=str(playback["aggregator"]),
            title_id=str(playback["title_id"]),
            title_name=name,
            ident=f"player-{slug}",
        )
        series = "<h2>Сезоны и серии</h2><p>Выберите сезон и серию в плеере.</p>" if item.get("is_series") else ""
        tags = ", ".join(html.escape(str(tag)) for tag in item.get("tags") or [])
        body = f'<p><a href="/">Каталог</a></p><h1>{html.escape(name)}</h1><p>{kind} · {html.escape(str(item.get("year") or ""))}</p><p>{tags}</p>{series}{live_player}'
        target = site / "title" / slug
        target.mkdir(parents=True, exist_ok=True)
        (target / "index.html").write_text(_page(name, body), encoding="utf-8")
        path = f"/title/{slug}/"
        if item.get("is_series") and not sample_series:
            sample_series = path
        if not item.get("is_series") and not sample_movie:
            sample_movie = path
    if not sample_series or not sample_movie:
        raise RuntimeError("для приёмки нужны воспроизводимые сериал и фильм")
    site.mkdir(parents=True, exist_ok=True)
    (site / "index.html").write_text(_page("Каталог", '<h1>Каталог</h1><div class="grid">' + "".join(cards) + "</div>"), encoding="utf-8")
    (site / "robots.txt").write_text("User-agent: *\nDisallow: /\n", encoding="utf-8")
    (site / "sitemap.xml").write_text('<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"></urlset>\n', encoding="utf-8")
    (site / "404.html").write_text(_page("404", "<h1>404</h1>"), encoding="utf-8")
    return {"sample_series_path": sample_series, "sample_movie_path": sample_movie, "rendered_titles": len(playable)}


def rewrite_bundle(*, archive_path: Path, items: list[dict], publisher_id: str) -> dict:
    if not archive_path.is_file():
        raise RuntimeError(f"архив основы не найден: {archive_path}")
    with tempfile.TemporaryDirectory(prefix="lords-live-") as raw:
        root = Path(raw)
        with tarfile.open(archive_path, "r") as source:
            source.extractall(root)
        site = root / "site"
        if site.exists():
            shutil.rmtree(site)
        meta = _write_site(site, items, publisher_id)
        manifest_path = root / "bundle-manifest.json"
        if manifest_path.is_file():
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest.update({"data_source": "cdnvideohub-live", "deployable": True, "player": "live", **meta})
            manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        temp_archive = archive_path.with_suffix(".tar.tmp")
        with tarfile.open(temp_archive, "w") as target:
            for path in sorted(root.rglob("*")):
                target.add(path, arcname=str(path.relative_to(root)), recursive=False)
        os.replace(temp_archive, archive_path)
    return meta


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--archive", type=Path, required=True)
    parser.add_argument("--cache", type=Path, required=True)
    parser.add_argument("--credentials-dir", type=Path, required=True)
    args = parser.parse_args()
    payload = json.loads(args.cache.read_text(encoding="utf-8"))
    publisher_id = (args.credentials_dir / "cdnvideohub-publisher-id").read_text(encoding="utf-8").strip()
    if not player.is_valid_publisher_id(publisher_id):
        raise RuntimeError("Publisher ID в credentials некорректен")
    result = rewrite_bundle(archive_path=args.archive, items=list(payload.get("items") or []), publisher_id=publisher_id)
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
