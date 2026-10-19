#!/usr/bin/env python3
"""Снимки страницы на компьютере и телефоне с манифестом. Только чтение сайта.

Зачем отдельный инструмент. Задание владельца требует показать снимки «до» и
«после» на компьютере и телефоне. Сами PNG в git не коммитятся (они раздули бы
репозиторий — правило уже записано в `tests/tools/screenshot_manifest.py`),
поэтому здесь снимок сохраняется в каталог вне репозитория, а в репозиторий
идёт МАНИФЕСТ: адрес, размер окна, размер файла, SHA-256 и время съёмки. Без
манифеста утверждение «снимки сняты» проверить нечем.

    python3 automation/local/page-screenshots.py --url https://zonafilm.cc/ \\
        --label before --out /путь/к/каталогу

Коды: 0 — снято, 2 — снять не удалось (браузера нет или страница не открылась).
"""
from __future__ import annotations

import argparse
import datetime as dt
import glob
import hashlib
import json
import pathlib
import sys

ХРОМ_ШАБЛОН = "/home/claude/.cache/ms-playwright/chromium*/chrome-linux*/chrome"
ОКНА = {"desktop": (1440, 900), "phone": (390, 844)}


def снять(адрес: str, метка: str, каталог: pathlib.Path,
          окна: dict | None = None, полная: bool = True) -> dict:
    """Снимки по каждому окну. Возвращает манифест; ничего не печатает."""
    окна = окна or ОКНА
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return {"измерено": False, "почему": "playwright не установлен"}
    кандидаты = sorted(glob.glob(ХРОМ_ШАБЛОН))
    if not кандидаты:
        return {"измерено": False, "почему": "Chromium playwright не найден"}
    каталог.mkdir(parents=True, exist_ok=True)
    снимки = []
    with sync_playwright() as p:
        браузер = p.chromium.launch(executable_path=кандидаты[-1],
                                    args=["--no-sandbox", "--disable-dev-shm-usage"])
        try:
            for имя, (ширина, высота) in окна.items():
                страница = браузер.new_page(viewport={"width": ширина, "height": высота})
                try:
                    ответ = страница.goto(адрес, wait_until="load", timeout=45000)
                    код = ответ.status if ответ else 0
                    файл = каталог / f"{метка}-{имя}.png"
                    страница.screenshot(path=str(файл), full_page=полная)
                    байты = файл.read_bytes()
                    снимки.append({
                        "окно": имя, "ширина": ширина, "высота": высота,
                        "код": код, "файл": str(файл), "байт": len(байты),
                        "sha256": hashlib.sha256(байты).hexdigest(),
                    })
                except Exception as сбой:  # noqa: BLE001 — снимок не важнее отчёта
                    снимки.append({"окно": имя, "почему": f"{type(сбой).__name__}: {сбой}"})
                finally:
                    страница.close()
        finally:
            браузер.close()
    удачных = [с for с in снимки if с.get("sha256")]
    return {"измерено": bool(удачных), "адрес": адрес, "метка": метка,
            "снято_в": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "снимки": снимки,
            "почему": "" if удачных else "ни одно окно не снято"}


def main(аргв: list[str] | None = None) -> int:
    р = argparse.ArgumentParser(description="снимки страницы с манифестом")
    р.add_argument("--url", required=True)
    р.add_argument("--label", default="snapshot")
    р.add_argument("--out", default="/tmp/page-screenshots")
    р.add_argument("--viewport-only", choices=sorted(ОКНА), action="append", default=[])
    # Первый экран — отдельный снимок: по полной странице нельзя судить о том,
    # что человек видит сразу, а именно это решает задание про состав главной.
    р.add_argument("--fold", action="store_true",
                   help="снять только первый экран, без прокрутки")
    р.add_argument("--json", action="store_true")
    дов = р.parse_args(аргв)
    окна = ({и: ОКНА[и] for и in дов.viewport_only} if дов.viewport_only else ОКНА)
    итог = снять(дов.url, дов.label, pathlib.Path(дов.out), окна,
                 полная=not дов.fold)
    if дов.json:
        print(json.dumps(итог, ensure_ascii=False, indent=2))
    else:
        if not итог["измерено"]:
            print(f"НЕ ИЗМЕРЕНО: {итог['почему']}")
        else:
            print(f"{итог['адрес']} — {итог['метка']}, снято {итог['снято_в']}")
            for с in итог["снимки"]:
                if с.get("sha256"):
                    print(f"   {с['окно']:8} {с['ширина']}×{с['высота']}"
                          f" код {с['код']} {с['байт']:8} байт"
                          f" sha256 {с['sha256'][:16]}… {с['файл']}")
                else:
                    print(f"   {с['окно']:8} НЕ СНЯТО — {с.get('почему')}")
    return 0 if итог["измерено"] else 2


if __name__ == "__main__":
    sys.exit(main())
