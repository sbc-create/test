"""Извлечение фактов рецепта: сначала JSON-LD Recipe, затем микроразметка.

Возвращает факты и замечания. Отсутствующее не угадывается: нет количества —
`quantity=None` и замечание; нет времени — время не заполняется.
Внешний HTML — данные, а не команды: ничего из страницы не исполняется и не
интерпретируется как инструкция.
"""

from __future__ import annotations

import hashlib
import html as htmllib
import json
import re
from dataclasses import asdict, dataclass, field
from html.parser import HTMLParser

PARSER_VERSION = "fd-extract/1.3"

UNITS = {
    "г": "g",
    "гр": "g",
    "грамм": "g",
    "граммов": "g",
    "кг": "kg",
    "мл": "ml",
    "л": "l",
    "литр": "l",
    "шт": "pcs",
    "штука": "pcs",
    "штуки": "pcs",
    "штук": "pcs",
    "ст. л.": "tbsp",
    "ст.л.": "tbsp",
    "ст. л": "tbsp",
    "ст.л": "tbsp",
    "ст. ложки": "tbsp",
    "ст. ложка": "tbsp",
    "столовая ложка": "tbsp",
    "столовые ложки": "tbsp",
    "столовых ложек": "tbsp",
    "ч. л.": "tsp",
    "ч.л.": "tsp",
    "ч. л": "tsp",
    "ч.л": "tsp",
    "ч. ложки": "tsp",
    "ч. ложка": "tsp",
    "чайная ложка": "tsp",
    "чайные ложки": "tsp",
    "чайных ложек": "tsp",
    "стакан": "cup",
    "стакана": "cup",
    "стаканов": "cup",
    "зубчик": "clove",
    "зубчика": "clove",
    "зубчиков": "clove",
    "щепотка": "pinch",
    "щепотки": "pinch",
    "пучок": "bunch",
    "пучка": "bunch",
    "пучков": "bunch",
    "ломтик": "slice",
    "ломтика": "slice",
    "ломтиков": "slice",
    "веточка": "sprig",
    "веточки": "sprig",
    "веточек": "sprig",
    "банка": "can",
    "банки": "can",
    "банок": "can",
    "головка": "head",
    "головки": "head",
    "головок": "head",
    "лист": "leaf",
    "листа": "leaf",
    "листов": "leaf",
    "кусок": "piece",
    "куска": "piece",
    "кусков": "piece",
    "стол.л": "tbsp",
    "стол. л": "tbsp",
    "чайн.л": "tsp",
    "чайн. л": "tsp",
    "ст": "cup",
    "штучки": "pcs",
    "пачка": "pack",
    "пачки": "pack",
    "пачек": "pack",
    "упаковка": "pack",
    "по вкусу": "to_taste",
}
UNIT_RX = "|".join(sorted((re.escape(u) for u in UNITS), key=len, reverse=True))
NUM = r"(\d+(?:[.,]\d+)?(?:\s*[-–]\s*\d+(?:[.,]\d+)?)?|\d+\s*/\s*\d+|½|¼|¾|⅓|⅔)"
FRACTIONS = {"½": 0.5, "¼": 0.25, "¾": 0.75, "⅓": 1 / 3, "⅔": 2 / 3}
# единицы, которые при пересчёте порций масштабируются как количество
SCALABLE = {
    "g",
    "kg",
    "ml",
    "l",
    "pcs",
    "tbsp",
    "tsp",
    "cup",
    "clove",
    "bunch",
    "slice",
    "sprig",
    "can",
    "head",
    "leaf",
    "piece",
    "pack",
    "pinch",
}
# Единица без числа означает одну: «Соль, щепотка» — это ровно одна щепотка.
SINGLE_UNIT = {
    "щепотка": "pinch",
    "пучок": "bunch",
    "веточка": "sprig",
    "зубчик": "clove",
    "ломтик": "slice",
    "кусок": "piece",
    "пачка": "pack",
    "банка": "can",
    "головка": "head",
    "стакан": "cup",
}


@dataclass
class Ingredient:
    raw: str
    name: str
    quantity: float | None
    quantity_max: float | None
    unit: str | None
    scalable: bool
    note: str | None = None


@dataclass
class Facts:
    source_url: str
    canonical_url: str | None
    title: str | None
    servings: int | None
    servings_raw: str | None
    prep_minutes: int | None
    cook_minutes: int | None
    total_minutes: int | None
    ingredients: list[Ingredient]
    steps: list[str]  # исходный текст шага — только закрытое хранилище
    category: str | None
    cuisine: str | None
    keywords: list[str]
    method_hints: list[str]
    image_present: bool
    extracted_with: str
    parser_version: str = PARSER_VERSION
    remarks: list[str] = field(default_factory=list)
    content_hash: str = ""

    def to_dict(self) -> dict:
        d = asdict(self)
        return d


