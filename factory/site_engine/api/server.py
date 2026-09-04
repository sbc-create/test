"""Подача Site Engine API по HTTP.

Отдельный модуль, потому что транспорт и логика отвечают на разные вопросы:
«что делать с запросом» и «как запрос сюда попал». Пока подачи не было,
описание существовало, а обратиться к API было нельзя — контракт без транспорта
выглядит готовым и не является таковым.

Три свойства заданы по умолчанию и меняются только осознанно:

* Привязка к 127.0.0.1. Слушать 0.0.0.0 нужно требовать явно: разница между
  «служба поднялась» и «служба доступна из интернета» — одна строка настройки,
  и увидеть её задним числом трудно.
* Предел размера тела. Без него отправитель решает, сколько памяти занять.
* Ответы без подробностей об исключениях. Трассировка в ответе — это карта
  внутреннего устройства, выданная тому, кто не смог сформировать корректный
  запрос.
"""
from __future__ import annotations

import http.server
import json
import signal
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, unquote, urlparse

from factory.site_engine.api import create_api
from factory.site_engine.api import startup as startup_protocol
from factory.site_engine.api.app import SiteEngineApi
from factory.site_engine.api.control import ControlApi
from factory.site_engine.api.lifecycle import Lifecycle, Notifier, watchdog_interval
from factory.site_engine.api.openapi import ЗАПИСЬ

MAX_BODY_BYTES = 256 * 1024
ADMIN_MAX_BODY_BYTES = 64 * 1024

def _control_get_prefixes() -> tuple[str, ...]:
    """Читающие маршруты управляющего слоя — из таблицы описания, не из списка.

    Список, который ведут вручную, отстаёт при добавлении маршрута, и отстаёт
    молча: маршрут уходит в читающий слой и отвечает 404, хотя реализован.
    Именно так и случилось с /api/v1/metrics.
    """
    prefixes = []
    for path, node in ЗАПИСЬ.items():
        if node.get("method") != "get":
            continue
        head, sep, _ = path.partition("{")
        prefixes.append(head if sep else path)
    return tuple(sorted(prefixes))


_CONTROL_GET_PREFIXES = _control_get_prefixes()


@dataclass
class ServerConfig:
    host: str = "127.0.0.1"
    port: int = 8787
    allow_public_bind: bool = False


def admin_enabled(env: dict[str, str] | None = None) -> bool:
    """Админка включается своим выключателем.

    Четвёртый независимый флаг, а не следствие остальных: интерфейс с формами
    и сессиями — отдельная поверхность нападения, и включать её вместе с
    машинным API значит включать её незаметно.
    """
    env = env if env is not None else {}
    return str(env.get("SITE_ENGINE_ADMIN", "")).strip().lower() in {"1", "true", "yes", "on"}


def http_enabled(env: dict[str, str] | None = None) -> bool:
    env = env if env is not None else {}
    return str(env.get("SITE_ENGINE_HTTP", "")).strip().lower() in {"1", "true", "yes", "on"}


def _is_control_path(method: str, path: str) -> bool:
    if method in {"POST", "PATCH", "PUT", "DELETE"}:
        return True
    return path.startswith(_CONTROL_GET_PREFIXES)


