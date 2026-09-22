"""Публичный API единого модуля оценок для витрины.

Слушает только loopback; наружу его проксирует nginx витрины. Три
действия: узнать свою оценку, поставить или изменить её, отозвать.

Разделение чтения и записи здесь не косметическое. Чтение открыто всем
посетителям, запись — только когорте: первый этап раскатки показывает
внешние оценки публично, а голосование держит закрытым. Поэтому у флагов
чтения и записи отдельные значения, и включение одного не включает
другое.

Сервер не доверяет интерфейсу ни в чём: оценка проверяется до записи,
``title_id`` определяется по паре (площадка, subject) из карты витрины,
а ``space`` сверяется с Origin. Клиент, приславший чужую площадку, не
получит доступ к её оценкам — он получит отказ.
"""

from __future__ import annotations

import json
import os
import re
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import parse_qs, urlparse

from factory.community.antifraud import (
    AntifraudGuard,
    KillSwitchActive,
    OriginRejected,
    RateLimited,
    ReadOnlyMode,
)
from factory.unified_ratings.community import CommunityRatings, UnknownSubject, VoteRejected
from factory.unified_ratings.site_projection import build_flags  # noqa: F401  (контракт флагов)

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = int(os.environ.get("UNIFIED_RATINGS_HTTP_PORT", "9147"))

MAX_BODY_BYTES = 4096
CSRF_HEADER = "X-CSRF-Token"
CSRF_COOKIE = "ur_csrf"
IDEMPOTENCY_HEADER = "Idempotency-Key"

#: Площадка → разрешённые Origin. Площадка из запроса обязана совпасть.
SPACE_ORIGINS: dict[str, tuple[str, ...]] = {
    "animedia": ("https://animedia.icu", "http://animedia.icu"),
}

_ME_RE = re.compile(r"^/api/unified-ratings/me$")
_VOTE_RE = re.compile(r"^/api/unified-ratings/vote$")
_HEALTH_RE = re.compile(r"^/api/unified-ratings/health$")


class ApiError(Exception):
    def __init__(self, status: int, code: str, message: str) -> None:
        super().__init__(message)
        self.status = status
        self.code = code
        self.message = message


class UnifiedRatingsApi:
    """Логика API без HTTP: её можно вызвать из теста напрямую."""

    def __init__(
        self,
        community: CommunityRatings,
        *,
        guard: AntifraudGuard | None = None,
        write_cohort: set[str] | None = None,
        public_write: bool = False,
    ) -> None:
        self.community = community
        self.guard = guard or AntifraudGuard()
        #: кто может голосовать, пока публичная запись выключена
        self.write_cohort = write_cohort or set()
        self.public_write = public_write

    # ------------------------------------------------------------------

    def _check_space(self, space: str, origin: str | None) -> None:
        allowed = SPACE_ORIGINS.get(space)
        if allowed is None:
            raise ApiError(404, "UNKNOWN_SPACE", f"площадка не обслуживается: {space}")
        if origin and origin not in allowed:
            raise ApiError(
                403, "ORIGIN_MISMATCH",
                f"Origin {origin} не принадлежит площадке {space}",
            )

    def _check_write_allowed(self, actor_id: str) -> None:
        """Запись открыта когорте, а не всем, пока владелец не решил иначе."""
        try:
            self.guard.assert_writable()
        except KillSwitchActive as exc:
            raise ApiError(503, "KILL_SWITCH", str(exc)) from None
        except ReadOnlyMode as exc:
            raise ApiError(503, "READ_ONLY", str(exc)) from None
        if self.public_write:
            return
        if actor_id not in self.write_cohort:
            raise ApiError(
                403, "NOT_IN_TEST_COHORT",
                "публичное голосование ещё не включено; доступ есть у тестовой когорты",
            )

    @staticmethod
    def _check_csrf(header_token: str | None, cookie_token: str | None) -> None:
        if not header_token or not cookie_token or header_token != cookie_token:
            raise ApiError(403, "CSRF_FAILED", "CSRF-токен отсутствует или не совпадает")

    # ------------------------------------------------------------------

    def me(self, *, space: str, subject_id: str, actor_id: str, origin: str | None) -> dict[str, Any]:
        self._check_space(space, origin)
        try:
            summary = self.community.summary(
                tenant_id=space, subject_id=subject_id, actor_id=actor_id
            )
        except UnknownSubject as exc:
            raise ApiError(404, "UNKNOWN_SUBJECT", str(exc)) from None
        return {
            "space": space,
            "subject_id": subject_id,
            "your_score": summary["your_score"],
            "aggregate": summary["aggregate"],
            "scale": "1-10",
            "write_enabled": self.public_write or actor_id in self.write_cohort,
        }

    def put_vote(
        self,
        *,
        space: str,
        subject_id: str,
        actor_id: str,
        score: Any,
        idempotency_key: str,
        origin: str | None,
        csrf_header: str | None = None,
        csrf_cookie: str | None = None,
    ) -> dict[str, Any]:
        self._check_space(space, origin)
        self._check_csrf(csrf_header, csrf_cookie)
        self._check_write_allowed(actor_id)
        if not idempotency_key:
            raise ApiError(400, "IDEMPOTENCY_REQUIRED", "требуется заголовок Idempotency-Key")
        try:
            result = self.community.submit(
                tenant_id=space,
                subject_id=subject_id,
                actor_id=actor_id,
                score=score,
                idempotency_key=idempotency_key,
            )
        except UnknownSubject as exc:
            raise ApiError(404, "UNKNOWN_SUBJECT", str(exc)) from None
        except VoteRejected as exc:
            raise ApiError(400, "INVALID_SCORE", str(exc)) from None
        return {
            "space": space,
            "subject_id": subject_id,
            "your_score": result["your_score"],
            "aggregate": result["aggregate"],
            "scale": "1-10",
        }

    def delete_vote(
        self,
        *,
        space: str,
        subject_id: str,
        actor_id: str,
        idempotency_key: str,
        origin: str | None,
        csrf_header: str | None = None,
        csrf_cookie: str | None = None,
    ) -> dict[str, Any]:
        self._check_space(space, origin)
        self._check_csrf(csrf_header, csrf_cookie)
        self._check_write_allowed(actor_id)
        if not idempotency_key:
            raise ApiError(400, "IDEMPOTENCY_REQUIRED", "требуется заголовок Idempotency-Key")
        try:
            result = self.community.retract(
                tenant_id=space,
                subject_id=subject_id,
                actor_id=actor_id,
                idempotency_key=idempotency_key,
            )
        except UnknownSubject as exc:
            raise ApiError(404, "UNKNOWN_SUBJECT", str(exc)) from None
        except VoteRejected as exc:
            raise ApiError(400, "INVALID_REQUEST", str(exc)) from None
        return {
            "space": space,
            "subject_id": subject_id,
            "your_score": None,
            "aggregate": result["aggregate"],
            "scale": "1-10",
        }

    def health(self) -> dict[str, Any]:
        return {
            "status": "ok",
            "public_write": self.public_write,
            "write_cohort_size": len(self.write_cohort),
            "kill_switch": self.guard.config.kill_switch,
            "read_only": self.guard.config.read_only,
        }


