#!/usr/bin/env python3
"""Снимок таблицы публичных маршрутов витрины yummyani.

Витрина ведёт таблицу `PublicTitleRoute`: слаг, идентификатор произведения у
поставщика и признак каноничности. Это не догадка о правиле адресации, а
объявление самой витрины о том, какой адрес какому произведению принадлежит.

**Почему снимок, а не запрос из движка.** Движок не должен ходить в базу
витрины: тогда сборка контракта зависела бы от того, поднят ли контейнер
витрины, а выгрузка переставала бы воспроизводиться. Снимок снимается один
раз, кладётся рядом с кэшем каталога и читается адаптером — тем же способом,
каким читается кэш каталога Lords.

**Пароль не спрашивается и не печатается.** Он уже есть в окружении
контейнера базы; команда выполняется внутри него, а наружу выходит только
результат.

Проверено на витрине `yummyani.site` 2026-09-06: 7 303 маршрута, у 7 302
признак каноничности. Все 7 303 идентификатора нашлись в кэше каталога,
которым ядро уже располагает, — то есть отдельный доступ к каталогу витрины
для связи не нужен.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import subprocess
import sys
from pathlib import Path

#: Соответствие витрины и контейнера её базы. Живёт здесь, потому что это
#: знание об эксплуатации, а не о предметной области, и в ядро оно не попадает.
CONTAINERS: dict[str, str] = {
    "yummyani-site": "yummyani-staging-pg-site-1",
    "yummyani-org": "yummyani-staging-pg-org-1",
    "yummyani-biz": "yummyani-staging-pg-biz-1",
}

QUERY = (
    'SELECT slug, "providerTitleId", canonical, '
    'to_char("updatedAt" AT TIME ZONE \'UTC\', \'YYYY-MM-DD"T"HH24:MI:SSZ\') '
    'FROM "PublicTitleRoute" ORDER BY slug;'
)


def export(site_id: str, *, container: str | None = None) -> dict:
    """Маршруты одной витрины. Пустой ответ — ошибка, а не пустая витрина."""
    имя = container or CONTAINERS.get(site_id)
    if not имя:
        raise SystemExit(f"витрина {site_id!r} не описана в CONTAINERS")

    # Запрос идёт стандартным вводом, а не частью командной строки: в нём есть
    # одинарные кавычки, и любая их подстановка в строку оболочки — это либо
    # синтаксическая ошибка, либо место, где чужое значение станет командой.
    выполнено = subprocess.run(
        ["docker", "exec", "-i", имя, "sh", "-lc",
         'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -qtA -F"|" -f -'],
        input=QUERY, capture_output=True, text=True)
    if выполнено.returncode != 0:
        raise SystemExit(f"чтение маршрутов не удалось: "
                         f"{выполнено.stderr.strip()[:300]}")

    маршруты = []
    for строка in выполнено.stdout.splitlines():
        части = строка.rstrip("\n").split("|")
        if len(части) < 3 or not части[0].strip():
            continue
        маршруты.append({
            "slug": части[0],
            "providerTitleId": части[1],
            "canonical": части[2] == "t",
            "updatedAt": части[3] if len(части) > 3 else "",
        })
    if not маршруты:
        raise SystemExit(
            "таблица маршрутов пуста. Пустая витрина и нечитаемая таблица "
            "выглядят одинаково, поэтому пустой ответ считается ошибкой")

    return {
        "siteId": site_id,
        "source": f"container:{имя}:PublicTitleRoute",
        "fetchedAt": dt.datetime.now(dt.timezone.utc).isoformat(),
        "routes": len(маршруты),
        "canonicalRoutes": sum(1 for m in маршруты if m["canonical"]),
        "items": маршруты,
    }


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("site_id")
    p.add_argument("--container")
    p.add_argument("--out", required=True)
    a = p.parse_args()

    снимок = export(a.site_id, container=a.container)
    путь = Path(a.out)
    путь.parent.mkdir(parents=True, exist_ok=True)
    путь.write_text(json.dumps(снимок, ensure_ascii=False, indent=1) + "\n",
                    "utf-8")
    print(json.dumps({k: v for k, v in снимок.items() if k != "items"},
                     ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
