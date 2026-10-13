"""Комплект переноса сайта food-baking: код из коммита, разрешённый экспорт контента, закрытая часть, команды.

Состав (каталог <out>/food-baking-<sha7>/):
  code.tar.gz     — templates/food-baking (без data/ и docs/screenshots/), inventory/ и .gitignore из коммита;
  content.tar.gz  — templates/food-baking/data/: публичный контент из git (закрытые снимки источников не входят);
  private/        — только своя редакционная база var/food-baking/preview/*.sqlite3, если есть (SQLite backup,
                    права 0600)
                    и опись версий versions.json для проверки восстановления;
  SHA256SUMS, MANIFEST.json, INSTALL.md — контроль целостности, описание и точные команды.

python3 -m bakebook.kit build --out <каталог>
python3 -m bakebook.kit verify-db --db <база> --versions <опись>   # после восстановления базы
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import sqlite3
import subprocess
import tarfile
import time
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parents[1]
SITE = "food-baking"
PKG = "bakebook"
QA_MODULE = "bakebook.qa"
DB = REPO / "var" / SITE / "preview" / f"{SITE}.sqlite3"


def _git(*args: str) -> str:
    return subprocess.run(["git", *args], cwd=REPO, capture_output=True, text=True, check=True).stdout.strip()


def _sha256(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def db_versions(db: Path) -> dict:
    con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    try:
        cur = dict(con.execute("SELECT content_id, current_version FROM content ORDER BY content_id"))
        vers = {
            cid: [
                list(r)
                for r in con.execute(
                    "SELECT recipe_version, payload_hash FROM versions WHERE content_id=? ORDER BY recipe_version",
                    (cid,),
                )
            ]
            for cid in cur
        }
        audit = con.execute("SELECT count(*) FROM audit").fetchone()[0]
    finally:
        con.close()
    return {"current": cur, "versions": vers, "audit_rows": audit}


def verify_db(db: Path, versions: Path) -> dict:
    want, got = json.loads(versions.read_text()), db_versions(db)
    diff = [cid for cid in want["versions"] if want["versions"][cid] != got["versions"].get(cid)]
    ok = not diff and want["current"] == got["current"] and got["audit_rows"] >= want["audit_rows"]
    return {
        "ok": ok,
        "content": len(got["current"]),
        "versions": sum(len(v) for v in got["versions"].values()),
        "mismatch": diff,
    }


def _install(sha: str, branch: str, port: int, has_db: bool) -> str:
    restore_db = (
        f"""
## 4. Восстановление редакционной базы (версии сохраняются)

```bash
cd /srv/{SITE}/templates/{SITE}
# отказ, если база уже есть или не совпадает со снимком
python3 -m {PKG}.editorial clone-db --from <комплект>/private/{SITE}.sqlite3
python3 -m {PKG}.kit verify-db --db ../../var/{SITE}/preview/{SITE}.sqlite3 --versions <комплект>/private/versions.json
python3 -m {PKG}.editorial status
```

Миграций нет: схема хранилища — версия 1, таблицы создаёт само хранилище (`CREATE TABLE IF NOT EXISTS`).
Учётка редактора в комплект не входит: `python3 -m {PKG}.editor_secret` на новом месте (секрет — вне репозитория).
"""
        if has_db
        else """
## 4. Данные

Своей базы у сайта нет: весь контент — файлы `data/` из `content.tar.gz` (шаг 1). Миграций нет.
"""
    )
    return f"""# Комплект переноса: {SITE}

Коммит `{sha}` ветки `{branch}`. Собран {time.strftime("%Y-%m-%d %H:%M UTC", time.gmtime())}.
Превью закрыто от индексации; домен не выбран (`origin.production: null`) — production этим комплектом не запускается.

## 1. Проверка и распаковка

```bash
cd <комплект> && sha256sum -c SHA256SUMS
mkdir -p /srv/{SITE} && cd /srv/{SITE}
tar -xzf <комплект>/code.tar.gz && tar -xzf <комплект>/content.tar.gz
```

## 2. Зависимости

```bash
python3 --version                                    # проверено на 3.10
# версии, на которых проверено
python3 -m pip install --user 'Jinja2==3.0.3' 'PyYAML==5.4.1' pytest
# только для браузерной приёмки (axe-core 4.13.0)
(cd templates/{SITE}/qa && npm ci --no-audit --no-fund)
```

