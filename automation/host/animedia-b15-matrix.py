#!/usr/bin/env python3
"""B15 — локальная матрица адаптива и доступности витрины Animedia.

Зачем отдельный стенд. До этого блока адаптив проверялся чтением CSS: «в стиле
есть `repeat(3,…)`, значит на 1024 три колонки». Это доказывает наличие
правила, а не раскладку — media-запрос может перекрываться другим, элемент
может переполнять контейнер при формально верной сетке, а обрезку текста строка
в CSS не показывает вовсе. Поэтому здесь поднимается настоящий сервер шаблона
на настоящем снимке каталога, страницы открываются в Chromium на шести
ширинах, и метрики снимаются из живого DOM.

Ничего не выдумывается: снимок берётся тот, что лежит на хосте, а манифест
собирается локально и помечен `local-b15`, чтобы его нельзя было спутать с
боевым артефактом.

Запуск:

    .venv/bin/python automation/host/animedia-b15-matrix.py \
        --out artifacts/evidence/animedia-blockwise-parity-03-2026-09-20/03-blocks/B15
"""
from __future__ import annotations

import argparse
import json
import os
import socket
import subprocess
import sys
import time
from pathlib import Path

КОРЕНЬ = Path(__file__).resolve().parents[2]
СНИМОК = Path("/srv/lords/.frontend/animedia-01-catalog.json")
ПОДРОБНОСТИ = Path("/srv/lords/.frontend/animedia-01-details.json")

#: Ширины из задания владельца. Высота берётся с запасом, чтобы страница
#: раскрывалась целиком и `scrollHeight` был настоящим.
ШИРИНЫ = (320, 390, 768, 1024, 1440, 1920)

#: Маршруты. Проблемные тайтл и серия — те, что назвал контракт стадии.
МАРШРУТЫ = (
    ("home", "/"),
    ("catalog", "/catalog/"),
    ("search", "/search/?q=%D0%B0%D0%BD%D0%B8%D0%BC%D0%B5"),
    ("collections", "/collections/"),
    ("collection_detail", "/collection/recently_added/"),
    ("title", "/title/nelyud-film-2-stolknovenie/"),
    ("episode", "/title/master-lda-i-plameni-2/season-2/episode-104/"),
    ("not_found", "/definitely-absent-route-xyz/"),
)

#: Порог «необъяснимой дыры» из контракта стадии.
ЗАЗОР_МАКС = 96
#: Допуск на горизонтальное переполнение — ноль по контракту, но субпиксельная
#: раскладка даёт дробный остаток, поэтому сравнение идёт по целому пикселю.
ПЕРЕПОЛНЕНИЕ_ДОПУСК = 1

