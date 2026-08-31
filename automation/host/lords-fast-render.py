#!/usr/bin/env python3
"""Быстрый рендер витрины Lords: переписывается только изменившееся.

Заменяет собой шаг сборки в конвейере. Всё остальное — идентификатор релиза по
содержимому, гейт плеера, атомарная подмена ссылки — остаётся прежним.

Коды возврата (тот же принцип, что у ворот: молчание не повод пропустить
обновление):

    0  — staging собран быстрым путём, публикация имеет смысл
    10 — переписывать нечего, staging не нужен
    2  — быстрым путём воспользоваться нельзя, нужен полный рендер
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from factory.lords import fast_path, live_catalog, live_site  # noqa: E402

СОБРАН = 0
НЕЧЕГО = 10
НУЖЕН_ПОЛНЫЙ = 2


def state_path(repo: Path, site_id: str) -> Path:
    return repo / "var" / "lords" / "render-state" / f"{site_id}.titles.json"


def load_state(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def save_state(path: Path, snapshot: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(".tmp")
    temp.write_text(json.dumps(snapshot, ensure_ascii=False), encoding="utf-8")
    temp.replace(path)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("site_id")
    parser.add_argument("--repo", default="/srv/site-factory/repo")
    parser.add_argument("--staging", required=True)
    parser.add_argument("--current", default=None, help="каталог site текущего релиза")
    parser.add_argument("--cache", default=None)
    parser.add_argument("--var", default=None)
    parser.add_argument("--record", action="store_true",
                        help="сохранить снимок произведений (только после приёмки релиза)")
    args = parser.parse_args(argv)

    repo = Path(args.repo)
    var = Path(args.var) if args.var else repo / "var"
    cache_root = args.cache or str(var / "lords" / "lords" / "catalog-cache")
    отчёт: dict = {"site": args.site_id}

    current = Path(args.current) if args.current else None
    if current is None or not current.is_dir():
        отчёт["решение"] = "нет текущего релиза — нужен полный рендер"
        print(json.dumps(отчёт, ensure_ascii=False))
        return НУЖЕН_ПОЛНЫЙ

    try:
        entries = live_site.load_live_items(args.site_id, root=cache_root)
    except Exception as error:  # noqa: BLE001
        отчёт["решение"] = f"каталог не прочитан: {error!r}"[:200]
        print(json.dumps(отчёт, ensure_ascii=False))
        return НУЖЕН_ПОЛНЫЙ

    catalog = live_catalog.catalog_from_live(entries)
    снимок = fast_path.title_digests(entries, catalog)
    путь_снимка = state_path(repo, args.site_id)
    прежний = load_state(путь_снимка)

    if args.record:
        save_state(путь_снимка, снимок)
        отчёт["решение"] = "снимок сохранён"
        отчёт["titles"] = len(снимок)
        print(json.dumps(отчёт, ensure_ascii=False))
        return СОБРАН

    if not прежний:
        отчёт["решение"] = "снимка произведений нет — нужен полный рендер"
        отчёт["titles"] = len(снимок)
        print(json.dumps(отчёт, ensure_ascii=False))
        return НУЖЕН_ПОЛНЫЙ

    изменения = fast_path.compare_titles(прежний, снимок)
    отчёт["изменения"] = изменения.as_dict()

    удаляемые = tuple(f"title/{slug}/index.html" for slug in изменения.removed_slugs)
    итог = fast_path.apply(
        args.site_id,
        base=current,
        target=Path(args.staging),
        cache_root=cache_root,
        var_root=var,
        only_title_slugs=frozenset(изменения.changed_slugs),
        remove_relatives=удаляемые,
        write=True,
    )
    отчёт["результат"] = итог.as_dict()

    if итог.pages_changed == 0 and итог.pages_removed == 0:
        отчёт["решение"] = "переписывать нечего"
        print(json.dumps(отчёт, ensure_ascii=False))
        return НЕЧЕГО

    if not итог.base_untouched:
        # Прежний релиз обязан остаться нетронутым. Если это не так, публиковать
        # нельзя: жёсткие ссылки могли быть переписаны на месте.
        отчёт["решение"] = "база изменилась — быстрый путь отменён"
        отчёт["нарушения"] = list(итог.base_violations[:10])
        print(json.dumps(отчёт, ensure_ascii=False))
        return НУЖЕН_ПОЛНЫЙ

    отчёт["решение"] = "staging собран быстрым путём"
    print(json.dumps(отчёт, ensure_ascii=False))
    return СОБРАН


if __name__ == "__main__":
    raise SystemExit(main())
