"""Браузерная приёмка games-story (atlas): карта действий (результат, а не наличие кнопки), axe-core, скриншоты, метрики (лаб.)."""

from __future__ import annotations

import argparse
import json
import subprocess
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
BASE = "http://127.0.0.1:8870"
AXE = ROOT / "qa" / "node_modules" / "axe-core" / "axe.min.js"
VIEW = {"mobile": {"width": 390, "height": 844}, "desktop": {"width": 1440, "height": 900}}
GUIDE = "/igra/celeste/glava-1-forsaken-city/"
SHOTS = {
    "where": "/igra/celeste/gde-ya/",
    "character": "/igra/celeste/personazh/theo/",
    "home": "/",
    "game": "/igra/celeste/",
    "guide": GUIDE,
    "collectibles": "/igra/celeste/kollekcii/",
    "videos": "/video/",
    "farewell": "/igra/celeste/glava-9-farewell/",
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
        with pg.expect_navigation():
            pg.locator(".hd__nav a", has_text="Celeste").click()
        A["nav_opens_game"] = pg.url.endswith("/igra/celeste/")
        box = pg.locator(".gc").nth(1).bounding_box()
        with pg.expect_navigation():
            pg.mouse.click(box["x"] + 20, box["y"] + box["height"] - 10)
        A["whole_card_opens_guide"] = pg.url.endswith(GUIDE)
        A["route_rendered"] = pg.locator(".route li").count() == 3
        boxes = pg.locator(".check input")
        boxes.nth(0).check()
        boxes.nth(1).check()
        pg.reload()
        A["progress_persists_after_reload"] = (
            boxes.nth(0).is_checked() and boxes.nth(1).is_checked() and not boxes.nth(2).is_checked()
        )
        pg.goto(BASE + "/igra/celeste/")
        A["game_page_shows_chapter_progress"] = (
            pg.locator(".gc[data-slug='glava-1-forsaken-city'] [data-progress]").inner_text() == "Прогресс: 2 из 4"
        )
        # общий счётчик на главной (идея B): отмечены «A-сторона» и «все клубники» главы 1 (20 клубник по источнику)
        pg.goto(BASE + "/")
        A["home_tally_red_from_source"] = pg.locator(".dash [data-stat=red]").inner_text() == "20"
        A["home_tally_sides"] = pg.locator(".dash [data-stat=sides]").inner_text() == "1"
        A["home_tally_full_chapters"] = pg.locator(".dash [data-stat=full]").inner_text() == "0"
        pg.goto(BASE + GUIDE)
        pg.click("[data-check-reset]")
        pg.reload()
        A["progress_reset"] = not boxes.nth(0).is_checked()
        with pg.expect_navigation():
            pg.locator(".pager a").last.click()
        A["pager_next_chapter"] = pg.url.endswith("/glava-2-old-site/")
        with pg.expect_navigation():
            pg.locator(".pager a").first.click()
        A["pager_prev_chapter"] = pg.url.endswith(GUIDE)
        pg.click(".toc a[href='#predmety']")
        A["toc_jumps"] = pg.evaluate("location.hash") == "#predmety"
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
        A["print_hides_navigation"] = not pg.locator(".hd").is_visible() and pg.locator(".route").is_visible()
        pg.emulate_media(media="screen")
        pg.goto(BASE + "/")
        pg.fill("#fq", "Badeline")
        with pg.expect_navigation():
            pg.press("#fq", "Enter")
        A["search_keyboard_results"] = pg.locator(".gc").count()
        with pg.expect_navigation():
            pg.click(".find--page .reset")
        A["search_clear"] = pg.locator("#sq").input_value() == ""
        pg.goto(BASE + "/poisk/?q=квантовый")
        A["search_no_results_message"] = pg.locator(".empty h2").inner_text() == "Ничего не нашлось"
        pg.goto(BASE + "/nesushchestvuet/")
        A["404_has_search_and_home"] = (
            pg.locator(".nf form").count() == 1 and pg.locator(".nf a[href='/']").count() == 1
        )
        # --- вариант C: атлас ---
        pg.goto(BASE + "/")
        pg.fill("#wq", "Huge Mess")
        with pg.expect_navigation():
            pg.press("#wq", "Enter")
        A["home_where_am_i_finds_checkpoint"] = (
            pg.locator(".cp").count() == 1 and "Celestial Resort" in pg.locator(".cp__where").inner_text()
        )
        with pg.expect_navigation():
            pg.locator(".cp__where a").click()
        A["checkpoint_opens_chapter"] = pg.url.endswith("/igra/celeste/glava-3-celestial-resort/")
        pg.goto(BASE + "/igra/celeste/gde-ya/")
        total = pg.locator(".cp").count()
        pg.fill("[data-cp-filter]", "start")
        A["live_filter_narrows"] = 0 < pg.locator(".cp:not([hidden])").count() < total and pg.locator(
            "[data-cp-count]"
        ).inner_text().startswith(str(pg.locator(".cp:not([hidden])").count()))
        pg.fill("[data-cp-filter]", "")
        A["live_filter_clears"] = pg.locator(".cp:not([hidden])").count() == total
        pg.goto(BASE + "/")
        with pg.expect_navigation():
            pg.locator(".chips a", has_text="Theo").click()
        A["character_chip_opens_page"] = pg.url.endswith("/personazh/theo/") and pg.locator(".appear li").count() >= 1
        with pg.expect_navigation():
            pg.locator(".appear a").first.click()
        A["character_page_links_chapter"] = "/igra/celeste/" in pg.url and pg.locator("h1").count() == 1
        pg.goto(BASE + "/igra/celeste/mehaniki/")
        A["mechanics_table_rows"] = pg.locator(".atl tbody tr").count() >= 10
        resp = pg.goto(BASE + "/igra/celeste/personazh/nikto/")
        A["unknown_character_404"] = resp.status == 404
        ctx.close()
        ctx = br.new_context(java_script_enabled=False)
        pg = ctx.new_page()
        pg.goto(BASE + "/video/")
        A["nojs_video_link_only"] = (
            pg.locator(".vid a[href^='https://www.youtube.com/watch']").count() == 2
            and not pg.locator("[data-play]").first.is_visible()
        )
        pg.goto(BASE + GUIDE)
        A["nojs_guide_route"] = pg.locator(".route li").count()
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
