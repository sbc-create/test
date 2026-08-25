"""Одноразовая HTTPS-форма ввода credentials.

Форма существует ровно столько, сколько нужно, чтобы один человек один раз ввёл
два значения. После успеха, истечения TTL или пятой неудачной попытки endpoint
исчезает: сервер закрывается, а пока он ещё жив в процессе завершения, отвечает
``404`` на любой путь — «сессия закончилась» и «такого адреса нет» для внешнего
наблюдателя выглядят одинаково.

Что здесь сделано и почему:

* **одноразовый код** печатается только в root-консоли (stderr сервиса, то есть
  ``journalctl`` root-owned unit'а). Ни в ответе HTTP, ни в JSON операции его нет:
  сессия агента не должна уметь войти в форму, которую сама же запустила;
* **TTL** ≤ 15 минут и жёстко ограничен сверху: значение из запроса не может его
  увеличить, только уменьшить;
* **пять попыток** считаются по коду доступа. Шестая не проверяется — сессия уже
  закрыта;
* **POST, тело ≤ 8 KiB, никаких query string**: значение в query попало бы в
  историю браузера, в Referer и в лог любого промежуточного узла. Обработчик
  ``GET`` с параметрами отвечает 404, а не «попробуйте POST»;
* **CSRF**: токен формы связан с сессией и сверяется постоянным по времени
  сравнением;
* **access_log off** — сервер не ведёт журнал запросов вовсе: ``log_message``
  переопределён в no-op. Записывается только факт исхода, без тела и заголовков;
* **HTTPS** поднимается на эфемерном self-signed сертификате, созданном на время
  сессии. Отпечаток сертификата печатается рядом с кодом — оператор сверяет его
  в браузере. Сертификат не переиспользуется и удаляется вместе с сессией.

Форма слушает петлевой адрес. Публичного имени у хаба нет, DNS трогать
запрещено, поэтому оператор пробрасывает порт (``ssh -L``) и открывает
``https://127.0.0.1:<порт>/``. Это осознанный выбор в пользу «никогда не
публиковалось наружу», а не упущение; адрес и порт настраиваются.
"""
from __future__ import annotations

import hmac
import html
import http.server
import os
import secrets
import ssl
import sys
import tempfile
import threading
import time
from dataclasses import dataclass, field
from datetime import UTC
from pathlib import Path

from factory.secret_hub.crypto import Secret

#: Верхняя граница TTL. Задание требует «максимум 15 минут»; запрос может
#: попросить меньше, но не больше.
MAX_TTL_SECONDS = 15 * 60
DEFAULT_TTL_SECONDS = 15 * 60

#: Больше пяти неверных кодов — сессия закрыта.
MAX_ATTEMPTS = 5

#: Тело запроса не может быть больше 8 KiB.
MAX_BODY_BYTES = 8 * 1024

#: Адрес по умолчанию: только петля. Наружу форма не публикуется.
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8443

HOST_ENV = "SECRET_HUB_ENROLL_HOST"
PORT_ENV = "SECRET_HUB_ENROLL_PORT"


@dataclass
class Session:
    """Состояние одной сессии ввода. Значения здесь не задерживаются."""

    #: Направления, которые форма предлагает выбрать. Список приходит из
    #: реестра: захардкоженного перечня направлений в форме нет, как и в
    #: остальном пакете.
    portfolios: tuple[str, ...]
    code: str
    csrf: str
    expires_at: float
    #: Путь, по которому форма доступна снаружи. За nginx это
    #: «/__factory-secrets», в петлевом режиме — «/».
    base_path: str = "/"
    #: Уникальная метка этой сессии в HTML. Не секрет: по ней лончер убеждается,
    #: что страницу отдал именно этот процесс, а не кэш, заглушка соседнего
    #: vhost или страница прошлой сессии.
    marker: str = ""
    attempts: int = 0
    finished: bool = False
    outcome: str = "pending"
    detail: str = ""
    #: Направление, выбранное в форме. До отправки — None.
    portfolio: str | None = None
    stored_version: int | None = None
    fingerprint: str | None = None
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    @property
    def expired(self) -> bool:
        return time.monotonic() >= self.expires_at

    @property
    def alive(self) -> bool:
        return not self.finished and not self.expired and self.attempts < MAX_ATTEMPTS

    def close(self, outcome: str, detail: str = "") -> None:
        self.finished = True
        self.outcome = outcome
        self.detail = detail

    def __repr__(self) -> str:  # код доступа — тоже секрет
        return f"<Session portfolios={len(self.portfolios)} outcome={self.outcome}>"


