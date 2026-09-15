#!/usr/bin/env python3
"""Сборка sitemap витрин из каталога. Ничего не публикует.

Карта собирается после того, как каталог обновился, и записывается целиком
или не записывается вовсе: частично обновлённая карта хуже устаревшей —
индекс уже ссылается на части, которых ещё нет.

Пока витрины закрыты `noindex`, карта готовится, но поисковым системам не
отправляется. Это разные решения, и смешивать их нельзя.
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import seo_layer as SEO  # noqa: E402

#: Разделы витрины, существующие у всех семейств. Проверяются отдельно: раздел,
#: которого нет, в карте не нужен, а карта с 404 внутри — это список
#: несуществующих страниц.
РАЗДЕЛЫ = ("/", "/catalog/", "/new/", "/collections/", "/schedule/")


def записи(каталог: pathlib.Path) -> list[dict]:
    д = json.loads(каталог.read_text(encoding="utf-8"))
    из = []
    for x in д.get("items", []):
        slug = x.get("slug")
        if not slug:
            continue
        # `lastmod` — только настоящая дата. `published_at_estimated`
        # означает, что дату вывели, а не узнали: в карту она не идёт.
        дата = ""
        if x.get("published_at") and not x.get("published_at_estimated"):
            дата = str(x["published_at"])[:10]
        из.append({"slug": slug, "lastmod": дата})
    return из


def главное(argv: list[str] | None = None) -> int:
    р = argparse.ArgumentParser(description=__doc__)
    р.add_argument("--domain", required=True)
    р.add_argument("--catalog", required=True)
    р.add_argument("--out", required=True)
    а = р.parse_args(argv)
    стр = записи(pathlib.Path(а.catalog))
    файлы = SEO.построить_sitemap(а.domain, стр, РАЗДЕЛЫ)
    итог = SEO.записать_атомарно(а.out, файлы)
    итог["domain"] = а.domain
    итог["catalog_entries"] = len(стр)
    итог["with_lastmod"] = sum(1 for s in стр if s["lastmod"])
    print(json.dumps(итог, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(главное())
