"""Браузерная приёмка food-appliances: сценарии (табло → шаг, поиск по режиму, без JS), axe-core, скриншоты, метрики (лаб.)."""

from __future__ import annotations

import argparse
import json
import subprocess
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
BASE = "http://127.0.0.1:8866"
AXE = ROOT / "qa" / "node_modules" / "axe-core" / "axe.min.js"
VIEW = {"mobile": {"width": 390, "height": 844}, "desktop": {"width": 1440, "height": 900}}
RECIPE = "/recept/plov-v-multivarke/"
CONSOLE = "/recept/zharkoe-v-multivarke/"  # шаг 2: «Выпечка» 15 минут по источнику
SHOTS = {
    "home": "/",
    "appliance": "/pribor/multivarka/",
    "category": "/pribor/aerogril/kurica/",
    "recipe": RECIPE,
    "recipe_console": CONSOLE,
    "mode": "/rezhim/multivarka-vypechka/",
    "guide": "/kak-chitat-rezhimy/",
}
AXE_PAGES = list(SHOTS.values()) + [
    "/recept/syrniki-v-aerogrile/",
    "/poisk/?q=тушение",
    "/poisk/?q=zzz",
    "/nesushchestvuet/",
]
PERF = """() => new Promise(res => { let lcp = 0, cls = 0;
  new PerformanceObserver(l => { for (const e of l.getEntries()) lcp = e.startTime; }).observe({type: 'largest-contentful-paint', buffered: true});
  new PerformanceObserver(l => { for (const e of l.getEntries()) if (!e.hadRecentInput) cls += e.value; }).observe({type: 'layout-shift', buffered: true});
  setTimeout(() => res({lcp_ms: Math.round(lcp), cls: +cls.toFixed(4)}), 1200); })"""


def run(shots: Path | None) -> dict:
    head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    res = {
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
            pg.on(
                "console",
                lambda m, v=v, pg=pg: m.type == "error" and res["console_errors"].append(f"{v}: {m.text} @ {pg.url}"),
            )
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
        pg.goto(BASE + "/")
        pg.keyboard.press("Tab")
        S["first_tab_skip"] = pg.evaluate("document.activeElement.className") == "skip"
        with pg.expect_navigation():
            pg.locator(".dev", has_text="Аэрогриль").click()
        S["device_opens_own_table"] = pg.url.endswith("/pribor/aerogril/") and all(
            t == "Аэрогриль" for t in pg.locator(".cmp td[data-label='Прибор']").all_inner_texts()
        )
        with pg.expect_navigation():
            pg.locator(".cmp tbody th a").first.click()
        S["table_row_opens_recipe"] = "/recept/" in pg.url
        pg.goto(BASE + CONSOLE)
        step2 = pg.locator("#shag-2")
        S["setting_chip_in_source_step"] = "«Выпечка»" in step2.locator(".set").inner_text()
        step2.locator(".timer").click()
        pg.wait_for_timeout(1300)
        S["timer_counts_down_15"] = step2.locator(".timer").inner_text().startswith("Осталось 14:")
        step2.locator(".timer").click()
        S["timer_stops"] = step2.locator(".timer").inner_text() == "Таймер 15 мин"
        marks = pg.locator("[data-step-done]")
        marks.nth(0).check()
        marks.nth(1).check()
        S["progress_counts"] = pg.locator("[data-progress]").inner_text().startswith("Сделано шагов: 2 из ")
        pg.reload()
        S["marks_persist_after_reload"] = marks.nth(0).is_checked() and marks.nth(1).is_checked()
        S["storage_keys_own_namespace"] = pg.evaluate("Object.keys(localStorage)") == [
            "fab.steps." + CONSOLE.strip("/").split("/")[-1]
        ]
        pg.click("[data-steps-reset]")
        S["reset_clears"] = not marks.nth(0).is_checked()
        pg.goto(BASE + "/")
        pg.fill("#fq", "тушение")
        with pg.expect_navigation():
            pg.press("#fq", "Enter")
        S["search_by_mode_results"] = pg.locator("main a[href^='/recept/']").count() > 0
        with pg.expect_navigation():
            pg.locator(".devices a", has_text="Режимы").click()
        S["modes_nav_opens_guide"] = pg.url.endswith("/kak-chitat-rezhimy/") and pg.locator("h1").count() == 1
        resp = pg.goto(BASE + "/nesushchestvuet/")
        S["real_404"] = resp.status == 404
        ctx.close()
        ctx = br.new_context(java_script_enabled=False)
        pg = ctx.new_page()
        pg.goto(BASE + RECIPE)
        S["nojs_steps_and_settings"] = (
            pg.locator("li[id^='shag-']").count() > 0 and pg.locator(".set__chip").count() > 0
        )
        S["nojs_timers_and_marks_hidden"] = (
            pg.locator(".timer").first.is_hidden() and pg.locator(".done").first.is_hidden()
        )
        pg.goto(BASE + "/poisk/?q=" + "аэрогриль")
        S["nojs_search_results"] = pg.locator("main a[href^='/recept/']").count() > 0
        ctx.close()
        br.close()
    res["actions"] = dict(S)
    return res


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--shots")
    ap.add_argument("--out")
    a = ap.parse_args()
    out = run(Path(a.shots) if a.shots else None)
    if a.out:
        Path(a.out).write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n")
    print(json.dumps(out["scenarios"], ensure_ascii=False))
    print("axe", {k: v for k, v in out["axe"].items() if k != "version" and v})
    print("console", out["console_errors"])
