"""Планировщик крафта (вариант craft-planner): сколько чего нужно на N штук предмета.

Всё считается из сетки источника: количество ингредиента = число занятых им слотов, выход = размер стопки результата.
Предмет без рецепта из материалов сайта — базовый: добывается, плавится или не описан.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

MAX_N = 64


@dataclass
class Step:
    entry: object
    crafts: int
    made: int
    need: int
    recipe: dict
    inputs: list = field(default_factory=list)  # [(entry, на один крафт, всего)]

    @property
    def surplus(self) -> int:
        return self.made - self.need


@dataclass
class Plan:
    target: object
    n: int
    steps: list  # от первого действия к последнему
    base: list  # [(entry, всего)]


def match(site, title: str):
    """Материал сайта для названия в слоте: точное имя или «<вид> Имя» (Oak Planks → Planks)."""
    for e in site.entries:
        if e.type in ("item", "resource") and (title == e.name or title.endswith(" " + e.name)):
            return e
    return None


def recipe_inputs(site, e) -> tuple[dict, list] | None:
    """Первый рецепт предмета, все слоты которого — материалы сайта: (рецепт, [(материал, штук на крафт)])."""
    for r in e.recipes:
        ents = [match(site, t) for t in r.get("slot_items", [])]
        if ents and all(ents) and e not in ents:
            per: dict = {}
            for x in ents:
                per[x] = per.get(x, 0) + 1
            return r, list(per.items())
    return None


def plan(site, e, n: int) -> Plan:
    if not 1 <= n <= MAX_N:
        raise ValueError(f"количество от 1 до {MAX_N}")
    order: list = []
    seen: set = set()

    def visit(x):
        if x in seen:
            return
        seen.add(x)
        ri = recipe_inputs(site, x)
        for y, _ in ri[1] if ri else []:
            visit(y)
        order.append(x)

    visit(e)
    demand = {e: n}
    steps, base = [], []
    for x in reversed(order):  # потребители раньше поставщиков
        need = demand.get(x, 0)
        ri = recipe_inputs(site, x)
        if not ri:
            base.append((x, need))
            continue
        r, per = ri
        crafts = math.ceil(need / r["count"])
        st = Step(x, crafts, crafts * r["count"], need, r)
        for y, q in per:
            demand[y] = demand.get(y, 0) + crafts * q
            st.inputs.append((y, q, crafts * q))
        steps.append(st)
    return Plan(e, n, list(reversed(steps)), base)


def uses(site, e) -> list[tuple]:
    """Куда идёт материал: [(предмет, штук материала на крафт, выход крафта)] по рецептам планировщика."""
    out = []
    for x in site.entries:
        ri = recipe_inputs(site, x)
        for y, q in ri[1] if ri else []:
            if y is e:
                out.append((x, q, ri[0]["count"]))
    return out
