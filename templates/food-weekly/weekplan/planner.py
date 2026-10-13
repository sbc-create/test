"""Планы недели: проверка, замены, список покупок.

* блюдо плана — ссылка на материал соседнего сайта (site + slug → content_id
  из снимка каталога), рецепт не копируется;
* замена допустима только на блюдо того же приёма пищи (по разделу сайта рецептов);
* список покупок: количество × (люди / порции рецепта); одинаковые продукты
  складываются только при совпадении единицы; «по вкусу» и продукты без
  количества — отдельными строками. Время и температура не пересчитываются.
"""

from __future__ import annotations

import json
import re
from collections import OrderedDict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MEALS = OrderedDict([("breakfast", "Завтрак"), ("lunch", "Обед"), ("dinner", "Ужин")])
MEAL_CATEGORIES = {
    "breakfast": {"zavtraki"},
    "lunch": {"supy", "salaty", "zakuski"},
    "dinner": {"vtorye-blyuda", "garniry"},
}
DAYS = ["Понедельник", "Вторник", "Среда", "Четверг", "Пятница", "Суббота", "Воскресенье"]
UNITS = {
    "g": "г",
    "kg": "кг",
    "ml": "мл",
    "l": "л",
    "pcs": "шт.",
    "tbsp": "ст. л.",
    "tsp": "ч. л.",
    "cup": "стак.",
    "clove": "зуб.",
    "pinch": "щеп.",
    "bunch": "пучок",
    "slice": "ломт.",
    "sprig": "веточка",
    "can": "банка",
    "head": "гол.",
    "leaf": "лист",
    "piece": "кус.",
    "pack": "пачка",
}
SWAP_RX = re.compile(r"^d([1-7])-(breakfast|lunch|dinner)-(\d)$")


class PlanError(ValueError):
    pass


def load_catalogs() -> dict[str, dict]:
    out = {}
    for p in (ROOT / "data" / "catalog").glob("*.json"):
        snap = json.loads(p.read_text())
        out[snap["site_id"]] = {
            "meta": {k: v for k, v in snap.items() if k != "items"},
            "items": {x["slug"]: x for x in snap["items"]},
        }
    return out


def load_plans(catalogs: dict) -> OrderedDict:
    plans = OrderedDict()
    for p in sorted((ROOT / "data" / "plans").glob("*.json")):
        plan = json.loads(p.read_text())
        if plan["site_id"] != "food-weekly":
            raise PlanError(f"{p.name}: чужой site_id")
        if len(plan["days"]) != 7:
            raise PlanError(f"{p.name}: в плане не 7 дней")
        for n, day in enumerate(plan["days"], 1):
            for meal in MEALS:
                for ref in day[meal]:
                    item = catalogs.get(ref["site"], {}).get("items", {}).get(ref["slug"])
                    if not item:
                        raise PlanError(f"{p.name}: день {n}, {meal}: нет материала {ref['site']}:{ref['slug']}")
                    if item["category"] not in MEAL_CATEGORIES[meal]:
                        raise PlanError(f"{p.name}: день {n}: {ref['slug']} не подходит для «{MEALS[meal]}»")
        plans[plan["slug"]] = plan
    return plans


def parse_swaps(raw: str) -> dict[tuple[int, str, int], str]:
    out = {}
    for part in (raw or "").split(","):
        if ":" not in part:
            continue
        key, slug = part.split(":", 1)
        m = SWAP_RX.match(key.strip())
        if m and re.fullmatch(r"[a-z0-9-]{3,80}", slug.strip()):
            out[(int(m.group(1)), m.group(2), int(m.group(3)))] = slug.strip()
    return out


def encode_swaps(swaps: dict) -> str:
    return ",".join(f"d{d}-{m}-{i}:{s}" for (d, m, i), s in sorted(swaps.items()))


def resolve(plan: dict, catalogs: dict, swaps: dict) -> tuple[list[dict], list[str]]:
    """Дни плана с учётом замен. Недопустимая замена игнорируется с пояснением."""
    notes, days = [], []
    for n, day in enumerate(plan["days"], 1):
        row = {}
        for meal in MEALS:
            dishes = []
            for i, ref in enumerate(day[meal]):
                site = ref["site"]
                slug = swaps.get((n, meal, i), ref["slug"])
                item = catalogs[site]["items"].get(slug)
                if not item or item["category"] not in MEAL_CATEGORIES[meal]:
                    notes.append(f"Замена «{slug}» для дня {n} не подходит — оставлено исходное блюдо.")
                    slug, item = ref["slug"], catalogs[site]["items"][ref["slug"]]
                dishes.append(
                    {
                        "site": site,
                        "slug": slug,
                        "item": item,
                        "swapped": slug != ref["slug"],
                        "original": ref["slug"],
                        "key": f"d{n}-{meal}-{i}",
                    }
                )
            row[meal] = dishes
        days.append(row)
    return days, notes


