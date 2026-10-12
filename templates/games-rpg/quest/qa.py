"""Браузерная приёмка games-rpg (party-planner): карта действий (результат, а не наличие кнопки), axe-core, скриншоты, метрики (лаб.)."""

from __future__ import annotations

import argparse
import json
import subprocess
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
BASE = "http://127.0.0.1:8860"
AXE = ROOT / "qa" / "node_modules" / "axe-core" / "axe.min.js"
VIEW = {"mobile": {"width": 390, "height": 844}, "desktop": {"width": 1440, "height": 900}}
QUEST = "/baldurs-gate-3/kvesty/kvest-spasti-halsina/"
SHOTS = {
    "home": "/",
    "party": "/otryad/?p=gale&p=karlach&p=shadowheart",
    "chars": "/baldurs-gate-3/personazhi/?sort=STR",
    "character": "/baldurs-gate-3/personazhi/gale/",
    "build": "/baldurs-gate-3/bildy/klass-voin/",
    "quest": QUEST,
}
AXE_PAGES = list(SHOTS.values()) + [
    "/baldurs-gate-3/bildy/",
    "/baldurs-gate-3/bildy/klass-volshebnik/",
    "/baldurs-gate-3/mehaniki/mehanika-preimushchestvo/",
    "/baldurs-gate-3/versiya/versiya-patch-8/",
    "/kak-my-rabotaem/",
    "/istochniki/",
    "/poisk/?q=Gale",
    "/poisk/?q=квантовый",
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
        "actions": {},
        "axe": {},
        "perf_lab": {},
        "console_errors": [],
        "screenshots": [],
    }
    A = res["actions"]
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
                if shots:
                    shots.mkdir(parents=True, exist_ok=True)
                    f = shots / f"{name}-{v}.png"
                    pg.screenshot(path=str(f), full_page=True)
                    res["screenshots"].append(str(f))
            for path in AXE_PAGES:
                pg.goto(BASE + path)
                pg.add_script_tag(path=str(AXE))
                r = pg.evaluate("""async () => { const r = await axe.run(document, {runOnly: {type: 'tag', values:
                    ['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa', 'wcag22aa', 'best-practice']}}); return {v: axe.version,
                    violations: r.violations.map(x => ({id: x.id, impact: x.impact, n: x.nodes.length,
                    sample: x.nodes[0] && x.nodes[0].target.join(' ')}))}; }""")
                res["axe"]["version"] = r["v"]
                res["axe"][f"{v}:{path}"] = r["violations"]
            ctx.close()

        # --- действия на телефоне, с проверкой результата ---
        ctx = br.new_context(viewport=VIEW["mobile"], locale="ru-RU")
        pg = ctx.new_page()
        pg.goto(BASE + "/")
        pg.keyboard.press("Tab")
        A["keyboard_first_tab_is_skip"] = pg.evaluate("document.activeElement.className") == "skip"
        pg.keyboard.press("Enter")
        A["skip_moves_focus_to_main"] = pg.evaluate("document.activeElement.id") == "main"
        A["no_last_party_initially"] = not pg.locator("[data-last-party]").is_visible()
        pg.locator("input[name=p][value=gale]").check()
        pg.locator("input[name=p][value=karlach]").check()
        with pg.expect_navigation():
            pg.click(".pf button")
        A["party_submits"] = "p=gale" in pg.url and "p=karlach" in pg.url
        A["party_best_rows"] = pg.locator(".best tbody tr").count() == 6
        A["party_tie_lists_both"] = (
            "Gale, Karlach" in pg.locator(".best tbody tr", has_text="Телосложение").inner_text()
        )
        pg.goto(BASE + "/")
        A["last_party_link_on_home"] = (
            pg.locator("[data-last-party] a").get_attribute("href") == "/otryad/?p=gale&p=karlach"
        )
        with pg.expect_navigation():
            pg.locator(".hd__nav a", has_text="Персонажи").click()
        with pg.expect_navigation():
            pg.locator(".cmp thead a", has_text="Сила").click()
        A["table_sort_by_header"] = "sort=STR" in pg.url and pg.locator(".cmp tbody th a").first.inner_text() in (
            "Karlach",
            "Lae'zel",
        )
        with pg.expect_navigation():
            pg.locator(".cmp tbody th a", has_text="Gale").click()
        A["abilities_shown"] = pg.locator(".abil div").count() == 6
        with pg.expect_navigation():
            pg.click(".patch")
        A["patch_badge_opens_version"] = pg.url.endswith("/versiya/versiya-patch-8/")
        pg.goto(BASE + "/baldurs-gate-3/bildy/klass-voin/")
        A["build_progression_rows"] = pg.locator(".prog tbody tr").count()
        A["build_no_hscroll_on_phone"] = pg.evaluate("document.documentElement.scrollWidth <= innerWidth")
        pg.goto(BASE + QUEST)
        boxes = pg.locator(".check input")
        boxes.nth(0).check()
        boxes.nth(2).check()
        pg.reload()
        A["quest_stages_persist"] = (
            boxes.nth(0).is_checked() and boxes.nth(2).is_checked() and not boxes.nth(1).is_checked()
        )
        pg.click("[data-check-reset]")
        pg.reload()
        A["quest_stages_reset"] = not boxes.nth(0).is_checked()
        pg.evaluate(
            "window.__printed = 0; window.print = () => { window.__printed++; }; 0"
        )  # «; 0»: не возвращать функцию
        pg.click("[data-print]")
        A["print_button_calls_print"] = pg.evaluate("window.__printed") == 1
        pg.emulate_media(media="print")
        A["print_hides_navigation"] = not pg.locator(".hd").is_visible() and pg.locator(".check").is_visible()
        pg.emulate_media(media="screen")
        pg.locator("a.ref").first.click()
        A["ref_jumps_to_source"] = pg.evaluate("location.hash") == "#ist-1"
        pg.goto(BASE + "/")
        pg.fill("#fq", "Gale")
        with pg.expect_navigation():
            pg.press("#fq", "Enter")
        A["search_keyboard_results"] = pg.locator(".row").count()
        with pg.expect_navigation():
            pg.click(".find--page .reset")
        A["search_clear"] = pg.locator("#sq").input_value() == ""
        pg.goto(BASE + "/poisk/?q=квантовый")
        A["search_no_results_message"] = pg.locator(".empty h2").inner_text() == "Ничего не нашлось"
        pg.goto(BASE + "/nesushchestvuet/")
        A["404_has_search_and_home"] = (
            pg.locator(".nf form").count() == 1 and pg.locator(".nf a[href='/']").count() == 1
        )
        pg.go_back()
        A["history_back_returns"] = "/poisk/" in pg.url
        ctx.close()
        ctx = br.new_context(java_script_enabled=False)
        pg = ctx.new_page()
        pg.goto(BASE + QUEST)
        A["nojs_stages_listed"] = pg.locator(".check li").count()
        pg.goto(BASE + "/otryad/?p=wyll&p=astarion")
        A["nojs_party_works"] = pg.locator(".best tbody tr").count() == 6
        A["nojs_print_hidden"] = not pg.locator("[data-print]").is_visible()
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
    print(json.dumps(out["actions"], ensure_ascii=False))
    print("axe", {k: v for k, v in out["axe"].items() if k != "version" and v})
    print("console", out["console_errors"])