PAGE = """<!doctype html>
<html lang="ru"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="referrer" content="no-referrer">
<meta name="robots" content="noindex, nofollow">
<title>Secret Hub — ввод credentials</title>
<style>
 body{{font:16px/1.5 system-ui,sans-serif;max-width:34rem;margin:3rem auto;padding:0 1rem}}
 label{{display:block;margin:1rem 0 .25rem;font-weight:600}}
 input,select{{width:100%;padding:.5rem;font:inherit;border:1px solid #999;border-radius:4px}}
 button{{margin-top:1.5rem;padding:.6rem 1.2rem;font:inherit}}
 .err{{color:#a00;font-weight:600}}
 .note{{color:#555;font-size:.9rem}}
</style></head><body>
<!-- {marker} -->
<h1>Secret Hub</h1>
<p class="note">Форма одноразовая. Она исчезнет после успешного ввода, по истечении
срока или после пяти неверных кодов. Значения проверяются у провайдера живым
read-only запросом до записи; неверные не сохраняются.</p>
{error}
<form method="POST" action="{action}" autocomplete="off">
 <input type="hidden" name="csrf" value="{csrf}">
 <label for="portfolio">Направление</label>
 <select id="portfolio" name="portfolio" required>{options}</select>
 <label for="code">Одноразовый код (из root-консоли)</label>
 <input id="code" name="code" type="password" required autocomplete="off">
 <label for="api_token">CDNVideoHub API Token</label>
 <input id="api_token" name="api_token" type="password" required autocomplete="off">
 <label for="publisher_id">CDNVideoHub Publisher ID</label>
 <input id="publisher_id" name="publisher_id" type="text" required autocomplete="off">
 <button type="submit">Проверить и сохранить</button>
</form>
</body></html>"""

DONE_PAGE = """<!doctype html>
<html lang="ru"><head><meta charset="utf-8">
<meta name="robots" content="noindex, nofollow"><title>Готово</title></head><body>
<!-- {marker} -->
<h1>Сохранено</h1>
<p>Направление <b>{portfolio}</b>: credentials проверены у провайдера и записаны
(версия {version}, отпечаток {fingerprint}).</p>
<p>Форма закрыта. Повторное обращение по этому адресу вернёт 404.</p>
</body></html>"""


def _options(session: Session) -> str:
    """Список направлений для <select>. Берётся из сессии, а не из литерала."""
    return "".join(
        f'<option value="{html.escape(name)}">{html.escape(name)}</option>'
        for name in session.portfolios
    )


