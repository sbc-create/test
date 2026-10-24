"""Ограниченный HTTP-клиент для аудита и импорта.

Правила (ТЗ, этап 2Б):
* только GET, только https и только хосты из config/crawl.yaml И
  inventory/network-allowlist.yaml одновременно;
* каждый редирект проверяется заново; адрес, разрешающийся в петлю,
  частную сеть, link-local или metadata endpoint, отвергается;
* один запрос на хост одновременно, пауза между запросами, тайм-аут,
  ограниченные повторы, уважение Retry-After, предел размера ответа.
"""

from __future__ import annotations

import contextlib
import gzip
import hashlib
import ipaddress
import json
import socket
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]  # templates/food-daily
REPO = ROOT.parents[1]


class FetchRefused(RuntimeError):
    """Запрос не разрешён политикой — не сетевой сбой."""


@dataclass
class Response:
    url: str  # итоговый адрес после редиректов
    requested: str
    status: int | None
    headers: dict
    body: bytes
    redirects: list = field(default_factory=list)
    error: str | None = None
    from_cache: bool = False

    def text(self) -> str:
        ctype = self.headers.get("content-type", "")
        enc = "utf-8"
        if "charset=" in ctype:
            enc = ctype.split("charset=")[-1].split(";")[0].strip() or enc
        try:
            return self.body.decode(enc, errors="replace")
        except LookupError:
            return self.body.decode("utf-8", errors="replace")


def load_config() -> dict:
    return yaml.safe_load((ROOT / "config" / "crawl.yaml").read_text())


def allowed_hosts() -> set[str]:
    cfg = load_config()
    mine = set()
    for h in cfg["hosts"]:
        mine.add(urllib.parse.urlsplit(h["base"]).hostname)
        for a in h.get("aliases", []):
            mine.add(urllib.parse.urlsplit(a).hostname)
    inv = yaml.safe_load((REPO / "inventory" / "network-allowlist.yaml").read_text())
    inventory = {e["host"] for e in inv.get("hosts", []) if "GET" in e.get("methods", [])}
    return mine & inventory


def _public_address(host: str) -> None:
    try:
        infos = socket.getaddrinfo(host, 443, proto=socket.IPPROTO_TCP)
    except socket.gaierror as exc:
        raise FetchRefused(f"dns: {host}: {exc}") from exc
    for info in infos:
        ip = ipaddress.ip_address(info[4][0])
        if (
            ip.is_private
            or ip.is_loopback
            or ip.is_link_local
            or ip.is_reserved
            or ip.is_multicast
            or ip.is_unspecified
        ):
            raise FetchRefused(f"{host} разрешается в непубличный адрес {ip}")


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *a, **k):  # редиректы разбираем сами
        return None


