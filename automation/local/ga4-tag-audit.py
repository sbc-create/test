#!/usr/bin/env python3
"""Тег GA4 на живых витринах — различающая проба, а не взгляд в интерфейс (D203).

Для каждой витрины снимаются / и /catalog/:
* домен С ожидаемым ID (--expect домен=G-…): ровно один тег с этим ID, ровно один
  gtag config, ни одного явного page_view (его шлёт config — явный задвоил бы);
* домен БЕЗ ожидаемого ID: тега GA4 нет вовсе (правило «нет ID — нет тега»);
* Метрика на месте и не задвоена: признак счётчика ровно один;
* смешение: один ID на двух доменах — отказ на входе и нарушение на живых страницах;
* число для веса страницы: байты и время ответа — сравнивать до и после.
Непатченная витрина без --expect даёт «ок» по отсутствию тега и НАРУШЕНИЕ, если
для неё ожидание задано, — так проба доказуемо различает. Не измерено — отдельно.

    python3 automation/local/ga4-tag-audit.py [--expect домен=G-ID …] [домен …]
"""
from __future__ import annotations

import argparse
import http.client
import re
import sys
import time

СЕТЬ = ("lordserial33.biz", "lordfilm47.space", "1lordserials1.online", "lordserials22.info",
        "zonafilm.space", "zonafilm12.site", "zonafilm.cc", "an1mego.site", "animeg0.site",
        "an1meg0.site", "animedia.icu", "animedia.space")
ПУТИ = ("/", "/catalog/")
#: Та же форма, что у слоя (seo_layer._ФОРМАТ_GA4): иная тег не получает.
ФОРМА_ID = re.compile(r"G-[A-Z0-9]{4,16}")


def снять(хост: str, путь: str) -> dict:
    начало = time.monotonic()
    с = http.client.HTTPSConnection(хост, timeout=60)
    с.request("GET", путь, headers={"User-Agent": "seo-operator-ga4-audit/1"})
    r = с.getresponse()
    тело = r.read(5_000_000).decode("utf-8", "replace")
    return {"код": r.status, "build": r.getheader("x-site-factory-build-id"), "байт": len(тело),
            "сек": round(time.monotonic() - начало, 2), **разобрать(тело)}


def разобрать(тело: str) -> dict:
    return {
        "ga4_id": re.findall(r'data-ga4-id="([^"]*)"', тело),
        "config": len(re.findall(r"gtag\(\s*['\"]config['\"]", тело)),
        "page_view": len(re.findall(r"['\"]event['\"]\s*,\s*['\"]page_view['\"]", тело)),
        "gtm": тело.count("googletagmanager.com/gtag/js"),
        "метрика": тело.count("data-metrika-counter="),
    }


def беды_пробы(с: dict, ждём: str | None) -> list[str]:
    б = []
    if с["код"] != 200:
        б.append(f"код {с['код']}")
    if с["метрика"] != 1:
        б.append(f"Метрика: признаков {с['метрика']} (ждём 1)")
    if с["page_view"]:
        б.append(f"явный page_view: {с['page_view']}")
    if ждём is not None and not ФОРМА_ID.fullmatch(ждём.strip()):
        # ID задан, но не проходит форму: слой тега не поставит. Проба это
        # называет (BLOCKED_INPUT), а не молчит, и проверяет, что тега нет.
        б.append(f"BLOCKED_INPUT: ID {ждём!r} не проходит форму G-[A-Z0-9]{{4,16}} — тега быть не должно")
        ждём = None
    if ждём is None:
        if с["ga4_id"] or с["config"] or с["gtm"]:
            б.append(f"тег GA4 без ID в site.json: {с['ga4_id']} config={с['config']} gtm={с['gtm']}")
    else:
        if len(с["ga4_id"]) != 1:
            б.append(f"метка data-ga4-id: {len(с['ga4_id'])} шт (ждём 1)")
        if с["ga4_id"] != [ждём]:
            б.append(f"ID {с['ga4_id']} (ждём [{ждём}])")
        if с["config"] != 1 or с["gtm"] != 1:
            б.append(f"config={с['config']} gtm={с['gtm']} (ждём по 1)")
    return б


def смешение(ожидания: dict[str, str]) -> dict[str, list[str]]:
    """ID, ожидаемые у двух и более доменов: у каждого сайта свой ресурс."""
    по_id: dict[str, list[str]] = {}
    for домен, и in ожидания.items():
        по_id.setdefault(и.strip(), []).append(домен)
    return {и: sorted(д) for и, д in по_id.items() if len(д) > 1}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--expect", action="append", default=[], metavar="домен=G-ID")
    ap.add_argument("hosts", nargs="*")
    a = ap.parse_args(argv)
    ожидания = dict(e.split("=", 1) for e in a.expect)
    хосты = a.hosts or list(СЕТЬ)
    if any(х not in СЕТЬ for х in [*хосты, *ожидания]):
        print("домены вне перечня")
        return 2
    плохо = 0
    повтор = смешение(ожидания)
    if повтор:
        print("ОТКАЗ — один ID ожидается у нескольких доменов (смешение данных):", повтор)
        return 2
    увидено: dict[str, set[str]] = {}
    for х in хосты:
        for путь in ПУТИ:
            try:
                с = снять(х, путь)
            except OSError as exc:
                print(f"НЕ ИЗМЕРЕНО {х}{путь}: {exc}")
                плохо += 1
                continue
            б = беды_пробы(с, ожидания.get(х))
            for и in с["ga4_id"]:
                увидено.setdefault(и, set()).add(х)
            плохо += bool(б)
            print(f"{'ок' if not б else 'НАРУШЕНИЕ':10} {х + путь:32} build {с['build']} ga4={с['ga4_id']} "
                  f"config={с['config']} метрика={с['метрика']} {с['байт']} Б {с['сек']} с", flush=True)
            for стр in б:
                print("    ·", стр)
    for и, домены in sorted(увидено.items()):
        if len(домены) > 1:
            print(f"НАРУШЕНИЕ  смешение: {и} стоит на {sorted(домены)}")
            плохо += 1
    print("ИТОГ", "чисто" if not плохо else f"нарушений/не измерено: {плохо}")
    return 1 if плохо else 0


if __name__ == "__main__":
    sys.exit(main())
