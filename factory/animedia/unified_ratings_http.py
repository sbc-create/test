"""Обработчик /api/unified-ratings/* внутри процесса витрины.

Витрина уже слушает свой порт, поэтому API оценок живёт в ней же: иначе
пришлось бы поднимать вторую службу и править nginx, а правка nginx на
этом этапе запрещена и к оценкам отношения не имеет.

Модуль отделён от адаптера намеренно. Адаптер только читает два файла и
не знает про базу; здесь — единственное место, где витрина к базе
обращается, и только ради голоса, который поставил человек.

Запись открыта owner-когорте, а не всем. Публичная раскатка голосования
на этом этапе равна нулю, и включается она флагом, а не наличием кода.
"""

from __future__ import annotations

import json
import os
import re
import sys
from typing import Any

# Модуль общего рейтингового ядра лежит вне релиза витрины: релиз
# неизменяем, а ядро обновляется отдельно и своей веткой.
CORE_ROOT = os.environ.get("UNIFIED_RATINGS_CORE", "/home/claude/wt-unified-ratings-1-10-sources-01")
if CORE_ROOT not in sys.path:
    sys.path.insert(0, CORE_ROOT)

API_PREFIX = "/api/unified-ratings"
_ME_RE = re.compile(rf"^{re.escape(API_PREFIX)}/me$")
_VOTE_RE = re.compile(rf"^{re.escape(API_PREFIX)}/vote$")
_HEALTH_RE = re.compile(rf"^{re.escape(API_PREFIX)}/health$")

SPACE = "animedia"
DB_PATH = os.environ.get(
    "UNIFIED_RATINGS_DB", "/srv/site-factory/repo/var/ratings/ratings.sqlite"
)

#: Владелец канарейки. Голос принимается только от этой личности, пока
#: публичная запись выключена.
OWNER_COHORT = {
    x.strip()
    for x in os.environ.get("UNIFIED_RATINGS_OWNER_COHORT", "owner-canary").split(",")
    if x.strip()
}

_api: Any = None
_error: str = ""


def _build_api():
    """Ленивая сборка: витрина поднимается, даже если ядро недоступно."""
    global _api, _error
    if _api is not None or _error:
        return _api
    try:
        from factory.community.service import CommunityVotesService
        from factory.community.store import CommunityStore
        from factory.unified_ratings.api import UnifiedRatingsApi
        from factory.unified_ratings.community import CommunityRatings
        from factory.unified_ratings.store import UnifiedStore

        store = UnifiedStore(DB_PATH, apply_migration=False)
        ledger = CommunityStore(DB_PATH)
        community = CommunityRatings(store, CommunityVotesService(ledger))
        from . import unified_ratings_adapter as adapter

        _api = UnifiedRatingsApi(
            community,
            write_cohort=set(OWNER_COHORT),
            public_write=adapter.public_write_enabled(),
        )
    except Exception as exc:  # noqa: BLE001
        # Недоступное ядро — это отсутствие API, а не сломанная витрина.
        _error = f"{type(exc).__name__}: {exc}"
        _api = None
    return _api


def handles(path: str) -> bool:
    return path.startswith(API_PREFIX)


def _identity(handler) -> str:
    """Личность голосующего из cookie витрины.

    Открытый IP личностью не считается: один адрес — это офис или
    оператор, а не посетитель.
    """
    raw = handler.headers.get("Cookie") or ""
    for part in raw.split(";"):
        if "=" in part:
            key, value = part.split("=", 1)
            if key.strip() == "ur_owner":
                return value.strip()
    return ""


def dispatch(handler, method: str, path: str, query: dict) -> tuple[int, dict]:
    """Вернуть (код, тело). Ошибки — коды, а не текст исключения."""
    from factory.unified_ratings.api import ApiError

    api = _build_api()
    if api is None:
        return 503, {"error": "CORE_UNAVAILABLE", "message": _error[:200]}

    origin = handler.headers.get("Origin")
    cookies = handler.headers.get("Cookie") or ""
    csrf_cookie = ""
    for part in cookies.split(";"):
        if "=" in part:
            key, value = part.split("=", 1)
            if key.strip() == "ur_csrf":
                csrf_cookie = value.strip()
    actor = _identity(handler)

    try:
        if _HEALTH_RE.match(path):
            from . import unified_ratings_adapter as adapter

            return 200, {**api.health(), "adapter": adapter.runtime_status()}
        if method == "GET" and _ME_RE.match(path):
            return 200, api.me(
                space=(query.get("space") or [SPACE])[0],
                subject_id=(query.get("subject_id") or [""])[0],
                actor_id=actor,
                origin=origin,
            )
        if _VOTE_RE.match(path) and method in ("PUT", "DELETE"):
            length = int(handler.headers.get("Content-Length") or 0)
            if length > 4096:
                return 413, {"error": "BODY_TOO_LARGE"}
            body = json.loads(handler.rfile.read(length) or b"{}")
            common = {
                "space": str(body.get("space") or SPACE),
                "subject_id": str(body.get("subject_id") or ""),
                "actor_id": actor,
                "idempotency_key": handler.headers.get("Idempotency-Key") or "",
                "origin": origin,
                "csrf_header": handler.headers.get("X-CSRF-Token"),
                "csrf_cookie": csrf_cookie,
            }
            if method == "PUT":
                return 200, api.put_vote(score=body.get("score"), **common)
            return 200, api.delete_vote(**common)
        return 404, {"error": "NOT_FOUND"}
    except ApiError as exc:
        return exc.status, {"error": exc.code, "message": exc.message}
    except (ValueError, json.JSONDecodeError):
        return 400, {"error": "BAD_REQUEST"}
    except Exception:  # noqa: BLE001
        return 500, {"error": "INTERNAL"}
