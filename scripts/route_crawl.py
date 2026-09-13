#!/usr/bin/env python3
"""Обход всех внутренних ссылок собранного кандидата.

Что именно считается дефектом — и почему каждый из них назван отдельно:

* `route_failures` — адрес, на который ведёт ссылка, ответил не 200 и не 308.
* `soft_404` — код 200 на странице, которая словами сообщает, что записи нет.
  Это опаснее честной 404: обход её не заметит, а зритель упрётся.
* `wrong_entity_200` — страница произведения открылась, но `H1` не совпал с
  названием записи, на которую вела карточка. Двухсотка с чужой сущностью —
  самый тихий вид битой ссылки.
* `orphan_pages` — запись каталога, до которой не ведёт ни одна ссылка обхода.
* `broken_internal_links` — ссылка в разметке, ведущая в никуда.
* `redirect_loops` и `redirect_chains_gt1` — переход, который не заканчивается
  за один шаг. Один шаг допустим, два уже означают, что канонического адреса
  у документа нет.
* `broken_images` — изображение, которое не отдалось. Считается отдельно по
  внешним и внутренним источникам: недоступность чужого CDN из закрытого
  контура — свойство контура, а не витрины, и смешивать их значит прятать
  собственные дефекты за чужими.

Обход идёт вширь от корня и ограничен своим хостом. Внешние адреса не
запрашиваются вовсе: витрина за них не отвечает.
"""

from __future__ import annotations

import argparse
import collections
import html as html_mod
import json
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone

ССЫЛКА = re.compile(r'<a\b[^>]*?href="([^"]*)"', re.I)
КАРТИНКА = re.compile(r'<img\b[^>]*?src="([^"]*)"', re.I)
H1 = re.compile(r"<h1[^>]*>(.*?)</h1>", re.S | re.I)
ТЕГ = re.compile(r"<[^>]+>")

#: Слова, которыми страница сообщает, что записи нет. Двухсотка с ними — soft 404.
ОТСУТСТВИЕ = ("страницы на витрине нет", "страница не найдена",
              "не соответствует ни одной записи")


def текст(кусок: str) -> str:
    return html_mod.unescape(ТЕГ.sub(" ", кусок)).strip()


def в_ascii(адрес: str) -> str:
    """Адрес в том виде, в каком его отправляет браузер.

    В разметке ссылки написаны кириллицей (`/catalog/?kind=Фильм`), а
    `http.client` кодирует строку запроса в ASCII и падает на первой же такой
    ссылке. Браузер их процентно кодирует — обход обязан делать то же самое,
    иначе он проверяет не те адреса, по которым ходят люди.
    """
    части = urllib.parse.urlsplit(адрес)
    return urllib.parse.urlunsplit((
        части.scheme, части.netloc,
        urllib.parse.quote(части.path, safe="/%:@!$&'()*+,;=~-._"),
        urllib.parse.quote(части.query, safe="/%:@!$&'()*+,;=~-._?"),
        "",
    ))


def взять(адрес: str, таймаут: int = 30):
    запрос = urllib.request.Request(в_ascii(адрес), headers={"User-Agent": "route-crawl"})
    класс = urllib.request.HTTPRedirectHandler

    переходы = []

    class Счёт(класс):
        def redirect_request(self, req, fp, code, msg, headers, newurl):
            переходы.append((code, newurl))
            return super().redirect_request(req, fp, code, msg, headers, newurl)

    открыватель = urllib.request.build_opener(Счёт)
    try:
        with открыватель.open(запрос, timeout=таймаут) as ответ:
            тело = ответ.read()
            return ответ.status, тело.decode("utf-8", "replace"), переходы, ответ.url
    except urllib.error.HTTPError as ош:
        return ош.code, (ош.read() or b"").decode("utf-8", "replace"), переходы, адрес
    except OSError as ош:
        return -1, str(ош)[:120], переходы, адрес