class _Handler(http.server.BaseHTTPRequestHandler):
    session: Session
    hub: object
    server_version = "SecretHub"
    sys_version = ""
    protocol_version = "HTTP/1.1"

    # access_log off: сервер не пишет журнал запросов вовсе. Путь, заголовки и
    # тело в журнал не попадают ни при каком исходе.
    def log_message(self, *args, **kwargs) -> None:
        return

    def log_request(self, *args, **kwargs) -> None:
        return

    # --- ответы -----------------------------------------------------------
    def _send(self, status: int, body: str, content_type: str = "text/html; charset=utf-8") -> None:
        payload = body.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Cache-Control", "no-store, max-age=0")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("X-Robots-Tag", "noindex, nofollow")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Content-Security-Policy", "default-src 'none'; style-src 'unsafe-inline'; form-action 'self'")
        self.send_header("Connection", "close")
        self.end_headers()
        self.wfile.write(payload)

    def _gone(self) -> None:
        """Закончившаяся сессия неотличима от несуществующего адреса."""
        self._send(404, "<!doctype html><title>404</title><h1>404</h1>")

    # --- методы -----------------------------------------------------------
    def _path_matches(self) -> bool:
        """Точное совпадение с публичным путём, без query.

        Query отвергается целиком: секрет в query string оседает в истории
        браузера, в Referer и в журнале любого промежуточного узла. Форма
        никогда не предлагает такой путь, но проверить это дешевле, чем
        объяснять потом.
        """
        return self.path == self.session.base_path

    def do_GET(self) -> None:
        if not self.session.alive or not self._path_matches():
            self._gone()
            return
        self._send(200, self._render())

    def do_POST(self) -> None:
        session = self.session
        if not session.alive or not self._path_matches():
            self._gone()
            return

        length_raw = self.headers.get("Content-Length", "")
        try:
            length = int(length_raw)
        except ValueError:
            self._gone()
            return
        if length < 0 or length > MAX_BODY_BYTES:
            # Ограничение проверяется по заголовку и ещё раз по факту чтения:
            # заголовку верить нельзя, а читать неограниченное тело — нельзя тем
            # более.
            self._send(413, "<!doctype html><title>413</title><h1>413</h1>")
            return
        body = self.rfile.read(length)
        if len(body) > MAX_BODY_BYTES:
            self._send(413, "<!doctype html><title>413</title><h1>413</h1>")
            return

        fields = _parse_form(body)
        with session._lock:
            if not session.alive:
                self._gone()
                return

            if not _equal(fields.get("csrf", ""), session.csrf):
                session.attempts += 1
                self._fail(session, "Форма отклонена: не совпал CSRF-токен.")
                return

            if not _equal(fields.get("code", ""), session.code):
                session.attempts += 1
                if session.attempts >= MAX_ATTEMPTS:
                    session.close("too_many_attempts",
                                  f"{MAX_ATTEMPTS} неверных кодов: сессия закрыта")
                    self._gone()
                    _stop(self.server)
                    return
                self._fail(session, f"Неверный код. Попытка {session.attempts} из {MAX_ATTEMPTS}.")
                return

            # Направление берётся из формы, но принимается только из списка
            # сессии. Иначе подставленное в POST имя записало бы секрет в
            # направление, которого оператор не выбирал, — а список сессии
            # собран из реестра.
            portfolio = fields.get("portfolio", "").strip()
            if portfolio not in session.portfolios:
                session.attempts += 1
                self._fail(session, "Направление не выбрано или не входит в список.")
                return

            api_token = fields.get("api_token", "").strip()
            publisher_id = fields.get("publisher_id", "").strip()
            if not api_token or not publisher_id:
                session.attempts += 1
                self._fail(session, "Оба поля обязательны. Пустое поле — не разрешение "
                                    "работать без значения.")
                return

            values = {
                "api_token": Secret(api_token, label=f"{portfolio}/api_token"),
                "publisher_id": Secret(publisher_id, label=f"{portfolio}/publisher_id"),
            }
            # Значения существуют ровно здесь и уходят в store_verified, который
            # проверяет их у провайдера и записывает только принятые.
            result = self.hub.store_verified(portfolio, values)
            del values, api_token, publisher_id, fields

            if not result.get("stored"):
                session.attempts += 1
                reason = result.get("reason", "провайдер не подтвердил credentials")
                if session.attempts >= MAX_ATTEMPTS:
                    session.close("too_many_attempts", reason)
                    self._gone()
                    _stop(self.server)
                    return
                self._fail(session, f"Не сохранено: {reason}")
                return

            session.portfolio = portfolio
            session.stored_version = result.get("version")
            session.fingerprint = result.get("fingerprint")
            session.close("stored", f"версия {session.stored_version}")

        self._send(200, DONE_PAGE.format(
            marker=html.escape(session.marker),
            portfolio=html.escape(portfolio),
            version=html.escape(str(session.stored_version)),
            fingerprint=html.escape(str(session.fingerprint)),
        ))
        _stop(self.server)

    def _render(self, error: str = "") -> str:
        session = self.session
        return PAGE.format(
            marker=html.escape(session.marker),
            action=html.escape(session.base_path),
            options=_options(session),
            csrf=html.escape(session.csrf),
            error=error,
        )

    def _fail(self, session: Session, message: str) -> None:
        self._send(400, self._render(
            f'<p class="err">{html.escape(message)}</p>'))

def _equal(supplied: str, expected: str) -> bool:
    """Постоянное по времени сравнение, переживающее не-ASCII ввод.

    ``hmac.compare_digest`` на ``str`` работает только с ASCII и на кириллице
    выбрасывает ``TypeError``. В обработчике это означало не «код неверен», а
    падение соединения без ответа: пользователь, набравший в поле кода русские
    буквы, получал разорванное соединение вместо честного отказа, и попытка при
    этом не засчитывалась. Сравнение идёт по UTF-8 байтам.
    """
    return hmac.compare_digest(supplied.encode("utf-8"), expected.encode("utf-8"))


