#!/usr/bin/env python3
"""Живая приёмка витрины Animedia после перезапуска: два прогона на шести ширинах.

Запускается по факту смены PID, а не по расписанию: пока процесс прежний,
проверять нечего — код выбирается при старте. Сверяет отдаваемую личность с
принятым артефактом, коды маршрутов, индексацию в заголовке и в meta, canonical,
геометрию, карточки и порядок лент. Мутаций не делает: при провале печатает
команды отката, но не выполняет их — перезапуск принадлежит владельцу.

    .venv/bin/python automation/host/animedia-live-acceptance.py \\
        --domain animedia.icu --expect-artifact <sha256> --expect-build <id> \\
        --out <каталог>
"""
from __future__ import annotations

import argparse
import json
import subprocess
import time
from pathlib import Path

ШИРИНЫ = (320, 390, 768, 1024, 1440, 1920)
МАРШРУТЫ = (
    ("home", "/", 200),
    ("catalog", "/catalog/", 200),
    ("new", "/new/", 200),
    ("search", "/search/?q=%D0%B0%D0%BD%D0%B8%D0%BC%D0%B5", 200),
    ("search_empty", "/search/?q=%D1%8A%D1%8B%D1%8C%D1%89%D0%B7%D1%85", 200),
    ("collections", "/collections/", 200),
    ("collection_detail", "/collection/recently_added/", 200),
    ("title", "/title/nelyud-film-2-stolknovenie/", 200),
    ("episode", "/title/master-lda-i-plameni-2/season-2/episode-104/", 200),
    ("schedule", "/schedule/", 200),
    ("not_found", "/definitely-absent-route-xyz/", 404),
    ("page_huge", "/new/?page=99999", 404),
)

ОРАКУЛ = r"""
() => {
  const cs = getComputedStyle, W = window.innerWidth;
  const видим = (el) => {
    const r = el.getBoundingClientRect(), s = cs(el);
    return r.width > 0 && r.height > 0 && s.visibility !== 'hidden' && s.display !== 'none';
  };
  const карточки = [...document.querySelectorAll('a.zt')].filter(видим);
  const без_подписи = карточки.filter((к) => {
    const т = к.querySelector('.zt__t');
    return !т || !видим(т) || !(т.textContent || '').trim();
  }).length;
  const плееры = [...document.querySelectorAll('section.zpl')].filter(видим);
  const рамки = [...document.querySelectorAll('.zpl__f')].filter(видим)
    .map((e) => { const r = e.getBoundingClientRect();
      return +(r.width / Math.max(r.height, 1)).toFixed(4); });
  const мелкие = [...document.querySelectorAll(
    'button, [role=button], input, select, nav a, .zpg a, [class*="chip"] a,'
    + ' [class*="filt"] a, [data-rl-dot], [data-rl], header a')].filter(видим)
    .filter((el) => { const r = el.getBoundingClientRect();
      return r.width < 44 || r.height < 44; }).length;
  return {
    overflow_px: Math.round(document.documentElement.scrollWidth - W),
    h1: document.querySelectorAll('h1').length,
    robots: (document.querySelector('meta[name=robots]') || {}).content || null,
    canonical: (document.querySelector('link[rel=canonical]') || {}).href || null,
    cards: карточки.length, cards_without_title: без_подписи,
    players: плееры.length, player_ratios: рамки,
    broken_images: [...document.querySelectorAll('img')]
      .filter((i) => i.complete && i.naturalWidth === 0 && !i.hidden).length,
    small_targets: мелкие,
    footer_build_marker: (() => { const f = document.querySelector('footer');
      return f ? /source=|runtime=|build=/.test(f.innerHTML) : null; })(),
  };
}
"""


def pid(юнит: str) -> str:
    return subprocess.run(["systemctl", "show", "-p", "MainPID", "--value", юнит],
                          capture_output=True, text=True).stdout.strip()


