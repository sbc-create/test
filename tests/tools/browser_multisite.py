#!/usr/bin/env python3
"""Браузерная приёмка трёх сайтов: наполняет стенд, поднимает сервер, гоняет Playwright.

Отчёт Playwright сохраняется в артефакт. Недоступный движок помечается пропуском
с причиной — «прогнали в трёх браузерах» без установленных браузеров не заявляется.
"""
from __future__ import annotations

import os
import socket
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
APP = ROOT / "blueprints" / "payload-next-multisite" / "app"


def free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def main() -> int:
    chromium = Path(os.environ.get("FACTORY_CHROMIUM", "/opt/pw-browsers/chromium-1194/chrome-linux/chrome"))
    if not chromium.exists():
        print(f"SKIPPED: Chromium не найден по пути {chromium}; браузерная приёмка не выполнялась")
        return 2

    port = free_port()
    env = dict(os.environ)
    env.update({
        "PLAYER_PUBLISHER_ID_A": "stand-publisher-a",
        "PLAYER_PUBLISHER_ID_B": "stand-publisher-b",
        "PLAYER_PUBLISHER_ID_C": "stand-publisher-c",
        "PLAYER_MODE": "mock",
        "FACTORY_ENVIRONMENT": "staging",
        # Заведомо «секретное» значение: тест проверяет, что оно не попало в страницу.
        "CDNVIDEOHUB_API_TOKEN": "stand-content-api-token-must-not-leak",
        "FACTORY_MULTISITE_PORT": str(port),
    })

    seeding = subprocess.run(
        [sys.executable, str(ROOT / "tests/tools/with_app_env.py"), "--scope", "anime", "--",
         str(APP / "node_modules/.bin/tsx"), str(APP / "tests" / "stand-seed.ts")],
        cwd=ROOT, env=env, capture_output=True, text=True, timeout=900, check=False,
    )
    if seeding.returncode != 0:
        print("FAIL: не удалось наполнить стенд")
        print(seeding.stdout[-3000:], seeding.stderr[-3000:])
        return 1

    server = subprocess.Popen(
        [sys.executable, str(ROOT / "tests/tools/with_app_env.py"), "--scope", "anime",
         "--cwd", str(APP), "--", str(APP / "node_modules/.bin/next"), "dev", "-p", str(port), "-H", "127.0.0.1"],
        cwd=ROOT, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
    )
    try:
        deadline = time.time() + 180
        while time.time() < deadline:
            try:
                with socket.create_connection(("127.0.0.1", port), timeout=2):
                    break
            except OSError:
                time.sleep(0.5)
        else:
            print("FAIL: сервер не открыл порт")
            return 1

        result = subprocess.run(
            [str(ROOT / "node_modules/.bin/playwright"), "test", "-c", "playwright.multisite.config.js"],
            cwd=ROOT, env=env, text=True, check=False,
        )
        return result.returncode
    finally:
        server.terminate()
        try:
            output = server.communicate(timeout=30)[0] or ""
        except subprocess.TimeoutExpired:
            server.kill()
            output = server.communicate()[0] or ""
        log_path = ROOT / "var" / "artifacts" / "browser-multisite-server.log"
        log_path.parent.mkdir(parents=True, exist_ok=True)
        log_path.write_text(output, encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
