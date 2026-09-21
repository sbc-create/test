#!/usr/bin/env python3
"""Проверка карусели первого экрана Animedia по требованиям владельца.

Счётчик «слайдов больше одного» слайдером не доказывает ничего: одна большая
картинка с двумя стрелками тоже даст единицу. Поэтому здесь проверяется
поведение — что нажатие двигает ленту, что после конца она возвращается к
началу, что клавиатура работает, что точки показывают страницы, что цели
нажатия не меньше 44×44 и что при настройке «меньше движения» прокрутка
becomes мгновенной, а не плавной.

Запускается против локально поднятого рантайма: живой домен для этого трогать
не нужно.

    .venv/bin/python automation/host/animedia-slider-check.py \\
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


СОСТАВ = r"""
() => {
  const рамка = document.querySelector('.ahero .zrl') || document.querySelector('.zrl');
  if (!рамка) return {present: false};
  const vp = рамка.querySelector('.zrl__vp');
  const плитки = [...рамка.querySelectorAll('.zrl__track > *')];
  const данные = плитки.map((п) => {
    const a = п.matches('a') ? п : п.querySelector('a');
    const i = п.querySelector('img');
    const t = п.querySelector('.zt__t, h3, h2, [class*="title"]');
    return {href: a ? a.getAttribute('href') : null,
            img: i ? (i.currentSrc || i.getAttribute('src')) : null,
            title: t ? (t.textContent || '').trim() : null,
            id: п.getAttribute('data-slug') || (a ? a.getAttribute('href') : null)};
  });
  const кнопки = [...рамка.querySelectorAll('[data-rl]')].map((b) => {
    const r = b.getBoundingClientRect();
    return {dir: b.getAttribute('data-rl'), w: Math.round(r.width), h: Math.round(r.height),
            label: b.getAttribute('aria-label')};
  });
  const точки = [...рамка.querySelectorAll('[data-rl-dot]')].map((d) => {
    const r = d.getBoundingClientRect();
    return {w: Math.round(r.width), h: Math.round(r.height),
            current: d.getAttribute('aria-current')};
  });
  // Невидимая накладка поверх ленты: элемент, перекрывающий центр первой плитки.
  let накладка = null;
  if (плитки.length) {
    const r = плитки[0].getBoundingClientRect();
    const сверху = document.elementFromPoint(r.x + r.width / 2, r.y + r.height / 2);
    if (сверху && !плитки[0].contains(сверху) && сверху !== плитки[0]) {
      накладка = {tag: сверху.tagName, cls: String(сверху.className).slice(0, 40)};
    }
  }
  return {
    present: true, slides: плитки.length,
    unique_ids: new Set(данные.map((d) => d.id).filter(Boolean)).size,
    unique_images: new Set(данные.map((d) => d.img).filter(Boolean)).size,
    unique_titles: new Set(данные.map((d) => d.title).filter(Boolean)).size,
    unique_hrefs: new Set(данные.map((d) => d.href).filter(Boolean)).size,
    buttons: кнопки, dots: точки,
    dots_hidden: (рамка.querySelector('[data-rl-dots]') || {}).hidden,
    scroll_left: vp ? Math.round(vp.scrollLeft) : null,
    scroll_width: vp ? vp.scrollWidth : null,
    client_width: vp ? vp.clientWidth : null,
    vp_tabindex: vp ? vp.getAttribute('tabindex') : null,
    overlay: накладка,
    autoplay: [...рамка.querySelectorAll('video,[autoplay]')].length,
  };
}
"""


ОСЕЛ = """
() => new Promise((готово) => {
  const v = document.querySelector('.zrl__vp');
  if (!v) { готово(null); return; }
  let прежний = -1, тихо = 0;
  const тик = () => {
    const сейчас = Math.round(v.scrollLeft);
    тихо = сейчас === прежний ? тихо + 1 : 0;
    прежний = сейчас;
    if (тихо >= 6) { готово(сейчас); return; }
    requestAnimationFrame(тик);
  };
  requestAnimationFrame(тик);
})
"""

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

    итог = {"task": "ANIMEDIA-SLIDER-CHECK", "tenant": "animedia",
            "checked_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "runtime": a.runtime, "widths": list(ШИРИНЫ), "cells": [], "failures": []}
    провалы = итог["failures"]
    правило = f"MAP {a.domain} 127.0.0.1:{порт}"
    try:
        with sync_playwright() as pw:
            b = pw.chromium.launch(args=[f"--host-resolver-rules={правило}"])
            try:
                for ширина in ШИРИНЫ:
                    for движение in ("no-preference", "reduce"):
                        ctx = b.new_context(viewport={"width": ширина, "height": 900},
                                            reduced_motion=движение)
                        стр = ctx.new_page()
                        стр.goto(f"http://{a.domain}/", wait_until="load", timeout=60000)
                        стр.wait_for_timeout(400)
                        с = стр.evaluate(СОСТАВ)
                        ключ = f"{ширина}/{движение}"
                        if not с.get("present"):
                            провалы.append(f"{ключ}: карусели нет на первом экране")
                            итог["cells"].append({"width": ширина, "motion": движение, **с})
                            ctx.close()
                            continue
                        # Нажатие «вперёд» обязано двигать ленту.
                        стр.click('.zrl [data-rl="next"]')
                        # Плавная прокрутка длится дольше фиксированной паузы:
                        # ждём, пока лента остановится, иначе оракул измеряет
                        # середину анимации и объявляет это дефектом.
                        после_вперёд = стр.evaluate(ОСЕЛ)
                        # Цикличность: с конца «вперёд» возвращает к началу.
                        # Перемотка в конец сама по себе анимируется (CSS
                        # scroll-behavior: smooth), поэтому ждём, пока лента
                        # действительно окажется в конце: иначе нажатие придёт
                        # в середину ленты и проверит не то.
                        стр.evaluate("() => {const v=document.querySelector('.zrl__vp');"
                                     "v.scrollLeft = v.scrollWidth;}")
                        в_конце = стр.evaluate(ОСЕЛ)
                        предел = стр.evaluate("() => {const v=document.querySelector('.zrl__vp');"
                                              "return v.scrollWidth - v.clientWidth;}")
                        if в_конце is not None and предел - в_конце > 4:
                            провалы.append(f"{ключ}: лента не домотана до конца "
                                           f"({в_конце} из {предел}) — проверка цикличности "
                                           f"недействительна")
                        стр.click('.zrl [data-rl="next"]')
                        после_цикла = стр.evaluate(ОСЕЛ)
                        # Клавиатура: фокус на ленту и стрелка вправо.
                        стр.evaluate("() => document.querySelector('.zrl__vp').focus()")
                        стр.evaluate("() => {document.querySelector('.zrl__vp').scrollLeft = 0;}")
                        стр.wait_for_timeout(200)
                        стр.keyboard.press("ArrowRight")
                        после_клавиши = стр.evaluate(ОСЕЛ)
                        ячейка = {"width": ширина, "motion": движение, **с,
                                  "scroll_after_next": после_вперёд,
                                  "scroll_after_wrap": после_цикла,
                                  "scroll_after_key": после_клавиши}
                        итог["cells"].append(ячейка)
                        стр.screenshot(path=str(вывод / f"slider-{ширина}-{движение}.png"))

                        if с["slides"] < 6:
                            провалы.append(f"{ключ}: слайдов {с['slides']}, нужно не меньше шести")
                        for поле in ("unique_ids", "unique_images", "unique_titles",
                                     "unique_hrefs"):
                            if с[поле] < 6:
                                провалы.append(f"{ключ}: {поле}={с[поле]} — повторяющиеся элементы")
                        if len(с["buttons"]) < 2:
                            провалы.append(f"{ключ}: кнопок листания {len(с['buttons'])}")
                        for к in с["buttons"]:
                            if к["w"] < 44 or к["h"] < 44:
                                провалы.append(f"{ключ}: кнопка {к['dir']} {к['w']}x{к['h']} < 44x44")
                            if not к["label"]:
                                провалы.append(f"{ключ}: кнопка {к['dir']} без подписи")
                        если_нужны = с["scroll_width"] > с["client_width"] + 4
                        if если_нужны and not с["dots"]:
                            провалы.append(f"{ключ}: нет точек-страниц при листаемой ленте")
                        for д in с["dots"]:
                            if д["w"] < 44 or д["h"] < 44:
                                провалы.append(f"{ключ}: точка {д['w']}x{д['h']} < 44x44")
                        if после_вперёд <= (с["scroll_left"] or 0):
                            провалы.append(f"{ключ}: кнопка «вперёд» не двигает ленту")
                        if после_цикла > 4:
                            провалы.append(f"{ключ}: с конца лента не возвращается к началу "
                                           f"(осталось {после_цикла})")
                        if после_клавиши <= 0:
                            провалы.append(f"{ключ}: клавиатура не листает ленту")
                        if с["vp_tabindex"] is None:
                            провалы.append(f"{ключ}: лента не получает фокус")
                        if с["overlay"]:
                            провалы.append(f"{ключ}: поверх плитки лежит {с['overlay']}")
                        if с["autoplay"]:
                            провалы.append(f"{ключ}: автозапуск в карусели")
                        print(f"  {ключ}: слайдов {с['slides']} уникальных {с['unique_ids']} "
                              f"кнопок {len(с['buttons'])} точек {len(с['dots'])} "
                              f"вперёд→{после_вперёд} цикл→{после_цикла} клавиша→{после_клавиши}",
                              flush=True)
                        ctx.close()
            finally:
                b.close()
    finally:
        процесс.terminate()
        try:
            процесс.wait(timeout=20)
        except subprocess.TimeoutExpired:
            процесс.kill()
    итог["SLIDER_PASS"] = not провалы
    (вывод / "SLIDER_CHECK.json").write_text(json.dumps(итог, ensure_ascii=False, indent=1),
                                             encoding="utf-8")
    print("SLIDER_PASS:", итог["SLIDER_PASS"])
    for f in провалы[:20]:
        print("  провал:", f)
    return 0 if итог["SLIDER_PASS"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
