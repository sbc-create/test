#!/usr/bin/env python3
"""Браузерная приёмка zonafilm.cc: реальные страницы в реальном движке.

Отличие от `zonafilm-cc-acceptance.py`: там HTTP и разметка, здесь — то, что
видно и работает только после исполнения страницы. Ошибки консоли, неудавшиеся
запросы, битые изображения, горизонтальное переполнение, LCP и CLS, клавиатура
и focus-visible, отклик на настоящий клик.

Скриншоты снимаются на каждой ширине для каждого маршрута: владелец должен
увидеть витрину, а не прочитать о ней.

Ничего не меняет на сервере: только открывает страницы.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

ШИРИНЫ = [320, 390, 768, 1024, 1440, 1920]

#: Метрики собираются наблюдателями производительности самого браузера, а не
#: вычисляются по таймингам вручную: ручной счёт даёт число, похожее на LCP, но
#: не являющееся им.
СБОР_МЕТРИК = """
() => new Promise((resolve) => {
  const out = {lcp: null, cls: 0, longtasks: 0};
  try {
    new PerformanceObserver((l) => {
      const e = l.getEntries();
      if (e.length) out.lcp = e[e.length - 1].startTime;
    }).observe({type: 'largest-contentful-paint', buffered: true});
  } catch (e) {}
  try {
    new PerformanceObserver((l) => {
      for (const entry of l.getEntries()) {
        if (!entry.hadRecentInput) out.cls += entry.value;
      }
    }).observe({type: 'layout-shift', buffered: true});
  } catch (e) {}
  try {
    new PerformanceObserver((l) => { out.longtasks += l.getEntries().length; })
      .observe({type: 'longtask', buffered: true});
  } catch (e) {}
  const nav = performance.getEntriesByType('navigation')[0];
  out.ttfb = nav ? nav.responseStart : null;
  out.domContentLoaded = nav ? nav.domContentLoadedEventEnd : null;
  out.transferSize = nav ? nav.transferSize : null;
  setTimeout(() => resolve(out), 2500);
})
"""

ОСМОТР_СТРАНИЦЫ = """
() => {
  const doc = document.documentElement;
  const overflow = Math.max(0, doc.scrollWidth - doc.clientWidth);
  const wide = [...document.querySelectorAll('*')]
    .filter(el => el.getBoundingClientRect().right > doc.clientWidth + 2)
    .slice(0, 8)
    .map(el => (el.tagName + '.' + (el.className || '').toString().slice(0, 40)));
  const imgs = [...document.images];
  const broken = imgs.filter(i => i.complete && i.naturalWidth === 0)
    .map(i => i.currentSrc || i.src).slice(0, 10);
  const links = [...document.querySelectorAll('a[href]')];
  const small = links.filter(a => {
    const r = a.getBoundingClientRect();
    return r.width > 0 && r.height > 0 && (r.width < 24 || r.height < 24);
  }).length;
  const noAria = [...document.querySelectorAll('button, [role="button"], input, select')]
    .filter(el => !el.getAttribute('aria-label') && !el.getAttribute('title')
                  && !el.textContent.trim()
                  && !(el.labels && el.labels.length)).length;
  const h1 = document.querySelectorAll('h1').length;
  return {
    overflow_px: overflow, wide_elements: wide,
    images: imgs.length, broken_images: broken,
    links: links.length, small_targets: small,
    controls_without_label: noAria, h1: h1,
    title: document.title,
    robots: (document.querySelector('meta[name="robots"]') || {}).content || null,
    canonical: (document.querySelector('link[rel="canonical"]') || {}).href || null,
  };
}
"""

КЛАВИАТУРА = """
() => {
  const el = document.activeElement;
  if (!el || el === document.body) return {focused: null, visible: false};
  const s = getComputedStyle(el);
  const r = el.getBoundingClientRect();
  return {
    focused: el.tagName + (el.className ? '.' + el.className.toString().slice(0, 40) : ''),
    outline: s.outlineStyle + ' ' + s.outlineWidth,
    boxShadow: s.boxShadow.slice(0, 60),
    visible: (s.outlineStyle !== 'none' && parseFloat(s.outlineWidth) > 0)
             || s.boxShadow !== 'none',
    inViewport: r.top >= 0 && r.bottom <= innerHeight + 1,
  };
}
"""


def безопасное(текст: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", текст.lower()).strip("-") or "root"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--origin", required=True,
                        help="адрес, по которому браузер ходит, например "
                             "http://zonafilm.cc:9123 — имя домена настоящее")
    parser.add_argument("--host", required=True, help="домен витрины")
    parser.add_argument("--map-to", default="127.0.0.1",
                        help="куда резолвить домен: DNS-записи ещё нет, и имя "
                             "подставляется резолвером браузера, а не заголовком — "
                             "Host в extra_http_headers Chromium запрещает")
    parser.add_argument("--out", required=True)
    parser.add_argument("--shots", required=True)
    parser.add_argument("--route", action="append", default=[])
    parser.add_argument("--widths", default=",".join(str(w) for w in ШИРИНЫ))
    args = parser.parse_args()

    маршруты = args.route or ["/", "/catalog/", "/collection/recently_added/", "/search/?q=матрица"]
    ширины = [int(w) for w in args.widths.split(",") if w.strip()]
    каталог_снимков = Path(args.shots)
    каталог_снимков.mkdir(parents=True, exist_ok=True)

    отчёт: dict = {"origin": args.origin, "host": args.host, "widths": ширины,
                   "routes": маршруты, "pages": {},
                   "started_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}

    with sync_playwright() as pw:
        правила = f"MAP {args.host} {args.map_to}, MAP www.{args.host} {args.map_to}"
        браузер = pw.chromium.launch(args=[
            "--no-sandbox", "--disable-dev-shm-usage",
            f"--host-resolver-rules={правила}",
        ])
        отчёт["host_resolver_rules"] = правила
        for маршрут in маршруты:
            отчёт["pages"][маршрут] = {}
            for ширина in ширины:
                контекст = браузер.new_context(
                    viewport={"width": ширина, "height": 900},
                    device_scale_factor=1,
                    ignore_https_errors=True,
                )
                страница = контекст.new_page()
                ошибки: list[str] = []
                отказы: list[dict] = []
                страница.on("console", lambda m: ошибки.append(f"{m.type}: {m.text}"[:300])
                            if m.type in ("error",) else None)
                страница.on("pageerror", lambda e: ошибки.append(f"pageerror: {e}"[:300]))
                страница.on("requestfailed", lambda r: отказы.append(
                    {"url": r.url[:200], "failure": (r.failure or "")[:120]}))
                коды: dict[int, int] = {}
                страница.on("response", lambda r: коды.__setitem__(
                    r.status, коды.get(r.status, 0) + 1))

                запись: dict = {"width": ширина}
                try:
                    ответ = страница.goto(args.origin + маршрут, wait_until="load",
                                          timeout=60000)
                    запись["status"] = ответ.status if ответ else None
                    страница.wait_for_timeout(1200)
                    запись["metrics"] = страница.evaluate(СБОР_МЕТРИК)
                    запись["inspect"] = страница.evaluate(ОСМОТР_СТРАНИЦЫ)

                    # Клавиатура: один Tab обязан дать видимый фокус.
                    страница.keyboard.press("Tab")
                    запись["keyboard"] = страница.evaluate(КЛАВИАТУРА)

                    # Отклик на настоящий клик: приближение INP. Кликается
                    # первая ссылка, которая никуда не уводит, либо кнопка.
                    начало = time.monotonic()
                    try:
                        цель = страница.query_selector("button, [role='button'], summary")
                        if цель:
                            цель.click(timeout=3000)
                            страница.wait_for_timeout(120)
                        запись["interaction_ms"] = round(
                            (time.monotonic() - начало) * 1000 - 120, 1)
                    except Exception as e:
                        запись["interaction_ms"] = None
                        запись["interaction_error"] = f"{type(e).__name__}"

                    имя = f"{безопасное(маршрут)}-{ширина}.png"
                    страница.screenshot(path=str(каталог_снимков / имя),
                                        full_page=(ширина in (390, 1440)))
                    запись["screenshot"] = имя
                except Exception as e:
                    запись["error"] = f"{type(e).__name__}: {e}"[:300]

                запись["console_errors"] = ошибки
                запись["failed_requests"] = отказы
                запись["response_codes"] = {str(k): v for k, v in sorted(коды.items())}
                отчёт["pages"][маршрут][str(ширина)] = запись
                контекст.close()
        браузер.close()

    # --- сводка -----------------------------------------------------------
    все = [з for м in отчёт["pages"].values() for з in м.values()]
    lcp = [з["metrics"]["lcp"] for з in все
           if з.get("metrics") and з["metrics"].get("lcp")]
    cls = [з["metrics"]["cls"] for з in все if з.get("metrics")]
    отчёт["summary"] = {
        "pages_measured": len(все),
        "console_errors": sum(len(з.get("console_errors") or []) for з in все),
        "failed_requests": sum(len(з.get("failed_requests") or []) for з in все),
        "broken_images": sum(len((з.get("inspect") or {}).get("broken_images") or [])
                             for з in все),
        "horizontal_overflow_pages": [
            f'{м} @{ш}' for м, по_ширине in отчёт["pages"].items()
            for ш, з in по_ширине.items()
            if (з.get("inspect") or {}).get("overflow_px", 0) > 0],
        "http_5xx": sum(v for з in все for k, v in (з.get("response_codes") or {}).items()
                        if k.startswith("5")),
        "http_4xx": sum(v for з in все for k, v in (з.get("response_codes") or {}).items()
                        if k.startswith("4")),
        "lcp_p75_ms": round(sorted(lcp)[int(len(lcp) * 0.75)], 1) if lcp else None,
        "cls_max": round(max(cls), 4) if cls else None,
        "keyboard_focus_visible_pages": sum(
            1 for з in все if (з.get("keyboard") or {}).get("visible")),
        "controls_without_label": sum(
            (з.get("inspect") or {}).get("controls_without_label", 0) for з in все),
        "errors": [з["error"] for з in все if з.get("error")],
    }
    отчёт["finished_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(отчёт, ensure_ascii=False, indent=2),
                              encoding="utf-8")
    print(json.dumps(отчёт["summary"], ensure_ascii=False, indent=2))
    плохо = (отчёт["summary"]["console_errors"] or отчёт["summary"]["broken_images"]
             or отчёт["summary"]["http_5xx"]
             or отчёт["summary"]["horizontal_overflow_pages"]
             or отчёт["summary"]["errors"])
    return 1 if плохо else 0


if __name__ == "__main__":
    raise SystemExit(main())
