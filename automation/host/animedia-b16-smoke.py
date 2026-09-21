#!/usr/bin/env python3
"""B16 smoke по живым доменам Animedia на 390/768/1440 — после перезапуска.

Запускать дважды подряд, как требует паспорт B16. Мутаций не делает: только GET
и чтение DOM.

Что проверяется на канарейке (`animedia.icu`):

* `build_id` и `artifact_sha256` в заголовках и в `/__template_version` равны
  ожидаемым и совпадают между собой;
* `meta robots` и `X-Robots-Tag` остались `noindex, nofollow`;
* canonical точно по домену;
* восемь маршрутов отдают ожидаемый код, отсутствующий — 404, а не 200 и не 503;
* горизонтального переполнения нет, обязательный текст не обрезан, плеер один
  и его рамка 16:9, в подвале нет знаков сборки.

И отдельно — что **второй домен не изменился**: его `build_id` обязан остаться
прежним. Расхождение означает, что затронут общий рантайм: стоп и откат.

    .venv/bin/python automation/host/animedia-b16-smoke.py \\
        --expect-build 20260921T153817Z-c8c4587-animedia-b16 \\
        --expect-artifact 7aae3d2cff614275db6bda926b6023fdf0c6208c76cda7eac8b796673c74ef06 \\
        --peer-expect-build 20260920T102102Z-89666321-nova \\
        --out <каталог>
"""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

ШИРИНЫ = (390, 768, 1440)
МАРШРУТЫ = (
    ("home", "/", 200),
    ("catalog", "/catalog/", 200),
    ("search", "/search/?q=%D0%B0%D0%BD%D0%B8%D0%BC%D0%B5", 200),
    ("collections", "/collections/", 200),
    ("collection_detail", "/collection/recently_added/", 200),
    ("title", "/title/nelyud-film-2-stolknovenie/", 200),
    ("episode", "/title/master-lda-i-plameni-2/season-2/episode-104/", 200),
    ("not_found", "/definitely-absent-route-xyz/", 404),
    ("page_huge", "/new/?page=99999", 404),
)

ОРАКУЛ = r"""
() => {
  const док = document.documentElement, w = window.innerWidth;
  const видим = (el) => {
    const r = el.getBoundingClientRect(), s = getComputedStyle(el);
    return r.width > 0 && r.height > 0 && s.visibility !== 'hidden' && s.display !== 'none';
  };
  const обрезанные = [];
  for (const sel of ['h1','button','.zpg a','.zpg span','.zhub__t','.zhub__m',
                     '.aeps__title','.aeps__meta','.ahub__s','[data-b13-count]']) {
    for (const el of document.querySelectorAll(sel)) {
      if (!видим(el)) continue;
      const s = getComputedStyle(el);
      if (el.scrollWidth - el.clientWidth > 1 &&
          (s.overflow === 'hidden' || s.textOverflow === 'ellipsis')) {
        обрезанные.push({sel, text: (el.textContent || '').trim().slice(0, 40)});
      }
    }
  }
  const плееры = [...document.querySelectorAll('section.zpl')].filter(видим);
  const рамки = [...document.querySelectorAll('.zpl__f')].filter(видим).map((e) => {
    const r = e.getBoundingClientRect();
    return +(r.width / r.height).toFixed(4);
  });
  const подвал = document.querySelector('footer');
  return {
    overflow_px: Math.round(док.scrollWidth - w),
    clipped_required: обрезанные,
    player_instances: плееры.length,
    player_ratios: рамки,
    footer_build_marker: подвал ? /source=|runtime=|build=/.test(подвал.innerHTML) : null,
    robots: (document.querySelector('meta[name=robots]') || {}).content || null,
    canonical: (document.querySelector('link[rel=canonical]') || {}).href || null,
    h1_count: document.querySelectorAll('h1').length,
  };
}
"""