def custom_days(catalogs: dict, picks: dict[tuple[int, str], str]) -> tuple[list[dict], list[str]]:
    """Своя неделя: по одному блюду на приём пищи; блюдо — только из каталога и только своей категории."""
    notes, days = [], []
    items = catalogs["food-daily"]["items"]
    for n in range(1, 8):
        row = {}
        for meal in MEALS:
            slug = picks.get((n, meal))
            it = items.get(slug) if slug else None
            if slug and (not it or it["category"] not in MEAL_CATEGORIES[meal]):
                notes.append(f"«{slug}» не подходит для дня {n} ({MEALS[meal].lower()}) — пропущено.")
                it = None
            row[meal] = (
                [
                    {
                        "site": "food-daily",
                        "slug": slug,
                        "item": it,
                        "swapped": False,
                        "original": slug,
                        "key": f"d{n}-{meal}",
                    }
                ]
                if it
                else []
            )
        days.append(row)
    return days, notes


def alternatives(catalogs: dict, site: str, meal: str) -> list[dict]:
    return sorted(
        (x for x in catalogs[site]["items"].values() if x["category"] in MEAL_CATEGORIES[meal]),
        key=lambda x: x["title"],
    )


def fmt(q: float) -> str:
    if abs(q - round(q)) < 0.05:
        return str(int(round(q)))
    return (f"{q:.1f}" if q < 10 else f"{q:.0f}").replace(".", ",")


# Один и тот же продукт под разными названиями в рецептах. Только явные
# совпадения — «сливки 33%» и «сливки» не объединяются: это разные продукты.
SAME_PRODUCT = [
    (re.compile(r"^(куриное яйцо|куриные яйца|яйца|яйцо)$"), "Куриные яйца"),
    (re.compile(r"^(лук|репчатый лук|лук репчатый)$"), "Лук репчатый"),
    (re.compile(r"^(морковь|морковка)$"), "Морковь"),
    (re.compile(r"^(картофель|картошка)$"), "Картофель"),
    (re.compile(r"^(сливочное масло|масло сливочное)$"), "Сливочное масло"),
    (re.compile(r"^(растительное масло|масло растительное)$"), "Растительное масло"),
    (
        re.compile(r"^(чёрный молотый перец|черный молотый перец|молотый черный перец|молотый чёрный перец)$"),
        "Чёрный молотый перец",
    ),
    (re.compile(r"^(пшеничная мука|мука)$"), "Пшеничная мука"),
]
NOT_BOUGHT = re.compile(r"^(вода|кипяток)$")


def product_name(raw: str) -> str:
    n = re.sub(r"\s+", " ", raw.strip().lower().replace("ё", "е"))
    for rx, name in SAME_PRODUCT:
        if rx.match(n.replace("е", "е")):
            return name
    return raw.strip()


def shopping_list(days: list[dict], people: int) -> dict:
    """Сумма по всем блюдам недели. Ключ — (название в нижнем регистре, единица)."""
    rows: dict[tuple[str, str], dict] = OrderedDict()
    loose: dict[str, dict] = OrderedDict()
    for day in days:
        for meal in MEALS:
            for dish in day[meal]:
                it = dish["item"]
                k = people / it["servings"] if it["servings"] else None
                for ing in it["ingredients"]:
                    name = product_name(ing["name"])
                    key = name.lower().replace("ё", "е")
                    if NOT_BOUGHT.match(key):
                        continue
                    if ing["unit"] == "to_taste" or ing["quantity"] is None or k is None:
                        e = loose.setdefault(key, {"name": name, "recipes": []})
                        e["recipes"].append(it["title"])
                        continue
                    e = rows.setdefault(
                        (key, ing["unit"]),
                        {"name": name, "unit": ing["unit"], "qty": 0.0, "qty_max": 0.0, "ranged": False, "recipes": []},
                    )
                    e["qty"] += ing["quantity"] * k
                    e["qty_max"] += (ing["quantity_max"] or ing["quantity"]) * k
                    e["ranged"] = e["ranged"] or bool(ing["quantity_max"])
                    e["recipes"].append(it["title"])
    items = []
    for (_, unit), e in sorted(rows.items(), key=lambda kv: kv[1]["name"].lower()):
        amount = fmt(e["qty"]) + (f"–{fmt(e['qty_max'])}" if e["ranged"] else "")
        hint = None
        if (
            unit in ("pcs", "head", "clove", "piece", "can", "pack", "bunch")
            and abs(e["qty_max"] - round(e["qty_max"])) > 0.05
        ):
            hint = f"купить ≈{int(-(-e['qty_max'] // 1))}"  # штучное — вверх до целого
        items.append(
            {
                "name": e["name"],
                "amount": f"{amount} {UNITS.get(unit, unit)}",
                "unit": unit,
                "hint": hint,
                "recipes": sorted(set(e["recipes"])),
            }
        )
    to_taste = [
        {"name": e["name"], "recipes": sorted(set(e["recipes"]))}
        for e in sorted(loose.values(), key=lambda e: e["name"].lower())
    ]
    return {"items": items, "to_taste": to_taste}