ОРАКУЛ_JS = r"""
() => {
  const вид = {w: window.innerWidth, h: window.innerHeight};
  const док = document.documentElement;
  const видим = (el) => {
    const r = el.getBoundingClientRect();
    const s = getComputedStyle(el);
    return r.width > 0 && r.height > 0 && s.visibility !== 'hidden' &&
           s.display !== 'none' && s.opacity !== '0';
  };
  const прям = (el) => {
    const r = el.getBoundingClientRect();
    return {x: Math.round(r.x), y: Math.round(r.y),
            w: Math.round(r.width), h: Math.round(r.height)};
  };

  // 1. Горизонтальное переполнение документа и самые широкие виновники.
  const переполнение = Math.round(док.scrollWidth - вид.w);
  const широкие = [];
  for (const el of document.querySelectorAll('body *')) {
    if (!видим(el)) continue;
    const r = el.getBoundingClientRect();
    if (Math.round(r.right) > вид.w + 1 || Math.round(r.left) < -1) {
      широкие.push({sel: el.tagName.toLowerCase() + '.' + (el.className || '').toString().split(' ')[0],
                    right: Math.round(r.right), left: Math.round(r.left)});
      if (широкие.length >= 8) break;
    }
  }

  // 2. Обрезка обязательного текста. Обязательное — H1, даты и время,
  //    подписи сезона/серии/озвучки, кнопки, значения фильтров.
  //    Заголовок карточки (`.zt__t`) сюда не входит: у него объявленный clamp,
  //    а полное имя доступно в ссылке. Его переполнение считается отдельно —
  //    как нит вёрстки, а не как обрезка обязательного текста.
  const обязательные = [
    'h1', '[data-b13-count]', '.zft__col b', 'button', '.ahub__s',
    '.zpg a', '.zpg span', '.aeps__title', '.aeps__meta',
    '.zhub__t', '.zhub__m', '.asearch__form button', '.zhd__n a',
  ];
  const обрезанные = [];
  for (const sel of обязательные) {
    for (const el of document.querySelectorAll(sel)) {
      if (!видим(el)) continue;
      const s = getComputedStyle(el);
      const клип = el.scrollWidth - el.clientWidth > 1 &&
                   (s.overflow === 'hidden' || s.textOverflow === 'ellipsis' ||
                    s.overflowX === 'hidden');
      const обрез = s.textOverflow === 'ellipsis' && el.scrollWidth > el.clientWidth + 1;
      if (клип || обрез) {
        обрезанные.push({sel, text: (el.textContent || '').trim().slice(0, 48),
                         scrollW: el.scrollWidth, clientW: el.clientWidth});
        if (обрезанные.length >= 12) break;
      }
    }
  }

  // 3. Многоточие в дате или времени. Дата обязана читаться целиком.
  const времена = [];
  for (const el of document.querySelectorAll('time, .aeps__meta, [data-added-at], .zt__m')) {
    if (!видим(el)) continue;
    const t = (el.textContent || '');
    if (/\d/.test(t) && (t.includes('…') || t.includes('...'))) {
      времена.push(t.trim().slice(0, 60));
    }
  }

  // 4. Постеры: объявленная рамка 2:3 и целостность картинки.
  const постеры = [];
  let битые = 0;
  for (const el of document.querySelectorAll('.zt__p, .ztitle__poster, .aep-ctx__poster, .zhub__p')) {
    if (!видим(el)) continue;
    const r = el.getBoundingClientRect();
    if (r.width < 8 || r.height < 8) continue;
    постеры.push({ratio: +(r.width / r.height).toFixed(4),
                  w: Math.round(r.width), h: Math.round(r.height),
                  cls: (el.className || '').toString().split(' ')[0]});
  }
  for (const img of document.querySelectorAll('img')) {
    if (!img.complete) continue;
    if (img.naturalWidth === 0 && !img.hidden) битые++;
  }

  // 5. Пустые видимые блоки и необъяснимые дыры между секциями.
  const пустые = [];
  for (const el of document.querySelectorAll('section, .zsec, .ahero, .zhub, .zg, footer')) {
    if (!видим(el)) continue;
    const r = el.getBoundingClientRect();
    const текст = (el.textContent || '').trim();
    const есть_медиа = el.querySelector('img, video, iframe, svg');
    if (r.height > 24 && !текст && !есть_медиа) {
      пустые.push({cls: (el.className || '').toString().split(' ')[0], h: Math.round(r.height)});
    }
  }
  const секции = [...document.querySelectorAll('main > *, main .zwrap > *')]
      .filter(видим).map(прям).sort((a, b) => a.y - b.y);
  let макс_зазор = 0, зазоры = [];
  for (let i = 1; i < секции.length; i++) {
    const зазор = секции[i].y - (секции[i - 1].y + секции[i - 1].h);
    if (зазор > макс_зазор) макс_зазор = зазор;
    if (зазор > 96) зазоры.push(зазор);
  }

  // 6. Наложения соседних карточек в сетке.
  let наложений = 0;
  const сетки = document.querySelectorAll('.zg, .zhub');
  for (const сетка of сетки) {
    const дети = [...сетка.children].filter(видим).map(прям);
    for (let i = 0; i < дети.length; i++) {
      for (let j = i + 1; j < дети.length; j++) {
        const a = дети[i], b = дети[j];
        const пересек = a.x < b.x + b.w - 1 && b.x < a.x + a.w - 1 &&
                        a.y < b.y + b.h - 1 && b.y < a.y + a.h - 1;
        if (пересек) наложений++;
      }
    }
  }

  // 7. Колонки сетки и ширины карточек — считаются по раскладке, не по CSS.
  const раскладка = [];
  for (const сетка of сетки) {
    const дети = [...сетка.children].filter(видим).map(прям);
    if (!дети.length) continue;
    const первыйY = дети[0].y;
    const колонок = дети.filter((d) => Math.abs(d.y - первыйY) <= 4).length;
    раскладка.push({cls: (сетка.className || '').toString().split(' ')[0],
                    // Полный список классов: `zhub` и `zhub--home` — разные
                    // сетки с разными контрактами, и по первому классу их не
                    // отличить.
                    classes: (сетка.className || '').toString().trim(),
                    scope: сетка.closest('.zwrap--catalog') ? 'catalog' :
                           (сетка.closest('.zsec--home-cols') ? 'home-cols' : 'generic'),
                    cols: колонок, count: дети.length,
                    cardW: дети[0].w, cardH: дети[0].h,
                    lastRow: дети.filter((d) => Math.abs(d.y - дети[дети.length - 1].y) <= 4).length});
  }

  // 8. Плеер: один экземпляр, 16:9, без автозапуска.
  //    Экземпляр считается по самой секции плеера. Объединение селекторов
  //    давало двойку на одном плеере: вложенный `video-player` — часть той же
  //    секции, а не второй плеер.
  const плееры = [...document.querySelectorAll('section.zpl')].filter(видим);
  const рамки = [...document.querySelectorAll('.zpl__f')].filter(видим).map((el) => {
    const r = el.getBoundingClientRect();
    return {ratio: +(r.width / r.height).toFixed(4), w: Math.round(r.width), h: Math.round(r.height)};
  });
  // `autoplay="0"` — это объявленное «выключено». Наличие атрибута само по
  // себе автозапуском не является, поэтому смотрится значение.
  const выкл = new Set(['0', 'false', 'off', 'no', '']);
  const автозапуск = [...document.querySelectorAll('video, iframe, video-player, [autoplay]')]
      .filter((el) => {
        if (!el.hasAttribute('autoplay')) return false;
        return !выкл.has((el.getAttribute('autoplay') || '').trim().toLowerCase());
      }).length;
  const автозапуск_объявлен_выкл = [...document.querySelectorAll('[autoplay]')]
      .filter((el) => выкл.has((el.getAttribute('autoplay') || '').trim().toLowerCase())).length;

  // 8b. Переполнение заголовка карточки — отдельный, более мягкий счётчик.
  const карточные_заголовки = [];
  for (const el of document.querySelectorAll('.zt__t')) {
    if (!видим(el)) continue;
    if (el.scrollWidth - el.clientWidth > 1) {
      карточные_заголовки.push({text: (el.textContent || '').trim().slice(0, 40),
                                scrollW: el.scrollWidth, clientW: el.clientWidth});
      if (карточные_заголовки.length >= 6) break;
    }
  }

  // 9. Навигация и подвал достижимы.
  const шапка = document.querySelector('header, .zhd');
  const подвал = document.querySelector('footer');
  const бургер = document.querySelector('[data-drawer-toggle]');
  const мелкие = [];
  for (const el of document.querySelectorAll('a, button, [role=button]')) {
    if (!видим(el)) continue;
    const r = el.getBoundingClientRect();
    if (r.width < 44 && r.height < 44) {
      мелкие.push({tag: el.tagName.toLowerCase(),
                   cls: (el.className || '').toString().split(' ')[0],
                   w: Math.round(r.width), h: Math.round(r.height)});
      if (мелкие.length >= 10) break;
    }
  }

  return {
    viewport: вид,
    doc: {scrollWidth: док.scrollWidth, scrollHeight: док.scrollHeight},
    overflow_px: переполнение,
    overflow_offenders: широкие,
    clipped_required: обрезанные,
    timestamp_ellipsis: времена,
    posters: постеры,
    broken_images: битые,
    empty_visible_blocks: пустые,
    max_section_gap: макс_зазор,
    gaps_over_96: зазоры,
    grid_overlaps: наложений,
    grids: раскладка,
    player_instances: плееры.length,
    player_frames: рамки,
    autoplay_attrs: автозапуск,
    autoplay_declared_off: автозапуск_объявлен_выкл,
    card_title_overflow: карточные_заголовки,
    header_present: !!шапка,
    header_h: шапка ? Math.round(шапка.getBoundingClientRect().height) : 0,
    footer_present: !!подвал,
    footer_h: подвал ? Math.round(подвал.getBoundingClientRect().height) : 0,
    drawer_toggle_present: !!бургер,
    small_touch_targets: мелкие,
    h1_count: document.querySelectorAll('h1').length,
    h1_text: (document.querySelector('h1') || {}).textContent
             ? document.querySelector('h1').textContent.trim().slice(0, 80) : null,
    robots: (document.querySelector('meta[name=robots]') || {}).content || null,
    canonical: (document.querySelector('link[rel=canonical]') || {}).href || null,
  };
}
"""


