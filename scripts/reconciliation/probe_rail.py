#!/usr/bin/env python3
"""Измеряет ленту-слайдер на живой витрине: геометрию, кнопки и шаг прокрутки.

Дефект слайдера надо сначала увидеть числами, иначе правка будет угадыванием.
Скрипт снимает на каждой ширине: сколько карточек помещается, остаётся ли
пустая полоса справа, попадает ли кнопка на карточку, что делает нажатие и
останавливается ли прокрутка на границе карточки.

Запуск: python3 scripts/reconciliation/probe_rail.py [базовый_адрес]
"""

from __future__ import annotations

import json
import sys

from playwright.sync_api import sync_playwright

БАЗА = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:9120"
ШИРИНЫ = (390, 768, 1440)

ЗАМЕР = """
() => {
  const out = [];
  document.querySelectorAll('.zrl').forEach((rl, i) => {
    const vp = rl.querySelector('.zrl__vp');
    const track = rl.querySelector('.zrl__track');
    if (!vp || !track) return;
    const cards = [...track.children];
    const vr = vp.getBoundingClientRect();
    const first = cards[0] ? cards[0].getBoundingClientRect() : null;
    const prev = rl.querySelector('[data-rl="prev"]');
    const next = rl.querySelector('[data-rl="next"]');
    const pr = prev ? prev.getBoundingClientRect() : null;
    const gap = parseFloat(getComputedStyle(track).gap) || 0;
    const step = first ? first.width + gap : 0;
    out.push({
      rail: i,
      viewportW: Math.round(vr.width),
      trackW: Math.round(track.scrollWidth),
      cards: cards.length,
      cardW: first ? Math.round(first.width) : null,
      gap: Math.round(gap),
      step: Math.round(step),
      // сколько карточек реально видно и сколько места остаётся пустым
      fits: step ? Math.floor((vr.width + gap) / step) : 0,
      tailPx: step ? Math.round(vr.width - (Math.floor((vr.width + gap) / step) * step - gap)) : null,
      scrollLeft: Math.round(vp.scrollLeft),
      maxScroll: Math.round(vp.scrollWidth - vp.clientWidth),
      prevDisabled: prev ? prev.hasAttribute('disabled') : null,
      nextDisabled: next ? next.hasAttribute('disabled') : null,
      // Скрытая кнопка сохраняет прямоугольник, поэтому одного пересечения
      // мало: карточку закрывает только та кнопка, которую видно.
      prevVisible: prev ? (getComputedStyle(prev).visibility !== 'hidden'
                           && parseFloat(getComputedStyle(prev).opacity) > 0.01) : null,
      prevOverlapsCard: (pr && first) ? (pr.right > first.left + 1) : null,
      prevCoversCard: (pr && first && prev)
        ? (pr.right > first.left + 1
           && getComputedStyle(prev).visibility !== 'hidden'
           && parseFloat(getComputedStyle(prev).opacity) > 0.01)
        : null,
      btnTopPct: pr && vr.height ? Math.round(((pr.top + pr.height / 2 - vr.top) / vr.height) * 100) : null,
      jsStep: Math.max(160, Math.round(vp.clientWidth * 0.86)),
    });
  });
  return out;
}
"""


def main() -> int:
    отчёт: dict[str, object] = {"база": БАЗА, "ширины": {}}
    with sync_playwright() as p:
        браузер = p.chromium.launch()
        try:
            for ширина in ШИРИНЫ:
                контекст = браузер.new_context(
                    viewport={"width": ширина, "height": 900},
                    device_scale_factor=1)
                страница = контекст.new_page()
                страница.goto(f"{БАЗА}/", wait_until="load", timeout=60000)
                страница.wait_for_timeout(400)
                до = страница.evaluate(ЗАМЕР)

                # Одно нажатие «вперёд» на первой ленте: куда встанет прокрутка.
                после = None
                if до:
                    кнопка = страница.query_selector('.zrl [data-rl="next"]')
                    if кнопка:
                        кнопка.click()
                        страница.wait_for_timeout(900)
                        после = страница.evaluate(ЗАМЕР)

                отчёт["ширины"][str(ширина)] = {
                    "до_нажатия": до,
                    "после_нажатия_вперёд": после[0] if после else None,
                }
                страница.close()
                контекст.close()
        finally:
            браузер.close()

    print(json.dumps(отчёт, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