class Client:
    def __init__(self, *, cache_dir: Path | None = None, config: dict | None = None):
        self.cfg = config or load_config()
        self.lim = self.cfg["limits"]
        self.allowed = allowed_hosts()
        self.cache_dir = cache_dir
        self._last: dict[str, float] = {}
        self._locks: dict[str, threading.Lock] = {}
        self._glock = threading.Lock()
        self._opener = urllib.request.build_opener(_NoRedirect)
        self.stats = {"requests": 0, "cache_hits": 0, "errors": 0}

    # -- политика -----------------------------------------------------
    def check(self, url: str) -> str:
        parts = urllib.parse.urlsplit(url)
        if parts.scheme != "https":
            raise FetchRefused(f"не https: {url}")
        host = (parts.hostname or "").lower()
        if host not in self.allowed:
            raise FetchRefused(f"хост вне allowlist: {host}")
        if parts.port not in (None, 443):
            raise FetchRefused(f"нестандартный порт: {url}")
        _public_address(host)
        return host

    def _lock(self, host: str) -> threading.Lock:
        with self._glock:
            return self._locks.setdefault(host, threading.Lock())

    def _cache_path(self, url: str) -> Path | None:
        if not self.cache_dir:
            return None
        key = hashlib.sha256(url.encode()).hexdigest()
        return self.cache_dir / key[:2] / key

    # -- запрос ---------------------------------------------------------
    def get(self, url: str, *, use_cache: bool = True, max_redirects: int = 5) -> Response:
        cp = self._cache_path(url)
        if use_cache and cp and cp.with_suffix(".json").exists():
            meta = json.loads(cp.with_suffix(".json").read_text())
            self.stats["cache_hits"] += 1
            body = gzip.decompress(cp.with_suffix(".body.gz").read_bytes())
            return Response(
                meta["url"],
                url,
                meta["status"],
                meta["headers"],
                body,
                meta["redirects"],
                meta.get("error"),
                True,
            )
        chain: list = []
        current = url
        for _ in range(max_redirects + 1):
            host = self.check(current)
            resp = self._fetch_once(host, current)
            if resp.status in (301, 302, 303, 307, 308) and "location" in resp.headers:
                nxt = urllib.parse.urljoin(current, resp.headers["location"])
                chain.append({"from": current, "to": nxt, "status": resp.status})
                current = nxt
                continue
            resp.requested, resp.redirects = url, chain
            if cp and resp.status is not None and resp.error is None:
                cp.parent.mkdir(parents=True, exist_ok=True)
                cp.with_suffix(".body.gz").write_bytes(gzip.compress(resp.body))
                cp.with_suffix(".json").write_text(
                    json.dumps(
                        {
                            "url": resp.url,
                            "status": resp.status,
                            "headers": resp.headers,
                            "redirects": chain,
                            "error": resp.error,
                            "fetched_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                        }
                    )
                )
            return resp
        return Response(current, url, None, {}, b"", chain, "too many redirects")

    def _fetch_once(self, host: str, url: str) -> Response:
        attempts = int(self.lim["max_attempts"])
        last_err = None
        for attempt in range(1, attempts + 1):
            with self._lock(host):
                wait = self._last.get(host, 0) + float(self.lim["min_delay_seconds"]) - time.monotonic()
                if wait > 0:
                    time.sleep(wait)
                req = urllib.request.Request(
                    url,
                    headers={
                        "User-Agent": self.cfg["user_agent"],
                        "Accept-Encoding": "gzip",
                        "Accept": "text/html,application/xml,text/xml,*/*;q=0.5",
                    },
                )
                self.stats["requests"] += 1
                try:
                    with self._opener.open(req, timeout=float(self.lim["timeout_seconds"])) as r:
                        status, headers, body = (
                            r.status,
                            {k.lower(): v for k, v in r.headers.items()},
                            self._read(r),
                        )
                except urllib.error.HTTPError as e:
                    status, headers = e.code, {k.lower(): v for k, v in (e.headers or {}).items()}
                    body = b""
                    with contextlib.suppress(Exception):  # тело ошибки не обязательно
                        body = self._read(e)
                except (urllib.error.URLError, TimeoutError, OSError, ValueError) as e:
                    self._last[host] = time.monotonic()
                    last_err = f"{type(e).__name__}: {e}"
                    self.stats["errors"] += 1
                    time.sleep(min(2**attempt, 30))
                    continue
                finally:
                    self._last[host] = time.monotonic()
            if headers.get("content-encoding") == "gzip" and body:
                with contextlib.suppress(OSError):
                    body = gzip.decompress(body)
            if status in (429, 503) and attempt < attempts:
                ra = headers.get("retry-after", "")
                delay = int(ra) if ra.isdigit() else 2**attempt * 5
                if delay > int(self.lim["max_retry_after_seconds"]):
                    return Response(url, url, status, headers, body, error=f"retry-after {delay}s exceeds limit")
                time.sleep(delay)
                continue
            if status is not None and 500 <= status < 600 and attempt < attempts:
                time.sleep(2**attempt)
                continue
            return Response(url, url, status, headers, body)
        return Response(url, url, None, {}, b"", error=last_err or "attempts exhausted")

    def _read(self, r) -> bytes:
        limit = int(self.lim["max_response_bytes"])
        data = r.read(limit + 1)
        if len(data) > limit:
            raise ValueError(f"ответ больше {limit} байт")
        return data
