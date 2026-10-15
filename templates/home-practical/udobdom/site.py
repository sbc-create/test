"""Модель представления home-practical: помещение → задача → инструкция; подборки, теги, поиск."""

from __future__ import annotations

import json
import re
from pathlib import Path

import yaml

from udobdom.content import ROOMS, TAGS, TASKS

ROOT = Path(__file__).resolve().parents[1]
ROOM_LEDE = {
    "kuhnya": "Шкафы, ящики и контейнеры для продуктов.",
    "prihozhaya": "Обувь, верхняя одежда и всё, что нужно у двери.",
    "spalnya": "Комоды, шкафы и мелочи, которые теряются в ящиках.",
    "gostinaya": "Стеллажи, полки и следы от крепежа на стенах.",
    "vannaya": "Навесные шкафы и хранение во влажном помещении.",
    "rabochee-mesto": "Бумаги и мелочи под столом и рядом с ним.",
}
SOURCE_KIND = {"manufacturer": "Производитель", "organization": "Профильная организация"}


def stem(w: str) -> str:
    return w[:5] if len(w) > 5 else w


def words(s: str) -> list[str]:
    return re.findall(r"[a-zа-яё0-9]+", s.lower().replace("ё", "е"))


class Material:
    def __init__(self, raw: dict, sources: dict):
        self.raw = raw
        for k in (
            "slug",
            "title",
            "room",
            "task",
            "summary",
            "applies",
            "need",
            "steps",
            "limits",
            "checklist",
            "version",
            "published_at",
            "updated_at",
            "review_status",
        ):
            setattr(self, k, raw[k])
        self.not_for = raw.get("not_for")
        self.tags = raw.get("tags", [])
        self.calc = raw.get("calc", [])
        self.related_slugs = raw.get("related", [])
        self.sources = [sources[s] for s in raw["sources"]]
        self.src_index = {s["id"]: i + 1 for i, s in enumerate(self.sources)}
        self.url = f"/instrukciya/{self.slug}/"
        self.room_label = ROOMS[self.room]
        self.task_label = TASKS[self.task]
        self.manufacturer = [x for x in self.limits if x["kind"] == "manufacturer"]
        self.organization = [x for x in self.limits if x["kind"] == "organization"]
        self.editorial = [x for x in self.limits if x["kind"] == "editorial"]
        self.passport = self._passport()
        self.search_text = " ".join(
            [self.title, self.summary, self.applies, self.room_label, self.task_label]
            + [TAGS[t] for t in self.tags]
            + [x["text"] for x in self.need + self.steps]
        )

    def _passport(self) -> list[dict]:
        """Размеры и нагрузки производителя — первым блоком инструкции, с номером источника."""
        out = []
        for s in self.sources:
            for k, v in s.get("measures", {}).items():
                out.append(
                    {
                        "label": MEASURE_RU.get(k, k),
                        "value": ru_value(v),
                        "src": s["id"],
                        "load": k.lower().startswith("max"),
                    }
                )
        return out


def ru_value(v: str) -> str:
    v = re.sub(r"(\d)\.(\d)", r"\1,\2", v)
    return re.sub(r"\b(cm|mm|kg|l)\b", lambda m: {"cm": "см", "mm": "мм", "kg": "кг", "l": "л"}[m.group(1)], v)


MEASURE_RU = {
    "Width": "Ширина",
    "Depth": "Глубина",
    "Height": "Высота",
    "Length": "Длина",
    "Thickness": "Толщина",
    "Volume": "Объём",
    "Max. load": "Макс. нагрузка",
    "Max. load/shelf": "Макс. нагрузка на полку",
    "Max. load/drawer": "Макс. нагрузка на ящик",
    "Depth of drawer (inside)": "Глубина ящика внутри",
    "Width of drawer (inside)": "Ширина ящика внутри",
    "Drawer pull-out": "Выдвижение ящика",
    "Storage capacity": "Объём хранения",
    "Free height under furniture": "Свободная высота под мебелью",
}


class Site:
    def __init__(self, content: Path | None = None):
        self.cfg = yaml.safe_load((ROOT / "config" / "site.yaml").read_text())
        data = json.loads((content or ROOT / "data" / "content.json").read_text())
        if data["site_id"] != self.cfg["site_id"]:
            raise PermissionError("контент другого сайта")
        self.sources = data["sources"]
        self.materials = [Material(x, self.sources) for x in data["items"]]
        self.by_slug = {m.slug: m for m in self.materials}
        cols = yaml.safe_load((ROOT / "config" / "collections.yaml").read_text())["collections"]
        self.collections = {c["slug"]: {**c, "items": self.with_tag(c["tag"])} for c in cols}
        self.collections = {k: v for k, v in self.collections.items() if len(v["items"]) >= 2}

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

    def related(self, m: Material) -> list[Material]:
        return [self.by_slug[s] for s in m.related_slugs if s in self.by_slug]

    def in_room(self, room: str) -> list[Material]:
        return [m for m in self.materials if m.room == room]

    def for_task(self, task: str) -> list[Material]:
        return [m for m in self.materials if m.task == task]

    def with_tag(self, tag: str) -> list[Material]:
        return [m for m in self.materials if tag in m.tags]

    def tags(self) -> dict[str, list[Material]]:
        """Страницы тегов: ≥2 материала и тег не совпадает с подборкой (иначе — дубль подборки)."""
        backed = {c["tag"] for c in self.collections.values()}
        out = {t: self.with_tag(t) for t in TAGS if t not in backed}
        return {t: v for t, v in out.items() if len(v) >= 2}

    def tag_url(self, tag: str) -> str | None:
        for c in self.collections.values():
            if c["tag"] == tag:
                return f"/podborki/{c['slug']}/"
        return f"/teg/{tag}/" if tag in self.tags() else None

    def filter(self, room: str | None, task: str | None) -> list[Material]:
        return [m for m in self.materials if (not room or m.room == room) and (not task or m.task == task)]

    def search(self, q: str) -> list[Material]:
        qs = [stem(w) for w in words(q)]
        if not qs:
            return []
        scored = []
        for m in self.materials:
            ws = {stem(w) for w in words(m.search_text)}
            title = {stem(w) for w in words(m.title)}
            if all(any(x.startswith(w) for x in ws) for w in qs):
                scored.append((-sum(any(x.startswith(w) for x in title) for w in qs), m.title, m))
        return [m for *_, m in sorted(scored, key=lambda t: (t[0], t[1]))]

    def used_sources(self) -> list[dict]:
        return sorted(self.sources.values(), key=lambda s: (s["kind"], s["name"]))
