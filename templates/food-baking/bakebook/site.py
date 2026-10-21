"""Модель представления food-baking. Единственный вход — data/content.json."""

from __future__ import annotations

import json
import math
import os
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
    "deserty": "Десерты",
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


# «Куриное яйцо» — яйца, а не мясо курицы: прилагательное убирается, иначе «курица» находит всю выпечку на яйцах.
EGG = re.compile(r"\bкурин(?:ое|ые|ый|ых|ого|ом|ым|ыми|ой|ая|ую)\s+(?=(?:яйц|яиц|желт|белк|бело))")


def norm(s: str) -> str:
    s = EGG.sub("", re.sub(r"[^\w\s-]+", " ", s.lower().replace("ё", "е")))
    return re.sub(r"\s+", " ", s).strip()


# Поиск по словам: слово запроса совпадает с НАЧАЛОМ слова рецепта, расхождение допустимо только окончанием
# («кексы» ~ «кекс», «сливой» ~ «слива»); части слова в середине не совпадают.
ENDINGS = sorted(
    (
        "ами ями ого его ому ему ыми ими ой ей ий ый ая яя ое ее ые ие ую юю "
        "ах ях ов ев ом ем ам ям а я о е у ю ы и ь"
    ).split(),
    key=len,
    reverse=True,
)
STOP = frozenset("с со и в во на из по без для к от а".split())
# «печень» (субпродукт) и «печенье» (выпечка) различаются только окончанием — разводим явно
LIVER = re.compile(r"^печен(ь|и|ью|ями|ям|ях)$|^печенк")
COOKIE = re.compile(r"^печень[еяю]|^печений")


def stem(w: str) -> str:
    for e in ENDINGS:
        if w.endswith(e) and len(w) - len(e) >= 3:
            return w[: -len(e)]
    return w


def word_matches(w: str, tokens: frozenset[str]) -> bool:
    st = stem(w)
    for t in tokens:
        if t == w or (t.startswith(st) and (t[len(st) :] in ENDINGS or t == st)):
            if (LIVER.match(w) and COOKIE.match(t)) or (COOKIE.match(w) and LIVER.match(t)):
                continue
            return True
    return False


def qty(q, unit) -> str:
    if unit == "to_taste":
        return "по вкусу"
    if q is None:
        return "—"
    frac = {0.25: "¼", 0.5: "½", 0.75: "¾"}
    w, r = int(q), round(q - int(q), 2)
    s = (str(w) if w else "") + frac[r] if r in frac else (str(int(q)) if q == int(q) else str(q).replace(".", ","))
    return f"{s} {UNITS.get(unit or '', '')}".strip()


MONTHS = (
    "января",
    "февраля",
    "марта",
    "апреля",
    "мая",
    "июня",
    "июля",
    "августа",
    "сентября",
    "октября",
    "ноября",
    "декабря",
)

# Сезонная выпечка: продукты сезона по месяцам. Блок на главной — только из рецептов, где эти продукты есть.
SEASONS = {
    (9, 10, 11): ("Осенняя выпечка", ("tykva", "yabloki", "sliva")),
    (12, 1, 2): ("Зимняя выпечка", ("prazdnik", "orehi")),
    (6, 7, 8): ("Летняя выпечка", ("vishnya", "vinograd")),
}

IMAGE_KINDS = ("photo", "illustration")
IMAGE_REQUIRED = ("file", "width", "height", "widths", "kind", "alt", "source", "license")


def ru_date(iso: str | None) -> str:
    """2026-10-12 → «12 октября 2026»."""
    if not iso:
        return ""
    y, m, d = iso[:10].split("-")
    return f"{int(d)} {MONTHS[int(m) - 1]} {y}"


