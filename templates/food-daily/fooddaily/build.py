"""Детерминированная сборка статического артефакта food-daily из commit.

Собирается только из файлов этой ветки (templates/food-daily) по
закоммиченному снимку контента: `git archive <commit> templates/food-daily`
во временный каталог → рендер всех индексируемых URL, 404, robots, sitemap
и статики в var/food-daily/build/<commit>/ + manifest с хешами.
Неотслеживаемые и чужие файлы в сборку попасть не могут.
"""

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


def build(commit: str) -> dict:
    sha = subprocess.run(
        ["git", "rev-parse", commit], cwd=REPO, capture_output=True, text=True, check=True
    ).stdout.strip()
    out = REPO / "var" / "food-daily" / "build" / sha
    with tempfile.TemporaryDirectory(dir=REPO / "var" / "food-daily") as tmp:
        tar = subprocess.run(
            ["git", "archive", sha, "templates/food-daily"],
            cwd=REPO,
            capture_output=True,
            check=True,
        ).stdout
        with tarfile.open(fileobj=io.BytesIO(tar)) as t:
            t.extractall(tmp)
        src = Path(tmp) / "templates" / "food-daily"
        code = (
            "import json,sys,shutil; from pathlib import Path\n"
            "from fooddaily.server import App\n"
            "out=Path(sys.argv[1]); app=App(); files={}\n"
            "def put(rel, body):\n"
            "    p=out/rel; p.parent.mkdir(parents=True, exist_ok=True); b=body.encode() if isinstance(body,str) else body; p.write_bytes(b)\n"
            "for path,_ in app.sitemap_urls():\n"
            "    st,html,_=app.route(path,{}); assert st==200,(path,st); put(path.lstrip('/')+'index.html', html)\n"
            "for path in ['/poisk/','/izbrannoe/','/spisok-pokupok/']:\n"
            "    st,html,_=app.route(path,{}); put(path.lstrip('/')+'index.html', html)\n"
            "put('404.html', app.not_found()[1]); put('robots.txt', app.robots()); put('sitemap.xml', app.sitemap())\n"
            "shutil.copytree('static', out/'static', dirs_exist_ok=True)\n"
        )
        out.mkdir(parents=True, exist_ok=True)
        subprocess.run([sys.executable, "-c", code, str(out)], cwd=src, check=True)
    files = {}
    for p in sorted(out.rglob("*")):
        if p.is_file() and p.name != "manifest.json":
            files[str(p.relative_to(out))] = hashlib.sha256(p.read_bytes()).hexdigest()
    manifest = {
        "site_id": "food-daily",
        "commit": sha,
        "files": len(files),
        "tree_sha256": hashlib.sha256(json.dumps(files, sort_keys=True).encode()).hexdigest(),
        "hashes": files,
    }
    (out / "manifest.json").write_text(json.dumps(manifest, indent=1) + "\n")
    return {k: manifest[k] for k in ("site_id", "commit", "files", "tree_sha256")} | {
        "path": str(out.relative_to(REPO))
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="food-daily build")
    ap.add_argument("--commit", default="HEAD")
    a = ap.parse_args(argv)
    print(json.dumps(build(a.commit), ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
