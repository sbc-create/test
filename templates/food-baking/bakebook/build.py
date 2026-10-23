"""Сборка статического артефакта food-baking из commit (`git archive` только
templates/food-baking) → var/food-baking/build/<sha>/ + manifest с хешами."""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parents[1]
RENDER = """
import sys, shutil
from pathlib import Path
from bakebook.server import App
out = Path(sys.argv[1]); app = App()
def put(rel, body):
    p = out / rel; p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(body.encode() if isinstance(body, str) else body)
for path, _ in app.sitemap_urls():
    st, html, _ = app.route(path, {}); assert st == 200, (path, st); put(path.lstrip('/') + 'index.html', html)
put('404.html', app.not_found()[1]); put('sitemap.xml', app.sitemap()); put('robots.txt', app.route('/robots.txt', {})[1])
shutil.copytree('static', out / 'static', dirs_exist_ok=True)
"""


def build(commit: str) -> dict:
    sha = subprocess.run(
        ["git", "rev-parse", commit], cwd=REPO, capture_output=True, text=True, check=True
    ).stdout.strip()
    out = REPO / "var" / "food-baking" / "build" / sha
    (REPO / "var" / "food-baking").mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=REPO / "var" / "food-baking") as tmp:
        tar = subprocess.run(
            ["git", "archive", sha, "templates/food-baking"], cwd=REPO, capture_output=True, check=True
        ).stdout
        with tarfile.open(fileobj=io.BytesIO(tar)) as t:
            t.extractall(tmp)
        out.mkdir(parents=True, exist_ok=True)
        subprocess.run(
            [sys.executable, "-c", RENDER, str(out)], cwd=Path(tmp) / "templates" / "food-baking", check=True
        )
    files = {
        str(p.relative_to(out)): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in sorted(out.rglob("*"))
        if p.is_file() and p.name != "manifest.json"
    }
    tree = hashlib.sha256(json.dumps(files, sort_keys=True).encode()).hexdigest()
    (out / "manifest.json").write_text(
        json.dumps(
            {"site_id": "food-baking", "commit": sha, "files": len(files), "tree_sha256": tree, "hashes": files},
            indent=1,
        )
        + "\n"
    )
    return {
        "site_id": "food-baking",
        "commit": sha,
        "files": len(files),
        "tree_sha256": tree,
        "path": str(out.relative_to(REPO)),
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="food-baking build")
    ap.add_argument("--commit", default="HEAD")
    print(json.dumps(build(ap.parse_args(argv).commit)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
