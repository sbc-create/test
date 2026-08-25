"""Запуск одноразового приёма. Вызывается root-сценарием, не человеком.

Печатает только состояние: код доступа печатает сценарий, а не этот процесс,
чтобы код не проходил через лишние руки.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

from factory.lords import web_intake


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="одноразовый приём учётных данных Lords")
    parser.add_argument("--code", required=True, help="одноразовый код (передаётся сценарием)")
    parser.add_argument("--port", type=int, default=0)
    parser.add_argument("--ttl", type=int, default=web_intake.DEFAULT_TTL_SECONDS)
    parser.add_argument("--token-file", required=True)
    parser.add_argument("--publisher-file", required=True)
    parser.add_argument("--probe-url", required=True)
    parser.add_argument("--port-file", required=True,
                        help="куда записать выбранный порт для nginx")
    parser.add_argument("--result-file", required=True,
                        help="куда записать итог приёма (без секретов)")
    parser.add_argument("--marker", default="",
                        help="уникальная метка формы: по ней сценарий убеждается,\nчто отвечает именно приёмник, а не сайт")
    args = parser.parse_args(argv)

    intake = web_intake.Intake(
        code=args.code,
        token_file=Path(args.token_file),
        publisher_file=Path(args.publisher_file),
        probe_url=args.probe_url,
        ttl_seconds=args.ttl,
        marker=args.marker,
    )

    accepted = {"done": False}

    def on_accept() -> None:
        accepted["done"] = True

    server, port = web_intake.serve(intake, port=args.port, on_accept=on_accept)
    Path(args.port_file).write_text(str(port), encoding="utf-8")
    print(f"intake: слушает 127.0.0.1:{port}", flush=True)

    try:
        while not accepted["done"]:
            if intake.expired():
                intake.state = web_intake.STATE_EXPIRED
                break
            if intake.state == web_intake.STATE_LOCKED:
                break
            time.sleep(0.5)
    finally:
        server.shutdown()
        server.server_close()

    # Дать обработчику дописать ответ браузеру перед снятием endpoint.
    if accepted["done"]:
        time.sleep(1.0)

    result = {
        "state": intake.state,
        "accepted": accepted["done"],
        "attempts": intake.attempts,
    }
    Path(args.result_file).write_text(json.dumps(result, ensure_ascii=False), encoding="utf-8")
    print(f"intake: завершён, состояние {intake.state}", flush=True)
    return 0 if accepted["done"] else 1


if __name__ == "__main__":
    sys.exit(main())