class _Handler(http.server.BaseHTTPRequestHandler):
    server_version = "SiteEngine"
    sys_version = ""

    # Журнал доступа пишется через logging сервера, а не в stderr процесса:
    # иначе вывод тестов и служебные записи смешиваются.
    def log_message(self, fmt: str, *args: Any) -> None:  # noqa: A003
        pass

    def _send(self, status: int, payload: dict) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        # Ответы управляющего API не кэшируются нигде: устаревшее состояние
        # задания хуже, чем отсутствие ответа.
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _error(self, status: int, code: str, message: str) -> None:
        self._send(status, {"error": {"code": code, "message": message}})

    def _read_body(self) -> dict | None:
        raw_length = self.headers.get("Content-Length")
        if raw_length is None:
            return {}
        try:
            length = int(raw_length)
        except ValueError:
            self._error(400, "invalid_length", "негодный Content-Length")
            return None
        if length < 0 or length > MAX_BODY_BYTES:
            self._error(413, "body_too_large", f"не более {MAX_BODY_BYTES} байт")
            return None
        raw = self.rfile.read(length)
        if not raw:
            return {}
        try:
            parsed = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            self._error(400, "invalid_json", "тело запроса не разобрано как JSON")
            return None
        if not isinstance(parsed, dict):
            self._error(400, "invalid_json", "ожидался объект JSON")
            return None
        return parsed

    def _cookies(self) -> dict[str, str]:
        raw = self.headers.get("Cookie") or ""
        jar: dict[str, str] = {}
        for chunk in raw.split(";"):
            name, sep, value = chunk.strip().partition("=")
            if sep and name:
                jar[name] = value
        return jar

    def _read_form(self) -> dict[str, str] | None:
        raw_length = self.headers.get("Content-Length")
        if raw_length is None:
            return {}
        try:
            length = int(raw_length)
        except ValueError:
            self._error(400, "invalid_length", "негодный Content-Length")
            return None
        if length < 0 or length > ADMIN_MAX_BODY_BYTES:
            self._html(413, "<p>Слишком большая форма.</p>")
            return None
        raw = self.rfile.read(length).decode("utf-8", errors="replace")
        return {k: v[-1] for k, v in parse_qs(raw, keep_blank_values=True).items()}

    def _text(self, status: int, body: str, content_type: str) -> None:
        payload = body.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(payload)

    def _html(self, status: int, body: str, extra: dict[str, str] | None = None) -> None:
        payload = body.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Cache-Control", "no-store")
        # Панель не встраивается никуда и не загружает ничего постороннего.
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Content-Security-Policy",
                         "default-src 'none'; style-src 'unsafe-inline'; form-action 'self'")
        for key, value in (extra or {}).items():
            self.send_header(key, value)
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(payload)

    def _handle_admin(self, method: str, path: str) -> None:
        app = getattr(self.server, "admin_app", None)
        if app is None:
            self._error(404, "not_found", "маршрут не найден")
            return
        form: dict[str, str] = {}
        if method == "POST":
            parsed = self._read_form()
            if parsed is None:
                return
            form = parsed
        try:
            response = app.handle(method, path, form=form, cookies=self._cookies())
        except Exception:  # noqa: BLE001
            self._html(500, "<p>Внутренняя ошибка.</p>")
            return
        self._html(response.status, response.html, response.headers)

    def _headers_dict(self) -> dict[str, str]:
        return {k.lower(): v for k, v in self.headers.items()}

    def _handle(self, method: str) -> None:
        parsed = urlparse(self.path)
        path = unquote(parsed.path)
        query = {k: v[-1] for k, v in parse_qs(parsed.query).items()}

        # Готовность отвечает без токена и без подробностей: её опрашивает
        # supervisor и балансировщик, а не человек. Подробности состояния
        # доступны по /api/v1/metrics, где нужен токен.
        if path == "/api/v1/ready":
            self._readiness()
            return

        жизнь = getattr(self.server, "lifecycle", None)
        if жизнь is not None and not жизнь.enter():
            # Служба сливается: новый запрос принимать нельзя, но и молчать
            # нельзя — балансировщик должен увидеть отказ, а не таймаут.
            self.send_response(503)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Connection", "close")
            self.send_header("Retry-After", "5")
            тело = b'{"error": {"code": "draining", "message": "\xd1\x81\xd0\xbb\xd1\x83\xd0\xb6\xd0\xb1\xd0\xb0 \xd0\xb7\xd0\xb0\xd0\xb2\xd0\xb5\xd1\x80\xd1\x88\xd0\xb0\xd0\xb5\xd1\x82\xd1\x81\xd1\x8f"}}'
            self.send_header("Content-Length", str(len(тело)))
            self.end_headers()
            self.wfile.write(тело)
            return
        try:
            self._serve(method, path, query)
        finally:
            if жизнь is not None:
                жизнь.leave()

    def _readiness(self) -> None:
        жизнь = getattr(self.server, "lifecycle", None)
        if жизнь is not None and not жизнь.accepting:
            self._json(503, {"ready": False, "reason": "draining"})
            return
        корень = getattr(self.server, "service_root", None)
        if корень is not None:
            плохие = [c for c in startup_protocol.check_state_dirs(корень)
                      if c.status == startup_protocol.FATAL]
            if плохие:
                # Каталог состояния мог стать недоступен уже после запуска.
                # Служба, отвечающая «готова» без доступа к очереди, обманывает
                # балансировщик.
                self._json(503, {"ready": False, "reason": "state_unavailable"})
                return
        self._json(200, {"ready": True})

    def _json(self, status: int, payload: dict) -> None:
        self._send(status, payload)

    def _serve(self, method: str, path: str, query: dict) -> None:
        if path == "/admin" or path.startswith("/admin/"):
            self._handle_admin(method, path)
            return

        body = self._read_body()
        if body is None:
            return

        try:
            if _is_control_path(method, path):
                # Для читающих управляющих маршрутов параметры приходят строкой
                # запроса. Приводится только limit: приводить всё подряд значит
                # однажды превратить идентификатор сайта «123» в число.
                merged = {**query, **body}
                if "limit" in merged and isinstance(merged["limit"], str):
                    try:
                        merged["limit"] = int(merged["limit"])
                    except ValueError:
                        self._error(400, "invalid_limit", "limit — целое число")
                        return
                response = self.server.control_api.handle(
                    method, path, body=merged, headers=self._headers_dict()
                )
                # Единственный маршрут с не-JSON представлением: сборщику нужен
                # текстовый формат. Разбирать JSON он не умеет, а заводить ради
                # этого второй адрес значит заводить и вторую проверку прав.
                if path == "/api/v1/metrics" and response.status == 200:
                    self._text(200, response.body.get("prometheus", ""),
                               "text/plain; version=0.0.4; charset=utf-8")
                    return
            else:
                if method != "GET":
                    self._error(405, "method_not_allowed", "маршрут только для чтения")
                    return
                response = self.server.read_api.handle(path, query)
        except Exception:  # noqa: BLE001
            # Подробности — в журнал процесса, наружу только факт.
            self._error(500, "internal_error", "внутренняя ошибка")
            return
        self._send(response.status, response.body)

    def do_GET(self) -> None:  # noqa: N802
        self._handle("GET")

    def do_POST(self) -> None:  # noqa: N802
        self._handle("POST")

    def do_PATCH(self) -> None:  # noqa: N802
        self._handle("PATCH")

    def do_DELETE(self) -> None:  # noqa: N802
        self._error(405, "method_not_allowed", "удаление не предусмотрено")

    def do_PUT(self) -> None:  # noqa: N802
        self._error(405, "method_not_allowed", "замена целиком не предусмотрена")