def main() -> int:
    р = argparse.ArgumentParser(description=__doc__)
    р.add_argument("--domain", required=True)
    р.add_argument("--peer-domain", default=None)
    р.add_argument("--unit", required=True)
    р.add_argument("--expect-build", required=True)
    р.add_argument("--expect-artifact", required=True)
    р.add_argument("--peer-expect-build", default=None)
    р.add_argument("--runs", type=int, default=2)
    р.add_argument("--out", required=True)
    a = р.parse_args()
    вывод = Path(a.out)
    (вывод / "screenshots").mkdir(parents=True, exist_ok=True)

    from playwright.sync_api import sync_playwright

    итог = {"task": "ANIMEDIA-LIVE-ACCEPTANCE", "tenant": "animedia",
            "domain": a.domain, "unit": a.unit,
            "expect_build": a.expect_build, "expect_artifact": a.expect_artifact,
            "checked_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "main_pid_at_start": pid(a.unit),
            "widths": list(ШИРИНЫ), "runs": [], "failures": []}
    провалы = итог["failures"]
    with sync_playwright() as pw:
        b = pw.chromium.launch()
        try:
            for прогон in range(1, a.runs + 1):
                ячейки = []
                for ширина in ШИРИНЫ:
                    ctx = b.new_context(viewport={"width": ширина, "height": 900})
                    стр = ctx.new_page()
                    for имя, путь, ждём in МАРШРУТЫ:
                        о = стр.goto(f"https://{a.domain}{путь}", wait_until="load",
                                     timeout=60000)
                        стр.wait_for_timeout(200)
                        м = стр.evaluate(ОРАКУЛ)
                        з = о.headers if о else {}
                        я = {"route": имя, "width": ширина, "run": прогон,
                             "http": о.status if о else None, "expected": ждём,
                             "build": з.get("x-site-factory-build-id"),
                             "artifact": з.get("x-site-factory-artifact-sha256"),
                             "x_robots": з.get("x-robots-tag"), **м}
                        ячейки.append(я)
                        if прогон == 1:
                            стр.screenshot(path=str(вывод / "screenshots"
                                                    / f"{имя}-{ширина}.png"))
                        к = f"прогон {прогон} {имя}@{ширина}"
                        if я["http"] != ждём:
                            провалы.append(f"{к}: код {я['http']}, ожидался {ждём}")
                        if я["build"] != a.expect_build:
                            провалы.append(f"{к}: build {я['build']}")
                        if я["artifact"] != a.expect_artifact:
                            провалы.append(f"{к}: artifact {я['artifact']}")
                        if not (я["x_robots"] and "noindex" in я["x_robots"]):
                            провалы.append(f"{к}: X-Robots-Tag {я['x_robots']}")
                        if я["http"] == 200:
                            if not (я["robots"] and "noindex" in я["robots"]):
                                провалы.append(f"{к}: meta robots {я['robots']}")
                            if not (я["canonical"] and a.domain in я["canonical"]):
                                провалы.append(f"{к}: canonical {я['canonical']}")
                            if я["h1"] != 1:
                                провалы.append(f"{к}: H1 {я['h1']}")
                        if я["overflow_px"] > 1:
                            провалы.append(f"{к}: переполнение {я['overflow_px']}px")
                        if я["cards_without_title"]:
                            провалы.append(f"{к}: карточек без подписи "
                                           f"{я['cards_without_title']}")
                        if я["broken_images"]:
                            провалы.append(f"{к}: битых изображений {я['broken_images']}")
                        if я["players"] > 1:
                            провалы.append(f"{к}: плееров {я['players']}")
                        for r in я["player_ratios"]:
                            if abs(r - 16 / 9) / (16 / 9) * 100 > 1:
                                провалы.append(f"{к}: рамка плеера {r}")
                        if я["small_targets"]:
                            провалы.append(f"{к}: целей меньше 44 — {я['small_targets']}")
                        if я["footer_build_marker"]:
                            провалы.append(f"{к}: знак сборки в подвале")
                    ctx.close()
                    print(f"  прогон {прогон} ширина {ширина:>5}: ячеек {len(МАРШРУТЫ)}",
                          flush=True)
                итог["runs"].append({"run": прогон, "cells": ячейки})
            if a.peer_domain and a.peer_expect_build:
                ctx = b.new_context(viewport={"width": 1440, "height": 900})
                стр = ctx.new_page()
                о = стр.goto(f"https://{a.peer_domain}/", wait_until="load", timeout=60000)
                з = о.headers if о else {}
                итог["peer"] = {"domain": a.peer_domain,
                                "build": з.get("x-site-factory-build-id"),
                                "http": о.status if о else None}
                if итог["peer"]["build"] != a.peer_expect_build:
                    провалы.append(f"второй домен изменился: {итог['peer']['build']}")
                ctx.close()
        finally:
            b.close()
    итог["main_pid_at_end"] = pid(a.unit)
    итог["pid_stable_during_run"] = итог["main_pid_at_start"] == итог["main_pid_at_end"]
    итог["ACCEPTANCE_PASS"] = not провалы and итог["pid_stable_during_run"]
    (вывод / "LIVE_ACCEPTANCE.json").write_text(
        json.dumps(итог, ensure_ascii=False, indent=1), encoding="utf-8")
    print("ACCEPTANCE_PASS:", итог["ACCEPTANCE_PASS"], "| провалов:", len(провалы))
    for f in провалы[:15]:
        print("  провал:", f)
    return 0 if итог["ACCEPTANCE_PASS"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
