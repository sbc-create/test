#!/usr/bin/env python3
"""Различимость шаблонных пакетов: подпись и попарное сходство.

## Зачем считать, а не смотреть

«Пятьдесят разных шаблонов» легко подменяется пятьюдесятью одинаковыми
раскладками с разными переменными цвета. На глаз это видно не сразу, особенно
когда пакеты просматриваются по одному. Поэтому различие измеряется подписью,
в которую цвет входит ОДНОЙ составляющей из восьми: перекрасить пакет и
объявить его новым не получится.

## Из чего состоит подпись

* порядок и типы блоков главной;
* грамматика карточек по блокам и её распределение;
* модель навигации — сколько пунктов и есть ли отдельная точка входа;
* наличие и модель героя;
* лестницы колонок из CSS — сколько колонок на каждой точке перелома;
* плотность на широком экране;
* форма — радиус скругления и шаг сетки;
* роль зелёного в палитре.

Сходство считается по Жаккару на множестве признаков. Порог различается для
пакетов одного семейства и разных: внутри семейства общего заведомо больше, и
требовать от них той же дистанции значило бы запретить семейства вовсе.
"""

from __future__ import annotations

import argparse
import itertools
import json
import pathlib
import re

ПОРОГ_ОБЩИЙ = 0.82
ПОРОГ_СЕМЕЙСТВО = 0.88
ПОРОГ_МЕЖДУ_СЕМЕЙСТВАМИ = 0.76


def лестницы(пакет: pathlib.Path) -> dict[str, list[tuple[int, int]]]:
    """Класс сетки → [(точка перелома, колонок)] из layout.css пакета."""
    файл = пакет / "layout.css"
    if not файл.is_file():
        return {}
    текст = файл.read_text(encoding="utf-8")
    собрано: dict[str, list[tuple[int, int]]] = {}

    def добавить(класс: str, точка: int, колонок: int) -> None:
        собрано.setdefault(класс, []).append((точка, колонок))

    # Базовые правила — вне media, точка 0.
    без_медиа = re.sub(r"@media[^{]*\{.*?\}\s*\}", "", текст, flags=re.S)
    for класс, колонок in re.findall(
            r"\.(g--[a-z-]+)\{[^}]*grid-template-columns:repeat\((\d+)", без_медиа):
        добавить(класс, 0, int(колонок))

    for точка, тело in re.findall(r"@media\(min-width:(\d+)px\)\{(.*?)\}\s*\}", текст, re.S):
        for класс, колонок in re.findall(
                r"\.(g--[a-z-]+)\{[^}]*grid-template-columns:repeat\((\d+)", тело):
            добавить(класс, int(точка), int(колонок))
    return {к: sorted(set(v)) for к, v in собрано.items()}


def колонок_на(лестница: list[tuple[int, int]], ширина: int) -> int:
    подходящие = [к for т, к in лестница if ширина >= т]
    return подходящие[-1] if подходящие else 0


def подпись(пакет: pathlib.Path) -> dict:
    манифест = json.loads((пакет / "template.json").read_text(encoding="utf-8"))
    блоки = манифест["home_block_order"]
    лест = лестницы(пакет)

    токены = (пакет / "tokens.css").read_text(encoding="utf-8") if (пакет / "tokens.css").is_file() else ""
    радиус = re.search(r"--radius:\s*(\d+)px", токены)
    шаг = re.search(r"--gap:\s*(\d+)px", токены)
    фон = re.search(r"--bg:\s*(#[0-9a-fA-F]{6})", токены)

    грамматики = [б.get("грамматика") for б in блоки if б.get("грамматика")]
    признаки = set()
    признаки.add(f"порядок:{'>'.join(б['тип'] for б in блоки)}")
    признаки.add(f"блоков:{len(блоки)}")
    признаки.add(f"герой:{'да' if any(б['тип'] == 'hero' for б in блоки) else 'нет'}")
    признаки.add(f"грамматики:{'+'.join(sorted(set(грамматики)))}")
    признаки.add(f"ведущая-грамматика:{грамматики[0] if грамматики else 'нет'}")
    признаки.add(f"навигация:{len(манифест['navigation'])}")
    признаки.add(f"радиус:{радиус.group(1) if радиус else '?'}")
    признаки.add(f"шаг:{шаг.group(1) if шаг else '?'}")
    признаки.add(f"фон:{(фон.group(1) if фон else '?').lower()}")
    признаки.add(f"зелёный:{манифест.get('green_identity', '?')}")
    # Лестницы сравниваются по ПОЗИЦИИ блока, а не по имени класса сетки.
    # Имена у пакетов разные по определению, и ключ по имени давал бы нулевое
    # пересечение всегда — то есть объявлял бы различными даже две копии.
    сетки_по_порядку = [б.get("класс", "") for б in блоки if б.get("класс")]
    for номер, класс in enumerate(сетки_по_порядку):
        лестница = лест.get(класс, [])
        for ширина in (320, 768, 1440, 1920):
            признаки.add(f"сетка{номер}@{ширина}:{колонок_на(лестница, ширина)}")

    плотность = max((колонок_на(л, 1440) for л in лест.values()), default=0)
    return {
        "template_id": манифест["template_id"],
        "slug": манифест["slug"],
        "family": манифест["family"],
        "green_identity": манифест.get("green_identity"),
        "block_order": [б["тип"] for б in блоки],
        "card_grammar": sorted(set(грамматики)),
        "desktop_density_1440": плотность,
        "ladders": {к: v for к, v in лест.items()},
        "features": sorted(признаки),
    }


