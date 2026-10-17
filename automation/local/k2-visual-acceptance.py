#!/usr/bin/env python3
"""Визуальная приёмка витрины на ОТРИСОВАННОЙ публичной странице.

Зачем. Зелёные проверки и код 200 на адрес картинки не говорят, что увидел
посетитель: дефект «буква поверх постера» давал 200 на всех адресах, а дефект
блока подборок — корректный CSS, который перебивался по весу селекторов.
Поэтому приёмка берёт вычисленные стили и реальные размеры из браузера.

Что измеряется на каждой ширине и в каждой теме:

  буквы поверх картинки   контейнеров, где картинка нарисована, а заглушка
                          всё ещё показывается (обязан быть ноль);
  блок подборок           число колонок, display сетки превью, размер превью
                          и высоты карточек (они обязаны совпадать);
  постеры                 сколько нарисовано и сколько осталось без адреса;
  страница                горизонтальное переполнение и высота.

Снимки сохраняются рядом: без них «проверено» остаётся словом.

    python3 automation/local/k2-visual-acceptance.py https://lordfilm.group/ after-release
"""
from __future__ import annotations

import json
import pathlib
import sys

from playwright.sync_api import sync_playwright

БРАУЗЕР = ("/home/claude/.cache/ms-playwright/chromium-1234/"
           "chrome-linux64/chrome")
ВЫХОД = pathlib.Path(__file__).resolve().parents[2] / "var" / "k2-data" / "shots"
ШИРИНЫ = [("desktop", 1366, 900), ("tablet", 800, 900), ("phone", 390, 844)]

МЕРА = """() => {
    const м = (э) => э ? {
        display: getComputedStyle(э).display,
        cols: getComputedStyle(э).gridTemplateColumns,
        w: Math.round(э.getBoundingClientRect().width),
        h: Math.round(э.getBoundingClientRect().height),
    } : null;
    // «Нарисована» — это complete И ненулевая natural-ширина. Одной
    // natural-ширины мало: у картинки, которая ещё ГРУЗИТСЯ, размеры уже
    // известны из заголовка файла, а изображения на экране ещё нет. Первая
    // редакция считала такую картинку нарисованной и объявляла дефектом
    // заглушку под ней — измерено 2026-10-17 на «Восточном человеке»
    // (complete=false, naturalWidth=500): заглушка там стояла правильно.
    const нарисована = (i) => i && i.complete && i.naturalWidth > 0;
    const боксы = [...document.querySelectorAll('.zt__p,.c__p,.hub__p')];
    const буквы = боксы.filter(b => {
        const i = b.querySelector('img[data-poster]');
        const z = b.querySelector('[class*="__none"],[class*="__ph"]');
        return нарисована(i) && z && getComputedStyle(z).display !== 'none';
    });
    const пост = [...document.querySelectorAll('img[data-poster]')];
    const карточки = [...document.querySelectorAll('.hub__c')];
    const без_адреса = [...document.querySelectorAll('a[href^="/title/"]')]
        .filter(a => !a.querySelector('img'));
    return {
        букв_поверх: буквы.length,
        примеры_букв: буквы.slice(0, 3).map(b => (b.closest('a') || {}).title || ''),
        постеров: пост.length,
        нарисовано: пост.filter(нарисована).length,
        карточек_без_адреса: без_адреса.length,
        hub: м(document.querySelector('.hub')),
        hub__g: м(document.querySelector('.hub__g')),
        hub__p: м(document.querySelector('.hub__p')),
        высоты_подборок: карточки.map(э => Math.round(э.getBoundingClientRect().height)),
        переполнение: document.documentElement.scrollWidth > window.innerWidth,
        высота: document.body.scrollHeight,
    };
}"""

ПРОКРУТКА = """() => new Promise(r => {
    let y = 0;
    const шаг = () => {
        window.scrollBy(0, window.innerHeight); y += window.innerHeight;
        if (y < document.body.scrollHeight + window.innerHeight) setTimeout(шаг, 220);
        else { window.scrollTo(0, 0); setTimeout(r, 1200); }
    };
    шаг();
})"""


def главная(аргв: list[str]) -> int:
    адрес = аргв[0] if аргв else "https://lordfilm.group/"
    метка = аргв[1] if len(аргв) > 1 else "acceptance"
    ВЫХОД.mkdir(parents=True, exist_ok=True)
    итог: dict = {}
    плохо = 0
    with sync_playwright() as p:
        б = p.chromium.launch(executable_path=БРАУЗЕР)
        for тема in ("dark", "light"):
            for имя, ш, в in ШИРИНЫ:
                стр = б.new_page(viewport={"width": ш, "height": в},
                                 color_scheme=тема)
                try:
                    стр.goto(адрес, wait_until="load", timeout=90000)
                    стр.evaluate(ПРОКРУТКА)
                    стр.wait_for_timeout(2500)
                    з = стр.evaluate(МЕРА)
                    ключ = f"{тема}/{имя}"
                    итог[ключ] = з
                    плохо += bool(з["букв_поверх"]) + bool(з["переполнение"])
                    print(f"{ключ}: буквы поверх {з['букв_поверх']}, "
                          f"постеров {з['нарисовано']}/{з['постеров']}, "
                          f"без адреса {з['карточек_без_адреса']}, "
                          f"подборки {з['hub']['cols'] if з['hub'] else '—'}, "
                          f"превью {з['hub__p']['w'] if з['hub__p'] else '—'}×"
                          f"{з['hub__p']['h'] if з['hub__p'] else '—'}, "
                          f"высоты {з['высоты_подборок']}, "
                          f"переполнение {з['переполнение']}")
                    стр.screenshot(path=str(ВЫХОД / f"{метка}-{тема}-{имя}.png"),
                                   full_page=True)
                except Exception as ош:  # noqa: BLE001
                    print(f"[x] {тема}/{имя}: {ош}")
                    плохо += 1
                finally:
                    стр.close()
        б.close()
    (ВЫХОД / f"{метка}-мера.json").write_text(
        json.dumps(итог, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"\nотказов приёмки: {плохо}; снимки и мера: {ВЫХОД}")
    return 1 if плохо else 0


if __name__ == "__main__":
    sys.exit(главная(sys.argv[1:]))
