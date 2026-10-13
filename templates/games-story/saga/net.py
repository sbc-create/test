"""Сеть games-story: GET к хостам из inventory/network-allowlist.yaml и
config/sources.yaml одновременно; robots.txt (RFC 9309); пауза на хост;
проверка адресов и редиректов; предел размера ответа."""

from __future__ import annotations

import gzip
import ipaddress
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
UA = "games-story-audit/1.0 (site-factory reference audit; respects robots.txt)"
LIMIT = 30 * 1024 * 1024


class Refused(RuntimeError):
    pass


def allowed() -> set[str]:
    inv = yaml.safe_load((REPO / "inventory" / "network-allowlist.yaml").read_text())
    mine = {s["host"] for s in yaml.safe_load((ROOT / "config" / "sources.yaml").read_text())["sources"]}
    return mine & {e["host"] for e in inv["hosts"] if "GET" in e.get("methods", [])}


def robots_rules(text: str) -> list:
    groups, agents, rules, in_rules = [], [], [], False
    for raw in text.splitlines():
        line = raw.split("#", 1)[0].strip()
        if ":" not in line:
            continue
        k, v = (x.strip() for x in line.split(":", 1))
        if k.lower() == "user-agent":
            if in_rules:
                groups.append((agents, rules))
                agents, rules, in_rules = [], [], False
            agents.append(v.lower())
        elif k.lower() in ("allow", "disallow"):
            in_rules = True
            if v:
                rx = "".join(".*" if c == "*" else re.escape(c) for c in v.rstrip("$")) + (
                    "$" if v.endswith("$") else ""
                )
                rules.append((k.lower() == "allow", len(v), re.compile(rx)))
    if agents:
        groups.append((agents, rules))
    token = UA.split("/")[0]
    mine = [r for a, rs in groups if any(x != "*" and x in token for x in a) for r in rs]
    return mine or [r for a, rs in groups if "*" in a for r in rs]


def robots_allow(rules: list, url: str) -> bool:
    p = urllib.parse.urlsplit(url)
    path = (p.path or "/") + (f"?{p.query}" if p.query else "")
    best, ok = -1, True
    for allow, n, rx in rules:
        if rx.match(path) and (n > best or (n == best and allow)):
            best, ok = n, allow
    return ok


class Client:
    def __init__(self, delay: float = 2.0):
        self.ok, self.delay = allowed(), delay
        self.last: dict[str, float] = {}
        self.rules: dict[str, list] = {}
        self.requests = 0

    def _check(self, url: str) -> str:
        p = urllib.parse.urlsplit(url)
        if p.scheme != "https" or p.hostname not in self.ok or p.port not in (None, 443):
            raise Refused(f"вне политики: {url}")
        for info in socket.getaddrinfo(p.hostname, 443):
            ip = ipaddress.ip_address(info[4][0])
            if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast:
                raise Refused(f"непубличный адрес {ip}")
        return p.hostname

    def _raw(self, host: str, url: str) -> tuple[int | None, bytes, dict]:
        wait = self.last.get(host, 0) + self.delay - time.monotonic()
        if wait > 0:
            time.sleep(wait)
        self.requests += 1

        class NoRedirect(urllib.request.HTTPRedirectHandler):
            def redirect_request(self, *a, **k):
                return None

        op = urllib.request.build_opener(NoRedirect)
        try:
            with op.open(
                urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Encoding": "gzip"}), timeout=30
            ) as r:
                st, body, hd = r.status, r.read(LIMIT + 1), {k.lower(): v for k, v in r.headers.items()}
        except urllib.error.HTTPError as e:
            st, body, hd = e.code, b"", {k.lower(): v for k, v in (e.headers or {}).items()}
        finally:
            self.last[host] = time.monotonic()
        if len(body) > LIMIT:
            raise Refused("ответ слишком большой")
        if hd.get("content-encoding") == "gzip" and body:
            body = gzip.decompress(body)
        return st, body, hd

    def get(self, url: str) -> tuple[int | None, str, bytes]:
        for _ in range(6):
            host = self._check(url)
            if host not in self.rules:
                st, body, _ = self._raw(host, f"https://{host}/robots.txt")
                self.rules[host] = robots_rules(body.decode("utf-8", "replace") if st == 200 else "")
            if not robots_allow(self.rules[host], url):
                raise Refused(f"robots.txt запрещает {url}")
            st, body, hd = self._raw(host, url)
            if st in (301, 302, 303, 307, 308) and "location" in hd:
                url = urllib.parse.urljoin(url, hd["location"])
                continue
            return st, url, body
        raise Refused("слишком много редиректов")