def _parse_form(body: bytes) -> dict[str, str]:
    """Разбор ``application/x-www-form-urlencoded`` без сохранения сырого тела.

    ``parse_qs`` из ``urllib`` подошёл бы, но он оставляет исходную строку в
    памяти дольше, чем нужно, и складывает значения в списки, которые потом
    приходится разворачивать. Здесь разбор прямой и результат — плоский словарь.
    """
    from urllib.parse import unquote_plus

    out: dict[str, str] = {}
    try:
        text = body.decode("utf-8")
    except UnicodeDecodeError:
        return out
    for pair in text.split("&"):
        if "=" not in pair:
            continue
        name, _, raw = pair.partition("=")
        out[unquote_plus(name)] = unquote_plus(raw)
    return out


def _stop(server) -> None:
    threading.Thread(target=server.shutdown, daemon=True).start()


def _ephemeral_certificate(directory: Path) -> tuple[Path, str]:
    """Self-signed сертификат на время сессии и его отпечаток.

    Сертификат создаётся заново для каждой сессии и живёт в каталоге, который
    удаляется вместе с ней. Отпечаток печатается в root-консоли: оператор
    сверяет его в браузере и потому не обязан доверять «просто HTTPS».
    """
    from datetime import datetime, timedelta

    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import ec
    from cryptography.x509.oid import NameOID

    key = ec.generate_private_key(ec.SECP256R1())
    subject = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "site-factory-secret-hub")])
    now = datetime.now(UTC)
    certificate = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(subject)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - timedelta(minutes=1))
        .not_valid_after(now + timedelta(hours=1))
        .add_extension(x509.SubjectAlternativeName([
            x509.DNSName("localhost"),
            x509.IPAddress(__import__("ipaddress").ip_address("127.0.0.1")),
        ]), critical=False)
        .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
        .sign(key, hashes.SHA256())
    )
    pem = directory / "enroll.pem"
    fd = os.open(pem, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    try:
        os.write(fd, key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        ))
        os.write(fd, certificate.public_bytes(serialization.Encoding.PEM))
    finally:
        os.close(fd)
    fingerprint = certificate.fingerprint(hashes.SHA256()).hex()
    pretty = ":".join(fingerprint[i:i + 2] for i in range(0, len(fingerprint), 2)).upper()
    return pem, pretty


