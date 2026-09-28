#!/usr/bin/env python3
"""Указатель поиска строится по СОБРАННОЙ витрине, а не по каталогу.

Источником имён и адресов служат сами страницы релиза. Причина простая: адрес
страницы вычисляется отрисовщиком, и повторять это вычисление здесь значило бы
завести второй источник правды. Разойдутся они не сразу, а на записях с
совпадающими слагами — то есть там, где ошибку труднее всего заметить.

Побочное следствие полезно само по себе: указатель не может сослаться на
страницу, которой нет.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from factory.lords import search_index as си  # noqa: E402

БЛОК = re.compile(r'<script type="application/ld\+json">(.*?)</script>', re.S)


def _из_страницы(путь: Path) -> dict[str, str] | None:
    try:
        текст = путь.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None
    for кусок in БЛОК.findall(текст):
        try:
            данные = json.loads(кусок)
        except ValueError:
            continue
        if not isinstance(данные, dict):
            continue
        имя = данные.get("name")
        if данные.get("@type") in ("Movie", "TVSeries", "TVSeason", "TVEpisode") and имя:
            return {"name": str(имя),
                    "original_name": str(данные.get("alternateName") or ""),
                    "year": данные.get("copyrightYear")}
    return None


def собрать(release: Path) -> dict:
    каталог = release / "site" / "title"
    записи = []
    for страница in sorted(каталог.glob("*/index.html")):
        разобрано = _из_страницы(страница)
        if разобрано is None:
            continue
        разобрано["url"] = f"/title/{страница.parent.name}/"
        записи.append(разобрано)
    индекс = си.build(записи)
    индекс["items"] = записи
    return индекс


def main(argv=None) -> int:
    р = argparse.ArgumentParser(description=__doc__)
    р.add_argument("release", help="каталог релиза (в нём site/)")
    р.add_argument("--out", default="",
                   help="куда писать; по умолчанию <release>/search-index.json")
    args = р.parse_args(argv)

    релиз = Path(args.release)
    if not (релиз / "site" / "title").is_dir():
        print(f"ОТКАЗ: в релизе {релиз} нет собранных страниц произведений", file=sys.stderr)
        return 3
    индекс = собрать(релиз)
    if not индекс["items"]:
        # Пустой указатель отвечал бы «ничего не найдено» на любой запрос, и
        # витрина выглядела бы исправной без единого результата.
        print(f"ОТКАЗ: по страницам релиза {релиз} не собрано ни одной записи", file=sys.stderr)
        return 3
    цель = Path(args.out) if args.out else релиз / "search-index.json"
    си.save(индекс, цель)
    print(f"указатель: записей {len(индекс['items'])}, кусков {len(индекс['postings'])}, "
          f"{цель}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
