#!/usr/bin/env python3
"""Живая проверка витрины Zona: маршруты, ширины, ворота и скриншоты.

Одного «страница открылась» мало: витрина уже отдавала 200 с обрезанным
временем и с кнопкой, которая ничего не делает. Поэтому здесь на каждой
ширине снимается геометрия и данные, а не только картинка, и каждый снимок
подписан тем, что именно он доказывает.

Запуск:
    python3 scripts/reconciliation/verify_zona_live.py <origin> <метка> <каталог>
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

ORIGIN = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:9120"
МЕТКА = sys.argv[2] if len(sys.argv) > 2 else "after"
ВЫХОД = Path(sys.argv[3] if len(sys.argv) > 3
             else "artifacts/evidence/zona-slider-date-deploy-01/screenshots")

ШИРИНЫ = (390, 768, 1440)

#: Маршруты приёмки. Тайтл и серия подставляются с живой главной: жёстко
#: зашитый slug однажды исчезнет из каталога, и проверка начнёт врать.
МАРШРУТЫ: list[tuple[str, str]] = [
    ("home", "/"),
    ("catalog", "/catalog/"),
    ("new", "/new/"),
    ("search", "/search/?q=matrix"),
    ("search_empty", "/search/?q=zzznothingatall"),
    ("notfound", "/no-such-page-here/"),
]

ЗАМЕР = """
() => {
  const doc = document.documentElement;
  const карточки = [...document.querySelectorAll('a.zt, a.zadded__row')];
  const обрезано = [];
  document.querySelectorAll('.zt__t, .zadded__t').forEach(t => {
    if (t.scrollHeight > t.clientHeight + 1 && !t.hasAttribute('data-clamp-allowed'))
      обрезано.push((t.textContent || '').slice(0, 40));
  });
  const времена = [...document.querySelectorAll('.zadded__when')]
    .map(e => (e.textContent || '').trim());
  const рельсы = [...document.querySelectorAll('.zrl')].map(rl => {
    const vp = rl.querySelector('.zrl__vp');
    const p = rl.querySelector('[data-rl="prev"]');
    const n = rl.querySelector('[data-rl="next"]');
    if (!vp) return null;
    const cs = p ? getComputedStyle(p) : null;
    return {
      w: Math.round(vp.clientWidth),
      scrollLeft: Math.round(vp.scrollLeft),
      maxScroll: Math.round(vp.scrollWidth - vp.clientWidth),
      prevDisabled: p ? p.hasAttribute('disabled') : null,
      nextDisabled: n ? n.hasAttribute('disabled') : null,
      prevVisible: cs ? (cs.visibility !== 'hidden' && parseFloat(cs.opacity) > 0.01) : null,
    };
  }).filter(Boolean);
  const битые = [...document.images].filter(i => i.complete && i.naturalWidth === 0).length;
  const плееры = document.querySelectorAll('iframe[src], [data-player] iframe').length;
  // Оболочка плеера обязана быть на странице серии ещё до нажатия, а тяжёлый
  // iframe — не обязан: контракт требует ноль кадров до действия зрителя.
  const оболочка = document.querySelectorAll('[data-player], .zplayer, #player').length;
  const авто = [...document.querySelectorAll('iframe[src]')]
    .filter(f => /autoplay=1|autoplay=true/i.test(f.src)).length;
  return {
    title: document.title,
    h1: (document.querySelector('h1') || {}).textContent || null,
    h1count: document.querySelectorAll('h1').length,
    scrollW: doc.scrollWidth,
    innerW: window.innerWidth,
    overflowX: doc.scrollWidth > window.innerWidth + 1,
    cards: карточки.length,
    clippedUndeclared: обрезано,
    addedLabels: времена.slice(0, 6),
    rails: рельсы,
    brokenImages: битые,
    players: плееры,
    playerShell: оболочка,
    autoplay: авто,
    robotsMeta: (document.querySelector('meta[name="robots"]') || {}).content || null,
  };
}
"""


def main() -> int:
    ВЫХОД.mkdir(parents=True, exist_ok=True)
    строки: list[dict[str, object]] = []

    with sync_playwright() as p:
        браузер = p.chromium.launch()
        try:
            # Живые адреса тайтла и серии берутся с главной.
            контекст = браузер.new_context(viewport={"width": 1440, "height": 900})
            стр = контекст.new_page()
            стр.goto(f"{ORIGIN}/", wait_until="load", timeout=120000)
            ссылки = стр.eval_on_selector_all(
                "a[href^='/title/']", "els => els.map(e => e.getAttribute('href'))")
            # Плеер живёт на сериях, а на главной сериалов может не оказаться
            # вовсе: там витрина показывает то, что недавно добавили. Раздел
            # сериалов — единственное место, где сериал гарантированно есть.
            try:
                стр.goto(f"{ORIGIN}/series/", wait_until="load", timeout=120000)
                ссылки = стр.eval_on_selector_all(
                    "a[href^='/title/']",
                    "els => els.map(e => e.getAttribute('href'))") + ссылки
            except Exception:
                pass
            стр.close()
            контекст.close()

            маршруты = list(МАРШРУТЫ)
            серия = None
            if ссылки:
                маршруты.append(("title", ссылки[0]))
                # Ссылку на серию с главной не взять — её там нет. Обходим
                # страницы тайтлов, пока не встретится сериал: плеер надо
                # проверять на настоящей серии, а не на придуманном адресе.
                контекст = браузер.new_context(viewport={"width": 1440, "height": 900})
                стр = контекст.new_page()
                for href in ссылки[:12]:
                    try:
                        стр.goto(f"{ORIGIN}{href}", wait_until="load", timeout=120000)
                        найдено = стр.eval_on_selector_all(
                            "a[href*='/season-'][href*='/episode-']",
                            "els => els.map(e => e.getAttribute('href'))")
                        if найдено:
                            серия = найдено[0]
                            маршруты.append(("title_series", href))
                            break
                    except Exception:
                        continue
                стр.close()
                контекст.close()
            if серия:
                маршруты.append(("episode", серия))

            for ширина in ШИРИНЫ:
                контекст = браузер.new_context(
                    viewport={"width": ширина, "height": 900}, device_scale_factor=1)
                for имя, путь in маршруты:
                    страница = контекст.new_page()
                    ответ = None
                    try:
                        ответ = страница.goto(f"{ORIGIN}{путь}",
                                              wait_until="load", timeout=120000)
                        страница.wait_for_timeout(350)
                        замер = страница.evaluate(ЗАМЕР)
                        # На странице серии проверяется и сам запуск: после
                        # нажатия кадр обязан появиться, но ровно один.
                        if имя == "episode":
                            кнопка = страница.query_selector(
                                "[data-play], .zplay, a[href='#player'], button:has-text('Смотреть')")
                            if кнопка:
                                try:
                                    кнопка.click(timeout=5000)
                                    страница.wait_for_timeout(2500)
                                except Exception:
                                    pass
                            замер["playersAfterClick"] = страница.evaluate(
                                "() => document.querySelectorAll('iframe[src]').length")
                        снимок = ВЫХОД / f"{МЕТКА}_{имя}_{ширина}.png"
                        страница.screenshot(path=str(снимок), full_page=False)
                        строки.append({
                            "route": имя, "path": путь, "viewport": ширина,
                            "status": ответ.status if ответ else None,
                            "screenshot": снимок.name, **замер,
                        })
                    except Exception as e:
                        строки.append({"route": имя, "path": путь,
                                       "viewport": ширина, "error": str(e)})
                    finally:
                        страница.close()
                контекст.close()
        finally:
            браузер.close()

    ok = [r for r in строки if "error" not in r]
    ворота = {
        "ROWS": len(строки),
        "ERRORS": len(строки) - len(ok),
        "HORIZONTAL_OVERFLOW_COUNT": sum(1 for r in ok if r.get("overflowX")),
        "UNDECLARED_CLAMP_COUNT": sum(len(r.get("clippedUndeclared") or []) for r in ok),
        "TIMESTAMP_TRUNCATED_COUNT": sum(
            1 for r in ok for t in (r.get("addedLabels") or [])
            if t.endswith(tuple(f", {h:02d}" for h in range(24)))),
        "BROKEN_IMAGE_COUNT": sum(r.get("brokenImages") or 0 for r in ok),
        "AUTOPLAY_COUNT": sum(r.get("autoplay") or 0 for r in ok),
        "PLAYER_IFRAMES_BEFORE_ACTION": max([r.get("players") or 0 for r in ok] or [0]),
        "PLAYER_INSTANCE_MAX_AFTER_CLICK": max(
            [r.get("playersAfterClick") or 0 for r in ok
             if r.get("route") == "episode"] or [0]),
        "PLAYER_SHELL_ON_EPISODE": min(
            [r.get("playerShell") or 0 for r in ok
             if r.get("route") == "episode"] or [0]),
        "SOFT_404_COUNT": sum(
            1 for r in ok if r.get("route") == "notfound" and r.get("status") == 200),
        "MULTIPLE_H1_COUNT": sum(1 for r in ok if (r.get("h1count") or 0) > 1),
        "RAIL_PREV_ENABLED_AT_START": sum(
            1 for r in ok for rl in (r.get("rails") or [])
            if rl.get("scrollLeft") == 0 and rl.get("prevDisabled") is False
            and rl.get("maxScroll", 0) > 0),
        "ROUTES_NOT_200": sorted({
            f"{r['route']}:{r['status']}" for r in ok
            if r.get("route") != "notfound" and r.get("status") != 200}),
        "NOINDEX_EVERYWHERE": all(
            "noindex" in (r.get("robotsMeta") or "").lower() for r in ok),
    }
    отчёт = {"origin": ORIGIN, "метка": МЕТКА, "ворота": ворота, "строки": строки}
    (ВЫХОД.parent / f"LIVE_MATRIX_{МЕТКА}.json").write_text(
        json.dumps(отчёт, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(ворота, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
