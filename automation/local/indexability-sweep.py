#!/usr/bin/env python3
"""Доступны ли страницы поисковику: первый вопрос у домена с 2 визитами в сутки.

Зачем именно это и именно сейчас. Измерение разрыва до цели показало, что
действующие Lords и Zona держат 2–3 визита в сутки. На таком уровне
редакционная отделка текста не решает ничего: сначала надо знать, может ли
страница вообще попасть в индекс. Проверяется по каждому домену:

  код главной        отвечает ли сайт вообще
  X-Robots-Tag       запрет на уровне края (он умеет только закрывать)
  meta robots        что вычислил рантайм
  canonical          на себя ли ссылается главная
  robots.txt         закрыт ли обход целиком, назван ли sitemap
  sitemap.xml        есть ли карта и сколько в ней частей
  адресов в части    сколько страниц предъявлено поиску
  выборка из карты   отвечают ли сами страницы 200

Что инструмент НЕ делает: не судит о попадании в индекс. Индексация
измеряется Вебмастером, доступ к которому закрыт (B023), и подменять её
доступностью страницы нельзя — это разные утверждения.

    python3 automation/local/indexability-sweep.py
    python3 automation/local/indexability-sweep.py --domain lordfilm47.space
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

КОРЕНЬ = Path(__file__).resolve().parents[2]
РЕЕСТР = КОРЕНЬ / "config" / "site-cells.json"
ОБРАЗЦОВ = 3


def достать(url: str, таймаут: int = 30) -> tuple[int, str, str]:
    г = subprocess.run(
        ["curl", "-sSL", "-D", "-", "-o", "-", "-w", "\n%{http_code}",
         "--max-time", str(таймаут), url],
        capture_output=True, text=True, timeout=таймаут + 20)
    весь = г.stdout or ""
    части = весь.rsplit("\n", 1)
    код = int(части[-1]) if части[-1].strip().isdigit() else 0
    тело = части[0]
    # Заголовки идут до первой пустой строки.
    голова, _, остальное = тело.partition("\r\n\r\n")
    if not остальное:
        голова, _, остальное = тело.partition("\n\n")
    return код, голова, остальное


def код(url: str, таймаут: int = 25) -> int:
    г = subprocess.run(
        ["curl", "-sSL", "-o", "/dev/null", "-w", "%{http_code}",
         "--max-time", str(таймаут), url],
        capture_output=True, text=True, timeout=таймаут + 15)
    т = (г.stdout or "").strip()
    return int(т) if т.isdigit() else 0


def по_домену(домен: str) -> dict:
    итог: dict = {"домен": домен}
    к, голова, тело = достать(f"https://{домен}/")
    итог["код"] = к
    м = re.search(r"(?im)^x-robots-tag:\s*(.+)$", голова)
    итог["x_robots"] = м.group(1).strip() if м else ""
    м2 = re.search(r'(?is)<meta[^>]+name=["\']robots["\'][^>]+content=["\']([^"\']+)',
                   тело)
    итог["meta_robots"] = м2.group(1).strip() if м2 else ""
    м3 = re.search(r'(?is)<link[^>]+rel=["\']canonical["\'][^>]+href=["\']([^"\']+)',
                   тело)
    итог["canonical"] = м3.group(1).strip() if м3 else ""
    итог["canonical_свой"] = домен in итог["canonical"]

    _, _, robots = достать(f"https://{домен}/robots.txt", 20)
    строки = [с.strip().lower() for с in robots.splitlines()]
    итог["robots_запрет_всего"] = any(с == "disallow: /" for с in строки)
    итог["robots_sitemap"] = any(с.startswith("sitemap:") for с in строки)

    _, _, индекс = достать(f"https://{домен}/sitemap.xml", 40)
    итог["частей_карты"] = индекс.count("<sitemap>")
    адреса_частей = re.findall(r"<loc>([^<]+)</loc>", индекс)
    итог["карта_есть"] = bool(адреса_частей)
    образцы: list[str] = []
    if итог["частей_карты"] and адреса_частей:
        _, _, часть = достать(адреса_частей[0], 60)
        адреса = re.findall(r"<loc>([^<]+)</loc>", часть)
        итог["адресов_в_части"] = len(адреса)
        образцы = адреса[:ОБРАЗЦОВ]
    else:
        адреса = адреса_частей
        итог["адресов_в_части"] = len(адреса)
        образцы = адреса[:ОБРАЗЦОВ]
    итог["образцы"] = [(у, код(у)) for у in образцы]
    итог["образцы_200"] = sum(1 for _, к2 in итог["образцы"] if к2 == 200)
    return итог


def главное(аргв=None) -> int:
    р = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    р.add_argument("--domain", action="append", default=[])
    опции = р.parse_args(аргв)

    домены = опции.domain
    if not домены:
        д = json.loads(РЕЕСТР.read_text(encoding="utf-8"))
        домены = sorted({я["domain"] for я in д["cells"]
                         if я.get("status") == "live"
                         and not (я.get("promotion") or {}).get("excluded")})
    print(f"доменов: {len(домены)}\n")
    with ThreadPoolExecutor(4) as ex:
        итоги = list(ex.map(по_домену, домены))

    print(f"{'домен':24s} {'код':>4s} {'x-robots':14s} {'meta':14s} "
          f"{'canon':6s} {'robots':14s} {'частей':>7s} {'адресов':>8s} {'200/3':>6s}")
    беды = []
    for и in sorted(итоги, key=lambda x: x["домен"]):
        robots = ("ЗАПРЕТ ВСЕГО" if и["robots_запрет_всего"]
                  else ("карта названа" if и["robots_sitemap"] else "без карты"))
        print(f"{и['домен']:24s} {и['код']:4d} {и['x_robots'][:14]:14s} "
              f"{и['meta_robots'][:14]:14s} "
              f"{'свой' if и['canonical_свой'] else 'ЧУЖОЙ':6s} {robots:14s} "
              f"{и['частей_карты']:7d} {и['адресов_в_части']:8d} "
              f"{и['образцы_200']:3d}/{len(и['образцы'])}")
        if и["код"] != 200:
            беды.append(f"{и['домен']}: главная отвечает {и['код']}")
        if "noindex" in (и["x_robots"] + и["meta_robots"]).lower():
            беды.append(f"{и['домен']}: запрет индексации в сигналах")
        if и["robots_запрет_всего"]:
            беды.append(f"{и['домен']}: robots.txt запрещает обход целиком")
        if not и["карта_есть"]:
            беды.append(f"{и['домен']}: карты сайта нет")
        if not и["robots_sitemap"]:
            беды.append(f"{и['домен']}: карта не названа в robots.txt")
        if not и["canonical_свой"]:
            беды.append(f"{и['домен']}: canonical ведёт не на свой домен")
        if и["образцы"] and и["образцы_200"] < len(и["образцы"]):
            плохие = [у for у, к2 in и["образцы"] if к2 != 200]
            беды.append(f"{и['домен']}: страницы из карты не 200: {плохие[:2]}")

    print(f"\nнаходок: {len(беды)}")
    for б in беды:
        print(f"   {б}")
    print("\nиндексация Вебмастером здесь НЕ измеряется: доступ к нему закрыт "
          "(B023), и доступность страницы попаданием в индекс не является")
    return 1 if беды else 0


if __name__ == "__main__":
    raise SystemExit(главное())