def свободный_порт() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def манифест(путь: Path, коммит: str) -> Path:
    путь.write_text(json.dumps({
        "schema_version": 1,
        "template_family": "animedia",
        "design_version": "1.2.4",
        "source_commit": коммит,
        "runtime_commit": коммит,
        # Явная метка: это локальный стенд, а не боевой артефакт.
        "build_id": "local-b15",
        "artifact_sha256": "0" * 64,
        "profile": "animedia-icu",
        "built_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }, ensure_ascii=False, indent=1), encoding="utf-8")
    return путь


def поднять(порт: int, ман: Path, лог: Path) -> subprocess.Popen:
    окр = dict(os.environ)
    окр.update({
        "LORDS_TEMPLATE_MANIFEST": str(ман),
        "LORDS_CATALOG": str(СНИМОК),
        "LORDS_DETAILS": str(ПОДРОБНОСТИ),
        "ANIMEDIA_HOST_PROFILE": "animedia-icu",
    })
    поток = лог.open("w", encoding="utf-8")
    proc = subprocess.Popen(
        [sys.executable, str(КОРЕНЬ / "automation/host/lords-frontend.py"),
         "--port", str(порт)],
        stdout=поток, stderr=subprocess.STDOUT, env=окр, cwd=str(КОРЕНЬ))
    for _ in range(600):
        time.sleep(0.25)
        if proc.poll() is not None:
            raise SystemExit(f"сервер не поднялся, см. {лог}")
        try:
            with socket.create_connection(("127.0.0.1", порт), timeout=0.5):
                return proc
        except OSError:
            continue
    proc.terminate()
    raise SystemExit("сервер не ответил за 150 с")


def main() -> int:
    р = argparse.ArgumentParser(description=__doc__)
    р.add_argument("--out", required=True)
    р.add_argument("--shots", action="store_true",
                   help="сохранять полные скриншоты каждой пары маршрут×ширина")
    args = р.parse_args()
    вывод = Path(args.out)
    (вывод / "screenshots").mkdir(parents=True, exist_ok=True)
    (вывод / "raw").mkdir(parents=True, exist_ok=True)

    коммит = subprocess.run(["git", "rev-parse", "HEAD"], cwd=str(КОРЕНЬ),
                            capture_output=True, text=True).stdout.strip()
    ман = манифест(вывод / "raw" / "local-manifest.json", коммит)
    порт = свободный_порт()
    лог = вывод / "raw" / "local-server.log"
    proc = поднять(порт, ман, лог)
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        proc.terminate()
        raise SystemExit("playwright не установлен в .venv")

    итог: dict = {
        "stage": "ANIMEDIA-BLOCKWISE-PARITY-03",
        "block": "B15",
        "source_commit": коммит,
        "snapshot": {"catalog": str(СНИМОК), "details": str(ПОДРОБНОСТИ)},
        "measured_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "browser": "chromium",
        "viewports": list(ШИРИНЫ),
        "routes": [и for и, _ in МАРШРУТЫ],
        "cells": [],
    }
    with sync_playwright() as pw:
        браузер = pw.chromium.launch()
        try:
            for ширина in ШИРИНЫ:
                ctx = браузер.new_context(viewport={"width": ширина, "height": 900},
                                          device_scale_factor=1)
                стр = ctx.new_page()
                for имя, путь in МАРШРУТЫ:
                    url = f"http://127.0.0.1:{порт}{путь}"
                    ответ = стр.goto(url, wait_until="load", timeout=60000)
                    стр.wait_for_timeout(250)
                    метрики = стр.evaluate(ОРАКУЛ_JS)
                    метрики.update({"route": имя, "path": путь, "width": ширина,
                                    "http": ответ.status if ответ else None})
                    итог["cells"].append(метрики)
                    if args.shots:
                        стр.screenshot(
                            path=str(вывод / "screenshots" / f"{имя}-{ширина}.png"),
                            full_page=True)
                    print(f"  {ширина:>4} {имя:<18} http={метрики['http']} "
                          f"overflow={метрики['overflow_px']} "
                          f"clip={len(метрики['clipped_required'])} "
                          f"gap={метрики['max_section_gap']}", flush=True)
                ctx.close()
        finally:
            браузер.close()
    proc.terminate()
    proc.wait(timeout=20)

    (вывод / "RESPONSIVE_MATRIX.json").write_text(
        json.dumps(итог, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"матрица: {вывод / 'RESPONSIVE_MATRIX.json'} ячеек {len(итог['cells'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
