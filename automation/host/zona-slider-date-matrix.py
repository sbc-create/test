#!/usr/bin/env python3
"""Zona: браузерное измерение слайдера и даты поступления на 390/768/1440.

Зачем. Обе починки — геометрические: высота ряда слайдера, кадрирование постера
и полная дата в ленте «Недавно добавленные». Ни одну из них нельзя доказать
чтением CSS: `max-height` обрезает ряд, который уже растянулся под пропорцию
постера, а обрезку даты многоточием видно только по фактической ширине узла.
Поэтому здесь поднимается настоящий сервер шаблона на настоящем снимке Zona и
метрики снимаются из живого DOM в Chromium.

Запуск:

    .venv/bin/python automation/host/zona-slider-date-matrix.py --out <каталог>
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import socket
import subprocess
import sys
import time
from pathlib import Path

КОРЕНЬ = Path(__file__).resolve().parents[2]
СНИМОК = Path("/srv/lords/.frontend/zona-01-catalog.json")
ПОДРОБНОСТИ = Path("/srv/lords/.frontend/zona-01-details.json")
НЕДЕЛЯ = Path("/srv/lords/.frontend/zona-01-popular-weekly.json")

#: Ширины из задания владельца.
ШИРИНЫ = (390, 768, 1440)
МАРШРУТЫ = (("home", "/"), ("catalog", "/catalog/"), ("new", "/new/"))

ОРАКУЛ_JS = r"""
() => {
  const вид = {w: window.innerWidth, h: window.innerHeight};
  const док = document.documentElement;
  const видим = (el) => {
    const r = el.getBoundingClientRect();
    const s = getComputedStyle(el);
    return r.width > 0 && r.height > 0 && s.visibility !== 'hidden' && s.display !== 'none';
  };

  // 1. Слайдер: высота ряда и кадрирование постера.
  const героев = [];
  for (const el of document.querySelectorAll('.zhero')) {
    if (!видим(el)) continue;
    const r = el.getBoundingClientRect();
    const медиа = el.querySelector('.zhero__media');
    const тело = el.querySelector('.zhero__body');
    const img = el.querySelector('.zhero__media img');
    const s = img ? getComputedStyle(img) : null;
    героев.push({
      h: Math.round(r.height), w: Math.round(r.width),
      media_h: медиа ? Math.round(медиа.getBoundingClientRect().height) : null,
      body_h: тело ? Math.round(тело.getBoundingClientRect().height) : null,
      // Тело не должно выходить за ряд: именно так текст уезжал под обрез.
      body_overflows: тело ? (тело.getBoundingClientRect().bottom -
                              r.bottom > 1) : false,
      body_visible_text: тело ? (тело.textContent || '').trim().length : 0,
      object_position: s ? s.objectPosition : null,
      object_fit: s ? s.objectFit : null,
      img_natural: img ? [img.naturalWidth, img.naturalHeight] : null,
    });
  }

  // 2. Полка: остаток справа после деления контейнера на карточки.
  const полок = [];
  for (const track of document.querySelectorAll('.zrl__track')) {
    if (!видим(track)) continue;
    const дети = [...track.children].filter(видим);
    if (!дети.length) continue;
    const обёртка = track.closest('.zrl__vp') || track.parentElement;
    const шир_обёртки = обёртка
      ? Math.round(обёртка.getBoundingClientRect().width) : null;
    const первая = дети[0].getBoundingClientRect();
    const вторая = дети[1] ? дети[1].getBoundingClientRect() : null;
    const строка = дети.filter((d) =>
      Math.abs(d.getBoundingClientRect().top - первая.top) <= 4);
    const последняя = строка[строка.length - 1].getBoundingClientRect();
    полок.push({
      cards_in_row: строка.length,
      card_w: Math.round(первая.width),
      gap: вторая ? Math.round(вторая.left - первая.right) : null,
      wrapper_w: шир_обёртки,
      // Мёртвая полоса справа имеет смысл только когда ряд уместился в
      // обёртку. У прокручиваемой полки ряд шире обёртки намеренно, и
      // разность там — не «пустота», а длина прокрутки.
      row_w: Math.round(последняя.right - первая.left),
      fits: шир_обёртки !== null && (последняя.right - первая.left) <= шир_обёртки + 1,
      tail_px: (шир_обёртки !== null &&
                (последняя.right - первая.left) <= шир_обёртки + 1)
        ? Math.round(шир_обёртки - (последняя.right - первая.left)) : null,
      max_width_computed: getComputedStyle(дети[0]).maxWidth,
    });
  }

  // 3. Дата поступления: целиком или обрезана.
  const даты = [];
  for (const el of document.querySelectorAll('.zadded__when')) {
    if (!видим(el)) continue;
    const s = getComputedStyle(el);
    даты.push({
      text: (el.textContent || '').trim(),
      scrollW: el.scrollWidth, clientW: el.clientWidth,
      clipped: el.scrollWidth - el.clientWidth > 1,
      ellipsis: s.textOverflow === 'ellipsis',
      max_width: s.maxWidth,
      // Многоточие в тексте — прямой признак обрезки.
      has_ellipsis_char: (el.textContent || '').includes('…'),
    });
  }

  return {
    viewport: вид,
    overflow_px: Math.round(док.scrollWidth - вид.w),
    heroes: героев,
    shelves: полок,
    added_dates: даты,
    robots: (document.querySelector('meta[name=robots]') || {}).content || null,
  };
}
"""


def свободный_порт() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def поднять(порт: int, ман: Path, лог: Path) -> subprocess.Popen:
    окр = dict(os.environ)
    окр.update({
        "LORDS_TEMPLATE_MANIFEST": str(ман),
        "LORDS_CATALOG": str(СНИМОК),
        "LORDS_DETAILS": str(ПОДРОБНОСТИ),
        "LORDS_POPULAR_WEEKLY": str(НЕДЕЛЯ),
    })
    поток = лог.open("w", encoding="utf-8")
    proc = subprocess.Popen(
        [sys.executable, str(КОРЕНЬ / "automation/host/lords-frontend.py"),
         "--port", str(порт)],
        stdout=поток, stderr=subprocess.STDOUT, env=окр, cwd=str(КОРЕНЬ))
    # Снимок Zona — 16 МБ каталога и 78 МБ подробностей: индекс строится
    # минутами, и 150 с не хватало.
    for _ in range(4800):
        time.sleep(0.25)
        if proc.poll() is not None:
            raise SystemExit(f"сервер не поднялся, см. {лог}")
        try:
            with socket.create_connection(("127.0.0.1", порт), timeout=0.5):
                return proc
        except OSError:
            continue
    proc.terminate()
    raise SystemExit("сервер не ответил за 1200 с")


def main() -> int:
    р = argparse.ArgumentParser(description=__doc__)
    р.add_argument("--out", required=True)
    р.add_argument("--shots", action="store_true")
    args = р.parse_args()
    вывод = Path(args.out)
    (вывод / "raw").mkdir(parents=True, exist_ok=True)
    (вывод / "screenshots").mkdir(parents=True, exist_ok=True)

    артефакт = КОРЕНЬ / "automation/host/lords-frontend.py"
    цифра = hashlib.sha256(артефакт.read_bytes()).hexdigest()
    коммит = subprocess.run(["git", "rev-parse", "HEAD"], cwd=str(КОРЕНЬ),
                            capture_output=True, text=True).stdout.strip()
    грязно = bool(subprocess.run(
        ["git", "status", "--porcelain=v1", "--", "automation/host/lords-frontend.py"],
        cwd=str(КОРЕНЬ), capture_output=True, text=True).stdout.strip())

    ман = вывод / "raw" / "local-manifest.json"
    ман.write_text(json.dumps({
        "schema_version": 1, "template_family": "zona", "design_version": "1.2.0",
        "source_commit": коммит, "runtime_commit": коммит,
        "build_id": "local-zona-slider-date", "artifact_sha256": "0" * 64,
        "profile": "zona-general",
        "built_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }, ensure_ascii=False, indent=1), encoding="utf-8")

    порт = свободный_порт()
    proc = поднять(порт, ман, вывод / "raw" / "local-server.log")
    from playwright.sync_api import sync_playwright

    итог = {
        "task": "ZONA-SLIDER-CROP-DATE",
        "measured_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "browser": "chromium",
        "source_commit": коммит,
        "measured_artifact_sha256": цифра,
        "artifact_uncommitted_at_measurement": грязно,
        "snapshot": {"catalog": str(СНИМОК), "details": str(ПОДРОБНОСТИ)},
        "viewports": list(ШИРИНЫ),
        "cells": [],
    }
    with sync_playwright() as pw:
        браузер = pw.chromium.launch()
        try:
            for ширина in ШИРИНЫ:
                ctx = браузер.new_context(viewport={"width": ширина, "height": 900})
                стр = ctx.new_page()
                for имя, путь in МАРШРУТЫ:
                    ответ = стр.goto(f"http://127.0.0.1:{порт}{путь}",
                                     wait_until="load", timeout=60000)
                    стр.wait_for_timeout(250)
                    м = стр.evaluate(ОРАКУЛ_JS)
                    м.update({"route": имя, "width": ширина,
                              "http": ответ.status if ответ else None})
                    итог["cells"].append(м)
                    if args.shots:
                        стр.screenshot(path=str(вывод / "screenshots" /
                                                f"{имя}-{ширина}.png"), full_page=False)
                    героев = м["heroes"][0] if м["heroes"] else {}
                    даты = м["added_dates"]
                    print(f"  {ширина:>5} {имя:<9} http={м['http']} "
                          f"overflow={м['overflow_px']} hero_h={героев.get('h')} "
                          f"body_over={героев.get('body_overflows')} "
                          f"dates={len(даты)} clipped={sum(1 for d in даты if d['clipped'])} "
                          f"tail={[s['tail_px'] for s in м['shelves'][:2]]}", flush=True)
                ctx.close()
        finally:
            браузер.close()
    proc.terminate()
    proc.wait(timeout=20)
    (вывод / "SLIDER_DATE_MATRIX.json").write_text(
        json.dumps(итог, ensure_ascii=False, indent=1), encoding="utf-8")
    print("матрица:", вывод / "SLIDER_DATE_MATRIX.json", "ячеек", len(итог["cells"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
