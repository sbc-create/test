#!/usr/bin/env python3
"""Проверка отдаваемого состояния витрин Lords на 390/768/1440 — без мутаций.

Зачем именно так. Домены Lords не входят в `inventory/network-allowlist.yaml`,
и расширять его по своей инициативе нельзя. Но проверять нужно то, что витрина
действительно отдаёт, а не фикстуру. Поэтому Chromium получает
`--host-resolver-rules`: имя домена разрешается в `127.0.0.1:<порт витрины>`.
Запрос уходит на тот самый процесс, который обслуживает домен, и несёт
настоящий заголовок `Host` — то есть витрина выбирает свой профиль как в бою.
Внешняя сеть при этом не затрагивается.

Ничего не меняется: только GET и чтение DOM.
"""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

РЕЕСТР = Path("/srv/lords/.frontend/lords-runtime-registry.json")
ШИРИНЫ = (390, 768, 1440)
МАРШРУТЫ = (("home", "/"), ("catalog", "/catalog/"), ("new", "/new/"))

ОРАКУЛ_JS = r"""
() => {
  const вид = {w: window.innerWidth};
  const док = document.documentElement;
  const видим = (el) => {
    const r = el.getBoundingClientRect();
    const s = getComputedStyle(el);
    return r.width > 0 && r.height > 0 && s.visibility !== 'hidden' && s.display !== 'none';
  };
  const обязательные = ['h1', 'button', '.zpg a', '.zpg span', '.zadded__when'];
  const обрезанные = [];
  for (const sel of обязательные) {
    for (const el of document.querySelectorAll(sel)) {
      if (!видим(el)) continue;
      const s = getComputedStyle(el);
      if (el.scrollWidth - el.clientWidth > 1 &&
          (s.overflow === 'hidden' || s.textOverflow === 'ellipsis')) {
        обрезанные.push({sel, text: (el.textContent || '').trim().slice(0, 40),
                         scrollW: el.scrollWidth, clientW: el.clientWidth});
      }
    }
  }
  let битые = 0;
  for (const img of document.querySelectorAll('img')) {
    if (img.complete && img.naturalWidth === 0 && !img.hidden) битые++;
  }
  const шапка = document.querySelector('header, .zhd, .ztop');
  const подвал = document.querySelector('footer');
  return {
    overflow_px: Math.round(док.scrollWidth - вид.w),
    clipped_required: обрезанные,
    broken_images: битые,
    h1_count: document.querySelectorAll('h1').length,
    h1_text: (document.querySelector('h1') || {textContent: ''}).textContent.trim().slice(0, 60),
    header_present: !!шапка,
    footer_present: !!подвал,
    footer_has_build_marker: подвал
      ? /source=|runtime=|build=/.test(подвал.innerHTML) : null,
    robots: (document.querySelector('meta[name=robots]') || {}).content || null,
    canonical: (document.querySelector('link[rel=canonical]') || {}).href || null,
  };
}
"""


def main() -> int:
    р = argparse.ArgumentParser(description=__doc__)
    р.add_argument("--sites", default="lords-02,lords-03")
    р.add_argument("--out", required=True)
    р.add_argument("--shots", action="store_true")
    args = р.parse_args()
    вывод = Path(args.out)
    (вывод / "screenshots").mkdir(parents=True, exist_ok=True)

    реестр = json.loads(РЕЕСТР.read_text(encoding="utf-8"))["sites"]
    цели = []
    for sid in [s.strip() for s in args.sites.split(",") if s.strip()]:
        з = реестр[sid]
        цели.append((sid, з["exact_domain"], з["port"], з["release_link"]))

    правила = ",".join(f"MAP {домен} 127.0.0.1:{порт}" for _, домен, порт, _ in цели)
    from playwright.sync_api import sync_playwright

    итог = {
        "task": "LORDS-SERVED-VERIFY",
        "checked_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "browser": "chromium",
        "resolver_rules": правила,
        "mutations_performed": 0,
        "viewports": list(ШИРИНЫ),
        "sites": {sid: {"domain": д, "port": п,
                        "release_link_target": str(Path(ссылка).resolve())
                        if Path(ссылка).exists() else None}
                  for sid, д, п, ссылка in цели},
        "cells": [],
    }
    with sync_playwright() as pw:
        браузер = pw.chromium.launch(args=[f"--host-resolver-rules={правила}"])
        try:
            for ширина in ШИРИНЫ:
                ctx = браузер.new_context(viewport={"width": ширина, "height": 900})
                стр = ctx.new_page()
                for sid, домен, _порт, _ссылка in цели:
                    for имя, путь in МАРШРУТЫ:
                        ответ = стр.goto(f"http://{домен}{путь}",
                                         wait_until="load", timeout=60000)
                        стр.wait_for_timeout(200)
                        м = стр.evaluate(ОРАКУЛ_JS)
                        заг = ответ.headers if ответ else {}
                        м.update({
                            "site": sid, "domain": домен, "route": имя,
                            "width": ширина, "http": ответ.status if ответ else None,
                            "served_build": заг.get("x-site-factory-build-id"),
                            "served_revision": заг.get("x-site-factory-template-revision"),
                            "served_artifact": заг.get("x-site-factory-artifact-sha256"),
                            "x_robots": заг.get("x-robots-tag"),
                        })
                        итог["cells"].append(м)
                        if args.shots:
                            стр.screenshot(
                                path=str(вывод / "screenshots" /
                                         f"{sid}-{имя}-{ширина}.png"), full_page=False)
                        print(f"  {ширина:>5} {sid:<9} {имя:<8} http={м['http']} "
                              f"overflow={м['overflow_px']} clip={len(м['clipped_required'])} "
                              f"build={м['served_build']}", flush=True)
                ctx.close()
        finally:
            браузер.close()
    (вывод / "LORDS_SERVED_MATRIX.json").write_text(
        json.dumps(итог, ensure_ascii=False, indent=1), encoding="utf-8")
    print("матрица:", вывод / "LORDS_SERVED_MATRIX.json", "ячеек", len(итог["cells"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
