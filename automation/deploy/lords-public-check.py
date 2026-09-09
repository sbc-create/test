#!/usr/bin/env python3
"""Публичная приёмка витрины Lords. Выполняется от claude, ничего не меняет.

Одного HTTP 200 недостаточно, и это не фигура речи: витрина три месяца отдавала
двести с каталогом тридцатипятичасовой давности, а однажды плеер исчез со всех
страниц при исправных двухстах. Поэтому проверяется не доступность, а то, что
выложено именно ожидаемое.

Проверки идут по публичному HTTPS-домену, а не по 127.0.0.1: default-vhost и
чужой сертификат — тоже способ ответить двумястами не тем сайтом.
"""

from __future__ import annotations

import argparse
import json
import re
import ssl
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

МАРШРУТЫ = ("/", "/catalog/", "/search/", "/new/")
ШИРИНЫ = (390, 768, 1440)
ССЫЛКА_ТАЙТЛА = re.compile(r'href="(/title/[^"]+)"')
КАРТИНКА = re.compile(r'<img[^>]+src="([^"]+)"')
ПЛЕЕР = re.compile(r"<video-player|<iframe", re.I)


def достать(адрес: str, таймаут: float = 30.0) -> tuple[int, str, dict]:
    запрос = urllib.request.Request(адрес, headers={"User-Agent": "lords-public-check"})
    контекст = ssl.create_default_context()
    try:
        with urllib.request.urlopen(запрос, timeout=таймаут, context=контекст) as ответ:
            тело = ответ.read(4_000_000).decode("utf-8", "replace")
            return ответ.status, тело, dict(ответ.headers)
    except urllib.error.HTTPError as ошибка:
        return ошибка.code, "", {}
    except Exception as ошибка:  # noqa: BLE001 — недоступность это тоже результат
        return 0, f"{type(ошибка).__name__}: {ошибка}", {}


def проверить_картинки(база: str, страницы: list[str], нужно: int = 30) -> dict:
    адреса, видел = [], set()
    for html in страницы:
        for src in КАРТИНКА.findall(html):
            полный = src if src.startswith("http") else база + src
            if полный not in видел:
                видел.add(полный)
                адреса.append(полный)
    проверено = годных = 0
    беды = []
    for адрес in адреса[: нужно + 15]:
        проверено += 1
        try:
            запрос = urllib.request.Request(адрес, headers={"User-Agent": "lords-public-check"})
            with urllib.request.urlopen(запрос, timeout=20) as ответ:
                тип = ответ.headers.get("Content-Type", "")
                тело = ответ.read(300_000)
            # Заглушка постера — 532-байтная SVG, и отдаётся она с кодом 200.
            # Размер здесь единственный признак, отличающий её от картинки.
            if ответ.status == 200 and тип.startswith("image/") and len(тело) > 1200:
                годных += 1
            else:
                беды.append({"url": адрес, "status": ответ.status,
                             "type": тип, "bytes": len(тело)})
        except Exception as ошибка:  # noqa: BLE001
            беды.append({"url": адрес, "error": f"{type(ошибка).__name__}: {ошибка}"[:160]})
        if годных >= нужно and проверено >= нужно:
            break
    return {"checked": проверено, "ok": годных, "required": нужно, "failures": беды[:10]}


def браузеры(репозиторий: Path, база: str, сайт: str, куда: Path) -> dict:
    """Штатный набор приёмки релиза в Chromium и Firefox."""
    итоги = {}
    конфиг = репозиторий / "var" / "release-acceptance.config.js"
    конфиг.parent.mkdir(parents=True, exist_ok=True)
    конфиг.write_text(
        "const { defineConfig, devices } = require('@playwright/test');\n"
        "const launchOptions = { args: ['--no-sandbox', '--disable-dev-shm-usage'] };\n"
        "module.exports = defineConfig({\n"
        "  testDir: '../tests/e2e-release',\n"
        "  timeout: 180000, expect: { timeout: 20000 },\n"
        "  fullyParallel: false, forbidOnly: true, retries: 0, workers: 1,\n"
        "  reporter: [['list'], ['json', { outputFile: 'var/artifacts/release-acceptance.json' }]],\n"
        "  use: { trace: 'off', screenshot: 'only-on-failure' },\n"
        "  projects: [\n"
        "    { name: 'chromium', use: { ...devices['Desktop Chrome'], launchOptions } },\n"
        "    { name: 'firefox', use: { ...devices['Desktop Firefox'] } },\n"
        "  ],\n"
        "});\n", encoding="utf-8")
    for движок in ("chromium", "firefox"):
        журнал = куда / f"playwright-{движок}.log"
        готово = subprocess.run(
            ["npx", "playwright", "test", "--config=var/release-acceptance.config.js",
             f"--project={движок}"],
            cwd=репозиторий, capture_output=True, text=True, timeout=3600,
            env={**dict(__import__("os").environ),
                 "PLAYWRIGHT_BROWSERS_PATH": "/opt/pw-browsers",
                 "RELEASE_BASE": база, "RELEASE_SITE": сайт,
                 "PATH": "/usr/local/bin:/usr/bin:/bin"})
        журнал.write_text(готово.stdout + "\n" + готово.stderr, encoding="utf-8")
        итоги[движок] = "pass" if готово.returncode == 0 else "fail"
    return итоги


