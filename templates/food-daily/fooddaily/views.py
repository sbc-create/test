"""Провайдер данных и модели представления food-daily.

Шаблоны получают только эти модели — ни БД, ни HTTP к источникам, ни
очередей (граница шаблона, factory/contracts/template_boundary.py).
Источник данных — снимок data/content-snapshot.json.
"""

from __future__ import annotations

import json
import math
import os
import re
from dataclasses import dataclass, field
from functools import cached_property
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]

CATEGORIES = {
    "zavtraki": ("Завтраки", "Сырники, оладьи, каши и яйца — то, что успеваешь утром."),
    "supy": ("Супы", "Супы на каждый день: на бульоне, на воде и супы-пюре."),
    "vtorye-blyuda": ("Вторые блюда", "Котлеты, курица, рыба, плов и паста на ужин."),
    "garniry": ("Гарниры", "Крупы и овощи, которые можно подать отдельно или к мясу."),
    "salaty": ("Салаты", "Салаты из свежих овощей и сытные салаты к обеду."),
    "zakuski": ("Закуски", "Быстрые перекусы и блюда в лаваше."),
}

TAGS = {
    "tvorog": ("Творог", "product"),
    "kefir": ("Кефир", "product"),
    "moloko": ("Молоко", "product"),
    "yajca": ("Яйца", "product"),
    "tykva": ("Тыква", "product"),
    "pshyono": ("Пшено", "product"),
    "kurica": ("Курица", "product"),
    "syr": ("Сыр", "product"),
    "farsh": ("Фарш", "product"),
    "chechevica": ("Чечевица", "product"),
    "pomidory": ("Помидоры", "product"),
    "ris": ("Рис", "product"),
    "makarony": ("Макароны", "product"),
    "svinina": ("Свинина", "product"),
    "ryba": ("Рыба", "product"),
    "grechka": ("Гречка", "product"),
    "griby": ("Грибы", "product"),
    "kapusta": ("Капуста", "product"),
    "ovoshchi": ("Овощи", "product"),
    "na-skovorode": ("На сковороде", "method"),
    "v-duhovke": ("В духовке", "method"),
    "varka": ("Варка", "method"),
    "tushenie": ("Тушение", "method"),
    "na-paru": ("На пару", "method"),
    "blender": ("С блендером", "method"),
    "bez-varki": ("Без варки", "method"),
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
    "clove": "зуб.",
    "pinch": "щеп.",
    "bunch": "пучок",
    "slice": "ломт.",
    "sprig": "веточка",
    "can": "банка",
    "head": "гол.",
    "leaf": "лист",
    "piece": "кус.",
    "pack": "пачка",
}

TIME_BUCKETS = {
    "do-20": ("до 20 минут", 0, 20),
    "do-40": ("до 40 минут", 0, 40),
    "do-60": ("до часа", 0, 60),
    "bolshe-chasa": ("больше часа", 61, 10**6),
}

# Подборки: правило — по фактам и тегам, не ручной список. Подборка
# существует, только если в неё попадают ≥3 рецепта.
COLLECTIONS = {
    "bystro-do-30-minut": (
        "Быстро: до 30 минут",
        "Рецепты, у которых по данным источника на всё уходит не больше получаса.",
        lambda r: r.total_minutes is not None and r.total_minutes <= 30,
    ),
    "zavtraki-iz-tvoroga": (
        "Завтраки из творога",
        "Сырники, запеканка и ленивые вареники.",
        lambda r: "tvorog" in r.tags,
    ),
    "s-kuricej": (
        "С курицей",
        "Супы, вторые блюда и салаты, где главный продукт — курица.",
        lambda r: "kurica" in r.tags,
    ),
    "osen-s-tykvoj": (
        "Осенью: с тыквой",
        "Каши, супы и выпечка к сезону тыквы.",
        lambda r: "tykva" in r.tags,
    ),
    "uzhin-na-skovorode": (
        "Ужин на одной сковороде",
        "Вторые блюда и гарниры, которые готовятся на плите.",
        lambda r: "na-skovorode" in r.tags and r.category in ("vtorye-blyuda", "garniry"),
    ),
}


# «Куриное яйцо», «куриный желток» — это яйца, а не мясо курицы: при сопоставлении продуктов прилагательное
# убирается, иначе запрос «курица» (основа «кури») находит блины и оладьи.
EGG = re.compile(r"\bкурин(?:ое|ые|ый|ых|ого|ом|ым|ыми|ой|ая|ую)\s+(?=(?:яйц|яиц|желт|белк|бело))")


