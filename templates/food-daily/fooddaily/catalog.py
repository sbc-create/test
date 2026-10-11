"""Обход каталога для сайтов без карты сайта.

Переходит только по страницам-спискам (регулярные выражения `follow` из
config/crawl.yaml), а все ссылки того же хоста записывает в urls.jsonl с
`discovered_via=catalog`. Тексты рецептов не скачиваются. Очередь и
посещённые страницы лежат в catalog-state.json — повторный запуск
продолжает с места остановки.
"""

from __future__ import annotations

import argparse
import html
import json
import re
import time
import urllib.parse

from .http import Client, FetchRefused, load_config
from .inventory import CRAWL_ROOT, normalize
from .robots import Robots

HREF = re.compile(r"""href\s*=\s*["']([^"'#<>\s]+)["']""", re.I)
ASSET = re.compile(r"\.(css|js|png|jpe?g|gif|svg|webp|ico|woff2?|json|xml|pdf)(\?|$)", re.I)


class CatalogCrawl:
    def __init__(self, host_cfg: dict, client: Client):
        self.h = host_cfg
        self.c = client
        self.cat = host_cfg["catalog"]
        self.base = host_cfg["base"].rstrip("/")
        self.host = urllib.parse.urlsplit(self.base).hostname
        self.dir = CRAWL_ROOT / host_cfg["id"]
        self.dir.mkdir(parents=True, exist_ok=True)
        self.state_path = self.dir / "catalog-state.json"
        self.follow = [re.compile(p) for p in self.cat["follow"]]
        robots_path = self.dir / "robots.txt"
        if not robots_path.exists():
            r = client.get(self.base + "/robots.txt")
            robots_path.write_text(r.text() if r.status == 200 else "")
        self.robots = Robots(robots_path.read_text())
        if self.state_path.exists():
            self.state = json.loads(self.state_path.read_text())
        else:
            self.state = {
                "host": host_cfg["id"],
                "started_at": _now(),
                "queue": [self.base + s for s in self.cat["seeds"]],
                "visited": {},
                "seen_links": 0,
                "finished": False,
            }
        self.seen: set[str] = set(self.state["visited"]) | set(self.state["queue"])

    def _follow(self, url: str) -> bool:
        p = urllib.parse.urlsplit(url)
        pq = p.path + (("?" + p.query) if p.query else "")
        return any(rx.search(pq) for rx in self.follow)

    def save(self) -> None:
        tmp = self.state_path.with_suffix(".tmp")
        tmp.write_text(json.dumps(self.state, ensure_ascii=False))
        tmp.replace(self.state_path)

    def run(self, *, deadline: float, max_pages: int | None = None) -> dict:
        cap = max_pages or int(self.cat["max_pages"])
        ua = self.c.cfg["user_agent"]
        recorded: set[str] = set()
        out_path = self.dir / "urls.jsonl"
        if out_path.exists():
            for line in out_path.open():
                if '"catalog"' in line:
                    recorded.add(json.loads(line)["url"])
        with out_path.open("a") as out, (self.dir / "journal.jsonl").open("a") as log:
            while self.state["queue"] and len(self.state["visited"]) < cap and time.monotonic() < deadline:
                url = self.state["queue"].pop(0)
                if not self.robots.can_fetch(ua, url):
                    self.state["visited"][url] = "robots_disallow"
                    continue
                try:
                    r = self.c.get(url, use_cache=False)
                except FetchRefused as e:
                    self.state["visited"][url] = f"refused: {e}"
                    continue
                self.state["visited"][url] = r.status
                log.write(
                    json.dumps(
                        {
                            "at": _now(),
                            "event": "catalog_page",
                            "url": url,
                            "status": r.status,
                            "final": r.url,
                            "error": r.error,
                        },
                        ensure_ascii=False,
                    )
                    + "\n"
                )
                if r.status != 200:
                    continue
                for raw in HREF.findall(r.text()):
                    link = urllib.parse.urljoin(r.url, html.unescape(raw))
                    lp = urllib.parse.urlsplit(link)
                    if lp.scheme != "https" or lp.hostname != self.host or ASSET.search(lp.path):
                        continue
                    norm = normalize(link)
                    if norm not in recorded:
                        recorded.add(norm)
                        out.write(
                            json.dumps(
                                {
                                    "source_url": link,
                                    "url": norm,
                                    "lastmod": None,
                                    "discovered_via": "catalog",
                                    "sitemap": None,
                                    "found_on": url,
                                    "has_video": False,
                                },
                                ensure_ascii=False,
                            )
                            + "\n"
                        )
                        self.state["seen_links"] += 1
                    if self._follow(norm) and norm not in self.seen:
                        self.seen.add(norm)
                        self.state["queue"].append(norm)
                if len(self.state["visited"]) % 20 == 0:
                    out.flush()
                    self.save()
        self.state["finished"] = not self.state["queue"]
        self.state["stopped_reason"] = None if self.state["finished"] else "page/time budget"
        self.state["updated_at"] = _now()
        self.save()
        return {
            "host": self.h["id"],
            "pages": len(self.state["visited"]),
            "queue": len(self.state["queue"]),
            "links": self.state["seen_links"],
            "finished": self.state["finished"],
        }


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="food-daily catalog")
    ap.add_argument("--host", action="append")
    ap.add_argument("--max-pages", type=int)
    ap.add_argument("--max-seconds", type=float, default=5400)
    a = ap.parse_args(argv)
    cfg = load_config()
    hosts = [h for h in cfg["hosts"] if "catalog" in h and (not a.host or h["id"] in a.host)]
    client = Client(config=cfg)
    deadline = time.monotonic() + a.max_seconds
    import concurrent.futures as cf

    with cf.ThreadPoolExecutor(max_workers=len(hosts) or 1) as ex:
        futs = {
            ex.submit(CatalogCrawl(h, client).run, deadline=deadline, max_pages=a.max_pages): h["id"] for h in hosts
        }
        for f in cf.as_completed(futs):
            try:
                print(json.dumps(f.result(), ensure_ascii=False), flush=True)
            except Exception as e:
                print(json.dumps({"host": futs[f], "error": f"{type(e).__name__}: {e}"}), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
