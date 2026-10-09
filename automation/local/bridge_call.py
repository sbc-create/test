"""Вызов инструмента моста MCP (127.0.0.1:9000) по JSON-RPC.

    python3 automation/local/bridge_call.py <tool> '<json>'


Один и тот же путь у сессии редактора и у фонового запуска: мост — штатный
интерфейс очереди и публикации, прямой записи в хранилища нет.

Запрос несёт ТОКЕН ДОВЕРИЯ из локального файла. Он отличает нашу сторону от
клиента моста: поле `author` называет сам вызывающий, поэтому правами оно быть
не может — Qwen прислал бы любое имя. Файл читается только с этого хоста, а
клиент MCP приходит подключением, файловой системы у него нет. Без токена мост
даёт права роли `qwen`: подготовку черновиков, но не изменения production.
"""

import json
import os
import pathlib
import sys
import urllib.request

tool, args = sys.argv[1], json.loads(sys.argv[2] if len(sys.argv) > 2 else "{}")


def токен() -> str:
    из_среды = os.environ.get("FACTORY_BRIDGE_TRUSTED_TOKEN", "").strip()
    if из_среды:
        return из_среды
    путь = os.environ.get("FACTORY_BRIDGE_TRUSTED_TOKEN_FILE", "").strip()
    файл = (pathlib.Path(путь) if путь
            else pathlib.Path(__file__).resolve().parents[2] / "var"
            / "bridge-trusted-token")
    try:
        return файл.read_text(encoding="utf-8").strip()
    except OSError:
        return ""


заголовки = {"Content-Type": "application/json",
             "Accept": "application/json, text/event-stream"}
значение = токен()
if значение:
    заголовки["X-Factory-Trusted"] = значение
req = urllib.request.Request(
    "http://127.0.0.1:9000/mcp",
    data=json.dumps(
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {"name": tool, "arguments": args},
        }
    ).encode(),
    headers=заголовки,
)
raw = urllib.request.urlopen(req, timeout=300).read().decode()
for line in raw.splitlines():
    if line.startswith("data:"):
        msg = json.loads(line[5:])
        res = msg.get("result") or msg
        for c in res.get("content") or []:
            if c.get("type") == "text":
                try:
                    print(json.dumps(json.loads(c["text"]), ensure_ascii=False, indent=1))
                except ValueError:
                    print(c["text"])
        if "error" in msg:
            print(json.dumps(msg["error"], ensure_ascii=False))
