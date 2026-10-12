"""Браузерная приёмка home-practical (problem-checklists): карта действий (результат, а не наличие кнопки), axe-core, скриншоты, метрики (лаб.)."""

from __future__ import annotations

import argparse
import json
import subprocess
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
BASE = "http://127.0.0.1:8852"
AXE = ROOT / "qa" / "node_modules" / "axe-core" / "axe.min.js"
VIEW = {"mobile": {"width": 390, "height": 844}, "desktop": {"width": 1440, "height": 900}}
MAT = "/instrukciya/zakrepit-komod-k-stene/"
PROB = "/problemy/mebel-mozhet-upast/"
SHOTS = {
    "home": "/",
    "problem": PROB,
    "catalog": "/zadachi/?sort=nazvanie",
    "material": MAT,
    "room": "/pomeshcheniya/spalnya/",
    "empty-filter": "/zadachi/?pomeshchenie=kuhnya&zadacha=mebel",
}
AXE_PAGES = list(SHOTS.values()) + [
    "/problemy/",
    "/pomeshcheniya/",
    "/zadachi/mebel/",
    "/instrukciya/razdelit-yashchik-komoda/",
    "/instrukciya/zadelat-otverstiya-ot-krepezha/",
    "/podborki/",
    "/podborki/obuv/",
    "/teg/sverlenie/",
    "/istochniki/",
    "/kak-my-proveryaem/",
    "/poisk/?q=полка",
    "/poisk/?q=квантовый",
    "/sohranennoe/",
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
            pg.locator(".problems a").first.click()
        A["home_problem_opens"] = pg.url.endswith(PROB)
        with pg.expect_navigation():
            pg.locator(".seq__t a").first.click()
        A["problem_first_solution_opens"] = pg.url.endswith(MAT)
        steps = pg.locator("[data-step]")
        n = steps.count()
        steps.nth(0).check()
        steps.nth(1).check()
        A["progress_text_after_2"] = pg.locator("[data-progress-text]").inner_text()
        A["progress_value"] = pg.evaluate("document.querySelector('[data-progress]').value") == 2
        pg.click("[data-next]")
        A["next_step_focuses_first_unchecked"] = pg.evaluate("document.activeElement.id") == "shag-3"
        pg.reload()
        A["steps_persist_after_reload"] = [steps.nth(i).is_checked() for i in range(n)] == [True, True] + [False] * (
            n - 2
        )
        pg.goto(BASE + PROB)
        A["problem_page_shows_progress"] = (
            pg.locator(".seq li").first.locator("[data-progress]").inner_text() == f"Выполнено шагов: 2 из {n}"
        )
        pg.goto(BASE + MAT)
        for i in range(n):
            steps.nth(i).check()
        A["all_steps_done_text"] = pg.locator("[data-progress-text]").inner_text().startswith("Все шаги выполнены")
        pg.click("[data-next]")
        A["next_after_all_goes_to_final"] = pg.evaluate("document.activeElement.id") == "itog"
        checks = pg.locator("[data-check]")
        checks.nth(0).check()
        pg.reload()
        A["final_check_persists"] = checks.nth(0).is_checked() and pg.locator(
            "[data-check-status]"
        ).inner_text().startswith("Проверено 1")
        pg.click("[data-steps-reset]")
        pg.reload()
        A["steps_reset"] = not any(steps.nth(i).is_checked() for i in range(n))
        pg.click("[data-save]")
        pg.reload()
        A["save_persists_after_reload"] = pg.get_attribute("[data-save]", "aria-pressed") == "true"
        A["saved_badge"] = pg.locator(".nav .badge").inner_text()
        pg.goto(BASE + "/sohranennoe/")
        A["saved_page_lists_item"] = pg.locator("[data-saved-item]:not([hidden])").count() == 1
        pg.click("[data-saved-clear]")
        A["saved_clear_shows_empty"] = pg.locator("[data-saved-empty]").is_visible()
        pg.goto(BASE + MAT)
        pg.evaluate(
            "window.__printed = 0; window.print = () => { window.__printed++; }; 0"
        )  # «; 0»: не возвращать функцию
        pg.click("[data-print]")
        A["print_button_calls_print"] = pg.evaluate("window.__printed") == 1
        pg.emulate_media(media="print")
        A["print_hides_navigation"] = not pg.locator(".bar").is_visible() and pg.locator(".todo__list").is_visible()
        pg.emulate_media(media="screen")
        pg.locator("a.ref").first.click()
        A["ref_jumps_to_source"] = pg.evaluate("location.hash").startswith("#ist-")
        # каталог: сегментные фильтры, сортировка, сброс, пустое состояние, история
        pg.goto(BASE + "/zadachi/")
        total = pg.locator("tbody tr").count()
        pg.locator(".seg label", has_text="Ванная").click()
        pg.select_option("#sort", "nazvanie")
        with pg.expect_navigation():
            pg.click(".ctl button")
        titles = pg.locator("tbody td:first-child").all_inner_texts()
        rooms = pg.locator("tbody td:nth-child(2)").all_inner_texts()
        A["filter_and_sort"] = {
            "total": total,
            "after": len(titles),
            "ok": bool(titles) and set(rooms) == {"Ванная"} and titles == sorted(titles),
        }
        with pg.expect_navigation():
            pg.click(".ctl .reset")
        A["filter_reset_restores_all"] = pg.locator("tbody tr").count() == total
        pg.goto(BASE + "/zadachi/?pomeshchenie=kuhnya&zadacha=mebel")
        A["filter_empty_state_with_exits"] = pg.locator(".empty a").count() == 2
        pg.go_back()
        A["history_back_returns"] = pg.url.endswith("/zadachi/")
        pg.go_forward()
        A["history_forward_returns"] = "zadacha=mebel" in pg.url
        # поиск
        pg.goto(BASE + "/")
        pg.fill("#hq", "комод")
        with pg.expect_navigation():
            pg.press("#hq", "Enter")
        A["search_keyboard_results"] = pg.locator(".row").count()
        with pg.expect_navigation():
            pg.click(".find--wide .reset")
        A["search_clear"] = pg.locator("#sq").input_value() == "" and pg.locator(".row").count() == 0
        A["search_empty_query_offers_problems"] = pg.locator(".plain a[href^='/problemy/']").count() >= 5
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
        pg.goto(BASE + MAT)
        A["nojs_steps_listed"] = pg.locator(".todo__list li").count()
        A["nojs_progress_and_save_hidden"] = (
            not pg.locator("[data-progress-box]").is_visible() and not pg.locator("[data-save]").is_visible()
        )
        pg.goto(BASE + "/zadachi/?pomeshchenie=prihozhaya&sort=nazvanie")
        A["nojs_filter_works"] = pg.locator("tbody tr").count() == 2
        pg.goto(BASE + PROB)
        A["nojs_problem_lists_solutions"] = pg.locator(".seq li").count() == 6
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
