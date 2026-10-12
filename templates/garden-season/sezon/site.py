"""Модель garden-season: месяц × регион → сезонная работа; культуры, типы работ, подборки, поиск."""

from __future__ import annotations

import json
import re
from pathlib import Path

import yaml

from sezon.content import CROPS, MONTH_SLUG, MONTHS_RU, REGIONS, TYPES

ROOT = Path(__file__).resolve().parents[1]
REGION_NOTE = {
    "or-all": "Пункт календаря OSU без указания района — для штата Орегон в целом; сам OSU оговаривает, что советы подходят не для всех его районов.",
    "or-west": "Западный Орегон — пункт календаря OSU с пометкой «Western Oregon».",
    "or-east": "Центральный и восточный Орегон — пункт календаря OSU с пометкой о центральной или восточной части штата.",
    "or-local": "Отдельный район Орегона — пункт календаря OSU с названием района (долины, побережье, высокогорье).",
    "uk": "Великобритания — сроки из руководств RHS; RHS сама различает более мягкие и более холодные районы.",
}
SOURCE_KIND = {"university": "Университетский справочник", "organization": "Садоводческая организация"}


def stem(w: str) -> str:
    return w[:5] if len(w) > 5 else w


def words(s: str) -> list[str]:
    return re.findall(r"[a-zа-яё0-9]+", s.lower().replace("ё", "е"))


class Work:
    def __init__(self, raw: dict, sources: dict):
        self.raw = raw
        for k in (
            "slug",
            "title",
            "type",
            "summary",
            "applies",
            "timing",
            "steps",
            "limits",
            "checklist",
            "version",
            "published_at",
            "updated_at",
            "review_status",
        ):
            setattr(self, k, raw[k])
        self.crop = raw.get("crop")
        self.need = raw.get("need", [])
        self.calc = raw.get("calc", [])
        self.related_slugs = raw.get("related", [])
        self.sources = [sources[s] for s in raw["sources"]]
        self.src_index = {s["id"]: i + 1 for i, s in enumerate(self.sources)}
        self.url = f"/rabota/{self.slug}/"
        self.type_label = TYPES[self.type]
        self.crop_label = CROPS.get(self.crop) if self.crop else None
        self.months = sorted({t["month"] for t in self.timing if t.get("month")})
        self.regions = list(dict.fromkeys(t["region"] for t in self.timing))
        self.when = self._when(sources)
        self.search_text = " ".join(
            [self.title, self.summary, self.applies, self.type_label, self.crop_label or ""]
            + [x["text"] for x in self.steps]
            + [MONTHS_RU[m - 1] for m in self.months]
        )

    def _when(self, sources: dict) -> list[dict]:
        """Строки «месяц — регион — что» для таблицы сроков, с номером источника."""
        out = []
        for t in self.timing:
            src = sources[t["src"]]
            item = next(x for x in src.get("items", []) + src.get("quotes", []) if x["id"] == t["item"])
            out.append(
                {
                    "month": t.get("month"),
                    "region": t["region"],
                    "label": item.get("region_label"),
                    "when": item.get("when"),
                    "src": t["src"],
                }
            )
        return sorted(out, key=lambda x: (x["month"] or 13, list(REGIONS).index(x["region"])))

    def limits_of(self, kind: str) -> list[dict]:
        return [x for x in self.limits if x["kind"] == kind]

    def refs(self, x: dict) -> list[int]:
        return sorted({self.src_index[r["src"]] for r in x.get("refs", [])})


