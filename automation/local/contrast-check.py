#!/usr/bin/env python3
"""Контраст текста главной в ОБЕИХ темах — числом, а не на глаз.

Повод. На снимке главной в тёмной теме заголовок и абзац «О каталоге»
выглядят серыми на почти чёрном. Причина видна в разметке: цвета этих двух
блоков заданы прямо в атрибуте `style` (`color:#5b6470`, `color:#4d555e`), то
есть мимо палитры. В светлой теме это серый на белом и читается; в тёмной —
серый на чёрном, и это уже не оформление, а нечитаемый текст.

Здесь считается контраст по WCAG 2.1 (отношение яркостей) для каждой темы.
Порог для обычного текста — 4.5:1, для крупного (от 18.66px жирного или 24px)
— 3:1. Инструмент НИЧЕГО не чинит: он называет пару цветов и число.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

КОРЕНЬ = Path(__file__).resolve().parents[2]
КОРЕНЬ_ФАБРИКИ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(КОРЕНЬ_ФАБРИКИ))

from factory.seo.render_check import chromium_path  # noqa: E402

#: Путь к готовой сборке Chromium. Номер сборки здесь НЕ вписывается числом:
#: закреплённый номер однажды выключил браузерную приёмку целиком (на машине с
#: другой сборкой проверка сообщала «Chromium не найден»). Поиск общий —
#: `factory.seo.render_check.chromium_path`: явный `FACTORY_CHROMIUM`, затем
#: известные каталоги, затем шаблон от новой сборки к старой.
ГОТОВЫЙ_CHROMIUM = Path(chromium_path() or "")
#: Что меряем на каждой странице: адрес, селектор и человеческое имя.
#: Жёстко заданные цвета живут не только на главной, поэтому страниц две.
ЦЕЛИ = [("/", "h1.lead", "заголовок главной"),
        ("/", ".zsub", "подзаголовок направления"),
        ("/", "section.sec p", "абзац «О каталоге»"),
        ("/", ".hub__c b", "название подборки"),
        ("/", ".hub__c p", "описание подборки"),
        ("/catalog/", ".zsub", "подзаголовок каталога"),
        ("/title/preduprezhdenie/", ".crumbs", "хлебные крошки"),
        ("/title/preduprezhdenie/", ".plot p", "описание произведения"),
        ("/title/preduprezhdenie/", ".facts dd", "значение в таблице сведений"),
        ("/title/preduprezhdenie/", ".claim", "строка «Смотреть …»"),
        ("/", ".hd__nav a", "пункт меню в шапке"),
        ("/", ".ft__col a", "ссылка в подвале"),
        ("/", ".ft__about", "абзац о витрине в подвале"),
        ("/", ".ft__contact", "обратная связь в подвале"),
        ("/", ".tabs a", "таблетка жанра на главной"),
        ("/catalog/", ".filt__seg a", "кнопка фильтра в каталоге"),
        ("/catalog/", ".pg a, .pager a", "ссылка страницы"),
        ("/catalog/", "select", "поле фильтра"),
        ("/title/gryaznye-sekrety/", ".eps a", "номер серии"),
        ("/title/gryaznye-sekrety/", ".sea__h span", "подпись сезона")]


def яркость(цвет: tuple[float, float, float]) -> float:
    def канал(з: float) -> float:
        з = з / 255.0
        return з / 12.92 if з <= 0.04045 else ((з + 0.055) / 1.055) ** 2.4
    r, g, b = (канал(к) for к in цвет)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def разобрать(строка: str) -> tuple[float, float, float] | None:
    строка = (строка or "").strip()
    if not строка.startswith("rgb"):
        return None
    числа = строка[строка.index("(") + 1: строка.index(")")].replace("/", " ")
    части = [ч for ч in числа.replace(",", " ").split() if ч]
    try:
        return tuple(float(ч) for ч in части[:3])  # type: ignore[return-value]
    except ValueError:
        return None


def отношение(текст: str, фон: str) -> float | None:
    т, ф = разобрать(текст), разобрать(фон)
    if т is None or ф is None:
        return None
    a, b = яркость(т) + 0.05, яркость(ф) + 0.05
    return round(max(a, b) / min(a, b), 2)


def окружение(конфиг: dict, проект: Path, данные: Path) -> dict:
    env = dict(os.environ)
    for имя, шаблон in (конфиг.get("environment") or {}).items():
        env[имя] = (str(шаблон).replace("<data>", str(данные))
                    .replace("<app>", str(проект)))
    env["SITE_CONTACT_EMAIL"] = str(конфиг.get("contact_email") or "")
    env["LORDS_INDEXING_SITE"] = str(конфиг.get("domain") or "")
    env["LORDS_INDEXING_RELEASE_PERMITS_OPEN"] = "false"
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    return env


def main() -> int:
    р = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    р.add_argument("--site", required=True)
    р.add_argument("--data", required=True)
    р.add_argument("--port", type=int, default=19900)
    а = р.parse_args()

    проект = КОРЕНЬ / "var" / "new-sites" / а.site
    конфиг = json.loads((проект / "config" / "site.json").read_text(encoding="utf-8"))
    врем = Path(tempfile.mkdtemp(prefix=f"контраст-{а.site}-"))
    данные = врем / "data"
    данные.mkdir()
    for ф in Path(а.data).glob(f"{а.site}-*.json"):
        shutil.copy(ф, данные / ф.name)

    проц = subprocess.Popen(
        [sys.executable, str(проект / "src" / конфиг["entrypoint"]),
         "--port", str(а.port)], cwd=проект,
        env=окружение(конфиг, проект, данные),
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    for _ in range(120):
        try:
            urllib.request.urlopen(f"http://127.0.0.1:{а.port}/healthz", timeout=12)
            break
        except Exception:  # noqa: BLE001
            if проц.poll() is not None:
                print("ОТКАЗ: рантайм не поднялся", file=sys.stderr)
                return 1
            time.sleep(1)

    итог: dict = {"site": а.site, "domain": конфиг.get("domain"), "темы": {}}
    код = 0
    try:
        from playwright.sync_api import sync_playwright

        with sync_playwright() as pw:
            пуск = ({"executable_path": str(ГОТОВЫЙ_CHROMIUM)}
                    if ГОТОВЫЙ_CHROMIUM.is_file() else {})
            браузер = pw.chromium.launch(**пуск)
            for тема in ("light", "dark"):
                к = браузер.new_context(viewport={"width": 1366, "height": 768},
                                        color_scheme=тема)
                стр = к.new_page()
                замеры = {}
                текущий_адрес = None
                for адрес, селектор, имя in ЦЕЛИ:
                    if адрес != текущий_адрес:
                        стр.goto(f"http://127.0.0.1:{а.port}{адрес}",
                                 wait_until="domcontentloaded")
                        текущий_адрес = адрес
                    узел = стр.locator(селектор)
                    if узел.count() == 0:
                        замеры[имя] = {"найдено": False, "адрес": адрес}
                        continue
                    пара = стр.evaluate(
                        "(sel) => {const n=document.querySelector(sel);"
                        "const s=getComputedStyle(n);"
                        "let f=n, bg=getComputedStyle(f).backgroundColor;"
                        "while(f && (bg==='rgba(0, 0, 0, 0)'||bg==='transparent'))"
                        "{f=f.parentElement; if(!f) break; bg=getComputedStyle(f).backgroundColor;}"
                        "return {color:s.color, bg:bg, size:s.fontSize, weight:s.fontWeight};}",
                        селектор)
                    о = отношение(пара["color"], пара["bg"])
                    кегль = float(str(пара["size"]).replace("px", "") or 0)
                    крупный = кегль >= 24 or (кегль >= 18.66
                                              and str(пара["weight"]) in ("700", "bold", "800", "900"))
                    порог = 3.0 if крупный else 4.5
                    замеры[имя] = {"найдено": True, "адрес": адрес, "цвет": пара["color"],
                                   "фон": пара["bg"], "кегль": пара["size"],
                                   "отношение": о, "порог": порог,
                                   "проходит": (о is not None and о >= порог)}
                    if о is not None and о < порог:
                        код = 3
                итог["темы"][тема] = замеры
                к.close()
            браузер.close()
    except Exception as ош:  # noqa: BLE001
        итог["ошибка"] = f"{type(ош).__name__}: {ош}"
        код = код or 1
    finally:
        проц.terminate()
        try:
            проц.wait(timeout=15)
        except subprocess.TimeoutExpired:
            проц.kill()
        shutil.rmtree(врем, ignore_errors=True)

    выход = КОРЕНЬ / "var" / "k2-data" / "audit" / а.site
    выход.mkdir(parents=True, exist_ok=True)
    (выход / "contrast.json").write_text(
        json.dumps(итог, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8")
    for тема, замеры in итог["темы"].items():
        print(f"{тема}:")
        for имя, з in замеры.items():
            if not з.get("найдено"):
                print(f"    {имя:28} не найден на странице")
                continue
            знак = "ок" if з["проходит"] else "НИЖЕ ПОРОГА"
            print(f"    {имя:28} {з['отношение']} при пороге {з['порог']} — {знак}"
                  f"  ({з['цвет']} на {з['фон']})")
    return код


if __name__ == "__main__":
    raise SystemExit(main())