def _num(s: str) -> float | None:
    s = s.strip().replace(",", ".")
    if s in FRACTIONS:
        return round(FRACTIONS[s], 3)
    if "/" in s:
        a, b = (x.strip() for x in s.split("/", 1))
        try:
            return round(float(a) / float(b), 3)
        except (ValueError, ZeroDivisionError):
            return None
    try:
        return float(s)
    except ValueError:
        return None


def parse_ingredient(raw: str) -> Ingredient:
    """«Сливки 33%-ные, 400 мл» / «Мука — 2 стакана» / «Соль по вкусу»."""
    text = re.sub(r"\s+", " ", htmllib.unescape(raw)).strip(" .;")
    name, qty, qmax, unit, note = text, None, None, None, None
    m = re.search(rf"[,—–:-]?\s*{NUM}\s*({UNIT_RX})?\.?\s*$", text, re.I)
    if m and m.start() > 0:
        name = text[: m.start()].strip(" ,—–:-")
        rng = m.group(1)
        if re.search(r"[-–]", rng) and "/" not in rng:
            a, b = re.split(r"\s*[-–]\s*", rng)
            qty, qmax = _num(a), _num(b)
        else:
            qty = _num(rng)
        unit = UNITS.get((m.group(2) or "").lower()) if m.group(2) else None
        if m.group(2) is None:
            unit = "pcs"
            note = "единица не указана — принята как штуки"
    else:
        m2 = re.search(
            r"[,—–:-]?\s*(по вкусу|для подачи|для жарки|для смазывания|по желанию|на кончике ножа)\s*$",
            text,
            re.I,
        )
        m3 = re.search(r"[,—–:-]\s*(" + "|".join(SINGLE_UNIT) + r")\s*$", text, re.I)
        if m3:
            name = text[: m3.start()].strip(" ,—–:-")
            qty, unit = 1.0, SINGLE_UNIT[m3.group(1).lower()]
            note = "количество «одна» следует из единицы без числа"
        elif m2:
            name = text[: m2.start()].strip(" ,—–:-")
            unit = "to_taste"
            note = m2.group(1).lower()
    scalable = unit in SCALABLE and qty is not None
    return Ingredient(
        raw=text,
        name=name,
        quantity=qty,
        quantity_max=qmax,
        unit=unit,
        scalable=scalable,
        note=note,
    )


def iso_minutes(v) -> int | None:
    if not v or not isinstance(v, str):
        return None
    m = re.fullmatch(r"P(?:(\d+)D)?T?(?:(\d+)H)?(?:(\d+)M)?(?:\d+S)?", v.strip())
    if not m or not any(m.groups()):
        return None
    d, h, mi = (int(x) if x else 0 for x in m.groups())
    total = d * 1440 + h * 60 + mi
    return total or None


def _servings(v) -> tuple[int | None, str | None]:
    if v is None:
        return None, None
    if isinstance(v, list):
        v = v[0] if v else None
    raw = str(v)
    m = re.search(r"\d+", raw)
    return (int(m.group()) if m else None), raw


def _steps(instr) -> list[str]:
    out: list[str] = []
    if isinstance(instr, str):
        parts = [p for p in re.split(r"\n+|(?<=\.)\s+(?=\d+\.)", instr) if p.strip()]
        return [_clean(p) for p in parts]
    for s in instr or []:
        if isinstance(s, str):
            out.append(_clean(s))
        elif isinstance(s, dict):
            if s.get("@type") == "HowToSection":
                out += _steps(s.get("itemListElement"))
            elif s.get("text"):
                out.append(_clean(s["text"]))
    return [s for s in out if s]


def _clean(s: str) -> str:
    s = re.sub(r"<[^>]+>", " ", htmllib.unescape(str(s)))
    return re.sub(r"\s+", " ", s).strip()


def _jsonld_blocks(page: str):
    for b in re.findall(r"<script[^>]+application/ld\+json[^>]*>(.*?)</script>", page, re.S | re.I):
        try:
            j = json.loads(b.strip())
        except json.JSONDecodeError:
            continue
        stack = j if isinstance(j, list) else [j]
        while stack:
            x = stack.pop(0)
            if isinstance(x, dict):
                if "@graph" in x:
                    stack += x["@graph"]
                yield x


def _is_recipe(x: dict) -> bool:
    t = x.get("@type")
    return t == "Recipe" or (isinstance(t, list) and "Recipe" in t)