class Site:
    def __init__(self, content: Path | None = None):
        self.cfg = yaml.safe_load((ROOT / "config" / "site.yaml").read_text())
        data = json.loads((content or ROOT / "data" / "content.json").read_text())
        if data["site_id"] != self.cfg["site_id"]:
            raise PermissionError("контент другого сайта")
        self.sources = data["sources"]
        self.works = [Work(x, self.sources) for x in data["items"]]
        self.by_slug = {w.slug: w for w in self.works}
        self.osu_by_month = {s["month"]: s for s in self.sources.values() if s.get("month")}
        cols = yaml.safe_load((ROOT / "config" / "collections.yaml").read_text())["collections"]
        self.collections = {}
        for c in cols:
            items = [w for w in self.works if self._match(w, c)]
            if len(items) >= 2:
                self.collections[c["slug"]] = {**c, "items": items}

    @staticmethod
    def _match(w: Work, c: dict) -> bool:
        if "months" in c and not set(w.months) & set(c["months"]):
            return False
        if "types" in c and w.type not in c["types"]:
            return False
        return not ("crops" in c and w.crop not in c["crops"])

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

    def month_slug(self, m: int) -> str:
        return MONTH_SLUG[m - 1]

    def month_of(self, slug: str) -> int | None:
        return MONTH_SLUG.index(slug) + 1 if slug in MONTH_SLUG else None

    def in_month(self, m: int, region: str | None = None, typ: str | None = None) -> list[Work]:
        out = []
        for w in self.works:
            hit = [t for t in w.timing if t.get("month") == m and (not region or t["region"] == region)]
            if hit and (not typ or w.type == typ):
                out.append(w)
        return out

    def by_region_in_month(self, m: int) -> dict[str, list[Work]]:
        out = {}
        for r in REGIONS:
            ws = self.in_month(m, r)
            if ws:
                out[r] = ws
        return out

    def for_crop(self, c: str) -> list[Work]:
        return [w for w in self.works if w.crop == c]

    def crops(self) -> dict[str, list[Work]]:
        return {c: self.for_crop(c) for c in CROPS if self.for_crop(c)}

    def for_type(self, t: str) -> list[Work]:
        return [w for w in self.works if w.type == t]

    def for_region(self, r: str) -> list[Work]:
        return [w for w in self.works if r in w.regions]

    def crop_grid(self, c: str) -> dict[str, dict[int, list[Work]]]:
        """Регион → месяц → работы: таблица сроков культуры без смешивания регионов."""
        grid: dict[str, dict[int, list[Work]]] = {}
        for w in self.for_crop(c):
            for t in w.timing:
                if t.get("month"):
                    grid.setdefault(t["region"], {}).setdefault(t["month"], [])
                    if w not in grid[t["region"]][t["month"]]:
                        grid[t["region"]][t["month"]].append(w)
        return {r: grid[r] for r in REGIONS if r in grid}

    def region_timeline(self, r: str, typ: str | None = None, crop: str | None = None) -> dict[int, list[Work]]:
        """Месяц → работы ТОЛЬКО со сроками этого региона (без подмешивания сроков других регионов)."""
        out: dict[int, list[Work]] = {}
        for w in self.works:
            if (typ and w.type != typ) or (crop and w.crop != crop):
                continue
            for t in w.timing:
                if t["region"] == r and t.get("month") and w not in out.setdefault(t["month"], []):
                    out[t["month"]].append(w)
        return dict(sorted(out.items()))

    def region_seasonal(self, r: str) -> list[Work]:
        """Работы со сроком «по сезону» (цитата без месяца) для региона."""
        return [w for w in self.works if any(t["region"] == r and not t.get("month") for t in w.timing)]

    def related(self, w: Work) -> list[Work]:
        return [self.by_slug[s] for s in w.related_slugs if s in self.by_slug]

    def search(self, q: str) -> list[Work]:
        qs = [stem(x) for x in words(q)]
        if not qs:
            return []
        out = []
        for w in self.works:
            ws = {stem(x) for x in words(w.search_text)}
            if all(any(x.startswith(s) for x in ws) for s in qs):
                out.append(w)
        return sorted(out, key=lambda w: w.title)

    def used_sources(self) -> list[dict]:
        return sorted(self.sources.values(), key=lambda s: (s["publisher"], s.get("month") or 0, s["name"]))
