#!/usr/bin/env python3
"""Ссылки на подборки с `/catalog/` и отправка целей — ПУБЛИЧНО, числами.

Зачем отдельная проверка. `/catalog/` отдаёт 200 и тогда, когда ссылок на
подборки на ней нет вовсе: именно так и было до 27.10, а это самая посещаемая
страница разделов (animedia.icu: 1252 просмотра за 20–26.10 против 414 у
главной). Код ответа на вопрос «ведёт ли каталог к подборкам» не отвечает —
отвечает число ссылок и метка полосы.

Что проверяется на каждом домене:

* `/catalog/` отдаёт 200, на ней полоса с меткой `data-collections="catalog"`
  (полоса раздела помечена `section` — метки различают их без догадок по
  подписи);
* сколько с этой страницы ведёт ссылок на `/collection/…` и каких;
* на странице работы — единственная точка отправки целей `window.__sfGoal`,
  цель `title_view` и номер счётчика в разметке.

Повторы запроса — из-за MOD-204: animedia.icu отдаёт 503 части запросов при
исправном приложении, и один 503 не является ответом о содержимом страницы.
Число попыток попадает в отчёт: молчаливый повтор скрыл бы деградацию.

Только чтение. Ничего не публикуется и не меняется.

    python3 automation/local/catalog-collections-public-check.py \\
        --domain zonafilm.space --title /title/shepot-za-oknom/
    python3 automation/local/catalog-collections-public-check.py --all
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys

#: Домены, у которых полоса каталога выложена, и работа для проверки целей.
#: Пустая работа означает «цели на этом домене этой проверкой не мерим».
ИЗВЕСТНЫЕ = (
    ("zonafilm.space", "/title/shepot-za-oknom/"),
    ("zonafilm12.site", ""),
    ("animedia.icu", ""),
)
ПОПЫТОК = 6


def получить(адрес: str, попыток: int = ПОПЫТОК) -> tuple[str, str, int]:
    """Тело, код ответа и число потраченных попыток."""
    тело, код = "", "0"
    for н in range(1, попыток + 1):
        п = subprocess.run(
            ["curl", "-sS", "-m", "30", "-w", "\n%{http_code}", адрес],
            capture_output=True, text=True)
        куски = п.stdout.rsplit("\n", 1)
        if len(куски) == 2:
            тело, код = куски[0], куски[1].strip()
        if код == "200":
            return тело, код, н
    return тело, код, попыток


def разобрать_каталог(тело: str) -> dict:
    """Что страница каталога говорит о подборках."""
    ссылки = sorted(set(re.findall(r'href="(/collection/[a-z0-9_-]+/)"', тело)))
    полоса = re.search(r'data-collections="(catalog|section)"', тело)
    return {
        "метка полосы": полоса.group(1) if полоса else None,
        "ссылок на подборки": len(ссылки),
        "адреса": ссылки,
        "ссылка на хаб": '<a href="/collections/">' in тело,
    }


def разобрать_цели(тело: str) -> dict:
    """Уходит ли цель с этой страницы и каким счётчиком."""
    счётчик = re.search(r"var C=(\d+),", тело)
    return {
        "точка отправки": "window.__sfGoal=g" in тело,
        "цель title_view": "__sfGoalOnce('title_view')" in тело,
        "счётчик": счётчик.group(1) if счётчик else None,
        "третий аргумент у отправки": bool(
            re.search(r"reachGoal['\"],\s*n\s*,", тело)),
    }


def проверить(домен: str, работа: str) -> dict:
    тело, код, попыток = получить(f"https://{домен}/catalog/")
    строка = {"/catalog/ код": код, "попыток": попыток}
    if код == "200":
        строка.update(разобрать_каталог(тело))
    if работа:
        тело_р, код_р, попыток_р = получить(f"https://{домен}{работа}")
        карточка = {"код": код_р, "попыток": попыток_р, "адрес": работа}
        if код_р == "200":
            карточка.update(разобрать_цели(тело_р))
        строка["карточка"] = карточка
    return строка


def главная(аргв=None) -> int:
    р = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    р.add_argument("--domain")
    р.add_argument("--title", default="", help="адрес работы для проверки целей")
    р.add_argument("--all", action="store_true", help="все известные домены")
    а = р.parse_args(аргв)
    if not а.all and not а.domain:
        р.error("нужен --domain или --all")
    пары = (ИЗВЕСТНЫЕ if а.all else ((а.domain, а.title),))

    итог, беда = {}, 0
    for домен, работа in пары:
        строка = проверить(домен, работа)
        итог[домен] = строка
        # Беда — это 200 без полосы либо полоса без ссылок: страница обещает
        # каталог и не ведёт к подборкам.
        if строка["/catalog/ код"] != "200":
            беда += 1
        elif строка.get("метка полосы") != "catalog" or not строка.get(
                "ссылок на подборки"):
            беда += 1
        карточка = строка.get("карточка") or {}
        if карточка and (карточка.get("код") != "200"
                         or not карточка.get("точка отправки")
                         or карточка.get("третий аргумент у отправки")):
            беда += 1
    print(json.dumps(итог, ensure_ascii=False, indent=1))
    print(f"\nдоменов с бедой: {беда} из {len(пары)}")
    return 1 if беда else 0


if __name__ == "__main__":
    raise SystemExit(главная())
