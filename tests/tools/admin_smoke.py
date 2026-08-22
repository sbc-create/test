#!/usr/bin/env python3
"""Проверка, что админка действительно поднимается и отвечает.

Ничего не «считается проверенным» без запуска: сервер стартует, страницы
запрашиваются по HTTP, ответы и коды фиксируются в артефакте. Дополнительно
проверяется, что в HTML не утекли секреты и что REST API не отдаёт данные
анонимному запросу.
"""
from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
APP = ROOT / "blueprints" / "payload-next-multisite" / "app"
ARTIFACT = ROOT / "var" / "artifacts" / "admin-smoke.json"


def free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def fetch(url: str, timeout: float = 120.0) -> tuple[int, str]:
    request = urllib.request.Request(url, headers={"Host": "site-a.localhost"})
    try:
        # Локальный стенд: прокси окружения к нему не относится.
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        with opener.open(request, timeout=timeout) as response:
            return response.status, response.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as error:
        return error.code, error.read().decode("utf-8", "replace")


def wait_for(port: int, deadline: float) -> bool:
    while time.time() < deadline:
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=2):
                return True
        except OSError:
            time.sleep(0.5)
    return False


def main() -> int:
    port = free_port()
    env = dict(os.environ)
    env["PORT"] = str(port)
    command = [
        sys.executable, str(ROOT / "tests/tools/with_app_env.py"),
        "--scope", "anime", "--cwd", str(APP), "--",
        str(APP / "node_modules/.bin/next"), "dev", "-p", str(port), "-H", "127.0.0.1",
    ]
    process = subprocess.Popen(command, cwd=ROOT, env=env, stdout=subprocess.PIPE,
                               stderr=subprocess.STDOUT, text=True)
    checks: list[dict[str, object]] = []
    try:
        if not wait_for(port, time.time() + 180):
            print("FAIL: сервер не открыл порт за 180 секунд")
            return 1

        status, body = fetch(f"http://127.0.0.1:{port}/admin")
        checks.append({"name": "GET /admin отвечает", "status": status, "ok": status == 200})

        secret = os.environ.get("PAYLOAD_SECRET", "")
        leaked = bool(secret) and secret in body
        checks.append({"name": "секрет не утёк в HTML админки", "ok": not leaked})
        password_leaked = "postgresql://" in body
        checks.append({"name": "строка подключения к БД не утекла в HTML", "ok": not password_leaked})

        russian = "Вход" in body or "Электронная почта" in body or "Пароль" in body or "Создать" in body
        checks.append({"name": "интерфейс админки русский", "ok": russian})

        api_status, api_body = fetch(f"http://127.0.0.1:{port}/api/posts?limit=100")
        payload_docs = 0
        try:
            payload_docs = len(json.loads(api_body).get("docs", []))
        except json.JSONDecodeError:
            payload_docs = -1
        checks.append({
            "name": "анонимный REST не отдаёт материалы сайтов",
            "status": api_status,
            "docs": payload_docs,
            "ok": payload_docs == 0,
        })
        if any(not check["ok"] for check in checks):
            # Лог сервера — часть доказательства: без него «500» ничего не объясняет.
            process.terminate()
            try:
                output = process.communicate(timeout=30)[0] or ""
            except subprocess.TimeoutExpired:
                process.kill()
                output = process.communicate()[0] or ""
            log_path = ROOT / "var" / "artifacts" / "admin-smoke-server.log"
            log_path.parent.mkdir(parents=True, exist_ok=True)
            log_path.write_text(output, encoding="utf-8")
            print("--- последние строки лога сервера ---")
            print("\n".join(output.splitlines()[-40:]))
    finally:
        process.terminate()
        try:
            process.wait(timeout=30)
        except subprocess.TimeoutExpired:
            process.kill()

    ARTIFACT.parent.mkdir(parents=True, exist_ok=True)
    ARTIFACT.write_text(json.dumps({"port": port, "checks": checks}, ensure_ascii=False, indent=2), encoding="utf-8")

    failed = [check for check in checks if not check["ok"]]
    for check in checks:
        print(("PASS  " if check["ok"] else "FAIL  ") + str(check["name"]) +
              (f" (status={check['status']})" if "status" in check else ""))
    print(f"\n{len(checks) - len(failed)}/{len(checks)} проверок пройдено; артефакт: {ARTIFACT.relative_to(ROOT)}")
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
