"""Проверка ширин: все URL sitemap × 320/390/768/1440 — горизонтальный скролл, обрезанные подсказки,
href="#", зоны нажатия <24 px, вложенные ссылки, ошибки консоли. Запуск: python3 qa/viewports.py <порт> [доп. URL…]."""

import json
import re
import sys
import urllib.request
from pathlib import Path

from playwright.sync_api import sync_playwright

PORT = int(sys.argv[1])
BASE = f"http://127.0.0.1:{PORT}"
EXTRA = sys.argv[2:]
sm = urllib.request.urlopen(BASE + "/sitemap.xml").read().decode()
urls = [re.sub(r"^https?://[^/]+", "", u) for u in re.findall(r"<loc>(.*?)</loc>", sm)] + EXTRA
EXE = (
    Path.home()
    / ".cache/ms-playwright/chromium_headless_shell-1234/chrome-headless-shell-linux64/chrome-headless-shell"
)
CHECK = """() => {
 const out = {hscroll: document.documentElement.scrollWidth > innerWidth, cut: [], hash: [], small: [], nested: 0};
 const c = document.createElement('canvas').getContext('2d');
 for (const i of document.querySelectorAll('input[placeholder]')) { const s = getComputedStyle(i);
   if (s.display === 'none' || !i.offsetWidth) continue;
   c.font = `${s.fontWeight} ${s.fontSize} ${s.fontFamily}`;
   const room = i.clientWidth - parseFloat(s.paddingLeft) - parseFloat(s.paddingRight);
   if (c.measureText(i.placeholder).width > room + 1) out.cut.push(i.placeholder + ' ' + Math.round(room)); }
 for (const a of document.querySelectorAll('a[href="#"], a:not([href])')) out.hash.push(a.outerHTML.slice(0, 80));
 for (const el of document.querySelectorAll('a, button, input, select, summary, [role=button]')) {
   const r = el.getBoundingClientRect(); if (!r.width || getComputedStyle(el).visibility === 'hidden') continue;
   if (el.closest('p, li p, .prose, td') && el.tagName === 'A') continue;  // ссылки в тексте — исключение WCAG 2.5.8
   if (r.height < 24 || r.width < 24) out.small.push(el.tagName + ':' + (el.textContent || el.name || '').trim().slice(0, 30) + ' ' + Math.round(r.width) + 'x' + Math.round(r.height)); }
 out.nested = document.querySelectorAll('a a, a button, button a').length;
 return out; }"""
res = {"base": BASE, "urls": len(urls), "issues": {}, "console": []}
with sync_playwright() as p:
    br = p.chromium.launch(executable_path=str(EXE))
    for w, h in ((320, 640), (390, 844), (768, 1024), (1440, 900)):
        pg = br.new_page(viewport={"width": w, "height": h})
        pg.on(
            "console",
            lambda m, w=w, pg=pg: m.type == "error"
            and "404" not in m.text
            and res["console"].append(f"{w} {pg.url} {m.text}"),
        )
        for u in urls:
            r = pg.goto(BASE + u)
            o = pg.evaluate(CHECK)
            o["status"] = r.status
            bad = {k: v for k, v in o.items() if v and k != "status"}
            if o["status"] != 200 and u not in EXTRA:
                bad["status"] = o["status"]
            if bad:
                res["issues"][f"{w} {u}"] = bad
        pg.close()
    br.close()
small = sorted({s for v in res["issues"].values() for s in v.get("small", [])})
print(
    json.dumps(
        {
            "urls": len(urls),
            "pages_with_issues": len(res["issues"]),
            "kinds": sorted({k for v in res["issues"].values() for k in v}),
            "small_targets": small[:15],
            "cut": sorted({c for v in res["issues"].values() for c in v.get("cut", [])}),
            "hscroll": [k for k, v in res["issues"].items() if v.get("hscroll")][:10],
            "hash": sorted({c for v in res["issues"].values() for c in v.get("hash", [])})[:5],
            "console": res["console"][:5],
        },
        ensure_ascii=False,
        indent=1,
    )
)
