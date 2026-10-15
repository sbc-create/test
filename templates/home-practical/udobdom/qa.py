"""Браузерная приёмка home-practical: карта действий (результат, а не наличие кнопки), axe-core, скриншоты, метрики (лаб.)."""

from __future__ import annotations

import argparse
import json
import subprocess
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
BASE = "http://127.0.0.1:8851"
AXE = ROOT / "qa" / "node_modules" / "axe-core" / "axe.min.js"
VIEW = {"mobile": {"width": 390, "height": 844}, "desktop": {"width": 1440, "height": 900}}
MAT = "/instrukciya/razdelit-yashchik-komoda/"
SHOTS = {
    "home": "/",
    "room": "/pomeshcheniya/spalnya/",
    "catalog": "/zadachi/?pomeshchenie=vannaya",
    "material": MAT,
    "collection": "/podborki/krepim-k-stene/",
    "empty-filter": "/zadachi/?pomeshchenie=kuhnya&zadacha=mebel",
}
AXE_PAGES = list(SHOTS.values()) + [
    "/pomeshcheniya/",
    "/zadachi/mebel/",
    "/instrukciya/zakrepit-komod-k-stene/",
    "/instrukciya/zadelat-otverstiya-ot-krepezha/",
    "/podborki/",
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
        A["mobile_rooms_bar_hidden"] = not pg.locator(".rooms-bar").is_visible()
        pg.click(".menu summary")
        A["mobile_menu_opens"] = pg.locator(".menu nav").is_visible()
        with pg.expect_navigation():
            pg.locator(".menu a", has_text="Ванная").click()
        A["mobile_menu_link_opens_room"] = (
            pg.url.endswith("/pomeshcheniya/vannaya/") and pg.locator("h1").inner_text() == "Ванная"
        )
        # фильтры: сочетание, результат, сброс
        pg.goto(BASE + "/zadachi/")
        total = pg.locator(".card").count()
        pg.select_option("#f-room", "spalnya")
        pg.select_option("#f-task", "organizaciya")
        with pg.expect_navigation():
            pg.click(".filters button")
        cards = pg.locator(".card__where").all_inner_texts()
        A["filter_room_task_combo"] = {
            "total": total,
            "after": len(cards),
            "ok": len(cards) > 0 and all("Спальня" in c and "Организация" in c for c in cards),
        }
        with pg.expect_navigation():
            pg.click(".filters__reset")
        A["filter_reset_restores_all"] = pg.locator(".card").count() == total and pg.url.endswith("/zadachi/")
        pg.goto(BASE + "/zadachi/?pomeshchenie=kuhnya&zadacha=mebel")
        A["filter_empty_state_with_exits"] = pg.locator(".empty a").count() >= 2
        pg.go_back()
        A["history_back_returns"] = pg.url.endswith("/zadachi/")
        pg.go_forward()
        A["history_forward_returns"] = "zadacha=mebel" in pg.url
        # поиск: ввод с клавиатуры, результат, пустой запрос, нет результатов, очистка
        pg.goto(BASE + "/")
        pg.fill("#hq", "обувь")
        with pg.expect_navigation():
            pg.press("#hq", "Enter")
        A["search_keyboard_results"] = pg.locator(".card").count()
        with pg.expect_navigation():
            pg.click(".find--page .filters__reset")
        A["search_clear"] = pg.locator("#sq").input_value() == "" and pg.locator(".card").count() == 0
        pg.goto(BASE + "/poisk/?q=")
        A["search_empty_query_hint"] = pg.locator(".chips__plain a").count() == 6
        pg.goto(BASE + "/poisk/?q=квантовый")
        A["search_no_results_message"] = pg.locator(".empty h2").inner_text() == "Ничего не нашлось"
        # материал: оглавление, ссылка на источник, чек-лист, сохранение, печать
        pg.goto(BASE + MAT)
        pg.click(".toc a[href='#shagi']")
        A["toc_jumps_to_steps"] = pg.evaluate("location.hash") == "#shagi"
        pg.locator("a.ref").first.click()
        A["ref_jumps_to_source"] = (
            pg.evaluate("location.hash").startswith("#ist-") and pg.locator(pg.evaluate("location.hash")).count() == 1
        )
        boxes = pg.locator(".check input")
        boxes.nth(0).check()
        boxes.nth(2).check()
        pg.reload()
        A["checklist_persists_after_reload"] = [boxes.nth(i).is_checked() for i in range(boxes.count())] == [
            True,
            False,
            True,
        ]
        A["checklist_status_text"] = pg.locator("[data-check-status]").inner_text()
        pg.click("[data-check-reset]")
        pg.reload()
        A["checklist_reset"] = not any(boxes.nth(i).is_checked() for i in range(boxes.count()))
        pg.click("[data-save]")
        A["save_button_pressed"] = pg.get_attribute("[data-save]", "aria-pressed") == "true"
        pg.reload()
        A["save_persists_after_reload"] = pg.get_attribute("[data-save]", "aria-pressed") == "true"
        A["saved_badge"] = pg.locator(".saved-link .badge").inner_text()
        pg.goto(BASE + "/sohranennoe/")
        A["saved_page_lists_item"] = pg.locator("[data-saved-item]:not([hidden]) .card").count() == 1
        pg.click("[data-saved-clear]")
        A["saved_clear_shows_empty"] = pg.locator("[data-saved-empty]").is_visible()
        pg.goto(BASE + MAT)
        pg.evaluate(
            "window.__printed = 0; window.print = () => { window.__printed++; }; 0"
        )  # «; 0»: не возвращать функцию — Playwright вызывает её при сериализации
        pg.click("[data-print]")
        A["print_button_calls_print"] = pg.evaluate("window.__printed") == 1
        pg.emulate_media(media="print")
        A["print_hides_navigation"] = not pg.locator(".top").is_visible() and pg.locator(".steps").is_visible()
        pg.emulate_media(media="screen")
        pg.goto(BASE + "/pomeshcheniya/spalnya/")
        href = pg.locator(".card__title a").first.get_attribute("href")
        box = pg.locator(".card").first.bounding_box()
        with pg.expect_navigation():
            pg.mouse.click(box["x"] + 20, box["y"] + box["height"] - 12)
        A["whole_card_clickable"] = pg.url.endswith(href)
        pg.goto(BASE + "/nesushchestvuet/")
        A["404_has_search_and_home"] = (
            pg.locator(".nf form").count() == 1 and pg.locator(".nf a[href='/']").count() == 1
        )
        ctx.close()

        # --- без JavaScript ---
        ctx = br.new_context(java_script_enabled=False)
        pg = ctx.new_page()
        pg.goto(BASE + MAT)
        A["nojs_material_steps"] = pg.locator(".steps li").count()
        A["nojs_save_button_hidden"] = not pg.locator("[data-save]").is_visible()
        pg.goto(BASE + "/zadachi/?pomeshchenie=prihozhaya")
        A["nojs_filter_works"] = pg.locator(".card").count() == 2
        pg.goto(BASE + "/")
        pg.click(".menu summary") if pg.locator(".menu summary").is_visible() else None
        A["nojs_rooms_reachable"] = pg.locator("a[href='/pomeshcheniya/kuhnya/']").count() >= 1
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
