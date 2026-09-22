#!/usr/bin/env python3
"""Проверить модерацию на живом animedia.icu тремя ролями.

Запускается из animedia-enable-moderator.sh под root, потому что ключ
модератора читается только root. Значение ключа никуда не печатается.

Проверяется ровно то, ради чего модератор включался:
  * обычный посетитель отправляет сообщение и видит его «на проверке»;
  * посторонний посетитель его не видит;
  * посторонний НЕ может одобрить;
  * модератор может одобрить;
  * одобренное становится публичным.

За собой убирает: тестовое сообщение удаляется модератором. Голоса и чужие
сообщения не трогаются.
"""
from __future__ import annotations

import http.cookiejar
import re
import ssl
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

SITE = "https://animedia.icu"
TITLE = "/title/master-lda-i-plameni-2/"
SUBJECT = "01a0b507-3280-7b2a-8af4-674dd73cff72"
SLUG = "master-lda-i-plameni-2"
MARK = f"проверка модерации {int(time.time())}"

fails: list[str] = []


def check(ok: bool, what: str, detail: str = "") -> None:
    print(f"   {'ok  ' if ok else 'FAIL'} {what}" + (f"  [{detail}]" if detail and not ok else ""))
    if not ok:
        fails.append(what)


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *a, **k):
        return None


class Visitor:
    def __init__(self, mod_key: str = "") -> None:
        self.jar = http.cookiejar.CookieJar()
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        self.opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(self.jar),
            urllib.request.HTTPSHandler(context=ctx),
            NoRedirect())
        if mod_key:
            self.jar.set_cookie(http.cookiejar.Cookie(
                0, "amd_mod", mod_key, None, False, "animedia.icu", True, False,
                "/", True, True, None, True, None, None, {}))

    def get(self, path: str) -> str:
        req = urllib.request.Request(SITE + path)
        with self.opener.open(req, timeout=20) as r:
            return r.read().decode("utf-8", "replace")

    def post(self, path: str, fields: dict) -> str:
        data = urllib.parse.urlencode(fields).encode()
        req = urllib.request.Request(SITE + path, data=data)
        try:
            with self.opener.open(req, timeout=20) as r:
                return r.headers.get("Location", "")
        except urllib.error.HTTPError as e:
            return e.headers.get("Location", "") or f"HTTP {e.code}"

    def csrf(self, page: str) -> str:
        m = re.search(r'name="csrf" value="([0-9a-f]+)"', page)
        return m.group(1) if m else ""


def main() -> int:
    try:
        with open("/etc/animedia/community-moderator.key", encoding="utf-8") as f:
            key = f.read().strip()
    except OSError as e:
        print(f"REFUSED: ключ модератора недоступен: {e}", file=sys.stderr)
        return 1
    if not key:
        print("REFUSED: ключ пуст", file=sys.stderr)
        return 1

    author, stranger, moderator = Visitor(), Visitor(), Visitor(mod_key=key)

    print("\n   -- обычный посетитель отправляет сообщение")
    page = author.get(TITLE)
    token = author.csrf(page)
    check(bool(token), "форма несёт CSRF-токен")
    where = author.post("/community/comment", {
        "slug": SLUG, "subject": SUBJECT, "back": TITLE,
        "name": "Проверка модерации", "text": MARK, "csrf": token})
    check("community=ok" in where, "сообщение принято", where)

    page = author.get(TITLE)
    check(MARK in page, "автор видит своё сообщение")
    check('data-comment-status="pending"' in page, "оно помечено как ожидающее")
    check(MARK not in stranger.get(TITLE), "посторонний его не видит")

    print("\n   -- посторонний пытается одобрить")
    spage = stranger.get(TITLE)
    check('data-moderation-queue="1"' not in spage, "посторонний не видит очередь")
    mpage = moderator.get(TITLE)
    ids = re.findall(r'data-moderation-id="([0-9a-f]+)"', mpage)
    check(bool(ids), "модератор видит очередь")
    if not ids:
        return 1
    # Найти именно своё сообщение в очереди.
    target = ""
    for cid in ids:
        block = mpage.split(f'data-moderation-id="{cid}"', 1)[1][:600]
        if MARK in block:
            target = cid
            break
    check(bool(target), "сообщение найдено в очереди")
    if not target:
        return 1

    where = stranger.post("/community/comment/decide", {
        "slug": SLUG, "subject": SUBJECT, "back": TITLE, "id": target,
        "decision": "approved", "csrf": stranger.csrf(spage)})
    check("community=forbidden" in where, "посторонний одобрить НЕ может", where)
    check(MARK not in stranger.get(TITLE), "после его попытки сообщение всё ещё скрыто")

    print("\n   -- модератор одобряет")
    where = moderator.post("/community/comment/decide", {
        "slug": SLUG, "subject": SUBJECT, "back": TITLE, "id": target,
        "decision": "approved", "csrf": moderator.csrf(mpage)})
    check("community=ok" in where, "решение модератора принято", where)
    check(MARK in Visitor().get(TITLE), "одобренное сообщение стало публичным")

    print("\n   -- уборка")
    mpage = moderator.get(TITLE)
    where = moderator.post("/community/comment/delete", {
        "slug": SLUG, "subject": SUBJECT, "back": TITLE, "id": target,
        "csrf": moderator.csrf(mpage)})
    check("community=ok" in where, "тестовое сообщение удалено", where)
    check(MARK not in Visitor().get(TITLE), "оно исчезло со страницы")

    print(f"\nMODERATION_VERDICT={'PASS' if not fails else 'FAIL'}")
    for f in fails:
        print(f"  - {f}")
    return 0 if not fails else 1


if __name__ == "__main__":
    raise SystemExit(main())
