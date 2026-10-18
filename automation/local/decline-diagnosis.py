#!/usr/bin/env python3
"""Почему домен просел: цепочка от обнаружения страницы до соответствия ожиданию.

Четыре домена потеряли от 26 до 49 визитов за неделю, а у двух поисковых
визитов ноль. Одинакового ответа у них быть не должно, поэтому проверяется
цепочка, и по каждому звену печатается ИЗМЕРЕННЫЙ факт, а не общий вывод:

  доступность      код и время главной, кода 5xx/4xx быть не должно;
  обнаружение      robots.txt: не закрыт ли обход, названа ли карта;
  карта            доступна ли, сколько в ней адресов, отвечают ли выборочные;
  индексация       X-Robots-Tag и meta robots;
  canonical        ссылается ли главная на себя, нет ли чужого домена;
  внутренние       сколько ссылок на свои разделы и произведения с главной;
  посадочные       какие адреса давали входы по Метрике (из снимка),
                   и отвечают ли они сейчас.

Инструмент ничего не исправляет и ни к чему не обращается, кроме самого домена
и уже собранных снимков.

    python3 automation/local/decline-diagnosis.py lordfilm47.space animeg0.site
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

КОРЕНЬ = Path(__file__).resolve().parents[2]
ТРАФИК = КОРЕНЬ / "var" / "seo" / "traffic-wow.json"


def взять(url: str, таймаут: int = 45) -> tuple[str, str, float]:
    п = subprocess.run(
        ["curl", "-sS", "--max-time", str(таймаут), "-w",
         "\n@@%{http_code}@@%{time_total}", url],
        capture_output=True, text=True)
    тело = п.stdout or ""
    м = re.search(r"\n@@(\d+)@@([\d.]+)$", тело)
    if not м:
        return тело, "0", -1.0
    return тело[:м.start()], м.group(1), float(м.group(2))


def заголовки(url: str) -> dict[str, list[str]]:
    п = subprocess.run(["curl", "-sSI", "--max-time", "30", url],
                       capture_output=True, text=True)
    итог: dict[str, list[str]] = {}
    for строка in (п.stdout or "").splitlines():
        к, _, з = строка.partition(":")
        if з:
            итог.setdefault(к.strip().lower(), []).append(з.strip())
    return итог


def посадочные_из_снимка(домен: str) -> dict[str, float]:
    if not ТРАФИК.is_file():
        return {}
    j = json.loads(ТРАФИК.read_text(encoding="utf-8"))
    for с in j.get("строки") or []:
        if с["домен"] == домен:
            return с.get("посадочные") or {}
    return {}


def по_домену(домен: str) -> None:
    print(f"\n=== {домен}")
    тело, код, сек = взять(f"https://{домен}/")
    шапка = заголовки(f"https://{домен}/")
    print(f"  доступность: код {код}, {сек:.2f} с, байт {len(тело)}")
    if код != "200":
        print("  дальше не иду: главная не отвечает 200")
        return

    robots, код_r, _ = взять(f"https://{домен}/robots.txt")
    закрыт = bool(re.search(r"(?mi)^\s*Disallow:\s*/\s*$", robots))
    карта = re.findall(r"(?mi)^\s*Sitemap:\s*(\S+)", robots)
    print(f"  robots.txt: код {код_r}, обход закрыт целиком: {закрыт}, "
          f"карт названо {len(карта)}")

    адресов = 0
    частей = 0
    if карта:
        тело_к, код_к, _ = взять(карта[0])
        частей = len(re.findall(r"<sitemap>", тело_к))
        адресов = len(re.findall(r"<loc>", тело_к))
        print(f"  карта {карта[0]}: код {код_к}, частей {частей}, "
              f"элементов <loc> {адресов}")
        if частей:
            первая = re.search(r"<sitemap>.*?<loc>([^<]+)</loc>", тело_к, re.S)
            if первая:
                тело_ч, код_ч, _ = взять(первая.group(1))
                адресов_ч = len(re.findall(r"<loc>", тело_ч))
                print(f"    первая часть: код {код_ч}, адресов {адресов_ч}")

    мета = re.search(r'<meta[^>]+name="robots"[^>]+content="([^"]*)"', тело, re.I)
    print(f"  индексация: X-Robots-Tag {шапка.get('x-robots-tag') or '—'}, "
          f"meta robots {мета.group(1) if мета else '—'}")

    канон = re.search(r'<link[^>]+rel="canonical"[^>]+href="([^"]+)"', тело, re.I)
    свой = bool(канон and домен in канон.group(1))
    print(f"  canonical: {канон.group(1) if канон else '—'} "
          f"({'на себя' if свой else 'ЧУЖОЙ или нет'})")

    разделы = set(re.findall(r'href="(/[a-z0-9_-]+/)"', тело))
    тайтлы = len(set(re.findall(r'href="/title/[^"]+"', тело)))
    print(f"  внутренние ссылки с главной: разделов {len(разделы)}, "
          f"произведений {тайтлы}")

    пос = посадочные_из_снимка(домен)
    if пос:
        верх = sorted(пос.items(), key=lambda п: -п[1])[:5]
        print(f"  посадочные по Метрике (входов за неделю):")
        for адрес, входов in верх:
            _, код_п, сек_п = взять(f"https://{домен}{адрес}")
            метка = "" if код_п == "200" else "  ← НЕ 200"
            print(f"    {входов:5.0f}  {адрес[:52]:52} {код_п} "
                  f"{сек_п:.2f} с{метка}")
    else:
        print("  посадочные: в снимке нет данных")


def главная(аргв: list[str]) -> int:
    домены = аргв or ["lordfilm47.space", "animeg0.site", "animedia.space",
                      "an1mego.site", "1lordserials1.online"]
    for д in домены:
        по_домену(д)
    return 0


if __name__ == "__main__":
    sys.exit(главная(sys.argv[1:]))