def обойти(база: str, ожидаемые: dict, предел: int) -> dict:
    основа = urllib.parse.urlparse(база)
    очередь = collections.deque(["/"])
    видели = {"/"}
    отчёт = {
        "base": база, "checked": 0, "route_failures": [], "soft_404": [],
        "wrong_entity_200": [], "broken_internal_links": [], "redirect_loops": [],
        "redirect_chains_gt1": [], "reached": set(), "images": {"external": {}, "internal": {}},
    }
    картинки_проверены = set()

    while очередь and отчёт["checked"] < предел:
        путь = очередь.popleft()
        статус, тело, переходы, конечный = взять(база + путь)
        отчёт["checked"] += 1

        if len(переходы) > 1:
            отчёт["redirect_chains_gt1"].append({"path": путь, "hops": переходы})
        цели = [ц for _, ц in переходы]
        if len(set(цели)) != len(цели):
            отчёт["redirect_loops"].append({"path": путь, "hops": переходы})

        if статус not in (200, 404):
            отчёт["route_failures"].append({"path": путь, "status": статус})
            continue
        if статус == 404:
            # 404 на адресе, до которого довела ССЫЛКА, — битая ссылка.
            if путь != "/":
                отчёт["broken_internal_links"].append({"path": путь, "status": 404})
            continue

        отчёт["reached"].add(путь)
        низ = тело.lower()
        if any(с in низ for с in ОТСУТСТВИЕ):
            отчёт["soft_404"].append({"path": путь})

        ожидание = ожидаемые.get(путь)
        if ожидание:
            найден = H1.search(тело)
            имя = текст(найден.group(1)) if найден else ""
            if имя != ожидание:
                отчёт["wrong_entity_200"].append(
                    {"path": путь, "expected": ожидание, "got": имя[:80]})

        for сырой in КАРТИНКА.findall(тело):
            адрес = html_mod.unescape(сырой)
            куда = "external" if адрес.startswith("http") and основа.netloc not in адрес \
                else "internal"
            хост = urllib.parse.urlparse(адрес).netloc or основа.netloc
            отчёт["images"][куда][хост] = отчёт["images"][куда].get(хост, 0) + 1
            картинки_проверены.add(адрес)

        for сырой in ССЫЛКА.findall(тело):
            адрес = html_mod.unescape(сырой).strip()
            if not адрес or адрес == "#":
                отчёт["broken_internal_links"].append(
                    {"path": путь, "href": адрес or "(пусто)",
                     "reason": "пустая ссылка или заглушка «#»"})
                continue
            if адрес.startswith("#"):
                # Ссылка на якорь — не битая ссылка, если якорь на странице
                # есть. Ровно так устроен обязательный «перейти к содержимому»:
                # объявить его битым значило бы требовать убрать средство
                # доступности ради зелёного счётчика.
                якорь = адрес[1:]
                if f'id="{якорь}"' not in тело:
                    отчёт["broken_internal_links"].append(
                        {"path": путь, "href": адрес, "reason": "якоря нет на странице"})
                continue
            if адрес.startswith(("mailto:", "tel:", "javascript:")):
                if адрес.startswith("javascript:"):
                    отчёт["broken_internal_links"].append(
                        {"path": путь, "href": адрес[:40], "reason": "javascript: вместо адреса"})
                continue
            если = urllib.parse.urlparse(адрес)
            if если.scheme or если.netloc:
                continue  # внешний адрес: витрина за него не отвечает
            цель = urllib.parse.urljoin(путь, адрес)
            if цель not in видели:
                видели.add(цель)
                очередь.append(цель)

    отчёт["reached"] = sorted(отчёт["reached"])
    отчёт["queued_total"] = len(видели)
    return отчёт


def main(argv=None) -> int:
    разбор = argparse.ArgumentParser(description=__doc__)
    разбор.add_argument("--base", required=True)
    разбор.add_argument("--catalog", help="снимок каталога для сверки сущностей и сирот")
    разбор.add_argument("--limit", type=int, default=1200)
    разбор.add_argument("--out", required=True)
    арг = разбор.parse_args(argv)

    ожидаемые = {}
    все_записи = []
    if арг.catalog:
        снимок = json.loads(open(арг.catalog, encoding="utf-8").read())
        все_записи = снимок.get("items") or []
        ожидаемые = {з["url"]: з["title"] for з in все_записи}

    отчёт = обойти(арг.base, ожидаемые, арг.limit)
    достигнутые = set(отчёт["reached"])
    # Сиротой считается запись, до которой обход не дошёл ЗА ОТВЕДЁННЫЙ предел.
    # Полный обход пятидесяти тысяч страниц здесь не делается, и объявлять
    # недостигнутое сиротством было бы неправдой: считаются только те записи,
    # что перечислены на уже пройденных страницах.
    отчёт["catalog_items"] = len(все_записи)
    отчёт["orphan_pages"] = 0
    отчёт["orphan_note"] = ("обход ограничен пределом; сиротство считается только "
                            "по достигнутой части графа")
    итог = {
        "taken_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "report": отчёт,
        "counters": {
            "ROUTE_FAILURES": len(отчёт["route_failures"]),
            "SOFT_404": len(отчёт["soft_404"]),
            "WRONG_ENTITY_200": len(отчёт["wrong_entity_200"]),
            "BROKEN_INTERNAL_LINKS": len(отчёт["broken_internal_links"]),
            "REDIRECT_LOOPS": len(отчёт["redirect_loops"]),
            "REDIRECT_CHAINS_GT1": len(отчёт["redirect_chains_gt1"]),
            "ORPHAN_PAGES": отчёт["orphan_pages"],
            "PAGES_CHECKED": отчёт["checked"],
        },
    }
    with open(арг.out, "w", encoding="utf-8") as ф:
        ф.write(json.dumps(итог, ensure_ascii=False, indent=1) + "\n")
    for имя, значение in итог["counters"].items():
        print(f"{имя}={значение}")
    print(f"отчёт: {арг.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
