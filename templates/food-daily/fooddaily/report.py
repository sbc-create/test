"""Отчёты аудита: таблица подсчёта, экспорт реестра, выборочная проверка.

coverage_status:
* complete — все карты сайта, найденные по robots.txt/sitemap-index, получены
  с кодом 200 и разобраны; «complete» относится ТОЛЬКО к этому охвату, а не
  к индексу поисковика и не к цифре на главной сайта;
* partial — охват ограничен (обход каталога, запрет robots, бюджет страниц,
  часть карт недоступна);
* unavailable — данных нет.
Неизвестное — пусто (null), а не ноль.
"""

from __future__ import annotations

import argparse
import csv
import json
import random
import re
import time
from pathlib import Path

from .classify import classify, host_counts
from .extract import extract
from .http import Client, FetchRefused, load_config
from .inventory import CRAWL_ROOT
from .robots import Robots

ROOT = Path(__file__).resolve().parents[1]
AUDIT = ROOT / "docs" / "audit"
RU_HOSTS = [h["id"] for h in load_config()["hosts"] if not h.get("ux_only")]


def _state(host: str, name: str) -> dict | None:
    p = CRAWL_ROOT / host / name
    return json.loads(p.read_text()) if p.exists() else None


def host_row(host: str, export_dir: Path | None) -> dict:
    sm, cat = _state(host, "state.json"), _state(host, "catalog-state.json")
    c = host_counts(host, export=(export_dir / f"{host}.jsonl.gz") if export_dir else None)
    sm_urls = sm and sm.get("url_count_raw", 0) > 0
    reasons = []
    if sm_urls:
        bad = {
            k: v
            for k, v in sm["done"].items()
            if v.get("status") != 200 or v.get("kind") not in ("urlset", "sitemapindex")
        }
        method = "sitemap"
        scope = f"все карты из robots.txt/sitemap-index: {len(sm['done'])} файлов"
        status = "complete" if sm["finished"] and not bad else "partial"
        if bad:
            reasons.append(f"недоступны карты: {len(bad)}")
    elif cat:
        method = "catalog_crawl"
        scope = f"обход рубрик: {len(cat['visited'])} страниц-списков, правила follow из config/crawl.yaml"
        status = "partial"
        reasons.append("карта сайта недоступна (" + _sitemap_reason(sm) + "); обход каталога не равен полному реестру")
        robots_blocked = sum(1 for v in cat["visited"].values() if v == "robots_disallow")
        if robots_blocked:
            reasons.append(f"robots.txt запрещает {robots_blocked} страниц-списков (напр. пагинацию)")
        if not cat.get("finished"):
            reasons.append(f"бюджет обхода исчерпан, в очереди {len(cat['queue'])} страниц")
    else:
        method, scope, status = "none", "", "unavailable"
        reasons.append(_sitemap_reason(sm))
    checked = (cat or {}).get("updated_at") or (sm or {}).get("updated_at")
    row = {
        "host": load_host(host)["base"].split("//")[1],
        "checked_at": checked,
        "method": method,
        "scope": scope,
        "coverage_status": status,
        "unique_urls": c.get("unique_urls"),
        "recipe_urls": c.get("recipe"),
        "article_urls": c.get("article"),
        "category_urls": c.get("category"),
        "tag_urls": c.get("tag"),
        "video_page_urls": c.get("video"),
        "other_urls": c.get("other"),
        "unknown_urls": c.get("unknown"),
        "listing_pages_excluded": c.get("listing_page"),
        "variants_excluded": c.get("variant"),
        "incompleteness": "; ".join(reasons) or None,
        "evidence": f"var/food-daily/crawl/{host}/ (journal.jsonl, state); data/inventory/{host}.jsonl.gz",
    }
    return row


def _sitemap_reason(sm: dict | None) -> str:
    if not sm:
        return "карта не запрашивалась"
    done = sm.get("done", {})
    return (
        ", ".join(
            f"{u.rsplit('/', 1)[-1]} → {v.get('status')}{'/' + v['kind'] if v.get('kind') else ''}"
            for u, v in list(done.items())[:3]
        )
        or "нет карт"
    )


