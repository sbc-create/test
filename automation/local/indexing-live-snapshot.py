#!/usr/bin/env python3
"""Живой режим индексации по сети: снимок до операций и сверка после.

Зачем. Задание владельца требует сохранять режим индексации каждого сайта, и
это требование нельзя подтвердить обещанием: в истории этого хозяйства
пересоздание контейнера уже один раз поставило `yummyani.site` в `NOINDEX`
(P0, коммиты `2336594` и `7f1a5a3`). Значит перед операциями владельца нужен
снимок того, что ФАКТИЧЕСКИ отдаётся обходу, а после — сверка.

Снимается по каждому живому домену из реестра: заголовок `X-Robots-Tag`,
`<meta name="robots">`, `canonical` главной и код ответа. Четыре значения, а не
одно: заголовок и мета могут расходиться, и тогда важно какое именно изменилось.

Сверка называет РОВНО то, что изменилось, и отличает это от того, что не
измерено. Домен, который не ответил при сверке, — не «режим сохранён» и не
«режим сломан», а отдельный исход: мерить было нечем.

    python3 automation/local/indexing-live-snapshot.py --snapshot
    python3 automation/local/indexing-live-snapshot.py --compare
"""
from __future__ import annotations

import argparse
import json
import re
import ssl
import sys
import urllib.error
import urllib.request
from pathlib import Path

КОРЕНЬ = Path(__file__).resolve().parents[2]
РЕЕСТР = КОРЕНЬ / "config" / "site-cells.json"
СНИМКИ = КОРЕНЬ / "var" / "indexing-baselines"

_КАНОН = re.compile(r"""<link[^>]+rel=["']canonical["'][^>]*>""", re.I)
_ROBOTS = re.compile(r"""<meta[^>]+name=["']robots["'][^>]*>""", re.I)
_HREF = re.compile(r"""href=["']([^"']+)["']""", re.I)
_CONTENT = re.compile(r"""content=["']([^"']+)["']""", re.I)

НЕ_ИЗМЕРЕНО = "НЕ ИЗМЕРЕНО"


def живые_домены() -> list[str]:
    д = json.loads(РЕЕСТР.read_text(encoding="utf-8"))
    ячейки = д.get("cells") or д
    return sorted({з.get("domain") for з in ячейки
                   if з.get("status") == "live" and з.get("domain")})


def _значение(разметка: str, образец: re.Pattern, поле: re.Pattern) -> str:
    м = образец.search(разметка)
    if not м:
        return ""
    з = поле.search(м.group(0))
    return з.group(1).strip() if з else ""


def снять(домен: str, предел: float) -> dict:
    контекст = ssl.create_default_context()
    контекст.check_hostname = False
    контекст.verify_mode = ssl.CERT_NONE
    открыть = urllib.request.build_opener(
        urllib.request.HTTPSHandler(context=контекст))
    запрос = urllib.request.Request(
        f"https://{домен}/", headers={"User-Agent": "factory-indexing-snapshot"})
    try:
        ответ = открыть.open(запрос, timeout=предел)
        разметка = ответ.read(300_000).decode("utf-8", "replace")
        return {
            "код": str(ответ.status),
            "x_robots_tag": ответ.headers.get("X-Robots-Tag", ""),
            "meta_robots": _значение(разметка, _ROBOTS, _CONTENT),
            "canonical": _значение(разметка, _КАНОН, _HREF),
        }
    except urllib.error.HTTPError as сбой:
        return {"код": str(сбой.code),
                "x_robots_tag": сбой.headers.get("X-Robots-Tag", ""),
                "meta_robots": "", "canonical": ""}
    except Exception as сбой:
        # Отказ связи — факт о замере, а не о витрине. Склеить его с
        # «режим сохранён» значило бы подтвердить то, чего не видели.
        return {"ошибка": f"{type(сбой).__name__}: {str(сбой)[:80]}"}


ПОЛЯ = ("код", "x_robots_tag", "meta_robots", "canonical")


def главное(аргв=None) -> int:
    р = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    р.add_argument("--snapshot", action="store_true")
    р.add_argument("--compare", action="store_true")
    р.add_argument("--timeout", type=float, default=60.0)
    р.add_argument("--store", type=Path, default=СНИМКИ)
    р.add_argument("--label", default="latest")
    опции = р.parse_args(аргв)

    if опции.snapshot == опции.compare:
        print("нужен ровно один из --snapshot и --compare", file=sys.stderr)
        return 2

    файл = опции.store / f"{опции.label}.json"
    домены = живые_домены()
    сейчас = {домен: снять(домен, опции.timeout) for домен in домены}

    if опции.snapshot:
        опции.store.mkdir(parents=True, exist_ok=True)
        файл.write_text(json.dumps(сейчас, ensure_ascii=False, indent=1),
                        encoding="utf-8")
        открытых = sum(1 for з in сейчас.values()
                       if "noindex" not in (з.get("x_robots_tag", "")
                                            + з.get("meta_robots", "")).lower()
                       and "ошибка" not in з)
        неснятых = [д for д, з in сейчас.items() if "ошибка" in з]
        print(f"снимок сохранён: {файл}")
        print(f"   доменов {len(домены)}; открыто обходу {открытых}; "
              f"не снято {len(неснятых)}")
        for домен in домены:
            з = сейчас[домен]
            if "ошибка" in з:
                print(f"   [? ] {домен:26s} {НЕ_ИЗМЕРЕНО}: {з['ошибка']}")
            else:
                print(f"   [ок] {домен:26s} код {з['код']}, "
                      f"X-Robots-Tag {з['x_robots_tag'] or '—'}, "
                      f"meta {з['meta_robots'] or '—'}")
        return 2 if неснятых else 0

    if not файл.is_file():
        print(f"сверять не с чем: снимка {файл} нет.\n"
              "Без снимка «режим сохранён» было бы утверждением о том, "
              "чего мы не знаем.", file=sys.stderr)
        return 2
    было = json.loads(файл.read_text(encoding="utf-8"))

    изменений = 0
    неизмеренных = 0
    print(f"сверка с {файл}")
    for домен in sorted(set(было) | set(сейчас)):
        б = было.get(домен)
        с = сейчас.get(домен)
        if б is None:
            print(f"   [+ ] {домен:26s} в снимке его не было — новый домен")
            continue
        if с is None:
            print(f"   [- ] {домен:26s} в реестре больше нет")
            continue
        if "ошибка" in с:
            неизмеренных += 1
            print(f"   [? ] {домен:26s} {НЕ_ИЗМЕРЕНО}: {с['ошибка']}")
            continue
        if "ошибка" in б:
            print(f"   [? ] {домен:26s} в снимке не был измерен — "
                  "сверять не с чем")
            continue
        разошлось = [(п, б.get(п, ""), с.get(п, "")) for п in ПОЛЯ
                     if б.get(п, "") != с.get(п, "")]
        if not разошлось:
            print(f"   [ок] {домен:26s} режим не изменился")
            continue
        изменений += 1
        print(f"   [!!] {домен:26s} ИЗМЕНИЛОСЬ:")
        for поле, было_зн, стало_зн in разошлось:
            print(f"        {поле}: {было_зн or '—'} → {стало_зн or '—'}")

    print(f"\nизменений: {изменений}; не измерено: {неизмеренных}")
    if неизмеренных and not изменений:
        print("часть доменов не ответила — «режим сохранён» по ним НЕ "
              "утверждается", file=sys.stderr)
        return 2
    return 1 if изменений else 0


if __name__ == "__main__":
    raise SystemExit(главное())
