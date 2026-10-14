"""Модель представления food-baking. Единственный вход — data/content.json."""

from __future__ import annotations

import json
import math
import re
from pathlib import Path

import yaml

from .drafts import DOUGH_LABELS

ROOT = Path(__file__).resolve().parents[1]

GROUPS = {
    "keks": "Кексы",
    "hleb": "Хлеб",
    "pirog": "Пироги",
    "pechene": "Печенье",
    "zavarnoe": "Заварные пирожные",
    "tort": "Торты",
    "bulochki": "Булочки",
    "sloyki": "Слойки",
}
TAGS = {
    "limon": "Лимон",
    "shokolad": "Шоколад",
    "sliva": "Слива",
    "yabloki": "Яблоки",
    "tykva": "Тыква",
    "orehi": "Орехи",
    "banan": "Банан",
    "vishnya": "Вишня",
    "vinograd": "Виноград",
    "syr": "Сыр",
    "k-chayu": "К чаю",
    "prazdnik": "К празднику",
    "nesladkaya-vypechka": "Несладкая выпечка",
    "bez-muki": "Без муки",
    "bez-pshenichnoj-muki": "Без пшеничной муки",
    "bez-vypechki": "Без духовки",
}
UNITS = {
    "g": "г",
    "kg": "кг",
    "ml": "мл",
    "l": "л",
    "pcs": "шт.",
    "tbsp": "ст. л.",
    "tsp": "ч. л.",
    "cup": "стак.",
    "pinch": "щеп.",
    "pack": "пачка",
    "clove": "зуб.",
}


def norm(s: str) -> str:
    s = s.lower().replace("ё", "е")
    return re.sub(r"\s+", " ", re.sub(r"[^\w\s-]+", " ", s)).strip()


def qty(q, unit) -> str:
    if unit == "to_taste":
        return "по вкусу"
    if q is None:
        return "—"
    frac = {0.25: "¼", 0.5: "½", 0.75: "¾"}
    w, r = int(q), round(q - int(q), 2)
    s = (str(w) if w else "") + frac[r] if r in frac else (str(int(q)) if q == int(q) else str(q).replace(".", ","))
    return f"{s} {UNITS.get(unit or '', '')}".strip()


def minutes(m) -> str:
    if not m:
        return ""
    h, mm = divmod(int(m), 60)
    parts = ([f"{h} ч"] if h else []) + ([f"{mm} мин"] if mm else [])
    return " ".join(parts)


class Recipe:
    def __init__(self, raw: dict):
        self.raw = raw
        for k in (
            "slug",
            "title",
            "intro",
            "tags",
            "servings",
            "oven",
            "steps",
            "pitfalls",
            "source",
            "version",
            "published_at",
            "updated_at",
            "dough",
            "group",
            "seo_title",
            "seo_description",
            "review_status",
        ):
            setattr(self, k, raw[k])
        self.url = f"/recept/{self.slug}/"
        self.times = raw["times"]
        self.ingredients = [
            {"name": i["name"], "amount": qty(i["quantity"], i["unit"]), "weighed": i["unit"] in ("g", "kg", "ml", "l")}
            for i in raw["ingredients"]
        ]

    @property
    def group_label(self) -> str:
        return GROUPS.get(self.group, self.group)

    @property
    def dough_label(self) -> str | None:
        return DOUGH_LABELS[self.dough][0] if self.dough else None

    @property
    def temps(self) -> list[int]:
        return sorted({t["value_c"] for t in self.oven["temperatures"]}, key=lambda t: -t)

    @property
    def total(self) -> str:
        return minutes(self.times["total_minutes"])

    @property
    def form(self) -> str | None:
        f = self.oven["forms"]
        if not f:
            return None
        # «Форму для кекса» / «формы диаметром 20 см» → именительный падеж для подписи
        return re.sub(r"^[Фф]орм[уые]\b", "Форма", f[0]["text"]).replace("противень", "Противень", 1)

    @property
    def timers(self) -> list[dict]:
        """Таймеры — только из времени выпекания, названного в шаге источника."""
        out = []
        for t in self.oven["bake_times"]:
            n = next((k for k, s in enumerate(self.steps) if t["step"] in s["src"]), None)
            if n is not None:
                out.append({"minutes": t["min"], "max": t["max"], "step": n + 1})
        return out

    @property
    def search_text(self) -> str:
        return norm(
            " ".join([self.title] + [i["name"] for i in self.ingredients] + [TAGS.get(t, t) for t in self.tags])
        )


class Site:
    def __init__(self, content: Path | None = None, config: Path | None = None):
        self.cfg = yaml.safe_load((config or ROOT / "config" / "site.yaml").read_text())
        data = json.loads((content or ROOT / "data" / "content.json").read_text())
        if data["site_id"] != self.cfg["site_id"]:
            raise PermissionError("контент принадлежит другому сайту")
        self.recipes = [Recipe(x) for x in data["items"]]
        self.by_slug = {r.slug: r for r in self.recipes}

    @property
    def origin(self) -> str:
        o = self.cfg["origin"][self.cfg["mode"]]
        if not o:
            raise RuntimeError(f"origin для режима {self.cfg['mode']} не задан (BLOCKED_INPUT)")
        return o.rstrip("/")

    @property
    def indexable(self) -> bool:
        return (
            self.cfg["mode"] == "production"
            and bool(self.cfg["production_authorized"])
            and bool(self.cfg["origin"]["production"])
        )

    def abs(self, path: str) -> str:
        return self.origin + path

    def doughs(self) -> dict[str, list[Recipe]]:
        """Вид теста получает страницу при ≥2 рецептах."""
        out: dict[str, list[Recipe]] = {}
        for r in self.recipes:
            if r.dough:
                out.setdefault(r.dough, []).append(r)
        return {k: v for k, v in out.items() if len(v) >= 2}

    def pitfalls_for(self, dough: str) -> list[tuple[Recipe, dict]]:
        return [(r, p) for r in self.doughs().get(dough, []) for p in r.pitfalls]

    def tags(self) -> dict[str, list[Recipe]]:
        out: dict[str, list[Recipe]] = {}
        for r in self.recipes:
            for t in r.tags:
                out.setdefault(t, []).append(r)
        return {k: v for k, v in out.items() if len(v) >= 2 and k in TAGS}

    def tag_links(self, r: Recipe) -> list[tuple[str, str]]:
        live = self.tags()
        return [(f"/teg/{t}/", TAGS[t]) for t in r.tags if t in live]

    def search(self, q: str) -> list[Recipe]:
        words = norm(q).split()
        # без морфологии: для слов длиннее 5 букв сравнивается основа без окончания («заварной» ~ «заварного»)
        return [
            r
            for r in self.recipes
            if words and all(w in r.search_text or (len(w) > 5 and w[:-2] in r.search_text) for w in words)
        ]

    def filter(self, dough: str = "", oven: str = "") -> list[Recipe]:
        items = self.recipes
        if dough:
            items = [r for r in items if r.dough == dough]
        if oven == "net":
            items = [r for r in items if not r.temps]
        elif oven == "da":
            items = [r for r in items if r.temps]
        return items

    def page(self, items: list, n: int) -> tuple[list, int]:
        per = self.cfg["per_page"]
        return items[(n - 1) * per : n * per], max(1, math.ceil(len(items) / per))
