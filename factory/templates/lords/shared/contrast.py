#!/usr/bin/env python3
"""Контраст объявленных пакетом пар цветов — до отрисовки.

Браузерное измерение находит недостаточный контраст там, где он проявился. Но
причина почти всегда в паре токенов: заливка кнопки и надпись на ней, текст и
фон, приглушённый текст и карточка. Пара либо годна, либо нет — это считается
арифметикой и не требует ни браузера, ни снимка.

Гейт здесь стоит раньше и говорит прямее: «у T011 --brand с --brand-ink дают
4.38 при пороге 4.5». Починить это в токенах на порядок дешевле, чем искать
в трёхстах измерениях, какой именно элемент просел.

Порог — 4.5 для обычного текста и 3.0 для крупного, как в WCAG AA. Смягчать
порог, чтобы пакет прошёл, запрещено: это меняет не цвет, а определение
годности.
"""

from __future__ import annotations

import argparse
import json
import pathlib
import re

ПОРОГ_ОБЫЧНЫЙ = 4.5
ПОРОГ_КРУПНЫЙ = 3.0

#: Пары, которые обязаны быть читаемыми, и на каком пороге.
#: Каждая пара — настоящее сочетание из ядра оформления, а не абстракция.
ПАРЫ = (
    ("--ink", "--bg", ПОРОГ_ОБЫЧНЫЙ, "основной текст на фоне страницы"),
    ("--ink", "--card", ПОРОГ_ОБЫЧНЫЙ, "текст карточки на карточке"),
    ("--dim", "--bg", ПОРОГ_ОБЫЧНЫЙ, "приглушённый текст на фоне"),
    ("--dim", "--card", ПОРОГ_ОБЫЧНЫЙ, "приглушённый текст на карточке"),
    ("--dim", "--soft", ПОРОГ_ОБЫЧНЫЙ, "приглушённый текст на подложке"),
    ("--brand-ink", "--brand", ПОРОГ_ОБЫЧНЫЙ, "надпись на кнопке бренда"),
    ("--brand-text", "--bg", ПОРОГ_ОБЫЧНЫЙ, "зелёный текст на фоне"),
    ("--brand-text", "--card", ПОРОГ_ОБЫЧНЫЙ, "зелёный текст на карточке"),
    ("--brand-text", "--soft", ПОРОГ_ОБЫЧНЫЙ, "зелёный текст на подложке"),
)


def _канал(значение: float) -> float:
    return значение / 12.92 if значение <= 0.03928 else ((значение + 0.055) / 1.055) ** 2.4


def яркость(цвет: str) -> float:
    цвет = цвет.strip().lstrip("#")
    if len(цвет) == 3:
        цвет = "".join(с * 2 for с in цвет)
    r, g, b = (int(цвет[i:i + 2], 16) / 255 for i in (0, 2, 4))
    return 0.2126 * _канал(r) + 0.7152 * _канал(g) + 0.0722 * _канал(b)


def отношение(первый: str, второй: str) -> float:
    a, b = яркость(первый), яркость(второй)
    светлее, темнее = max(a, b), min(a, b)
    return round((светлее + 0.05) / (темнее + 0.05), 2)


def токены(текст: str) -> dict[str, str]:
    return {f"--{имя}": значение
            for имя, значение in re.findall(r"--([a-z-]+):\s*(#[0-9a-fA-F]{3,6})", текст)}


def проверить_пакет(пакет: pathlib.Path, запасные: dict) -> list[dict]:
    объявлено = токены((пакет / "tokens.css").read_text(encoding="utf-8"))
    цвета = dict(запасные, **объявлено)
    беды = []
    for передний, задний, порог, что in ПАРЫ:
        if передний not in цвета or задний not in цвета:
            continue
        значение = отношение(цвета[передний], цвета[задний])
        if значение < порог:
            беды.append({
                "template_id": пакет.name[:4],
                "pair": f"{передний} на {задний}",
                "what": что, "ratio": значение, "need": порог,
                "colors": f"{цвета[передний]} / {цвета[задний]}",
            })
    return беды


def проверить(корень: pathlib.Path, ядро: pathlib.Path) -> dict:
    запасные = токены((ядро / "core.css").read_text(encoding="utf-8"))
    пакеты = sorted(п for п in корень.iterdir()
                    if п.is_dir() and (п / "tokens.css").is_file())
    беды = []
    for пакет in пакеты:
        беды.extend(проверить_пакет(пакет, запасные))
    return {
        "packages": len(пакеты),
        "pairs_per_package": len(ПАРЫ),
        "TOKEN_CONTRAST_VIOLATIONS": len(беды),
        "violations": беды,
        "PASS": not беды,
    }


def главное() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default="factory/templates/lords")
    parser.add_argument("--core", default="factory/templates/lords/shared")
    parser.add_argument("--record")
    args = parser.parse_args()
    отчёт = проверить(pathlib.Path(args.root), pathlib.Path(args.core))
    if args.record:
        pathlib.Path(args.record).parent.mkdir(parents=True, exist_ok=True)
        pathlib.Path(args.record).write_text(
            json.dumps(отчёт, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(отчёт, ensure_ascii=False, indent=2)[:3000])
    return 0 if отчёт["PASS"] else 2


if __name__ == "__main__":
    raise SystemExit(главное())
