"""Сетевой доступ food-baking: только чтение, только разрешённые хосты.

* https + хост из inventory/network-allowlist.yaml (метод GET) и из
  config/sources.yaml шаблона одновременно;
* каждый редирект проверяется заново; петля, частные сети, link-local и
  metadata запрещены;
* robots.txt по RFC 9309 (`*`, `$`, самое длинное совпадение, Allow при равенстве);
* один запрос на хост, пауза, ограниченные повторы, предел размера ответа.
"""

from __future__ import annotations

import gzip
import ipaddress
import re
import socket
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parents[1]
UA = "food-baking-audit/1.0 (site-factory reference audit; respects robots.txt)"
MAX_BYTES = 20 * 1024 * 1024


class Refused(RuntimeError):
    pass


@dataclass
class Page:
    url: str
    status: int | None
    body: bytes
    headers: dict = field(default_factory=dict)
    redirects: list = field(default_factory=list)

    @property
    def text(self) -> str:
        return self.body.decode("utf-8", "replace")


def allowed_hosts() -> set[str]:
    mine = {s["host"] for s in yaml.safe_load((ROOT / "config" / "sources.yaml").read_text())["sources"]}
    inv = yaml.safe_load((REPO / "inventory" / "network-allowlist.yaml").read_text())
    return mine & {e["host"] for e in inv["hosts"] if "GET" in e.get("methods", [])}


def _robot_rx(pattern: str) -> re.Pattern:
    end = pattern.endswith("$")
    body = "".join(".*" if c == "*" else re.escape(c) for c in pattern.rstrip("$"))
    return re.compile(body + ("$" if end else ""))


class Robots:
    def __init__(self, text: str):
        groups, agents, rules, in_rules = [], [], [], False
        for raw in text.splitlines():
            line = raw.split("#", 1)[0].strip()
            if ":" not in line:
                continue
            k, v = (x.strip() for x in line.split(":", 1))
            k = k.lower()
            if k == "user-agent":
                if in_rules:
                    groups.append((agents, rules))
                    agents, rules, in_rules = [], [], False
                agents.append(v.lower())
            elif k in ("allow", "disallow"):
                in_rules = True
                if v:
                    rules.append((k == "allow", len(v), _robot_rx(v if v.startswith(("/", "*")) else "/" + v)))
        if agents:
            groups.append((agents, rules))
        token = UA.split("/")[0].lower()
        mine = [r for a, rs in groups if any(x != "*" and x in token for x in a) for r in rs]
        self.rules = mine or [r for a, rs in groups if "*" in a for r in rs]

    def allows(self, url: str) -> bool:
        p = urllib.parse.urlsplit(url)
        path = (p.path or "/") + (("?" + p.query) if p.query else "")
        best, ok = -1, True
        for allow, n, rx in self.rules:
            if rx.match(path) and (n > best or (n == best and allow)):
                best, ok = n, allow
        return ok


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *a, **k):
        return None


class Client:
    def __init__(self, delay: float = 2.0):
        self.allowed = allowed_hosts()
        self.delay = delay
        self.last: dict[str, float] = {}
        self.robots: dict[str, Robots] = {}
        self.opener = urllib.request.build_opener(_NoRedirect)
        self.requests = 0

    def _check(self, url: str) -> str:
        p = urllib.parse.urlsplit(url)
        host = (p.hostname or "").lower()
        if p.scheme != "https" or host not in self.allowed or p.port not in (None, 443):
            raise Refused(f"вне политики: {url}")
        for info in socket.getaddrinfo(host, 443, proto=socket.IPPROTO_TCP):
            ip = ipaddress.ip_address(info[4][0])
            if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast:
                raise Refused(f"{host} → непубличный адрес {ip}")
        return host

    def _raw(self, host: str, url: str) -> Page:
        wait = self.last.get(host, 0) + self.delay - time.monotonic()
        if wait > 0:
            time.sleep(wait)
        req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Encoding": "gzip"})
        self.requests += 1
        try:
            with self.opener.open(req, timeout=30) as r:
                status, headers, body = r.status, {k.lower(): v for k, v in r.headers.items()}, r.read(MAX_BYTES + 1)
        except urllib.error.HTTPError as e:
            status, headers, body = e.code, {k.lower(): v for k, v in (e.headers or {}).items()}, b""
        finally:
            self.last[host] = time.monotonic()
        if len(body) > MAX_BYTES:
            raise Refused(f"ответ больше {MAX_BYTES} байт: {url}")
        if headers.get("content-encoding") == "gzip" and body:
            body = gzip.decompress(body)
        return Page(url, status, body, headers)

    def robots_for(self, host: str) -> Robots:
        if host not in self.robots:
            pg = self._raw(host, f"https://{host}/robots.txt")
            self.robots[host] = Robots(pg.text if pg.status == 200 else "")
        return self.robots[host]

    def get(self, url: str) -> Page:
        chain = []
        for _ in range(6):
            host = self._check(url)
            if not self.robots_for(host).allows(url):
                raise Refused(f"robots.txt запрещает {url}")
            pg = self._raw(host, url)
            if pg.status in (301, 302, 303, 307, 308) and "location" in pg.headers:
                nxt = urllib.parse.urljoin(url, pg.headers["location"])
                chain.append((url, pg.status, nxt))
                url = nxt
                continue
            pg.redirects = chain
            return pg
        raise Refused("слишком много редиректов")
