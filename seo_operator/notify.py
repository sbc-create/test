"""Доставка SEO-отчётов владельцу в Telegram.

Команды (`python3 -m seo_operator.cli notify <команда>`), все — из служб systemd,
которым токен приходит через LoadCredential:

* `discover` — кто написал боту `/start`: список чатов (id, тип, имя) в
  var/notify/chat-candidates.json. Сообщений не отправляет. Чат владельца
  подтверждает сам владелец, записывая его id в файл учётных данных.
* `test`    — тестовое сообщение в подтверждённый чат; доставка подтверждается
  ответом Telegram (`ok`, `message_id`).
* `daily`   — полный суточный отчёт: короткая сводка сообщением и файл .md.
* `alerts`  — только ошибки, требующие вмешательства. Одна и та же ошибка
  повторно не отправляется, пока не исчезнет и не появится снова.

Почасовые сводки в Telegram не уходят: они остаются в var/seo-regular/hourly.

Безопасность. Токен читается из $CREDENTIALS_DIRECTORY/telegram_bot_token и
нигде не печатается и не пишется: адрес запроса с токеном не попадает ни в
журнал, ни в текст исключения. Сессии агента токен не выдаётся вовсе.
"""
from __future__ import annotations

import datetime as dt
import json
import os
import urllib.error
import urllib.parse
import urllib.request
import uuid
from pathlib import Path
from typing import Any, Callable

REPO_ROOT = Path(__file__).resolve().parents[1]
STATE = REPO_ROOT / "var" / "notify"
API = "https://api.telegram.org"
LIMIT = 4000  # предел сообщения Telegram — 4096 знаков


class NotConfigured(RuntimeError):
    """Нет токена или подтверждённого чата. Причина — без значения секрета."""


def _cred(name: str) -> str:
    base = os.environ.get("CREDENTIALS_DIRECTORY")
    if not base:
        raise NotConfigured(f"нет CREDENTIALS_DIRECTORY: {name} выдаётся только службе через LoadCredential")
    path = Path(base) / name
    if not path.is_file():
        raise NotConfigured(f"учётные данные {name} не переданы службе")
    value = path.read_text(encoding="utf-8").strip()
    if not value:
        raise NotConfigured(f"учётные данные {name} пусты")
    return value


def _now() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _log(state: Path, **fields: Any) -> None:
    state.mkdir(parents=True, exist_ok=True)
    with (state / "deliveries.jsonl").open("a", encoding="utf-8") as fh:
        fh.write(json.dumps({"at": _now(), **fields}, ensure_ascii=False) + "\n")


class Bot:
    def __init__(self, token: str, *, opener: Callable[..., Any] | None = None) -> None:
        self._token = token
        self._open = opener or urllib.request.urlopen

    def call(self, method: str, *, data: bytes | None = None, content_type: str | None = None,
             timeout: int = 30) -> dict:
        # Адрес содержит токен: он не выходит за пределы этой функции.
        req = urllib.request.Request(f"{API}/bot{self._token}/{method}", data=data, method="POST" if data else "GET")
        if content_type:
            req.add_header("Content-Type", content_type)
        try:
            with self._open(req, timeout=timeout) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            try:
                body = json.loads(exc.read().decode("utf-8"))
            except (ValueError, OSError):
                body = {}
            return {"ok": False, "error_code": exc.code, "description": body.get("description", "HTTP error")}
        except (urllib.error.URLError, OSError) as exc:
            return {"ok": False, "description": f"сеть: {type(exc).__name__}"}

    def send(self, chat_id: str, text: str) -> dict:
        data = urllib.parse.urlencode({"chat_id": chat_id, "text": text[:LIMIT],
                                       "disable_web_page_preview": "true"}).encode()
        return self.call("sendMessage", data=data, content_type="application/x-www-form-urlencoded")

    def send_document(self, chat_id: str, path: Path, caption: str = "") -> dict:
        boundary = uuid.uuid4().hex
        parts = []
        for name, value in (("chat_id", chat_id), ("caption", caption[:1000])):
            parts.append(f'--{boundary}\r\nContent-Disposition: form-data; name="{name}"\r\n\r\n{value}\r\n'.encode())
        parts.append((f'--{boundary}\r\nContent-Disposition: form-data; name="document"; filename="{path.name}"\r\n'
                      "Content-Type: text/markdown\r\n\r\n").encode() + path.read_bytes() + b"\r\n")
        parts.append(f"--{boundary}--\r\n".encode())
        return self.call("sendDocument", data=b"".join(parts),
                         content_type=f"multipart/form-data; boundary={boundary}", timeout=60)


