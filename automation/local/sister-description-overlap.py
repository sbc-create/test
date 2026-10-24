#!/usr/bin/env python3
"""Дословное совпадение описаний у витрин-сестёр (MOD-53).

ПОВОД. 16.10 на выборке 40 страниц описания `yummyani.biz` и `yummyani.org`
совпали ДОСЛОВНО во всех 40 случаях: слой различия по домену в выпущенных
образах не работал. Для поиска это две витрины с одинаковым содержимым.

Критерий записи требует ПОВТОРЯЕМОЙ выборки: тот же `seed`, те же пути. Иначе
«стало лучше» нельзя отличить от «попались другие страницы». Поэтому выборка
берётся детерминированно из карты сайта первой витрины, и те же пути
запрашиваются у второй.

Исходы различаются: СОВПАЛИ дословно / РАЗЛИЧАЮТСЯ / НЕ ИЗМЕРЕНО (страница не
отдалась или описания нет). Молчание о неизмеренном запрещено: доля, считанная
по меньшему числу страниц, выглядит как улучшение.
"""
from __future__ import annotations

import argparse
import html
import random
import re
import subprocess
import sys

ОПИСАНИЕ = re.compile(
    r'<meta[^>]+name=["\']description["\'][^>]+content=["\'](.*?)["\']', re.S | re.I)
АДРЕС = re.compile(r"<loc>\s*(.*?)\s*</loc>", re.S)


def получить(url: str, таймаут: int) -> tuple[str, str]:
    try:
        г = subprocess.run(
            ["curl", "-sS", "-L", "--max-time", str(таймаут),
             "-w", "\n@@КОД:%{http_code}", url],
            capture_output=True, text=True, timeout=таймаут + 10)
    except subprocess.TimeoutExpired:
        return "", f"предел ожидания {таймаут} с"
    if г.returncode != 0:
        return "", (г.stderr.strip().splitlines() or ["загрузчик отказал"])[-1]
    тело, _, хвост = г.stdout.rpartition("@@КОД:")
    if хвост.strip() != "200":
        return "", f"HTTP {хвост.strip() or 'код не получен'}"
    return тело, ""


def описание(html_код: str) -> str:
    м = ОПИСАНИЕ.search(html_код)
    return " ".join(html.unescape(м.group(1)).split()) if м else ""


def пути(домен: str, таймаут: int, сколько: int, seed: int) -> list[str]:
    """Детерминированная выборка путей произведений из карты сайта.

    Индекс карты обходится ОДИН уровень: у витрин Yummy адреса произведений
    лежат не в `sitemap-1.xml`, а в части `/sitemap/titles.xml`, объявленной
    индексом. Первая редакция искала только плоские имена и напечатала «не
    удалось взять адреса» — то есть сообщила о пустоте там, где адреса есть.
    """
    собрано: list[str] = []
    for имя in ("sitemap.xml", "sitemap-1.xml"):
        код, _ = получить(f"https://{домен}/{имя}", таймаут)
        if not код:
            continue
        адреса = АДРЕС.findall(код)
        прямые = [а for а in адреса if "/anime/" in а or "/title/" in а]
        if прямые:
            собрано = прямые
            break
        # Это индекс: идём в части, где по имени ожидаются произведения.
        части = [а for а in адреса
                 if "title" in а.lower() or "anime" in а.lower()] or адреса[:3]
        for часть in части:
            к2, _ = получить(часть, таймаут)
            собрано.extend(а for а in АДРЕС.findall(к2 or "")
                           if "/anime/" in а or "/title/" in а)
            if len(собрано) >= сколько * 20:
                break
        if собрано:
            break
    if not собрано:
        return []
    пути = sorted({re.sub(r"^https?://[^/]+", "", а) for а in собрано})
    random.Random(seed).shuffle(пути)
    return пути[:сколько]


def главное(argv: list[str] | None = None) -> int:
    р = argparse.ArgumentParser(description=__doc__)
    р.add_argument("--a", default="yummyani.biz")
    р.add_argument("--b", default="yummyani.org")
    р.add_argument("--sample", type=int, default=40)
    р.add_argument("--seed", type=int, default=42)
    р.add_argument("--timeout", type=int, default=25)
    а = р.parse_args(argv)

    выборка = пути(а.a, а.timeout, а.sample, а.seed)
    if not выборка:
        print(f"НЕ ИЗМЕРЕНО: у {а.a} не удалось взять адреса произведений"
              " из карты сайта")
        return 2
    print(f"выборка: {len(выборка)} путей из карты {а.a}, seed {а.seed}")
    совпали, различны, неизмерено = [], [], []
    for путь in выборка:
        к1, о1 = получить(f"https://{а.a}{путь}", а.timeout)
        к2, о2 = получить(f"https://{а.b}{путь}", а.timeout)
        если = о1 or о2
        д1, д2 = описание(к1), описание(к2)
        if если or not д1 or not д2:
            неизмерено.append((путь, если or "описания нет на одной из витрин"))
            continue
        (совпали if д1 == д2 else различны).append(путь)
    сравнимых = len(совпали) + len(различны)
    print(f"сравнимых страниц {сравнимых} из {len(выборка)};"
          f" НЕ ИЗМЕРЕНО {len(неизмерено)}")
    for путь, почему in неизмерено[:5]:
        print(f"   не измерено: {путь} — {почему}")
    if not сравнимых:
        print("НЕ ИЗМЕРЕНО: сравнимых страниц нет")
        return 2
    доля = len(совпали) / сравнимых
    print()
    print(f"СОВПАЛИ дословно: {len(совпали)} из {сравнимых} ({доля:.0%})")
    print(f"РАЗЛИЧАЮТСЯ:      {len(различны)}")
    for путь in различны[:5]:
        print(f"   различаются: {путь}")
    print()
    if доля >= 0.5:
        print(f"ВЫВОД: описания сестёр совпадают дословно у {доля:.0%}"
              " сравнимых страниц — слой различия по домену не работает"
              " (MOD-53). Порог закрытия записи: ниже половины")
        return 1
    print(f"ВЫВОД: дословных совпадений {доля:.0%} — ниже половины,"
          " условие записи MOD-53 выполнено")
    return 0


if __name__ == "__main__":
    sys.exit(главное())
