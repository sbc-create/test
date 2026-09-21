#!/usr/bin/env python3
"""Измерение витрины Animedia для матрицы расхождений с оригиналом.

Измеряет то, что можно сравнить числом: геометрию, контейнер, шапку, логотип,
меню, поиск, первый экран, слайдер, карточки, постеры, сетку, типографику,
цвета, тени, рамки, радиусы, кнопки, фильтры, листалку, хлебные крошки,
рейтинги, метаданные, даты, плеер, подвал, мобильную навигацию и штатные
состояния. Субъективного «похоже» здесь нет.

Только чтение: GET и вычисления в DOM. Домены берутся из контракта контура,
выход — в каталог доказательств Animedia.

    .venv/bin/python automation/host/animedia-parity-probe.py \\
        --domain animedia.icu --label before --out <каталог>
"""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

ШИРИНЫ = (320, 390, 768, 1024, 1440, 1920)

# Маршруты нашей витрины. Первые четыре сопоставимы с оригиналом — по ним есть
# и снимки, и метрики; остальные измеряются для собственных ворот качества.
МАРШРУТЫ = (
    ("home", "/", 200, True),
    ("title", "/title/nelyud-film-2-stolknovenie/", 200, True),
    ("collections", "/collections/", 200, True),
    ("collection_detail", "/collection/recently_added/", 200, True),
    ("catalog", "/catalog/", 200, False),
    ("new", "/new/", 200, False),
    ("search", "/search/?q=%D0%B0%D0%BD%D0%B8%D0%BC%D0%B5", 200, False),
    ("search_empty", "/search/?q=%D1%8A%D1%8B%D1%8C%D1%89%D0%B7%D1%85", 200, False),
    ("schedule", "/schedule/", 200, False),
    ("episode", "/title/master-lda-i-plameni-2/season-2/episode-104/", 200, False),
    ("not_found", "/definitely-absent-route-xyz/", 404, False),
)

