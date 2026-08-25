"""Точка входа панели: ``python3 -m factory.secret_hub.panel serve``.

Запускается unit'ом от непривилегированной учётной записи. Root здесь не
нужен и, более того, нежелателен: панель не должна уметь ничего, кроме как
спросить хаб и передать ему введённое значение.
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="factory.secret_hub.panel",
                                     description="Веб-панель Secret Hub")
    parser.add_argument("action", choices=["serve"])
    parser.add_argument("--host")
    parser.add_argument("--port", type=int)
    args = parser.parse_args(argv)

    if os.geteuid() == 0:
        # Панель принимает запросы из интернета. Процессу с такими правами
        # нечего делать под root: всё привилегированное умеет хаб, и это
        # разделение — главная причина, по которой панель вообще существует
        # отдельным процессом.
        print("Панель не запускается от root: привилегированные операции "
              "выполняет сервис Secret Hub.", file=sys.stderr)
        print("нужно: systemctl start site-factory-secret-panel.service", file=sys.stderr)
        return 3

    from factory.secret_hub.panel.server import PanelConfig, serve
    from factory.secret_hub.registry import load as load_config

    config = load_config()
    form = config.public_form
    if form is None:
        print("[BLOCKED_INPUT] public_form не описан в config/secret-hub.json.",
              file=sys.stderr)
        return 3

    panel = PanelConfig(
        base_path=form.path,
        server_name=form.server_name,
        socket_path=config.socket_path,
        state_dir=Path(form.panel_state_dir),
        host=args.host or "127.0.0.1",
        port=args.port or form.loopback_port,
    )
    print(f"панель слушает {panel.host}:{panel.port}, публичный адрес {form.url}",
          file=sys.stderr, flush=True)
    try:
        serve(panel)
    except KeyboardInterrupt:
        return 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
