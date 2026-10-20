#!/usr/bin/env python3
"""Насколько похожи между собой витрины одного семейства — глазами поиска.

Зачем. У пар и троек доменов одного семейства трафик расходится на два
порядка: animedia.icu 117 визитов людей в сутки и 712 поисковых за неделю,
animedia.space — 3 и НОЛЬ. Техническая цепочка у обоих в порядке (200, robots
открыт, карта есть, canonical на себя). Тогда первый вопрос — не отличает ли
поиск их друг от друга вовсе.

Что измеряется, и это именно измерение, а не впечатление:

  заголовок, описание, H1 главной — совпадают ли дословно;
  состав главной — доля общих адресов произведений;
  текст главной — доля общих слов (Жаккар по множеству слов);
  выборка страниц произведений — совпадают ли title и H1 на тех же адресах.

Вывод инструмент не делает: он печатает доли. «Похоже» и «дубль» — разные
утверждения, и второе решается не здесь.

    python3 automation/local/cross-site-duplicate-probe.py animedia.icu animedia.space
"""
from __future__ import annotations

import re
import subprocess
import sys
from itertools import combinations

СЕМЬИ = {
    "animedia": ["animedia.icu", "animedia.space"],
    "animego": ["animeg0.site", "an1meg0.site", "an1mego.site"],
    "zona": ["zonafilm.cc", "zonafilm.space", "zonafilm12.site"],
    "yummy": ["yummyani.site", "yummyani.org", "yummyani.biz"],
}


def страница(url: str) -> str:
    return subprocess.run(["curl", "-sS", "--max-time", "45", url],
                          capture_output=True, text=True).stdout or ""


def текст(html: str) -> str:
    т = re.sub(r"(?is)<(script|style)[^>]*>.*?</\1>", " ", html)
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", т)).strip()


def поле(html: str, образец: str) -> str:
    м = re.search(образец, html, re.I | re.S)
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", м.group(1))).strip() if м else ""


def слепок(домен: str) -> dict:
    html = страница(f"https://{домен}/")
    # Две формы адреса карточки существуют одновременно: `/title/<слаг>` у
    # Lords, Zona и Animedia, `/anime/<слаг>` у Yummy. Зная только первую,
    # зонд печатал на Yummy «общих 0 из 0 (0 %)» — а это читается как
    # «совпадений нет», тогда как измерено не было ничего.
    адреса = set(re.findall(r'href="(/(?:title|anime)/[^"]+)"', html))
    слова = {w.lower() for w in re.findall(r"[А-Яа-яЁёA-Za-z]{4,}", текст(html))}
    return {
        "домен": домен,
        "title": поле(html, r"<title[^>]*>(.*?)</title>"),
        "description": поле(html, r'<meta[^>]+name="description"[^>]+content="([^"]*)"'),
        "h1": поле(html, r"<h1[^>]*>(.*?)</h1>"),
        "адреса": адреса,
        "слова": слова,
    }


def жаккар(а: set, б: set) -> float:
    if not а or not б:
        return 0.0
    return 100.0 * len(а & б) / len(а | б)


def сравнить(домены: list[str]) -> None:
    слепки = {д: слепок(д) for д in домены}
    for а, б in combinations(домены, 2):
        па, пб = слепки[а], слепки[б]
        print(f"\n--- {а} ↔ {б}")
        for поле_ in ("title", "description", "h1"):
            одинаково = па[поле_] == пб[поле_] and па[поле_] != ""
            метка = "СОВПАДАЕТ ДОСЛОВНО" if одинаково else "различается"
            print(f"  {поле_:12} {метка}")
            if одинаково:
                print(f"               «{па[поле_][:90]}»")
        всего_адресов = len(па["адреса"] | пб["адреса"])
        if всего_адресов == 0:
            # Ноль из нуля — это НЕ «совпадений нет», а «мерить было нечего».
            # Выдавать второе за первое значило бы объявить пару различной,
            # ничего не измерив.
            print("  адреса главной: НЕ ИЗМЕРЕНО — ни на одной из двух главных"
                  " не нашлось адресов карточек")
        else:
            print(f"  адреса главной: общих "
                  f"{len(па['адреса'] & пб['адреса'])} из "
                  f"{всего_адресов} ({жаккар(па['адреса'], пб['адреса']):.0f} %)")
        print(f"  слова главной:  {жаккар(па['слова'], пб['слова']):.0f} % общих")
        общие = sorted(па["адреса"] & пб["адреса"])[:3]
        for адрес in общие:
            х_а = страница(f"https://{а}{адрес}")
            х_б = страница(f"https://{б}{адрес}")
            ЗАГ = r"<title[^>]*>(.*?)</title>"
            t_a, t_b = поле(х_а, ЗАГ), поле(х_б, ЗАГ)
            h_a, h_b = поле(х_а, r"<h1[^>]*>(.*?)</h1>"), поле(х_б, r"<h1[^>]*>(.*?)</h1>")
            print(f"    {адрес[:46]:46} title {'=' if t_a == t_b else '≠'} "
                  f"h1 {'=' if h_a == h_b else '≠'}")


def главная(аргв: list[str]) -> int:
    if аргв:
        сравнить(аргв)
        return 0
    for имя, домены in СЕМЬИ.items():
        print(f"\n===== семейство {имя}")
        сравнить(домены)
    return 0


if __name__ == "__main__":
    sys.exit(главная(sys.argv[1:]))