def load_host(host_id: str) -> dict:
    return next(h for h in load_config()["hosts"] if h["id"] == host_id)


def counts(export: bool) -> list[dict]:
    exp = ROOT / "data" / "inventory" if export else None
    rows = [host_row(h, exp) for h in RU_HOSTS]
    AUDIT.mkdir(parents=True, exist_ok=True)
    with (AUDIT / "competitor-counts.csv").open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    return rows


def verify_sample(hosts: list[str], n: int, seed: int) -> dict:
    """Выборка по хосту: половина — URL, классифицированные как рецепт,
    половина — остальные типы. Проверяется HTTP, canonical, meta robots и
    наличие разметки Recipe; «рецепт» без разметки и «не рецепт» с ней —
    расхождения классификации."""
    client = Client()
    rnd = random.Random(seed)
    out = {
        "seed": seed,
        "per_host": n,
        "checked_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "hosts": {},
    }
    for h in hosts:
        p = CRAWL_ROOT / h / "urls.jsonl"
        if not p.exists():
            continue
        seen, rec, non = set(), [], []
        for line in p.open():
            d = json.loads(line)
            if d["url"] in seen:
                continue
            seen.add(d["url"])
            t, rule = classify(h, d["url"], d.get("sitemap"))
            if t in ("listing_page", "variant"):
                continue
            (rec if t == "recipe" else non).append((d["source_url"], t, rule))
        sample = rnd.sample(rec, min(n // 2, len(rec))) + rnd.sample(non, min(n - n // 2, len(non)))
        rp = CRAWL_ROOT / h / "robots.txt"
        robots = Robots(rp.read_text() if rp.exists() else "")
        rows = []
        for url, t, rule in sample:
            if not robots.can_fetch(client.cfg["user_agent"], url):
                rows.append({"url": url, "type": t, "rule": rule, "status": "robots_disallow"})
                continue
            try:
                r = client.get(url, use_cache=False)
            except FetchRefused as e:
                rows.append({"url": url, "type": t, "rule": rule, "status": None, "error": str(e)})
                continue
            page = r.text()
            canon = re.search(r'<link[^>]+rel=["\']canonical["\'][^>]*href=["\']([^"\']+)', page, re.I) or re.search(
                r'<link[^>]+href=["\']([^"\']+)["\'][^>]*rel=["\']canonical', page, re.I
            )
            robots_meta = re.search(r'<meta[^>]+name=["\']robots["\'][^>]*content=["\']([^"\']+)', page, re.I)
            # JSON-LD и микроразметка одного рецепта — не два рецепта: берётся максимум
            n_recipe = max(
                len(re.findall(r'"@type"\s*:\s*\[?\s*"Recipe"', page)),
                len(re.findall(r'itemtype=["\']https?://schema\.org/Recipe', page)),
            )
            title_m = re.search(r"<title[^>]*>(.*?)</title>", page, re.S | re.I)
            title = re.sub(r"\s+", " ", title_m.group(1)).strip() if title_m else ""
            # ItemList и слово «рецепты» встречаются и на странице одного рецепта
            # (блок похожих), поэтому признак листинга — несколько Recipe или «N рецептов»
            listing = n_recipe > 1 or bool(re.search(r"\d+\s+рецепт", title, re.I))
            has_recipe = n_recipe >= 1 and not listing  # главный объект страницы — один рецепт
            facts = extract(page, url, r.url) if has_recipe else None
            agree = (t == "recipe") == has_recipe
            rows.append(
                {
                    "url": url,
                    "type": t,
                    "rule": rule,
                    "status": r.status,
                    "final_url": r.url,
                    "redirects": len(r.redirects),
                    "canonical": canon.group(1) if canon else None,
                    "canonical_self": (canon.group(1).rstrip("/") == r.url.rstrip("/")) if canon else None,
                    "meta_robots": robots_meta.group(1) if robots_meta else None,
                    "recipe_markup": has_recipe,
                    "recipe_markup_count": n_recipe,
                    "listing_signals": listing,
                    "title": title[:120],
                    "recipe_title": facts.title if facts else None,
                    "classification_agrees": agree,
                }
            )
        ok = [x for x in rows if x.get("status") == 200]
        out["hosts"][h] = {
            "sampled": len(rows),
            "http_200": len(ok),
            "classification_agree": sum(1 for x in ok if x["classification_agrees"]),
            "recipe_type_sampled": sum(1 for x in ok if x["type"] == "recipe"),
            "recipe_type_with_markup": sum(1 for x in ok if x["type"] == "recipe" and x["recipe_markup"]),
            "non_recipe_with_markup": sum(1 for x in ok if x["type"] != "recipe" and x["recipe_markup"]),
            "canonical_self": sum(1 for x in ok if x.get("canonical_self")),
            "canonical_other": sum(1 for x in ok if x.get("canonical_self") is False),
            "no_canonical": sum(1 for x in ok if x.get("canonical") is None),
            "noindex": sum(1 for x in ok if x.get("meta_robots") and "noindex" in x["meta_robots"].lower()),
            "rows": rows,
        }
    return out


def _topic_status(rows: list[dict]) -> None:
    """Статус обработки темы — по фактическому состоянию хранилища и снимка."""
    from .pipeline import DB_PATH, open_store

    if not DB_PATH.exists():
        return
    st = open_store()
    ready, preview, blocked = set(), set(), set()
    for r in st.db.execute("SELECT facts_json, complete FROM records WHERE facts_json IS NOT NULL"):
        if r["complete"]:
            ready.add(json.loads(r["facts_json"]).get("topic_id"))
    for r in st.db.execute(
        "SELECT c.publish_status, v.payload_json FROM content c JOIN versions v "
        "ON v.content_id=c.content_id AND v.recipe_version=c.current_version"
    ):
        tid = json.loads(r["payload_json"])["facts"].get("topic_id")
        (preview if r["publish_status"] in ("preview", "published") else blocked).add(tid)
    for row in rows:
        t = row["topic_id"]
        row["status"] = (
            "preview"
            if t in preview
            else "blocked_facts"
            if t in blocked
            else "facts_ready"
            if t in ready
            else "queued"
        )
    path = ROOT / "data" / "topic-map.csv"
    with path.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="food-daily report")
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("counts")
    c.add_argument("--export", action="store_true", help="записать data/inventory/<host>.jsonl.gz")
    v = sub.add_parser("verify-sample")
    v.add_argument("--hosts", default=",".join(RU_HOSTS))
    v.add_argument("--n", type=int, default=12)
    v.add_argument("--seed", type=int, default=20261011)
    v.add_argument("--out", default=str(AUDIT / "verify-sample.json"))
    sub.add_parser("topics")
    a = ap.parse_args(argv)
    if a.cmd == "counts":
        for r in counts(a.export):
            print(
                json.dumps(
                    {
                        k: r[k]
                        for k in (
                            "host",
                            "coverage_status",
                            "unique_urls",
                            "recipe_urls",
                            "unknown_urls",
                        )
                    },
                    ensure_ascii=False,
                )
            )
    elif a.cmd == "verify-sample":
        res = verify_sample(a.hosts.split(","), a.n, a.seed)
        out = Path(a.out)
        if out.exists():  # слияние: прежние хосты сохраняются, перепроверенные заменяются
            prev = json.loads(out.read_text())
            prev["hosts"].update(res["hosts"])
            prev.setdefault("runs", []).append({"checked_at": res["checked_at"], "hosts": list(res["hosts"])})
            res = {**prev, "seed": res["seed"], "per_host": res["per_host"]}
        out.write_text(json.dumps(res, ensure_ascii=False, indent=1) + "\n")
        for h, x in res["hosts"].items():
            print(h, {k: v for k, v in x.items() if k != "rows"})
    elif a.cmd == "topics":
        from .topics import build

        rows = build(ROOT / "data" / "topic-map.csv", RU_HOSTS)
        _topic_status(rows)
        print(json.dumps({"topics": len(rows), "food_daily": sum(r["site_id"] == "food-daily" for r in rows)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
