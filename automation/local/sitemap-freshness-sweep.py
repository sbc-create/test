#!/usr/bin/env python3
"""Обновляется ли карта сайта ВООБЩЕ — по публичной выдаче, сравнением с сетью.

    python3 automation/local/sitemap-freshness-sweep.py              # вся сеть
    python3 automation/local/sitemap-freshness-sweep.py lordfilm47.space …
    python3 automation/local/sitemap-freshness-sweep.py --today 2026-10-18

Зачем отдельный инструмент, когда даты в карте уже проверяет
`sitemap-lastmod-check.py`: тот отвечает на вопрос «правильные ли даты в
карте» — границы, массовая подстановка, устойчивость при перезапуске. Он
полностью исправен на карте, которая НЕ ОБНОВЛЯЕТСЯ: даты в ней законные,
просто все трёхдневной давности. Вопрос здесь другой — «сдвинулась ли карта
вслед за каталогом», и измеряется он сравнением с остальной сетью, потому что
абсолютное «сегодня» не является требованием: у части семейств карта
собирается раз в сутки и день отставания нормален.

Измерено 2026-10-18 (повод для инструмента): у одиннадцати витрин сети самый
свежий `lastmod` сегодняшний или вчерашний, а у 1lordserials1.online —
2026-10-15, при том что каталог за эти сутки вырос с 65 749 до 66 159 позиций
(журнал выпусков `publish-reports`). Файлы карты в её `<data>/sitemap/`
записаны ровно в момент запуска процесса (2026-10-15 20:25) и с тех пор не
менялись. Сборщик карты перезаписывает её при смене поколения
`(данные.revision, len(данные.items))` — значит у этой витрины поколение не
менялось трое суток.

Что считается находкой: отставание на двое суток и больше И при этом хотя бы
одна витрина сети моложе. Второе условие обязательно — без него общая задержка
доставки по всей сети выглядела бы как дефект отдельной витрины, а это разные
причины и разные владельцы.

Только чтение публичной выдачи своих же витрин. Закрытый от индексации домен
не является находкой: у него карты и не должно быть.
"""
from __future__ import annotations

import argparse
import datetime as dt
import re
import subprocess
import sys
import tempfile
from pathlib import Path

#: Домены сети с открытой индексацией. Перечень не расширяется по инициативе
#: инструмента: домен, которого здесь нет, называется в аргументах.
СЕТЬ = (
    "lordfilm47.space", "lordserial33.biz", "1lordserials1.online",
    "lordserials22.info", "zonafilm.space", "zonafilm.cc", "zonafilm12.site",
    "animedia.icu", "animedia.space", "an1mego.site", "animeg0.site",
    "an1meg0.site",
)

#: Сколько суток отставания считается находкой. Одни сутки — обычный шаг
#: суточной доставки, и находкой не являются.
ПОРОГ_СУТОК = 2


def достать(адрес: str, цель: Path, таймаут: int) -> bool:
    г = subprocess.run(["curl", "-sSL", "--max-time", str(таймаут),
                        "-o", str(цель), "-w", "%{http_code}", адрес],
                       capture_output=True, text=True)
    return г.returncode == 0 and (г.stdout or "").strip().endswith("200")


def даты_карты(домен: str, ящик: Path, таймаут: int) -> tuple[list[str], str]:
    """Все `lastmod` карты домена: индекс плюс до четырёх его частей."""
    индекс = ящик / f"{домен}-index.xml"
    if not достать(f"https://{домен}/sitemap.xml", индекс, таймаут):
        return ([], "карта не получена")
    текст = индекс.read_text(encoding="utf-8", errors="replace")
    даты = re.findall(r"<lastmod>(\d{4}-\d\d-\d\d)", текст)
    части = [а for а in re.findall(r"<loc>([^<]+)</loc>", текст)
             if а.endswith((".xml", ".xml.gz"))]
    for н, адрес in enumerate(части[:4]):
        часть = ящик / f"{домен}-{н}.xml"
        if достать(адрес, часть, таймаут):
            даты += re.findall(r"<lastmod>(\d{4}-\d\d-\d\d)",
                               часть.read_text(encoding="utf-8",
                                               errors="replace"))
    if not даты:
        return ([], "в карте нет lastmod")
    return (даты, "")


def отставание(даты: list[str], сегодня: dt.date) -> int:
    return (сегодня - dt.date.fromisoformat(max(даты))).days


def главная(аргв: list[str] | None = None) -> int:
    р = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    р.add_argument("domains", nargs="*")
    р.add_argument("--today", default="")
    р.add_argument("--timeout", type=int, default=40)
    а = р.parse_args(аргв)
    сегодня = (dt.date.fromisoformat(а.today) if а.today
               else dt.datetime.now(dt.timezone.utc).date())
    домены = а.domains or list(СЕТЬ)
    ящик = Path(tempfile.mkdtemp(prefix="sitemap-freshness-"))

    итоги: dict[str, int] = {}
    print(f"{'домен':24} {'самый свежий lastmod':22} отставание")
    for домен in домены:
        даты, беда = даты_карты(домен, ящик, а.timeout)
        if беда:
            print(f"{домен:24} {беда:22} НЕ ИЗМЕРЕНО")
            continue
        сут = отставание(даты, сегодня)
        итоги[домен] = сут
        пометка = ("сегодня" if сут == 0 else f"{сут} сут"
                   if сут < ПОРОГ_СУТОК else f"ОТСТАЛА НА {сут} сут")
        print(f"{домен:24} {max(даты):22} {пометка}")

    if not итоги:
        print("\nни одной карты не измерено", file=sys.stderr)
        return 2
    самая_молодая = min(итоги.values())
    находки = [д for д, с in итоги.items()
               if с >= ПОРОГ_СУТОК and с > самая_молодая]
    print(f"\nкарта не сдвинулась вслед за каталогом: {len(находки)}"
          + (f" — {', '.join(sorted(находки))}" if находки else ""))
    print(f"самая молодая карта сети отстаёт на {самая_молодая} сут — это и "
          f"есть мера общей задержки доставки, она находкой не считается")
    if не_измерено := [д for д in домены if д not in итоги]:
        print(f"не измерено: {', '.join(не_измерено)} — это пробел, а не "
              f"исправность")
    return 1 if находки else 0


if __name__ == "__main__":
    raise SystemExit(главная())
