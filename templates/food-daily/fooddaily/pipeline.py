"""Возобновляемый импорт: URL → исходная запись → факты → дедупликация.

Закрытое хранилище исходных текстов: var/food-daily/private/ (0700, вне git,
вне публичной сборки), срок хранения — sources.retention_days. Публичная
сборка получает только наш текст из утверждённой версии и факты.
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import os
import re
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

from .classify import classify
from .extract import PARSER_VERSION, extract, is_complete
from .http import REPO, Client, FetchRefused
from .inventory import CRAWL_ROOT
from .robots import Robots
from .store import SITE_ID, Store, now
from .topics import TOPICS, _slug_tokens, term, topic_matches

VAR = REPO / "var" / "food-daily"
PRIVATE = VAR / "private"
DB_PATH = VAR / "preview" / "food-daily.sqlite3"
ROOT = Path(__file__).resolve().parents[1]

# Условия использования, проверенные в задании; непроверенное помечено.
SOURCES = {
    "eda-rambler": (
        "https://eda.rambler.ru",
        "https://help.rambler.ru/legal/1430/",
        "not_verified",
        "условия на help.rambler.ru — хост вне allowlist задания, не открывались; "
        "режим: только факты + собственный текст + ссылка на источник",
        30,
    ),
    "gastronom": (
        "https://www.gastronom.ru",
        "https://www.gastronom.ru/page/usage",
        "quote_with_link_only",
        "цитирование только со ссылкой в начале текста; полное копирование не разрешено → "
        "только факты + собственный текст + ссылка",
        30,
    ),
    "1000-menu": (
        "https://1000.menu",
        "https://1000.menu/general-rules",
        "not_found",
        "в правилах сайта нет условий перепечатки; режим: только факты",
        30,
    ),
}


def open_store() -> Store:
    s = Store(DB_PATH)
    for host, (base, terms, status, note, days) in SOURCES.items():
        s.db.execute(
            "INSERT OR REPLACE INTO sources VALUES (?,?,?,?,?,?)",
            (host, base, terms, status, note, days),
        )
    return s


def _dedupe_key(topic_id: str, facts: dict) -> str:
    names = sorted({re.sub(r"[^а-яёa-z]+", " ", i["name"].lower()).strip() for i in facts["ingredients"]})
    return topic_id + ":" + hashlib.sha256("|".join(names).encode()).hexdigest()[:16]


def plan(hosts: list[str], per_topic: int, topic_limit: int, out: Path) -> list[dict]:
    """По одному URL на тему из каждого хоста по порядку приоритета хостов."""
    import csv

    topic_csv = ROOT / "data" / "topic-map.csv"
    order = [r["topic_id"] for r in csv.DictReader(topic_csv.open()) if r["site_id"] == SITE_ID][:topic_limit]
    need = {t["topic_id"]: ([term(x) for x in t["need"]], [term(x) for x in t["exclude"]]) for t in TOPICS}
    picks: dict[str, list[dict]] = {tid: [] for tid in order}
    for h in hosts:
        for line in (CRAWL_ROOT / h / "urls.jsonl").open():
            d = json.loads(line)
            if classify(h, d["url"], d.get("sitemap"))[0] != "recipe":
                continue
            toks = _slug_tokens(d["url"])
            for tid in order:
                if len([p for p in picks[tid] if p["host"] == h]) >= per_topic:
                    continue
                req, ex = need[tid]
                if topic_matches(toks, req, ex):
                    picks[tid].append({"topic_id": tid, "host": h, "url": d["source_url"]})
                    break
    flat = [p for tid in order for p in picks[tid]]
    if DB_PATH.exists():
        st = open_store()
        known = {r[0] for r in st.db.execute("SELECT source_url FROM records")}
        covered = {
            (json.loads(r[0]).get("topic_id"), r[1])
            for r in st.db.execute("SELECT facts_json, host FROM records WHERE complete=1 AND facts_json IS NOT NULL")
        }
        flat = [p for p in flat if p["url"] not in known and (p["topic_id"], p["host"]) not in covered]
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(flat, ensure_ascii=False, indent=1))
    return flat


def run(plan_items: list[dict], *, limit: int | None = None, actor: str = "food-daily-import") -> dict:
    st = open_store()
    client = Client()
    PRIVATE.mkdir(parents=True, exist_ok=True)
    os.chmod(PRIVATE, 0o700)
    counts = {
        "planned": len(plan_items),
        "skipped_known": 0,
        "robots_disallow": 0,
        "fetched": 0,
        "fetch_failed": 0,
        "extracted": 0,
        "complete": 0,
        "no_recipe": 0,
    }
    robots_cache: dict[str, Robots] = {}
    for item in plan_items[: limit or None]:
        url, host = item["url"], item["host"]
        if st.db.execute("SELECT 1 FROM records WHERE source_url=?", (url,)).fetchone():
            counts["skipped_known"] += 1
            continue
        if host not in robots_cache:
            rp = CRAWL_ROOT / host / "robots.txt"
            robots_cache[host] = Robots(rp.read_text() if rp.exists() else "")
        if not robots_cache[host].can_fetch(client.cfg["user_agent"], url):
            counts["robots_disallow"] += 1
            continue
        try:
            r = client.get(url, use_cache=False)
        except FetchRefused as e:
            counts["fetch_failed"] += 1
            st.audit(actor, "fetch_refused", url=url, error=str(e))
            continue
        rid = "rec-" + hashlib.sha256(url.encode()).hexdigest()[:16]
        retention = (datetime.now(timezone.utc) + timedelta(days=SOURCES.get(host, (0, 0, 0, 0, 30))[4])).strftime(
            "%Y-%m-%d"
        )
        if r.status != 200:
            counts["fetch_failed"] += 1
            st.db.execute(
                "INSERT INTO records (record_id, site_id, host, source_url, final_url, http_status, fetched_at, "
                "status) VALUES (?,?,?,?,?,?,?,?)",
                (rid, SITE_ID, host, url, r.url, r.status, now(), "fetch_failed"),
            )
            continue
        counts["fetched"] += 1
        # исходник — только в закрытое хранилище, сжатым, со сроком хранения
        raw_path = PRIVATE / host / f"{rid}.html.gz"
        raw_path.parent.mkdir(parents=True, exist_ok=True)
        raw_path.write_bytes(gzip.compress(r.body))
        facts = extract(r.text(), url, r.url)
        if facts is None:
            counts["no_recipe"] += 1
            st.db.execute(
                "INSERT INTO records (record_id, site_id, host, source_url, final_url, http_status, fetched_at, "
                "parser_version, private_path, retention_until, status) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                (
                    rid,
                    SITE_ID,
                    host,
                    url,
                    r.url,
                    r.status,
                    now(),
                    PARSER_VERSION,
                    str(raw_path.relative_to(REPO)),
                    retention,
                    "no_recipe_markup",
                ),
            )
            continue
        counts["extracted"] += 1
        fd = facts.to_dict()
        fd["topic_id"] = item["topic_id"]
        complete = is_complete(facts)
        counts["complete"] += int(complete)
        st.db.execute(
            "INSERT INTO records VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                rid,
                SITE_ID,
                host,
                url,
                r.url,
                facts.canonical_url,
                r.status,
                now(),
                facts.content_hash,
                PARSER_VERSION,
                facts.extracted_with,
                int(complete),
                json.dumps(fd, ensure_ascii=False),
                json.dumps(facts.remarks, ensure_ascii=False),
                str(raw_path.relative_to(REPO)),
                retention,
                _dedupe_key(item["topic_id"], fd),
                "extracted" if complete else "extracted_incomplete",
            ),
        )
        st.audit(actor, "record_extracted", url=url, complete=complete, remarks=facts.remarks)
    return counts


def reextract(st: Store) -> dict:
    """Повторное извлечение из закрытого хранилища новой версией парсера,
    без сетевых запросов. Записи, чей исходник уже удалён по сроку, не трогаются."""
    out = {"reextracted": 0, "complete": 0, "missing_raw": 0}
    for r in st.db.execute("SELECT * FROM records WHERE private_path IS NOT NULL").fetchall():
        p = REPO / r["private_path"]
        if not p.exists():
            out["missing_raw"] += 1
            continue
        old = json.loads(r["facts_json"]) if r["facts_json"] else {}
        facts = extract(
            gzip.decompress(p.read_bytes()).decode("utf-8", "replace"),
            r["source_url"],
            r["final_url"],
        )
        if facts is None:
            continue
        fd = facts.to_dict()
        fd["topic_id"] = old.get("topic_id")
        complete = is_complete(facts)
        st.db.execute(
            "UPDATE records SET facts_json=?, remarks_json=?, complete=?, content_hash=?, parser_version=?, "
            "extracted_with=?, canonical_url=?, dedupe_key=?, status=? WHERE record_id=?",
            (
                json.dumps(fd, ensure_ascii=False),
                json.dumps(facts.remarks, ensure_ascii=False),
                int(complete),
                facts.content_hash,
                PARSER_VERSION,
                facts.extracted_with,
                facts.canonical_url,
                _dedupe_key(fd["topic_id"], fd),
                "extracted" if complete else "extracted_incomplete",
                r["record_id"],
            ),
        )
        out["reextracted"] += 1
        out["complete"] += int(complete)
    st.audit("food-daily-import", "reextract", parser_version=PARSER_VERSION, **out)
    return out


def retopic(st: Store) -> dict:
    """Перепривязка записей к темам текущим сопоставителем (без сети).
    Запись, слаг которой не подходит ни к одной теме, получает topic_id=None
    и статус topic_mismatch: она не становится материалом темы."""
    import csv

    order = [r["topic_id"] for r in csv.DictReader((ROOT / "data" / "topic-map.csv").open())]
    need = {t["topic_id"]: ([term(x) for x in t["need"]], [term(x) for x in t["exclude"]]) for t in TOPICS}
    out = {"kept": 0, "changed": 0, "mismatch": 0}
    for r in st.db.execute(
        "SELECT record_id, source_url, facts_json, complete FROM records WHERE facts_json IS NOT NULL"
    ).fetchall():
        fd = json.loads(r["facts_json"])
        toks = _slug_tokens(r["source_url"])
        matched = [tid for tid in order if topic_matches(toks, *need[tid])]
        new = fd["topic_id"] if fd["topic_id"] in matched else (matched[0] if matched else None)
        out["kept" if new == fd["topic_id"] else ("mismatch" if new is None else "changed")] += 1
        fd["topic_id"], fd["topic_candidates"] = new, matched
        status = "topic_mismatch" if new is None else ("extracted" if r["complete"] else "extracted_incomplete")
        st.db.execute(
            "UPDATE records SET facts_json=?, status=?, dedupe_key=? WHERE record_id=?",
            (
                json.dumps(fd, ensure_ascii=False),
                status,
                _dedupe_key(new or "none", fd),
                r["record_id"],
            ),
        )
    st.audit("food-daily-import", "retopic", **out)
    return out


def dedupe_report(st: Store) -> dict:
    rows = st.db.execute(
        "SELECT record_id, dedupe_key, complete, facts_json FROM records WHERE facts_json IS NOT NULL"
    ).fetchall()
    by_topic: dict[str, list] = {}
    for r in rows:
        by_topic.setdefault(json.loads(r["facts_json"])["topic_id"], []).append(r)
    keys = {r["dedupe_key"] for r in rows}
    return {
        "records_with_facts": len(rows),
        "unique_dedupe_keys": len(keys),
        "topics": len(by_topic),
        "topics_with_several_variants": sum(1 for v in by_topic.values() if len({x["dedupe_key"] for x in v}) > 1),
    }


def purge_expired(st: Store) -> int:
    """Удаляет просроченные исходники из закрытого хранилища (факты остаются)."""
    today = time.strftime("%Y-%m-%d")
    n = 0
    for r in st.db.execute(
        "SELECT record_id, private_path FROM records WHERE retention_until < ? AND private_path IS NOT NULL",
        (today,),
    ).fetchall():
        p = REPO / r["private_path"]
        if p.exists():
            p.unlink()
            n += 1
        st.db.execute("UPDATE records SET private_path=NULL WHERE record_id=?", (r["record_id"],))
    return n


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="food-daily import")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p1 = sub.add_parser("plan")
    p1.add_argument("--hosts", default="eda-rambler,gastronom,1000-menu")
    p1.add_argument("--per-topic", type=int, default=1)
    p1.add_argument("--topics", type=int, default=40)
    p2 = sub.add_parser("run")
    p2.add_argument("--limit", type=int)
    sub.add_parser("status")
    sub.add_parser("reextract")
    sub.add_parser("retopic")
    sub.add_parser("purge-expired")
    a = ap.parse_args(argv)
    plan_path = VAR / "import" / "plan.json"
    if a.cmd == "plan":
        items = plan(a.hosts.split(","), a.per_topic, a.topics, plan_path)
        print(
            json.dumps(
                {
                    "planned": len(items),
                    "by_host": {h: sum(1 for i in items if i["host"] == h) for h in a.hosts.split(",")},
                },
                ensure_ascii=False,
            )
        )
    elif a.cmd == "run":
        print(json.dumps(run(json.loads(plan_path.read_text()), limit=a.limit), ensure_ascii=False))
    elif a.cmd == "status":
        st = open_store()
        q = lambda sql: st.db.execute(sql).fetchone()[0]  # noqa: E731
        print(
            json.dumps(
                {
                    "records": q("SELECT count(*) FROM records"),
                    "by_status": dict(st.db.execute("SELECT status, count(*) FROM records GROUP BY status").fetchall()),
                    "by_host": dict(st.db.execute("SELECT host, count(*) FROM records GROUP BY host").fetchall()),
                    **dedupe_report(st),
                },
                ensure_ascii=False,
            )
        )
    elif a.cmd == "reextract":
        print(json.dumps(reextract(open_store())))
    elif a.cmd == "retopic":
        print(json.dumps(retopic(open_store())))
    elif a.cmd == "purge-expired":
        print(json.dumps({"purged": purge_expired(open_store())}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
