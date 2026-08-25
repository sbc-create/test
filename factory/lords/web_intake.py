"""Одноразовая веб-форма приёма учётных данных CDNVideoHub.

Нужна там, где секрет нельзя перепечатать руками: владелец открывает страницу в
обычном браузере и вставляет значения из буфера. Форма живёт считанные минуты и
исчезает насовсем.

Устройство подчинено одному правилу: секрет не должен оказаться нигде, кроме
файла с правами 0600. Поэтому здесь нет ни одного места, где значение попадало
бы в адрес, журнал, вывод процесса или ответ браузеру.

Что охраняется и чем:

* приём только POST, значения только в теле — адрес и query остаются пустыми,
  а именно они попадают в access_log, историю браузера и Referer;
* журнал сервера отключён целиком: `log_message` заглушён, потому что базовый
  обработчик пишет строку запроса, а её содержимое нам неподконтрольно;
* размер тела ограничен: неограниченный POST — это способ занять память;
* код доступа одноразовый и с ограничением попыток, чтобы его нельзя было
  подобрать за отведённые минуты;
* CSRF-токен привязан к сессии, выданной этим же сервером;
* ответ формы не содержит введённых значений даже при ошибке — перерисовывать
  введённый секрет обратно в HTML незачем.
"""

from __future__ import annotations

import contextlib
import hmac
import json
import os
import secrets
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

#: Больше тела нам не нужно: токен и число. Всё сверх — либо ошибка, либо атака.
MAX_BODY_BYTES = 8 * 1024

#: Попытки ввода кода. Код короткий, поэтому счёт жёсткий.
MAX_CODE_ATTEMPTS = 5

#: Длина одноразового кода в символах. Алфавит без похожих знаков.
CODE_LENGTH = 8
# Без 0/O, 1/I/L: код читают с консоли и набирают в браузере.
CODE_ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"

DEFAULT_TTL_SECONDS = 15 * 60

STATE_WAITING = "WAITING"
STATE_ACCEPTED = "ACCEPTED"
STATE_EXPIRED = "EXPIRED"
STATE_LOCKED = "LOCKED"


def generate_code() -> str:
    return "".join(secrets.choice(CODE_ALPHABET) for _ in range(CODE_LENGTH))


def is_valid_publisher_id(value: str) -> bool:
    text = (value or "").strip()
    if not text.isdigit() or text.startswith("0"):
        return False
    return int(text) >= 1


