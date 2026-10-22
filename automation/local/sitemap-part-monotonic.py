#!/usr/bin/env python3
"""Растёт ли часть карты МОНОТОННО: сверка множеств двух чтений, а не чисел.

Только чтение публичной карты; снимки складываются в `var/sitemap-snapshots/`.

ЗАЧЕМ. Измерено 22.10 на `yummyani.site`: `episodes.xml` дал 1 679 адресов в
23:4xZ и 464 в 00:2xZ, и в переходе 23:00→00:25 потеряно 1 217 адресов (все
серии `detektiv-konan`, работа вышла из карты целиком) при добавленных двух
(`tristiya`). Работ в обоих чтениях ровно 36: предел `DETAIL_LIMIT = 40`
держит ЧИСЛО работ, а состав меняется целыми работами.

Поэтому приёмка правки D1 по ЧИСЛАМ невозможна: и 464, и 1 679 меньше 123 000,
и оба можно принять за «ещё не доехало». Проверять нужно монотонность состава:
второе чтение обязано быть НАДМНОЖЕСТВОМ первого.

Исходы раздельные:

* ``ПЕРВЫЙ СНИМОК``   — сравнивать не с чем, снимок сохранён;
* ``НАДМНОЖЕСТВО``    — ничего не исчезло (добавленное печатается);
* ``ПОТЕРИ``          — адреса исчезли: именно это ловит проверка;
* ``НЕ ИЗМЕРЕНО``     — часть не прочитана.

    python3 automation/local/sitemap-part-monotonic.py \\
        --url https://yummyani.site/sitemap/episodes.xml
    python3 automation/local/sitemap-part-monotonic.py --url … --json

Коды: 0 — надмножество или первый снимок; 1 — потери; 2 — не измерено.
"""
from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import pathlib
import re
import subprocess
import sys
import tempfile

КОРЕНЬ = pathlib.Path(__file__).resolve().parents[2]
СНИМКИ = КОРЕНЬ / "var" / "sitemap-snapshots"

ПЕРВЫЙ = "ПЕРВЫЙ СНИМОК"
НАДМНОЖЕСТВО = "НАДМНОЖЕСТВО"
ПОТЕРИ = "ПОТЕРИ"
НЕ_ИЗМЕРЕНО = "НЕ ИЗМЕРЕНО"


def сравнить(прежние: set[str], текущие: set[str]) -> dict:
    """Исход по двум множествам адресов. Чистая функция.

    Работы считаются отдельно от адресов: потеря одной работы весит тысячу
    адресов, и смешивать эти два числа нельзя.
    """
    исчезли = прежние - текущие
    добавились = текущие - прежние
    исход = ПОТЕРИ if исчезли else НАДМНОЖЕСТВО
    return {
        "исход": исход,
        "было": len(прежние),
        "стало": len(текущие),
        "исчезло": len(исчезли),
        "добавилось": len(добавились),
        "исчезли_работы": sorted({работа(а) for а in исчезли})[:12],
        "добавились_работы": sorted({работа(а) for а in добавились})[:12],
        "примеры_исчезших": sorted(исчезли)[:5],
    }


def работа(адрес: str) -> str:
    """Слаг работы из адреса серии или сезона; для прочего — пустая строка."""
    м = re.search(r"/(?:anime|title)/([^/?#]+)", адрес)
    return м.group(1) if м else ""


def адреса_части(url: str, таймаут: int = 250) -> set[str]:
    with tempfile.NamedTemporaryFile(suffix=".xml") as б:
        subprocess.run(["curl", "-sSL", "--max-time", str(таймаут),
                        "-o", б.name, url], capture_output=True)
        текст = open(б.name, encoding="utf-8", errors="replace").read()
    return {а.strip() for а in re.findall(r"<loc>\s*([^<\s]+)\s*</loc>", текст)}


def путь_снимка(url: str) -> pathlib.Path:
    ключ = hashlib.sha256(url.encode()).hexdigest()[:16]
    имя = re.sub(r"[^a-zA-Z0-9._-]+", "-", url.split("://", 1)[-1])[:60]
    return СНИМКИ / f"{имя}-{ключ}.json"


def проверить(url: str) -> dict:
    текущие = адреса_части(url)
    if not текущие:
        return {"url": url, "исход": НЕ_ИЗМЕРЕНО,
                "почему": "часть не прочитана или пуста"}
    файл = путь_снимка(url)
    снято = datetime.datetime.now(datetime.timezone.utc).isoformat()
    if файл.is_file():
        прежний = json.loads(файл.read_text(encoding="utf-8"))
        итог = сравнить(set(прежний.get("адреса") or []), текущие)
        итог["прежний_снимок"] = прежний.get("снято")
    else:
        итог = {"исход": ПЕРВЫЙ, "стало": len(текущие),
                "почему": "сравнивать не с чем, снимок сохранён"}
    СНИМКИ.mkdir(parents=True, exist_ok=True)
    файл.write_text(json.dumps({"url": url, "снято": снято,
                                "адреса": sorted(текущие)},
                               ensure_ascii=False), encoding="utf-8")
    итог.update({"url": url, "снято": снято, "снимок": str(файл)})
    return итог


def main(аргв: list[str] | None = None) -> int:
    р = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    р.add_argument("--url", action="append", required=True)
    р.add_argument("--json", action="store_true")
    а = р.parse_args(аргв)

    итоги = [проверить(u) for u in а.url]
    if а.json:
        print(json.dumps({"частей": len(итоги), "части": итоги},
                         ensure_ascii=False, indent=2))
    else:
        for и in итоги:
            print(f"{и['url'][:70]:72} {и['исход']}")
            if и["исход"] == ПОТЕРИ:
                print(f"   было {и['было']}, стало {и['стало']};"
                      f" исчезло {и['исчезло']}, добавилось {и['добавилось']}")
                print(f"   работы, ушедшие из части: {и['исчезли_работы']}")
                print(f"   работы, вошедшие в часть: {и['добавились_работы']}")
                for п in и["примеры_исчезших"]:
                    print(f"      исчез: {п}")
            elif и["исход"] == НАДМНОЖЕСТВО:
                print(f"   было {и['было']}, стало {и['стало']},"
                      f" добавилось {и['добавилось']}, исчезло 0"
                      f" (прежний снимок {и.get('прежний_снимок', '—')})")
            else:
                print(f"   {и.get('почему', '')}")

    if all(и["исход"] == НЕ_ИЗМЕРЕНО for и in итоги):
        return 2
    return 1 if any(и["исход"] == ПОТЕРИ for и in итоги) else 0


if __name__ == "__main__":
    sys.exit(main())