ОРАКУЛ = r"""
() => {
  const W = window.innerWidth, док = document.documentElement, cs = getComputedStyle;
  const видим = (el) => {
    if (!el) return false;
    const r = el.getBoundingClientRect(), s = cs(el);
    return r.width > 0 && r.height > 0 && s.visibility !== 'hidden' && s.display !== 'none';
  };
  const пр = (el) => { const r = el.getBoundingClientRect();
    return {w: Math.round(r.width), h: Math.round(r.height),
            x: Math.round(r.x), y: Math.round(r.y + window.scrollY)}; };
  const число = (v) => Math.round(parseFloat(v) || 0);
  const первый = (sel) => document.querySelector(sel);

  // --- шапка, логотип, меню, поиск ---
  const шапка = первый('header');
  const логотип = шапка && (шапка.querySelector('a[class*="logo"], .zhd__logo, [class*="brand"]')
                            || шапка.querySelector('a'));
  const пункты = [...document.querySelectorAll('header nav a, header a[href^="/"]')]
    .filter(видим).map((a) => ({text: (a.textContent || '').trim().slice(0, 30),
                                href: a.getAttribute('href')}));
  const поиск = первый('header input[type=search], header input[name=q], input[name=q]');

  // --- контейнер ---
  const обёртка = первый('.zwrap, main > .zwrap, main');
  const кос = обёртка ? cs(обёртка) : null;

  // --- карточки и сетка ---
  const карточки = [...document.querySelectorAll('article, .zt, .zcard, [class*="card"]')]
    .filter(видим);
  const сетка = карточки.length ? пр(карточки[0]) : null;
  let колонки = null, промежуток = null;
  if (карточки.length > 1) {
    const строки = {};
    карточки.forEach((к) => { const y = Math.round(к.getBoundingClientRect().y);
      (строки[y] = строки[y] || []).push(к); });
    const первая = Object.values(строки).sort((a, b) => b.length - a.length)[0] || [];
    колонки = первая.length;
    if (первая.length > 1) {
      const a = первая[0].getBoundingClientRect(), b = первая[1].getBoundingClientRect();
      промежуток = Math.round(Math.min(Math.abs(b.x - a.right), Math.abs(a.x - b.right)));
    }
  }
  const постеры = карточки.slice(0, 12).map((к) => {
    const i = к.querySelector('img'); if (!i) return null; const r = i.getBoundingClientRect();
    return {w: Math.round(r.width), h: Math.round(r.height),
            ratio: +(r.width / Math.max(r.height, 1)).toFixed(3),
            loading: i.getAttribute('loading'), hasSize: !!(i.width && i.height),
            broken: i.complete && i.naturalWidth === 0};
  }).filter(Boolean);
  const пк = карточки[0] ? cs(карточки[0]) : null;

  // --- слайдер ---
  const слайдер = первый('[class*="slider"], [class*="carousel"], .ahero, [data-slider]');
  let сведения_слайдера = null;
  if (слайдер) {
    const слайды = [...слайдер.querySelectorAll('[class*="slide"], li, article, a[href]')]
      .filter(видим);
    const ссылки = [...new Set(слайды.map((s) => (s.getAttribute('href')
      || (s.querySelector('a') || {}).getAttribute?.('href') || '')).filter(Boolean))];
    const картинки = [...new Set([...слайдер.querySelectorAll('img')]
      .map((i) => i.currentSrc || i.src).filter(Boolean))];
    сведения_слайдера = {
      box: пр(слайдер), slides: слайды.length, unique_hrefs: ссылки.length,
      unique_images: картинки.length,
      buttons: слайдер.querySelectorAll('button, [role=button]').length,
      indicators: слайдер.querySelectorAll('[class*="dot"], [class*="indicator"], [role=tab]').length,
      autoplay_attr: слайдер.getAttribute('data-autoplay'),
      is_single_image: картинки.length <= 1 && слайды.length <= 1,
    };
  }

  // --- секции ---
  const секции = [...document.querySelectorAll('section')].filter(видим).map((s, i) => {
    const з = s.querySelector('h1,h2,h3');
    return {idx: i, cls: s.className, title: з ? (з.textContent || '').trim().slice(0, 40) : '',
            ...пр(s)};
  });

  // --- типографика и цвета ---
  const тело = cs(document.body), h1 = первый('h1'), h2 = первый('h2');
  const ссылка = первый('main a, a');

  // --- листалка, крошки, фильтры, рейтинги, даты ---
  const листалка = первый('.zpg, [class*="pagination"], nav[aria-label*="страниц"]');
  const крошки = первый('[class*="breadcrumb"], nav[aria-label*="лебн"], .zbc');
  const фильтры = [...document.querySelectorAll('.afilt, [class*="filter"] select, [class*="filter"] a')]
    .filter(видим).length;
  const рейтинги = [...document.querySelectorAll('[class*="rating"], [class*="score"], .zt__r')]
    .filter(видим).map((e) => (e.textContent || '').trim().slice(0, 24)).slice(0, 8);
  const даты = [...document.querySelectorAll('time, [class*="date"], [datetime]')]
    .filter(видим).map((e) => (e.getAttribute('datetime') || e.textContent || '').trim().slice(0, 32))
    .slice(0, 8);

  // --- плеер ---
  const плееры = [...document.querySelectorAll('section.zpl, [class*="player"]')].filter(видим);
  const рамки = [...document.querySelectorAll('.zpl__f, [class*="player"] iframe, [class*="frame"]')]
    .filter(видим).map((e) => { const r = e.getBoundingClientRect();
      return +(r.width / Math.max(r.height, 1)).toFixed(4); });
  const видео = [...document.querySelectorAll('video, iframe')].map((v) => ({
    tag: v.tagName, autoplay: v.getAttribute('autoplay'), poster: v.getAttribute('poster'),
    src: (v.getAttribute('src') || '').slice(0, 60)}));

  // --- подвал и мобильная навигация ---
  const подвал = первый('footer');
  const мобнав = первый('[class*="burger"], [class*="drawer"], [aria-label*="еню"], button[aria-expanded]');

  // --- качество: переполнение, обрезка, мелкие цели, фокус ---
  const обрезанные = [];
  for (const sel of ['h1', 'h2', 'button', 'a', '.zt__t', '.zpg a', '.ahub__s']) {
    for (const el of document.querySelectorAll(sel)) {
      if (!видим(el)) continue;
      const s = cs(el);
      if (el.scrollWidth - el.clientWidth > 1 &&
          (s.overflow === 'hidden' || s.textOverflow === 'ellipsis')) {
        обрезанные.push({sel, text: (el.textContent || '').trim().slice(0, 30)});
      }
    }
  }
  const мелкие = [...document.querySelectorAll('a, button, [role=button], input, select')]
    .filter(видим).map((el) => { const r = el.getBoundingClientRect();
      return {w: Math.round(r.width), h: Math.round(r.height),
              text: (el.textContent || '').trim().slice(0, 20)}; })
    .filter((b) => b.w < 44 || b.h < 44);
  const битые = [...document.querySelectorAll('img')]
    .filter((i) => i.complete && i.naturalWidth === 0 && !i.hidden).length;
  const без_размеров = [...document.querySelectorAll('img')]
    .filter((i) => !(i.getAttribute('width') && i.getAttribute('height'))
                   && !cs(i).aspectRatio.includes('/')).length;

  return {
    viewport_w: W, scroll_w: док.scrollWidth, overflow_px: Math.round(док.scrollWidth - W),
    body_h: Math.round(document.body.scrollHeight),
    title: document.title,
    canonical: (первый('link[rel=canonical]') || {}).href || null,
    robots: (первый('meta[name=robots]') || {}).content || null,
    description: (первый('meta[name=description]') || {}).content || null,
    h1_count: document.querySelectorAll('h1').length,
    h1_text: h1 ? (h1.textContent || '').trim().slice(0, 60) : null,
    header: шапка ? {...пр(шапка), position: cs(шапка).position,
                     bg: cs(шапка).backgroundColor, border_bottom: cs(шапка).borderBottomWidth,
                     shadow: cs(шапка).boxShadow.slice(0, 40)} : null,
    logo: логотип ? {...пр(логотип), text: (логотип.textContent || '').trim().slice(0, 24),
                     has_img: !!логотип.querySelector('img, svg')} : null,
    nav_items: пункты.length, nav: пункты.slice(0, 12),
    search: поиск ? {...пр(поиск), placeholder: поиск.getAttribute('placeholder'),
                     type: поиск.getAttribute('type')} : null,
    container: обёртка ? {width: число(кос.width), max_width: кос.maxWidth,
                          pad_left: число(кос.paddingLeft), pad_right: число(кос.paddingRight),
                          margin: кос.marginLeft} : null,
    cards_count: карточки.length, first_card: сетка, columns: колонки, gap: промежуток,
    card_style: пк ? {radius: пк.borderRadius, shadow: пк.boxShadow.slice(0, 40),
                      border: пк.borderWidth, bg: пк.backgroundColor} : null,
    posters: постеры,
    slider: сведения_слайдера,
    sections: секции,
    typography: {body_font: тело.fontFamily.slice(0, 40), body_size: тело.fontSize,
                 body_lh: тело.lineHeight, color: тело.color, bg: тело.backgroundColor,
                 h1_size: h1 ? cs(h1).fontSize : null, h1_weight: h1 ? cs(h1).fontWeight : null,
                 h2_size: h2 ? cs(h2).fontSize : null, h2_weight: h2 ? cs(h2).fontWeight : null,
                 link_color: ссылка ? cs(ссылка).color : null},
    pagination: листалка ? {...пр(листалка),
                            links: листалка.querySelectorAll('a').length} : null,
    breadcrumbs: крошки ? {...пр(крошки), items: крошки.querySelectorAll('a').length} : null,
    filters_count: фильтры,
    ratings_sample: рейтинги, dates_sample: даты,
    player_instances: плееры.length, player_ratios: рамки, media: видео,
    footer: подвал ? {...пр(подвал), links: подвал.querySelectorAll('a').length,
                      cols: подвал.querySelectorAll('[data-b14-cols] > *').length,
                      bg: cs(подвал).backgroundColor} : null,
    mobile_nav: мобнав ? {...пр(мобнав), expanded: мобнав.getAttribute('aria-expanded'),
                          label: мобнав.getAttribute('aria-label')} : null,
    clipped_required: обрезанные,
    small_touch_targets: мелкие.length, small_touch_sample: мелкие.slice(0, 5),
    broken_images: битые, images_without_size: без_размеров,
    reduced_motion_rules: [...document.styleSheets].reduce((n, ss) => {
      try { return n + [...ss.cssRules].filter((r) =>
        (r.conditionText || '').includes('prefers-reduced-motion')).length; }
      catch (e) { return n; }
    }, 0),
  };
}
"""


