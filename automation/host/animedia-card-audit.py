#!/usr/bin/env python3
"""Разбор карточек Animedia по блокам: что на них видно, а что только в разметке.

Владелец видит на живых витринах «почти одни постеры». Счётчик карточек этого
не покажет: подпись может быть в разметке и при этом иметь нулевую высоту,
нулевую прозрачность или быть срезанной рамкой. Поэтому здесь меряется
видимость каждого поля карточки, а не его наличие.

Блоки различаются: лента первого экрана, сетка каталога, «Похожее аниме»,
рекомендации, нижние блоки внутренних страниц. По каждому — свой разбор.

    .venv/bin/python automation/host/animedia-card-audit.py \\
        --runtime automation/host/animedia-frontend.py --out <каталог>
"""
from __future__ import annotations

import argparse
import json
import os
import socket
import subprocess
import time
from pathlib import Path

КОРЕНЬ = Path(__file__).resolve().parents[2]
ШИРИНЫ = (390, 768, 1440)
СТРАНИЦЫ = (
    ("home", "/"),
    ("catalog", "/catalog/"),
    ("title", "/title/nelyud-film-2-stolknovenie/"),
    ("episode", "/title/master-lda-i-plameni-2/season-2/episode-104/"),
    ("collection_detail", "/collection/recently_added/"),
    ("search", "/search/?q=%D0%B0%D0%BD%D0%B8%D0%BC%D0%B5"),
)

РАЗБОР = r"""
() => {
  const cs = getComputedStyle;
  const видим = (el) => {
    if (!el) return false;
    const r = el.getBoundingClientRect(), s = cs(el);
    return r.width > 0 && r.height > 0 && s.visibility !== 'hidden'
           && s.display !== 'none' && parseFloat(s.opacity) > 0.05;
  };
  const текст = (el) => (el ? (el.textContent || '').trim() : '');
  // Блок карточки — ближайшая секция или лента, в которой она лежит.
  const имя_блока = (к) => {
    const с = к.closest('section, .ahero, .zsec, .zg, .zrl');
    if (!с) return 'без блока';
    const з = с.querySelector('h1,h2,h3');
    const подпись = з ? текст(з).slice(0, 40) : '';
    return (подпись || String(с.className).split(' ')[0] || с.tagName).slice(0, 40);
  };
  const карточки = [...document.querySelectorAll('a.zt')];
  const по_блокам = {};
  for (const к of карточки) {
    const блок = имя_блока(к);
    const r = к.getBoundingClientRect();
    const п = к.querySelector('.zt__p');
    const т = к.querySelector('.zt__t');
    const м = к.querySelector('.zt__m');
    const о = к.querySelector('.zt__r');
    const серии = к.querySelector('.zt__eps');
    const оценки = [...к.querySelectorAll('.zt__rate')];
    const запись = {
      w: Math.round(r.width), h: Math.round(r.height),
      poster_visible: видим(п),
      title_in_dom: !!т, title_visible: видим(т),
      title_text: текст(т).slice(0, 40),
      title_h: т ? Math.round(т.getBoundingClientRect().height) : 0,
      title_font: т ? cs(т).fontSize : null,
      meta_in_dom: !!м, meta_visible: видим(м), meta_text: текст(м).slice(0, 40),
      rating_in_dom: !!о, rating_visible: видим(о), rating_text: текст(о).slice(0, 40),
      variant: к.getAttribute('data-card-variant') || '',
      eps_badge_visible: видим(серии),
      eps_known: !!(серии && серии.getAttribute('data-eps-total')),
      eps_badge_text: текст(серии),
      ratings_visible: оценки.filter(видим).length,
      ratings_sources: оценки.map((о) => о.getAttribute('data-rating-source')),
      ratings_values: оценки.map((о) => о.getAttribute('data-rating-value')),
      ratings_scales: оценки.map((о) => о.getAttribute('data-rating-scale')),
      ratings_text: оценки.map((о) => текст(о)).join(' | ').slice(0, 40),
      href: к.getAttribute('href'),
      clickable_area: Math.round(r.width * r.height),
    };
    (по_блокам[блок] = по_блокам[блок] || []).push(запись);
  }
  const свод = {};
  for (const [блок, список] of Object.entries(по_блокам)) {
    const n = список.length;
    const доля = (ф) => +(список.filter((x) => x[ф]).length / n).toFixed(2);
    свод[блок] = {
      cards: n,
      title_visible_share: доля('title_visible'),
      meta_visible_share: доля('meta_visible'),
      rating_visible_share: доля('rating_visible'),
      poster_visible_share: доля('poster_visible'),
      title_in_dom_share: доля('title_in_dom'),
      rating_in_dom_share: доля('rating_in_dom'),
      sample: список.slice(0, 3),
      unique_hrefs: new Set(список.map((x) => x.href)).size,
      unique_titles: new Set(список.map((x) => x.title_text).filter(Boolean)).size,
      variants: [...new Set(список.map((x) => x.variant))],
      eps_badge_share: доля('eps_badge_visible'),
      eps_data_hidden: список.filter((x) => x.eps_known && !x.eps_badge_visible).length,
      ratings_share: +(список.filter((x) => x.ratings_visible > 0).length / n).toFixed(2),
      two_ratings_share: +(список.filter((x) => x.ratings_visible >= 2).length / n).toFixed(2),
      zero_ratings_shown: список.filter(
        (x) => x.ratings_values.some((v) => !v || Number(v) === 0)).length,
    };
  }
  return {blocks: свод, cards_total: карточки.length};
}
"""


