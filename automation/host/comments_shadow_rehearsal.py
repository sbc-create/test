#!/usr/bin/env python3
"""Rehearse the whole animedia.icu pilot on a shadow contour, without root.

The Stage 1 deploy needs root for three things this session cannot do: install
a systemd unit, edit an nginx vhost and restart a service. What it does *not*
need root for is proof that the thing being deployed works. This script builds
the same three-part arrangement on spare loopback ports and runs the owner's
acceptance list against it end to end:

    router (mimics the nginx location split)
      ├── /api/comments/*  ->  the comments gateway
      └── everything else  ->  the Animedia site runtime with the adapter

The router exists because the widget and the API must share an origin, which
in production is nginx's job. It is a test fixture, 60 lines, and is never
installed anywhere.

Nothing here touches the live site, the live gateway, nginx, systemd, any
symlink or the production database. The shadow database is created in a
temporary directory and removed with it.

    python3 automation/host/comments_shadow_rehearsal.py --report out.json
"""

from __future__ import annotations

import argparse
import http.client
import json
import os
import pathlib
import secrets
import shutil
import signal
import socket
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit

REPO = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

RELEASE = pathlib.Path(
    "/srv/lords/.frontend/releases/20260922T071857Z-e84ee6e-animedia-comments-stage1"
)
MANIFEST = "/srv/lords/.frontend/template-manifest-animedia-01.json"
CATALOG = "/srv/lords/.frontend/animedia-01-catalog.json"
LEGACY = "/srv/lords/animedia-01/current/site"
API_PREFIX = "/api/comments/"


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class _Router(BaseHTTPRequestHandler):
    """What the nginx `location ^~ /api/comments/` split does in production."""

    site_port = 0
    gateway_port = 0

    def log_message(self, *a):
        pass

    def _proxy(self, port: int) -> None:
        body = b""
        length = int(self.headers.get("Content-Length") or 0)
        if length:
            body = self.rfile.read(length)

        conn = http.client.HTTPConnection("127.0.0.1", port, timeout=20)
        headers = {k: v for k, v in self.headers.items() if k.lower() != "host"}
        # `proxy_set_header Host $host` — the caller's Host, not a fixed one.
        # An earlier version hardcoded animedia.icu here and the tenant
        # isolation check passed for the wrong reason: a request sent with
        # Host: animedia.space reached the gateway relabelled as animedia.icu.
        # The fixture was lying, not the product.
        #
        # One translation remains, and only one. A caller that addressed the
        # loopback address named no site at all, and in production would have
        # arrived through the animedia.icu vhost. A browser cannot send a Host
        # it did not navigate to, so this is what lets Playwright drive the
        # contour. Any caller that *does* name a site keeps it, which is what
        # the tenant-isolation checks depend on.
        incoming = self.headers.get("Host", "")
        bare = incoming.split(":")[0]
        headers["Host"] = (
            "animedia.icu" if bare in ("127.0.0.1", "localhost", "::1", "") else incoming
        )
        headers["X-Real-IP"] = "127.0.0.1"
        try:
            conn.request(self.command, self.path, body=body or None, headers=headers)
            upstream = conn.getresponse()
            payload = upstream.read()
            self.send_response(upstream.status)
            for name, value in upstream.getheaders():
                if name.lower() in ("transfer-encoding", "content-length", "connection"):
                    continue
                self.send_header(name, value)
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            if self.command != "HEAD":
                self.wfile.write(payload)
        except Exception as exc:  # noqa: BLE001 — a fixture, not a product
            self.send_response(502)
            self.end_headers()
            self.wfile.write(str(exc).encode())
        finally:
            conn.close()

    def _dispatch(self):
        path = urlsplit(self.path).path
        self._proxy(self.gateway_port if path.startswith(API_PREFIX) else self.site_port)

    do_GET = do_POST = do_PATCH = do_DELETE = do_OPTIONS = do_HEAD = _dispatch


