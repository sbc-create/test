"""Модель games-survival: игра (по реестру) → ресурсы, предметы, биомы; рецепты и связи «из чего → во что» из источника."""

from __future__ import annotations

import json
import re
from pathlib import Path

import yaml

from craft.content import TYPES

ROOT = Path(__file__).resolve().parents[1]
SECTION = {"item": "predmety", "resource": "resursy", "biome": "biomy", "version": "versiya"}


def words(s: str) -> list[str]:
    return re.findall(r"[a-zа-яё0-9]+", s.lower().replace("ё", "е"))


def own_recipes(name: str, recipes: list[dict]) -> list[dict]:
    """Рецепты самого предмета страницы: результат совпадает с ним (или «<вид> Planks» для досок),
    но не производные вроде Copper Chest из Chest и не служебные строки «Iron → Iron Ingot»."""
    out = []
    for r in recipes:
        res, ing = r["result"], r["ingredients"]
        exact = res == name and name not in ing  # «Damaged Shield → Shield» — ремонт, а не крафт
        variant = res.endswith(" " + name) and name not in ing
        odd = len(ing.split()) == 1 and res.startswith(ing) and r["slots"] == 1 and r["count"] == 1
        if (exact or variant) and not odd and not (variant and ing.endswith(name)) and r not in out:
            out.append(r)
    return out


class Entry:
    def __init__(self, raw: dict, sources: dict):
        self.raw = raw
        for k in ("slug", "game", "type", "title", "summary", "version", "published_at"):
            setattr(self, k, raw[k])
        self.src = sources[raw["src"]]
        self.also = [sources[s] for s in raw.get("also", [])]
        self.related_slugs = raw.get("related", [])
        self.name = self.src["name"]
        self.section = SECTION[self.type]
        self.url = f"/{self.game}/{self.section}/{self.slug}/"
        self.recipes = own_recipes(self.name, self.src.get("recipes", []))
        self.search_text = " ".join([self.title, self.summary, self.name, *[r["ingredients"] for r in self.recipes]])


class Site:
    def __init__(self, content: Path | None = None):
        self.cfg = yaml.safe_load((ROOT / "config" / "site.yaml").read_text())
        data = json.loads((content or ROOT / "data" / "content.json").read_text())
        if data["site_id"] != self.cfg["site_id"]:
            raise PermissionError("контент другого сайта")
        self.ownership, self.sources = data["ownership"], data["sources"]
        self.entries = [Entry(x, self.sources) for x in data["items"]]
        self.by_slug = {e.slug: e for e in self.entries}
        self.games = {k: v for k, v in self.ownership["games"].items() if v["owner"] == self.cfg["site_id"]}
        self.version = next((e for e in self.entries if e.type == "version"), None)

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

    def sections(self, game: str) -> dict[str, tuple[str, list[Entry]]]:
        out = {}
        for t, label in TYPES.items():
            items = [e for e in self.entries if e.game == game and e.type == t]
            if items and t != "version":
                out[SECTION[t]] = (label, items)
        return out

    def made_from(self, e: Entry) -> list[Entry]:
        """Материалы сайта, названные в ингредиентах рецептов e (по тексту источника)."""
        ing = " ".join(r["ingredients"] for r in e.recipes)
        return [
            x
            for x in self.entries
            if x is not e and x.type in ("item", "resource") and re.search(r"\b" + re.escape(x.name.rstrip("s")), ing)
        ]

    def used_for(self, e: Entry) -> list[Entry]:
        """Обратная связь: материалы, в рецептах которых e названо ингредиентом."""
        return [x for x in self.entries if x is not e and e in self.made_from(x)]

    def related(self, e: Entry) -> list[Entry]:
        return [self.by_slug[s] for s in e.related_slugs if s in self.by_slug]

    def search(self, q: str) -> list[Entry]:
        qs = [w[:5] for w in words(q)]
        if not qs:
            return []
        return [
            e
            for e in self.entries
            if all(any(x.startswith(s) for x in {w[:5] for w in words(e.search_text)}) for s in qs)
        ]
