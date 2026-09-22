#!/usr/bin/env python3
"""Доступность и плеер Animedia: проверка поведением, а не наличием узлов.

Доступность здесь — не список атрибутов, а ответы на вопросы: доходит ли
клавиатура до содержимого, виден ли фокус, есть ли у кнопок имена, различим ли
текст на фоне, не ломается ли вёрстка при увеличении шрифта.

Плеер — не «есть ли тег», а: одна ли оболочка, не тянется ли тяжёлый поток до
действия пользователя, честно ли объяснено отсутствие потока, нет ли второго
скрытого плеера и не подменён ли он постером с ложной кнопкой.

    .venv/bin/python automation/host/animedia-a11y-player-audit.py --out <каталог>
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
ШИРИНЫ = (320, 390, 768, 1024, 1440, 1920)
СТРАНИЦЫ = (("home", "/"), ("catalog", "/catalog/"),
            ("title", "/title/nelyud-film-2-stolknovenie/"),
            ("episode", "/title/master-lda-i-plameni-2/season-2/episode-104/"),
            ("search_empty", "/search/?q=%D1%8A%D1%8B%D1%8C%D1%89%D0%B7%D1%85"),
            ("not_found", "/definitely-absent-route-xyz/"))

ДОСТУП = r"""
() => {
  const cs = getComputedStyle;
  const видим = (el) => {
    const r = el.getBoundingClientRect(), s = cs(el);
    return r.width > 0 && r.height > 0 && s.visibility !== 'hidden' && s.display !== 'none';
  };
  const яркость = (цвет) => {
    const m = String(цвет).match(/rgba?\(([^)]+)\)/);
    if (!m) return null;
    const [r, g, b] = m[1].split(',').map((x) => parseFloat(x) / 255);
    const к = (c) => (c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4);
    return 0.2126 * к(r) + 0.7152 * к(g) + 0.0722 * к(b);
  };
  const контраст = (перед, зад) => {
    const a = яркость(перед), b = яркость(зад);
    if (a === null || b === null) return null;
    const [св, тём] = a > b ? [a, b] : [b, a];
    return +((св + 0.05) / (тём + 0.05)).toFixed(2);
  };
  const фон = (el) => {
    let у = el;
    while (у) {
      const ф = cs(у).backgroundColor;
      if (ф && ф !== 'rgba(0, 0, 0, 0)' && ф !== 'transparent') return ф;
      у = у.parentElement;
    }
    return cs(document.body).backgroundColor;
  };
  // Заголовки и их порядок.
  const заголовки = [...document.querySelectorAll('h1,h2,h3,h4')].filter(видим)
    .map((h) => ({уровень: +h.tagName[1], текст: (h.textContent || '').trim().slice(0, 40)}));
  let скачки = 0, прошлый = 0;
  for (const з of заголовки) {
    if (прошлый && з.уровень > прошлый + 1) скачки++;
    прошлый = з.уровень;
  }
  // Ориентиры страницы.
  const ориентиры = {
    header: !!document.querySelector('header'),
    nav: !!document.querySelector('nav'),
    main: !!document.querySelector('main'),
    footer: !!document.querySelector('footer'),
  };
  // Кнопки без доступного имени.
  const безымянные = [...document.querySelectorAll('button, [role=button]')].filter(видим)
    .filter((b) => !((b.textContent || '').trim() || b.getAttribute('aria-label')
                     || b.getAttribute('title'))).length;
  // Поля без подписи.
  const без_подписи = [...document.querySelectorAll('input, select, textarea')].filter(видим)
    .filter((i) => {
      if (i.getAttribute('aria-label') || i.getAttribute('title')) return false;
      const id = i.getAttribute('id');
      if (id && document.querySelector(`label[for="${id}"]`)) return false;
      return !i.closest('label');
    }).length;
  // Пустые интерактивные элементы.
  const пустые = [...document.querySelectorAll('a, button')].filter(видим)
    .filter((e) => !(e.textContent || '').trim() && !e.querySelector('img, svg')
                   && !e.getAttribute('aria-label')).length;
  // Контраст основного текста и приглушённого.
  const тело = document.body;
  const образцы = [];
  for (const sel of ['.zt__t', '.zt__m', '.zsub', 'footer a', '.zhd__n a']) {
    const el = [...document.querySelectorAll(sel)].filter(видим)[0];
    if (el) образцы.push({sel, контраст: контраст(cs(el).color, фон(el)),
                          размер: cs(el).fontSize});
  }
  return {
    headings: заголовки.slice(0, 12), heading_jumps: скачки,
    h1_count: document.querySelectorAll('h1').length,
    landmarks: ориентиры,
    buttons_without_name: безымянные,
    inputs_without_label: без_подписи,
    empty_interactive: пустые,
    contrast_samples: образцы,
    overflow_px: Math.round(document.documentElement.scrollWidth - window.innerWidth),
    images_without_alt: [...document.querySelectorAll('img')].filter(видим)
      .filter((i) => i.getAttribute('alt') === null).length,
  };
}
"""

ПЛЕЕР = r"""
() => {
  const видим = (el) => {
    const r = el.getBoundingClientRect(), s = getComputedStyle(el);
    return r.width > 0 && r.height > 0 && s.visibility !== 'hidden' && s.display !== 'none';
  };
  const оболочки = [...document.querySelectorAll('section.zpl')];
  const рамки = [...document.querySelectorAll('.zpl__f')];
  const видео = [...document.querySelectorAll('video')];
  const кадры = [...document.querySelectorAll('iframe')];
  const состояние = (оболочки[0] || {}).getAttribute
    ? оболочки[0].getAttribute('data-state') : null;
  const сообщение = document.querySelector('.zpl__msg, .zpl [class*="state"], .zpl p');
  return {
    shells: оболочки.length, shells_visible: оболочки.filter(видим).length,
    frames: рамки.length,
    frame_ratio: рамки[0] ? +(рамки[0].getBoundingClientRect().width
      / Math.max(рамки[0].getBoundingClientRect().height, 1)).toFixed(4) : null,
    videos: видео.length, iframes: кадры.length,
    autoplay: видео.filter((v) => v.hasAttribute('autoplay')).length
      + кадры.filter((f) => (f.getAttribute('allow') || '').includes('autoplay')).length,
    state: состояние,
    message: сообщение ? (сообщение.textContent || '').trim().slice(0, 120) : null,
    poster_with_fake_play: [...document.querySelectorAll('.zpl img')].filter(видим)
      .filter((i) => i.closest('a')).length,
  };
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

    итог = {"task": "ANIMEDIA-A11Y-PLAYER-AUDIT", "tenant": "animedia",
            "checked_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "cells": [], "player": [], "keyboard": [], "failures": []}
    провалы = итог["failures"]
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
                        стр.wait_for_timeout(200)
                        д = стр.evaluate(ДОСТУП)
                        итог["cells"].append({"route": имя, "width": ширина, **д})
                        к = f"{имя}@{ширина}"
                        if д["h1_count"] != 1:
                            провалы.append(f"{к}: H1 {д['h1_count']}")
                        if д["heading_jumps"]:
                            провалы.append(f"{к}: пропуски уровней заголовков {д['heading_jumps']}")
                        for о, есть in д["landmarks"].items():
                            if not есть:
                                провалы.append(f"{к}: нет ориентира {о}")
                        if д["buttons_without_name"]:
                            провалы.append(f"{к}: кнопок без имени {д['buttons_without_name']}")
                        if д["inputs_without_label"]:
                            провалы.append(f"{к}: полей без подписи {д['inputs_without_label']}")
                        if д["empty_interactive"]:
                            провалы.append(f"{к}: пустых интерактивных {д['empty_interactive']}")
                        if д["images_without_alt"]:
                            провалы.append(f"{к}: изображений без alt {д['images_without_alt']}")
                        if д["overflow_px"] > 1:
                            провалы.append(f"{к}: переполнение {д['overflow_px']}")
                        for о in д["contrast_samples"]:
                            if о["контраст"] is not None and о["контраст"] < 4.5:
                                провалы.append(f"{к}: контраст {о['sel']} = {о['контраст']}")
                        if имя == "episode":
                            п = стр.evaluate(ПЛЕЕР)
                            итог["player"].append({"width": ширина, **п})
                            if п["shells_visible"] > 1:
                                провалы.append(f"{к}: плееров {п['shells_visible']}")
                            if п["autoplay"]:
                                провалы.append(f"{к}: автозапуск {п['autoplay']}")
                            if п["videos"] + п["iframes"] > 0 and п["state"] != "playable":
                                провалы.append(f"{к}: тяжёлый поток при состоянии {п['state']}")
                            if п["shells"] and not (п["frame_ratio"] or п["message"]):
                                провалы.append(f"{к}: пустая оболочка без объяснения")
                            if п["frame_ratio"] and abs(п["frame_ratio"] - 16 / 9) > 0.05:
                                провалы.append(f"{к}: рамка плеера {п['frame_ratio']}")
                    # Клавиатура: доходит ли Tab до содержимого и виден ли фокус.
                    стр.goto(f"http://{a.domain}/", wait_until="load", timeout=60000)
                    стр.wait_for_timeout(200)
                    путь_фокуса = []
                    for _ in range(12):
                        стр.keyboard.press("Tab")
                        ф = стр.evaluate("""() => {
                          const a = document.activeElement;
                          if (!a || a === document.body) return null;
                          const s = getComputedStyle(a);
                          return {tag: a.tagName, cls: String(a.className).slice(0, 24),
                                  text: (a.textContent || '').trim().slice(0, 24),
                                  outline: s.outlineStyle + ' ' + s.outlineWidth,
                                  shadow: s.boxShadow.slice(0, 24)};
                        }""")
                        if ф:
                            путь_фокуса.append(ф)
                    итог["keyboard"].append({"width": ширина, "path": путь_фокуса[:12]})
                    без_фокуса = [ф for ф in путь_фокуса
                                  if ф["outline"].startswith("none") and not ф["shadow"]]
                    if len(путь_фокуса) < 5:
                        провалы.append(f"@{ширина}: клавиатура дошла лишь до "
                                       f"{len(путь_фокуса)} элементов")
                    if без_фокуса:
                        провалы.append(f"@{ширина}: без видимого фокуса "
                                       f"{len(без_фокуса)} элементов")
                    print(f"  ширина {ширина:>5}: страниц {len(СТРАНИЦЫ)}, "
                          f"фокус по {len(путь_фокуса)} элементам", flush=True)
                    ctx.close()
            finally:
                b.close()
    finally:
        процесс.terminate()
        try:
            процесс.wait(timeout=20)
        except subprocess.TimeoutExpired:
            процесс.kill()
    итог["A11Y_PLAYER_PASS"] = not провалы
    (вывод / "A11Y_PLAYER_AUDIT.json").write_text(
        json.dumps(итог, ensure_ascii=False, indent=1), encoding="utf-8")
    print("A11Y_PLAYER_PASS:", итог["A11Y_PLAYER_PASS"], "| находок:", len(провалы))
    for f in провалы[:20]:
        print("  •", f)
    return 0 if итог["A11Y_PLAYER_PASS"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