class Shadow:
    def __init__(self) -> None:
        self.tmp = pathlib.Path(tempfile.mkdtemp(prefix="comments-shadow-"))
        self.procs: list[subprocess.Popen] = []
        self.router: ThreadingHTTPServer | None = None
        self.site_port = free_port()
        self.gateway_port = free_port()
        self.router_port = free_port()
        self.base = f"http://127.0.0.1:{self.router_port}"

    # --- setup ---------------------------------------------------------

    def _keys(self) -> pathlib.Path:
        keys = self.tmp / "keys"
        keys.mkdir(mode=0o700)
        for purpose in ("subject", "network", "cohort"):
            (keys / f"animedia.{purpose}").write_text(secrets.token_hex(32))
        return keys

    def _database(self) -> pathlib.Path:
        from factory.comments_platform.store import CommentsStore
        from factory.comments_platform.tenancy import TenantScope

        db = self.tmp / "comments.sqlite"
        store = CommentsStore(db)
        store.create_schema()
        scope = TenantScope("animedia", "animedia-01")
        store.upsert_site(scope, module_version="0.1.0-mvp",
                          artifact_checksum="0" * 64, moderation_mode="pre")
        # Generous limits: the rehearsal makes many writes in seconds, and a
        # rate limit firing here would measure the fixture, not the product.
        store.upsert_policy(scope, policy_version="v1",
                            rate_per_minute=120, rate_per_hour=1200)
        store._conn.commit()
        store.close()
        return db

    def start(self) -> None:
        keys = self._keys()
        db = self._database()

        env = dict(os.environ)
        env.update({
            "PYTHONPATH": str(REPO),
            "LORDS_TEMPLATE_MANIFEST": MANIFEST,
            "LORDS_CATALOG": CATALOG,
            "LORDS_LEGACY_ROOT": LEGACY,
            "LORDS_SITE_NAME": "Animedia",
            "PYTHONDONTWRITEBYTECODE": "1",
            "ANIMEDIA_COMMENTS_MOUNT": "1",
        })

        self.procs.append(subprocess.Popen(
            [sys.executable, str(RELEASE / "animedia-frontend.py"),
             "--port", str(self.site_port)],
            cwd=str(RELEASE), env=env,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        ))
        self.procs.append(subprocess.Popen(
            [sys.executable, "-m", "factory.comments_platform.gateway",
             "--host", "127.0.0.1", "--port", str(self.gateway_port),
             "--store", str(db), "--config",
             str(REPO / "config" / "comments-platform" / "sites.json"),
             "--credentials", str(keys),
             "--artifact-checksum", "shadow"],
            cwd=str(REPO), env=env,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        ))

        handler = type("_Bound", (_Router,),
                       {"site_port": self.site_port, "gateway_port": self.gateway_port})
        self.router = ThreadingHTTPServer(("127.0.0.1", self.router_port), handler)
        import threading
        threading.Thread(target=self.router.serve_forever, daemon=True).start()

        self.keys = keys
        self.db = db
        self._wait_ready()

    def _wait_ready(self, timeout: float = 45.0) -> None:
        deadline = time.time() + timeout
        while time.time() < deadline:
            site = self.http("GET", "/")[0]
            api = self.http("GET", "/api/comments/v1/healthz")[0]
            if site == 200 and api == 200:
                return
            time.sleep(1)
        raise SystemExit("shadow contour did not come up")

    def stop(self) -> None:
        if self.router:
            self.router.shutdown()
            self.router.server_close()
        for proc in self.procs:
            proc.send_signal(signal.SIGTERM)
            try:
                proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                proc.kill()
        shutil.rmtree(self.tmp, ignore_errors=True)

    # --- helpers -------------------------------------------------------

    def http(self, method, path, body=None, cookies=None, headers=None):
        conn = http.client.HTTPConnection("127.0.0.1", self.router_port, timeout=20)
        hdrs = dict(headers or {})
        hdrs["Host"] = "animedia.icu"
        payload = None
        if body is not None:
            payload = json.dumps(body).encode()
            hdrs["Content-Type"] = "application/json"
        if cookies:
            hdrs["Cookie"] = "; ".join(f"{k}={v}" for k, v in cookies.items())
        try:
            conn.request(method, path, body=payload, headers=hdrs)
            response = conn.getresponse()
            raw = response.read()
            try:
                parsed = json.loads(raw)
            except ValueError:
                parsed = raw
            return response.status, parsed, dict(response.getheaders())
        except Exception:  # noqa: BLE001
            return 0, None, {}
        finally:
            conn.close()

    def owner_cookies(self):
        from factory.comments_platform import cohorts
        from factory.comments_platform.gateway import CredentialSecretResolver
        from factory.comments_platform.tenancy import TenantScope

        token = cohorts.issue_cohort_token(
            CredentialSecretResolver(self.keys),
            TenantScope("animedia", "animedia-01"),
            cohort=cohorts.OWNER_TEST, subject_id="owner", ttl_seconds=3600,
        )
        csrf = secrets.token_urlsafe(16)
        return ({cohorts.COHORT_COOKIE: token,
                 "cp_guest": "owner-shadow-" + "x" * 20,
                 "cp_csrf": csrf},
                {"X-CP-CSRF": csrf})

    def restart_gateway(self):
        """Prove comments survive a gateway restart, as the brief asks."""
        proc = self.procs[1]
        proc.send_signal(signal.SIGTERM)
        proc.wait(timeout=10)
        env = dict(os.environ)
        env.update({"PYTHONPATH": str(REPO), "PYTHONDONTWRITEBYTECODE": "1"})
        self.procs[1] = subprocess.Popen(
            [sys.executable, "-m", "factory.comments_platform.gateway",
             "--host", "127.0.0.1", "--port", str(self.gateway_port),
             "--store", str(self.db), "--config",
             str(REPO / "config" / "comments-platform" / "sites.json"),
             "--credentials", str(self.keys), "--artifact-checksum", "shadow"],
            cwd=str(REPO), env=env,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        deadline = time.time() + 30
        while time.time() < deadline:
            if self.http("GET", "/api/comments/v1/healthz")[0] == 200:
                return
            time.sleep(0.5)
        raise SystemExit("gateway did not come back after restart")


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", default="")
    parser.add_argument("--keep-up", action="store_true",
                        help="leave the contour running and print its base URL")
    args = parser.parse_args(argv)

    if not RELEASE.is_dir():
        raise SystemExit(f"prepared release missing: {RELEASE}")

    shadow = Shadow()
    shadow.start()
    print(f"shadow contour on {shadow.base}", file=sys.stderr)

    if args.keep_up:
        print(shadow.base)
        try:
            while True:
                time.sleep(3600)
        except KeyboardInterrupt:
            shadow.stop()
        return 0

    try:
        from importlib import import_module
        checks = import_module("automation.host.comments_shadow_checks")
        report = checks.run(shadow)
    finally:
        shadow.stop()

    report["generated_at_utc"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    if args.report:
        pathlib.Path(args.report).parent.mkdir(parents=True, exist_ok=True)
        pathlib.Path(args.report).write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    failed = [c for c in report["checks"] if not c["ok"]]
    for check in report["checks"]:
        print(f"  {'ok  ' if check['ok'] else 'FAIL'} {check['name']}: {check['detail']}")
    print(f"\n{len(report['checks']) - len(failed)}/{len(report['checks'])} checks passed")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