def сходство(a: dict, b: dict) -> float:
    п1, п2 = set(a["features"]), set(b["features"])
    if not (п1 | п2):
        return 1.0
    return len(п1 & п2) / len(п1 | п2)


def проверить(пакеты: list[pathlib.Path]) -> dict:
    подписи = [подпись(п) for п in пакеты]
    пары = []
    нарушения = []
    for a, b in itertools.combinations(подписи, 2):
        с = сходство(a, b)
        одно_семейство = a["family"] == b["family"]
        порог = ПОРОГ_СЕМЕЙСТВО if одно_семейство else ПОРОГ_МЕЖДУ_СЕМЕЙСТВАМИ
        запись = {
            "pair": [a["template_id"], b["template_id"]],
            "same_family": одно_семейство,
            "similarity": round(с, 4),
            "threshold": порог,
        }
        пары.append(запись)
        if с >= порог:
            нарушения.append(запись)

    # Отличие только цветом: подписи совпадают во всём, кроме палитры.
    только_цвет = []
    for a, b in itertools.combinations(подписи, 2):
        без_цвета_a = {п for п in a["features"] if not п.startswith(("фон:", "зелёный:"))}
        без_цвета_b = {п for п in b["features"] if not п.startswith(("фон:", "зелёный:"))}
        if без_цвета_a == без_цвета_b:
            только_цвет.append([a["template_id"], b["template_id"]])

    порядки = [">".join(п["block_order"]) for п in подписи]
    дубли_порядка = len(порядки) - len(set(порядки))

    return {
        "templates": len(подписи),
        "signatures": подписи,
        "pairs": пары,
        "PAIRWISE_SIMILARITY_MAX": max((п["similarity"] for п in пары), default=0.0),
        "PAIRWISE_SIMILARITY_VIOLATIONS": len(нарушения),
        "violations": нарушения,
        "COLOR_ONLY_VARIANTS": len(только_цвет),
        "color_only_pairs": только_цвет,
        "HOME_BLOCK_ORDER_DUPLICATES": дубли_порядка,
        "GREEN_PRIMARY_OR_SECONDARY_COUNT": sum(
            1 for п in подписи if п["green_identity"] in ("primary", "secondary")),
        "PASS": not нарушения and not только_цвет and дубли_порядка == 0,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default="factory/templates/lords")
    parser.add_argument("--record")
    args = parser.parse_args()

    пакеты = sorted(p for p in pathlib.Path(args.root).iterdir()
                    if p.is_dir() and re.match(r"^T\d{3}-", p.name))
    отчёт = проверить(пакеты)
    if args.record:
        pathlib.Path(args.record).parent.mkdir(parents=True, exist_ok=True)
        pathlib.Path(args.record).write_text(
            json.dumps(отчёт, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({k: v for k, v in отчёт.items() if k not in ("signatures", "pairs")},
                     ensure_ascii=False, indent=2))
    return 0 if отчёт["PASS"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
