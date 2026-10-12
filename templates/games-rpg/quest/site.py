"""Модель games-rpg: игра (по реестру) → разделы (персонажи, билды, квесты, механики) → материал; версия игры."""

from __future__ import annotations

import json
import re
from pathlib import Path

import yaml

from quest.content import TYPES

ROOT = Path(__file__).resolve().parents[1]
ABIL_RU = {
    "STR": "Сила",
    "DEX": "Ловкость",
    "CON": "Телосложение",
    "INT": "Интеллект",
    "WIS": "Мудрость",
    "CHA": "Харизма",
}
SECTION = {
    "character": "personazhi",
    "build": "bildy",
    "quest": "kvesty",
    "mechanic": "mehaniki",
    "item": "predmety",
    "version": "versiya",
}


def words(s: str) -> list[str]:
    return re.findall(r"[a-zа-яё0-9']+", s.lower().replace("ё", "е"))


class Entry:
    def __init__(self, raw: dict, sources: dict):
        self.raw = raw
        for k in ("slug", "game", "type", "title", "summary", "version", "published_at"):
            setattr(self, k, raw[k])
        self.points, self.tips, self.checklist = raw.get("points", []), raw.get("tips", []), raw.get("checklist", [])
        self.src = sources[raw["src"]]
        self.also = [sources[s] for s in raw.get("also", [])]
        self.related_slugs = raw.get("related", [])
        self.section = SECTION[self.type]
        self.url = f"/{self.game}/{self.section}/{self.slug}/"
        self.abilities = [(ABIL_RU[k], v) for k, v in self.src.get("abilities", {}).items()]
        self.progression = self.src.get("progression", [])
        self.stages = self.src.get("stages", [])
        self.patches = self.src.get("patches", [])
        self.item = self.src.get("item")
        self.search_text = " ".join([self.title, self.summary, self.src["name"], *self.points, *self.stages])


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

    def in_section(self, game: str, section: str) -> list[Entry]:
        return [e for e in self.entries if e.game == game and e.section == section]

    def sections(self, game: str) -> dict[str, tuple[str, list[Entry]]]:
        out = {}
        for t, label in TYPES.items():
            sec = SECTION[t]
            items = self.in_section(game, sec)
            if items and t != "version":
                out[sec] = (label, items)
        return out

    def characters(self, game: str) -> list[Entry]:
        return [e for e in self.entries if e.game == game and e.type == "character"]

    def sort_characters(self, game: str, key: str) -> list[Entry]:
        chars = self.characters(game)
        if key in ABIL_RU:
            return sorted(chars, key=lambda e: (-dict(e.src.get("abilities", {})).get(key, 0), e.title))
        return sorted(chars, key=lambda e: e.title)

    def party(self, game: str, slugs: list[str]) -> dict:
        """Сводка отряда: только факты источника — классы и наибольшее значение каждой характеристики в отряде."""
        members = [e for e in self.characters(game) if e.slug in slugs][:4]
        best = {}
        for k, ru in ABIL_RU.items():
            vals = [(e.src.get("abilities", {}).get(k, 0), e) for e in members]
            if vals:
                v = max(x[0] for x in vals)
                best[ru] = (v, [e for x, e in vals if x == v])  # при равенстве — все обладатели максимума
        return {"members": members, "classes": [e.points[0] for e in members if e.points], "best": best}

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
