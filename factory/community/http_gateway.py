"""Loopback HTTP gateway for Yummy community ratings public API.

Binds 127.0.0.1 only. nginx/yummy-frontend proxies /api/community/ratings/*.
"""

from __future__ import annotations

import json
import os
import re
import sys
import traceback
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import parse_qs, urlparse

from factory.community.api import CSRF_COOKIE, MAX_BODY_BYTES, PublicRatingsFacade
from factory.community.identity_v1 import COOKIE_NAME, set_cookie_header
from factory.community.metrics import snapshot
from factory.community.rollout import as_public_dict, load_flags
from factory.community.service import CommunityVotesService
from factory.community.store import CommunityStore
from factory.ratings.prod_db import resolve_canonical_db

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = int(os.environ.get("COMMUNITY_RATINGS_HTTP_PORT", "9145"))

_SUBJECT_RE = re.compile(r"^/api/community/ratings/(?:titles|subjects)/([^/]+)(?:/(preview|vote))?$")
_SESSION_RE = re.compile(r"^/api/community/ratings/session$")
_HEALTH_RE = re.compile(r"^/api/community/ratings/(?:health|metrics)$")
_FLAGS_RE = re.compile(r"^/api/community/ratings/flags$")


def _strip_internal(payload: dict[str, Any]) -> tuple[dict[str, Any], list[tuple[str, str]]]:
    headers: list[tuple[str, str]] = []
    out = dict(payload)
    set_id = out.pop("_set_identity_cookie", None)
    set_csrf = out.pop("_set_csrf", None)
    out.pop("_identity_id", None)
    if set_id:
        headers.append(("Set-Cookie", set_cookie_header(set_id)))
    if set_csrf:
        headers.append(
            (
                "Set-Cookie",
                f"{CSRF_COOKIE}={set_csrf}; Max-Age=86400; Secure; HttpOnly; SameSite=Lax; Path=/",
            )
        )
    cc = out.pop("cache_control", None) or "no-store"
    headers.append(("Cache-Control", cc))
    headers.append(("X-Content-Type-Options", "nosniff"))
    return out, headers


