"""Вариант inventory-first: что можно сделать из того, что есть.

Ингредиенты рецепта — предметы в занятых слотах сетки источника (slot_items); количество — число слотов.
Слот, которому нет материала на сайте, остаётся недостающим под своим названием из источника.
"""

from __future__ import annotations

from collections import Counter

from craft.plan import match


def options(site) -> list:
    return [e for e in site.entries if e.type in ("item", "resource", "building")]


def needs(site, recipe: dict) -> list[dict]:
    """[{key, entry|None, title, qty}] по слотам рецепта."""
    cnt: Counter = Counter()
    info: dict = {}
    for t in recipe.get("slot_items", []):
        e = match(site, t)
        key = e.slug if e else "?" + t
        cnt[key] += 1
        info[key] = (e, t)
    return [{"key": k, "entry": info[k][0], "title": info[k][1], "qty": q} for k, q in cnt.items()]


def craftable(site, have: set[str]) -> tuple[list, list]:
    """(можно сейчас, не хватает одного): [(предмет, рецепт, нужды, недостающее)]."""
    now, almost = [], []
    for e in site.entries:
        if e.type not in ("item", "building"):
            continue
        for r in e.recipes:
            ns = needs(site, r)
            if not ns:
                continue
            missing = [n for n in ns if n["key"] not in have]
            if not missing:
                now.append((e, r, ns, missing))
            elif len(missing) == 1 and len(ns) > 1:
                almost.append((e, r, ns, missing))
    return now, almost
