"""Проверка галереи в Chromium: 4 ширины × 2 темы, axe, картинки, горизонтальный скролл, консоль.

Запуск: python3 -m http.server 8877 --bind 127.0.0.1 (из этой папки), затем python3 check_gallery.py > check-result.json
"""

import json
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

AXE = "/home/claude/wt-template-games-rpg/templates/games-rpg/qa/node_modules/axe-core/axe.min.js"
# тот же Chromium, что у приёмки вариантов (pip-пакет playwright новее скачанного браузера)
PW = Path.home() / ".cache/ms-playwright"
EXE = PW / "chromium_headless_shell-1234/chrome-headless-shell-linux64/chrome-headless-shell"
BASE = "http://127.0.0.1:8877/"
CARDS = 30
SCROLL = """async () => { for (let y = 0; y < document.body.scrollHeight; y += innerHeight / 2) {
  window.scrollTo(0, y); await new Promise(r => setTimeout(r, 40)); } }"""
BROKEN = "[...document.images].filter(i => !i.complete || i.naturalWidth === 0).length"
AXE_RUN = """async () => (await axe.run(document, {runOnly: {type: 'tag', values:
  ['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa', 'wcag22aa', 'best-practice']}})).violations
  .map(x => x.id + ':' + x.nodes.length)"""


def check(br, width, height, scheme):
    ctx = br.new_context(viewport={"width": width, "height": height}, color_scheme=scheme)
    pg = ctx.new_page()
    errs = []
    pg.on("console", lambda m, errs=errs: m.type == "error" and errs.append(m.text))
    resp = pg.goto(BASE, wait_until="networkidle")
    pg.evaluate(SCROLL)
    pg.wait_for_load_state("networkidle")
    pg.wait_for_timeout(300)
    res = {
        "status": resp.status,
        "hscroll": pg.evaluate("document.documentElement.scrollWidth > innerWidth"),
        "cards": pg.locator("article.v").count(),
        "recs": pg.locator(".rec").count(),
        "broken_img": pg.evaluate(BROKEN),
        "console": errs,
    }
    pg.add_script_tag(path=AXE)
    res["axe"] = pg.evaluate(AXE_RUN)
    ctx.close()
    return res


def main():
    out = {}
    with sync_playwright() as p:
        br = p.chromium.launch(executable_path=str(EXE))
        for width, height in ((320, 700), (390, 844), (768, 1000), (1440, 900)):
            for scheme in ("light", "dark"):
                out[f"{width}:{scheme}"] = check(br, width, height, scheme)
        br.close()
    print(json.dumps(out, ensure_ascii=False, indent=1))
    bad = [
        k
        for k, r in out.items()
        if r["status"] != 200 or r["hscroll"] or r["cards"] != CARDS or r["broken_img"] or r["console"] or r["axe"]
    ]
    print("bad:", bad, file=sys.stderr)
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
