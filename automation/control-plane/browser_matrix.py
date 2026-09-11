#!/usr/bin/env python3
"""Браузерная матрица: Chromium и Firefox, desktop и mobile.

Проверяется только отсутствие публичной деградации. Сайты не изменяются,
формы не отправляются, ничего не кликается кроме перехода по адресу.

HTTP-клиент браузером не является: здесь запускается настоящий движок и
исполняется JavaScript, поэтому пустая страница, собираемая скриптом,
будет видна, а для curl выглядела бы исправным ответом.
"""
from __future__ import annotations

import json, sys
from pathlib import Path
from playwright.sync_api import sync_playwright

ДОМЕНЫ = ["lordfilm47.space", "yummyani.site", "zonafilm.space", "animedia.icu"]
ВИДЫ = [("desktop", 1366, 768), ("mobile", 390, 844)]
ОТЧЁТ = Path("/srv/site-factory/control-plane-contracts/evidence/browser-matrix.json")

провалы: list[str] = []
строки: list[dict] = []


def проверить(page, домен: str, движок: str, вид: str) -> dict:
    ответ = page.goto(f"https://{домен}/", wait_until="domcontentloaded",
                      timeout=45000)
    код = ответ.status if ответ else 0
    page.wait_for_timeout(800)
    ссылок = page.locator("a[href]").count()
    текст = (page.locator("body").inner_text(timeout=10000) or "").strip()
    ошибки = page.evaluate("() => window.__errs ? window.__errs.length : 0")
    ок = код == 200 and ссылок >= 5 and len(текст) >= 200
    з = {"domain": домен, "engine": движок, "viewport": вид, "http": код,
         "links": ссылок, "text_len": len(текст), "js_errors": ошибки,
         "pass": ок}
    if not ок:
        провалы.append(f"{движок}/{вид}/{домен}")
    return з


def main() -> int:
    with sync_playwright() as pw:
        for движок, запуск in (("chromium", pw.chromium), ("firefox", pw.firefox)):
            бр = запуск.launch(headless=True)
            try:
                for вид, w, h in ВИДЫ:
                    ctx = бр.new_context(viewport={"width": w, "height": h},
                                         ignore_https_errors=False)
                    page = ctx.new_page()
                    page.add_init_script(
                        "window.__errs=[];addEventListener('error',"
                        "e=>window.__errs.push(String(e.message)))")
                    for д in ДОМЕНЫ:
                        try:
                            з = проверить(page, д, движок, вид)
                        except Exception as e:  # noqa: BLE001
                            з = {"domain": д, "engine": движок, "viewport": вид,
                                 "http": 0, "error": type(e).__name__,
                                 "pass": False}
                            провалы.append(f"{движок}/{вид}/{д}")
                        строки.append(з)
                        print("  %-10s %-8s %-22s HTTP %-4s ссылок %-4s текст %-6s %s"
                              % (движок, вид, д, з.get("http"), з.get("links", "-"),
                                 з.get("text_len", "-"),
                                 "PASS" if з["pass"] else "FAIL"), flush=True)
                    ctx.close()
            finally:
                бр.close()
    итог = {"verdict": "PASS" if not провалы else "FAIL",
            "engines": ["chromium", "firefox"],
            "viewports": [v[0] for v in ВИДЫ],
            "checks": len(строки), "failures": провалы,
            "public_mutations": 0, "rows": строки}
    ОТЧЁТ.parent.mkdir(parents=True, exist_ok=True)
    ОТЧЁТ.write_text(json.dumps(итог, ensure_ascii=False, indent=1),
                     encoding="utf-8")
    print("\n  проверок: %d, вердикт: %s" % (len(строки), итог["verdict"]))
    return 0 if not провалы else 1


if __name__ == "__main__":
    sys.exit(main())
