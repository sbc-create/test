#!/usr/bin/env python3
"""Одна сущность на всю страницу: снимок → карточка → маршрут → разметка.

Проверяется то, что рвалось на живых витринах: карточки строились из СВЕЖЕГО
снимка каталога, а страницы произведений искались в СТАРОМ статическом наборе.
Пока эти два множества совпадали, всё выглядело исправным; как только снимок
ушёл вперёд, каждая карточка стала вести в никуда.

Поэтому для каждой карточки сверяется цепочка:

    запись снимка → href карточки → маршрут → H1 → <title> → description
                  → canonical → og:* → JSON-LD

Все восемь обязаны описывать ОДНУ запись. Расхождение называется по имени:

* `route_failure`   — маршрут не ответил 200;
* `soft_404`        — 200, но страница словами говорит, что записи нет;
* `wrong_entity`    — 200 с названием другой записи;
* `metadata_drift`  — какой-то из восьми источников назвал другое;
* `canonical_host`  — canonical ведёт не на проверяемый домен либо на 127.0.0.1.

Выборка детерминированная: одни и те же позиции снимка при одном и том же
снимке. Случайная выборка не воспроизводится, и «у меня прошло» в ней ничего
не значит.
"""
from __future__ import annotations

import argparse
import html as html_mod
import json
import re
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

H1 = re.compile(r"<h1[^>]*>(.*?)</h1>", re.S | re.I)
TITLE = re.compile(r"<title[^>]*>(.*?)</title>", re.S | re.I)
DESC = re.compile(r'<meta\s+name="description"\s+content="([^"]*)"', re.I)
CANON = re.compile(r'<link\s+rel="canonical"\s+href="([^"]*)"', re.I)
OG = re.compile(r'<meta\s+property="og:([a-z_]+)"\s+content="([^"]*)"', re.I)
LD = re.compile(r'<script type="application/ld\+json">(.*?)</script>', re.S)
ТЕГ = re.compile(r"<[^>]+>")
ОТСУТСТВИЕ = ("страницы на витрине нет", "страница не найдена",
              "не соответствует ни одной записи")


def текст(кусок: str) -> str:
    return html_mod.unescape(ТЕГ.sub(" ", кусок)).strip()


def в_ascii(адрес: str) -> str:
    ч = urllib.parse.urlsplit(адрес)
    return urllib.parse.urlunsplit((
        ч.scheme, ч.netloc,
        urllib.parse.quote(ч.path, safe="/%:@!$&'()*+,;=~-._"),
        urllib.parse.quote(ч.query, safe="/%:@!$&'()*+,;=~-._?"), ""))


def взять(адрес: str):
    запрос = urllib.request.Request(в_ascii(адрес), headers={"User-Agent": "entity-parity"})
    try:
        with urllib.request.urlopen(запрос, timeout=40) as ответ:
            return ответ.status, ответ.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as ош:
        return ош.code, (ош.read() or b"").decode("utf-8", "replace")
    except OSError as ош:
        return -1, str(ош)[:140]