def discover(bot: Bot, state: Path = STATE) -> dict:
    res = bot.call("getUpdates")
    chats: dict[str, dict] = {}
    for upd in res.get("result") or []:
        msg = upd.get("message") or upd.get("my_chat_member") or {}
        chat = msg.get("chat") or {}
        if chat.get("id") is not None:
            chats[str(chat["id"])] = {"chat_id": str(chat["id"]), "type": chat.get("type"),
                                      "title": chat.get("title"), "username": chat.get("username"),
                                      "first_name": chat.get("first_name"),
                                      "last_text": (msg.get("text") or "")[:40]}
    out = {"at": _now(), "ok": res.get("ok", False), "description": res.get("description"),
           "chats": list(chats.values())}
    state.mkdir(parents=True, exist_ok=True)
    (state / "chat-candidates.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    _log(state, kind="discover", ok=out["ok"], chats=len(chats), description=out["description"])
    return out


def test_message(bot: Bot, chat_id: str, state: Path = STATE) -> dict:
    text = ("Тест доставки SEO-отчётов сети. Если вы видите это сообщение, канал работает: "
            "полный отчёт будет приходить в 09:00 МСК, ночью — только ошибки, требующие вмешательства.")
    res = bot.send(chat_id, text)
    _log(state, kind="test", ok=res.get("ok"), chat_id=chat_id,
         message_id=(res.get("result") or {}).get("message_id"), description=res.get("description"))
    return res


def _daily_summary(report_json: Path) -> str:
    r = json.loads(report_json.read_text(encoding="utf-8"))
    a = r.get("analytics") or {}
    issues = r.get("issues") or {}
    ch = r.get("changes") or {}
    mod = r.get("module") or {}
    lines = [f"SEO-сеть — отчёт за {r['date_msk']}",
             f"Учтён снимок аналитики: {str(a.get('snapshot', ''))[10:20] or 'нет'} ({a.get('status', '—')})",
             f"Проблемы сайтов: новых {len(issues.get('new') or [])}, сохраняются "
             f"{len(issues.get('persisting') or [])}, устранено {len(issues.get('resolved') or [])}"]
    for it in (issues.get("new") or [])[:5]:
        lines.append(f" • {it['domain']} {it['code']}")
    if ch:
        lines.append(f"Страницы: написано {len(ch.get('written') or [])}, оптимизировано "
                     f"{len(ch.get('optimized') or [])}, проверено на сайте {len(ch.get('verified') or [])}, "
                     f"эффект пока не установлен {len(ch.get('effect_pending') or [])}, измерен "
                     f"{len(ch.get('measured') or [])}")
    if mod:
        lines.append(f"SEO-модуль: найдено {mod.get('found')} → исправлено {mod.get('fixed')} → "
                     f"проверено {mod.get('verified')} → осталось {len(mod.get('remaining') or [])}")
    lines.append("Полный отчёт — во вложении.")
    return "\n".join(lines)


def _editor_runs(since: dt.datetime) -> list[dict]:
    log = REPO_ROOT / "var" / "editor-runs" / "runs.jsonl"
    out = []
    if log.is_file():
        for line in log.read_text(encoding="utf-8").splitlines():
            try:
                r = json.loads(line)
            except ValueError:
                continue
            at = dt.datetime.fromisoformat(r.get("finished_at", "1970-01-01T00:00:00Z").replace("Z", "+00:00"))
            if at >= since:
                out.append(r)
    return out


def daily(bot: Bot, chat_id: str, *, today: str | None = None, state: Path = STATE,
          reports: Path = REPO_ROOT / "var" / "seo-regular" / "reports" / "daily") -> dict:
    today = today or dt.datetime.now(dt.timezone(dt.timedelta(hours=3))).strftime("%Y-%m-%d")
    md, js = reports / f"{today}.md", reports / f"{today}.json"
    if not md.is_file() or not js.is_file():
        text = (f"SEO-сеть: суточный отчёт за {today} не сформирован к 09:00 МСК — "
                "проверьте seo-regular-daily (это ошибка, а не пустой день).")
        res = bot.send(chat_id, text)
        _log(state, kind="daily", ok=res.get("ok"), report=None, description=res.get("description"))
        return res
    runs = _editor_runs(dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=1))
    verdicts: dict[str, int] = {}
    for r in runs:
        verdicts[r.get("verdict", "?")] = verdicts.get(r.get("verdict", "?"), 0) + 1
    summary = _daily_summary(js) + f"\nФоновый редактор за сутки: {verdicts or 'запусков не было'}"
    res = bot.send(chat_id, summary)
    doc = bot.send_document(chat_id, md, caption=f"Полный SEO-отчёт {today}") if res.get("ok") else {}
    _log(state, kind="daily", ok=bool(res.get("ok") and doc.get("ok")), report=str(md),
         message_id=(res.get("result") or {}).get("message_id"),
         document_message_id=(doc.get("result") or {}).get("message_id"),
         description=res.get("description") or doc.get("description"))
    return {"ok": bool(res.get("ok") and doc.get("ok")), "summary": res, "document": doc}


