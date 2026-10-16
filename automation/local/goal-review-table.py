#!/usr/bin/env python3
"""Недельный разбор по цели 5 000 визитов: две полные недели, по доменам.

Источник — артефакт шага `goal_review` службы сбора
(`var/analytics/goal-review-<дата>.json`), а не мой пересчёт: там уже сведены
две полные недели по часовому поясу счётчика, разделены Яндекс и Google,
отмечены аномальные сутки и посчитана концентрация поисковых входов на
страницах. Инструмент только читает и показывает.

Печатается по каждому домену:

  w1 / w2        средние визиты в сутки за 02–08.10 и 09–15.10
  изменение      во сколько раз выросло или упало
  суток ≥ цели   сколько суток недели достигли 5 000
  Я / G          поисковые визиты Яндекса и Google ОТДЕЛЬНО
  страниц        сколько страниц получили поисковые входы
  top1           доля входов на самой популярной странице
  авто           ЧИСЛО визитов автоматического браузера за w2 — не
                 доля: первая версия таблицы напечатала «53941 %»,
                 подставив абсолютное значение в формат доли
  всплески       сутки, помеченные как аномальные

Домен без измерения называется отдельно: отсутствие данных — не ноль.

    python3 automation/local/goal-review-table.py
    python3 automation/local/goal-review-table.py --file <путь>
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

ПО_УМОЛЧАНИЮ = Path("/home/claude/wt-portable-site-cell-01/var/analytics")


def свежий(каталог: Path) -> Path:
    файлы = sorted(каталог.glob("goal-review-*.json"))
    if not файлы:
        raise SystemExit(f"в {каталог} нет артефактов goal-review-*.json")
    return файлы[-1]


def главное(аргв=None) -> int:
    р = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    р.add_argument("--file", type=Path)
    опции = р.parse_args(аргв)

    путь = опции.file or свежий(ПО_УМОЛЧАНИЮ)
    д = json.loads(путь.read_text(encoding="utf-8"))
    недели = д.get("weeks") or {}
    цель = д.get("goal", 5000)
    print(f"артефакт: {путь}")
    print(f"собран: {д.get('collected_at')}; цель {цель} визитов в сутки")
    print(f"w1: {недели.get('w1')}  w2: {недели.get('w2')}")
    предв = д.get("preliminary_days") or []
    if предв:
        print(f"предварительные сутки (данные дорастают): {', '.join(предв)}")
    print()

    строки = [с for с in д.get("sites") or [] if с.get("measured")]
    без = [с for с in д.get("sites") or [] if not с.get("measured")]
    строки.sort(key=lambda с: -(с.get("w2") or {}).get("avg_per_day", 0))

    print(f"{'домен':22s} {'w1/сут':>7s} {'w2/сут':>7s} {'изм.':>6s} "
          f"{'≥цели':>5s} {'Яндекс':>7s} {'Google':>7s} {'страниц':>7s} "
          f"{'top1':>5s} {'авто,визитов':>12s} всплески")
    итог_w1 = итог_w2 = 0.0
    for с in строки:
        w1 = с.get("w1") or {}
        w2 = с.get("w2") or {}
        a1 = w1.get("avg_per_day") or 0.0
        a2 = w2.get("avg_per_day") or 0.0
        итог_w1 += a1
        итог_w2 += a2
        изм = f"×{a2 / a1:.1f}" if a1 else ("—" if not a2 else "нов.")
        п = с.get("search_pages") or {}
        top1 = п.get("top1_share")
        всплески = (w2.get("spikes") or [])
        print(f"{с['domain']:22s} {a1:7.1f} {a2:7.1f} {изм:>6s} "
              f"{w2.get('days_ge_goal', 0):5d} {w2.get('yandex', 0):7.0f} "
              f"{w2.get('google', 0):7.0f} {п.get('pages', 0):7d} "
              f"{(f'{top1:.0%}' if top1 is not None else '—'):>5s} "
              f"{(w2.get('automated') or 0):12.0f} "
              f"{len(всплески)}: {', '.join(d[5:] for d in всплески[:3])}")

    print(f"\nсумма по сети: w1 {итог_w1:.0f} → w2 {итог_w2:.0f} визитов в "
          f"сутки. В артефакте это РЕАЛЬНЫЕ визиты: автоматический "
          f"браузер уже вычтен, его число — в колонке «авто»")
    достигают = [с["domain"] for с in строки
                 if (с.get("w2") or {}).get("avg_per_day", 0) >= цель]
    print(f"достигают цели в среднем за w2: {', '.join(достигают) or 'ни один'}")
    print("общий трафик сети цель по каждому домену не заменяет")
    if без:
        print(f"\nбез измерения — НЕ НОЛЬ ({len(без)}):")
        for с in без:
            print(f"   {с['domain']:22s} {с.get('reason') or 'причина не названа'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(главное())