class CommunityRatingsHandler(BaseHTTPRequestHandler):
    facade: PublicRatingsFacade

    def log_message(self, fmt: str, *args: Any) -> None:  # noqa: A003
        sys.stderr.write("[community-ratings] " + (fmt % args) + "\n")

    def _read_json(self) -> tuple[dict[str, Any] | None, int, str | None]:
        length = int(self.headers.get("Content-Length") or 0)
        if length > MAX_BODY_BYTES:
            return None, length, "too large"
        raw = self.rfile.read(length) if length else b""
        if not raw:
            return {}, length, None
        try:
            data = json.loads(raw.decode("utf-8"))
        except Exception:
            return None, length, "invalid json"
        if not isinstance(data, dict):
            return None, length, "body must be object"
        return data, length, None

    def _cookie(self) -> str | None:
        return self.headers.get("Cookie")

    def _csrf_cookie(self) -> str | None:
        raw = self._cookie() or ""
        for part in raw.split(";"):
            part = part.strip()
            if part.startswith(CSRF_COOKIE + "="):
                return part.split("=", 1)[1]
        return None

    def _peer_ip(self) -> str:
        # Socket peer. When nginx proxies from loopback, accept X-Real-IP only
        # for peppered network bucket — never as identity.
        peer = self.client_address[0] if self.client_address else ""
        if peer in ("127.0.0.1", "::1"):
            xri = (self.headers.get("X-Real-IP") or "").strip()
            if xri and "," not in xri:
                return xri
        return peer

    def _send(self, status: int, payload: dict[str, Any]) -> None:
        body, extra = _strip_internal(payload)
        raw = json.dumps(body, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        for k, v in extra:
            self.send_header(k, v)
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(raw)

    def do_GET(self) -> None:  # noqa: N802
        path = urlparse(self.path).path
        if _HEALTH_RE.match(path):
            flags = load_flags()
            return self._send(
                200,
                {
                    "status": 200,
                    "ok": True,
                    "metrics": snapshot(
                        kill_switch_state=int(flags.KILL_SWITCH),
                        rollout_percent=int(flags.PUBLIC_WRITE_ROLLOUT_PERCENT),
                    ),
                    "flags": as_public_dict(flags),
                },
            )
        if _FLAGS_RE.match(path):
            return self._send(200, {"status": 200, "flags": as_public_dict()})
        if _SESSION_RE.match(path):
            return self._send(200, self.facade.session_bootstrap(cookie_header=self._cookie()))
        m = _SUBJECT_RE.match(path)
        if m and not m.group(2):
            subject = m.group(1)
            return self._send(
                200,
                self.facade.get_public(subject_id=subject, cookie_header=self._cookie()),
            )
        return self._send(404, {"status": 404, "error": "not found"})

    def do_POST(self) -> None:  # noqa: N802
        path = urlparse(self.path).path
        body, length, err = self._read_json()
        if err:
            return self._send(400, {"status": 400, "error": err})
        m = _SUBJECT_RE.match(path)
        if m and m.group(2) == "preview":
            score = (body or {}).get("score", (body or {}).get("rating"))
            out = self.facade.preview(
                subject_id=m.group(1),
                score=score,
                cookie_header=self._cookie(),
            )
            return self._send(int(out.get("status") or 200), out)
        if m and m.group(2) == "vote":
            # POST vote with action=retract OR cast
            action = (body or {}).get("action") or "cast"
            method = "DELETE" if action == "retract" else "PUT"
            out = self.facade.mutate(
                method=method,
                subject_id=m.group(1),
                body=body,
                cookie_header=self._cookie(),
                origin=self.headers.get("Origin"),
                csrf_header=self.headers.get("X-CSRF-Token"),
                csrf_cookie=self._csrf_cookie(),
                idempotency_key=self.headers.get("Idempotency-Key") or "",
                content_type=self.headers.get("Content-Type"),
                peer_ip=self._peer_ip(),
                body_len=length,
            )
            return self._send(int(out.get("status") or 200), out)
        return self._send(404, {"status": 404, "error": "not found"})

    def do_PUT(self) -> None:  # noqa: N802
        path = urlparse(self.path).path
        body, length, err = self._read_json()
        if err:
            return self._send(400, {"status": 400, "error": err})
        m = _SUBJECT_RE.match(path)
        if not m or m.group(2) != "vote":
            return self._send(404, {"status": 404, "error": "not found"})
        out = self.facade.mutate(
            method="PUT",
            subject_id=m.group(1),
            body=body,
            cookie_header=self._cookie(),
            origin=self.headers.get("Origin"),
            csrf_header=self.headers.get("X-CSRF-Token"),
            csrf_cookie=self._csrf_cookie(),
            idempotency_key=self.headers.get("Idempotency-Key") or "",
            content_type=self.headers.get("Content-Type"),
            peer_ip=self._peer_ip(),
            body_len=length,
        )
        return self._send(int(out.get("status") or 200), out)

    def do_DELETE(self) -> None:  # noqa: N802
        path = urlparse(self.path).path
        body, length, err = self._read_json()
        if err and length:
            return self._send(400, {"status": 400, "error": err})
        m = _SUBJECT_RE.match(path)
        if not m or m.group(2) != "vote":
            return self._send(404, {"status": 404, "error": "not found"})
        out = self.facade.mutate(
            method="DELETE",
            subject_id=m.group(1),
            body=body or {},
            cookie_header=self._cookie(),
            origin=self.headers.get("Origin"),
            csrf_header=self.headers.get("X-CSRF-Token"),
            csrf_cookie=self._csrf_cookie(),
            idempotency_key=self.headers.get("Idempotency-Key") or "",
            content_type=self.headers.get("Content-Type") or "application/json",
            peer_ip=self._peer_ip(),
            body_len=length,
        )
        return self._send(int(out.get("status") or 200), out)

    def do_OPTIONS(self) -> None:  # noqa: N802
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "https://yummyani.site")
        self.send_header("Access-Control-Allow-Methods", "GET,POST,PUT,DELETE,OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type,Idempotency-Key,X-CSRF-Token")
        self.send_header("Access-Control-Allow-Credentials", "true")
        self.send_header("Content-Length", "0")
        self.end_headers()


def build_facade(db_path: str | None = None) -> PublicRatingsFacade:
    store = CommunityStore(db_path or resolve_canonical_db())
    return PublicRatingsFacade(CommunityVotesService(store))


def serve(host: str = DEFAULT_HOST, port: int = DEFAULT_PORT, db_path: str | None = None) -> None:
    facade = build_facade(db_path)
    handler = type("Handler", (CommunityRatingsHandler,), {"facade": facade})
    httpd = ThreadingHTTPServer((host, port), handler)
    sys.stderr.write(f"[community-ratings] listening on http://{host}:{port}\n")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        httpd.server_close()


def main(argv: list[str] | None = None) -> int:
    argv = list(argv or sys.argv[1:])
    host = DEFAULT_HOST
    port = DEFAULT_PORT
    db = None
    i = 0
    while i < len(argv):
        if argv[i] == "--host":
            host = argv[i + 1]
            i += 2
        elif argv[i] == "--port":
            port = int(argv[i + 1])
            i += 2
        elif argv[i] == "--db":
            db = argv[i + 1]
            i += 2
        else:
            i += 1
    try:
        serve(host=host, port=port, db_path=db)
        return 0
    except Exception:
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