def collect_alerts(now: dt.datetime | None = None) -> dict[str, str]:
    """Ошибки, требующие вмешательства. Ключ — устойчивый идентификатор ошибки."""
    now = now or dt.datetime.now(dt.timezone.utc)
    out: dict[str, str] = {}
    st = json.loads((REPO_ROOT / "var" / "seo-regular" / "state.json").read_text(encoding="utf-8"))
    for key, it in (st.get("open_issues_check") or {}).items():
        if it.get("severity") == "critical":
            out[f"site:{key}"] = f"Сайт {it['domain']}: {it['code']} — {it.get('detail', '')}"
    for r in _editor_runs(now - dt.timedelta(hours=3)):
        if r.get("verdict") == "INCOMPLETE" or r.get("model_exit") not in (0, None):
            out[f"editor:{r['run_id']}"] = (f"Фоновый редактор, запуск {r['run_id']}: {r.get('verdict')}, "
                                            f"выход модели {r.get('model_exit')}, шаги {r.get('steps')}")
    snaps = sorted((REPO_ROOT / "artifacts" / "analytics").glob("analytics-????-??-??.json"))
    if snaps:
        age = (now - dt.datetime.fromisoformat(snaps[-1].name[10:20]).replace(tzinfo=dt.timezone.utc)).days
        if age >= 2:
            out["analytics:stale"] = f"Снимок аналитики не обновлялся: последний {snaps[-1].name[10:20]}"
    return out


def alerts(bot: Bot, chat_id: str, current: dict[str, str], state: Path = STATE) -> dict:
    path = state / "sent-alerts.json"
    try:
        sent = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        sent = {}
    new = {k: v for k, v in current.items() if k not in sent}
    result = {"new": len(new), "suppressed": len(current) - len(new), "ok": True}
    if new:
        text = "SEO-сеть: требуется вмешательство\n" + "\n".join(f"• {v}" for v in new.values())
        res = bot.send(chat_id, text)
        result["ok"] = bool(res.get("ok"))
        _log(state, kind="alert", ok=res.get("ok"), keys=sorted(new),
             message_id=(res.get("result") or {}).get("message_id"), description=res.get("description"))
        if res.get("ok"):
            sent.update({k: _now() for k in new})
    # Исчезнувшая ошибка забывается: появится снова — будет новое уведомление.
    sent = {k: v for k, v in sent.items() if k in current}
    state.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(sent, ensure_ascii=False, indent=1), encoding="utf-8")
    return result


def main(argv: list[str]) -> int:
    cmd = argv[0] if argv else ""
    try:
        bot = Bot(_cred("telegram_bot_token"))
        if cmd == "discover":
            out = discover(bot)
            print(json.dumps({k: out[k] for k in ("ok", "description")} | {"chats": len(out["chats"])},
                             ensure_ascii=False))
            return 0 if out["ok"] else 69
        chat_id = _cred("telegram_chat_id")
        if cmd == "test":
            res = test_message(bot, chat_id)
        elif cmd == "daily":
            res = daily(bot, chat_id)
        elif cmd == "alerts":
            res = alerts(bot, chat_id, collect_alerts())
        else:
            print("команды: discover | test | daily | alerts")
            return 64
    except NotConfigured as exc:
        _log(STATE, kind=cmd or "?", ok=False, description=str(exc))
        print(json.dumps({"ok": False, "not_configured": str(exc)}, ensure_ascii=False))
        return 78
    print(json.dumps({"ok": res.get("ok"), "description": res.get("description")}, ensure_ascii=False))
    return 0 if res.get("ok") else 69