def поднять(рантайм: Path, витрина: str, лог: Path):
    корень = Path(os.environ.get("ANIMEDIA_RUNTIME_ROOT", "/srv/lords/.frontend"))
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        порт = s.getsockname()[1]
    окр = dict(os.environ)
    окр.update({"ANIMEDIA_TEMPLATE_MANIFEST": str(корень / f"template-manifest-{витрина}.json"),
                "ANIMEDIA_CATALOG": str(корень / f"{витрина}-catalog.json"),
                "ANIMEDIA_SITE_NAME": "Animedia", "PYTHONDONTWRITEBYTECODE": "1"})
    for чужое in ("LORDS_TEMPLATE_MANIFEST", "LORDS_CATALOG", "LORDS_DETAILS"):
        окр.pop(чужое, None)
    p = subprocess.Popen(["/usr/bin/python3", str(рантайм), "--port", str(порт)],
                         stdout=лог.open("w", encoding="utf-8"),
                         stderr=subprocess.STDOUT, env=окр, cwd=str(КОРЕНЬ))
    for _ in range(600):
        time.sleep(0.5)
        if p.poll() is not None:
            raise SystemExit(f"рантайм не поднялся, см. {лог}")
        try:
            with socket.create_connection(("127.0.0.1", порт), timeout=0.5):
                return p, порт
        except OSError:
            continue
    raise SystemExit("порт не открылся")


def main() -> int:
    р = argparse.ArgumentParser(description=__doc__)
    р.add_argument("--runtime", default="automation/host/animedia-frontend.py")
    р.add_argument("--site", default="animedia-01")
    р.add_argument("--domain", default="animedia.icu")
    р.add_argument("--out", required=True)
    a = р.parse_args()
    вывод = Path(a.out)
    вывод.mkdir(parents=True, exist_ok=True)
    процесс, порт = поднять(Path(a.runtime), a.site, вывод / "runtime.log")

    from playwright.sync_api import sync_playwright

    итог = {"task": "ANIMEDIA-CARD-AUDIT", "tenant": "animedia",
            "checked_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "runtime": a.runtime, "cells": [], "findings": []}
    находки = итог["findings"]
    правило = f"MAP {a.domain} 127.0.0.1:{порт}"
    try:
        with sync_playwright() as pw:
            b = pw.chromium.launch(args=[f"--host-resolver-rules={правило}"])
            try:
                for ширина in ШИРИНЫ:
                    ctx = b.new_context(viewport={"width": ширина, "height": 900})
                    стр = ctx.new_page()
                    for имя, путь in СТРАНИЦЫ:
                        стр.goto(f"http://{a.domain}{путь}", wait_until="load", timeout=60000)
                        стр.wait_for_timeout(250)
                        р_ = стр.evaluate(РАЗБОР)
                        итог["cells"].append({"route": имя, "width": ширина, **р_})
                        for блок, с in р_["blocks"].items():
                            ключ = f"{имя}@{ширина} «{блок}»"
                            if с["cards"] < 3:
                                continue
                            # Что карточка обязана показать, знает её вариант:
                            # у ленты первого экрана состав другой, и у
                            # оригинала он такой же — только название.
                            компактный = all(в == "compact" for в in с["variants"])
                            if с["title_visible_share"] < 0.95:
                                находки.append(
                                    f"{ключ}: название видно у "
                                    f"{int(с['title_visible_share'] * 100)}% карточек")
                            if not компактный:
                                if с["meta_visible_share"] < 0.95:
                                    находки.append(
                                        f"{ключ}: год и тип видны у "
                                        f"{int(с['meta_visible_share'] * 100)}% карточек")
                                if с["ratings_share"] < 0.5:
                                    находки.append(
                                        f"{ключ}: оценка видна лишь у "
                                        f"{int(с['ratings_share'] * 100)}% карточек")
                                # Счётчик серий рисуется только там, где число
                                # серий известно: у фильмов сезонов нет вовсе.
                                # Поэтому проверяется не доля, а честность —
                                # если данные у карточки есть, счётчик обязан
                                # быть виден.
                                if с["eps_data_hidden"]:
                                    находки.append(
                                        f"{ключ}: счётчик серий есть в данных, но скрыт "
                                        f"({с['eps_data_hidden']} карточек)")
                            if с["zero_ratings_shown"]:
                                находки.append(
                                    f"{ключ}: показан нулевой или пустой рейтинг "
                                    f"({с['zero_ratings_shown']})")
                            if с["unique_hrefs"] < с["cards"]:
                                находки.append(
                                    f"{ключ}: повторяющиеся карточки "
                                    f"({с['cards'] - с['unique_hrefs']} дублей)")
                        print(f"  {ширина:>5} {имя:<18} карточек {р_['cards_total']:>3} "
                              f"блоков {len(р_['blocks'])}", flush=True)
                    ctx.close()
            finally:
                b.close()
    finally:
        процесс.terminate()
        try:
            процесс.wait(timeout=20)
        except subprocess.TimeoutExpired:
            процесс.kill()
    итог["CARD_AUDIT_PASS"] = not находки
    (вывод / "CARD_AUDIT.json").write_text(json.dumps(итог, ensure_ascii=False, indent=1),
                                           encoding="utf-8")
    print("CARD_AUDIT_PASS:", итог["CARD_AUDIT_PASS"], "| находок:", len(находки))
    for f in находки[:25]:
        print("  •", f)
    return 0 if итог["CARD_AUDIT_PASS"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
