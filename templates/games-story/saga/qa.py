"""Браузерная приёмка games-story (progress-tracker): карта действий (результат, а не наличие кнопки), axe-core, скриншоты, метрики (лаб.)."""

from __future__ import annotations

import argparse
import json
import subprocess
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
BASE = "http://127.0.0.1:8858"
AXE = ROOT / "qa" / "node_modules" / "axe-core" / "axe.min.js"
VIEW = {"mobile": {"width": 390, "height": 844}, "desktop": {"width": 1440, "height": 900}}
GUIDE = "/igra/celeste/glava-1-forsaken-city/"
SHOTS = {
    "home": "/",
    "tracker": "/igra/celeste/",
    "guide": GUIDE,
    "items": "/igra/celeste/predmety/",
    "item": "/igra/celeste/predmety/krasnye-klubniki/",
    "videos": "/video/",
}
AXE_PAGES = list(SHOTS.values()) + [
    "/igra/celeste/prolog/",
    "/igra/celeste/glava-8-core/",
    "/igra/celeste/glava-6-reflection/",
    "/kak-my-rabotaem/",
    "/istochniki/",
    "/poisk/?q=Badeline",
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
        external = []
        ctx.route(
            "**/*",
            lambda r: r.continue_() if r.request.url.startswith(BASE) else (external.append(r.request.url), r.abort()),
        )
        pg = ctx.new_page()
        pg.goto(BASE + "/")
        pg.keyboard.press("Tab")
        A["keyboard_first_tab_is_skip"] = pg.evaluate("document.activeElement.className") == "skip"
        pg.keyboard.press("Enter")
        A["skip_moves_focus_to_main"] = pg.evaluate("document.activeElement.id") == "main"
        A["no_external_requests_on_load"] = not external
        A["home_counters_zero"] = pg.locator(".dash [data-stat=red]").inner_text() == "0"
        with pg.expect_navigation():
            pg.locator(".dash .btn").first.click()
        A["home_opens_tracker"] = pg.url.endswith("/igra/celeste/")
        row = pg.locator("tr[data-slug='glava-1-forsaken-city']")
        row.locator("[data-red-input]").fill("12")
        row.locator("[data-red-input]").press("Tab")
        row.locator("input[data-side=A]").check()
        A["tracker_totals_update"] = (
            pg.locator("tfoot [data-stat=red]").inner_text() == "12"
            and pg.locator("tfoot [data-stat=sides]").inner_text() == "1"
        )
        row2 = pg.locator("tr[data-slug='glava-2-old-site']")
        row2.locator("[data-red-input]").fill("999")
        row2.locator("[data-red-input]").press("Tab")
        A["tracker_clamps_to_source_max"] = row2.locator("[data-red-input]").input_value() == "18"
        pg.reload()
        A["tracker_persists_after_reload"] = (
            row.locator("[data-red-input]").input_value() == "12" and row.locator("input[data-side=A]").is_checked()
        )
        pg.goto(BASE + "/")
        A["home_counters_after_progress"] = (
            pg.locator(".dash [data-stat=red]").inner_text() == "30"
            and pg.locator(".dash [data-stat=sides]").inner_text() == "1"
        )
        pg.goto(BASE + GUIDE)
        A["guide_tracker_shares_state"] = pg.locator(".trk [data-red-input]").input_value() == "12"
        A["route_rendered"] = pg.locator(".steps li").count() == 3
        with pg.expect_navigation():
            pg.locator(".pager a").last.click()
        A["pager_next_chapter"] = pg.url.endswith("/glava-2-old-site/")
        pg.goto(BASE + "/igra/celeste/")
        with pg.expect_navigation():
            pg.click("[data-tracker-reset]")
        A["tracker_reset_all"] = pg.locator("tfoot [data-stat=red]").inner_text() == "0"
        with pg.expect_navigation():
            pg.locator(".hd__nav a", has_text="Предметы").click()
        with pg.expect_navigation():
            pg.locator(".types a").first.click()
        A["items_type_page"] = (
            pg.url.endswith("/predmety/krasnye-klubniki/") and pg.locator("tfoot td").first.inner_text() == "175"
        )
        pg.goto(BASE + "/video/")
        A["video_no_iframe_before_click"] = pg.locator("iframe").count() == 0
        pg.locator("[data-play]").first.click()
        A["video_iframe_after_click"] = (
            pg.locator("iframe.vid__frame").first.get_attribute("src")
            == "https://www.youtube-nocookie.com/embed/JVUIz-dGyK4"
        )
        A["video_external_request_only_after_click"] = bool(external) and all(
            "youtube-nocookie.com" in u for u in external
        )
        pg.goto(BASE + GUIDE)
        pg.evaluate(
            "window.__printed = 0; window.print = () => { window.__printed++; }; 0"
        )  # «; 0»: не возвращать функцию
        pg.click("[data-print]")
        A["print_button_calls_print"] = pg.evaluate("window.__printed") == 1
        pg.emulate_media(media="print")
        A["print_hides_navigation"] = not pg.locator(".hd").is_visible() and pg.locator(".steps").is_visible()
        pg.emulate_media(media="screen")
        pg.goto(BASE + "/")
        pg.fill("#fq", "Badeline")
        with pg.expect_navigation():
            pg.press("#fq", "Enter")
        A["search_keyboard_results"] = pg.locator(".types li").count()
        with pg.expect_navigation():
            pg.click(".find--page .reset")
        A["search_clear"] = pg.locator("#sq").input_value() == ""
        pg.goto(BASE + "/poisk/?q=квантовый")
        A["search_no_results_message"] = pg.locator(".empty h2").inner_text() == "Ничего не нашлось"
        pg.goto(BASE + "/nesushchestvuet/")
        A["404_has_search_and_home"] = (
            pg.locator(".nf form").count() == 1 and pg.locator(".nf a[href='/']").count() == 1
        )
        ctx.close()
        ctx = br.new_context(java_script_enabled=False)
        pg = ctx.new_page()
        pg.goto(BASE + "/video/")
        A["nojs_video_link_only"] = (
            pg.locator(".vid a[href^='https://www.youtube.com/watch']").count() == 2
            and not pg.locator("[data-play]").first.is_visible()
        )
        pg.goto(BASE + GUIDE)
        A["nojs_guide_route"] = pg.locator(".steps li").count()
        pg.goto(BASE + "/igra/celeste/")
        A["nojs_tracker_disabled_numbers_visible"] = (
            pg.locator("[data-red-input]").first.is_disabled() and pg.locator(".of").count() > 5
        )
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