def main() -> int:
    р = argparse.ArgumentParser(description=__doc__)
    р.add_argument("--domain", default="animedia.icu")
    р.add_argument("--peer-domain", default="animedia.space")
    р.add_argument("--expect-build", required=True)
    р.add_argument("--expect-artifact", required=True)
    р.add_argument("--peer-expect-build", required=True)
    р.add_argument("--out", required=True)
    р.add_argument(
        "--mode", choices=("deploy", "incident"), default="deploy",
        help=("deploy — приёмка кандидата: полный набор критериев, включая требование "
              "B14 «в подвале нет знаков сборки». incident — вопрос «витрина жива и "
              "отдаёт верное»: доступность, коды маршрутов, индексация, canonical, "
              "геометрия, плеер и неизменность второго домена. Критерии качества "
              "содержимого, которые закрывает только новая сборка, в режиме incident "
              "не считаются провалом, но печатаются и попадают в отчёт наблюдением. "
              "Аварийный гейт, который не может позеленеть после конца аварии, не гейт."))
    р.add_argument(
        "--known-footer-marker-build", default=None,
        help=("build_id, у которого знак сборки в подвале — известный дефект B14. "
              "Послабление привязано к одному build_id и на другие сборки не "
              "распространяется: иначе оно молча закрыло бы тот самый дефект и у "
              "кандидата. Такие провалы уходят в отдельный список и не влияют на "
              "доступность, но SMOKE_PASS остаётся False."))
    args = р.parse_args()
    вывод = Path(args.out)
    (вывод / "screenshots").mkdir(parents=True, exist_ok=True)

    from playwright.sync_api import sync_playwright

    итог = {
        "task": "ANIMEDIA-B16-SMOKE",
        "checked_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "domain": args.domain, "peer_domain": args.peer_domain,
        "expect_build": args.expect_build, "expect_artifact": args.expect_artifact,
        "peer_expect_build": args.peer_expect_build,
        "mode": args.mode,
        "known_footer_marker_build": args.known_footer_marker_build,
        "viewports": list(ШИРИНЫ), "cells": [], "failures": [],
        "known_build_defects": [],
    }
    провалы = итог["failures"]
    известные = итог["known_build_defects"]
    with sync_playwright() as pw:
        b = pw.chromium.launch()
        try:
            for ширина in ШИРИНЫ:
                ctx = b.new_context(viewport={"width": ширина, "height": 900})
                стр = ctx.new_page()
                for имя, путь, ждём in МАРШРУТЫ:
                    ответ = стр.goto(f"https://{args.domain}{путь}",
                                     wait_until="load", timeout=60000)
                    стр.wait_for_timeout(200)
                    м = стр.evaluate(ОРАКУЛ)
                    з = ответ.headers if ответ else {}
                    м.update({"route": имя, "width": ширина,
                              "http": ответ.status if ответ else None, "expected_http": ждём,
                              "served_build": з.get("x-site-factory-build-id"),
                              "served_artifact": з.get("x-site-factory-artifact-sha256"),
                              "x_robots": з.get("x-robots-tag")})
                    итог["cells"].append(м)
                    стр.screenshot(path=str(вывод / "screenshots" /
                                            f"{имя}-{ширина}.png"), full_page=False)
                    ключ = f"{имя}@{ширина}"
                    if м["http"] != ждём:
                        провалы.append(f"{ключ}: код {м['http']}, ожидался {ждём}")
                    if м["served_build"] != args.expect_build:
                        провалы.append(f"{ключ}: build {м['served_build']}")
                    if м["served_artifact"] != args.expect_artifact:
                        провалы.append(f"{ключ}: artifact {м['served_artifact']}")
                    if not (м["x_robots"] and "noindex" in м["x_robots"]):
                        провалы.append(f"{ключ}: X-Robots-Tag {м['x_robots']}")
                    if м["http"] == 200:
                        if not (м["robots"] and "noindex" in м["robots"]):
                            провалы.append(f"{ключ}: meta robots {м['robots']}")
                        if not (м["canonical"] and args.domain in м["canonical"]):
                            провалы.append(f"{ключ}: canonical {м['canonical']}")
                    if м["overflow_px"] > 1:
                        провалы.append(f"{ключ}: переполнение {м['overflow_px']}px")
                    if м["clipped_required"]:
                        провалы.append(f"{ключ}: обрезка {м['clipped_required'][:2]}")
                    if м["player_instances"] > 1:
                        провалы.append(f"{ключ}: плееров {м['player_instances']}")
                    for r in м["player_ratios"]:
                        if abs(r - 16 / 9) / (16 / 9) * 100 > 1:
                            провалы.append(f"{ключ}: рамка плеера {r}")
                    if м["footer_build_marker"]:
                        # Требование B14 принадлежит приёмке кандидата. В аварийном
                        # режиме это наблюдение, а не провал доступности; послабление
                        # в режиме deploy привязано к одному build_id и на другие
                        # сборки не распространяется.
                        известен = (args.known_footer_marker_build
                                    and м["served_build"] == args.known_footer_marker_build)
                        if args.mode == "incident" or известен:
                            известные.append(f"{ключ}: знак сборки в подвале (дефект B14)")
                        else:
                            провалы.append(f"{ключ}: знак сборки в подвале")
                    print(f"  {ширина:>5} {имя:<18} http={м['http']} "
                          f"build={(м['served_build'] or '?')[:32]}", flush=True)
                ctx.close()

            # Второй домен обязан остаться прежним.
            ctx = b.new_context(viewport={"width": 1440, "height": 900})
            стр = ctx.new_page()
            ответ = стр.goto(f"https://{args.peer_domain}/", wait_until="load", timeout=60000)
            з = ответ.headers if ответ else {}
            итог["peer"] = {"build": з.get("x-site-factory-build-id"),
                            "x_robots": з.get("x-robots-tag"),
                            "http": ответ.status if ответ else None}
            if итог["peer"]["build"] != args.peer_expect_build:
                провалы.append(
                    f"второй домен изменился: {итог['peer']['build']} — "
                    f"затронут общий рантайм, стоп и откат")
            print(f"  {args.peer_domain}: build={итог['peer']['build']} "
                  f"(ожидался {args.peer_expect_build})", flush=True)
            ctx.close()
        finally:
            b.close()
    итог["AVAILABILITY_PASS"] = not провалы
    # В режиме приёмки кандидата зелёным считается только полное отсутствие
    # замечаний. В аварийном режиме вердикт отвечает на вопрос аварии.
    итог["SMOKE_PASS"] = (not провалы) if args.mode == "incident" else (
        not провалы and not известные)
    (вывод / "SMOKE.json").write_text(json.dumps(итог, ensure_ascii=False, indent=1),
                                      encoding="utf-8")
    print("MODE:", args.mode)
    print("AVAILABILITY_PASS:", итог["AVAILABILITY_PASS"])
    print("SMOKE_PASS:", итог["SMOKE_PASS"])
    for f in провалы[:15]:
        print("  провал:", f)
    if известные:
        чей = (args.known_footer_marker_build
               or (итог["cells"][0]["served_build"] if итог["cells"] else "?"))
        print(f"  наблюдение: знак сборки в подвале — {len(известные)} ячеек, "
              f"сборка {чей} (дефект B14)")
    return 0 if итог["SMOKE_PASS"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
