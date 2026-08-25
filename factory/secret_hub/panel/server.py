"""HTTP-сервер панели. Работает от непривилегированной учётной записи.

Панель ничего не решает про секреты сама: она принимает значение из формы и
сразу передаёт его хабу операцией ``store``. Хаб проверяет его у провайдера,
шифрует и записывает. Обратно приходят версия, отпечаток и исход — значений в
ответе нет.

Что панель держит у себя: сессии, CSRF-токены, публичные ключи passkey'ев и
хеши recovery-кодов. Ни одно из этого не позволяет узнать credentials.

Защита запроса, по слоям:

* **cookie** — ``__Secure-`` префикс, ``Secure``, ``HttpOnly``, ``SameSite=Strict``,
  ``Path`` ровно на панель. Скрипт страницы её не читает, чужой сайт её не
  отправит, а сам сайт-арендатор её не получит;
* **CSRF** — токен в ``<meta>`` и заголовке ``X-CSRF-Token``, сверяется с
  сессией. ``SameSite=Strict`` уже отсекает межсайтовые POST, но один слой
  защиты — это отсутствие защиты, когда он ошибётся;
* **CSP** — ``default-src 'none'``, ``script-src 'self'``. Инлайн-скриптов нет,
  поэтому XSS не с чего начинать; ``frame-ancestors 'none'`` вместе с
  ``X-Frame-Options: DENY`` закрывает clickjacking;
* **тело ≤ 8 KiB** — по заголовку и по факту чтения;
* **rate limit** — на вход, восстановление и сохранение.

Журнал запросов не ведётся: ``log_message`` и ``log_request`` — no-op. Ни путь,
ни заголовки, ни тем более тело в лог не попадают.
"""
from __future__ import annotations

import http.cookies
import http.server
import json
import threading
from dataclasses import dataclass
from pathlib import Path

from factory.secret_hub.panel import MAX_BODY_BYTES, SESSION_COOKIE, ui
from factory.secret_hub.panel import auth as auth_mod
from factory.secret_hub.panel.store import PanelStore

#: Ограничение частоты сохранений: защита от случайного повтора и от перебора
#: токенов через панель.
SAVE_WINDOW_SECONDS = 60
SAVE_MAX_ATTEMPTS = 12

#: Cookie, в которой хранится идентификатор challenge между двумя шагами
#: церемонии WebAuthn. Значение challenge остаётся на сервере.
CHALLENGE_COOKIE = "__Secure-sfpanel-ch"


@dataclass
class PanelConfig:
    """Всё, что панели нужно знать о внешнем мире."""

    base_path: str
    server_name: str
    socket_path: Path
    state_dir: Path
    host: str = "127.0.0.1"
    port: int = 8459

    @property
    def rp(self) -> auth_mod.RelyingParty:
        return auth_mod.RelyingParty.for_domain(self.server_name)

    @property
    def db_path(self) -> Path:
        return self.state_dir / "panel.sqlite3"


