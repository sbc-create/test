"""Loopback HTTP gateway for the shared comments module.

`api.py` is deliberately framework-free: it turns a `Request` into a
`Response` and knows nothing about sockets. This module is the thin layer that
gives it a socket, and it is kept separate for the same reason — the contract
is testable without a server, and the server is replaceable without touching
the contract.

Shape of the deployment, modelled on the community ratings gateway already
running on this host (`/etc/nginx/snippets/yummyani-community-ratings.conf`
plus a systemd unit): a Python process bound to **127.0.0.1 only**, reached
through nginx, which supplies the real `Host` header. Binding to loopback is
not a detail — the tenant is derived from `Host`, and a process reachable from
outside nginx would let a caller choose that header freely.

Two things this gateway serves beyond the API:

* `GET /api/comments/v1/assets/comments-widget.js` and `.css` — the pinned
  widget files. Serving them here rather than from each site's template means
  a tenant integrates by referencing two URLs, and an artifact update reaches
  every site without touching any template. The files are served with their
  sha256 in an `ETag`, so a stale copy is detectable.
* `GET /api/comments/v1/healthz` — liveness, with the artifact checksum and
  the flag state, so an operator can tell what is running without guessing.

Secrets never appear in this file. The per-tenant keys come from a directory
supplied by systemd `LoadCredential`, and the process refuses to start without
it rather than inventing keys that would silently orphan every pseudonym on
the next restart.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import pathlib
import sys
import threading
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import parse_qs, urlsplit

from . import MODULE_VERSION
from .api import API_PREFIX, CommentsApi, Request
from .cohorts import CohortResolver
from .flags import FlagResolver
from .identity import GuestIdentityProvider, IdentityResolver, SecretResolver
from .service import CommentsService
from .store import CommentsStore
from .tenancy import SiteRegistry

WIDGET_DIR = pathlib.Path(__file__).resolve().parent / "widget"
ASSET_PREFIX = f"{API_PREFIX}/assets/"

# The browser-side guest pseudonym. Random, not a device fingerprint.
GUEST_COOKIE = "cp_guest"
HEALTH_PATH = f"{API_PREFIX}/healthz"

ASSET_TYPES = {
    ".js": "text/javascript; charset=utf-8",
    ".css": "text/css; charset=utf-8",
}

# Bodies larger than this are refused before being read. A comment is at most
# a few kilobytes; anything approaching this is either a mistake or a probe.
MAX_BODY_BYTES = 64 * 1024

# How long a guest pseudonym lives in the browser. Long enough that an author
# can still edit or delete what they wrote yesterday, short enough that it is
# not a permanent identifier.
GUEST_COOKIE_MAX_AGE = 30 * 24 * 3600


class CredentialSecretResolver:
    """Per-tenant keys from a systemd credentials directory.

    One file per `<tenant>.<purpose>` slot, mode 0600, outside the repository.
    A missing key is a startup failure, not a generated placeholder: inventing
    one would rotate every pseudonym on the site without anyone noticing, and
    would make a restart look like a privacy incident.

    Keys are **hex text**, 64 characters, created with `openssl rand -hex 32`.
    The first version of this read raw bytes and stripped whitespace, which is
    a quiet trap: random 32-byte material begins or ends with an ASCII
    whitespace byte roughly one time in thirty, and `.strip()` then shortened
    the key below the length check. The service started for some keys and
    refused others — the worst kind of intermittent. Hex contains no such byte,
    and an operator can create it with one obvious command.
    """

    KEY_BYTES = 32

    def __init__(self, directory: str | pathlib.Path) -> None:
        self._dir = pathlib.Path(directory)
        if not self._dir.is_dir():
            raise SystemExit(f"credentials directory not found: {self._dir}")
        self._cache: dict[str, bytes] = {}

    def tenant_key(self, tenant_id: str, purpose: str) -> bytes:
        slot = f"{tenant_id}.{purpose}"
        if slot in self._cache:
            return self._cache[slot]
        path = self._dir / slot
        try:
            text = path.read_text(encoding="ascii").strip()
        except OSError as exc:
            raise SystemExit(
                f"missing credential {slot}: {exc}. Keys are supplied through "
                "systemd LoadCredential and are never generated here."
            ) from exc
        except UnicodeDecodeError as exc:
            raise SystemExit(
                f"credential {slot} is not hex text; create it with `openssl rand -hex 32`"
            ) from exc

        try:
            key = bytes.fromhex(text)
        except ValueError as exc:
            raise SystemExit(
                f"credential {slot} is not valid hex; create it with `openssl rand -hex 32`"
            ) from exc
        if len(key) < self.KEY_BYTES:
            raise SystemExit(
                f"credential {slot} decodes to {len(key)} bytes; "
                f"{self.KEY_BYTES} or more are required"
            )
        self._cache[slot] = key
        return key


def _asset_bytes(name: str) -> tuple[bytes, str, str] | None:
    """Return (body, content type, sha256) for a pinned widget file."""
    if "/" in name or "\\" in name or name.startswith("."):
        return None
    path = WIDGET_DIR / name
    if path.suffix not in ASSET_TYPES or not path.is_file():
        return None
    body = path.read_bytes()
    return body, ASSET_TYPES[path.suffix], hashlib.sha256(body).hexdigest()


class _Handler(BaseHTTPRequestHandler):
    server_version = "comments-gateway"
    sys_version = ""

    # Injected by build_server.
    api: CommentsApi
    cohorts: CohortResolver
    registry: SiteRegistry
    flags: FlagResolver
    artifact_checksum: str
    db_lock: threading.RLock

    def log_message(self, fmt: str, *args: Any) -> None:
        """Access logging without request bodies, cookies or query strings.

        The default handler logs the full request line, which would put a
        cohort cookie's neighbours and any query string into the journal. Only
        method, path and status are recorded here; the path is truncated and
        its query removed.
        """
        try:
            path = urlsplit(self.path).path[:120]
        except ValueError:
            path = "<unparsable>"
        sys.stderr.write(f"{self.command} {path} {args[1] if len(args) > 1 else ''}\n")

    # --- plumbing -------------------------------------------------------

    def _read_body(self) -> dict[str, Any] | None:
        length = int(self.headers.get("Content-Length") or 0)
        if length <= 0:
            return None
        if length > MAX_BODY_BYTES:
            return {"__oversized__": True}
        raw = self.rfile.read(length)
        try:
            parsed = json.loads(raw.decode("utf-8"))
        except (ValueError, UnicodeDecodeError):
            return {"__malformed__": True}
        return parsed if isinstance(parsed, dict) else {"__malformed__": True}

    def _cookies(self) -> dict[str, str]:
        jar = SimpleCookie()
        try:
            jar.load(self.headers.get("Cookie", "") or "")
        except Exception:  # noqa: BLE001 — a malformed cookie header is not fatal
            return {}
        return {k: v.value for k, v in jar.items()}

    def _send(self, status: int, body: bytes, headers: dict[str, str]) -> None:
        self.send_response(status)
        for name, value in headers.items():
            self.send_header(name, value)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def _json(self, status: int, payload: dict[str, Any], headers: dict[str, str]) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        headers = dict(headers)
        headers.setdefault("Content-Type", "application/json; charset=utf-8")
        self._send(status, body, headers)

    # --- routes ---------------------------------------------------------

    def _handle(self) -> None:
        split = urlsplit(self.path)
        path = split.path
        query = {k: v[0] for k, v in parse_qs(split.query).items()}
        host = self.headers.get("Host", "")

        if path == HEALTH_PATH:
            return self._health(host)

        if path.startswith(ASSET_PREFIX) and self.command in ("GET", "HEAD"):
            return self._asset(path[len(ASSET_PREFIX):])

        body = self._read_body() if self.command in ("POST", "PUT", "PATCH") else None
        if isinstance(body, dict) and body.get("__oversized__"):
            return self._json(
                413,
                {"error": {"code": "BadRequest", "message": "request body is too large",
                           "request_id": self.headers.get("X-Request-Id", "")}},
                {},
            )
        if isinstance(body, dict) and body.get("__malformed__"):
            return self._json(
                400,
                {"error": {"code": "BadRequest", "message": "request is not valid",
                           "request_id": self.headers.get("X-Request-Id", "")}},
                {},
            )

        cookies = self._cookies()

        # A first-time visitor has no guest cookie, and the identity layer
        # rightly refuses an empty one. Minting it here rather than failing is
        # both correct and ordering-sensitive: without it the caller received
        # "your guest token is invalid" *before* the feature gate could say
        # "comments are not enabled", which is both confusing and a small
        # disclosure — the shape of the error told a visitor that something
        # was there to be refused.
        issued_guest = ""
        if not cookies.get(GUEST_COOKIE):
            issued_guest = GuestIdentityProvider.issue_guest_token()
            cookies[GUEST_COOKIE] = issued_guest

        request = Request(
            method=self.command,
            path=path,
            host=host,
            headers=dict(self.headers.items()),
            query=query,
            body=body,
            cookies=cookies,
            # nginx supplies this; it reaches only the rotating HMAC and is
            # never stored, logged or returned.
            remote_addr=self.headers.get("X-Real-IP", "") or "",
        )

        # The cohort is resolved here rather than inside the API so that a
        # deployment without this gateway cannot accidentally default to the
        # permissive answer: `api.py` has no notion of cohorts at all, and the
        # service treats a missing cohort as public.
        try:
            binding = self.registry.resolve_host(host)
            membership = self.cohorts.resolve(
                binding.scope, {"cookies": cookies, "query": query, "body": body or {}}
            )
            cohort = membership.cohort
        except Exception:  # noqa: BLE001 — an unknown host is answered by the API itself
            cohort = "public"

        # One database connection, one transaction at a time. The server stays
        # threaded so that asset and health requests never queue behind a
        # write, but everything that touches SQLite is serialised: the first
        # version of this gateway shared a connection across handler threads
        # and produced "SQLite objects created in a thread can only be used in
        # that same thread" under the owner scenario's second request.
        #
        # This caps write throughput at one request at a time, which is
        # correct for a single-owner pilot and is the honest limit to state
        # before any wider rollout.
        with self.db_lock:
            response = self.api.handle(request, cohort=cohort)

        headers = dict(response.headers)
        if issued_guest:
            # HttpOnly: the widget never needs to read it, and script access
            # would put a stable pseudonym within reach of any injected code.
            headers["Set-Cookie"] = (
                f"{GUEST_COOKIE}={issued_guest}; Path=/; Max-Age={GUEST_COOKIE_MAX_AGE}; "
                "HttpOnly; Secure; SameSite=Lax"
            )
        self._json(response.status, response.body, headers)

    def _asset(self, name: str) -> None:
        found = _asset_bytes(name)
        if found is None:
            return self._json(404, {"error": {"code": "NotFound", "message": "not found",
                                              "request_id": ""}}, {})
        body, content_type, digest = found
        if self.headers.get("If-None-Match") == f'"{digest}"':
            return self._send(304, b"", {"ETag": f'"{digest}"'})
        self._send(
            200,
            body,
            {
                "Content-Type": content_type,
                "ETag": f'"{digest}"',
                # Short cache: the pilot may repin the artifact, and a day-long
                # cache would leave the owner testing yesterday's widget.
                "Cache-Control": "public, max-age=300",
                "X-Robots-Tag": "noindex, nofollow",
                "X-Comments-Module-Version": MODULE_VERSION,
            },
        )

    def _health(self, host: str) -> None:
        """Liveness plus what is actually running. No secrets, no counts."""
        payload: dict[str, Any] = {
            "status": "ok",
            "module_version": MODULE_VERSION,
            "artifact_checksum": self.artifact_checksum,
            "sites": len(self.registry.all_bindings()),
        }
        try:
            binding = self.registry.resolve_host(host)
            payload["site"] = {
                "site_id": binding.site_id,
                "public": self.flags.resolve_for_cohort(binding, "public").as_dict(),
                "owner_test": self.flags.resolve_for_cohort(binding, "owner_test").as_dict(),
            }
        except Exception:  # noqa: BLE001 — health must answer even for an unknown Host
            payload["site"] = None
        self._json(200, payload, {"Cache-Control": "no-store"})

    def do_GET(self) -> None:  # noqa: N802 — BaseHTTPRequestHandler's contract
        self._handle()

    do_HEAD = do_GET
    do_POST = do_GET
    do_PATCH = do_GET
    do_DELETE = do_GET
    do_OPTIONS = do_GET


def build_server(
    *,
    host: str,
    port: int,
    store_path: str,
    config_path: str,
    secrets: SecretResolver,
    artifact_checksum: str = "",
) -> ThreadingHTTPServer:
    registry = SiteRegistry.from_file(config_path)
    store = CommentsStore(store_path, allow_cross_thread=True)
    flags = FlagResolver()
    service = CommentsService(store, registry, flags=flags, artifact_hash=artifact_checksum)
    api = CommentsApi(service, registry, IdentityResolver(secrets, None))

    handler = type(
        "_BoundHandler",
        (_Handler,),
        {
            "api": api,
            "cohorts": CohortResolver(secrets),
            "registry": registry,
            "flags": flags,
            "artifact_checksum": artifact_checksum,
            "db_lock": threading.RLock(),
        },
    )
    return ThreadingHTTPServer((host, port), handler)


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=9150)
    parser.add_argument("--store", default=os.environ.get("COMMENTS_DB", ""))
    parser.add_argument("--config", default=os.environ.get("COMMENTS_SITES_CONFIG", ""))
    parser.add_argument(
        "--credentials",
        default=os.environ.get("CREDENTIALS_DIRECTORY", ""),
        help="systemd LoadCredential directory holding <tenant>.<purpose> key files",
    )
    parser.add_argument("--artifact-checksum", default="")
    args = parser.parse_args(argv)

    if args.host not in ("127.0.0.1", "::1", "localhost"):
        # The tenant is derived from the Host header, which nginx sets. A
        # process reachable from outside would let a caller choose it.
        raise SystemExit(
            f"refusing to bind to {args.host}: this gateway is loopback only"
        )
    if not args.store or not args.config:
        raise SystemExit("--store and --config are required")
    if not args.credentials:
        raise SystemExit(
            "--credentials (or CREDENTIALS_DIRECTORY) is required; keys are never generated here"
        )

    server = build_server(
        host=args.host,
        port=args.port,
        store_path=args.store,
        config_path=args.config,
        secrets=CredentialSecretResolver(args.credentials),
        artifact_checksum=args.artifact_checksum,
    )
    sys.stderr.write(f"comments gateway on {args.host}:{args.port}\n")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
