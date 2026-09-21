#!/usr/bin/env python3
"""Нормализованная фикстура каталога для отрисовки шаблонных пакетов.

Фикстура берётся из живого каталога витрины и НИЧЕГО к нему не добавляет.
В каталоге есть `kind`, `poster`, `published_at`, `slug`, `title`, `year` — и
больше ничего. Значит у фикстуры не может появиться ни рейтинга, ни жанра, ни
описания: шаблон обязан уметь честно обходиться без них, а не получать их из
воздуха ради красивой картинки.

Отсутствие поля отмечается явно (`absent_fields`), чтобы проверка отличала
«данных нет» от «шаблон забыл их отрисовать».

Выборка ограничена и детерминирована: первые N записей в порядке каталога.
Случайная выборка сделала бы снимки невоспроизводимыми, а сравнение шаблонов
между собой — бессмысленным.
"""

from __future__ import annotations

import argparse
import json
import pathlib

ИСТОЧНИК = pathlib.Path("/srv/lords/.frontend/lords-01-catalog.json")
#: Полей ровно столько, сколько есть в источнике. Список закрыт намеренно.
ПОЛЯ = ("slug", "title", "url", "year", "kind", "poster", "published_at",
        "published_at_estimated")


def собрать(источник: pathlib.Path, сколько: int) -> dict:
    сырой = json.loads(источник.read_text(encoding="utf-8"))
    записи = сырой.get("items") or []
    выборка = []
    for запись in записи[:сколько]:
        выборка.append({поле: запись.get(поле) for поле in ПОЛЯ})

    виды = sorted({з["kind"] for з in выборка if з.get("kind")})
    годы = sorted({з["year"] for з in выборка if з.get("year")}, reverse=True)
    без_постера = [з["slug"] for з in выборка if not з.get("poster")]

    return {
        "schema": "lords-template-fixture/1",
        "source_revision": сырой.get("revision", ""),
        "source_built_at": сырой.get("builtAt", ""),
        "source_count": сырой.get("count", len(записи)),
        "sample_size": len(выборка),
        "fields_present": list(ПОЛЯ),
        # Честный список того, чего в данных НЕТ. Шаблон, который отрисует
        # рейтинг или жанр, возьмёт их не отсюда — и это будет видно.
        "absent_fields": ["rating", "genre", "country", "description", "episodes",
                          "premiere_at", "popularity"],
        "kinds": виды,
        "years": годы,
        "titles_without_poster": без_постера,
        "items": выборка,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", default=str(ИСТОЧНИК))
    parser.add_argument("--count", type=int, default=60)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()

    фикстура = собрать(pathlib.Path(args.source), args.count)
    путь = pathlib.Path(args.out)
    путь.parent.mkdir(parents=True, exist_ok=True)
    путь.write_text(json.dumps(фикстура, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"фикстура: {len(фикстура['items'])} записей, видов {len(фикстура['kinds'])}, "
          f"без постера {len(фикстура['titles_without_poster'])} → {путь}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