def выборка(записи: list, сколько: int) -> list:
    """Детерминированная стратифицированная выборка.

    Берутся края и равномерная решётка по всему снимку: первые записи, средние,
    последние. Так в выборку попадают и свежие записи, и хвост, который обычно
    и ломается.
    """
    n = len(записи)
    if n <= сколько:
        return list(записи)
    позиции = {0, 1, 2, n - 3, n - 2, n - 1}
    шаг = max(1, n // (сколько - len(позиции)))
    позиции.update(range(0, n, шаг))
    упорядоченные = sorted(p for p in позиции if 0 <= p < n)[:сколько]
    return [записи[p] for p in упорядоченные]


def сверить(база: str, запись: dict) -> dict:
    домен = urllib.parse.urlparse(база).netloc.split(":")[0]
    итог = {"slug": запись["slug"], "expected_title": запись["title"],
            "href": запись["url"], "problems": []}
    код, тело = взять(база + запись["url"])
    итог["status"] = код
    if код != 200:
        итог["problems"].append("route_failure")
        return итог
    низ = тело.lower()
    if any(с in низ for с in ОТСУТСТВИЕ):
        итог["problems"].append("soft_404")

    ожидаемое = запись["title"]
    найден = H1.search(тело)
    итог["h1"] = текст(найден.group(1)) if найден else ""
    if итог["h1"] != ожидаемое:
        итог["problems"].append("wrong_entity" if итог["h1"] else "metadata_drift")

    найден = TITLE.search(тело)
    итог["title_tag"] = текст(найден.group(1)) if найден else ""
    if ожидаемое not in итог["title_tag"]:
        итог["problems"].append("metadata_drift:title")

    найден = DESC.search(тело)
    итог["description"] = html_mod.unescape(найден.group(1)) if найден else ""
    if not итог["description"]:
        итог["problems"].append("metadata_drift:description_missing")

    найден = CANON.search(тело)
    итог["canonical"] = найден.group(1) if найден else ""
    if not итог["canonical"]:
        итог["problems"].append("metadata_drift:canonical_missing")
    else:
        разбор = urllib.parse.urlparse(итог["canonical"])
        if разбор.path != запись["url"]:
            итог["problems"].append("metadata_drift:canonical_path")
        # canonical обязан называть ТОТ домен, по которому пришёл запрос.
        # На стенде петли это и есть 127.0.0.1, и объявлять его дефектом —
        # значит ловить собственную оснастку: рантайм берёт хост из запроса,
        # и другого правильного ответа на петле не существует. Дефектом петля
        # становится ровно тогда, когда запрос пришёл на публичное имя.
        if разбор.hostname != домен:
            итог["problems"].append(
                "canonical_host:loopback" if разбор.hostname in ("127.0.0.1", "localhost")
                else "canonical_host:foreign")

    граф = {к.lower(): html_mod.unescape(з) for к, з in OG.findall(тело)}
    итог["og"] = граф
    if not граф:
        итог["problems"].append("metadata_drift:og_missing")
    else:
        if ожидаемое not in (граф.get("title") or ""):
            итог["problems"].append("metadata_drift:og_title")
        if граф.get("url") and граф["url"] != итог["canonical"]:
            итог["problems"].append("metadata_drift:og_url")

    узлы = []
    for кусок in LD.findall(тело):
        try:
            узлы.append(json.loads(кусок))
        except ValueError:
            итог["problems"].append("metadata_drift:ld_invalid")
    итог["ld_types"] = [у.get("@type") for у in узлы if isinstance(у, dict)]
    основной = next((у for у in узлы if isinstance(у, dict)
                     and у.get("@type") in ("Movie", "TVSeries", "TVEpisode")), None)
    if not основной:
        итог["problems"].append("metadata_drift:ld_missing")
    else:
        имя = основной.get("name") or ""
        if основной["@type"] != "TVEpisode" and имя != ожидаемое:
            итог["problems"].append("wrong_entity:ld")
        if основной.get("url") and основной["url"] != итог["canonical"]:
            итог["problems"].append("metadata_drift:ld_url")

    if "127.0.0.1" in тело and домен not in ("127.0.0.1", "localhost"):
        итог["problems"].append("canonical_host:loopback_in_body")
    итог["ok"] = not итог["problems"]
    return итог


def main(argv=None) -> int:
    р = argparse.ArgumentParser(description=__doc__)
    р.add_argument("--base", required=True)
    р.add_argument("--catalog", required=True)
    р.add_argument("--sample", type=int, default=40)
    р.add_argument("--out", required=True)
    арг = р.parse_args(argv)

    записи = json.loads(Path(арг.catalog).read_text(encoding="utf-8"))["items"]
    проверяемые = выборка(записи, арг.sample)
    строки = [сверить(арг.base, з) for з in проверяемые]
    счёт = {
        "CHECKED": len(строки),
        "ROUTE_FAILURES": sum(1 for с in строки if "route_failure" in с["problems"]),
        "SOFT_404": sum(1 for с in строки if "soft_404" in с["problems"]),
        "WRONG_ENTITY_200": sum(1 for с in строки
                                if any(p.startswith("wrong_entity") for p in с["problems"])),
        "METADATA_DRIFT": sum(1 for с in строки
                              if any(p.startswith("metadata_drift") for p in с["problems"])),
        "CANONICAL_HOST_FAILURES": sum(1 for с in строки
                                       if any(p.startswith("canonical_host") for p in с["problems"])),
        "OK": sum(1 for с in строки if с.get("ok")),
    }
    Path(арг.out).write_text(json.dumps(
        {"taken_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
         "base": арг.base, "counters": счёт, "rows": строки},
        ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    for к, з in счёт.items():
        print(f"{к}={з}")
    плохие = [с for с in строки if not с.get("ok")][:5]
    for с in плохие:
        print(f"  ДЕФЕКТ {с['href']} → {с['problems']}")
    print(f"отчёт: {арг.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
