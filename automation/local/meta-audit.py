#!/usr/bin/env python3
"""Title, description, H1, canonical на страницах из карты сайта. Только чтение.

Для каждой витрины из каждой части sitemap берутся N адресов, равномерно по части
(детерминированно, без случайности — повтор сравним с прошлым), и по каждому
(SEO_KNOWLEDGE_PACK §4 REQ-SEO-META):
* код 200; ровно один <title>, ровно один meta description, ровно один <h1>;
* title, description и h1 не пусты; description не повторяет title;
* canonical ровно один и совпадает с адресом из карты;
* дубли title и description между разными адресами выборки.
Длина description нарушением НЕ считается: по §4 п.3 жёсткий лимит символов не
критерий; печатается справочно для чтения человеком.
Не измерено — отдельно, не успех. Запросы последовательные.

    python3 automation/local/meta-audit.py [--per-part N] домен […]
"""
from __future__ import annotations

import argparse
import html
import http.client
import re
import sys
import urllib.parse
from collections import defaultdict

СЕТЬ = ("lordserial33.biz", "lordfilm47.space", "1lordserials1.online", "lordserials22.info",
        "zonafilm.space", "zonafilm12.site", "zonafilm.cc", "an1mego.site", "animeg0.site",
        "an1meg0.site", "animedia.icu", "animedia.space")
UA = {"User-Agent": "seo-operator-meta-audit/1"}


def получить(хост: str, путь: str) -> tuple[int, str]:
    с = http.client.HTTPSConnection(хост, timeout=60)
    с.request("GET", путь, headers=UA)
    r = с.getresponse()
    return r.status, r.read(5_000_000).decode("utf-8", "replace")


def адреса(хост: str, на_часть: int) -> list[str]:
    код, карта = получить(хост, "/sitemap.xml")
    if код != 200:
        raise OSError(f"sitemap.xml {код}")
    части = re.findall(r"<sitemap>\s*<loc>([^<]+)</loc>", карта)
    if not части:
        return re.findall(r"<loc>([^<]+)</loc>", карта)[:на_часть]
    итог = []
    for ч in части:
        п = urllib.parse.urlsplit(html.unescape(ч.strip()))
        if п.hostname != хост:
            continue
        к, т = получить(хост, п.path)
        if к == 200:
            все = [html.unescape(x.strip()) for x in re.findall(r"<loc>([^<]+)</loc>", т)]
            шаг = max(1, len(все) // на_часть)
            итог += все[::шаг][:на_часть]
    return итог


def разобрать(тело: str) -> dict:
    голова = тело.split("</head>", 1)[0]
    чисто = lambda s: re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", "", s))).strip()  # noqa: E731
    return {
        "title": [чисто(x) for x in re.findall(r"<title[^>]*>(.*?)</title>", голова, re.S)],
        "desc": [html.unescape(x).strip() for x in
                 re.findall(r'<meta\s+name="description"\s+content="([^"]*)"', голова)],
        "h1": [чисто(x) for x in re.findall(r"<h1[^>]*>(.*?)</h1>", тело, re.S)],
        "canon": [html.unescape(x) for x in re.findall(r'<link rel="canonical" href="([^"]+)"', голова)],
    }


def беды(адрес: str, код: int, р: dict) -> list[str]:
    if код != 200:
        return [f"код {код}"]
    б = []
    for поле, имя in (("title", "title"), ("desc", "description"), ("h1", "h1"), ("canon", "canonical")):
        if len(р[поле]) != 1:
            б.append(f"{имя}: {len(р[поле])} шт")
    if р["title"] and not р["title"][0]:
        б.append("title пуст")
    if р["desc"] and not р["desc"][0]:
        б.append("description пуст")
    if р["desc"] and р["title"] and р["desc"][0] == р["title"][0]:
        б.append("description повторяет title")
    if р["h1"] and not р["h1"][0]:
        б.append("h1 пуст")
    if р["canon"] and р["canon"][0] != адрес:
        б.append(f"canonical {р['canon'][0]} ≠ адрес карты")
    return б


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--per-part", type=int, default=3)
    ap.add_argument("hosts", nargs="*")
    a = ap.parse_args(argv)
    хосты = a.hosts or list(СЕТЬ)
    if any(х not in СЕТЬ for х in хосты):
        print("домены вне перечня")
        return 2
    всего_бед = 0
    for х in хосты:
        try:
            список = адреса(х, a.per_part)
        except OSError as exc:
            print(f"НЕ ИЗМЕРЕНО {х}: {exc}")
            всего_бед += 1
            continue
        титулы, описания = defaultdict(list), defaultdict(list)
        плохих = 0
        for адрес in список:
            п = urllib.parse.urlsplit(адрес)
            try:
                код, тело = получить(х, п.path + (f"?{п.query}" if п.query else ""))
            except OSError as exc:
                print(f"  НЕ ИЗМЕРЕНО {адрес}: {exc}")
                плохих += 1
                continue
            р = разобрать(тело)
            б = беды(адрес, код, р)
            if р["title"]:
                титулы[р["title"][0]].append(адрес)
            if р["desc"]:
                описания[р["desc"][0]].append(адрес)
            if б:
                плохих += 1
                print(f"  НАРУШЕНИЕ {адрес}: {'; '.join(б)}")
        for имя, словарь in (("title", титулы), ("description", описания)):
            for текст, где in словарь.items():
                if len(где) > 1:
                    плохих += 1
                    print(f"  ДУБЛЬ {имя} «{текст[:80]}» × {len(где)}: {где[:4]}")
        всего_бед += плохих
        print(f"{'ок' if not плохих else 'НАРУШЕНИЯ':10} {х:22} адресов {len(список)}, с бедами {плохих}", flush=True)
    print("ИТОГ", "чисто" if not всего_бед else f"нарушений/не измерено: {всего_бед}")
    return 1 if всего_бед else 0


if __name__ == "__main__":
    sys.exit(main())