def write_secret_atomic(path: Path, value: str) -> None:
    """Секрет на диск: временный файл с правами 0600, затем rename.

    Права выставляются до записи содержимого, а не после: иначе между
    созданием и chmod существует окно, в котором файл читаем всем.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    os.chmod(path.parent, 0o700)
    tmp = path.with_name(f".{path.name}.tmp")
    descriptor = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(value)
            handle.flush()
            os.fsync(handle.fileno())
    except BaseException:
        os.unlink(tmp)
        raise
    os.replace(tmp, path)
    os.chmod(path, 0o600)


def probe_token(token: str, url: str, *, timeout: float = 30.0, opener=None) -> tuple[bool, str]:
    """Проверка токена до единой мутации.

    Токен уходит заголовком. В адрес он не попадает, поэтому не окажется ни в
    журнале провайдера, ни в нашем.
    """
    request = urllib.request.Request(url, method="GET")
    request.add_header("Authorization", f"Bearer {token}")
    request.add_header("Accept", "application/json")
    try:
        if opener is not None:
            status = opener(request, timeout)
        else:
            with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310
                status = response.status
    except urllib.error.HTTPError as error:
        status = error.code
    except (TimeoutError, OSError) as error:
        return False, f"источник недоступен: {type(error).__name__}"
    if status == 200:
        return True, "источник принял токен"
    if status in (401, 403):
        return False, "источник отклонил токен"
    return False, f"источник ответил {status}"


@dataclass
class Intake:
    """Состояние одноразового приёма. Секрет здесь не задерживается."""

    code: str
    token_file: Path
    publisher_file: Path
    probe_url: str
    ttl_seconds: int = DEFAULT_TTL_SECONDS
    started_at: float = field(default_factory=time.monotonic)
    attempts: int = 0
    state: str = STATE_WAITING
    sessions: dict = field(default_factory=dict)
    probe: object = None
    marker: str = ""
    _lock: threading.Lock = field(default_factory=threading.Lock)

    def expired(self, now: float | None = None) -> bool:
        current = time.monotonic() if now is None else now
        return (current - self.started_at) >= self.ttl_seconds

    def seconds_left(self, now: float | None = None) -> int:
        current = time.monotonic() if now is None else now
        return max(0, int(self.ttl_seconds - (current - self.started_at)))

    def new_session(self) -> tuple[str, str]:
        session = secrets.token_urlsafe(24)
        csrf = secrets.token_urlsafe(24)
        with self._lock:
            self.sessions[session] = csrf
        return session, csrf

    def csrf_for(self, session: str) -> str | None:
        with self._lock:
            return self.sessions.get(session)

    def check_code(self, supplied: str) -> tuple[bool, str]:
        with self._lock:
            if self.state != STATE_WAITING:
                return False, "приём закрыт"
            if self.attempts >= MAX_CODE_ATTEMPTS:
                self.state = STATE_LOCKED
                return False, "исчерпаны попытки ввода кода"
            self.attempts += 1
            # Сравнение с постоянным временем: обычное сравнение строк
            # подсказывает длину совпавшего префикса.
            if hmac.compare_digest(supplied.strip().upper(), self.code):
                return True, "код принят"
            left = MAX_CODE_ATTEMPTS - self.attempts
            if left <= 0:
                self.state = STATE_LOCKED
                return False, "исчерпаны попытки ввода кода"
            return False, f"код неверен, осталось попыток: {left}"

    def accept(self, token: str, publisher_id: str) -> tuple[bool, str]:
        """Проверить токен и сохранить обе величины. Секрет никуда не пишется."""
        if self.expired():
            self.state = STATE_EXPIRED
            return False, "срок действия формы истёк"
        if not token.strip():
            return False, "токен пуст"
        if not is_valid_publisher_id(publisher_id):
            return False, "Publisher ID обязан быть положительным целым"

        ok, reason = probe_token(token.strip(), self.probe_url, opener=self.probe)
        if not ok:
            # Ничего не изменено, форма остаётся открытой для повторного ввода.
            return False, reason

        write_secret_atomic(self.token_file, token.strip())
        write_secret_atomic(self.publisher_file, publisher_id.strip())
        with self._lock:
            self.state = STATE_ACCEPTED
            self.sessions.clear()
        return True, "учётные данные приняты"


PAGE = """<!doctype html>
<html lang="ru"><head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex, nofollow">
<title>Активация Lords</title>
<meta name="lords-form-marker" content="{marker}">
<style>
 body{{font:16px/1.5 system-ui,sans-serif;max-width:34rem;margin:3rem auto;padding:0 1rem}}
 label{{display:block;margin:1rem 0 .25rem;font-weight:600}}
 input{{width:100%;padding:.6rem;font-size:1rem;box-sizing:border-box}}
 button{{margin-top:1.5rem;padding:.7rem 1.4rem;font-size:1rem}}
 .msg{{padding:.75rem;border-left:4px solid #999;background:#f4f4f4;margin:1rem 0}}
 .err{{border-color:#b00}}
 .ok{{border-color:#080}}
 .muted{{color:#666;font-size:.9rem}}
</style></head><body>
<h1>Активация живого каталога Lords</h1>
{message}
<form method="POST" action="/__lords-activate" autocomplete="off">
 <input type="hidden" name="csrf" value="{csrf}">
 <label for="code">Одноразовый код из консоли</label>
 <input id="code" name="code" required autocapitalize="characters" autocomplete="off">
 <label for="token">CDNVIDEOHUB_API_TOKEN</label>
 <input id="token" name="token" type="password" required autocomplete="off">
 <label for="publisher">CDNVIDEOHUB_PUBLISHER_ID (число)</label>
 <input id="publisher" name="publisher" inputmode="numeric" pattern="[1-9][0-9]*" required
        autocomplete="off">
 <label for="rights">Подтверждение прав</label>
 <input id="rights" name="rights" required placeholder="RIGHTS_CONFIRMED=yes" autocomplete="off">
 <button type="submit">Активировать</button>
</form>
<p class="muted">Форма закроется через {left} с или сразу после успешной отправки.
Значения не попадают ни в адрес, ни в журналы.</p>
</body></html>
"""

DONE = """<!doctype html>
<html lang="ru"><head><meta charset="utf-8">
<meta name="robots" content="noindex, nofollow">
<title>Принято</title></head><body>
<h1>Учётные данные приняты</h1>
<p>Переключение каталога идёт в фоне. Эта страница больше не нужна и сейчас
исчезнет — обновлять её не надо.</p>
<p>Результат смотрите в root-консоли, где запускалась активация.</p>
</body></html>
"""

CLOSED = """<!doctype html>
<html lang="ru"><head><meta charset="utf-8">
<meta name="robots" content="noindex, nofollow">
<title>Приём закрыт</title></head><body>
<h1>Приём закрыт</h1><p>{reason}</p>
<p>Чтобы открыть форму заново, запустите активацию в консоли ещё раз.</p>
</body></html>
"""


def make_handler(intake: Intake, on_accept):
    class Handler(BaseHTTPRequestHandler):
        server_version = "lords-intake"
        sys_version = ""

        def log_message(self, *args):  # noqa: ARG002
            """Журнал отключён целиком.

            Базовый обработчик пишет строку запроса. Даже при приёме только POST
            это лишний канал, содержимое которого нам неподконтрольно.
            """

        def _send(self, status: int, body: str, *, session: str | None = None) -> None:
            payload = body.encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(payload)))
            self.send_header("X-Robots-Tag", "noindex, nofollow")
            self.send_header("Referrer-Policy", "no-referrer")
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            if session:
                self.send_header(
                    "Set-Cookie",
                    f"lords_intake={session}; Path=/__lords-activate; "
                    "HttpOnly; Secure; SameSite=Strict",
                )
            self.end_headers()
            self.wfile.write(payload)

        def _closed(self, reason: str) -> None:
            self._send(410, CLOSED.format(reason=reason))

        def _form(self, message: str = "", css: str = "") -> None:
            session, csrf = intake.new_session()
            block = f'<p class="msg {css}">{message}</p>' if message else ""
            self._send(
                200,
                PAGE.format(message=block, csrf=csrf, left=intake.seconds_left(),
                            marker=intake.marker),
                session=session,
            )

        def _session_cookie(self) -> str:
            raw = self.headers.get("Cookie") or ""
            for chunk in raw.split(";"):
                name, _, value = chunk.strip().partition("=")
                if name == "lords_intake":
                    return value
            return ""

        def do_GET(self):  # noqa: N802
            if self.path.split("?", 1)[0] != "/__lords-activate":
                self._send(404, "<h1>404</h1>")
                return
            if intake.expired():
                intake.state = STATE_EXPIRED
                self._closed("Срок действия формы истёк.")
                return
            if intake.state != STATE_WAITING:
                self._closed("Приём уже завершён.")
                return
            self._form()

        def do_POST(self):  # noqa: N802
            if self.path.split("?", 1)[0] != "/__lords-activate":
                self._send(404, "<h1>404</h1>")
                return
            if intake.expired():
                intake.state = STATE_EXPIRED
                self._closed("Срок действия формы истёк.")
                return
            if intake.state != STATE_WAITING:
                self._closed("Приём уже завершён.")
                return

            length = int(self.headers.get("Content-Length") or 0)
            if length <= 0 or length > MAX_BODY_BYTES:
                self._send(413, CLOSED.format(reason="Тело запроса неприемлемого размера."))
                return
            raw = self.rfile.read(length).decode("utf-8", "replace")
            fields = urllib.parse.parse_qs(raw, keep_blank_values=True)
            # Разобранное тело дальше этой функции не уходит; в журнал не пишется.

            expected = intake.csrf_for(self._session_cookie())
            supplied_csrf = (fields.get("csrf") or [""])[0]
            if not expected or not hmac.compare_digest(expected, supplied_csrf):
                self._form("Сессия формы устарела. Попробуйте ещё раз.", "err")
                return

            ok, reason = intake.check_code((fields.get("code") or [""])[0])
            if not ok:
                if intake.state == STATE_LOCKED:
                    self._closed("Исчерпаны попытки ввода кода. Приём закрыт.")
                else:
                    self._form(reason, "err")
                return

            if (fields.get("rights") or [""])[0].strip() != "RIGHTS_CONFIRMED=yes":
                self._form("Введите RIGHTS_CONFIRMED=yes для подтверждения прав.", "err")
                return

            accepted, message = intake.accept(
                (fields.get("token") or [""])[0],
                (fields.get("publisher") or [""])[0],
            )
            if not accepted:
                # Неверный токен ничего не меняет и не закрывает форму.
                self._form(message, "err")
                return

            self._send(200, DONE)
            with contextlib.suppress(OSError):
                self.wfile.flush()
            threading.Thread(target=on_accept, daemon=True).start()

    return Handler


def serve(intake: Intake, *, host: str = "127.0.0.1", port: int = 0, on_accept=lambda: None):
    """Поднимает приём и возвращает (сервер, порт). Останавливает вызывающий."""
    server = ThreadingHTTPServer((host, port), make_handler(intake, on_accept))
    server.daemon_threads = True
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, server.server_address[1]


def status_json(intake: Intake) -> str:
    """Состояние приёма без единого секрета."""
    return json.dumps(
        {
            "state": intake.state,
            "attempts": intake.attempts,
            "seconds_left": intake.seconds_left(),
            "code_present": bool(intake.code),
        },
        ensure_ascii=False,
    )
