"""Браузерная приёмка food-baking: сценарии, axe-core, скриншоты, лабораторные метрики.

Метрики лабораторные (локальный preview, без троттлинга), не полевые.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
BASE = "http://127.0.0.1:8848"
AXE = ROOT / "qa" / "node_modules" / "axe-core" / "axe.min.js"
VIEW = {"mobile": {"width": 390, "height": 844}, "desktop": {"width": 1440, "height": 900}}
SHOTS = {
    "home": "/",
    "catalog": "/recepty/",
    "recipe": "/recept/keks-s-kabachkom-i-ananasom/",
    "dough": "/testo/zavarnoe/",
    "pitfalls": "/oshibki/zavarnoe/",
}
AXE_PAGES = [
    "/",
    "/recepty/",
    "/recepty/page/2/",
    "/recept/limonnyj-keks/",
    "/recept/pirozhnye-lebedi/",
    "/recept/tort-bez-vypechki-s-vinogradom/",
    "/recept/olivkovyj-hleb/",
    "/testo/",
    "/testo/keksovoe/",
    "/oshibki/zavarnoe/",
    "/teg/shokolad/",
    "/poisk/?q=zzz",
    "/nesushchestvuet/",
]
PERF = """() => new Promise(res => { let lcp = 0, cls = 0;
  new PerformanceObserver(l => { for (const e of l.getEntries()) lcp = e.startTime; }).observe({type: 'largest-contentful-paint', buffered: true});
  new PerformanceObserver(l => { for (const e of l.getEntries()) if (!e.hadRecentInput) cls += e.value; }).observe({type: 'layout-shift', buffered: true});
  setTimeout(() => res({lcp_ms: Math.round(lcp), cls: +cls.toFixed(4),
    bytes: performance.getEntriesByType('resource').reduce((s, r) => s + (r.transferSize || 0), performance.getEntriesByType('navigation')[0].transferSize || 0)}), 1200); })"""


def run(shots: Path | None) -> dict:
    head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    res = {
        "base": BASE,
        "commit_head": head,
        "at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "scenarios": {},
        "axe": {},
        "perf_lab": {},
        "console_errors": [],
        "screenshots": [],
    }
    S = res["scenarios"]
    exe = (
        Path.home()
        / ".cache/ms-playwright/chromium_headless_shell-1234/chrome-headless-shell-linux64/chrome-headless-shell"
    )
    with sync_playwright() as p:
        br = p.chromium.launch(executable_path=str(exe) if exe.exists() else None)
        for v, vp in VIEW.items():
            ctx = br.new_context(viewport=vp, locale="ru-RU", bypass_csp=True)  # bypass_csp — только для внедрения axe
            pg = ctx.new_page()
            pg.on("console", lambda m, v=v: m.type == "error" and res["console_errors"].append(f"{v}: {m.text}"))
            pg.on("pageerror", lambda e, v=v: res["console_errors"].append(f"{v}: {e}"))
            for name, path in SHOTS.items():
                pg.goto(BASE + path)
                res["perf_lab"][f"{v}:{name}"] = pg.evaluate(PERF)
                S[f"{v}:{name}:no_hscroll"] = pg.evaluate("document.documentElement.scrollWidth <= innerWidth")
                if shots:
                    shots.mkdir(parents=True, exist_ok=True)
                    f = shots / f"{name}-{v}.png"
                    pg.screenshot(path=str(f), full_page=True)
                    res["screenshots"].append(str(f))
            for path in AXE_PAGES:
                pg.goto(BASE + path)
                pg.add_script_tag(path=str(AXE))
                r = pg.evaluate("""async () => { const r = await axe.run(document, {runOnly: {type: 'tag', values:
                    ['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa', 'best-practice']}}); return {v: axe.version,
                    violations: r.violations.map(x => ({id: x.id, impact: x.impact, n: x.nodes.length,
                    sample: x.nodes[0] && x.nodes[0].target.join(' ')}))}; }""")
                res["axe"]["version"] = r["v"]
                res["axe"][f"{v}:{path}"] = r["violations"]
            ctx.close()
        ctx = br.new_context(viewport=VIEW["mobile"], locale="ru-RU")
        pg = ctx.new_page()
        pg.goto(BASE + "/recept/keks-s-kabachkom-i-ananasom/")
        pg.click(".timer")
        pg.wait_for_timeout(1300)
        S["timer_counts_down_from_source_80_min"] = pg.locator(".timer").first.inner_text()
        pg.locator(".weigh input").first.check()
        S["weigh_checkbox"] = pg.locator(".weigh input").first.is_checked()
        S["oven_temp_text"] = pg.locator(".oven dd").first.inner_text()
        pg.goto(BASE + "/recepty/")
        with pg.expect_navigation():
            pg.select_option("select[name=testo]", "zavarnoe")
        S["filter_zavarnoe_rows"] = pg.locator(".toc__row").count()
        pg.goto(BASE + "/recepty/?testo=zavarnoe&duhovka=net")
        S["filter_empty"] = pg.locator(".empty h2").inner_text() if pg.locator(".empty h2").count() else None
        pg.goto(BASE + "/poisk/?q=" + "  ЗАВАРНОЙ  ")
        S["search_case_spaces"] = pg.locator(".toc__row").count()
        pg.goto(BASE + "/poisk/?q=печенье")
        S["search_pechene"] = pg.locator(".toc__row").count()
        pg.goto(BASE + "/")
        pg.keyboard.press("Tab")
        S["first_tab_skip"] = pg.evaluate("document.activeElement.className") == "skip"
        ctx.close()
        ctx = br.new_context(java_script_enabled=False)
        pg = ctx.new_page()
        pg.goto(BASE + "/recept/pirozhnye-lebedi/")
        S["nojs_steps"] = pg.locator(".method li").count()
        S["nojs_pitfalls"] = pg.locator(".pitfall").count()
        S["nojs_timers_hidden"] = (
            pg.locator("[data-timers]").is_hidden() if pg.locator("[data-timers]").count() else True
        )
        ctx.close()
        br.close()
    return res


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--shots")
    ap.add_argument("--out")
    a = ap.parse_args(argv)
    res = run(Path(a.shots) if a.shots else None)
    txt = json.dumps(res, ensure_ascii=False, indent=1)
    if a.out:
        Path(a.out).write_text(txt + "\n")
    print(txt)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
