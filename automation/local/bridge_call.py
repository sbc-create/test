"""Вызов инструмента моста MCP (127.0.0.1:9000) по JSON-RPC: python3 automation/local/bridge_call.py <tool> '<json>'.

Один и тот же путь у сессии редактора и у фонового запуска: мост — штатный
интерфейс очереди и публикации, прямой записи в хранилища нет.
"""
import json
import sys
import urllib.request

tool, args = sys.argv[1], json.loads(sys.argv[2] if len(sys.argv) > 2 else "{}")
req = urllib.request.Request(
    "http://127.0.0.1:9000/mcp",
    data=json.dumps({"jsonrpc": "2.0", "id": 1, "method": "tools/call",
                     "params": {"name": tool, "arguments": args}}).encode(),
    headers={"Content-Type": "application/json", "Accept": "application/json, text/event-stream"})
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
