"""Точка входа сервиса: `python3 -m factory.secret_hub serve`.

Отдельная от `factory.cli` намеренно. `factory secrets …` запускается сессией
агента и разговаривает с сервисом по сокету; этот модуль — сам сервис, и
запускает его только root-owned unit. Держать их в одной команде значило бы
сделать «поднять хаб в своём процессе» вопросом одного аргумента.
"""
from __future__ import annotations

import argparse
import os
import sys


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="factory.secret_hub",
                                     description="Сервис центрального Secret Hub")
    parser.add_argument("action", choices=["serve"])
    # Результат разбора не используется: у команды ровно одно действие. Разбор
    # нужен ради самой проверки — `python -m factory.secret_hub` без аргумента
    # или с чужим аргументом обязан отказаться, а не запустить сервис.
    parser.parse_args(argv)

    if os.geteuid() != 0:
        print("Сервис Secret Hub запускается только от root: он читает мастер-ключ и "
              "файлы секретов.", file=sys.stderr)
        print("нужно: systemctl start site-factory-secret-hub.service", file=sys.stderr)
        return 3

    from factory.errors import FactoryError
    from factory.secret_hub import service

    try:
        service.serve()
    except FactoryError as exc:
        print(f"[{exc.status}] {exc.reason}", file=sys.stderr)
        if exc.required_input:
            print(f"нужно: {exc.required_input}", file=sys.stderr)
        return 3
    except KeyboardInterrupt:
        return 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