# ---------------------------------------------------------------------------
# HTTP-слой
# ---------------------------------------------------------------------------


def _cookies(raw: str | None) -> dict[str, str]:
    out: dict[str, str] = {}
    for part in (raw or "").split(";"):
        if "=" in part:
            key, value = part.split("=", 1)
            out[key.strip()] = value.strip()
    return out


class UnifiedRatingsHandler(BaseHTTPRequestHandler):
    api: UnifiedRatingsApi
    #: как определить голосующего; подменяется в тестах
    identify = staticmethod(lambda handler: _identity_from_cookie(handler))

    server_version = "unified-ratings/1.0"

    def log_message(self, fmt: str, *args: Any) -> None:  # noqa: A003
        return  # запросы витрины не пишем: в них идентификаторы посетителей

    def _send(self, status: int, payload: dict[str, Any]) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(body)

    def _body(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length") or 0)
        if length > MAX_BODY_BYTES:
            raise ApiError(413, "BODY_TOO_LARGE", "тело запроса слишком велико")
        if not length:
            return {}
        try:
            return json.loads(self.rfile.read(length).decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            raise ApiError(400, "BAD_JSON", "тело запроса не является JSON") from None

    def _dispatch(self, method: str) -> None:
        parsed = urlparse(self.path)
        origin = self.headers.get("Origin")
        cookies = _cookies(self.headers.get("Cookie"))
        actor = self.identify(self)
        try:
            if _HEALTH_RE.match(parsed.path):
                self._send(200, self.api.health())
                return
            if method == "GET" and _ME_RE.match(parsed.path):
                query = parse_qs(parsed.query)
                self._send(200, self.api.me(
                    space=(query.get("space") or [""])[0],
                    subject_id=(query.get("subject_id") or [""])[0],
                    actor_id=actor,
                    origin=origin,
                ))
                return
            if _VOTE_RE.match(parsed.path) and method in ("PUT", "DELETE"):
                body = self._body()
                common = {
                    "space": str(body.get("space") or ""),
                    "subject_id": str(body.get("subject_id") or ""),
                    "actor_id": actor,
                    "idempotency_key": self.headers.get(IDEMPOTENCY_HEADER) or "",
                    "origin": origin,
                    "csrf_header": self.headers.get(CSRF_HEADER),
                    "csrf_cookie": cookies.get(CSRF_COOKIE),
                }
                if method == "PUT":
                    self._send(200, self.api.put_vote(score=body.get("score"), **common))
                else:
                    self._send(200, self.api.delete_vote(**common))
                return
            self._send(404, {"error": "NOT_FOUND"})
        except ApiError as exc:
            self._send(exc.status, {"error": exc.code, "message": exc.message})
        except RateLimited as exc:
            self._send(429, {"error": "RATE_LIMITED", "message": str(exc)})
        except OriginRejected as exc:
            self._send(403, {"error": "ORIGIN_REJECTED", "message": str(exc)})
        except Exception:  # noqa: BLE001
            # Внутренняя ошибка наружу не описывается: текст исключения
            # может содержать пути и идентификаторы.
            self._send(500, {"error": "INTERNAL"})

    def do_GET(self) -> None:  # noqa: N802
        self._dispatch("GET")

    def do_PUT(self) -> None:  # noqa: N802
        self._dispatch("PUT")

    def do_DELETE(self) -> None:  # noqa: N802
        self._dispatch("DELETE")


def _identity_from_cookie(handler: BaseHTTPRequestHandler) -> str:
    """Псевдонимная личность из cookie витрины.

    Открытый IP личностью не является и в таблицу голосов не попадает:
    один адрес — это подъезд, офис или оператор, а не посетитель.
    """
    from factory.community.identity_v1 import COOKIE_NAME, verify_token

    token = _cookies(handler.headers.get("Cookie")).get(COOKIE_NAME, "")
    if not token:
        return ""
    try:
        return verify_token(token) or ""
    except Exception:  # noqa: BLE001
        return ""


def serve(api: UnifiedRatingsApi, *, host: str = DEFAULT_HOST, port: int = DEFAULT_PORT):
    """Запустить сервер на loopback. Наружу его выставляет только nginx."""
    handler = type("BoundHandler", (UnifiedRatingsHandler,), {"api": api})
    return ThreadingHTTPServer((host, port), handler)
