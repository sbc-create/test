#!/usr/bin/env python3
"""Проверяет цель MOD-214: описатель srcset не обещает ширину больше настоящей.

Меряется ЦЕЛЬ, а не разметка, поэтому инструмент работает на витрине любого
семейства и с любым способом вывода обложек. Отсутствие srcset — не дефект:
это отдельный исход «нечего обещать», он и печатается отдельно.

Настоящая ширина берётся из заголовка самого файла, а не из имени, параметра
запроса или подписи в разметке. Для этого запрашивается начало файла
(Range), и если сервер отдал весь файл — читается он.
"""
from __future__ import annotations

import argparse
import io
import json
import re
import sys
import urllib.error
import urllib.parse
import urllib.request

ГОЛОВА_БАЙТ = 1 << 16
ТАЙМАУТ = 30
АГЕНТ = "site-factory-srcset-audit/1.0"

_IMG = re.compile(r"<img\b[^>]*>", re.I)
_SRCSET = re.compile(r"""srcset\s*=\s*["']([^"']+)["']""", re.I)
_SRC = re.compile(r"""\bsrc\s*=\s*["']([^"']+)["']""", re.I)


def _получить(url: str, начало: bool = False) -> bytes:
    запрос = urllib.request.Request(url, headers={"User-Agent": АГЕНТ})
    if начало:
        запрос.add_header("Range", f"bytes=0-{ГОЛОВА_БАЙТ - 1}")
    with urllib.request.urlopen(запрос, timeout=ТАЙМАУТ) as ответ:
        return ответ.read()


def _ширина_файла(url: str) -> tuple[int | None, str]:
    """Настоящая ширина из заголовка файла. Возвращает (ширина, причина)."""
    try:
        from PIL import Image
    except ImportError:
        return None, "Pillow недоступен в этом окружении"
    for начало in (True, False):
        try:
            данные = _получить(url, начало=начало)
        except urllib.error.HTTPError as сбой:
            if начало and сбой.code in (416, 501):
                continue
            return None, f"HTTP {сбой.code}"
        except (urllib.error.URLError, TimeoutError) as сбой:
            return None, f"сеть: {сбой}"
        try:
            with Image.open(io.BytesIO(данные)) as изображение:
                return int(изображение.size[0]), ""
        except Exception as сбой:  # noqa: BLE001 — любой разбор может не хватить головы
            if начало:
                continue
            return None, f"разбор: {type(сбой).__name__}"
    return None, "не удалось прочитать размер"


def _разобрать_srcset(значение: str) -> list[tuple[str, int]]:
    пары: list[tuple[str, int]] = []
    for кусок in значение.split(","):
        части = кусок.strip().split()
        if len(части) != 2 or not части[1].endswith("w"):
            continue
        try:
            пары.append((части[0], int(части[1][:-1])))
        except ValueError:
            continue
    return пары


def _без_ширины(url: str) -> str:
    разбор = urllib.parse.urlsplit(url)
    параметры = [(к, з) for к, з in urllib.parse.parse_qsl(разбор.query) if к != "w"]
    return urllib.parse.urlunsplit(
        (разбор.scheme, разбор.netloc, разбор.path,
         urllib.parse.urlencode(параметры), "")
    )


def проверить(домен: str, путь: str, предел: int) -> dict:
    страница = f"https://{домен}{путь}"
    итог: dict = {
        "домен": домен, "страница": страница,
        "обложек с srcset": 0, "обложек без srcset": 0,
        "описателей": 0, "ложных обещаний": 0, "не измерено": 0,
        "случаи": [], "исход": "",
    }
    try:
        разметка = _получить(страница).decode("utf-8", "replace")
    except Exception as сбой:  # noqa: BLE001
        итог["исход"] = f"страница не получена: {сбой}"
        return итог

    кандидаты: list[tuple[str, list[tuple[str, int]]]] = []
    for тег in _IMG.findall(разметка):
        найден = _SRCSET.search(тег)
        if not найден:
            источник = _SRC.search(тег)
            if источник and "poster" in источник.group(1):
                итог["обложек без srcset"] += 1
            continue
        пары = _разобрать_srcset(найден.group(1))
        if пары:
            кандидаты.append((тег, пары))

    итог["обложек с srcset"] = len(кандидаты)
    измеренные: dict[str, tuple[int | None, str]] = {}

    for _тег, пары in кандидаты[:предел]:
        основа = urllib.parse.urljoin(страница, _без_ширины(пары[-1][0]))
        if основа not in измеренные:
            измеренные[основа] = _ширина_файла(основа)
        настоящая, причина = измеренные[основа]
        for адрес, обещано in пары:
            итог["описателей"] += 1
            if настоящая is None:
                итог["не измерено"] += 1
                итог["случаи"].append(
                    {"адрес": адрес, "обещано": обещано,
                     "настоящая": None, "причина": причина})
                continue
            if обещано > настоящая:
                итог["ложных обещаний"] += 1
                итог["случаи"].append(
                    {"адрес": адрес, "обещано": обещано,
                     "настоящая": настоящая, "причина": "обещано больше настоящего"})

    if итог["обложек с srcset"] == 0:
        итог["исход"] = ("srcset у обложек нет — обещать нечего, "
                         "дефект MOD-214 на этой витрине не воспроизводится")
    elif итог["не измерено"] and not итог["описателей"] - итог["не измерено"]:
        итог["исход"] = "НЕ ИЗМЕРЕНО: ни один файл не прочитан"
    elif итог["ложных обещаний"]:
        итог["исход"] = f"ДЕФЕКТ: ложных обещаний {итог['ложных обещаний']}"
    else:
        итог["исход"] = "цель достигнута: ложных обещаний нет"
    return итог


def main() -> int:
    р = argparse.ArgumentParser()
    р.add_argument("--domain", action="append", required=True)
    р.add_argument("--path", default="/")
    р.add_argument("--limit", type=int, default=12,
                   help="сколько обложек страницы мерить")
    р.add_argument("--json", action="store_true")
    а = р.parse_args()

    итоги = [проверить(д, а.path, а.limit) for д in а.domain]
    if а.json:
        print(json.dumps(итоги, ensure_ascii=False, indent=1))
        return 0 if not any(и["ложных обещаний"] for и in итоги) else 1

    for и in итоги:
        print(f"== {и['домен']}{а.path}")
        print(f"   обложек с srcset {и['обложек с srcset']}, "
              f"без srcset {и['обложек без srcset']}, "
              f"описателей {и['описателей']}, "
              f"ложных {и['ложных обещаний']}, "
              f"не измерено {и['не измерено']}")
        print(f"   {и['исход']}")
        for с in и["случаи"][:6]:
            print(f"     обещано {с['обещано']}w, настоящая {с['настоящая']}"
                  f" — {с['причина']}")
    return 0 if not any(и["ложных обещаний"] for и in итоги) else 1


if __name__ == "__main__":
    sys.exit(main())
