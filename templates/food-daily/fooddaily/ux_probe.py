"""UX-измерения референсов в браузере с ограничениями источника.

* JS выключен; загружается только документ и CSS того же хоста —
  сторонние скрипты, реклама, счётчики и изображения не запрашиваются
  (allowlist и «один запрос на хост»). Поэтому замеры описывают серверный
  HTML без рекламы: рекламные места оцениваются по маркерам в HTML.
* Перед каждым документом — проверка robots.txt.
* Тексты, изображения и идентификаторы не сохраняются; скриншоты — только
  в var/ (вне git), для внутреннего сравнения.
"""

from __future__ import annotations

import json
import re
import time
import urllib.parse
from pathlib import Path

from playwright.sync_api import sync_playwright

from .http import REPO, allowed_hosts, load_config
from .inventory import CRAWL_ROOT
from .robots import Robots

ROOT = Path(__file__).resolve().parents[1]
UA = load_config()["user_agent"]
AD_MARKERS = (
    r"yandex_rtb|Ya\.Context|adfox|googlesyndication|adsbygoogle|adriver|betweendigital|getintent|"
    r"mediametrics|relap\.io|smi2|rtb\.|ad-block|data-ad-|\bbanner\b|advert"
)
VIDEO_MARKERS = r"<video|youtube\.com/embed|rutube\.ru/play|vk\.com/video_ext|dzen\.ru/embed|player\.vimeo"

MEASURE_JS = r"""
() => {
  const find = (re) => { const els = [...document.querySelectorAll('h1,h2,h3,h4,div,span,p,li,section')];
    for (const el of els) { if (el.children.length < 6 && re.test((el.textContent || '').trim().slice(0, 40))) { const r = el.getBoundingClientRect(); if (r.height > 0) return Math.round(r.top + scrollY); } } return null; };
  const h1 = document.querySelector('h1');
  return {
    doc_height: document.documentElement.scrollHeight,
    h1: h1 ? h1.textContent.trim().slice(0, 80) : null,
    y_ingredients: find(/^Ингредиент|^Состав|^Продукты|^Ingredients/i),
    y_steps: find(/^(Пошаговый|Способ приготовления|Приготовление|Как приготовить|Шаги|Инструкция|Method|Directions)/i),
    links: document.querySelectorAll('a[href]').length,
    forms_search: document.querySelectorAll('form input[type=search], form input[name=q], form input[name*=search], form input[name*=query]').length,
    servings_controls: [...document.querySelectorAll('input,button,select')].filter(e => /порц|serving/i.test((e.getAttribute('aria-label')||'') + (e.name||'') + (e.parentElement ? e.parentElement.textContent.slice(0, 60) : ''))).length,
    nav_links: document.querySelectorAll('nav a').length,
    breadcrumbs_visible: !!document.querySelector('[class*=breadcrumb], nav[aria-label*=крошк], [itemtype*=BreadcrumbList]'),
  };
}"""


def pick_pages(host_id: str) -> dict:
    base = next(h["base"] for h in load_config()["hosts"] if h["id"] == host_id)
    pages = {"home": base + "/"}
    sample = json.loads((ROOT / "docs" / "audit" / "verify-sample.json").read_text())["hosts"].get(host_id, {})
    recipes = [r["url"] for r in sample.get("rows", []) if r.get("type") == "recipe" and r.get("status") == 200][:3]
    cats = [
        r["url"] for r in sample.get("rows", []) if r.get("type") in ("category", "tag") and r.get("status") == 200
    ][:1]
    for i, u in enumerate(recipes):
        pages[f"recipe{i + 1}"] = u
    if cats:
        pages["category"] = cats[0]
    return pages


