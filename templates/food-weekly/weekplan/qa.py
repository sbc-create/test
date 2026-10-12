"""Браузерная приёмка food-weekly: сценарии (замена, список покупок, без JS), axe-core, скриншоты, метрики (лаб.)."""

from __future__ import annotations

import argparse
import json
import subprocess
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
BASE = "http://127.0.0.1:8849"
AXE = ROOT / "qa" / "node_modules" / "axe-core" / "axe.min.js"
VIEW = {"mobile": {"width": 390, "height": 844}, "desktop": {"width": 1440, "height": 900}}
PLAN = "/menyu/bystraya-nedelya-dlya-dvoih/"
SHOTS = {"home": "/", "catalog": "/menyu/", "week": PLAN, "day": PLAN + "den-3/", "shopping": PLAN + "pokupki/"}
AXE_PAGES = [
    "/",
    "/menyu/",
    PLAN,
    PLAN + "den-1/",
    PLAN + "pokupki/",
    "/kak-planirovat/",
    "/podborki/",
    "/podborki/supy-dlya-obedov/",
    PLAN + "?s=d1-dinner-0:plov-s-kuricej",
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
        pg.goto(BASE + PLAN + "pokupki/")
        before = pg.locator(".buy li").count()
        before_text = pg.locator(".buy").first.inner_text()
        pg.goto(BASE + PLAN)
        pg.locator(".swap summary").first.click()
        # первая замена: завтрак дня 1 (сырники) → ленивые вареники
        pg.locator(".swap select").first.select_option(value="d1-breakfast-0:lenivye-vareniki")
        with pg.expect_navigation():
            pg.locator(".swap button").first.click()
        S["swap_url_has_zamena_or_s"] = ("s=" in pg.url) or ("zamena=" in pg.url)
        S["swapped_marker"] = pg.locator(".dish--swapped").count()
        pg.click("text=Список покупок (с заменами)")
        S["shopping_after_swap_url"] = "zamena=" in pg.url
        S["shopping_rows_before_after"] = [before, pg.locator(".buy li").count()]
        S["shopping_changed_after_swap"] = pg.locator(".buy").first.inner_text() != before_text
        pg.locator(".buy input").first.check()
        pg.reload()
        S["bought_mark_persists"] = pg.locator(".buy input").first.is_checked()
        pg.goto(BASE + PLAN + "?s=d1-breakfast-0:plov-s-kuricej")
        S["invalid_swap_warning"] = pg.locator(".warn").count() >= 1
        pg.goto(BASE + "/")
        pg.keyboard.press("Tab")
        S["first_tab_skip"] = pg.evaluate("document.activeElement.className") == "skip"
        ctx.close()
        ctx = br.new_context(java_script_enabled=False)
        pg = ctx.new_page()
        pg.goto(BASE + PLAN)
        S["nojs_week_dishes"] = pg.locator(".dish").count()
        pg.goto(BASE + PLAN + "?s=d2-dinner-0:mintaj-v-slivkah")
        S["nojs_swap_works"] = pg.locator(".dish--swapped").count() >= 1
        ctx.close()
        br.close()
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