def start_session(hub, portfolios, *, ttl_seconds: int | None = None,
                  host: str | None = None, port: int | None = None,
                  base_path: str = "/", tls: bool = True,
                  announce=None, serve: bool = True, public_url: str | None = None) -> dict:
    """Поднимает форму и возвращает то, что можно показать вызывающему.

    Два режима:

    ``tls=True``
        Форма сама поднимает HTTPS на эфемерном self-signed сертификате.
        Применяется, когда до неё добираются пробросом порта.

    ``tls=False``
        Форма слушает обычный HTTP на петле, а TLS терминирует nginx настоящим
        сертификатом домена. Именно так работает публичный режим: снаружи это
        `https://<домен>/__factory-secrets`, а открытым текстом трафик идёт
        только внутри машины, между nginx и этим процессом.

    В ответе нет ни кода доступа, ни CSRF-токена: они печатаются в root-консоли.
    Вызывающая сторона узнаёт адрес, метку страницы, срок и итог.
    """
    if isinstance(portfolios, str):
        portfolios = (portfolios,)
    portfolios = tuple(portfolios)
    if not portfolios:
        raise ValueError("список направлений пуст: выбирать не из чего")

    ttl = min(int(ttl_seconds or DEFAULT_TTL_SECONDS), MAX_TTL_SECONDS)
    if ttl <= 0:
        ttl = DEFAULT_TTL_SECONDS
    host = host or os.environ.get(HOST_ENV) or DEFAULT_HOST
    # `is None`, а не `or`: порт 0 — это законная просьба «дай любой свободный»,
    # и `or` молча подменил бы её значением по умолчанию. Ровно на этом тесты и
    # начали драться за один и тот же 8443.
    if port is None:
        configured = os.environ.get(PORT_ENV)
        port = int(configured) if configured else DEFAULT_PORT
    port = int(port)

    session = Session(
        portfolios=portfolios,
        code=_readable_code(),
        csrf=secrets.token_urlsafe(32),
        expires_at=time.monotonic() + ttl,
        base_path=base_path,
        marker=f"secret-hub-form {secrets.token_hex(16)}",
    )

    workdir = Path(tempfile.mkdtemp(prefix="secret-hub-enroll-"))
    os.chmod(workdir, 0o700)
    fingerprint = "—"
    try:
        handler = type("_BoundEnrollHandler", (_Handler,),
                       {"session": session, "hub": hub})
        server = http.server.ThreadingHTTPServer((host, port), handler)
        if tls:
            pem, fingerprint = _ephemeral_certificate(workdir)
            context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
            context.minimum_version = ssl.TLSVersion.TLSv1_2
            context.load_cert_chain(pem)
            server.socket = context.wrap_socket(server.socket, server_side=True)
        actual_port = server.server_address[1]
        url = public_url or f"{'https' if tls else 'http'}://{host}:{actual_port}{base_path}"

        (announce or _announce_to_root_console)(session, url, actual_port, fingerprint, ttl)

        if not serve:
            return {"url": url, "ttl_seconds": ttl, "marker": session.marker,
                    "portfolios": list(portfolios), "server": server, "session": session}

        timer = threading.Timer(ttl, lambda: _expire(session, server))
        timer.daemon = True
        timer.start()
        try:
            server.serve_forever(poll_interval=0.2)
        finally:
            timer.cancel()
            server.server_close()
    finally:
        # Каталог с ключом сертификата уничтожается вместе с сессией: держать
        # его дольше незачем, а «временный файл, который забыли» — обычная
        # причина того, что секрет переживает процесс.
        import shutil

        shutil.rmtree(workdir, ignore_errors=True)

    if not session.finished:
        session.close("expired", f"TTL {ttl} с истёк")
    return {
        "portfolio": session.portfolio,
        "portfolios": list(portfolios),
        "outcome": session.outcome,
        "detail": session.detail,
        "attempts": session.attempts,
        "version": session.stored_version,
        "fingerprint": session.fingerprint,
        "marker": session.marker,
        "url": url,
        "ttl_seconds": ttl,
    }


def _expire(session: Session, server) -> None:
    with session._lock:
        if session.finished:
            return
        session.close("expired", "TTL истёк")
    _stop(server)


def _readable_code() -> str:
    """Код из групп, которые человек может перепечатать без ошибок.

    Алфавит без ``0/O`` и ``1/I/l``: одноразовый код вводится глазами с консоли,
    и перепутанный символ стоит одной из пяти попыток.
    """
    alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
    groups = ["".join(secrets.choice(alphabet) for _ in range(5)) for _ in range(4)]
    return "-".join(groups)


def _announce_to_root_console(session: Session, url: str, port: int, fingerprint: str,
                              ttl: int) -> None:
    """Печатает код только туда, куда смотрит root.

    stdout/stderr этого процесса — это root-консоль (или журнал root-owned
    unit'а, доступный только root). В ответ операции код не попадает: иначе тот,
    кто запустил форму, смог бы ею воспользоваться, а именно этого мы и не хотим.
    """
    lines = [
        "",
        "=" * 72,
        "  SECRET HUB — одноразовая форма ввода",
        "=" * 72,
        f"  Адрес:        {url}",
        f"  Направления:  {', '.join(session.portfolios)}",
        f"  Код доступа:  {session.code}",
    ]
    if fingerprint and fingerprint != "—":
        lines.append(f"  Отпечаток TLS (SHA-256): {fingerprint}")
    lines += [
        f"  Срок:         {ttl // 60} мин   Попыток: {MAX_ATTEMPTS}",
        "",
        "  Код напечатан только здесь. После успешного ввода, истечения срока",
        "  или пяти неверных попыток адрес отвечает 404.",
        "=" * 72,
        "",
    ]
    print("\n".join(lines), file=sys.stderr, flush=True)


__all__ = ["start_session", "Session", "MAX_ATTEMPTS", "MAX_TTL_SECONDS", "MAX_BODY_BYTES"]
