#!/usr/bin/env python3
"""Уходит ли с живой страницы запрос Метрики: измерение, а не наличие кода.

Зачем отдельно от отчётов. Отчёт Метрики говорит, ДОШЛИ ли события до сервиса,
и 15.10 он сказал неприятное: у тринадцати доменов счётчик есть, девять целей
записаны, визиты собираются, а достижений целей за семь суток ноль. Отчёт при
этом не отвечает, где обрыв: разметка не отправляет, край не пропускает или
цель не настроена.

Здесь измеряется первое звено — уходит ли с САМОЙ страницы запрос
`mc.yandex.ru/watch/<счётчик>` и какие цели в нём названы. Браузер настоящий
(chromium), страница живая, перехват на уровне сети.

Три исхода различаются, и ни один не выдаётся за другой:

  запрос ушёл, цель названа     разметка работает и событие отправлено
  запрос ушёл, цели нет         счётчик считает визиты, цель не отправляется
  запроса нет вовсе             разметки на странице нет либо она не исполняется

Чего инструмент НЕ делает: не нажимает в плеере и не выдаёт отсутствие события
за поломку счётчика — события бывают привязаны к действию, которого проба не
совершает. Поэтому в отчёте отдельно сказано, какие действия проба делала.

    python3 automation/local/metrika-hit-probe.py --url https://yummyani.site/
    python3 automation/local/metrika-hit-probe.py --domain lordserials22.info
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from urllib.parse import parse_qs, urlparse

КОРЕНЬ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(КОРЕНЬ))

from factory.seo.render_check import chromium_path  # noqa: E402

РЕЕСТР = КОРЕНЬ / "config" / "analytics.json"
ОЖИДАНИЕ_МС = 20000


def цель_из_адреса(адрес: str) -> str:
    """Имя цели Метрики из page-url запроса, иначе пустая строка.

    Цель (reachGoal) передаётся адресом вида goal://<домен>/<имя>. Параметр
    `t` целью НЕ является: это телеметрия браузера, и первая редакция пробы
    приняла её за цель — тогда «цели работают» получалось на любом сайте, где
    счётчик просто считает визиты.
    """
    if not адрес.startswith("goal://"):
        return ""
    хвост = адрес[len("goal://"):]
    имя = хвост.split("/", 1)[1] if "/" in хвост else ""
    return имя.strip("/") or адрес


def счётчик_домена(домен: str) -> int | None:
    д = json.loads(РЕЕСТР.read_text(encoding="utf-8"))
    for з in д.get("properties") or []:
        if з.get("domain") == домен:
            return з.get("counter_id")
    return None


def проба(url: str, ждать_мс: int = ОЖИДАНИЕ_МС) -> dict:
    """Загрузить страницу и собрать запросы к Метрике."""
    from playwright.sync_api import sync_playwright

    запросы: list[dict] = []
    итог: dict = {"url": url, "код": None, "запросы": запросы, "ошибка": ""}
    with sync_playwright() as p:
        браузер = p.chromium.launch(executable_path=chromium_path(),
                                    args=["--no-sandbox"])
        стр = браузер.new_page(viewport={"width": 1366, "height": 768})

        def перехват(запрос):
            if "mc.yandex.ru" not in запрос.url and "mc.yandex.com" not in запрос.url:
                return
            р = urlparse(запрос.url)
            м = re.search(r"/watch/(\d+)", р.path)
            параметры = parse_qs(р.query)
            # Цель Метрики (reachGoal) узнаётся по page-url вида
            # goal://<домен>/<имя>, а НЕ по параметру t: t — телеметрия
            # браузера, и принимать её за цель значило бы объявить цели
            # работающими на любом сайте, где счётчик просто считает визиты.
            адрес = (параметры.get("page-url") or [""])[0]
            цель = цель_из_адреса(адрес)
            запросы.append({
                "счётчик": int(м.group(1)) if м else None,
                "путь": р.path,
                "цель": цель,
                "страница": адрес[:120],
            })

        стр.on("request", перехват)
        try:
            ответ = стр.goto(url, wait_until="domcontentloaded", timeout=60000)
            итог["код"] = ответ.status if ответ else None
            # Разметка Метрики инициализируется после загрузки; ждём.
            стр.wait_for_timeout(ждать_мс)
            # Одно безопасное действие: прокрутка. Нажатий проба не делает.
            стр.mouse.wheel(0, 1200)
            стр.wait_for_timeout(2000)
        except Exception as сбой:  # noqa: BLE001 — измерение не падает
            итог["ошибка"] = f"{type(сбой).__name__}: {сбой}"[:160]
        finally:
            браузер.close()
    return итог


def главное(аргв=None) -> int:
    р = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    р.add_argument("--url", action="append", default=[])
    р.add_argument("--domain", action="append", default=[],
                   help="домен: берётся https://<домен>/ и счётчик из реестра")
    р.add_argument("--wait-ms", type=int, default=ОЖИДАНИЕ_МС)
    опции = р.parse_args(аргв)

    задания: list[tuple[str, str, int | None]] = []
    for u in опции.url:
        задания.append((urlparse(u).hostname or u, u, счётчик_домена(
            urlparse(u).hostname or "")))
    for d in опции.domain:
        задания.append((d, f"https://{d}/", счётчик_домена(d)))
    if not задания:
        print("нужен --url или --domain", file=sys.stderr)
        return 2

    плохо = 0
    for домен, url, ожидаемый in задания:
        и = проба(url, опции.wait_ms)
        счётчики = {з["счётчик"] for з in и["запросы"] if з["счётчик"]}
        цели = sorted({з["цель"] for з in и["запросы"] if з["цель"]})
        print(f"\n{домен}: код {и['код']}, запросов к Метрике "
              f"{len(и['запросы'])}")
        if и["ошибка"]:
            print(f"   ошибка загрузки: {и['ошибка']}")
        if not и["запросы"]:
            print("   запроса нет вовсе: разметки на странице нет либо она не "
                  "исполняется — это НЕ «цель не настроена»")
            плохо += 1
        else:
            print(f"   счётчики в запросах: {sorted(счётчики) or '—'}; "
                  f"в реестре {ожидаемый}")
            if ожидаемый and счётчики and ожидаемый not in счётчики:
                print("   ВНИМАНИЕ: на странице другой счётчик, чем в реестре")
                плохо += 1
            print(f"   названные цели: {цели or 'нет — считаются только визиты'}")
        print("   действия пробы: загрузка и прокрутка; нажатий не было, "
              "поэтому цели, привязанные к нажатию, здесь не ожидаются")
    return 1 if плохо else 0


if __name__ == "__main__":
    raise SystemExit(главное())