## 3. Запуск

```bash
cd /srv/{SITE}/templates/{SITE}
python3 -m {PKG}.server                 # порт из config/site.yaml: {port}; рядом с другим превью — добавьте --port N
```
{restore_db}
## 5. Проверка после переноса

```bash
cd /srv/{SITE}/templates/{SITE}
bash bin/{SITE} test
python3 -c "import urllib.request;print(urllib.request.urlopen('http://127.0.0.1:{port}/healthz').read().decode())"
# браузерная приёмка
QA_BASE=http://127.0.0.1:{port} python3 -m {QA_MODULE} --shots /tmp/{SITE}-shots --out /tmp/{SITE}-qa.json
```

Не входит в комплект: закрытые снимки источников `var/{SITE}/private` (не публикуются и не переносятся; без них
полная сверка текста черновиков с источником не выполняется), секреты, `node_modules`, скриншоты-доказательства
(они в git, `docs/screenshots/`).
"""


def build(out: Path) -> dict:
    if _git("status", "--porcelain", "--", f"templates/{SITE}", "inventory"):
        raise SystemExit("в шаблоне есть незакоммиченные изменения — комплект собирается только из коммита")
    sha, branch = _git("rev-parse", "HEAD"), _git("rev-parse", "--abbrev-ref", "HEAD")
    kit = out / f"{SITE}-{sha[:7]}"
    kit.mkdir(parents=True, exist_ok=False)
    raw = subprocess.run(
        ["git", "archive", "--format=tar", sha, f"templates/{SITE}", "inventory", ".gitignore"],
        cwd=REPO,
        capture_output=True,
        check=True,
    ).stdout
    src = tarfile.open(fileobj=io.BytesIO(raw))
    counts = {"code": 0, "content": 0}
    with tarfile.open(kit / "code.tar.gz", "w:gz") as code, tarfile.open(kit / "content.tar.gz", "w:gz") as content:
        for m in src.getmembers():
            if m.name.startswith(f"templates/{SITE}/docs/screenshots"):
                continue
            target = "content" if m.name.startswith(f"templates/{SITE}/data") else "code"
            (content if target == "content" else code).addfile(m, src.extractfile(m) if m.isfile() else None)
            counts[target] += m.isfile()
    private = None
    if DB.exists():
        pdir = kit / "private"
        pdir.mkdir(mode=0o700)
        dst = pdir / DB.name
        with sqlite3.connect(f"file:{DB}?mode=ro", uri=True) as a, sqlite3.connect(dst) as b:
            a.backup(b)
            b.execute("PRAGMA journal_mode=DELETE")  # один файл базы: без -wal/-shm, контрольная сумма стабильна
        os.chmod(dst, 0o600)
        (pdir / "versions.json").write_text(json.dumps(db_versions(dst), indent=1) + "\n")
        private = verify_db(dst, pdir / "versions.json") | {"db": f"private/{DB.name}"}
    port = yaml.safe_load((ROOT / "config" / "site.yaml").read_text())["server"]["port"]
    (kit / "INSTALL.md").write_text(_install(sha, branch, port, private is not None))
    files = sorted(p for p in kit.rglob("*") if p.is_file() and p.name != "SHA256SUMS")
    (kit / "SHA256SUMS").write_text("".join(f"{_sha256(p)}  {p.relative_to(kit)}\n" for p in files))
    manifest = {
        "site": SITE,
        "commit": sha,
        "branch": branch,
        "built_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "files_in_code": counts["code"],
        "files_in_content": counts["content"],
        "private": private,
        "excluded": ["docs/screenshots (в git)", f"var/{SITE}/private (закрытые снимки)", "секреты", "node_modules"],
    }
    (kit / "MANIFEST.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=1) + "\n")
    return {"kit": str(kit), **manifest}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog=f"{SITE} kit")
    sub = ap.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("build")
    b.add_argument("--out", required=True)
    v = sub.add_parser("verify-db")
    v.add_argument("--db", required=True)
    v.add_argument("--versions", required=True)
    a = ap.parse_args(argv)
    if a.cmd == "build":
        print(json.dumps(build(Path(a.out)), ensure_ascii=False))
        return 0
    res = verify_db(Path(a.db), Path(a.versions))
    print(json.dumps(res, ensure_ascii=False))
    return 0 if res["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
