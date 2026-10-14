#!/usr/bin/env python3
"""Сериальная поверхность ДЕЙСТВИЕМ: сезоны, серии, переход по серии.

Зачем отдельный инструмент. Общий осмотр считал сезоны и серии селектором
`a[href*='season'], [class*='season']` и на записи с ОДНИМ сезоном из восьми
серий писал «сезоны 8, серии 8»: адрес каждой серии содержит слово `season`,
поэтому счётчик сезонов считал серии. Число выглядело правдоподобно и прошло
бы в отчёт, не описывая ничего. А главное — проверки ДЕЙСТВИЕМ на этой
поверхности не было вовсе: ни один переход по серии не нажимался.

Здесь измеряется ровно то, что обещает разметка:
  * сколько блоков сезонов (`.sea`) — столько сезонов и должно быть в данных;
  * сколько серий доступно (`.eps a`) и сколько заявлено без дорожки
    (`.eps [data-off]`) — это разные вещи, и витрина их разделяет;
  * заголовок сезона называет заявленное число серий;
  * нажатие на вторую доступную серию УВОДИТ на её адрес, и там она помечена
    `aria-current="page"`;
  * страница сезона открывается и содержит тот же ряд серий;
  * недоступная серия НЕ ссылка (`span[data-off]`), то есть её нельзя открыть
    ни клавиатурой, ни прямым адресом из разметки;
  * состояние плеера на странице серии — без publisher_id ожидается
    `noaccess`, и это доказывает, что рамка на месте и ждёт только номер.

Ожидания берутся из доставленного `*-details.json` (`seasons`), а не
придумываются: расхождение числа сезонов или серий — дефект витрины, а не
вкусовая придирка.
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
ГОТОВЫЙ_CHROMIUM = Path("/home/claude/.cache/ms-playwright/chromium-1234"
                        "/chrome-linux64/chrome")
КОМПЬЮТЕР = {"width": 1366, "height": 768}


def окружение(конфиг: dict, проект: Path, данные: Path) -> dict:
    env = dict(os.environ)
    for имя, шаблон in (конфиг.get("environment") or {}).items():
        env[имя] = (str(шаблон).replace("<data>", str(данные))
                    .replace("<app>", str(проект)))
    контакт = str(конфиг.get("contact_email") or "").strip()
    if контакт:
        env["SITE_CONTACT_EMAIL"] = контакт
    домен = str(конфиг.get("domain") or "").strip()
    if домен:
        env["LORDS_INDEXING_SITE"] = домен
    разрешение = (конфиг.get("indexing") or {}).get("release_permits_open")
    env["LORDS_INDEXING_RELEASE_PERMITS_OPEN"] = "true" if разрешение is True else "false"
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    return env


def поднять(проект: Path, конфиг: dict, данные: Path, порт: int):
    точка = проект / "src" / конфиг["entrypoint"]
    процесс = subprocess.Popen(
        [sys.executable, str(точка), "--port", str(порт)],
        cwd=проект, env=окружение(конфиг, проект, данные),
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    for _ in range(120):
        try:
            urllib.request.urlopen(f"http://127.0.0.1:{порт}/healthz", timeout=12)
            return процесс, True
        except Exception:  # noqa: BLE001
            if процесс.poll() is not None:
                return процесс, False
            time.sleep(1)
    return процесс, False


def ожидание_из_данных(данные: Path, site: str) -> dict | None:
    """Первая запись с сезонами и её ожидаемый состав — из доставленных данных."""
    файл = данные / f"{site}-details.json"
    if not файл.is_file():
        return None
    д = json.loads(файл.read_text(encoding="utf-8"))
    for слаг, деталь in (д.get("details") or {}).items():
        сезоны = деталь.get("seasons") or []
        if сезоны and (деталь.get("type") in ("tv", "series")):
            return {
                "слаг": слаг, "имя": деталь.get("name"),
                "сезонов": len(сезоны),
                "серий заявлено": sum(int(с.get("eps") or 0) for с in сезоны),
                "серий доступно": sum(int(с.get("avail") or 0) for с in сезоны),
                "сезоны": сезоны,
            }
    return None


def проверить(стр, база: str, ожидание: dict) -> dict:
    итог: dict = {"слаг": ожидание["слаг"], "имя": ожидание["имя"],
                  "ожидание": {к: ожидание[к] for к in
                               ("сезонов", "серий заявлено", "серий доступно")}}
    стр.goto(f"{база}/title/{ожидание['слаг']}/", wait_until="domcontentloaded")

    # В рантайме два вида разметки серий: `.sea/.eps` у оформления lords и
    # `.zsea/.zeps` у zona. Партия идёт на первом, но инструмент обязан
    # работать на обоих — иначе на другом оформлении он тихо вернёт нули.
    итог["сезонов на странице"] = стр.locator(".sea, .zsea").count()
    итог["серий доступно на странице"] = стр.locator(".eps a, .zeps a").count()
    итог["серий без дорожки на странице"] = стр.locator(".eps [data-off], .zeps [data-off]").count()
    итог["заголовки сезонов"] = [
        с.strip() for с in стр.locator(".sea__h, .zsea__h").all_inner_texts()]
    итог["сезонов сходится"] = (итог["сезонов на странице"] == ожидание["сезонов"])
    итог["серий сходится"] = (
        итог["серий доступно на странице"] == ожидание["серий доступно"]
        and (итог["серий доступно на странице"] + итог["серий без дорожки на странице"])
        == ожидание["серий заявлено"])
    итог["состояние плеера на карточке"] = стр.evaluate(
        "() => {const n=document.querySelector('[data-player]');"
        "return n ? (n.getAttribute('data-state') || '') : null;}")

    # Переход ДЕЙСТВИЕМ: нажимаем вторую доступную серию, если она есть.
    ссылки = стр.locator(".eps a, .zeps a")
    если_есть = ссылки.count()
    if если_есть >= 2:
        адрес_до = стр.url
        цель = ссылки.nth(1).get_attribute("href")
        with стр.expect_navigation(wait_until="domcontentloaded", timeout=90000):
            ссылки.nth(1).click()
        итог["переход по серии"] = {
            "цель": цель,
            "адрес изменился": стр.url != адрес_до,
            "адрес": стр.url.replace(база, ""),
            "адрес совпал с ссылкой": стр.url.replace(база, "") == цель,
            # На странице серии именно эта серия обязана быть помечена
            # текущей: иначе посетитель не видит, где он.
            "помечена текущей": стр.locator('.eps a[aria-current="page"], .zeps a[aria-current="page"]').count() == 1,
            "номер текущей": (
                стр.locator('.eps a[aria-current="page"], .zeps a[aria-current="page"]').first.inner_text().strip()
                if стр.locator('.eps a[aria-current="page"], .zeps a[aria-current="page"]').count() else None),
            "состояние плеера": стр.evaluate(
                "() => {const n=document.querySelector('[data-player]');"
                "return n ? (n.getAttribute('data-state') || '') : null;}"),
            "код ответа": None,
        }
    else:
        итог["переход по серии"] = {"доступных ссылок": если_есть,
                                    "проверка не проводилась": True}

    # Страница сезона: отдельный адрес, тот же ряд серий.
    номер = int((ожидание["сезоны"][0] or {}).get("n") or 1)
    стр.goto(f"{база}/title/{ожидание['слаг']}/season/{номер}/",
             wait_until="domcontentloaded")
    итог["страница сезона"] = {
        "h1": (стр.locator("h1").first.inner_text().strip()
               if стр.locator("h1").count() else ""),
        "серий доступно": стр.locator(".eps a, .zeps a").count(),
        "серий без дорожки": стр.locator(".eps [data-off], .zeps [data-off]").count(),
    }
    return итог


def main() -> int:
    р = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    р.add_argument("--site", required=True)
    р.add_argument("--data", required=True)
    р.add_argument("--project", default=None)
    р.add_argument("--port", type=int, default=19700)
    а = р.parse_args()

    проект = Path(а.project or (КОРЕНЬ / "var" / "new-sites" / а.site))
    конфиг = json.loads((проект / "config" / "site.json").read_text(encoding="utf-8"))
    выход = КОРЕНЬ / "var" / "k2-data" / "audit" / а.site
    выход.mkdir(parents=True, exist_ok=True)

    врем = Path(tempfile.mkdtemp(prefix=f"serial-{а.site}-"))
    данные = врем / "data"
    данные.mkdir()
    for ф in Path(а.data).glob(f"{а.site}-*.json"):
        shutil.copy(ф, данные / ф.name)

    ожидание = ожидание_из_данных(данные, а.site)
    if not ожидание:
        print(f"{а.site}: в доставленных данных нет записи с сезонами — "
              "проверять нечего, и это НЕ успех")
        shutil.rmtree(врем, ignore_errors=True)
        return 2

    процесс, готово = поднять(проект, конфиг, данные, а.port)
    if not готово:
        вывод = (процесс.stdout.read() if процесс.stdout else b"").decode("utf-8", "replace")
        (выход / "serial-fail.log").write_text(вывод, encoding="utf-8")
        print("ОТКАЗ: рантайм не поднялся; журнал в", выход / "serial-fail.log")
        процесс.kill()
        shutil.rmtree(врем, ignore_errors=True)
        return 1

    база = f"http://127.0.0.1:{а.port}"
    итог = {"site": а.site, "domain": конфиг.get("domain")}
    код = 0
    try:
        from playwright.sync_api import sync_playwright

        with sync_playwright() as pw:
            пуск: dict = {}
            if ГОТОВЫЙ_CHROMIUM.is_file():
                пуск["executable_path"] = str(ГОТОВЫЙ_CHROMIUM)
            браузер = pw.chromium.launch(**пуск)
            контекст = браузер.new_context(viewport=КОМПЬЮТЕР)
            стр = контекст.new_page()
            итог["сериал"] = проверить(стр, база, ожидание)
            контекст.close()
            браузер.close()
    except Exception as ош:  # noqa: BLE001
        итог["ошибка"] = f"{type(ош).__name__}: {ош}"
        код = 1
    finally:
        процесс.terminate()
        try:
            процесс.wait(timeout=15)
        except subprocess.TimeoutExpired:
            процесс.kill()
        shutil.rmtree(врем, ignore_errors=True)

    (выход / "serial.json").write_text(
        json.dumps(итог, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8")
    print(json.dumps(итог, ensure_ascii=False, indent=2))
    с = итог.get("сериал") or {}
    if not (с.get("сезонов сходится") and с.get("серий сходится")):
        код = код or 3
    return код


if __name__ == "__main__":
    raise SystemExit(main())
