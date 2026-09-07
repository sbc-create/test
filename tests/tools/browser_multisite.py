#!/usr/bin/env python3
"""Браузерная приёмка трёх сайтов: наполняет стенд, поднимает сервер, гоняет Playwright.

Сервер поднимается из production-сборки, а не в режиме разработки. Причина не в
скорости: dev-режим React требует eval(), запрещённый нашей CSP, и измерять на
нём производительность бессмысленно — такой сборки в production не будет.

Отчёт Playwright сохраняется в артефакт. Недоступный движок помечается пропуском
с причиной — «прогнали в трёх браузерах» без установленных браузеров не заявляется.
"""
from __future__ import annotations

import os
import socket
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

# Инструменты запускаются как сценарии, а не импортируются пакетом: путь к
# соседнему модулю добавляется явно.
sys.path.insert(0, str(Path(__file__).resolve().parent))

import stand_env  # noqa: E402

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
    # Заведомо «секретное» значение включено намеренно: его ищет в выдаче
    # `tests/e2e-multisite/player.spec.js` и требует, чтобы оно там не нашлось.
    env = stand_env.stand_environment(port=port, with_leak_canary=True)

    seeding = subprocess.run(
        [sys.executable, str(ROOT / "tests/tools/with_app_env.py"), "--scope", "anime", "--push", "--",
         str(APP / "node_modules/.bin/tsx"), str(APP / "tests" / "stand-seed.ts")],
        cwd=ROOT, env=env, capture_output=True, text=True, timeout=900, check=False,
    )
    if seeding.returncode != 0:
        print("FAIL: не удалось наполнить стенд")
        print(seeding.stdout[-3000:], seeding.stderr[-3000:])
        return 1

    build_env = dict(env)
    build_env["NEXT_DIST_DIR"] = ".next-acceptance"
    print("сборка приложения для приёмки…", flush=True)
    built = subprocess.run(
        [sys.executable, str(ROOT / "tests/tools/with_app_env.py"), "--scope", "anime",
         "--cwd", str(APP), "--", str(APP / "node_modules/.bin/next"), "build"],
        cwd=ROOT, env=build_env, capture_output=True, text=True, timeout=1800, check=False,
    )
    if built.returncode != 0:
        print("FAIL: сборка приложения не удалась")
        print((built.stdout + built.stderr)[-4000:])
        return 1

    server = subprocess.Popen(
        [sys.executable, str(ROOT / "tests/tools/with_app_env.py"), "--scope", "anime",
         "--cwd", str(APP), "--", str(APP / "node_modules/.bin/next"), "start",
         "-p", str(port), "-H", "127.0.0.1"],
        cwd=ROOT, env=build_env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
    )
    try:
        if not stand_env.wait_for_port(port):
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
