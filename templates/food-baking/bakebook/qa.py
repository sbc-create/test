"""Браузерная приёмка food-baking: сценарии, axe-core, скриншоты, лабораторные метрики.

Метрики лабораторные (локальный preview, без троттлинга), не полевые.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
BASE = os.environ.get("QA_BASE", "http://127.0.0.1:8864").rstrip("/")  # чистая копия на другом порту
AXE = ROOT / "qa" / "node_modules" / "axe-core" / "axe.min.js"
VIEW = {"mobile": {"width": 390, "height": 844}, "desktop": {"width": 1440, "height": 900}}
SHOTS = {
    "home": "/",
    "catalog": "/recepty/",
    "recipe": "/recept/keks-s-kabachkom-i-ananasom/",
    "recipe_pct": "/recept/yablochnoe-myagkoe-pechene/",
    "dough": "/testo/zavarnoe/",
    "pitfalls": "/oshibki/zavarnoe/",
    "batch": "/pechem/?r=limonnyj-keks&r=yablochnoe-myagkoe-pechene&r=tort-bez-vypechki-s-vinogradom",
}
AXE_PAGES = [
    "/",
    "/pechem/",
    "/pechem/?r=limonnyj-keks&r=yablochnoe-myagkoe-pechene&r=tort-bez-vypechki-s-vinogradom",
    "/pechem/?r=neizvestno",
    "/recepty/",
    "/recepty/?sort=temp",
    "/recept/yablochnoe-myagkoe-pechene/",
    "/recepty/page/2/",
    "/recept/limonnyj-keks/",
    "/recept/pirozhnye-lebedi/",
    "/recept/tort-bez-vypechki-s-vinogradom/",
    "/recept/olivkovyj-hleb/",
    "/testo/",
    "/testo/keksovoe/",
    "/oshibki/zavarnoe/",
    "/teg/shokolad/",
    "/poisk/?q=zzz",
    "/nesushchestvuet/",
]
PERF = """() => new Promise(res => { let lcp = 0, cls = 0;
  new PerformanceObserver(l => { for (const e of l.getEntries()) lcp = e.startTime; }).observe({type: 'largest-contentful-paint', buffered: true});
  new PerformanceObserver(l => { for (const e of l.getEntries()) if (!e.hadRecentInput) cls += e.value; }).observe({type: 'layout-shift', buffered: true});
  setTimeout(() => res({lcp_ms: Math.round(lcp), cls: +cls.toFixed(4),
    bytes: performance.getEntriesByType('resource').reduce((s, r) => s + (r.transferSize || 0), performance.getEntriesByType('navigation')[0].transferSize || 0)}), 1200); })"""


def run(shots: Path | None) -> dict:
    head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    res = {
        "base": BASE,
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
            pg.on("console", lambda m, v=v: m.type == "error" and res["console_errors"].append(f"{v}: {m.text}"))
            pg.on("pageerror", lambda e, v=v: res["console_errors"].append(f"{v}: {e}"))
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
        # главная: переход к температуре и в рецепт
        pg.goto(BASE + "/")
        pg.keyboard.press("Tab")
        S["first_tab_skip"] = pg.evaluate("document.activeElement.className") == "skip"
        pg.locator(".temp-jump a", has_text="180").click()
        S["temp_jump_anchor"] = pg.evaluate("location.hash") == "#t-180"
        with pg.expect_navigation():
            pg.locator("#t-180 .rows a").first.click()
        S["temp_row_opens_recipe_at_180"] = pg.locator(".facts-b li", has_text="Духовка").locator("b").inner_text().startswith("180")
        # рабочий лист: таймер из источника, отметки сохраняются и сбрасываются
        pg.goto(BASE + "/recept/keks-s-kabachkom-i-ananasom/")
        pg.click(".timer")
        pg.wait_for_timeout(1300)
        S["timer_counts_down_from_source_80_min"] = pg.locator(".timer").first.inner_text().startswith("Осталось 79:")
        pg.click(".timer")
        S["timer_stops"] = pg.locator(".timer").first.inner_text() == "Таймер 80 мин"
        pg.locator("[data-weigh]").first.check()
        steps = pg.locator("[data-step-done]")
        steps.nth(0).check()
        S["steps_progress_text"] = pg.locator("[data-progress]").inner_text().startswith("Сделано шагов: 1 из ")
        pg.reload()
        S["marks_persist_after_reload"] = pg.locator("[data-weigh]").first.is_checked() and steps.nth(0).is_checked()
        S["storage_keys_own_namespace"] = (
            all(k.startswith("fbb.") for k in pg.evaluate("Object.keys(localStorage)"))
            and pg.evaluate("Object.keys(localStorage).length") == 2
        )
        pg.click("[data-steps-reset]")
        S["reset_clears_marks"] = not pg.locator("[data-weigh]").first.is_checked() and not steps.nth(0).is_checked()
        pg.goto(BASE + "/recept/yablochnoe-myagkoe-pechene/")
        pg.click(".pct-box summary")  # процент — в раскрываемом блоке
        S["bakers_pct_butter_50"] = (
            pg.locator(".pct-t tr", has_text="Сливочное масло").locator("td").first.inner_text() == "50 %"
        )
        pg.locator(".facts-b a", has_text="шаг").click()
        S["oven_strip_links_to_step"] = pg.evaluate("location.hash") == "#shag-5"
        # таблица (вид «таблица сравнения»; по умолчанию — карточки): фильтр и сортировка применяются сразу
        pg.goto(BASE + "/recepty/?vid=tablica")
        with pg.expect_navigation():
            pg.select_option("select[name=sort]", "temp")
        S["sort_hot_first"] = (
            pg.locator(".cmp tbody tr").first.locator("td[data-label='°C']").inner_text().startswith("220")
        )
        with pg.expect_navigation():
            pg.select_option("select[name=testo]", "zavarnoe")
        S["filter_zavarnoe_rows"] = pg.locator(".cmp tbody tr").count() == 2
        with pg.expect_navigation():  # выбранные условия видны над результатом; «Сбросить всё» снимает их
            pg.click(".applied__reset")
        S["filter_reset"] = pg.url.endswith("/recepty/")
        pg.goto(BASE + "/recepty/?testo=zavarnoe&duhovka=net")
        S["filter_empty"] = pg.locator(".empty h2").count() == 1
        with pg.expect_navigation():  # снять одно условие — второе остаётся
            pg.click(".applied__chip >> nth=0")
        S["filter_chip_removes_one"] = pg.url.endswith("/recepty/?duhovka=net") and pg.locator(".applied__chip").count() == 1
        pg.goto(BASE + "/poisk/?q=" + "  ЗАВАРНОЙ  ")
        S["search_case_spaces"] = pg.locator(".bcard").count() > 0
        pg.goto(BASE + "/poisk/?q=печенье")
        S["search_pechene"] = pg.locator(".bcard").count() > 0
        # «Пеку несколько» (перенесено из C): пустой выбор, счётчик, группы духовки, список, память, 400
        pg.goto(BASE + "/pechem/")
        pg.evaluate("localStorage.clear(); 0")
        pg.reload()
        url0 = pg.url
        pg.click(".bform .bbtn")
        S["batch_empty_submit_blocked"] = pg.url == url0
        pg.locator(".bpick label", has_text="Лимонный кекс").click()
        pg.locator(".bpick label", has_text="Мягкое печенье").click()
        pg.locator(".bpick label", has_text="без выпечки").click()
        S["batch_count_updates"] = pg.locator("[data-b-count]").inner_text() == "Отмечено: 3"
        with pg.expect_navigation():
            pg.click(".bform .bbtn")
        S["batch_oven_groups_shown"] = pg.locator(".ovenline b").all_inner_texts() == ["180 °C", "Без духовки"]
        S["batch_combined_list_rows"] = pg.locator(".blist li").count()
        pg.locator(".blist input").first.check()
        pg.reload()
        S["batch_bought_mark_persists"] = pg.locator(".blist input").first.is_checked()
        pg.goto(BASE + "/recepty/")
        S["batch_header_link_keeps_choice"] = "r=" in (pg.locator("[data-b-link]").get_attribute("href") or "")
        pg.goto(BASE + "/pechem/")
        S["batch_form_remembers_choice"] = pg.locator(".bpick input:checked").count() == 3
        resp = pg.goto(BASE + "/pechem/?r=neizvestno")
        S["batch_unknown_recipe_400_alert"] = resp.status == 400 and pg.locator(".err[role=alert]").count() == 1
        S["batch_storage_namespace_own"] = all(k.startswith("fbb.") for k in pg.evaluate("Object.keys(localStorage)"))
        resp = pg.goto(BASE + "/nesushchestvuet/")
        S["real_404"] = resp.status == 404
        ctx.close()
        ctx = br.new_context(java_script_enabled=False)
        pg = ctx.new_page()
        pg.goto(BASE + "/recept/pirozhnye-lebedi/")
        S["nojs_steps"] = pg.locator(".method-b > li").count() > 0
        S["nojs_pitfalls"] = pg.locator(".pitfall").count() > 0
        S["nojs_timers_and_marks_hidden"] = (
            pg.locator(".timer").first.is_hidden() and pg.locator(".done").first.is_hidden()
        )
        ctx.close()
        br.close()
    res["actions"] = dict(S)
    return res


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--shots")
    ap.add_argument("--out")
    a = ap.parse_args(argv)
    res = run(Path(a.shots) if a.shots else None)
    txt = json.dumps(res, ensure_ascii=False, indent=1)
    if a.out:
        Path(a.out).write_text(txt + "\n")
    print(txt)
    # итог: провал любого сценария или нарушение axe — код 1 (а не только запись в выводе)
    failed = [k for k, v in res["actions"].items() if v is False]
    axe_bad = [k for k, v in res.get("axe", {}).items() if k != "version" and v]
    if failed or axe_bad:
        print("FAILED:", failed, "axe:", axe_bad, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