class _Micro(HTMLParser):
    """Минимальный адаптер микроразметки schema.org/Recipe (itemprop)."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.props: dict[str, list[str]] = {}
        self._cur: list[tuple[str, int]] = []
        self._depth = 0
        self._buf: dict[int, list[str]] = {}

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        self._depth += 1
        ip = a.get("itemprop")
        if ip:
            if "content" in a:
                self.props.setdefault(ip, []).append(a["content"] or "")
            elif tag not in ("meta", "link", "img"):
                self._cur.append((ip, self._depth))
                self._buf[self._depth] = []

    def handle_endtag(self, tag):
        while self._cur and self._cur[-1][1] >= self._depth:
            ip, d = self._cur.pop()
            self.props.setdefault(ip, []).append(_clean(" ".join(self._buf.pop(d, []))))
        self._depth -= 1

    def handle_data(self, data):
        for _, d in self._cur:
            self._buf.setdefault(d, []).append(data)


METHOD_WORDS = {
    "духовк": "oven",
    "запек": "oven",
    "жар": "frying",
    "обжар": "frying",
    "вар": "boiling",
    "отвар": "boiling",
    "туш": "stewing",
    "гриль": "grill",
    "мультиварк": "multicooker",
    "аэрогрил": "air_fryer",
    "пар": "steaming",
    "микроволнов": "microwave",
    "без варки": "no_cook",
    "блендер": "blender",
}


def method_hints(steps: list[str]) -> list[str]:
    text = " ".join(steps).lower()
    return sorted({v for k, v in METHOD_WORDS.items() if k in text})


def extract(page: str, source_url: str, final_url: str | None = None) -> Facts | None:
    recipe = next((x for x in _jsonld_blocks(page) if _is_recipe(x)), None)
    remarks: list[str] = []
    canonical = None
    m = re.search(r'<link[^>]+rel=["\']canonical["\'][^>]*href=["\']([^"\']+)', page, re.I) or re.search(
        r'<link[^>]+href=["\']([^"\']+)["\'][^>]*rel=["\']canonical', page, re.I
    )
    if m:
        canonical = htmllib.unescape(m.group(1))
    if recipe:
        how = "json-ld"
        title = _clean(recipe.get("name") or recipe.get("headline") or "") or None
        servings, sraw = _servings(recipe.get("recipeYield"))
        ingredients = [parse_ingredient(i) for i in recipe.get("recipeIngredient") or [] if str(i).strip()]
        steps = _steps(recipe.get("recipeInstructions"))
        prep, cook, total = (iso_minutes(recipe.get(k)) for k in ("prepTime", "cookTime", "totalTime"))
        category = _first(recipe.get("recipeCategory"))
        cuisine = _first(recipe.get("recipeCuisine"))
        kw = recipe.get("keywords") or []
        keywords = [k.strip() for k in (kw.split(",") if isinstance(kw, str) else kw) if k and k.strip()]
        image_present = bool(recipe.get("image"))
    else:
        mp = _Micro()
        mp.feed(page)
        p = mp.props
        if not (p.get("recipeIngredient") or p.get("ingredients")):
            return None
        how = "microdata"
        h1 = re.search(r"<h1[^>]*>(.*?)</h1>", page, re.S | re.I)
        title = _clean(h1.group(1)) if h1 else None
        if not title:
            remarks.append("название не найдено в <h1>")
        servings, sraw = _servings((p.get("recipeYield") or [None])[0])
        ingredients = [parse_ingredient(i) for i in (p.get("recipeIngredient") or p.get("ingredients")) if i.strip()]
        steps = [s for s in (p.get("recipeInstructions") or p.get("text") or []) if s.strip()]
        prep, cook, total = (iso_minutes((p.get(k) or [None])[0]) for k in ("prepTime", "cookTime", "totalTime"))
        category = (p.get("recipeCategory") or [None])[0]
        cuisine = (p.get("recipeCuisine") or [None])[0]
        keywords = []
        image_present = bool(p.get("image"))
        remarks.append("извлечено из микроразметки: структура менее надёжна, чем JSON-LD")
    if total and prep and cook and prep + cook != total:
        remarks.append(f"противоречие времени: prep {prep} + cook {cook} ≠ total {total}")
    if not servings:
        remarks.append("число порций не указано")
    missing_q = [i.name for i in ingredients if i.quantity is None and i.unit != "to_taste"]
    if missing_q:
        remarks.append(f"нет количества у {len(missing_q)} из {len(ingredients)} ингредиентов")
    if not steps:
        remarks.append("шаги отсутствуют")
    facts = Facts(
        source_url=source_url,
        canonical_url=canonical or final_url,
        title=title,
        servings=servings,
        servings_raw=sraw,
        prep_minutes=prep,
        cook_minutes=cook,
        total_minutes=total,
        ingredients=ingredients,
        steps=steps,
        category=category,
        cuisine=cuisine,
        keywords=keywords,
        method_hints=method_hints(steps),
        image_present=image_present,
        extracted_with=how,
        remarks=remarks,
    )
    facts.content_hash = hashlib.sha256(
        json.dumps([facts.title, [asdict(i) for i in ingredients], steps, servings], ensure_ascii=False).encode()
    ).hexdigest()
    return facts


def is_complete(f: Facts) -> bool:
    """Полный рецепт: название, порции, ≥2 ингредиента с количествами, ≥2 шага."""
    with_q = [i for i in f.ingredients if i.quantity is not None or i.unit == "to_taste"]
    return bool(
        f.title and f.servings and len(f.ingredients) >= 2 and len(with_q) == len(f.ingredients) and len(f.steps) >= 2
    )


def _first(v):
    if isinstance(v, list):
        return v[0] if v else None
    return v
