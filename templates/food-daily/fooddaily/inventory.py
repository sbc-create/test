"""Реестр URL референсов: robots.txt → sitemap-index → вложенные карты.

Возобновляемый: состояние хоста в var/food-daily/crawl/<id>/state.json,
URL дописываются в urls.jsonl (сырой и нормализованный адрес, источник
обнаружения). Повторный запуск продолжает с первой необработанной карты.
Тексты страниц здесь не скачиваются — только карты сайта.
"""

from __future__ import annotations

import argparse
import contextlib
import gzip
import json
import re
import time
import urllib.parse
import xml.etree.ElementTree as ET
from pathlib import Path

from .http import REPO, Client, FetchRefused, load_config
from .robots import Robots

CRAWL_ROOT = REPO / "var" / "food-daily" / "crawl"

# Параметры, которые не меняют содержимое страницы (отслеживание).
TRACKING = re.compile(r"^(utm_[a-z]+|yclid|gclid|fbclid|from|ref|_openstat)$", re.I)


def normalize(url: str) -> str:
    """Нормализация без потери значимых параметров.

    Схема и хост в нижний регистр, фрагмент и параметры отслеживания
    убираются, остальной query сохраняется в исходном порядке: у части
    сайтов ID рецепта стоит именно в query string.
    """
    p = urllib.parse.urlsplit(url.strip())
    q = [(k, v) for k, v in urllib.parse.parse_qsl(p.query, keep_blank_values=True) if not TRACKING.match(k)]
    path = p.path or "/"
    return urllib.parse.urlunsplit((p.scheme.lower(), (p.hostname or "").lower(), path, urllib.parse.urlencode(q), ""))


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def parse_sitemap(body: bytes) -> tuple[str, list[dict]]:
    """Возвращает (kind, entries): kind = sitemapindex | urlset | invalid."""
    try:
        root = ET.fromstring(body)
    except ET.ParseError:
        return "invalid", []
    kind = _local(root.tag)
    out = []
    for node in root:
        rec: dict = {}
        for child in node:
            name = _local(child.tag)
            if name in ("loc", "lastmod"):
                rec[name] = (child.text or "").strip()
            elif name == "video":
                rec["has_video"] = True
            elif name == "image":
                rec["images"] = rec.get("images", 0) + 1
        if rec.get("loc"):
            out.append(rec)
    return kind, out


