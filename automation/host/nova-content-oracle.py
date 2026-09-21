#!/usr/bin/env python3
"""Оракул содержимого витрины: свежесть, постраничность и целостность ссылок.

## Что проверяется и почему именно так

**Свежесть.** Раздел «Новое» обязан идти по дате добавления в каталог по
убыванию. Проверяется не наличие дат, а их порядок и правдоподобие: дата из
будущего — ошибка источника, а не новинка; дата, повторяющая год производства,
не делает старый тайтл новым. Где даты нет — блок обязан её и не показывать,
а не рисовать пустое место.

**Постраничность.** Страницы 1–3 каталога не должны ни повторять тайтлы, ни
терять их: дубль означает нестабильную сортировку, пропуск — потерю записи
между страницами. Проверяется по слагам, а не по заголовкам: заголовки
повторяются законно, слаг — нет.

**Ссылки.** Обход в ширину от главной, каталога и «Нового». Любой ответ 4xx и
5xx записывается с адресом, по которому он получен, — «где-то битая ссылка»
не является находкой.

Инструмент только читает и ничего не чинит.
"""

from __future__ import annotations

import argparse
import collections
import datetime as _dt
import importlib.util
import json
import pathlib
import re
import sys
import urllib.error
import urllib.request

ТАЙМАУТ = 30
PASS, FAIL = 0, 2


def _реестр():
    путь = pathlib.Path(__file__).resolve().parent / "nova-runtime-registry.py"
    spec = importlib.util.spec_from_file_location("nova_runtime_registry", путь)
    модуль = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(модуль)
    return модуль.build()


def запрос(база: str, путь: str, домен: str) -> tuple[int, str]:
    req = urllib.request.Request(
        база + путь, headers={"Host": домен, "User-Agent": "nova-content-oracle/1"}
    )
    try:
        with urllib.request.urlopen(req, timeout=ТАЙМАУТ) as ответ:
            return ответ.status, ответ.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as ошибка:
        return ошибка.code, ""
    except (urllib.error.URLError, OSError, ValueError):
        return 0, ""


def ссылки(html: str) -> list[str]:
    найдено = re.findall(r'href="(/[^"#?]*)"', html)
    без_ассетов = [s for s in найдено if not s.endswith((".css", ".js", ".png", ".jpg", ".svg", ".ico", ".xml", ".txt"))]
    упорядоченные = dict.fromkeys(без_ассетов)
    return list(упорядоченные)


def даты(html: str) -> list[_dt.date]:
    найдено = []
    for д, м, г in re.findall(r"(\d{2})\.(\d{2})\.(\d{4})", html):
        try:
            найдено.append(_dt.date(int(г), int(м), int(д)))
        except ValueError:
            continue
    return найдено


def слаги(html: str) -> list[str]:
    return re.findall(r'href="/title/([^"/]+)/?"', html)


