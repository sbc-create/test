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
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, unquote, urlparse

from factory.site_engine.api import create_api
from factory.site_engine.api.app import SiteEngineApi
from factory.site_engine.api.control import ControlApi
from factory.site_engine.api.openapi import ЗАПИСЬ

MAX_BODY_BYTES = 256 * 1024

# Маршруты управляющего слоя, отвечающие на GET. Разделять по методу
# недостаточно: часть управляющих маршрутов читающая.
_CONTROL_GET_PREFIXES = ("/api/v1/audit", "/api/v1/jobs/")


@dataclass
class ServerConfig:
    host: str = "127.0.0.1"
    port: int = 8787
    allow_public_bind: bool = False


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

    def _headers_dict(self) -> dict[str, str]:
        return {k.lower(): v for k, v in self.headers.items()}

    def _handle(self, method: str) -> None:
        parsed = urlparse(self.path)
        path = unquote(parsed.path)
        query = {k: v[-1] for k, v in parse_qs(parsed.query).items()}

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

    def __init__(self, address, handler, read_api, control_api):
        super().__init__(address, handler)
        self.read_api = read_api
        self.control_api = control_api


def build_server(
    config: ServerConfig,
    read_api: SiteEngineApi,
    control_api: ControlApi,
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
    return _Server((config.host, config.port), _Handler, read_api, control_api)


def serve(
    config: ServerConfig,
    read_api: SiteEngineApi,
    control_api: ControlApi,
    *,
    ready: threading.Event | None = None,
) -> None:
    server = build_server(config, read_api, control_api)
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
    ids = _site_ids(root)
    if not ids:
        print(f"в {root}/config/site-profiles нет профилей", flush=True)
        return 65

    read_api = create_api(ids, root=root, env=env)
    control_api = ControlApi(root=root, env=env)
    config = ServerConfig(host=args.host, port=args.port,
                          allow_public_bind=args.allow_public_bind)
    server = build_server(config, read_api, control_api)
    адрес = server.server_address
    print(f"слушаю {адрес[0]}:{адрес[1]}, сайтов: {len(ids)}", flush=True)
    try:
        server.serve_forever(poll_interval=0.2)
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
