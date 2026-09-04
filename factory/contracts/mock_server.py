"""Mock-сервер канонических фикстур: шаблон собирается без живой CMS.

Правило контракта — шаблону запрещены прямые обращения к БД, очередям и raw HTTP
к CMS. Значит у него должен быть источник данных, поднимаемый одной командой и
не зависящий ни от чего: без него «независимая сборка шаблона» остаётся словами,
а лента упирается в чужой стенд.

Разбор адреса вынесен в чистую функцию `resolve`. Проверять маршрутизацию,
поднимая настоящий порт, значит получить тест, который падает от занятого порта
и таймаутов, — то есть мигающий тест вместо проверки логики.

Зависимостей нет намеренно: стандартной библиотеки достаточно, а лишний пакет в
шаблонной ленте — это ещё одна причина, по которой сборка не воспроизведётся.
"""

from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any

from factory.contracts.fixtures import EDGES, STATES, VIEW_MODELS, all_fixtures, edge_fixture, fixture

JSON_HEADERS = {"content-type": "application/json; charset=utf-8"}


def resolve(path: str) -> tuple[int, dict[str, Any]]:
    """Адрес → (код, тело). Чистая функция: ни сети, ни состояния.

    Поддерживается:
      /health                      — живость
      /viewmodels                  — перечень имён и состояний
      /fixtures                    — весь набор разом
      /viewmodel/<имя>             — состояние normal
      /viewmodel/<имя>/<состояние> — конкретное состояние
      /viewmodel/<имя>/edge/<край> — крайний случай
    """
    parts = [p for p in path.split("?")[0].strip("/").split("/") if p]

    if not parts or parts == ["health"]:
        return 200, {"status": "ok", "fixtures": len(all_fixtures())}

    if parts == ["viewmodels"]:
        return 200, {"view_models": list(VIEW_MODELS), "states": list(STATES), "edges": list(EDGES)}

    if parts == ["fixtures"]:
        return 200, all_fixtures()

    if parts[0] != "viewmodel" or len(parts) < 2:
        return 404, {"error": "неизвестный адрес", "path": path}

    name = parts[1]
    try:
        if len(parts) == 2:
            return 200, fixture(name)
        if len(parts) == 3:
            return 200, fixture(name, parts[2])
        if len(parts) == 4 and parts[2] == "edge":
            return 200, edge_fixture(name, parts[3])
    except KeyError as error:
        # Опечатка в имени обязана быть видна кодом ответа, а не пустым телом:
        # молчаливая пустота выглядит как «данных нет» и уводит расследование.
        return 404, {"error": str(error)}
    return 404, {"error": "неизвестный адрес", "path": path}


class _Handler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:  # noqa: N802 - имя задано базовым классом
        status, payload = resolve(self.path)
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        for key, value in JSON_HEADERS.items():
            self.send_header(key, value)
        self.send_header("content-length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *_args: Any) -> None:
        """Тишина по умолчанию: сервер поднимают внутри прогонов тестов."""


def serve(host: str = "127.0.0.1", port: int = 8787) -> None:  # pragma: no cover - точка входа
    server = HTTPServer((host, port), _Handler)
    print(f"mock-сервер фикстур: http://{host}:{port}  (наборов: {len(all_fixtures())})")
    server.serve_forever()


if __name__ == "__main__":  # pragma: no cover
    import argparse

    parser = argparse.ArgumentParser(description="Mock-сервер канонических фикстур")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8787)
    args = parser.parse_args()
    serve(args.host, args.port)