class _Handler(http.server.BaseHTTPRequestHandler):
    config: PanelConfig
    store: PanelStore
    server_version = "SecretHubPanel"
    sys_version = ""
    protocol_version = "HTTP/1.1"

    # Журнала запросов нет вовсе.
    def log_message(self, *args, **kwargs) -> None:
        return

    def log_request(self, *args, **kwargs) -> None:
        return

    # --- инфраструктура ответа -------------------------------------------
    def _headers(self, status: int, content_type: str, length: int,
                 cookies: list[str] | None = None) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(length))
        self.send_header("Cache-Control", "no-store, max-age=0")
        self.send_header("Pragma", "no-cache")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("X-Robots-Tag", "noindex, nofollow")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header(
            "Content-Security-Policy",
            "default-src 'none'; script-src 'self'; style-src 'unsafe-inline'; "
            "connect-src 'self'; form-action 'none'; base-uri 'none'; "
            "frame-ancestors 'none'",
        )
        self.send_header("Permissions-Policy", "publickey-credentials-get=(self)")
        for cookie in cookies or []:
            self.send_header("Set-Cookie", cookie)
        self.send_header("Connection", "close")
        self.end_headers()

    def _html(self, status: int, body: str, cookies: list[str] | None = None) -> None:
        payload = body.encode("utf-8")
        self._headers(status, "text/html; charset=utf-8", len(payload), cookies)
        self.wfile.write(payload)

    def _json(self, status: int, payload: dict, cookies: list[str] | None = None) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self._headers(status, "application/json; charset=utf-8", len(body), cookies)
        self.wfile.write(body)

    def _js(self, body: str) -> None:
        payload = body.encode("utf-8")
        self._headers(200, "application/javascript; charset=utf-8", len(payload))
        self.wfile.write(payload)

    def _not_found(self) -> None:
        self._html(404, "<!doctype html><title>404</title><h1>404</h1>")

    def _cookie(self, name: str, value: str, *, max_age: int) -> str:
        return (f"{name}={value}; Max-Age={max_age}; Path={self.config.base_path}; "
                "Secure; HttpOnly; SameSite=Strict")

    def _read_cookie(self, name: str) -> str:
        raw = self.headers.get("Cookie", "")
        if not raw:
            return ""
        jar = http.cookies.SimpleCookie()
        try:
            jar.load(raw)
        except http.cookies.CookieError:
            return ""
        morsel = jar.get(name)
        return morsel.value if morsel else ""

    # --- разбор запроса ---------------------------------------------------
    def _body(self) -> dict | None:
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            return None
        if length < 0 or length > MAX_BODY_BYTES:
            return None
        raw = self.rfile.read(length) if length else b"{}"
        if len(raw) > MAX_BODY_BYTES:
            return None
        try:
            data = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            return None
        return data if isinstance(data, dict) else None

    def _session(self):
        return self.store.session(self._read_cookie(SESSION_COOKIE))

    def _csrf_ok(self, session) -> bool:
        supplied = self.headers.get("X-CSRF-Token", "")
        import hmac as hmac_mod

        return bool(session) and hmac_mod.compare_digest(
            supplied.encode("utf-8"), session.csrf.encode("utf-8"))

    def _path(self) -> str:
        """Путь без базового префикса. Query не поддерживается вовсе."""
        base = self.config.base_path
        path = self.path
        if "?" in path:
            return "\x00"  # заведомо не совпадёт: query здесь не бывает
        if path == base:
            return "/"
        if path.startswith(base + "/"):
            return path[len(base):]
        return "\x00"

    # --- маршруты ---------------------------------------------------------
    def do_GET(self) -> None:
        route = self._path()
        if route == "/app.js":
            # Базовый путь объявляется префиксом, а не подстановкой в текст
            # скрипта: замена по подстроке однажды попадёт внутрь чужого
            # идентификатора и сломает файл незаметно.
            prefix = f"const BASE = {json.dumps(self.config.base_path)};\n"
            self._js(prefix + ui.SCRIPT)
            return
        if route != "/":
            self._not_found()
            return

        session = self._session()
        if session is None:
            fresh = self.store.create_session(label="gate")
            page = ui.gate(
                fresh.csrf, self.config.base_path,
                enrollment_open=self.store.enrollment_open(),
                has_passkey=self.store.has_passkey(),
            )
            self._html(200, page, [self._cookie(SESSION_COOKIE, fresh.session_id,
                                                max_age=900)])
            return
        if session.label != "owner":
            page = ui.gate(session.csrf, self.config.base_path,
                           enrollment_open=self.store.enrollment_open(),
                           has_passkey=self.store.has_passkey())
            self._html(200, page)
            return
        self._html(200, ui.page(self._rows(), session.csrf, self.config.base_path))

    def do_POST(self) -> None:
        route = self._path()
        routes = {
            "/api/login/begin": self._login_begin,
            "/api/login/finish": self._login_finish,
            "/api/register/begin": self._register_begin,
            "/api/register/finish": self._register_finish,
            "/api/portfolio/save": self._portfolio_save,
            "/api/portfolio/apply": self._portfolio_apply,
        }
        handler = routes.get(route)
        if handler is None:
            self._not_found()
            return

        body = self._body()
        if body is None:
            self._json(413, {"error": "Запрос слишком велик или не разобран."})
            return

        session = self._session()
        if session is None:
            self._json(401, {"error": "Сессия истекла. Обновите страницу."})
            return
        if not self._csrf_ok(session):
            self._json(403, {"error": "Форма устарела. Обновите страницу."})
            return
        try:
            handler(body, session)
        except auth_mod.RateLimited as exc:
            self._json(429, {"error": str(exc)})
        except auth_mod.AuthError as exc:
            self._json(400, {"error": str(exc)})
        except Exception as exc:  # pragma: no cover - защитная сетка
            self._json(500, {"error": f"Внутренняя ошибка ({exc.__class__.__name__})."})

    # --- вход -------------------------------------------------------------
    def _login_begin(self, body: dict, session) -> None:
        options = auth_mod.begin_authentication(self.store, self.config.rp)
        self._json(200, options)

    def _login_finish(self, body: dict, session) -> None:
        auth_mod.finish_authentication(
            self.store, self.config.rp,
            str(body.get("challenge_id") or ""), body.get("credential") or {},
        )
        self.store.drop_session(session.session_id)
        owner = self.store.create_session(label="owner")
        from factory.secret_hub.panel import SESSION_TTL_SECONDS

        self._json(200, {"ok": True},
                   [self._cookie(SESSION_COOKIE, owner.session_id,
                                 max_age=SESSION_TTL_SECONDS)])

    # --- регистрация ключа ------------------------------------------------
    def _register_begin(self, body: dict, session) -> None:
        """Право добавить ключ: код первичной регистрации, recovery или вход.

        Проверка идёт здесь, а не на шаге finish: иначе браузер создавал бы
        ключ, который затем отвергнут, и владелец видел бы диалог Touch ID без
        всякого результата.
        """
        allowed = session.label == "owner"
        if not allowed and body.get("enrollment_code"):
            auth_mod.use_enrollment_code(self.store, str(body["enrollment_code"]))
            allowed = True
        if not allowed and body.get("recovery_code"):
            auth_mod.use_recovery_code(self.store, str(body["recovery_code"]))
            allowed = True
        if not allowed:
            raise auth_mod.AuthError(
                "Чтобы добавить ключ, нужен действующий ключ или код восстановления.")
        # Право зафиксировано в сессии: шаг finish не станет проверять код
        # заново, а гасить его дважды нельзя — он одноразовый.
        self.store.drop_session(session.session_id)
        granted = self.store.create_session(label="may-register")
        options = auth_mod.begin_registration(self.store, self.config.rp)
        self._json(200, options,
                   [self._cookie(SESSION_COOKIE, granted.session_id, max_age=600)])

    def _register_finish(self, body: dict, session) -> None:
        if session.label not in ("may-register", "owner"):
            raise auth_mod.AuthError("Нет разрешения на добавление ключа.")
        auth_mod.finish_registration(
            self.store, self.config.rp,
            str(body.get("challenge_id") or ""), body.get("credential") or {},
            label=str(body.get("label") or "passkey"),
        )
        response: dict = {"ok": True}
        # Коды восстановления выдаются один раз — при появлении первого ключа.
        if self.store.recovery_status()["total"] == 0:
            response["recovery_codes"] = auth_mod.issue_recovery_codes(self.store)
        self.store.drop_session(session.session_id)
        owner = self.store.create_session(label="owner")
        from factory.secret_hub.panel import SESSION_TTL_SECONDS

        self._json(200, response,
                   [self._cookie(SESSION_COOKIE, owner.session_id,
                                 max_age=SESSION_TTL_SECONDS)])

    # --- направления ------------------------------------------------------
    def _require_owner(self, session) -> None:
        if session.label != "owner":
            raise auth_mod.AuthError("Требуется вход.")

    def _portfolio_save(self, body: dict, session) -> None:
        self._require_owner(session)
        request_id = str(body.get("request_id") or "")
        cached = self.store.recall_response(request_id)
        if cached:
            # Повтор той же отправки: возвращаем прежний ответ и не создаём
            # вторую версию секрета.
            self._json(200, json.loads(cached))
            return
        if self.store.attempts_within("save", SAVE_WINDOW_SECONDS) >= SAVE_MAX_ATTEMPTS:
            raise auth_mod.RateLimited("Слишком часто. Подождите минуту.")
        self.store.record_attempt("save")

        portfolio = str(body.get("portfolio") or "")
        result = self._hub({
            "op": "store",
            "portfolio": portfolio,
            "api_token": body.get("api_token") or "",
            "publisher_id": body.get("publisher_id") or "",
        })
        # Значения из тела запроса больше не нужны нигде.
        body.pop("api_token", None)
        body.pop("publisher_id", None)

        if not result.get("ok") or not result.get("stored"):
            reason = result.get("reason") or result.get("message") or "Проверка не пройдена."
            response = {"ok": False, "message": _human(reason)}
            self._json(200, response)
            return

        message = "Проверено и сохранено."
        if body.get("apply", True):
            applied = self._hub({"op": "apply", "portfolio": portfolio})
            if applied.get("ok"):
                message = "Проверено и применено."
            elif applied.get("error") == "BLOCKED_TARGET":
                message = ("Проверено и сохранено. Применять пока некуда: "
                           "инфраструктура направления не передана.")
            else:
                message = "Сохранено, но применить не удалось: " + _human(
                    applied.get("reason") or applied.get("status") or "неизвестная причина")
                response = {"ok": False, "message": message}
                if request_id:
                    self.store.remember_response(request_id, json.dumps(response))
                self._json(200, response)
                return

        response = {"ok": True, "message": message,
                    "fingerprint": result.get("fingerprint"),
                    "version": result.get("version")}
        if request_id:
            self.store.remember_response(request_id, json.dumps(response))
        self._json(200, response)

    def _portfolio_apply(self, body: dict, session) -> None:
        self._require_owner(session)
        result = self._hub({"op": "apply", "portfolio": str(body.get("portfolio") or "")})
        if result.get("ok"):
            self._json(200, {"ok": True, "message": "Применено к сайтам направления."})
            return
        if result.get("error") == "BLOCKED_TARGET":
            self._json(200, {"ok": False,
                             "message": "Применять пока некуда: инфраструктура "
                                        "направления не передана."})
            return
        self._json(200, {"ok": False, "message": _human(
            result.get("reason") or result.get("status") or "не применено")})

    # --- разговор с хабом -------------------------------------------------
    def _hub(self, payload: dict) -> dict:
        from factory.secret_hub import service

        try:
            return service.request(self.config.socket_path, payload)
        except FileNotFoundError:
            return {"ok": False, "reason": "Сервис Secret Hub не запущен."}
        except PermissionError:
            return {"ok": False, "reason": "Нет прав на обращение к сервису Secret Hub."}
        except (OSError, ConnectionError) as exc:
            return {"ok": False, "reason": f"Сервис не ответил ({exc.__class__.__name__})."}

    def _rows(self) -> list[dict]:
        """Состояние направлений для страницы. Значений в нём нет."""
        response = self._hub({"op": "status"})
        rows: list[dict] = []
        for row in response.get("portfolios", []):
            consumers = row.get("consumers") or []
            deployment = row.get("deployment") or []
            applied = sum(1 for d in deployment if d.get("status") == "applied")
            rows.append({
                "portfolio": row.get("portfolio"),
                "title": row.get("title") or row.get("portfolio"),
                "subtitle": _subtitle(row),
                "configured": bool(row.get("configured")),
                "verified": bool(row.get("verified")),
                "updated_at": row.get("updated_at"),
                "fingerprint": row.get("fingerprint"),
                "version": row.get("version"),
                "status": row.get("status"),
                "consumers": consumers,
                "consumer_count": len(consumers),
                "applied_count": applied,
            })
        return rows


