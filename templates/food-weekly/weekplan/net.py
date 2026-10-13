"""Сеть food-weekly: внешние хосты — только из allowlist (GET, robots.txt, пауза);
петля — только лента каталога сайтов сети из config/network.yaml."""

from __future__ import annotations

import ipaddress
import json
import re
import socket
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parents[1]
UA = "food-weekly-audit/1.0 (site-factory reference audit; respects robots.txt)"


class Refused(RuntimeError):
    pass


def allowed() -> set[str]:
    inv = yaml.safe_load((REPO / "inventory" / "network-allowlist.yaml").read_text())
    mine = set(yaml.safe_load((ROOT / "config" / "network.yaml").read_text())["audit_hosts"])
    return mine & {e["host"] for e in inv["hosts"] if "GET" in e.get("methods", [])}


def robots_allows(text: str, url: str) -> bool:
    rules, active, saw = [], False, False
    for raw in text.splitlines():
        line = raw.split("#", 1)[0].strip()
        if ":" not in line:
            continue
        k, v = (x.strip() for x in line.split(":", 1))
        k = k.lower()
        if k == "user-agent":
            if saw:
                active, saw = False, False
            active = active or v == "*"
        elif k in ("allow", "disallow") and active:
            saw = True
            if v:
                rx = "".join(".*" if c == "*" else re.escape(c) for c in v.rstrip("$")) + (
                    "$" if v.endswith("$") else ""
                )
                rules.append((k == "allow", len(v), re.compile(rx)))
    p = urllib.parse.urlsplit(url)
    path = (p.path or "/") + (f"?{p.query}" if p.query else "")
    best, ok = -1, True
    for a, n, rx in rules:
        if rx.match(path) and (n > best or (n == best and a)):
            best, ok = n, a
    return ok


class Client:
    def __init__(self, delay: float = 2.5):
        self.ok, self.delay, self.last, self.robots, self.requests = allowed(), delay, {}, {}, 0

    def _open(self, url: str) -> tuple[int | None, str, str]:
        host = urllib.parse.urlsplit(url).hostname
        wait = self.last.get(host, 0) + self.delay - time.monotonic()
        if wait > 0:
            time.sleep(wait)
        self.requests += 1
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": UA}), timeout=30) as r:
                return r.status, r.url, r.read(10_000_000).decode("utf-8", "replace")
        except urllib.error.HTTPError as e:
            return e.code, url, ""
        finally:
            self.last[host] = time.monotonic()

    def get(self, url: str) -> tuple[int | None, str, str]:
        p = urllib.parse.urlsplit(url)
        if p.scheme != "https" or p.hostname not in self.ok:
            raise Refused(f"вне политики: {url}")
        for info in socket.getaddrinfo(p.hostname, 443):
            ip = ipaddress.ip_address(info[4][0])
            if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved:
                raise Refused(f"непубличный адрес {ip}")
        if p.hostname not in self.robots:
            st, _, txt = self._open(f"https://{p.hostname}/robots.txt")
            self.robots[p.hostname] = txt if st == 200 else ""
        if not robots_allows(self.robots[p.hostname], url):
            raise Refused(f"robots.txt запрещает {url}")
        st, final, body = self._open(url)
        if urllib.parse.urlsplit(final).hostname not in self.ok:
            raise Refused(f"редирект вне политики: {final}")
        return st, final, body


def network_feed(site_id: str) -> dict:
    """Лента recipe-catalog/1 сайта сети по адресу из config/network.yaml (только петля в preview)."""
    cfg = yaml.safe_load((ROOT / "config" / "network.yaml").read_text())["sites"][site_id]
    url = cfg["catalog_feed"]
    p = urllib.parse.urlsplit(url)
    if p.hostname != "127.0.0.1" or p.path != "/api/catalog.v1.json":
        raise Refused(f"лента сайта сети вне контракта: {url}")
    with urllib.request.urlopen(url, timeout=10) as r:
        data = json.loads(r.read())
    if data.get("schema") != "recipe-catalog/1" or data.get("site_id") != site_id:
        raise Refused("лента не соответствует контракту recipe-catalog/1 или чужой site_id")
    return data
