#!/usr/bin/env python3
"""Есть ли горизонтальная прокрутка на телефоне и компьютере. Прямой замер.

Измерено 20.10 этим инструментом:

    zonafilm.space   phone  окно 390  scrollWidth документа 390  body 2863 — переполнения нет
    zonafilm.space   desktop окно 1440 scrollWidth документа 1440 body 2639 — переполнения нет
    zonafilm12.site  phone  окно 390  scrollWidth документа 390  body 2431 — переполнения нет
    zonafilm12.site  desktop окно 1440 scrollWidth документа 1440 body 3015 — переполнения нет

ЧТО ЭТИМ ЗАКРЫТО, И ЭТО ВАЖНЕЕ САМОГО ЧИСЛА. Полноэкранный снимок главной
выходит шириной 2 863 px при окне 390 px, и из этого легко заключить
переполнение — я и был близок к такому выводу. Вывод был бы ЛОЖНЫМ: `full_page`
снимает по `body.scrollWidth`, а горизонтальная прокрутка страницы возникает по
`documentElement.scrollWidth`. Ширина снимка здесь — это ширина дорожек полок
внутри контейнера с `overflow-x`, то есть устройство карусели, а не дефект.
Поэтому ширину снимка читать как переполнение нельзя, и инструмент печатает
обе величины рядом, чтобы вывод не делался по одной.

Мера та же, что в `automation/local/k2-visual-acceptance.py`:
`document.documentElement.scrollWidth > window.innerWidth`. Рядом печатаются
обе величины и `body.scrollWidth`, чтобы вывод читался без доверия к одному
числу.
"""
import glob
import sys

ОКНА = {"phone": (390, 844), "desktop": (1440, 900)}
ЗАМЕР = """() => ({
    innerWidth: window.innerWidth,
    docScrollWidth: document.documentElement.scrollWidth,
    bodyScrollWidth: document.body.scrollWidth,
    docClientWidth: document.documentElement.clientWidth,
    scrollHeight: document.documentElement.scrollHeight,
    переполнение: document.documentElement.scrollWidth > window.innerWidth,
})"""

адреса = sys.argv[1:] or ["https://zonafilm.space/"]
хром = sorted(glob.glob(
    "/home/claude/.cache/ms-playwright/chromium*/chrome-linux*/chrome"))
if not хром:
    print("НЕ ИЗМЕРЕНО: Chromium playwright не найден")
    raise SystemExit(2)

from playwright.sync_api import sync_playwright  # noqa: E402

with sync_playwright() as p:
    браузер = p.chromium.launch(executable_path=хром[-1],
                                args=["--no-sandbox", "--disable-dev-shm-usage"])
    try:
        for адрес in адреса:
            print(f"\n{адрес}")
            for имя, (ш, в) in ОКНА.items():
                страница = браузер.new_page(viewport={"width": ш, "height": в})
                try:
                    страница.goto(адрес, wait_until="load", timeout=45000)
                    з = страница.evaluate(ЗАМЕР)
                    print(f"   {имя:8} окно {з['innerWidth']:5}  "
                          f"scrollWidth документа {з['docScrollWidth']:5}  "
                          f"body {з['bodyScrollWidth']:5}  "
                          f"высота {з['scrollHeight']:5}  "
                          f"переполнение: {'ДА' if з['переполнение'] else 'нет'}")
                except Exception as ош:  # noqa: BLE001
                    print(f"   {имя:8} НЕ ИЗМЕРЕНО: {type(ош).__name__}")
                finally:
                    страница.close()
    finally:
        браузер.close()
