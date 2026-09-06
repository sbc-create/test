#!/usr/bin/env python3
"""Наборы содержимого для витрин-стендов — по запросу HANDOFF-032.

## Что это и чем оно не является

Это **синтетические** наборы для проверки пути публикации, а не содержимое
боевых витрин. Каждая запись объявляет себя таковой прямо в названии и
описании: читатель страницы видит «Фикстура», а не правдоподобный тайтл.
Образец взят у `sites/pilot-local/content/catalog.json`, на который ссылается
handoff.

Наборы **не делают** витрины боевыми. У site-a, site-b и site-c домены вида
`*.localhost`, `production_authorized: false`, `ssh_host_ref: null` и нет ни
рантайма, ни vhost. Набор закрывает ровно то, о чём просит handoff: очередь
разбора перестаёт быть пустой, и путь публикации становится проверяемым.

## Откуда берутся категории

Из навигации самой витрины (`sites/<id>/package.yaml`, раздел `navigation`).
Придумывать разделы нельзя: витрина уже объявила, из чего состоит, и второй
источник правды разошёлся бы с первым.

Запуск:
    .venv/bin/python scripts/build_content_packs.py
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SITES = ("site-a", "site-b", "site-c")

#: Сколько записей в наборе. Handoff просит «несколько десятков»: приёмка
#: проверяет путь, а не объём.
PER_CATEGORY = 8


def navigation_sections(package: str) -> list[dict]:
    """Разделы витрины из её собственной навигации."""
    block = re.search(r"^\s*primary:\s*$", package, re.M)
    if not block:
        return []
    tail = package[block.end():]
    out = []
    for label, url in re.findall(r"-\s*label:\s*(.+?)\n\s*url:\s*(\S+)", tail):
        slug = url.strip("/").split("/")[0]
        if not slug or slug in {"catalog"}:
            continue
        out.append({"slug": slug, "label": label.strip()})
        if len(out) >= 3:
            break
    return out


def build(site: str) -> dict:
    package = (ROOT / "sites" / site / "package.yaml").read_text(encoding="utf-8")
    sections = navigation_sections(package)
    if not sections:
        raise SystemExit(f"{site}: навигация не разобрана — категории брать неоткуда")

    categories = [
        {"slug": s["slug"], "title": s["label"],
         "description": f"Синтетический раздел «{s['label']}» стенда {site}. "
                        "Служит проверке пути публикации."}
        for s in sections
    ]

    titles = []
    for index, section in enumerate(sections, start=1):
        for n in range(1, PER_CATEGORY + 1):
            number = f"{index}{n:02d}"
            titles.append({
                # Идентификатор обязателен и устойчив: handoff отвергает запись
                # без него, потому что выдуманный идентификатор нельзя
                # сопоставить, и первое же обновление создаст дубль.
                "id": f"{site}-fx-{number}",
                "slug": f"fixture-{number}",
                "category": section["slug"],
                "title": f"Фикстура {section['label']} №{n:02d}",
                "description": (
                    f"Синтетическая запись №{n:02d} раздела «{section['label']}» "
                    f"стенда {site}. Не является публикацией: набор существует "
                    "ради проверки пути «правка → предпросмотр → публикация»."
                ),
                "sort_key": number,
                "availability": "available",
                "meta": f"Стенд {site}",
                "image": {
                    "src": "/assets/media/cover.svg",
                    "alt": f"Обложка синтетической записи {number}",
                    "width": 640, "height": 360,
                },
                "facts": [
                    {"label": "Раздел", "value": section["label"]},
                    {"label": "Тип записи", "value": "синтетическая фикстура"},
                ],
                "updated_at": "2026-09-06",
            })

    return {"schema_version": 1, "kind": "fixture",
            "categories": categories, "titles": titles}


def main() -> int:
    for site in SITES:
        catalog = build(site)
        out = ROOT / "sites" / site / "content" / "catalog.json"
        out.parent.mkdir(parents=True, exist_ok=True)
        payload = json.dumps(catalog, ensure_ascii=False, indent=2) + "\n"
        out.write_text(payload, encoding="utf-8")
        digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()

        package_path = ROOT / "sites" / site / "package.yaml"
        text = package_path.read_text(encoding="utf-8")
        text = re.sub(r"^(\s*content_package_ref:).*$",
                      r"\1 content/catalog.json", text, count=1, flags=re.M)
        text = re.sub(r"^(\s*content_package_sha256:).*$",
                      rf"\1 {digest}", text, count=1, flags=re.M)
        package_path.write_text(text, encoding="utf-8")

        print(f"  {site}: разделов {len(catalog['categories'])}, "
              f"записей {len(catalog['titles'])}, отпечаток {digest[:16]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