def load_images(by_slug: dict, path: Path | None = None) -> dict:
    """data/media/images.json: изображение блюда только с происхождением и правами; иначе — ошибка, а не пропуск."""
    p = path or ROOT / "data" / "media" / "images.json"
    if not p.exists():
        return {}
    out = {}
    for slug, e in json.loads(p.read_text()).get("items", {}).items():
        missing = [k for k in IMAGE_REQUIRED if not e.get(k)]
        if missing or e["kind"] not in IMAGE_KINDS or slug not in by_slug:
            raise ValueError(f"images.json: {slug}: нет {missing} или неверный kind/slug")
        for w in e["widths"]:
            if not (ROOT / "static" / "media" / f"{e['file']}-{w}.webp").is_file():
                raise FileNotFoundError(f"static/media/{e['file']}-{w}.webp")
        by_slug[slug].image = e
        out[slug] = e
    return out


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
        self.image: dict | None = None
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
    def lede(self) -> str:
        """Первая фраза вступления — для карточки."""
        m = re.match(r"(.+?[.!?])(\s|$)", self.intro.strip())
        return (m.group(1) if m else self.intro.strip())[:180]

    @property
    def group_url(self) -> str:
        return f"/recepty/{self.group}/"

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
    def flour_g(self) -> float | None:
        """Масса муки в граммах по составу источника (все виды муки в г/кг); None — если муки в граммах нет."""
        g = sum(
            i["quantity"] * (1000 if i["unit"] == "kg" else 1)
            for i in self.raw["ingredients"]
            if re.search(r"мук", i["name"], re.I) and i["unit"] in ("g", "kg") and i["quantity"]
        )
        return g or None

    @property
    def bench(self) -> list[dict]:
        """Строки рабочего листа: продукт, количество и пекарский процент (доля от массы муки) —
        только для продуктов в граммах; остальное без процента."""
        fl = self.flour_g
        out = []
        for raw, i in zip(self.raw["ingredients"], self.ingredients, strict=True):
            pct = None
            if fl and raw["unit"] in ("g", "kg") and raw["quantity"]:
                pct = round(raw["quantity"] * (1000 if raw["unit"] == "kg" else 1) / fl * 100)
            out.append({**i, "pct": pct})
        return out

    @property
    def bake_label(self) -> str | None:
        t = self.oven["bake_times"]
        if not t:
            return None
        return ", ".join(f"{x['min']}–{x['max']} мин" if x.get("max") else f"{x['min']} мин" for x in t)

    @property
    def search_text(self) -> str:
        return norm(
            " ".join([self.title] + [i["name"] for i in self.ingredients] + [TAGS.get(t, t) for t in self.tags])
        )


def config_file() -> Path:
    """config/site.yaml или файл конфигурации домена из SITE_CONFIG — только имя вида site.<имя>.yaml в config/:
    путь извне каталога config не принимается."""
    name = os.environ.get("SITE_CONFIG", "site.yaml")
    if not re.fullmatch(r"site(\.[a-z0-9-]+)?\.yaml", name):
        raise ValueError(f"SITE_CONFIG: недопустимое имя {name!r}")
    p = ROOT / "config" / name
    if not p.is_file():
        raise FileNotFoundError(p)
    return p


