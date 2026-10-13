"""Браузерная приёмка games-survival (inventory-first): карта действий (результат, а не наличие кнопки), axe-core, скриншоты, метрики (лаб.)."""

from __future__ import annotations

import argparse
import json
import subprocess
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
BASE = "http://127.0.0.1:8872"
AXE = ROOT / "qa" / "node_modules" / "axe-core" / "axe.min.js"
VIEW = {"mobile": {"width": 390, "height": 844}, "desktop": {"width": 1440, "height": 900}}
ITEM = "/minecraft/predmety/palka/"
SHOTS = {
    "inventory": "/iz-togo-chto-est/?est=doski&est=palka&est=ugol",
    "home": "/",
    "planner": "/planirovshchik/?item=fakel&n=16",
    "game": "/minecraft/",
    "section": "/minecraft/predmety/",
    "item": ITEM,
    "resource": "/minecraft/resursy/brevno/",
    "biome": "/minecraft/biomy/biom-les/",
}
AXE_PAGES = list(SHOTS.values()) + [
    "/planirovshchik/",
    "/planirovshchik/?item=fakel&n=0",
    "/minecraft/resursy/",
    "/minecraft/biomy/",
    "/minecraft/predmety/shchit/",
    "/minecraft/versiya/versiya/",
    "/kak-my-rabotaem/",
    "/istochniki/",
    "/poisk/?q=факел",
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
        pg.goto(BASE + "/planirovshchik/")  # вариант C: форма планировщика — на своей странице
        pg.keyboard.press("Tab")
        A["keyboard_first_tab_is_skip"] = pg.evaluate("document.activeElement.className") == "skip"
        pg.keyboard.press("Enter")
        A["skip_moves_focus_to_main"] = pg.evaluate("document.activeElement.id") == "main"
        pg.select_option("#pi", "fakel")
        pg.fill("#pn", "16")
        with pg.expect_navigation():
            pg.click(".pf .btn")
        A["home_form_opens_plan"] = "item=fakel" in pg.url and pg.locator("h1").inner_text() == "Факел × 16"
        A["plan_base_coal_16_torches"] = pg.locator(".tbl tbody tr", has_text="Уголь").locator("td").inner_text() == "4"
        A["plan_steps_in_order"] = pg.locator(".step b").all_inner_texts() == ["Доски", "Палка", "Факел"]
        boxes = pg.locator("[data-step]")
        boxes.nth(0).check()
        boxes.nth(1).check()
        A["steps_status_counts"] = pg.locator("[data-status]").inner_text() == "Готово шагов: 2 из 3."
        pg.reload()
        A["steps_persist_after_reload"] = (
            boxes.nth(0).is_checked() and boxes.nth(1).is_checked() and not boxes.nth(2).is_checked()
        )
        A["storage_uses_variant_namespace"] = pg.evaluate("Object.keys(localStorage)") == ["gsv-inv:steps:fakel-16"]
        pg.click("[data-steps-reset]")
        A["steps_reset_clears"] = (
            boxes.nth(0).is_checked() is False and pg.evaluate("localStorage.getItem('gsv-inv:steps:fakel-16')") == "[]"
        )
        pg.evaluate("window.__printed = 0; window.print = () => { window.__printed++; }; 0")  # «; 0»: не функция
        pg.click("[data-print]")
        A["print_button_calls_print"] = pg.evaluate("window.__printed") == 1
        pg.emulate_media(media="print")
        A["print_hides_navigation_and_form"] = (
            not pg.locator(".hd").is_visible()
            and not pg.locator(".pf").is_visible()
            and pg.locator(".step").first.is_visible()
        )
        pg.emulate_media(media="screen")
        pg.fill("#pn", "65")
        A["number_field_blocks_over_max"] = pg.evaluate("document.querySelector('#pn').checkValidity()") is False
        resp = pg.goto(BASE + "/planirovshchik/?item=fakel&n=0")
        A["bad_quantity_400_with_alert"] = resp.status == 400 and pg.locator(".err[role=alert]").count() == 1
        with pg.expect_navigation():
            pg.locator(".hd__nav a", has_text="Ресурсы").click()
        A["nav_opens_catalogue_table"] = pg.url.endswith("/resursy/") and pg.locator(".tbl--cat tbody tr").count() == 4
        with pg.expect_navigation():
            pg.locator(".tbl--cat a", has_text="Бревно").click()
        A["catalogue_row_opens_entry"] = pg.url.endswith("/minecraft/resursy/brevno/")
        with pg.expect_navigation():
            pg.locator("a.mini").first.click()
        A["uses_row_opens_plan"] = "item=doski" in pg.url and "n=4" in pg.url
        # связи «из чего → во что» (как в A; рекомендация: в приёмке C отдельно не проверялись)
        pg.goto(BASE + "/minecraft/predmety/palka/")
        with pg.expect_navigation():
            pg.locator(".note a", has_text="Доски").first.click()
        A["made_from_link_opens_ingredient"] = pg.url.endswith("/minecraft/predmety/doski/")
        pg.goto(BASE + "/minecraft/predmety/palka/")
        with pg.expect_navigation():
            pg.locator("#h-use ~ .tablewrap a:not(.mini)", has_text="Факел").click()
        A["used_for_link_opens_product"] = pg.url.endswith("/minecraft/predmety/fakel/")
        A["product_lists_back_link"] = pg.locator(".note a", has_text="Палка").count() == 1
        pg.goto(BASE + "/minecraft/predmety/kirka/")
        with pg.expect_navigation():
            pg.locator(".note a", has_text="Палка").first.click()
        A["tool_page_links_source_materials"] = pg.url.endswith("/minecraft/predmety/palka/")
        pg.goto(BASE + "/minecraft/predmety/shchit/")
        pg.fill("#en", "2")
        with pg.expect_navigation():
            pg.click(".pf .btn")
        A["entry_form_plans_quantity"] = pg.locator("h1").inner_text() == "Щит × 2"
        with pg.expect_navigation():
            pg.click(".patch")
        A["version_badge_opens_version"] = pg.url.endswith("/versiya/versiya/")
        pg.goto(BASE + "/minecraft/predmety/shchit/")
        A["entry_no_hscroll_on_phone"] = pg.evaluate("document.documentElement.scrollWidth <= innerWidth")
        pg.locator("a.ref").first.click()
        A["ref_jumps_to_source"] = pg.evaluate("location.hash") == "#ist-1"
        pg.goto(BASE + "/")
        pg.fill("#fq", "железо")
        with pg.expect_navigation():
            pg.press("#fq", "Enter")
        A["search_keyboard_results"] = pg.locator(".ec").count()
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
        # --- вариант C: инвентарь ---
        pg.evaluate("localStorage.clear(); 0")
        pg.goto(BASE + "/")
        url0 = pg.url
        pg.click(".inv .btn")
        A["empty_inventory_submit_blocked"] = pg.url == url0
        pg.locator(".inv__list label", has_text="Доски").click()
        pg.locator(".inv__list label", has_text="Палка").click()
        A["inv_count_updates"] = pg.locator("[data-inv-count]").inner_text() == "Отмечено: 2"
        with pg.expect_navigation():
            pg.click(".inv .btn")
        A["craftable_now_listed"] = pg.locator("#h-now").inner_text() == "Можно сделать сейчас: 10"
        A["almost_names_missing"] = pg.locator(".craft--almost .craft__miss", has_text="Уголь").count() == 1
        with pg.expect_navigation():
            pg.locator(".craft__t", has_text="Факел").click()
        A["craft_row_opens_item"] = pg.url.endswith("/predmety/fakel/")
        pg.goto(BASE + "/poisk/?q=x")
        A["header_link_keeps_inventory"] = "est=doski" in (pg.locator("[data-inv-link]").get_attribute("href") or "")
        pg.goto(BASE + "/")
        A["home_form_remembers_inventory"] = pg.locator("input[value=doski]").is_checked()
        resp = pg.goto(BASE + "/iz-togo-chto-est/?est=almaz")
        A["unknown_material_400_alert"] = resp.status == 400 and pg.locator(".err[role=alert]").count() == 1
        A["storage_namespace_own"] = all(k.startswith("gsv-inv:") for k in pg.evaluate("Object.keys(localStorage)"))
        ctx.close()
        ctx = br.new_context(java_script_enabled=False)
        pg = ctx.new_page()
        pg.goto(BASE + "/planirovshchik/?item=lestnica&n=3")
        A["nojs_plan_computed_on_server"] = pg.locator(".step").count() == 3
        A["nojs_reset_and_print_hidden"] = (
            not pg.locator("[data-print]").is_visible() and not pg.locator("[data-steps-reset]").is_visible()
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
