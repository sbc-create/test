"""Браузерная приёмка garden-season (month-calendar): карта действий (результат, а не наличие кнопки), axe-core, скриншоты, метрики (лаб.)."""

from __future__ import annotations

import argparse
import json
import subprocess
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
BASE = "http://127.0.0.1:8853"
AXE = ROOT / "qa" / "node_modules" / "axe-core" / "axe.min.js"
VIEW = {"mobile": {"width": 390, "height": 844}, "desktop": {"width": 1440, "height": 900}}
WORK = "/rabota/malina-obrezka/"
SHOTS = {
    "home": "/",
    "month": "/kalendar/oktyabr/",
    "calendar": "/kalendar/?region=or-west",
    "work": WORK,
    "crop": "/kultura/chesnok/",
    "empty-month": "/kalendar/dekabr/",
}
AXE_PAGES = list(SHOTS.values()) + [
    "/kalendar/",
    "/kalendar/fevral/",
    "/kultury/",
    "/kultura/malina/",
    "/regiony/",
    "/region/uk/",
    "/tip/zima/",
    "/podborki/",
    "/podborki/yagodniki/",
    "/rabota/uborka-i-hranenie-kartofelya/",
    "/rabota/sideraty-na-zimu/",
    "/kak-chitat-sroki/",
    "/istochniki/",
    "/poisk/?q=чеснок",
    "/poisk/?q=квантовый",
    "/kalendar/?region=uk&tip=zima",
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
        with pg.expect_navigation():
            pg.locator(".months a").nth(9).click()
        A["month_strip_opens_october"] = (
            pg.url.endswith("/kalendar/oktyabr/")
            and pg.get_attribute(".months a[aria-current]", "href") == "/kalendar/oktyabr/"
        )
        A["month_groups_regions"] = pg.locator("section.mreg").count()
        with pg.expect_navigation():
            pg.locator(".pager a").last.click()
        A["pager_next_month"] = pg.url.endswith("/kalendar/noyabr/")
        with pg.expect_navigation():
            pg.locator(".pager a").first.click()
        A["pager_prev_month"] = pg.url.endswith("/kalendar/oktyabr/")
        pg.goto(BASE + "/kalendar/dekabr/")
        A["empty_month_honest"] = pg.locator(".empty a[href*='oregonstate.edu']").count() == 1
        # календарь: фильтр, сброс, пустое сочетание, история
        pg.goto(BASE + "/kalendar/")
        total = pg.locator(".cal__m li a").count()
        pg.select_option("#f-r", "or-west")
        with pg.expect_navigation():
            pg.click(".flt button")
        A["filter_region_reduces"] = 0 < pg.locator(".cal__m li a").count() < total
        with pg.expect_navigation():
            pg.click(".flt .reset")
        A["filter_reset_restores_all"] = pg.locator(".cal__m li a").count() == total
        pg.goto(BASE + "/kalendar/?region=uk&tip=zima")
        A["filter_empty_state_with_exits"] = pg.locator(".empty a").count() == 2
        pg.go_back()
        A["history_back_returns"] = pg.url.endswith("/kalendar/")
        pg.go_forward()
        A["history_forward_returns"] = "tip=zima" in pg.url
        # культура: ячейка таблицы ведёт на работу
        pg.goto(BASE + "/kultura/chesnok/")
        with pg.expect_navigation():
            pg.locator(".cg td a").first.click()
        A["crop_cell_opens_work"] = pg.url.endswith("/rabota/posadka-chesnoka-osenyu/")
        # работа: регион у каждого срока, оглавление, источники, чек-лист, печать
        pg.goto(BASE + WORK)
        A["timing_rows_with_region"] = (
            pg.locator(".when__t tbody tr").count() == pg.locator(".when__t tbody .rg").count() == 4
        )
        pg.click(".toc a[href='#shagi']")
        A["toc_jumps_to_steps"] = pg.evaluate("location.hash") == "#shagi"
        pg.locator(".steps a.ref").first.click()
        A["ref_jumps_to_source"] = pg.evaluate("location.hash").startswith("#ist-")
        boxes = pg.locator(".check input")
        boxes.nth(0).check()
        pg.reload()
        A["checklist_persists_after_reload"] = boxes.nth(0).is_checked() and not boxes.nth(1).is_checked()
        pg.click("[data-check-reset]")
        pg.reload()
        A["checklist_reset"] = not boxes.nth(0).is_checked()
        pg.evaluate(
            "window.__printed = 0; window.print = () => { window.__printed++; }; 0"
        )  # «; 0»: не возвращать функцию
        pg.click("[data-print]")
        A["print_button_calls_print"] = pg.evaluate("window.__printed") == 1
        pg.emulate_media(media="print")
        A["print_hides_navigation"] = not pg.locator(".hd").is_visible() and pg.locator(".when").is_visible()
        pg.emulate_media(media="screen")
        pg.goto(BASE + "/region/or-west/")
        box = pg.locator(".wk").first.bounding_box()
        href = pg.locator(".wk__t a").first.get_attribute("href")
        with pg.expect_navigation():
            pg.mouse.click(box["x"] + 20, box["y"] + box["height"] - 10)
        A["whole_card_clickable"] = pg.url.endswith(href)
        # поиск
        pg.goto(BASE + "/")
        pg.fill("#fq", "чеснок")
        with pg.expect_navigation():
            pg.press("#fq", "Enter")
        A["search_keyboard_results"] = pg.locator(".wk").count()
        with pg.expect_navigation():
            pg.click(".find--page .reset")
        A["search_clear"] = pg.locator("#sq").input_value() == "" and pg.locator(".wk").count() == 0
        pg.goto(BASE + "/poisk/?q=октябрь")
        A["search_by_month"] = pg.locator(".wk").count()
        pg.goto(BASE + "/poisk/?q=квантовый")
        A["search_no_results_message"] = pg.locator(".empty h2").inner_text() == "Ничего не нашлось"
        pg.goto(BASE + "/nesushchestvuet/")
        A["404_has_search_and_home"] = (
            pg.locator(".nf form").count() == 1 and pg.locator(".nf a[href='/']").count() == 1
        )
        ctx.close()

        # --- без JavaScript ---
        ctx = br.new_context(java_script_enabled=False)
        pg = ctx.new_page()
        pg.goto(BASE + WORK)
        A["nojs_work_steps"] = pg.locator(".steps li").count()
        A["nojs_print_hidden"] = not pg.locator("[data-print]").is_visible()
        pg.goto(BASE + "/kalendar/?region=or-west")
        A["nojs_filter_works"] = pg.locator(".cal__m li a").count() > 0
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
