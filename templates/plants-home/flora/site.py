"""Модель plants-home: вид → условия (свет, почва, уход) → проблемы; подборки, поиск."""

from __future__ import annotations

import json
import re
from pathlib import Path

import yaml

from flora.content import DRAINAGE, LIGHT, MAINT, POISON, PROBLEMS, PROPAG, TOPICS

ROOT = Path(__file__).resolve().parents[1]


def stem(w: str) -> str:
    return w[:5] if len(w) > 5 else w


def words(s: str) -> list[str]:
    return re.findall(r"[a-zа-яё0-9]+", s.lower().replace("ё", "е"))


class Plant:
    def __init__(self, raw: dict, src: dict):
        self.raw, self.src = raw, src
        for k in (
            "slug",
            "ru_name",
            "summary",
            "care",
            "checklist",
            "version",
            "published_at",
            "updated_at",
            "review_status",
        ):
            setattr(self, k, raw[k])
        self.problems = raw.get("problems", [])
        self.calc = raw.get("calc", [])
        self.related_slugs = raw.get("related", [])
        self.sci = src["name"]
        self.common_en = src.get("common_names", [])
        a = src.get("attrs", {})
        self.light = [LIGHT[x] for x in a.get("Light:", []) if x in LIGHT]
        self.light_slugs = [x[0] for x in self.light]
        self.drainage = [DRAINAGE.get(x, x) for x in a.get("Soil Drainage:", [])]
        self.maint_en = (a.get("Maintenance:") or [None])[0]
        self.maint = MAINT.get(self.maint_en) if self.maint_en else None
        self.propag = [PROPAG.get(x, x) for x in a.get("Recommended Propagation Strategy:", [])]
        self.poison = POISON.get((a.get("Poison Severity:") or [None])[0]) if a.get("Poison Severity:") else None
        self.poison_note = "non-toxic" in " ".join(src.get("description", [])).lower()
        self.topics = {x["topic"] for x in self.care}
        self.url = f"/rastenie/{self.slug}/"
        self.search_text = " ".join(
            [
                self.ru_name,
                self.sci,
                self.summary,
                *self.common_en,
                *[x["text"] for x in self.care],
                *[PROBLEMS[p["tag"]][0] for p in self.problems],
                *[x[1] for x in self.light],
            ]
        )

    def care_by_topic(self) -> list[tuple[str, list[dict]]]:
        return [(t, [x for x in self.care if x["topic"] == t]) for t in TOPICS if t in self.topics]


class Site:
    def __init__(self, content: Path | None = None):
        self.cfg = yaml.safe_load((ROOT / "config" / "site.yaml").read_text())
        data = json.loads((content or ROOT / "data" / "content.json").read_text())
        if data["site_id"] != self.cfg["site_id"]:
            raise PermissionError("контент другого сайта")
        self.sources = data["sources"]
        self.plants = sorted((Plant(x, self.sources[x["src"]]) for x in data["items"]), key=lambda p: p.ru_name)
        self.by_slug = {p.slug: p for p in self.plants}
        cols = yaml.safe_load((ROOT / "config" / "collections.yaml").read_text())["collections"]
        self.collections = {}
        for c in cols:
            items = [p for p in self.plants if self._match(p, c)]
            if len(items) >= 2:
                self.collections[c["slug"]] = {**c, "items": items}

    @staticmethod
    def _match(p: Plant, c: dict) -> bool:
        if "light" in c:
            return c["light"] in p.light_slugs
        if "maintenance" in c:
            return p.maint_en == c["maintenance"]
        if "topic" in c:
            return c["topic"] in p.topics
        return False

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

    def lights(self) -> dict[str, tuple]:
        out = {}
        for v in LIGHT.values():
            if any(v[0] in p.light_slugs for p in self.plants):
                out[v[0]] = v
        return out

    def with_light(self, slug: str) -> list[Plant]:
        return [p for p in self.plants if slug in p.light_slugs]

    def with_problem(self, tag: str) -> list[Plant]:
        return [p for p in self.plants if any(x["tag"] == tag for x in p.problems)]

    def problems(self) -> dict[str, list[Plant]]:
        out = {t: self.with_problem(t) for t in PROBLEMS}
        return {t: v for t, v in out.items() if len(v) >= 2}

    def filter(self, light: str | None, maint: str | None) -> list[Plant]:
        return [p for p in self.plants if (not light or light in p.light_slugs) and (not maint or p.maint_en == maint)]

    def related(self, p: Plant) -> list[Plant]:
        return [self.by_slug[s] for s in p.related_slugs if s in self.by_slug]

    def search(self, q: str) -> list[Plant]:
        qs = [stem(x) for x in words(q)]
        if not qs:
            return []
        out = []
        for p in self.plants:
            ws = {stem(x) for x in words(p.search_text)}
            if all(any(x.startswith(s) for x in ws) for s in qs):
                out.append(p)
        return out
