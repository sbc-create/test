#!/usr/bin/env python3
"""Замер поиска: сколько запросов приложение теряет на непустом каталоге.

Что измеряется
--------------

Для каждого слова из настоящих названий каталога сравниваются два числа:

* сколько записей содержат это слово в названии (по снимку контура);
* сколько отдаёт поиск приложения (`/api/search`).

Ноль во втором столбце при ненулевом первом — потерянный запрос. Слово
берётся из названий, а не из головы: проверять поиск выдуманными словами
значит измерять собственную фантазию.

Оба адреса задаются явно: приложение (`--app`) и витрина (`--front`), чтобы
один и тот же прогон показал и потерю, и то, закрывает ли её витрина.
"""
from __future__ import annotations

import argparse
import collections
import json
import random
import re
import sqlite3
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

СЛОВО = re.compile(r"[^0-9A-Za-zА-Яа-яЁё]+")
ССЫЛКА = re.compile(r'href="(/anime/[^"]+)"')


def сверить(с: str) -> str:
    return СЛОВО.sub(" ", (с or "").casefold().replace("ё", "е")).strip()


def названия(база: Path) -> list[tuple[str, str]]:
    соед = sqlite3.connect(f"file:{база}?mode=ro", uri=True)
    try:
        return [(р[0] or "", р[1] or "") for р in соед.execute(
            "SELECT title_ru, COALESCE(title_original,'') FROM entity")]
    finally:
        соед.close()


def в_каталоге(пары: list[tuple[str, str]], слово: str) -> int:
    ц = сверить(слово)
    return sum(1 for ru, orig in пары
               if ц in сверить(ru) or ц in сверить(orig))


def через_api(основа: str, q: str) -> int | None:
    адрес = основа + "/api/search?q=" + urllib.parse.quote(q)
    try:
        with urllib.request.urlopen(адрес, timeout=30) as о:
            свод = json.loads(о.read().decode("utf-8", "replace"))
    except (urllib.error.URLError, OSError, ValueError):
        return None
    return len(свод.get("items") or [])


def через_страницу(основа: str, q: str) -> int | None:
    адрес = основа + "/search?q=" + urllib.parse.quote(q)
    try:
        with urllib.request.urlopen(адрес, timeout=60) as о:
            тело = о.read().decode("utf-8", "replace")
    except (urllib.error.URLError, OSError):
        return None
    return len(set(ССЫЛКА.findall(тело)))


def слова(пары: list[tuple[str, str]], сколько: int, зерно: int) -> list[str]:
    счёт: collections.Counter = collections.Counter()
    for ru, _ in пары:
        for w in СЛОВО.split(ru.casefold().replace("ё", "е")):
            if len(w) >= 4:
                счёт[w] += 1
    частые = [w for w, _ in счёт.most_common(400)]
    random.Random(зерно).shuffle(частые)
    return частые[:сколько]


def main() -> int:
    р = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    р.add_argument("--readmodel", required=True)
    р.add_argument("--app", required=True, help="адрес приложения, например http://127.0.0.1:3101")
    р.add_argument("--front", help="адрес витрины, например http://127.0.0.1:9310")
    р.add_argument("--out", required=True)
    р.add_argument("--words", type=int, default=60)
    р.add_argument("--seed", type=int, default=7)
    а = р.parse_args()

    пары = названия(Path(а.readmodel))
    проба = слова(пары, а.words, а.seed)
    строки = []
    for w in проба:
        строки.append({
            "word": w,
            "in_catalog": в_каталоге(пары, w),
            "app_api": через_api(а.app, w),
            "front_page": через_страницу(а.front, w) if а.front else None,
        })
    потеряно = [с for с in строки
                if с["in_catalog"] > 0 and (с["app_api"] or 0) == 0]
    закрыто = [с for с in потеряно if (с["front_page"] or 0) > 0]
    свод = {
        "captured_at_utc": __import__("datetime").datetime.now(
            __import__("datetime").timezone.utc).isoformat(),
        "readmodel": str(а.readmodel),
        "app": а.app, "front": а.front,
        "entities": len(пары), "words_probed": len(строки),
        "lost_by_app": len(потеряно),
        "lost_share": round(len(потеряно) / len(строки), 3) if строки else None,
        "covered_by_front": len(закрыто),
        "rows": строки,
    }
    Path(а.out).write_text(json.dumps(свод, ensure_ascii=False, indent=2),
                           encoding="utf-8")
    print(f"слов проверено: {len(строки)}; приложение теряет: {len(потеряно)}"
          f" ({свод['lost_share']}); витрина закрывает: {len(закрыто)}")
    for с in sorted(потеряно, key=lambda x: -x["in_catalog"])[:10]:
        print(f"   {с['word']:16} каталог={с['in_catalog']:4} "
              f"приложение={с['app_api']} витрина={с['front_page']}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