def main() -> int:
    р = argparse.ArgumentParser(description=__doc__)
    р.add_argument("--domain", required=True)
    р.add_argument("--label", required=True, help="before | after")
    р.add_argument("--out", required=True)
    р.add_argument("--shots-for-comparable-only", action="store_true", default=True)
    a = р.parse_args()
    вывод = Path(a.out)
    (вывод / "screenshots").mkdir(parents=True, exist_ok=True)

    from playwright.sync_api import sync_playwright

    итог = {"task": "ANIMEDIA-PARITY-PROBE", "tenant": "animedia",
            "domain": a.domain, "label": a.label,
            "measured_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "widths": list(ШИРИНЫ), "cells": []}
    with sync_playwright() as pw:
        b = pw.chromium.launch()
        try:
            for ширина in ШИРИНЫ:
                ctx = b.new_context(viewport={"width": ширина, "height": 900},
                                    device_scale_factor=1)
                стр = ctx.new_page()
                for имя, путь, ждём, сопоставим in МАРШРУТЫ:
                    ответ = стр.goto(f"https://{a.domain}{путь}", wait_until="load",
                                     timeout=60000)
                    стр.wait_for_timeout(250)
                    м = стр.evaluate(ОРАКУЛ)
                    з = ответ.headers if ответ else {}
                    м.update({"route": имя, "path": путь, "width": ширина,
                              "http": ответ.status if ответ else None,
                              "expected_http": ждём, "comparable_to_reference": сопоставим,
                              "served_build": з.get("x-site-factory-build-id"),
                              "served_artifact": з.get("x-site-factory-artifact-sha256"),
                              "x_robots": з.get("x-robots-tag")})
                    итог["cells"].append(м)
                    if сопоставим or ширина in (390, 1440):
                        стр.screenshot(path=str(вывод / "screenshots" /
                                                f"{a.label}-{имя}-{ширина}.png"),
                                       full_page=False)
                        стр.screenshot(path=str(вывод / "screenshots" /
                                                f"{a.label}-{имя}-{ширина}-full.png"),
                                       full_page=True)
                    print(f"  {ширина:>5} {имя:<16} http={м['http']} overflow={м['overflow_px']} "
                          f"cards={м['cards_count']} cols={м['columns']} "
                          f"cont={(м['container'] or {}).get('width')} "
                          f"hdr={(м['header'] or {}).get('h')}", flush=True)
                ctx.close()
        finally:
            b.close()
    (вывод / f"PROBE_{a.label}_{a.domain.replace('.', '_')}.json").write_text(
        json.dumps(итог, ensure_ascii=False, indent=1), encoding="utf-8")
    print("ячеек:", len(итог["cells"]), "->", вывод)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