def norm(s: str) -> str:
    """Нормализация для поиска: регистр, ё→е, пробелы и знаки; «куриное яйцо» → «яйцо»."""
    s = s.lower().replace("ё", "е")
    s = re.sub(r"[^\w\s-]+", " ", s)
    s = EGG.sub("", s)
    return re.sub(r"\s+", " ", s).strip()


# Поиск по словам: слово запроса совпадает с НАЧАЛОМ слова рецепта, расхождение допустимо только окончанием
# («тыквой» ~ «тыква», «сырники» ~ «сырник»); части слова в середине («пече» в «купечески») не совпадают.
ENDINGS = sorted(
    (
        "ами ями ого его ому ему ыми ими ой ей ий ый ая яя ое ее ые ие ую юю "
        "ах ях ов ев ом ем ам ям а я о е у ю ы и ь"
    ).split(),
    key=len,
    reverse=True,
)
# «печень» (субпродукт) и «печенье» (выпечка) различаются только окончанием — разводим явно
LIVER = re.compile(r"^печен(ь|и|ью|ями|ям|ях)$|^печенк")
COOKIE = re.compile(r"^печень[еяю]|^печений")


STOP = frozenset("с со и в во на из по без для к от а".split())


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


# Подбор «что есть дома»: продукт сравнивается со ВСЕМ составом рецепта (по названию строки), а не с темами.
# (ключ: название, группа, выражение по нормализованному названию строки состава)
PANTRY_GROUPS = ("Молочное и яйца", "Мясо и рыба", "Крупы, мука, макароны", "Овощи, грибы, зелень")
PRODUCTS = {
    "tvorog": ("Творог", 0, r"\bтворог\b"),
    "kefir": ("Кефир", 0, r"\bкефир"),
    "moloko": ("Молоко", 0, r"^молоко\b"),
    "smetana": ("Сметана", 0, r"\bсметан"),
    "slivki": ("Сливки", 0, r"^сливки\b"),
    "slivochnoe-maslo": ("Сливочное масло", 0, r"\bсливочное масло"),
    "syr": ("Сыр", 0, r"\bсыр\b|\bсырки\b|брынз"),
    "yajca": ("Яйца", 0, r"\bяйц|\bяиц|\bяичн|\bжелтк|\bжелток"),
    "kurica": ("Курица", 1, r"\bкурин|\bкуриц"),
    "svinina": ("Свинина", 1, r"\bсвинин"),
    "farsh": ("Фарш", 1, r"\bфарш"),
    "bekon": ("Бекон", 1, r"\bбекон"),
    "ryba": ("Рыба", 1, r"\bрыб|\bминтай"),
    "ris": ("Рис", 2, r"^рис$"),
    "grechka": ("Гречка", 2, r"гречнев|гречк"),
    "pshyono": ("Пшено", 2, r"^пшено\b"),
    "chechevica": ("Чечевица", 2, r"чечевиц"),
    "makarony": ("Макароны, лапша", 2, r"макарон|\bлапш"),
    "muka": ("Пшеничная мука", 2, r"(?:пшеничн|блинн)\w* мук"),
    "manka": ("Манная крупа", 2, r"\bманн"),
    "kartofel": ("Картофель", 3, r"картоф"),
    "luk": ("Лук репчатый", 3, r"^(?:репчатый |красный )?лук$"),
    "morkov": ("Морковь", 3, r"^морковь$"),
    "kapusta": ("Капуста", 3, r"белокочанн"),
    "cvetnaya-kapusta": ("Цветная капуста", 3, r"цветная капуста"),
    "pomidory": ("Помидоры", 3, r"помидор"),
    "ogurcy": ("Огурцы", 3, r"\bогур"),
    "sladkij-perec": ("Сладкий перец", 3, r"сладкий перец"),
    "tykva": ("Тыква", 3, r"тыкв"),
    "griby": ("Грибы", 3, r"гриб|шампиньон"),
    "chesnok": ("Чеснок", 3, r"^чеснок"),
    "zelen": ("Зелень", 3, r"зелень|укроп|петрушк|зеленый лук"),
}
PRODUCT_RX = {k: re.compile(v[2]) for k, v in PRODUCTS.items()}
# Базовое: обычно есть дома, но в «понадобится» не смешивается и показывается отдельно — проверить самому
BASIC = re.compile(
    r"^(?:соль|вода|сахар|сода|крахмал|уксус|перец)$|\bсоль\b|растительное масло|подсолнечное масло|оливковое масло"
    r"|молот|дробл|душист|\bзира\b|куркум|паприк|приправ|прованск|для подачи"
)