class HostInventory:
    def __init__(self, host_cfg: dict, client: Client):
        self.h = host_cfg
        self.c = client
        self.dir = CRAWL_ROOT / host_cfg["id"]
        self.dir.mkdir(parents=True, exist_ok=True)
        self.state_path = self.dir / "state.json"
        self.log_path = self.dir / "journal.jsonl"
        self.state = self._load()

    def _load(self) -> dict:
        if self.state_path.exists():
            return json.loads(self.state_path.read_text())
        return {
            "host": self.h["id"],
            "base": self.h["base"],
            "started_at": _now(),
            "robots": None,
            "pending": [],
            "done": {},
            "url_count_raw": 0,
            "finished": False,
        }

    def save(self) -> None:
        tmp = self.state_path.with_suffix(".tmp")
        tmp.write_text(json.dumps(self.state, ensure_ascii=False, indent=1))
        tmp.replace(self.state_path)

    def log(self, **rec) -> None:
        rec["at"] = _now()
        with self.log_path.open("a") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")

    # ---------------------------------------------------------------------
    def robots(self) -> None:
        if self.state["robots"] is not None:
            return
        url = self.h["base"].rstrip("/") + "/robots.txt"
        try:
            r = self.c.get(url)
        except FetchRefused as e:
            self.state["robots"] = {"url": url, "status": None, "error": str(e), "sitemaps": []}
            self.save()
            return
        text = r.text() if r.status == 200 else ""
        sitemaps = re.findall(r"(?im)^\s*sitemap\s*:\s*(\S+)", text)
        self.state["robots"] = {
            "url": url,
            "final_url": r.url,
            "status": r.status,
            "error": r.error,
            "redirects": r.redirects,
            "sitemaps": sitemaps,
            "bytes": len(r.body),
        }
        (self.dir / "robots.txt").write_text(text)
        if not sitemaps:
            sitemaps = [self.h["base"].rstrip("/") + "/sitemap.xml"]
            self.state["robots"]["sitemap_fallback"] = sitemaps[0]
        for s in sitemaps:
            if s not in self.state["done"] and s not in self.state["pending"]:
                self.state["pending"].append(s)
        self.log(event="robots", status=r.status, sitemaps=len(sitemaps))
        self.save()

    def robot_parser(self) -> Robots:
        p = self.dir / "robots.txt"
        return Robots(p.read_text() if p.exists() else "")

    def run(self, *, max_sitemaps: int | None = None, deadline: float | None = None) -> dict:
        self.robots()
        lim = self.c.lim
        cap = max_sitemaps or int(lim["max_sitemaps_per_host"])
        deadline = deadline or (time.monotonic() + float(lim["max_runtime_seconds_per_host"]))
        rp = self.robot_parser()
        processed = 0
        with (self.dir / "urls.jsonl").open("a") as out:
            while self.state["pending"]:
                if len(self.state["done"]) >= cap or time.monotonic() > deadline:
                    self.state["stopped_reason"] = "limit"
                    break
                if _disk(self.dir) > int(lim["max_disk_bytes_per_host"]):
                    self.state["stopped_reason"] = "disk limit"
                    break
                sm = self.state["pending"][0]
                if not rp.can_fetch(self.c.cfg["user_agent"], sm):
                    self.state["done"][sm] = {"status": "robots_disallow"}
                    self.state["pending"].pop(0)
                    continue
                try:
                    r = self.c.get(sm, use_cache=False)
                except FetchRefused as e:
                    self.state["done"][sm] = {"status": None, "error": str(e)}
                    self.state["pending"].pop(0)
                    self.log(event="refused", sitemap=sm, error=str(e))
                    self.save()
                    continue
                body = r.body
                if body[:2] == b"\x1f\x8b":
                    with contextlib.suppress(OSError):
                        body = gzip.decompress(body)
                kind, entries = parse_sitemap(body) if r.status == 200 else ("http_error", [])
                rec = {
                    "status": r.status,
                    "kind": kind,
                    "entries": len(entries),
                    "final_url": r.url,
                    "error": r.error,
                    "redirects": len(r.redirects),
                }
                if kind == "sitemapindex":
                    for e in entries:
                        loc = e["loc"]
                        if loc not in self.state["done"] and loc not in self.state["pending"]:
                            self.state["pending"].append(loc)
                elif kind == "urlset":
                    for e in entries:
                        out.write(
                            json.dumps(
                                {
                                    "source_url": e["loc"],
                                    "url": normalize(e["loc"]),
                                    "lastmod": e.get("lastmod") or None,
                                    "discovered_via": "sitemap",
                                    "sitemap": sm,
                                    "has_video": e.get("has_video", False),
                                },
                                ensure_ascii=False,
                            )
                            + "\n"
                        )
                    self.state["url_count_raw"] += len(entries)
                self.state["done"][sm] = rec
                self.state["pending"].pop(0)
                processed += 1
                self.log(event="sitemap", sitemap=sm, **rec)
                if processed % 5 == 0:
                    out.flush()
                    self.save()
        self.state["finished"] = not self.state["pending"]
        self.state["updated_at"] = _now()
        self.save()
        return {
            "host": self.h["id"],
            "sitemaps_done": len(self.state["done"]),
            "pending": len(self.state["pending"]),
            "raw_urls": self.state["url_count_raw"],
            "finished": self.state["finished"],
        }


def _disk(d: Path) -> int:
    return sum(p.stat().st_size for p in d.rglob("*") if p.is_file())


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="food-daily inventory")
    ap.add_argument("--host", action="append", help="id хоста из config/crawl.yaml; по умолчанию все")
    ap.add_argument("--max-sitemaps", type=int)
    ap.add_argument("--max-seconds", type=float)
    a = ap.parse_args(argv)
    cfg = load_config()
    hosts = [h for h in cfg["hosts"] if ((h["id"] in a.host) if a.host else not h.get("ux_only"))]
    import concurrent.futures as cf

    client = Client(config=cfg)
    deadline = time.monotonic() + a.max_seconds if a.max_seconds else None
    # разные хосты параллельно, внутри хоста — строго по одному запросу
    with cf.ThreadPoolExecutor(max_workers=len(hosts) or 1) as ex:
        futs = {
            ex.submit(HostInventory(h, client).run, max_sitemaps=a.max_sitemaps, deadline=deadline): h["id"]
            for h in hosts
        }
        for f in cf.as_completed(futs):
            try:
                print(json.dumps(f.result(), ensure_ascii=False), flush=True)
            except Exception as e:  # один хост не останавливает остальные
                print(
                    json.dumps({"host": futs[f], "error": f"{type(e).__name__}: {e}"}, ensure_ascii=False),
                    flush=True,
                )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