def _subtitle(row: dict) -> str:
    blocked = row.get("blocked_target")
    if blocked:
        return "Инфраструктура направления ещё не передана — сохранить можно, применить пока нет."
    consumers = row.get("consumers") or []
    if not consumers:
        return "Сайты направления не описаны."
    return f"Сайтов в направлении: {len(consumers)}. Все используют один набор credentials."


def _human(reason: str) -> str:
    """Переводит внутренние формулировки в понятные владельцу."""
    text = str(reason)
    table = {
        "провайдер отверг credentials": "CDNVideoHub не принял этот токен. Проверьте значение.",
        "сеть до провайдера недоступна": "Не удалось связаться с CDNVideoHub. Попробуйте позже.",
        "не соответствует форме": "Publisher ID выглядит неправильно.",
        "не запущен": "Служба Secret Hub не отвечает. Нужен запуск на сервере.",
    }
    for needle, human in table.items():
        if needle in text:
            return human
    return text


class _Server(http.server.ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True


def build_server(config: PanelConfig, store: PanelStore) -> _Server:
    handler = type("_BoundPanelHandler", (_Handler,),
                   {"config": config, "store": store})
    return _Server((config.host, config.port), handler)


def serve(config: PanelConfig, *, ready: threading.Event | None = None) -> None:
    """Поднимает панель. Вызывается unit'ом от непривилегированной учётной записи."""
    store = PanelStore(config.db_path)
    server = build_server(config, store)
    if ready is not None:
        ready.set()
    try:
        server.serve_forever(poll_interval=0.2)
    finally:
        server.server_close()
        store.close()