class _Server(http.server.ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True

    def __init__(self, address, handler, read_api, control_api, admin_app=None,
                 lifecycle=None, service_root=None):
        super().__init__(address, handler)
        self.read_api = read_api
        self.control_api = control_api
        self.admin_app = admin_app
        self.lifecycle = lifecycle if lifecycle is not None else Lifecycle()
        self.service_root = service_root


def build_server(
    config: ServerConfig,
    read_api: SiteEngineApi,
    control_api: ControlApi,
    admin_app: Any = None,
    lifecycle: Any = None,
    service_root: Any = None,
) -> _Server:
    """Сборка сервера.

    Публичная привязка требует явного разрешения, а не просто другого адреса:
    иначе строка «host: 0.0.0.0» в конфигурации проходит ревью как настройка
    сети, хотя означает выставление управляющего API наружу.
    """
    if config.host not in {"127.0.0.1", "::1", "localhost"} and not config.allow_public_bind:
        raise ValueError(
            f"привязка к {config.host} требует allow_public_bind=True: "
            "управляющий API не выставляется наружу по умолчанию"
        )
    return _Server((config.host, config.port), _Handler, read_api, control_api,
                   admin_app, lifecycle, service_root)


def serve(
    config: ServerConfig,
    read_api: SiteEngineApi,
    control_api: ControlApi,
    *,
    admin_app: Any = None,
    ready: threading.Event | None = None,
) -> None:
    server = build_server(config, read_api, control_api, admin_app)
    try:
        if ready is not None:
            ready.set()
        server.serve_forever(poll_interval=0.2)
    finally:
        server.server_close()


def _site_ids(root: Path) -> list[str]:
    directory = root / "config" / "site-profiles"
    return sorted(p.stem for p in directory.glob("*.json"))


def main(argv: list[str] | None = None) -> int:
    """Запуск службы.

    Отказ при выключенном флаге — не формальность: без него служба поднимается
    при любом случайном запуске, а узнают об этом по открытому порту.
    """
    import argparse
    import os

    parser = argparse.ArgumentParser(description="Site Engine API по HTTP")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8787)
    parser.add_argument("--root", default=".")
    parser.add_argument("--allow-public-bind", action="store_true",
                        help="выставить наружу; по умолчанию только 127.0.0.1")
    args = parser.parse_args(argv)

    env = dict(os.environ)
    if not http_enabled(env):
        print("SITE_ENGINE_HTTP не включён — служба не поднята", flush=True)
        return 64

    root = Path(args.root).resolve()

    # Протокол запуска — тот же, что выполняет выкладка и откат. Отдельного
    # облегчённого пути здесь нет: иначе откат поднимался бы не так, как потом
    # работает рабочая версия.
    отчёт = startup_protocol.run(root, env)
    print(отчёт.as_text(), flush=True)
    if not отчёт.ok:
        # Не подняться честнее, чем подняться и отвечать ошибкой на каждый
        # запрос: во втором случае supervisor считает службу исправной.
        return 70

    ids = _site_ids(root)
    if not ids:
        print(f"в {root}/config/site-profiles нет профилей", flush=True)
        return 65

    read_api = create_api(ids, root=root, env=env)
    control_api = ControlApi(root=root, env=env)
    admin_app = None
    if admin_enabled(env):
        from factory.site_engine.admin.app import AdminApp

        admin_app = AdminApp(read_api, control_api,
                             secure_cookie=args.host not in {"127.0.0.1", "::1", "localhost"})
        control_api.register_gauge(
            "site_engine_admin_sessions",
            lambda: [({}, admin_app.sessions.count())],
        )
    config = ServerConfig(host=args.host, port=args.port,
                          allow_public_bind=args.allow_public_bind)
    жизнь = Lifecycle(drain_timeout=float(env.get("SITE_ENGINE_DRAIN_SECONDS", "25")))
    server = build_server(config, read_api, control_api, admin_app,
                          lifecycle=жизнь, service_root=root)
    адрес = server.server_address
    состояние = "с админкой" if admin_app else "без админки"
    print(f"слушаю {адрес[0]}:{адрес[1]}, сайтов: {len(ids)}, {состояние}", flush=True)

    уведомитель = Notifier()
    поток = threading.Thread(target=server.serve_forever, kwargs={"poll_interval": 0.2},
                             daemon=True)
    поток.start()
    # READY после того, как сокет действительно принимает: сообщить о
    # готовности раньше значит пустить к себе трафик до готовности.
    уведомитель.ready(f"сайтов {len(ids)}, ограничений {len(отчёт.degraded)}")

    останов = threading.Event()

    def по_сигналу(signum, _frame):
        # Обработчик обязан быть коротким: разбор слива идёт в основном потоке.
        останов.set()

    signal.signal(signal.SIGTERM, по_сигналу)
    signal.signal(signal.SIGINT, по_сигналу)

    период = watchdog_interval()
    try:
        while not останов.is_set():
            # Ожидание с таймаутом, а не sleep: сигнал должен прерывать сразу.
            останов.wait(timeout=период if период > 0 else 1.0)
            if период > 0 and not останов.is_set():
                уведомитель.watchdog()
    finally:
        уведомитель.stopping("слив начатых запросов")
        print("получен сигнал остановки: перестаю принимать запросы", flush=True)
        жизнь.begin_drain()
        слито = жизнь.wait_drained()
        if not слито:
            print(f"слив не завершён за отведённое время, "
                  f"в работе осталось {жизнь.inflight}", flush=True)
        else:
            print("начатые запросы завершены", flush=True)
        server.shutdown()
        поток.join(timeout=10)
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
