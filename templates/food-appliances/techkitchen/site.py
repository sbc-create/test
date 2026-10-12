"""Модель представления food-appliances: прибор → категория → рецепт; режимы."""

from __future__ import annotations

import json
import re
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
APPLIANCES = {
    "multivarka": (
        "Мультиварка",
        "Чаша с программами: жарка, тушение, выпечка, крупы. Режимы и время — из каждого рецепта.",
    ),
    "aerogril": ("Аэрогриль", "Горячий воздух вместо масла: температура и минуты — из каждого рецепта."),
}
CATEGORIES = {
    "kurica": "Курица",
    "svinina": "Свинина",
    "ryba": "Рыба",
    "moreprodukty": "Морепродукты",
    "farsh": "Фарш",
    "ris": "Рис",
    "kartofel": "Картофель",
    "tvorog": "Творог",
    "yajca": "Яйца",
    "syr": "Сыр",
    "zavtrak": "Завтрак",
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
    "clove": "зуб.",
    "bunch": "пучок",
    "sprig": "веточка",
    "head": "гол.",
    "piece": "кус.",
}
TRANSLIT = str.maketrans(
    {
        "а": "a",
        "б": "b",
        "в": "v",
        "г": "g",
        "д": "d",
        "е": "e",
        "ё": "e",
        "ж": "zh",
        "з": "z",
        "и": "i",
        "й": "j",
        "к": "k",
        "л": "l",
        "м": "m",
        "н": "n",
        "о": "o",
        "п": "p",
        "р": "r",
        "с": "s",
        "т": "t",
        "у": "u",
        "ф": "f",
        "х": "h",
        "ц": "c",
        "ч": "ch",
        "ш": "sh",
        "щ": "sch",
        "ы": "y",
        "э": "e",
        "ю": "yu",
        "я": "ya",
        "ь": "",
        "ъ": "",
    }
)


def mode_slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower().translate(TRANSLIT)).strip("-")


def norm(s: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^\w\s-]+", " ", s.lower().replace("ё", "е"))).strip()


def amount(q, u) -> str:
    if u == "to_taste":
        return "по вкусу"
    if q is None:
        return "—"
    s = str(int(q)) if q == int(q) else str(q).replace(".", ",")
    return f"{s} {UNITS.get(u or '', '')}".strip()


class Recipe:
    def __init__(self, raw: dict):
        self.raw = raw
        for k in (
            "slug",
            "title",
            "intro",
            "appliance",
            "tags",
            "servings",
            "steps",
            "source",
            "version",
            "published_at",
            "updated_at",
            "seo_title",
            "seo_description",
            "modes",
            "temperatures",
            "appliance_times",
        ):
            setattr(self, k, raw[k])
        self.url = f"/recept/{self.slug}/"
        self.total = raw["times"]["total_minutes"]
        self.ingredients = [{"name": i["name"], "amount": amount(i["quantity"], i["unit"])} for i in raw["ingredients"]]

    @property
    def appliance_label(self) -> str:
        return APPLIANCES[self.appliance][0]

    @property
    def mode_names(self) -> list[str]:
        return list(dict.fromkeys(m["name"].capitalize() for m in self.modes))

    @property
    def step_settings(self) -> dict[int, list[dict]]:
        """Номер шага (с 1) → настройки прибора, которые источник называет в этом шаге: режим, температура, время."""
        out: dict[int, list[dict]] = {}
        for m in self.modes:
            out.setdefault(m["step"], []).append({"kind": "mode", "label": "Режим", "value": f"«{m['name']}»"})
        for t in self.temperatures:
            out.setdefault(t["step"], []).append(
                {"kind": "temp", "label": "Температура", "value": f"{t['value_c']} °C"}
            )
        for t in self.appliance_times:
            v = f"{t['min']}–{t['max']} мин" if t["max"] else f"{t['min']} мин"
            out.setdefault(t["step"], []).append({"kind": "time", "label": "Время", "value": v, "minutes": t["min"]})
        return out

    @property
    def time_label(self) -> str:
        return (
            ", ".join(f"{t['min']}–{t['max']}" if t["max"] else str(t["min"]) for t in self.appliance_times) + " мин"
            if self.appliance_times
            else ""
        )

    @property
    def search_text(self) -> str:
        return norm(
            " ".join([self.title, self.appliance_label] + [i["name"] for i in self.ingredients] + self.mode_names)
        )


class Site:
    def __init__(self, content: Path | None = None):
        self.cfg = yaml.safe_load((ROOT / "config" / "site.yaml").read_text())
        data = json.loads((content or ROOT / "data" / "content.json").read_text())
        if data["site_id"] != self.cfg["site_id"]:
            raise PermissionError("контент другого сайта")
        self.recipes = [Recipe(x) for x in data["items"]]
        self.by_slug = {r.slug: r for r in self.recipes}

    @property
    def indexable(self) -> bool:
        return (
            self.cfg["mode"] == "production"
            and bool(self.cfg["production_authorized"])
            and bool(self.cfg["origin"]["production"])
        )

    def abs(self, path: str) -> str:
        o = self.cfg["origin"][self.cfg["mode"]]
        if not o:
            raise RuntimeError("origin не задан (BLOCKED_INPUT)")
        return o.rstrip("/") + path

    def for_appliance(self, a: str) -> list[Recipe]:
        return [r for r in self.recipes if r.appliance == a]

    def categories(self, a: str) -> dict[str, list[Recipe]]:
        out: dict[str, list[Recipe]] = {}
        for r in self.for_appliance(a):
            for t in r.tags:
                if t in CATEGORIES:
                    out.setdefault(t, []).append(r)
        return {k: v for k, v in out.items() if len(v) >= 2}

    def modes(self) -> dict[str, dict]:
        """Режим → рецепты, где он назван; параметры у каждого рецепта свои. Страница — при ≥2 рецептах."""
        out: dict[str, dict] = {}
        for r in self.recipes:
            for name in r.mode_names:
                key = f"{r.appliance}-{mode_slug(name)}"
                e = out.setdefault(key, {"appliance": r.appliance, "name": name, "recipes": []})
                if r not in e["recipes"]:
                    e["recipes"].append(r)
        return {k: v for k, v in out.items() if len(v["recipes"]) >= 2}

    def search(self, q: str) -> list[Recipe]:
        words = norm(q).split()
        return [
            r
            for r in self.recipes
            if words and all(w in r.search_text or (len(w) > 5 and w[:-2] in r.search_text) for w in words)
        ]