def product_of(name: str) -> str | None:
    """Ключ продукта из списка подбора для строки состава (None — не из списка)."""
    n = norm(name)
    return next((k for k, rx in PRODUCT_RX.items() if rx.search(n)), None)


def fmt_qty(q: float | None) -> str:
    if q is None:
        return ""
    frac = {0.25: "¼", 0.5: "½", 0.75: "¾", 0.333: "⅓", 0.667: "⅔"}
    whole, rest = int(q), round(q - int(q), 3)
    if rest in frac:
        return (str(whole) if whole else "") + frac[rest]
    if abs(q - round(q)) < 0.01:
        return str(int(round(q)))
    return f"{q:.1f}".rstrip("0").rstrip(".").replace(".", ",")


@dataclass
class Ingredient:
    name: str
    quantity: float | None
    quantity_max: float | None
    unit: str | None
    scalable: bool

    @property
    def amount(self) -> str:
        if self.unit == "to_taste":
            return "по вкусу"
        if self.quantity is None:
            return ""
        q = fmt_qty(self.quantity) + (("–" + fmt_qty(self.quantity_max)) if self.quantity_max else "")
        return f"{q} {UNITS.get(self.unit or '', '')}".strip()

    @property
    def unit_label(self) -> str:
        return UNITS.get(self.unit or "", "")

    @property
    def jsonld(self) -> str:
        return f"{self.name}, {self.amount}" if self.amount else self.name


@dataclass
class Recipe:
    raw: dict
    related: list = field(default_factory=list)

    @property
    def slug(self):
        return self.raw["slug"]

    @property
    def url(self):
        return f"/recept/{self.slug}/"

    @property
    def d(self):
        return self.raw["draft"]

    @property
    def f(self):
        return self.raw["facts"]

    @property
    def title(self):
        return self.d["title"]

    @property
    def category(self):
        return self.d["category"]

    @property
    def category_label(self):
        return CATEGORIES[self.category][0]

    @property
    def tags(self):
        return self.d["tags"]

    @property
    def servings(self):
        return self.f["servings"]

    @property
    def yield_n(self) -> int | None:
        """Выход в порциях для показа и пересчёта. «1 порция» у источника — значение по умолчанию (суп из 500 г тыквы
        и 4 картофелин, шаурма из двух лавашей): выход считается не указанным, пересчёт — кратный (×½, ×2)."""
        return self.servings if self.servings and self.servings > 1 else None

    @property
    def nutrition(self) -> dict | None:
        """Примерная калорийность — только принятый расчёт (ккал на порцию, метод, источник данных) и известное
        число порций; иначе None: калорийность не показывается и не оценивается «на глаз»."""
        n = self.f.get("nutrition") or {}
        kcal = n.get("kcal_per_serving")
        ok = isinstance(kcal, int | float) and kcal > 0 and self.servings
        if not (ok and n.get("data_source") and n.get("method")):
            return None
        return {**n, "kcal": round(kcal), "kcal_total": round(kcal * self.servings)}

    @property
    def total_minutes(self):
        return self.f["total_minutes"]

    @property
    def prep_minutes(self):
        return self.f["prep_minutes"]

    @property
    def cook_minutes(self):
        return self.f["cook_minutes"]

    @property
    def published_at(self):
        return self.raw["published_at"]

    @property
    def updated_at(self):
        return self.raw["updated_at"]

    @property
    def source(self):
        return self.raw["source"]

    @property
    def image(self) -> dict | None:
        """Изображение блюда — только запись из data/media/images.json с правами и происхождением; иначе None."""
        return self.raw.get("_image")

    @property
    def has_video(self):
        return any(m["kind"] == "video" for m in self.raw["media"])

    @cached_property
    def ingredients(self) -> list[tuple[Ingredient, str]]:
        out = []
        for row in self.d["ingredients"]:
            fi = self.f["ingredients"][row["fact_index"]]
            out.append(
                (
                    Ingredient(
                        row["display_name"],
                        fi["quantity"],
                        fi["quantity_max"],
                        fi["unit"],
                        fi["scalable"],
                    ),
                    row.get("group") or "",
                )
            )
        return out

    @property
    def substitutions(self):
        """Только замены, которые называет сам источник (source_steps); остальное — в редакционных заметках."""
        names = {i["fact_index"]: i["display_name"] for i in self.d["ingredients"]}
        return [(names[s["from_index"]], s) for s in self.d.get("substitutions") or [] if s.get("source_steps")]

    @property
    def tips(self) -> list[dict]:
        """Только подсказки, подтверждённые шагами источника (source_steps)."""
        return [t for t in self.d.get("tips") or [] if t.get("source_steps")]

    @property
    def lede(self) -> str:
        """Первая фраза вступления — для карточки."""
        intro = self.d["intro"].strip()
        m = re.match(r"(.+?[.!?])(\s|$)", intro)
        return (m.group(1) if m else intro)[:160]

    @cached_property
    def key_ingredients(self) -> list[str]:
        """Главные продукты блюда: без соли, специй, масла и воды; до трёх."""
        skip = re.compile(
            r"^(соль|перец|черн|молот|масло|растительн|сливочное масло|вода|сахар|специи|приправ|зелень|"
            r"каменная соль|чёрн|душист|прованск|паприка|куркума|зира|сода|уксус)",
            re.I,
        )
        out = []
        for i, _ in self.ingredients:
            n = i.name.split("(")[0].strip()
            if not skip.match(n) and n not in out:
                out.append(n)
        return out[:3]

    @property
    def time_label(self) -> str:
        return minutes(self.total_minutes)

    @cached_property
    def search_text(self) -> str:
        names = " ".join(i.name for i, _ in self.ingredients)
        return norm(f"{self.title} {names} {' '.join(TAGS.get(t, (t,))[0] for t in self.tags)}")

    @cached_property
    def search_tokens(self) -> frozenset[str]:
        return frozenset(t for t in re.split(r"[\s-]+", self.search_text) if t)

    @cached_property
    def title_tokens(self) -> frozenset[str]:
        return frozenset(t for t in re.split(r"[\s-]+", norm(self.title)) if t)

    @cached_property
    def ingredient_text(self) -> str:
        return norm(" ".join(i.name for i, _ in self.ingredients))


