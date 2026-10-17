#!/usr/bin/env python3
"""Где ещё в сети блок подборок разъехался по весу селекторов. Только чтение.

Дефект: правило `.hub__c span` (класс+элемент) перебивает `.hub__g{display:grid}`,
и сетка превью превращается в столбец блоков во всю ширину карточки. Снаружи
это «изображения чрезмерно увеличены» и «подборки стоят в три карточки и одну
снизу».

Проверяется вычисленный стиль живой страницы, а не исходник: у каждой витрины
свой выпуск, и по шаблону фабрики об их состоянии судить нельзя.

    python3 automation/local/hub-layout-check.py
"""
from __future__ import annotations

import json
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from playwright.sync_api import sync_playwright

КОРЕНЬ = Path(__file__).resolve().parents[2]
РЕЕСТР = КОРЕНЬ / "config" / "site-cells.json"
БРАУЗЕР = ("/home/claude/.cache/ms-playwright/chromium-1234/"
           "chrome-linux64/chrome")

МЕРА = """() => {
    const г = document.querySelector('.hub__g');
    const к = document.querySelector('.hub');
    const карточки = [...document.querySelectorAll('.hub__c')];
    if (!к) return {нет_блока: true};
    const пр = document.querySelector('.hub__p img');
    return {
        колонок: (getComputedStyle(к).gridTemplateColumns || '').split(' ').length,
        сетка_превью: г ? getComputedStyle(г).display : null,
        превью: пр ? Math.round(пр.getBoundingClientRect().width) + 'x' +
                     Math.round(пр.getBoundingClientRect().height) : null,
        высоты: карточки.map(э => Math.round(э.getBoundingClientRect().height)),
    };
}"""


def домены() -> list[str]:
    j = json.loads(РЕЕСТР.read_text(encoding="utf-8"))
    ячейки = j.get("cells") or []
    записи = ячейки.values() if isinstance(ячейки, dict) else ячейки
    итог = []
    for з in записи:
        д = (з or {}).get("domain")
        if д and not д.endswith(".localhost"):
            итог.append(д)
    return sorted(set(итог))


def по_домену(браузер, домен: str) -> dict:
    стр = браузер.new_page(viewport={"width": 1366, "height": 900})
    try:
        стр.goto(f"https://{домен}/", wait_until="load", timeout=60000)
        стр.evaluate("() => document.querySelector('.hub')?.scrollIntoView()")
        стр.wait_for_timeout(1500)
        return {"домен": домен, **стр.evaluate(МЕРА)}
    except Exception as ош:  # noqa: BLE001
        return {"домен": домен, "ошибка": str(ош)[:60]}
    finally:
        стр.close()


def главная() -> int:
    плохо = 0
    with sync_playwright() as p:
        б = p.chromium.launch(executable_path=БРАУЗЕР)
        итоги = [по_домену(б, д) for д in домены()]
        б.close()
    for и in итоги:
        if "ошибка" in и:
            print(f"  {и['домен']:22} НЕ ИЗМЕРЕНО: {и['ошибка']}")
            continue
        if и.get("нет_блока"):
            print(f"  {и['домен']:22} блока подборок нет")
            continue
        сломан = и.get("сетка_превью") == "block"
        плохо += сломан
        print(f"{'✗' if сломан else ' '} {и['домен']:22} колонок "
              f"{и['колонок']}, сетка превью {и['сетка_превью']}, превью "
              f"{и['превью']}, высоты {и['высоты'][:4]}")
    print(f"\nвитрин с разъехавшимся блоком подборок: {плохо}")
    return 1 if плохо else 0


if __name__ == "__main__":
    sys.exit(главная())