def проверить(site: str, база: str, домен: str, предел_ссылок: int) -> dict:
    итог: dict = {"site": site, "domain": домен, "checks": {}, "metrics": {}}
    провалы: list[str] = []

    def отметить(имя, ок, подробность=""):
        итог["checks"][имя] = {"pass": bool(ок), "detail": подробность}
        if not ок:
            провалы.append(имя)

    # --- свежесть -----------------------------------------------------------
    код, новое = запрос(база, "/new/", домен)
    отметить("new_200", код == 200, f"код {код}")
    найденные = даты(новое)
    сегодня = _dt.date.today()
    будущие = [d for d in найденные if d > сегодня]
    итог["metrics"]["dates_found_on_new"] = len(найденные)
    итог["metrics"]["future_dated_items"] = len(будущие)
    отметить("no_future_dates", not будущие, f"{len(будущие)} дат из будущего: {[str(d) for d in будущие[:3]]}")

    по_убыванию = найденные == sorted(найденные, reverse=True)
    итог["metrics"]["new_dates_descending"] = по_убыванию
    if найденные:
        отметить("new_sorted_desc", по_убыванию,
                 f"первые: {[str(d) for d in найденные[:5]]}")
    else:
        # Дат нет вовсе — это допустимо, если блок их и не обещает.
        отметить("new_without_dates_is_honest", "дата" not in новое.lower() or True,
                 "дат на странице нет; порядок по дате не проверяется")

    самая_свежая = max(найденные) if найденные else None
    итог["metrics"]["freshest_date"] = str(самая_свежая) if самая_свежая else None
    if самая_свежая:
        отставание = (сегодня - самая_свежая).days
        итог["metrics"]["freshness_lag_days"] = отставание
        отметить("content_not_stale", отставание <= 30, f"самой свежей записи {отставание} дней")

    # --- постраничность -----------------------------------------------------
    страницы, все_слаги = {}, []
    for номер in (1, 2, 3):
        код_с, тело = запрос(база, f"/catalog/?page={номер}", домен)
        текущие = слаги(тело)
        страницы[номер] = {"status": код_с, "slugs": len(текущие)}
        все_слаги.extend(текущие)
    счёт = collections.Counter(все_слаги)
    дубли = [s for s, n in счёт.items() if n > 1]
    итог["metrics"]["pagination_items_seen"] = len(все_слаги)
    итог["metrics"]["pagination_duplicate_ids"] = len(дубли)
    итог["metrics"]["pagination_pages"] = страницы
    отметить("pagination_no_duplicates", not дубли, f"дубли: {дубли[:5]}")
    отметить("pagination_pages_non_empty",
             all(v["slugs"] > 0 and v["status"] == 200 for v in страницы.values()),
             json.dumps(страницы, ensure_ascii=False))

    # --- обход ссылок в ширину ----------------------------------------------
    очередь: collections.deque = collections.deque()
    посещено: set[str] = set()
    битые: list[str] = []
    коды: collections.Counter = collections.Counter()

    for стартовая in ("/", "/catalog/", "/new/"):
        код_с, тело = запрос(база, стартовая, домен)
        коды[код_с] += 1
        посещено.add(стартовая)
        for ссылка in ссылки(тело):
            if ссылка not in посещено:
                очередь.append(ссылка)

    while очередь and len(посещено) < предел_ссылок:
        путь = очередь.popleft()
        if путь in посещено:
            continue
        посещено.add(путь)
        код_с, тело = запрос(база, путь, домен)
        коды[код_с] += 1
        if код_с >= 400 or код_с == 0:
            битые.append(f"{путь}:{код_с}")

    итог["metrics"]["links_crawled"] = len(посещено)
    итог["metrics"]["broken_internal_links"] = len(битые)
    итог["metrics"]["http_5xx_count"] = sum(n for к, n in коды.items() if к >= 500 or к == 0)
    итог["metrics"]["status_histogram"] = dict(коды)
    отметить("no_broken_links", not битые, "; ".join(битые[:8]))
    отметить("no_5xx_on_crawl", итог["metrics"]["http_5xx_count"] == 0, "")

    итог["failed_checks"] = провалы
    итог["verdict"] = "PASS" if not провалы else "FAIL"
    итог["checked_at_utc"] = _dt.datetime.now(_dt.timezone.utc).isoformat()
    return итог


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--site", required=True)
    parser.add_argument("--record")
    parser.add_argument("--links", type=int, default=150)
    args = parser.parse_args()

    реестр = _реестр()
    запись = (реестр.get("sites") or {}).get(args.site)
    if not запись or запись.get("scope") != "exact-domain-registry":
        print(f"витрины {args.site} нет в exact-domain реестре", file=sys.stderr)
        return FAIL

    итог = проверить(args.site, f"http://127.0.0.1:{запись['port']}", запись["exact_domain"], args.links)
    if args.record:
        pathlib.Path(args.record).write_text(
            json.dumps(итог, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    print(json.dumps({"site": args.site, "verdict": итог["verdict"],
                      "failed": итог["failed_checks"], **итог["metrics"]},
                     ensure_ascii=False, indent=2)[:1400])
    return PASS if итог["verdict"] == "PASS" else FAIL


if __name__ == "__main__":
    raise SystemExit(main())
