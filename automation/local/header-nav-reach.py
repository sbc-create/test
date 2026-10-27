#!/usr/bin/env python3
"""До каждого пункта меню шапки можно добраться — на любой ширине.

ПОВОД. Приёмка 27.10 сообщила об обрезанной строке меню на `zonafilm12.site`.
Замер оказался жёстче: на 768 меню требует 688 px при 409 доступных, пункты
«Подборки» и «Каталог» уходят за край шапки, и кнопки, которой список
открывается, в этой полосе нет.

ПОЧЕМУ ОТДЕЛЬНЫЙ ИНСТРУМЕНТ, А НЕ ПЕРЕНОС `checks/header_fit.py`. Та проверка
закрепляет РАЗМЕТКУ одной витрины: ящик на `position:absolute` с `top:100%` и
буквальную строку медиазапроса. Витрина, добившаяся того же другим способом,
получает от неё шесть «дефектов», ни один из которых не виден посетителю.
Поставить её на такую витрину значило бы завести вечно красную проверку, а
такие перестают читать.

Здесь проверяется ЦЕЛЬ, а не способ: на каждой ширине либо все пункты меню
лежат внутри шапки, либо видна кнопка, которой меню открывается. Как именно
витрина это делает — её дело.

ЧЕГО НЕ ДЕЛАЕТ. Не судит о красоте и не меряет отступы. Недостижимая витрина
даёт «НЕ ИЗМЕРЕНО» с причиной, а не «ок»: молчание здесь означало бы, что
проверять было нечего.

    python3 automation/local/header-nav-reach.py --url https://zonafilm12.site/
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys

КОРЕНЬ = pathlib.Path(__file__).resolve().parents[2]
if str(КОРЕНЬ) not in sys.path:
    sys.path.insert(0, str(КОРЕНЬ))

#: Ширины, на которых меню чаще всего не помещается: между телефоном, где
#: ящик обычно есть, и широким экраном, где строка влезает.
ШИРИНЫ = (390, 768, 1024, 1280, 1440, 1920)

ОСМОТР = """() => {
  const меню = document.querySelector('.zhd__n');
  const шапка = document.querySelector('.zhd__in') || document.querySelector('.zhd');
  if (!меню || !шапка) return {нашли: false};
  const видно = (e) => {
      if (!e) return false;
      const s = getComputedStyle(e);
      return s.display !== 'none' && s.visibility !== 'hidden'
             && e.getBoundingClientRect().width > 0;
  };
  const правый = Math.round(шапка.getBoundingClientRect().right);
  const пункты = [...меню.querySelectorAll('a')];
  const за_краем = пункты.filter(
      a => Math.round(a.getBoundingClientRect().right) > правый + 1
  ).map(a => (a.textContent || '').trim());
  const в_прокрутке = меню.scrollWidth > меню.clientWidth + 1;
  return {
    нашли: true,
    меню_видно: видно(меню),
    кнопка_видна: видно(document.querySelector('.zhd__menu')),
    пунктов: пункты.length,
    за_краем: за_краем,
    в_прокрутке: в_прокрутке,
    нужно: меню.scrollWidth, влезает: меню.clientWidth,
  };
}"""


def проверить(браузер, адрес: str, ширина: int) -> dict:
    к = браузер.new_context(viewport={"width": ширина, "height": 900})
    к.route("**mc.yandex.*/**", lambda м: м.abort())
    с = к.new_page()
    try:
        с.goto(адрес, wait_until="load", timeout=60000)
        с.wait_for_timeout(1200)
        д = с.evaluate(ОСМОТР)
    except Exception as сбой:  # noqa: BLE001
        return {"ширина": ширина, "исход": "НЕ ИЗМЕРЕНО",
                "причина": f"{type(сбой).__name__}: {str(сбой)[:120]}"}
    finally:
        к.close()
    if not д.get("нашли"):
        return {"ширина": ширина, "исход": "НЕ ИЗМЕРЕНО",
                "причина": "шапки с меню на странице нет"}
    # Цель: либо всё меню внутри шапки, либо есть кнопка, которой его открыть.
    недостижимо = bool(д["за_краем"]) or (д["меню_видно"] and д["в_прокрутке"])
    достижимо = (not недостижимо) or д["кнопка_видна"]
    д.update({"ширина": ширина,
              "исход": "ок" if достижимо else "дефект"})
    return д


def главная(аргв=None) -> int:
    р = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    р.add_argument("--url", required=True, action="append")
    р.add_argument("--json", action="store_true")
    р.add_argument("--widths", default="",
                   help="ширины через запятую вместо набора по умолчанию: "
                        "нужны, когда ищешь, где именно меню перестаёт "
                        "помещаться, а не проверяешь известные точки")
    а = р.parse_args(аргв)
    ширины = ШИРИНЫ
    if а.widths:
        ширины = tuple(int(ч.strip()) for ч in а.widths.split(",") if ч.strip())
        if not ширины:
            print("ОТКАЗ: --widths без ширин", file=sys.stderr)
            return 2
    from factory.seo.render_check import chromium_path
    from playwright.sync_api import sync_playwright

    путь = chromium_path()
    пуск = {"headless": True}
    if путь:
        пуск["executable_path"] = путь
    итоги = []
    with sync_playwright() as pw:
        бр = pw.chromium.launch(**пуск)
        try:
            for адрес in а.url:
                for ш in ширины:
                    з = проверить(бр, адрес, ш)
                    з["url"] = адрес
                    итоги.append(з)
        finally:
            бр.close()
    if а.json:
        print(json.dumps(итоги, ensure_ascii=False, indent=1))
    else:
        for з in итоги:
            хвост = ""
            if з.get("за_краем"):
                хвост = f"  за краем: {з['за_краем']}"
            elif з.get("в_прокрутке"):
                хвост = f"  в прокрутке: нужно {з.get('нужно')} влезает {з.get('влезает')}"
            print(f"{з['исход']:12s} {з['url']:28s} {з['ширина']:5d}"
                  f"  кнопка меню: {'да' if з.get('кнопка_видна') else 'нет'}{хвост}"
                  + (f"  — {з.get('причина')}" if з.get("причина") else ""))
    дефектов = sum(1 for з in итоги if з["исход"] == "дефект")
    не_измерено = sum(1 for з in итоги if з["исход"] == "НЕ ИЗМЕРЕНО")
    print(f"\nитог: замеров {len(итоги)}, дефектов {дефектов}, "
          f"не измерено {не_измерено}")
    if не_измерено:
        return 2
    return 1 if дефектов else 0


if __name__ == "__main__":
    sys.exit(главная())
