"""REQ-SEO-REGULAR: доставка отчётов в Telegram — без утечки токена и без повторов."""
from __future__ import annotations

import io
import json

from seo_operator import notify

TOKEN = "123456:SECRET-TOKEN-VALUE"


class FakeApi:
    def __init__(self, updates=None, fail=False):
        self.requests = []
        self.updates = updates or []
        self.fail = fail

    def __call__(self, req, timeout):
        self.requests.append(req)
        method = req.full_url.rsplit("/", 1)[-1]
        if self.fail:
            body = {"ok": False, "description": "Forbidden: bot was blocked by the user"}
        elif method == "getUpdates":
            body = {"ok": True, "result": self.updates}
        else:
            body = {"ok": True, "result": {"message_id": len(self.requests)}}
        return io.BytesIO(json.dumps(body).encode())


def _all_files(path):
    return "".join(p.read_text(encoding="utf-8") for p in path.rglob("*") if p.is_file())


def test_token_never_reaches_state_files(tmp_path):
    api = FakeApi(fail=True)
    bot = notify.Bot(TOKEN, opener=api)
    notify.test_message(bot, "42", state=tmp_path)
    notify.alerts(bot, "42", {"site:a|DOWN": "сайт лежит"}, state=tmp_path)
    assert TOKEN not in _all_files(tmp_path)
    assert "SECRET" not in _all_files(tmp_path)


def test_discover_lists_chats_and_sends_nothing(tmp_path):
    api = FakeApi(updates=[{"message": {"chat": {"id": 777, "type": "private", "first_name": "Владелец"},
                                        "text": "/start"}}])
    out = notify.discover(notify.Bot(TOKEN, opener=api), state=tmp_path)
    assert out["chats"][0]["chat_id"] == "777"
    assert [r.full_url.rsplit("/", 1)[-1] for r in api.requests] == ["getUpdates"]


def test_same_alert_is_sent_once_and_again_after_it_reappears(tmp_path):
    api = FakeApi()
    bot = notify.Bot(TOKEN, opener=api)
    first = notify.alerts(bot, "42", {"site:a|DOWN": "сайт лежит"}, state=tmp_path)
    second = notify.alerts(bot, "42", {"site:a|DOWN": "сайт лежит"}, state=tmp_path)
    assert first["new"] == 1 and second["new"] == 0 and second["suppressed"] == 1
    assert len(api.requests) == 1
    notify.alerts(bot, "42", {}, state=tmp_path)  # ошибка устранена
    again = notify.alerts(bot, "42", {"site:a|DOWN": "сайт лежит"}, state=tmp_path)
    assert again["new"] == 1 and len(api.requests) == 2


def test_failed_delivery_is_retried_next_time(tmp_path):
    bot = notify.Bot(TOKEN, opener=FakeApi(fail=True))
    assert notify.alerts(bot, "42", {"k": "v"}, state=tmp_path)["ok"] is False
    ok_bot = notify.Bot(TOKEN, opener=FakeApi())
    assert notify.alerts(ok_bot, "42", {"k": "v"}, state=tmp_path)["new"] == 1


def test_missing_daily_report_is_reported_not_silent(tmp_path):
    api = FakeApi()
    res = notify.daily(notify.Bot(TOKEN, opener=api), "42", today="2026-10-09", state=tmp_path,
                       reports=tmp_path / "none")
    assert res["ok"] is True
    body = api.requests[0].data.decode()
    assert "%D0%BD%D0%B5+%D1%81%D1%84%D0%BE%D1%80%D0%BC%D0%B8%D1%80%D0%BE%D0%B2%D0%B0%D0%BD" in body  # «не сформирован»


def test_without_credentials_directory_it_is_not_configured(monkeypatch):
    monkeypatch.delenv("CREDENTIALS_DIRECTORY", raising=False)
    try:
        notify._cred("telegram_bot_token")
    except notify.NotConfigured as exc:
        assert "LoadCredential" in str(exc)
    else:
        raise AssertionError("без LoadCredential токен не должен находиться")