class Site:
    def __init__(self, content: Path | None = None, config: Path | None = None):
        self.cfg = yaml.safe_load((config or config_file()).read_text())
        data = json.loads((content or ROOT / "data" / "content.json").read_text())
        if data["site_id"] != self.cfg["site_id"]:
            raise PermissionError("контент принадлежит другому сайту")
        self.recipes = [Recipe(x) for x in data["items"]]
        self.by_slug = {r.slug: r for r in self.recipes}
        self.images = load_images(self.by_slug)

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

    def related(self, r: Recipe, n: int = 4) -> list[Recipe]:
        """Похожие: тот же раздел, тот же вид теста, общие темы; без совпадений — не показываются."""

        def score(o: Recipe) -> int:
            return (2 if o.group == r.group else 0) + (1 if r.dough and o.dough == r.dough else 0) + len(
                set(o.tags) & set(r.tags)
            )

        cands = sorted((o for o in self.recipes if o.slug != r.slug), key=lambda o: (-score(o), o.slug))
        return [o for o in cands if score(o) > 0][:n]

    def groups(self) -> dict[str, list[Recipe]]:
        """Разделы (кексы, хлеб…): только наполненные, в порядке GROUPS."""
        return {k: v for k in GROUPS if (v := [r for r in self.recipes if r.group == k])}

    @staticmethod
    def group_indexable(items: list) -> bool:
        return len(items) >= 2

    def season(self, month: int) -> tuple[str, list[tuple[str, str]], list[Recipe]] | None:
        """Сезонный блок: (заголовок, [(тег, подпись)], рецепты) — если по продуктам сезона есть ≥3 рецептов."""
        for months, (title, tags) in SEASONS.items():
            if month in months:
                items = [r for r in self.recipes if set(r.tags) & set(tags)]
                if len(items) >= 3:
                    live = self.tags()
                    return title, [(t, TAGS[t]) for t in tags if any(t in r.tags for r in items) and t in live], items
        return None

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
        words = [w for w in norm(q).split() if w not in STOP] or norm(q).split()
        if not words:
            return []
        hits = []
        for r in self.recipes:
            tokens = frozenset(t for t in re.split(r"[\s-]+", r.search_text) if t)
            if all(word_matches(w, tokens) for w in words):
                title = frozenset(t for t in re.split(r"[\s-]+", norm(r.title)) if t)
                hits.append((0 if all(word_matches(w, title) for w in words) else 1, r))
        return [r for _, r in sorted(hits, key=lambda x: (x[0], x[1].title))]

    def by_temp(self) -> list[tuple[int | None, list[Recipe]]]:
        """Рецепты по главной (первой по убыванию) температуре духовки; без духовки — в конце (None)."""
        groups: dict = {}
        for r in self.recipes:
            groups.setdefault(r.temps[0] if r.temps else None, []).append(r)
        return sorted(groups.items(), key=lambda kv: (kv[0] is None, -(kv[0] or 0)))

    def sorted_by(self, items: list[Recipe], key: str) -> list[Recipe]:
        if key == "temp":
            return sorted(items, key=lambda r: (not r.temps, -(r.temps[0] if r.temps else 0), r.title))
        if key == "vremya":
            t = lambda r: r.times["total_minutes"]  # noqa: E731
            return sorted(items, key=lambda r: (t(r) is None, t(r) or 0, r.title))
        if key == "nazvanie":
            return sorted(items, key=lambda r: r.title)
        return items

    def filter(self, dough: str = "", oven: str = "") -> list[Recipe]:
        items = self.recipes
        if dough:
            items = [r for r in items if r.dough == dough]
        if oven == "net":
            items = [r for r in items if not r.temps]
        elif oven == "da":
            items = [r for r in items if r.temps]
        return items

    def bake_set(self, slugs: list[str]) -> dict:
        """Несколько рецептов: общий список продуктов и порядок духовки — только арифметика над числами источника.
        Складываются строки с одинаковым названием и единицей (кг → г, л → мл); остальное — отдельными строками."""
        rs = [self.by_slug[s] for s in dict.fromkeys(slugs) if s in self.by_slug]
        conv = {"kg": ("g", 1000), "l": ("ml", 1000)}
        rows: dict = {}
        loose: dict = {}
        for r in rs:
            for i in r.raw["ingredients"]:
                name = i["name"].strip()
                key = name.lower().replace("ё", "е")
                if i["unit"] == "to_taste" or i["quantity"] is None:
                    loose.setdefault(key, {"name": name, "recipes": []})["recipes"].append(r.title)
                    continue
                unit, k = conv.get(i["unit"], (i["unit"], 1))
                e = rows.setdefault((key, unit), {"name": name, "unit": unit, "q": 0.0, "recipes": []})
                e["q"] += i["quantity"] * k
                e["recipes"].append(r.title)
        items = [
            {**e, "amount": qty(round(e["q"], 2), e["unit"])}
            for e in sorted(rows.values(), key=lambda e: e["name"].lower())
        ]
        oven: dict = {}
        for r in rs:
            oven.setdefault(r.temps[0] if r.temps else None, []).append(r)
        return {
            "recipes": rs,
            "items": items,
            "loose": sorted(loose.values(), key=lambda e: e["name"].lower()),
            "oven": sorted(oven.items(), key=lambda kv: (kv[0] is None, -(kv[0] or 0))),
        }

    def page(self, items: list, n: int) -> tuple[list, int]:
        per = self.cfg["per_page"]
        return items[(n - 1) * per : n * per], max(1, math.ceil(len(items) / per))
