"""Модель games-story: игра (по реестру) → главы → маршрут, механики, коллекционные предметы; видео; поиск."""

from __future__ import annotations

import json
import re
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
BERRY_RU = {
    "Strawberry": "красные клубники",
    "Golden Strawberries": "золотые клубники",
    "Forsaken City/Winged Gold Berry": "крылатая золотая клубника",
    "Farewell/Moon Berry": "лунная клубника",
}


def words(s: str) -> list[str]:
    return re.findall(r"[a-zа-яё0-9]+", s.lower().replace("ё", "е"))


class Guide:
    def __init__(self, raw: dict, sources: dict):
        self.raw = raw
        for k in ("slug", "game", "title", "summary", "checklist", "version", "published_at", "updated_at"):
            setattr(self, k, raw[k])
        self.mechanics, self.tips = raw.get("mechanics", []), raw.get("tips", [])
        self.src = sources[raw["src"]]
        self.also = [sources[s] for s in raw.get("also", [])]
        self.videos = [sources[v] for v in raw.get("videos", [])]
        self.related_slugs = raw.get("related", [])
        self.chapter = self.src.get("chapter")
        self.name = self.src["name"]
        self.checkpoints = self.src.get("checkpoints", [])
        self.berries = [
            {"label": BERRY_RU.get(b["kind"], b["kind"]), "count": b["count"]} for b in self.src.get("berries", [])
        ]
        self.red = next((b["count"] for b in self.src.get("berries", []) if b["kind"] == "Strawberry"), 0)
        self.sides = self.src.get("sides") or ""
        self.characters = self.src.get("characters", [])
        self.url = f"/igra/{self.game}/{self.slug}/"
        self.order = self.chapter if self.chapter is not None else (0 if self.slug == "prolog" else 7.5)
        self.search_text = " ".join(
            [self.title, self.summary, self.name, *self.mechanics, *self.checkpoints, *self.characters]
        )


class Site:
    def __init__(self, content: Path | None = None):
        self.cfg = yaml.safe_load((ROOT / "config" / "site.yaml").read_text())
        data = json.loads((content or ROOT / "data" / "content.json").read_text())
        if data["site_id"] != self.cfg["site_id"]:
            raise PermissionError("контент другого сайта")
        self.ownership = data["ownership"]
        self.sources = data["sources"]
        self.guides = sorted((Guide(x, self.sources) for x in data["items"]), key=lambda g: g.order)
        self.by_slug = {g.slug: g for g in self.guides}
        self.games = {k: v for k, v in self.ownership["games"].items() if v["owner"] == self.cfg["site_id"]}
        self.videos = [s for s in self.sources.values() if s["kind"] == "video"]

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

    def for_game(self, game: str) -> list[Guide]:
        return [g for g in self.guides if g.game == game]

    def red_total(self, game: str) -> int:
        return sum(g.red for g in self.for_game(game))

    def neighbours(self, g: Guide) -> tuple[Guide | None, Guide | None]:
        gs = self.for_game(g.game)
        i = gs.index(g)
        return (gs[i - 1] if i > 0 else None, gs[i + 1] if i + 1 < len(gs) else None)

    ITEM_TYPES = {
        "krasnye-klubniki": ("Красные клубники", "Strawberry"),
        "zolotye-klubniki": ("Золотые клубники", "Golden Strawberries"),
        "storony": ("Стороны A/B/C", None),
    }

    def by_item(self, game: str, t: str) -> list[tuple]:
        """Глава → значение для вида предмета (число клубник из источника или строка сторон)."""
        label, kind = self.ITEM_TYPES[t]
        out = []
        for g in self.for_game(game):
            if kind is None:
                if g.sides:
                    out.append((g, g.sides))
            else:
                n = next((b["count"] for b in g.src.get("berries", []) if b["kind"] == kind), 0)
                if n:
                    out.append((g, n))
        return out

    def side_letters(self, g: Guide) -> list[str]:
        return [x[-1] for x in re.findall(r"\d[ABC]", g.sides)]

    def sides_total(self, game: str) -> int:
        return sum(len(self.side_letters(g)) for g in self.for_game(game))

    def related(self, g: Guide) -> list[Guide]:
        return [self.by_slug[s] for s in g.related_slugs if s in self.by_slug]

    def search(self, q: str) -> list[Guide]:
        qs = [w[:5] for w in words(q)]
        if not qs:
            return []
        return [
            g
            for g in self.guides
            if all(any(x.startswith(s) for x in {w[:5] for w in words(g.search_text)}) for s in qs)
        ]
