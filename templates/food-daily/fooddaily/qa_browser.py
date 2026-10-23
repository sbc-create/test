"""Браузерная приёмка preview: сценарии E2E, лабораторные метрики, скриншоты.

Playwright (Python) из окружения пользователя; axe-core в этом worktree
недоступен (node_modules — висячая ссылка), поэтому доступность проверяется
собственным набором правил ниже и так и называется. Метрики — лабораторные
(одна машина, без троттлинга сети), полевыми данными не являются.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
BASE = os.environ.get("QA_BASE", "http://127.0.0.1:8876").rstrip("/")  # чистая копия на другом порту
VIEWPORTS = {"mobile": {"width": 390, "height": 844}, "desktop": {"width": 1440, "height": 900}}
SHOTS = {
    "party": "/na-kompaniyu/?r=plov-s-kuricej&r=grecheskij-salat&gosti=8",
    "home": "/",
    "catalog": "/recepty/",
    "fridge": "/iz-holodilnika/?est=kurica&est=ris",
    "catalog-table": "/recepty/?sort=vremya&vid=tablica",
    "recipe": "/recept/syrniki-s-ezhevikoj/",
    "tag": "/produkty/kurica/",
    "article": "/sovety/priznaki-gotovnosti/",
}

A11Y_JS = r"""
() => {
  const out = [];
  document.querySelectorAll('img').forEach(i => { if (!i.hasAttribute('alt')) out.push('img без alt: ' + i.src); });
  document.querySelectorAll('input, select, textarea').forEach(el => {
    if (el.type === 'hidden') return;
    const id = el.id; const lab = (id && document.querySelector('label[for="' + id + '"]')) || el.closest('label');
    if (!lab && !el.getAttribute('aria-label')) out.push('поле без подписи: ' + (el.name || el.outerHTML.slice(0, 60)));
  });
  document.querySelectorAll('button, a[href]').forEach(el => {
    if (el.closest('[hidden]') || el.hidden) return;
    const name = (el.innerText || '').trim() || el.getAttribute('aria-label') || (el.querySelector('.sr') && el.querySelector('.sr').textContent);
    if (!name) out.push('элемент без имени: ' + el.outerHTML.slice(0, 80));
  });
  const h1 = document.querySelectorAll('h1').length; if (h1 !== 1) out.push('h1 на странице: ' + h1);
  let prev = 1; document.querySelectorAll('main h1, main h2, main h3').forEach(h => {
    const l = +h.tagName[1]; if (l > prev + 1) out.push('пропуск уровня заголовка: ' + h.tagName + ' ' + h.textContent.slice(0, 40)); prev = l; });
  if (!document.querySelector('main')) out.push('нет landmark main');
  if (!document.documentElement.lang) out.push('нет lang');
  return out;
}"""

CONTRAST_JS = r"""
() => {
  function lum(c) { const m = c.match(/\d+(\.\d+)?/g).map(Number); const a = m.slice(0,3).map(v => { v/=255; return v<=0.03928? v/12.92 : Math.pow((v+0.055)/1.055, 2.4); }); return 0.2126*a[0]+0.7152*a[1]+0.0722*a[2]; }
  function bg(el) { while (el) { const c = getComputedStyle(el).backgroundColor; if (c && !c.endsWith(', 0)') && c !== 'transparent') return c; el = el.parentElement; } return 'rgb(255,255,255)'; }
  const bad = []; const sel = 'p, li, a, span, dt, dd, label, h1, h2, h3, button, small, output';
  document.querySelectorAll(sel).forEach(el => {
    if (!el.offsetParent || !el.textContent.trim() || el.closest('[hidden]')) return;
    const cs = getComputedStyle(el); const fg = cs.color; const b = bg(el);
    const L1 = lum(fg), L2 = lum(b); const r = (Math.max(L1,L2)+0.05)/(Math.min(L1,L2)+0.05);
    const big = parseFloat(cs.fontSize) >= 24 || (parseFloat(cs.fontSize) >= 18.66 && +cs.fontWeight >= 700);
    if (r < (big ? 3 : 4.5)) bad.push(el.tagName + ' «' + el.textContent.trim().slice(0, 30) + '» ' + r.toFixed(2));
  });
  return [...new Set(bad)].slice(0, 20);
}"""

PERF_JS = r"""
() => new Promise(res => {
  let lcp = 0, cls = 0;
  new PerformanceObserver(l => { for (const e of l.getEntries()) lcp = e.startTime; }).observe({type: 'largest-contentful-paint', buffered: true});
  new PerformanceObserver(l => { for (const e of l.getEntries()) if (!e.hadRecentInput) cls += e.value; }).observe({type: 'layout-shift', buffered: true});
  setTimeout(() => {
    const nav = performance.getEntriesByType('navigation')[0];
    const bytes = performance.getEntriesByType('resource').reduce((s, r) => s + (r.transferSize || 0), nav.transferSize || 0);
    res({lcp_ms: Math.round(lcp), cls: +cls.toFixed(4), ttfb_ms: Math.round(nav.responseStart), dom_ms: Math.round(nav.domContentLoadedEventEnd), bytes, requests: performance.getEntriesByType('resource').length + 1});
  }, 1500);
})"""


AXE = ROOT / "qa" / "node_modules" / "axe-core" / "axe.min.js"
AXE_PAGES = [
    "/",
    "/iz-holodilnika/",
    "/iz-holodilnika/?est=kurica&est=ris",
    "/iz-holodilnika/?est=kvantovyj",
    "/recepty/?sort=vremya&vid=tablica",
    "/recepty/",
    "/recepty/supy/",
    "/recepty/zavtraki/",
    "/produkty/kurica/",
    "/sposob/na-skovorode/",
    "/podborki/bystro-do-30-minut/",
    "/recept/syrniki-s-ezhevikoj/",
    "/recept/plov-s-kuricej/",
    "/recept/grecheskij-salat/",
    "/recept/domashnyaya-shaurma/",
    "/recept/tefteli-v-tomatnom-souse/",
    "/sovety/priznaki-gotovnosti/",
    "/poisk/?q=zzz",
    "/nesushchestvuet/",
]

KEYBOARD_JS = r"""
() => {
  const el = document.activeElement; if (!el || el === document.body) return null;
  const cs = getComputedStyle(el); const r = el.getBoundingClientRect();
  return {tag: el.tagName, text: (el.innerText || el.getAttribute('aria-label') || el.value || '').trim().slice(0, 40),
          outline: cs.outlineStyle !== 'none' && parseFloat(cs.outlineWidth) > 0, visible: r.width > 0 && r.height > 0};
}"""


def axe_and_keyboard(browser) -> dict:
    out = {"axe_version": None, "pages": {}, "keyboard": {}}
    if not AXE.exists():
        out["status"] = "NOT_RUN: axe-core не установлен (cd templates/food-daily/qa && npm ci)"
        return out
    for vname in ("mobile", "desktop"):
        # bypass_csp — только в тестовом браузере: строгая CSP сайта (script-src 'self') иначе не даёт внедрить axe
        ctx = browser.new_context(viewport=VIEWPORTS[vname], locale="ru-RU", bypass_csp=True)
        page = ctx.new_page()
        for path in AXE_PAGES:
            page.goto(BASE + path)
            page.add_script_tag(path=str(AXE))
            res = page.evaluate("""async () => { const r = await axe.run(document, {runOnly: {type: 'tag',
                values: ['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa', 'best-practice']}});
                return {v: axe.version, violations: r.violations.map(v => ({id: v.id, impact: v.impact,
                  nodes: v.nodes.length, sample: v.nodes[0] && v.nodes[0].target.join(' ')})), passes: r.passes.length}; }""")
            out["axe_version"] = res["v"]
            out["pages"][f"{vname}:{path}"] = {
                "violations": res["violations"],
                "passes": res["passes"],
            }
        ctx.close()
    # проход клавиатурой по главной и рецепту: порядок фокуса и видимость обводки
    ctx = browser.new_context(viewport=VIEWPORTS["desktop"], locale="ru-RU")
    page = ctx.new_page()
    for path in ("/", "/recept/syrniki-s-ezhevikoj/"):
        page.goto(BASE + path)
        seen = []
        for _ in range(30):
            page.keyboard.press("Tab")
            f = page.evaluate(KEYBOARD_JS)
            if f:
                seen.append(f)
        out["keyboard"][path] = {
            "steps": len(seen),
            "without_visible_outline": [x for x in seen if not x["outline"]],
            "order_head": [f"{x['tag']}:{x['text']}" for x in seen[:12]],
        }
    ctx.close()
    return out


def commit() -> str:
    return subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()


def run(shots_dir: Path | None) -> dict:
    res: dict = {
        "base": BASE,
        "commit_head": commit(),
        "at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "scenarios": {},
        "a11y": {},
        "contrast": {},
        "perf_lab": {},
        "console_errors": [],
        "screenshots": [],
    }
    S = res["scenarios"]
    with sync_playwright() as p:
        # установленная версия браузера, без скачивания новых
        exe = (
            Path.home()
            / ".cache/ms-playwright/chromium_headless_shell-1234/chrome-headless-shell-linux64/chrome-headless-shell"
        )
        browser = p.chromium.launch(executable_path=str(exe) if exe.exists() else None)
        for vname, vp in VIEWPORTS.items():
            ctx = browser.new_context(viewport=vp, device_scale_factor=1, locale="ru-RU")
            page = ctx.new_page()
            page.on(
                "console",
                lambda m, v=vname: m.type == "error" and res["console_errors"].append(f"{v}: {m.text}"),
            )
            page.on("pageerror", lambda e, v=vname: res["console_errors"].append(f"{v}: {e}"))
            for name, path in SHOTS.items():
                page.goto(BASE + path, wait_until="load")
                res["perf_lab"][f"{vname}:{name}"] = page.evaluate(PERF_JS)
                res["a11y"][f"{vname}:{name}"] = page.evaluate(A11Y_JS)
                res["contrast"][f"{vname}:{name}"] = page.evaluate(CONTRAST_JS)
                if shots_dir:
                    shots_dir.mkdir(parents=True, exist_ok=True)
                    f = shots_dir / f"{name}-{vname}.png"
                    page.screenshot(path=str(f), full_page=True)
                    res["screenshots"].append(
                        str(f.resolve().relative_to(ROOT)) if ROOT in f.resolve().parents else str(f)
                    )
            # горизонтальная прокрутка на телефоне недопустима
            for name, path in SHOTS.items():
                page.goto(BASE + path)
                S[f"{vname}:{name}:no_hscroll"] = page.evaluate("document.documentElement.scrollWidth <= innerWidth")
            ctx.close()

        ctx = browser.new_context(viewport=VIEWPORTS["mobile"], locale="ru-RU")
        page = ctx.new_page()
        # порции: 2 → 4 удваивает граммы, время не меняется
        page.goto(BASE + "/recept/syrniki-s-ezhevikoj/")
        before = page.locator(".ing").nth(1).locator(".ing__amount").inner_text()
        time_before = page.locator(".facts").inner_text()
        page.click("[data-servings-control] [data-step='1']")
        page.click("[data-servings-control] [data-step='1']")
        after = page.locator(".ing").nth(1).locator(".ing__amount").inner_text()
        S["servings_scale_2_to_4"] = {
            "before": before,
            "after": after,
            "ok": before == "190 г" and after == "380 г",
            "time_unchanged": page.locator(".facts").inner_text() == time_before,
        }
        # 22.10: выход не указан («1 порция» источника) — кратный пересчёт ×1 → ×1½, без «порций»
        page.goto(BASE + "/recept/tykvennyj-sup-pyure/")
        page.click("[data-servings-control] [data-step='1']")
        S["servings_unknown_yield_multiplier"] = (
            page.locator("[data-servings-control] output").inner_text() == "×1½ от рецепта"
            and page.locator(".ing").first.locator(".ing__amount").inner_text() == "750 г"
        )
        page.goto(BASE + "/recept/syrniki-s-ezhevikoj/")
        # список покупок
        page.click("[data-add-list]")
        page.goto(BASE + "/spisok-pokupok/")
        S["shopping_list_items"] = page.locator("[data-list] li").count()
        page.locator("[data-list] li input").first.check()
        page.click("[data-list-clear-done]")
        S["shopping_list_after_clear_done"] = page.locator("[data-list] li").count()
        # избранное
        page.goto(BASE + "/recept/syrniki-s-ezhevikoj/")
        page.click(".recipe__actions [data-fav]")
        S["favorite_counter"] = page.locator("[data-fav-count]").inner_text()
        page.goto(BASE + "/izbrannoe/")
        S["favorites_page_items"] = page.locator("[data-fav-grid] .card").count()
        # режим готовки и клавиатура
        page.goto(BASE + "/recept/syrniki-s-ezhevikoj/")
        page.click("[data-cook-open]")
        first = page.locator("[data-cook-count]").inner_text()
        # слой режима готовки закрывает весь экран (а не встаёт текстом внизу страницы)
        cover = page.evaluate(
            "(() => { const r = document.querySelector('[data-cook]').getBoundingClientRect();"
            " return r.top === 0 && r.left === 0 && r.width === innerWidth && r.height === innerHeight; })()"
        )
        page.keyboard.press("ArrowRight")
        second = page.locator("[data-cook-count]").inner_text()
        page.keyboard.press("Escape")
        S["cooking_mode"] = {
            "first": first,
            "after_arrow": second,
            "closed_on_esc": page.locator("[data-cook]").is_hidden(),
            "covers_screen": cover,
        }
        # фильтры: выбор применяется, сброс и пустой результат
        page.goto(BASE + "/recepty/")
        with page.expect_navigation():
            page.select_option("select[name=tip]", "supy")
        S["filter_supy_cards"] = page.locator(".grid .card").count()
        # выбранное условие видно над результатом; «Сбросить всё» снимает всё
        S["filter_reset_link"] = page.locator(".applied__reset", has_text="Сбросить всё").count() == 1
        page.goto(BASE + "/recepty/?produkt=tvorog&tip=supy")
        S["filter_empty_state"] = page.locator(".empty h2").inner_text() if page.locator(".empty h2").count() else None
        with page.expect_navigation():  # снять одно условие — второе остаётся
            page.click(".applied__chip >> nth=0")
        S["filter_chip_removes_one"] = (
            page.url.endswith("/recepty/?tip=supy") and page.locator(".applied__chip").count() == 1
        )
        with page.expect_navigation():
            page.click(".applied__reset")
        S["filter_reset_all"] = page.url.endswith("/recepty/") and page.locator(".applied__chip").count() == 0
        # поиск: ё/е, регистр, пробелы
        page.goto(BASE + "/poisk/?q=" + "  ТВОРОЖНАЯ   запеканка ")
        S["search_case_spaces"] = page.locator(".grid .card").count()
        page.goto(BASE + "/poisk/?q=клёцками")
        S["search_yo"] = page.locator(".grid .card").count()
        page.goto(BASE + "/poisk/?q=тыква")
        S["search_by_ingredient_tykva"] = page.locator(".grid .card").count()
        # клавиатура: первый Tab — ссылка «К содержимому»
        page.goto(BASE + "/")
        page.keyboard.press("Tab")
        S["first_tab_skip_link"] = page.evaluate("document.activeElement.className") == "skip"
        # вариант C: на компанию — форма на своей странице (на главной — переход к ней)
        page.evaluate("localStorage.clear(); 0")
        page.goto(BASE + "/na-kompaniyu/")
        url0 = page.url
        page.click(".pform .btn")
        S["party_empty_submit_blocked"] = page.url == url0
        page.locator(".ppick label", has_text="Плов с курицей").click()
        page.locator(".ppick label", has_text="Греческий салат").click()
        page.fill("#gosti", "8")
        S["party_count_updates"] = page.locator("[data-p-count]").inner_text() == "Отмечено блюд: 2"
        with page.expect_navigation():
            page.click(".pform .btn")
        S["party_list_scaled"] = (
            page.locator(".plist li").count() > 0 and "8 гостей" in page.locator(".lead").inner_text()
        )
        page.locator(".plist input").first.check()
        page.reload()
        S["party_bought_persists"] = page.locator(".plist input").first.is_checked()
        page.goto(BASE + "/recepty/")
        S["party_header_link_keeps_choice"] = "gosti=8" in (page.locator("[data-p-link]").get_attribute("href") or "")
        page.goto(BASE + "/")
        # главная: кнопка «Собрать список» ведёт к последнему выбору, форма открывается с ним
        page.click(".promo [data-p-link]")
        S["party_home_remembers_choice"] = (
            page.locator(".ppick input:checked").count() == 2 and page.locator("#gosti").input_value() == "8"
        )
        resp = page.goto(BASE + "/na-kompaniyu/?gosti=50")
        S["party_bad_guests_400_alert"] = resp.status == 400 and page.locator(".err[role=alert]").count() == 1
        S["party_storage_namespace_own"] = all(k.startswith("fdc.") for k in page.evaluate("Object.keys(localStorage)"))
        # перенесено из B: подбор «что есть дома» — выбор, результаты, память, пустой выбор, неверный продукт
        with page.expect_navigation():
            page.locator(".tools a", has_text="Что есть дома").click()
        S["fridge_header_link"] = page.url.endswith("/iz-holodilnika/")
        page.locator(".pick__item", has_text="Курица").click()
        page.locator(".pick__item", has_text="Рис").click()
        hint = page.locator("[data-fridge-hint]").inner_text()
        with page.expect_navigation():
            page.click(".pick .btn")
        first = page.locator(".match__t").first.inner_text()
        rows = page.locator(".match__row").count()
        page.goto(BASE + "/iz-holodilnika/")
        remembered = page.locator("input[value=kurica]").is_checked() and page.locator("input[value=ris]").is_checked()
        page.goto(BASE + "/iz-holodilnika/?est=kurica&est=ris")
        with page.expect_navigation():
            page.click("[data-fridge-clear]")
        cleared = not page.locator("input[value=kurica]").is_checked()
        url_before = page.url
        page.click(".pick .btn")
        empty_blocked = page.url == url_before and "хотя бы один" in page.locator("[data-fridge-hint]").inner_text()
        # 22.10: поиск по списку продуктов (по началу слова) и удаление одного выбранного продукта
        page.goto(BASE + "/iz-holodilnika/")
        page.fill("#pf", "кар")
        S["fridge_filter_word_start"] = page.locator(".pick__list li:visible").all_inner_texts() == ["Картофель"]
        page.fill("#pf", "ананас")
        S["fridge_filter_none_message"] = page.locator("[data-fridge-none]").is_visible()
        page.goto(BASE + "/iz-holodilnika/?est=tvorog&est=kefir&est=moloko")
        S["fridge_full_composition_needs_more"] = (
            page.locator(".match__row").count() > 0 and page.locator(".match__row--all").count() == 0
        )
        with page.expect_navigation():
            page.locator(".pchip", has_text="Кефир").click()
        S["fridge_chip_removes_one"] = page.url.endswith("?est=tvorog&est=moloko")
        resp = page.goto(BASE + "/iz-holodilnika/?est=kvantovyj")
        S["fridge_hint_counts_two"] = hint == "Отмечено: 2"
        S["fridge_first_has_both_plov"] = first == "Плов с курицей на сковороде"
        S["fridge_results_listed"] = rows
        S["fridge_remembers_selection"] = remembered
        S["fridge_clear_forgets_selection"] = cleared
        S["fridge_empty_submit_blocked"] = empty_blocked
        S["fridge_unknown_product_400_alert"] = resp.status == 400 and page.locator(".err[role=alert]").count() == 1
        # подсказки и замены — только подтверждённые источником, со ссылкой на шаг (13.10.2026)
        page.goto(BASE + "/recept/lenivye-vareniki/")
        links = page.locator("aside .src-step")
        S["tips_subs_link_to_source_step"] = links.count() == 2 and all(
            (links.nth(i).get_attribute("href") or "").startswith("https://") for i in range(links.count())
        )
        page.goto(BASE + "/recept/grecheskij-salat/")
        S["unsourced_tips_subs_hidden"] = page.locator("aside.tips, aside.subs").count() == 0
        # перенесено из B: каталог — сортировка по времени и вид-таблица применяются сразу
        page.goto(BASE + "/recepty/")
        with page.expect_navigation():
            page.select_option("select[name=sort]", "vremya")
        with page.expect_navigation():
            page.select_option("select[name=vid]", "tablica")
        times = page.locator(".cat td[data-label='Время']").all_inner_texts()

        def mins(t):
            m = re.fullmatch(r"(?:(\d+) ч)?\s*(?:(\d+) мин)?", t.strip())
            return int(m.group(1) or 0) * 60 + int(m.group(2) or 0) if m and t.strip() != "—" else 10**6

        S["catalog_table_sort_by_time"] = bool(times) and [mins(x) for x in times] == sorted(mins(x) for x in times)
        S["catalog_view_noindex"] = "noindex" in (page.locator("meta[name=robots]").get_attribute("content") or "")
        S["storage_namespace_own_after_fridge"] = all(
            k.startswith("fdc.") for k in page.evaluate("Object.keys(localStorage)")
        )
        # без JS рецепт целиком в HTML
        ctx.close()
        res["accessibility"] = axe_and_keyboard(browser)
        ctx = browser.new_context(java_script_enabled=False)
        page = ctx.new_page()
        page.goto(BASE + "/recept/syrniki-s-ezhevikoj/")
        S["nojs_recipe_steps"] = page.locator(".step").count()
        S["nojs_ingredients"] = page.locator(".ing").count()
        S["nojs_fav_button_hidden"] = page.locator(".recipe__actions [data-fav]").is_hidden()
        ctx.close()
        browser.close()
    acc = res["accessibility"]
    res["axe"] = {"version": acc.get("axe_version"), **{k: v["violations"] for k, v in acc.get("pages", {}).items()}}
    res["actions"] = {
        k: (all(x for x in v.values() if isinstance(x, bool)) if isinstance(v, dict) else v) for k, v in S.items()
    }
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
    axe_bad = [k for k, v in res["axe"].items() if k != "version" and v]
    if failed or axe_bad:
        print("FAILED:", failed, "axe:", axe_bad, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
