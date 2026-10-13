"""Комплект переноса: инструкция с точными командами сайта, проверка восстановленной базы по описи версий."""

import json
import sqlite3
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from bakebook import kit  # noqa: E402


def test_install_has_site_commands():
    port = yaml.safe_load((ROOT / "config" / "site.yaml").read_text())["server"]["port"]
    text = kit._install("0" * 40, "claude/x", port, has_db=False)
    assert "python3 -m bakebook.server" in text and str(port) in text and "sha256sum -c SHA256SUMS" in text
    assert "bash bin/food-baking test" in text and "production" in text


def test_verify_db_detects_version_mismatch(tmp_path):
    db = tmp_path / "x.sqlite3"
    con = sqlite3.connect(db)
    con.executescript(
        "CREATE TABLE content (content_id TEXT, current_version INT);"
        "CREATE TABLE versions (content_id TEXT, recipe_version INT, payload_hash TEXT);"
        "CREATE TABLE audit (id INTEGER PRIMARY KEY);"
        "INSERT INTO content VALUES ('a', 2); INSERT INTO versions VALUES ('a', 1, 'h1'), ('a', 2, 'h2');"
    )
    con.commit()
    con.close()
    ok = tmp_path / "v.json"
    ok.write_text(json.dumps(kit.db_versions(db)))
    assert kit.verify_db(db, ok)["ok"]
    bad = json.loads(ok.read_text())
    bad["versions"]["a"][1][1] = "other"
    (tmp_path / "bad.json").write_text(json.dumps(bad))
    assert not kit.verify_db(db, tmp_path / "bad.json")["ok"]
