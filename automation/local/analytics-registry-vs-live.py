#!/usr/bin/env python3
"""Поля состояния в реестре аналитики против ЖИВОЙ витрины.

Зачем. В реестре два поля описывают не настройку, а СОСТОЯНИЕ витрины:
`analytics_enabled` («разметка счётчика работает на страницах») и
`seo_indexing_enabled` («витрина открыта для индексации»). Меняют это
состояние ВЫКЛАДКИ, а поле обновляется только проверкой — и расходится.

Измерено 2026-10-15 20:10 (находку подняла линия `animedia.icu`): в обеих
рабочих копиях реестра `seo_indexing_enabled` равно `false` у ВСЕХ записей,
тогда как `animedia.icu` отдаёт `x-robots-tag: index, follow`, `robots.txt`
закрывает только служебные пути, а `/sitemap.xml` отвечает 200. И у десяти
домен `analytics_enabled` равно `false` при живом счётчике на страницах.

Поэтому правило: **состояние витрины берётся с витрины, а не из реестра.**
Реестр остаётся источником для того, что выкладками не меняется — номера
счётчиков и идентификаторы целей.

Инструмент только читает: одна страница и `robots.txt` на домен.

    python3 automation/local/analytics-registry-vs-live.py
    python3 automation/local/analytics-registry-vs-live.py --domain animedia.icu
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

КОРЕНЬ = Path(__file__).resolve().parents[2]
#: Копия, по которой работает служба сбора (её WorkingDirectory). Путь
#: называется явно: копий реестра несколько, и утверждение без имени копии
#: ничего не значит (MOD-40).
РЕЕСТР_СЛУЖБЫ = Path("/home/claude/wt-portable-site-cell-01/config/analytics.json")
РЕЕСТР_ВЕТКИ = КОРЕНЬ / "config" / "analytics.json"


def заголовки(домен: str) -> tuple[str, str]:
    г = subprocess.run(
        ["curl", "-sS", "-o", "/dev/null", "-D", "-", "--max-time", "30",
         f"https://{домен}/"], capture_output=True, text=True, timeout=60)
    вывод = г.stdout or ""
    код = ""
    м = re.search(r"HTTP/\S+\s+(\d{3})", вывод)
    if м:
        код = м.group(1)
    роботы = ""
    м2 = re.search(r"(?im)^x-robots-tag:\s*(.+)$", вывод)
    if м2:
        роботы = м2.group(1).strip()
    return код, роботы


def страница(домен: str) -> str:
    г = subprocess.run(["curl", "-sS", "--max-time", "30", f"https://{домен}/"],
                       capture_output=True, text=True, timeout=60)
    return г.stdout or ""


def robots(домен: str) -> str:
    г = subprocess.run(["curl", "-sS", "--max-time", "30",
                        f"https://{домен}/robots.txt"],
                       capture_output=True, text=True, timeout=60)
    return г.stdout or ""


def открыта_индексация(роботы: str, тело_robots: str) -> str | None:
    """Открыта ли витрина. `None` — не определилось, и это не «закрыта»."""
    низ = (роботы or "").lower()
    if "noindex" in низ:
        return "закрыта"
    if "index" in низ:
        return "открыта"
    if not тело_robots.strip():
        return None
    строки = [с.strip().lower() for с in тело_robots.splitlines()]
    if any(с == "disallow: /" for с in строки):
        return "закрыта"
    if any(с.startswith("allow:") or с.startswith("sitemap:") for с in строки):
        return "открыта"
    return None


def главное(аргв=None) -> int:
    р = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    р.add_argument("--domain", action="append", default=[])
    р.add_argument("--registry", type=Path, default=РЕЕСТР_СЛУЖБЫ,
                   help="какую КОПИЮ реестра сверять (по умолчанию — ту, "
                        "которую читает служба сбора)")
    опции = р.parse_args(аргв)

    путь = опции.registry if опции.registry.is_file() else РЕЕСТР_ВЕТКИ
    д = json.loads(путь.read_text(encoding="utf-8"))
    записи = {з["domain"]: з for з in (д.get("properties") or [])}
    домены = опции.domain or [
        имя for имя, з in записи.items()
        if з.get("counter_id") and з.get("counter_state") != "planned"]

    print(f"реестр: {путь} ({len(записи)} записей)")
    расхождений = 0
    for домен in sorted(домены):
        з = записи.get(домен)
        if з is None:
            print(f"{домен}: в этой копии реестра записи нет")
            continue
        код, роботы = заголовки(домен)
        если_тело = страница(домен)
        счётчик = str(з.get("counter_id") or "")
        разметка = bool(счётчик and счётчик in если_тело)
        состояние = открыта_индексация(роботы, robots(домен))
        беды = []
        if разметка != bool(з.get("analytics_enabled")):
            беды.append(f"analytics_enabled={з.get('analytics_enabled')} при "
                        f"разметке {'есть' if разметка else 'нет'}")
        if состояние is not None:
            объявлено = "открыта" if з.get("seo_indexing_enabled") else "закрыта"
            if состояние != объявлено:
                беды.append(f"seo_indexing_enabled={з.get('seo_indexing_enabled')} "
                            f"при живой витрине {состояние}")
        расхождений += 1 if беды else 0
        метка = "РАСХОЖДЕНИЕ" if беды else "сходится"
        print(f"{домен:24s} код {код or '—':>3} индексация "
              f"{состояние or 'не определилось':<16} {метка}")
        for б in беды:
            print(f"      {б}")

    print(f"\nсверено доменов: {len(домены)}; с расхождением: {расхождений}")
    print("состояние витрины берётся с ВИТРИНЫ: поля реестра меняют выкладки, "
          "а обновляет их только проверка")
    return 1 if расхождений else 0


if __name__ == "__main__":
    raise SystemExit(главное())
