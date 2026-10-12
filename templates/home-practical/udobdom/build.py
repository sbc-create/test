"""Сборка статического артефакта home-practical из commit (git archive только templates/home-practical)."""

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
from udobdom.server import App
out = Path(sys.argv[1]); app = App()
for path in app.sitemap_urls():
    st, html, _ = app.route(path, {}); assert st == 200, (path, st)
    p = out / path.lstrip('/') / 'index.html'; p.parent.mkdir(parents=True, exist_ok=True); p.write_text(html)
(out / '404.html').write_text(app.not_found()[1]); (out / 'sitemap.xml').write_text(app.sitemap())
shutil.copytree('static', out / 'static', dirs_exist_ok=True)
"""


def build(commit: str) -> dict:
    sha = subprocess.run(
        ["git", "rev-parse", commit], cwd=REPO, capture_output=True, text=True, check=True
    ).stdout.strip()
    out = REPO / "var" / "home-practical" / "build" / sha
    (REPO / "var" / "home-practical").mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=REPO / "var" / "home-practical") as tmp:
        tar = subprocess.run(
            ["git", "archive", sha, "templates/home-practical"], cwd=REPO, capture_output=True, check=True
        ).stdout
        with tarfile.open(fileobj=io.BytesIO(tar)) as t:
            t.extractall(tmp)
        out.mkdir(parents=True, exist_ok=True)
        subprocess.run(
            [sys.executable, "-c", RENDER, str(out)], cwd=Path(tmp) / "templates" / "home-practical", check=True
        )
    files = {
        str(p.relative_to(out)): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in sorted(out.rglob("*"))
        if p.is_file() and p.name != "manifest.json"
    }
    tree = hashlib.sha256(json.dumps(files, sort_keys=True).encode()).hexdigest()
    (out / "manifest.json").write_text(
        json.dumps(
            {"site_id": "home-practical", "commit": sha, "files": len(files), "tree_sha256": tree, "hashes": files},
            indent=1,
        )
        + "\n"
    )
    return {
        "site_id": "home-practical",
        "commit": sha,
        "files": len(files),
        "tree_sha256": tree,
        "path": str(out.relative_to(REPO)),
    }


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--commit", default="HEAD")
    print(json.dumps(build(ap.parse_args().commit)))