def снимки(база: str, куда: Path, метка: str) -> list[str]:
    движок = ("/opt/pw-browsers/chromium_headless_shell-1234/"
              "chrome-headless-shell-linux64/chrome-headless-shell")
    сделаны = []
    for ширина in ШИРИНЫ:
        файл = куда / f"{метка}-{ширина}.png"
        subprocess.run(
            [движок, "--no-sandbox", "--disable-gpu", "--disable-dev-shm-usage",
             "--hide-scrollbars", f"--window-size={ширина},2200",
             "--virtual-time-budget=15000",
             f"--user-data-dir={куда}/profile-{метка}-{ширина}",
             f"--screenshot={файл}", база + "/"],
            capture_output=True, timeout=200)
        if файл.is_file() and файл.stat().st_size > 0:
            сделаны.append(str(файл))
    return сделаны


def проверка(args) -> dict:
    база = f"https://{args.domain}"
    куда = Path(args.evidence)
    куда.mkdir(parents=True, exist_ok=True)
    отчёт = {"site": args.site, "domain": args.domain, "url": база,
             "checks": [], "routes": {}, "failures": []}

    def записать(имя: str, ок: bool, деталь: str = "") -> bool:
        отчёт["checks"].append({"check": имя, "ok": bool(ок), "detail": деталь})
        if not ок:
            отчёт["failures"].append(f"{имя}: {деталь}")
        return bool(ок)

    страницы = []
    for маршрут in МАРШРУТЫ:
        код, тело, _ = достать(база + маршрут)
        отчёт["routes"][маршрут] = код
        записать(f"маршрут {маршрут} отвечает 200", код == 200, str(код))
        if код == 200:
            страницы.append(тело)
    домашняя = страницы[0] if страницы else ""

    записать("страница называет свой домен", args.domain in домашняя,
             "маркера витрины нет" if домашняя else "главная не получена")

    путь_тайтла = ""
    совпало = ССЫЛКА_ТАЙТЛА.search(домашняя)
    if совпало:
        путь_тайтла = совпало.group(1)
        код, тело, _ = достать(база + путь_тайтла)
        отчёт["routes"][путь_тайтла] = код
        записать(f"страница произведения {путь_тайтла} отвечает 200", код == 200, str(код))
        if код == 200:
            страницы.append(тело)
            записать("плеер на странице произведения на месте",
                     bool(ПЛЕЕР.search(тело)), "разметки плеера нет")
    else:
        записать("на главной есть ссылки на произведения", False, "ссылок нет")

    записать("нет ответов 5xx", all(к < 500 for к in отчёт["routes"].values()),
             str({м: к for м, к in отчёт["routes"].items() if к >= 500}))

    картинки = проверить_картинки(база, страницы, нужно=args.images)
    отчёт["images"] = картинки
    записать(f"загрузилось не меньше {args.images} изображений",
             картинки["ok"] >= args.images,
             f"годных {картинки['ok']} из {картинки['checked']}")

    if args.expect_marker:
        # Маркер ищется в таблице стилей, а не в разметке страницы. Разметка
        # зависит от данных: класс «постер отсутствует» появляется от нехватки
        # обогащения, а не от смены шаблона, и доказывал бы не то. Таблица
        # стилей — чистый актив шаблона: у кандидата она строгое надмножество
        # боевой, девять селекторов против нуля в обратную сторону.
        код, стили, _ = достать(база + "/assets/site.css")
        отчёт["stylesheet_bytes"] = len(стили)
        записать("таблица стилей отдаётся", код == 200, str(код))
        записать(f"публично видно изменение шаблона: {args.expect_marker}",
                 args.expect_marker in стили,
                 f"маркера нет в /assets/site.css ({len(стили)} б)")

    отчёт["screenshots"] = снимки(база, куда, args.label)
    записать("снимки сделаны на трёх ширинах", len(отчёт["screenshots"]) == len(ШИРИНЫ),
             f"получено {len(отчёт['screenshots'])}")

    if args.browsers:
        итоги = браузеры(Path(args.repo), база, args.site, куда)
        отчёт["browsers"] = итоги
        записать("Chromium прошёл", итоги.get("chromium") == "pass", str(итоги))
        записать("Firefox прошёл", итоги.get("firefox") == "pass", str(итоги))

    отчёт["passed"] = not отчёт["failures"]
    return отчёт


def main() -> int:
    р = argparse.ArgumentParser()
    р.add_argument("--site", required=True)
    р.add_argument("--domain", required=True)
    р.add_argument("--evidence", required=True)
    р.add_argument("--repo", default="/home/claude/wt-release-03")
    р.add_argument("--label", default="after")
    р.add_argument("--images", type=int, default=30)
    р.add_argument("--expect-marker", default="")
    р.add_argument("--browsers", action="store_true")
    args = р.parse_args()
    отчёт = проверка(args)
    print(json.dumps(отчёт, ensure_ascii=False, indent=2))
    return 0 if отчёт["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
