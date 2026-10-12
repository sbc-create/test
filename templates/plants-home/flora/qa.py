"""Браузерная приёмка plants-home (pick-and-diagnose): карта действий (результат, а не наличие кнопки), axe-core, скриншоты, метрики (лаб.)."""

from __future__ import annotations

import argparse
import json
import subprocess
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
BASE = "http://127.0.0.1:8856"
AXE = ROOT / "qa" / "node_modules" / "axe-core" / "axe.min.js"
VIEW = {"mobile": {"width": 390, "height": 844}, "desktop": {"width": 1440, "height": 900}}
PLANT = "/rastenie/shlyumbergera-dekabrist/"
SHOTS = {
    "home": "/",
    "pick-result": "/podbor/?svet=ten&zhivotnye=da&submit=1",
    "compare": "/katalog/?sort=uhod",
    "plant": PLANT,
    "diagnose": "/chto-sluchilos/",
    "empty-pick": "/podbor/?svet=solnce&uhod=Medium&submit=1",
}
AXE_PAGES = list(SHOTS.values()) + [
    "/podbor/",
    "/katalog/",
    "/rastenie/aspidistra-vysokaya/",
    "/rastenie/falenopsis/",
    "/svet/",
    "/svet/ten/",
    "/problemy/",
    "/problema/korni-gniyut/",
    "/podborki/",
    "/podborki/neprihotlivye/",
    "/kak-chitat/",
    "/istochniki/",
    "/poisk/?q=фикус",
    "/poisk/?q=квантовый",
    "/katalog/?svet=solnce&uhod=Medium",
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
        pg.locator("input[name=svet][value=ten]").check()
        pg.locator("input[name=zhivotnye][value=da]").check()
        with pg.expect_navigation():
            pg.click(".pick button")
        A["pick_submits_choices"] = "svet=ten" in pg.url and "zhivotnye=da" in pg.url
        A["pick_shows_three_toxicity_groups"] = pg.locator(".res h3").count() == 3
        A["pick_nodata_warning"] = pg.locator("text=Это не значит, что растение безопасно").count() == 1
        A["pick_keeps_choice_after_submit"] = pg.locator("input[name=svet][value=ten]").is_checked()
        with pg.expect_navigation():
            pg.click(".res .reset")
        A["pick_restart"] = pg.url.endswith("/podbor/") and pg.locator(".res").count() == 0
        pg.goto(BASE + "/podbor/?svet=solnce&uhod=Medium&submit=1")
        A["pick_empty_state"] = pg.locator(".empty a").count() == 1
        pg.goto(BASE + "/")
        with pg.expect_navigation():
            pg.locator(".diag a").first.click()
        A["home_diagnose_link_opens_problem"] = "/problema/" in pg.url
        pg.goto(BASE + "/katalog/")
        total = pg.locator(".cmp tbody tr").count()
        pg.select_option("#f-l", "ten")
        pg.select_option("#f-s", "uhod")
        with pg.expect_navigation():
            pg.click(".flt button")
        A["compare_filter_and_sort"] = 0 < pg.locator(".cmp tbody tr").count() < total and "sort=uhod" in pg.url
        with pg.expect_navigation():
            pg.click(".flt .reset")
        A["compare_reset"] = pg.locator(".cmp tbody tr").count() == total
        pg.go_back()
        A["history_back_returns"] = "sort=uhod" in pg.url
        pg.go_forward()
        A["history_forward_returns"] = pg.url.endswith("/katalog/")
        with pg.expect_navigation():
            pg.locator(".cmp tbody th a").first.click()
        A["compare_row_opens_plant"] = "/rastenie/" in pg.url
        pg.goto(BASE + PLANT)
        A["ifthen_items"] = pg.locator(".ifthen li").count()
        with pg.expect_navigation():
            pg.locator(".ifthen a").first.click()
        A["ifthen_link_opens_problem"] = "/problema/" in pg.url
        pg.goto(BASE + PLANT)
        boxes = pg.locator(".check input")
        boxes.nth(0).check()
        pg.reload()
        A["checklist_persists_after_reload"] = boxes.nth(0).is_checked()
        pg.click("[data-check-reset]")
        pg.reload()
        A["checklist_reset"] = not boxes.nth(0).is_checked()
        pg.evaluate(
            "window.__printed = 0; window.print = () => { window.__printed++; }; 0"
        )  # «; 0»: не возвращать функцию
        pg.click("[data-print]")
        A["print_button_calls_print"] = pg.evaluate("window.__printed") == 1
        pg.emulate_media(media="print")
        A["print_hides_navigation"] = not pg.locator(".hd").is_visible() and pg.locator(".care").is_visible()
        pg.emulate_media(media="screen")
        pg.goto(BASE + "/")
        pg.fill("#fq", "фикус")
        with pg.expect_navigation():
            pg.press("#fq", "Enter")
        A["search_keyboard_results"] = pg.locator(".row").count()
        pg.goto(BASE + "/poisk/?q=квантовый")
        A["search_no_results_message"] = pg.locator(".empty h2").inner_text() == "Ничего не нашлось"
        pg.goto(BASE + "/nesushchestvuet/")
        A["404_has_search_and_home"] = (
            pg.locator(".nf form").count() == 1 and pg.locator(".nf a[href='/']").count() == 1
        )
        ctx.close()
        ctx = br.new_context(java_script_enabled=False)
        pg = ctx.new_page()
        pg.goto(BASE + "/podbor/?svet=ten&zhivotnye=da&submit=1")
        A["nojs_pick_works"] = pg.locator(".res .row").count() > 0
        pg.goto(BASE + PLANT)
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