def minutes(m: int | None) -> str:
    if not m:
        return ""
    h, mm = divmod(int(m), 60)
    if h and mm:
        return f"{h} ч {mm} мин"
    return f"{h} ч" if h else f"{mm} мин"


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


def ru_date(iso: str | None) -> str:
    """2026-10-11 → «11 октября 2026»."""
    if not iso:
        return ""
    y, m, d = iso[:10].split("-")
    return f"{int(d)} {MONTHS[int(m) - 1]} {y}"


# Сезонный блок главной: подборка, у которой по месяцу есть сезон. Показывается, только если подборка существует
# (в ней ≥3 рецептов) — без выдуманных «сезонных» блюд.
SEASONAL = {9: "osen-s-tykvoj", 10: "osen-s-tykvoj", 11: "osen-s-tykvoj"}


def iso_duration(m: int | None) -> str | None:
    if not m:
        return None
    h, mm = divmod(int(m), 60)
    return "PT" + (f"{h}H" if h else "") + (f"{mm}M" if mm else "")


IMAGE_KINDS = ("photo", "illustration")
IMAGE_REQUIRED = ("file", "width", "height", "widths", "kind", "alt", "source", "license")


def load_images(by_slug: dict, path: Path | None = None) -> dict:
    """data/media/images.json: slug → {file, width, height, widths, kind, alt, source, license, author?}.
    Запись без прав (source, license) или для неизвестного рецепта — ошибка, а не тихий пропуск:
    изображение без установленного происхождения на сайт не попадает."""
    p = path or ROOT / "data" / "media" / "images.json"
    if not p.exists():
        return {}
    data = json.loads(p.read_text())
    out = {}
    for slug, e in data.get("items", {}).items():
        missing = [k for k in IMAGE_REQUIRED if not e.get(k)]
        if missing or e["kind"] not in IMAGE_KINDS or slug not in by_slug:
            raise ValueError(f"images.json: {slug}: нет {missing} или неверный kind/slug")
        for w in e["widths"]:
            if not (ROOT / "static" / "media" / f"{e['file']}-{w}.webp").is_file():
                raise FileNotFoundError(f"static/media/{e['file']}-{w}.webp")
        by_slug[slug].raw["_image"] = e
        out[slug] = e
    return out


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
    def __init__(self, snapshot_path: Path | None = None, config_path: Path | None = None):
        self.cfg = yaml.safe_load((config_path or config_file()).read_text())
        snap = json.loads((snapshot_path or ROOT / "data" / "content-snapshot.json").read_text())
        if snap["site_id"] != self.cfg["site_id"]:
            raise PermissionError("снимок принадлежит другому сайту")
        self.generated_at = snap["generated_at"]
        self.recipes = sorted(
            (Recipe(x) for x in snap["items"]),
            key=lambda r: (r.published_at or "", r.slug),
            reverse=True,
        )
        self.by_slug = {r.slug: r for r in self.recipes}
        self.images = load_images(self.by_slug)
        self.articles = {}
        for ap in sorted((ROOT / "data" / "articles").glob("*.json")):
            a = json.loads(ap.read_text())
            if a["site_id"] != self.cfg["site_id"]:
                raise PermissionError(f"статья {ap.name} принадлежит другому сайту")
            self.articles[a["slug"]] = a
        for r in self.recipes:
            r.related = self._related(r)

    # ---- адреса -----------------------------------------------------
    @property
    def mode(self) -> str:
        return self.cfg["mode"]

    @property
    def origin(self) -> str:
        o = self.cfg["origin"][self.mode]
        if not o:
            raise RuntimeError(f"origin для режима {self.mode} не задан (BLOCKED_INPUT)")
        return o.rstrip("/")

    @property
    def indexable(self) -> bool:
        return (
            self.mode == "production"
            and bool(self.cfg.get("production_authorized"))
            and bool(self.cfg["origin"]["production"])
        )

    def abs(self, path: str) -> str:
        return self.origin + path

    # ---- выборки ------------------------------------------------------
    def _related(self, r: Recipe) -> list[Recipe]:
        def score(o: Recipe) -> float:
            return (2 if o.category == r.category else 0) + len(set(o.tags) & set(r.tags))

        cands = [o for o in self.recipes if o.slug != r.slug]
        cands.sort(key=lambda o: (-score(o), o.slug))
        return [o for o in cands if score(o) > 0][:3]  # один ряд сетки 3/2/1

    def category(self, key: str) -> list[Recipe]:
        return [r for r in self.recipes if r.category == key]

    def tag(self, key: str) -> list[Recipe]:
        return [r for r in self.recipes if key in r.tags]

    def tag_pages(self) -> dict[str, list[Recipe]]:
        mn = self.cfg["seo"]["tag_page_min_items"]
        return {t: self.tag(t) for t in TAGS if len(self.tag(t)) >= mn}

    def tag_indexable(self, key: str) -> bool:
        return len(self.tag(key)) >= self.cfg["seo"]["tag_index_min_items"]

    def collections(self) -> dict[str, tuple[str, str, list[Recipe]]]:
        out = {}
        for k, (title, desc, pred) in COLLECTIONS.items():
            items = [r for r in self.recipes if pred(r)]
            if len(items) >= 3:
                out[k] = (title, desc, items)
        return out

    def search(self, q: str) -> list[Recipe]:
        words = [w for w in norm(q).split() if w not in STOP] or norm(q).split()
        if not words:
            return []
        hits = []
        for r in self.recipes:
            if all(word_matches(w, r.search_tokens) for w in words):
                in_title = all(word_matches(w, r.title_tokens) for w in words)
                hits.append((0 if in_title else 1, r))
        return [r for _, r in sorted(hits, key=lambda x: (x[0], x[1].title))]

    def filter(self, *, product: str = "", time: str = "", category: str = "") -> list[Recipe]:
        items = self.recipes
        if category in CATEGORIES:
            items = [r for r in items if r.category == category]
        if product:
            p = norm(product)
            items = [
                r
                for r in items
                if p in r.ingredient_text or p in r.tags or (len(p) > 4 and p[:-2] in r.ingredient_text)
            ]
        if time in TIME_BUCKETS:
            _, lo, hi = TIME_BUCKETS[time]
            items = [r for r in items if r.total_minutes is not None and lo <= r.total_minutes <= hi]
        return items

    @staticmethod
    def tag_path(key: str) -> str:
        return f"/{'produkty' if TAGS[key][1] == 'product' else 'sposob'}/{key}/"

    def tag_links(self, r: Recipe) -> list[tuple[str, str]]:
        """Только теги, у которых есть работающая страница — без декоративного текста."""
        pages = self.tag_pages()
        return [(self.tag_path(t), TAGS[t][0]) for t in r.tags if t in pages]

    def readiness_by_category(self) -> list[tuple[str, list[tuple[Recipe, str]]]]:
        out = []
        for key, (label, _) in CATEGORIES.items():
            rows = [
                (r, st["readiness_cue"]) for r in self.category(key) for st in r.d["steps"] if st.get("readiness_cue")
            ]
            if rows:
                out.append((label, rows))
        return out

    def all_substitutions(self) -> list[tuple[Recipe, str, dict]]:
        return [(r, name, sub) for r in self.recipes for name, sub in r.substitutions]

    def tag_index(self, kind: str) -> list[tuple[str, str, int, bool]]:
        return [
            (self.tag_path(t), TAGS[t][0], len(items), self.tag_indexable(t))
            for t, items in self.tag_pages().items()
            if TAGS[t][1] == kind
        ]

    def product_options(self) -> list[tuple[str, str]]:
        return [(t, TAGS[t][0]) for t, items in self.tag_pages().items() if TAGS[t][1] == "product"]

    def fridge_products(self) -> list[tuple[str, str, int, int]]:
        """Продукты подбора, которые есть в составе хотя бы одного рецепта: (ключ, название, группа, число рецептов)."""
        n = {k: 0 for k in PRODUCTS}
        for r in self.recipes:
            for k in {product_of(i.name) for i, _ in r.ingredients} - {None}:
                n[k] += 1
        return [(k, label, g, n[k]) for k, (label, g, _) in PRODUCTS.items() if n[k]]

    def fridge(self, have: list[str]) -> list[dict]:
        """Рецепты, в составе которых есть хотя бы один выбранный продукт. Сравнивается каждая строка состава:
        есть (выбранные продукты), понадобится (остальное), базовое (соль, масло, специи — показывается отдельно).
        Сначала больше совпавших продуктов, затем меньше недостающего, затем быстрее."""
        want = set(have)
        rows = []
        for r in self.recipes:
            got, need, basic, keys = [], [], [], []
            for i, _ in r.ingredients:
                k = product_of(i.name)
                if k in want:
                    got.append(i.name)
                    keys.append(k)
                elif k is None and BASIC.search(norm(i.name)):
                    basic.append(i.name)
                else:
                    need.append(i.name)
            if got:
                rows.append(
                    {
                        "r": r,
                        "got": got,
                        "need": need,
                        "basic": basic,
                        "keys": sorted(set(keys)),
                        "total": len(r.ingredients),
                    }
                )
        rows.sort(key=lambda x: (-len(x["keys"]), len(x["need"]), x["r"].total_minutes or 10**6, x["r"].title))
        return rows

    def party(self, slugs: list[str], guests: int) -> dict:
        """Несколько рецептов на компанию: каждый пересчитан с его порций на гостей (как в пересчёте порций на странице
        рецепта: непересчитываемые продукты не меняются), одинаковые название и единица складываются."""
        rs = [self.by_slug[s] for s in dict.fromkeys(slugs) if s in self.by_slug]
        rows: dict = {}
        loose: dict = {}
        for r in rs:
            k = guests / r.yield_n if r.yield_n else 1  # выход не указан — количества как в рецепте
            for i, _ in r.ingredients:
                key = norm(i.name)
                if i.unit == "to_taste" or i.quantity is None or k is None:
                    loose.setdefault(key, {"name": i.name, "recipes": []})["recipes"].append(r.title)
                    continue
                f = k if i.scalable else 1
                e = rows.setdefault(
                    (key, i.unit),
                    {
                        "name": i.name,
                        "unit": i.unit,
                        "q": 0.0,
                        "qmax": 0.0,
                        "ranged": False,
                        "fixed": False,
                        "recipes": [],
                    },
                )
                e["q"] += i.quantity * f
                e["qmax"] += (i.quantity_max or i.quantity) * f
                e["ranged"] = e["ranged"] or bool(i.quantity_max)
                e["fixed"] = e["fixed"] or not i.scalable
                e["recipes"].append(r.title)
        items = []
        for e in sorted(rows.values(), key=lambda e: e["name"].lower()):
            amt = fmt_qty(e["q"]) + (("–" + fmt_qty(e["qmax"])) if e["ranged"] else "")
            items.append({**e, "amount": f"{amt} {UNITS.get(e['unit'] or '', '')}".strip()})
        return {"recipes": rs, "items": items, "loose": sorted(loose.values(), key=lambda e: e["name"].lower())}

    def page(self, items: list, n: int) -> tuple[list, int, int]:
        per = self.cfg["pagination"]["per_page"]
        pages = max(1, math.ceil(len(items) / per))
        return items[(n - 1) * per : n * per], n, pages