def probe(hosts: list[str], extra: dict[str, dict], shots: Path | None) -> dict:
    allowed = allowed_hosts()
    out = {
        "at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "mode": "js_off_same_host_css_only",
        "hosts": {},
    }
    exe = (
        Path.home()
        / ".cache/ms-playwright/chromium_headless_shell-1234/chrome-headless-shell-linux64/chrome-headless-shell"
    )
    with sync_playwright() as p:
        br = p.chromium.launch(executable_path=str(exe) if exe.exists() else None)
        for h in hosts:
            pages = {**pick_pages(h), **extra.get(h, {})}
            rp = CRAWL_ROOT / h / "robots.txt"
            robots = Robots(rp.read_text() if rp.exists() else "")
            host = urllib.parse.urlsplit(pages["home"]).hostname
            ctx = br.new_context(
                viewport={"width": 390, "height": 844},
                user_agent=UA,
                java_script_enabled=False,
                locale="ru-RU",
            )
            stats = {"blocked": 0, "loaded": 0}

            def make_route(host: str, stats: dict):
                # Playwright передаёт (route, request): параметры по умолчанию тут не годятся
                def route(r, req):
                    u = urllib.parse.urlsplit(req.url)
                    same = u.hostname == host and u.hostname in allowed
                    if same and req.resource_type in ("document", "stylesheet"):
                        stats["loaded"] += 1
                        return r.continue_()
                    stats["blocked"] += 1
                    return r.abort()

                return route

            ctx.route("**/*", make_route(host, stats))
            page = ctx.new_page()
            res = {}
            for name, url in pages.items():
                if not robots.can_fetch(UA, url):
                    res[name] = {"url": url, "robots": "disallow"}
                    continue
                t0 = time.time()
                try:
                    resp = page.goto(url, wait_until="load", timeout=45000)
                except Exception as e:  # тайм-аут или отказ — фиксируем, не повторяем
                    res[name] = {"url": url, "error": str(e)[:160]}
                    continue
                html = page.content()
                m = page.evaluate(MEASURE_JS)
                ld = re.findall(r'"@type"\s*:\s*"([A-Za-z]+)"', html)
                res[name] = {
                    "url": url,
                    "status": resp.status if resp else None,
                    "load_s": round(time.time() - t0, 2),
                    "html_kb": round(len(html.encode()) / 1024),
                    "ad_markers": len(re.findall(AD_MARKERS, html, re.I)),
                    "video_embeds": len(re.findall(VIDEO_MARKERS, html, re.I)),
                    "jsonld_types": sorted(set(ld))[:12],
                    **m,
                }
                if shots and name in ("home", "recipe1"):
                    shots.mkdir(parents=True, exist_ok=True)
                    page.screenshot(path=str(shots / f"{h}-{name}-mobile.png"), full_page=False)
                time.sleep(float(load_config()["limits"]["min_delay_seconds"]))
            res["_requests"] = stats
            out["hosts"][h] = res
            ctx.close()
        br.close()
    return out


def main(argv=None) -> int:
    import argparse

    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--hosts",
        default="1000-menu,eda-rambler,gastronom,povarenok,povar,iamcook,edimdoma,food-ru,menunedeli,russianfood",
    )
    ap.add_argument("--out", default=str(ROOT / "docs" / "audit" / "ux-probe.json"))
    a = ap.parse_args(argv)
    extra = {
        "bbcgoodfood": {"home": "https://www.bbcgoodfood.com/recipes"},
        "seriouseats": {"home": "https://www.seriouseats.com/"},
    }
    res = probe(a.hosts.split(","), extra, REPO / "var" / "food-daily" / "ux-shots")
    Path(a.out).write_text(json.dumps(res, ensure_ascii=False, indent=1) + "\n")
    for h, r in res["hosts"].items():
        print(
            h,
            json.dumps(
                {
                    k: (
                        {
                            kk: v.get(kk)
                            for kk in (
                                "status",
                                "html_kb",
                                "ad_markers",
                                "video_embeds",
                                "y_ingredients",
                                "y_steps",
                                "doc_height",
                                "forms_search",
                                "servings_controls",
                            )
                        }
                        if isinstance(v, dict) and "url" in v
                        else v
                    )
                    for k, v in r.items()
                },
                ensure_ascii=False,
            ),
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
