"""Импорт фактов рецептов выпечки с eda.rambler.ru.

Факты (ингредиенты, количества, порции, время, порядок шагов, температура,
форма) — в data/facts/<record>.json; исходный текст шагов — только в
var/food-baking/private (вне git и сборки, 30 дней). Неизвестное — null.
Повтор запуска не скачивает уже импортированное.
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import html as htmllib
import json
import os
import re
import time
import xml.etree.ElementTree as ET
from pathlib import Path

from .net import REPO, Client, Refused

ROOT = Path(__file__).resolve().parents[1]
FACTS = ROOT / "data" / "facts"
PRIVATE = REPO / "var" / "food-baking" / "private"
PARSER = "fb-extract/1.1"

# группы для разнообразия выборки: (группа, ключи слага)
GROUPS = [
    ("pirog", ["pirog", "sharlotka", "tart", "kish"]),
    ("pechene", ["pechene", "kukis", "pryanik"]),
    ("keks", ["keks", "maffin", "kapkejk", "brauni"]),
    ("hleb", ["hleb", "baton", "chiabatt", "fokachch", "lepeshk"]),
    ("bulochki", ["bulochk", "bulki", "sdob", "plyushk", "rogalik"]),
    ("tort", ["tort", "biskvit", "chizkejk", "chizkeik", "rulet"]),
    ("sloyki", ["sloj", "sloek", "kruassan"]),
    ("zavarnoe", ["eklery", "profitrol", "zavarn"]),
]

UNITS = {
    "г": "g",
    "кг": "kg",
    "мл": "ml",
    "л": "l",
    "штука": "pcs",
    "штуки": "pcs",
    "штук": "pcs",
    "шт": "pcs",
    "столовая ложка": "tbsp",
    "столовые ложки": "tbsp",
    "столовых ложек": "tbsp",
    "чайная ложка": "tsp",
    "чайные ложки": "tsp",
    "чайных ложек": "tsp",
    "стакан": "cup",
    "стакана": "cup",
    "стаканов": "cup",
    "щепотка": "pinch",
    "пачка": "pack",
    "пачки": "pack",
    "зубчик": "clove",
    "зубчика": "clove",
    "по вкусу": "to_taste",
}
UNIT_RX = "|".join(sorted((re.escape(u) for u in UNITS), key=len, reverse=True))


def parse_ingredient(raw: str) -> dict:
    text = re.sub(r"\s+", " ", htmllib.unescape(raw)).strip(" .")
    m = re.match(rf"^(.*?),\s*(\d+(?:[.,]\d+)?|½|¼|¾)\s*({UNIT_RX})?\s*$", text)
    if m:
        q = {"½": 0.5, "¼": 0.25, "¾": 0.75}.get(m.group(2)) or float(m.group(2).replace(",", "."))
        return {
            "raw": text,
            "name": m.group(1).strip(),
            "quantity": q,
            "unit": UNITS.get(m.group(3) or "", "pcs" if not m.group(3) else None),
        }
    m = re.match(rf"^(.*?),\s*({UNIT_RX})\s*$", text)
    if m:
        u = UNITS[m.group(2)]
        return {"raw": text, "name": m.group(1).strip(), "quantity": None if u == "to_taste" else 1.0, "unit": u}
    return {"raw": text, "name": text, "quantity": None, "unit": None}


def iso_min(v) -> int | None:
    m = re.fullmatch(r"P(?:(\d+)D)?T?(?:(\d+)H)?(?:(\d+)M)?", (v or "").strip()) if isinstance(v, str) else None
    if not m or not any(m.groups()):
        return None
    d, h, mi = (int(x or 0) for x in m.groups())
    return d * 1440 + h * 60 + mi or None


TEMP = re.compile(r"(\d{2,3})\s*(?:°\s*C|°С|°|градус)", re.I)
BAKE_TIME = re.compile(
    r"(?:выпека|запека|печь|пеки|в духовк)[^.]{0,80}?(?:(\d{1,2})\s*час\w*\s*(?:(\d{1,2})\s*мин\w*)?|"
    r"(\d{1,3})\s*(?:[-–]\s*(\d{1,3}))?\s*мин)",
    re.I,
)
FORM = re.compile(
    r"(форм[уеаы]?[^.]{0,40}?(?:диаметр\w*\s*)?(\d{2})\s*см|противен\w*|форм[ауые]\s+для\s+\w+|кексниц\w*|"
    r"форм\w* для маффинов|силиконов\w+ форм\w*)",
    re.I,
)
CAUTION = re.compile(
    r"(\bне\s+(?:открыва|переса|перемешива|допуска|давайте|кладите|забудьте|вынимайте)|иначе|"
    r"чтобы не|обязательно|важно)",
    re.I,
)


def oven_facts(steps: list[str]) -> dict:
    temps, times, forms, cautions = [], [], [], []
    for i, s in enumerate(steps):
        for t in TEMP.findall(s):
            if 100 <= int(t) <= 300:
                temps.append({"value_c": int(t), "step": i})
        for h, hm, a, b in BAKE_TIME.findall(s):
            if h:  # «1 час 20 минут» → 80 минут
                times.append({"min": int(h) * 60 + int(hm or 0), "max": None, "step": i})
            else:
                times.append({"min": int(a), "max": int(b) if b else None, "step": i})
        for f in FORM.findall(s):
            forms.append({"text": f[0].strip()[:80], "diameter_cm": int(f[1]) if f[1] else None, "step": i})
        if CAUTION.search(s):
            cautions.append(i)
    return {"temperatures": temps, "bake_times": times, "forms": forms, "caution_steps": cautions}


def extract(page: str, url: str) -> dict | None:
    for block in re.findall(r"<script[^>]+application/ld\+json[^>]*>(.*?)</script>", page, re.S):
        try:
            data = json.loads(block)
        except json.JSONDecodeError:
            continue
        for x in data if isinstance(data, list) else data.get("@graph", [data]):
            if isinstance(x, dict) and x.get("@type") == "Recipe":
                steps = [
                    re.sub(r"\s+", " ", htmllib.unescape(s.get("text", s) if isinstance(s, dict) else s)).strip()
                    for s in x.get("recipeInstructions") or []
                ]
                steps = [s for s in steps if s]
                y = re.search(r"\d+", str(x.get("recipeYield") or ""))
                ing = [parse_ingredient(i) for i in x.get("recipeIngredient") or []]
                facts = {
                    "source_url": url,
                    "title": htmllib.unescape(x.get("name") or "").strip() or None,
                    "servings": int(y.group()) if y else None,
                    "prep_minutes": iso_min(x.get("prepTime")),
                    "cook_minutes": iso_min(x.get("cookTime")),
                    "total_minutes": iso_min(x.get("totalTime")),
                    "ingredients": ing,
                    "source_category": x.get("recipeCategory"),
                    "oven": oven_facts(steps),
                    "parser_version": PARSER,
                }
                remarks = []
                if any(i["quantity"] is None and i["unit"] != "to_taste" for i in ing):
                    remarks.append("есть ингредиенты без количества")
                if not facts["oven"]["temperatures"]:
                    remarks.append("температура духовки в источнике не названа")
                facts["remarks"] = remarks
                facts["complete"] = bool(
                    facts["title"]
                    and facts["servings"]
                    and len(ing) >= 2
                    and len(steps) >= 2
                    and all(i["quantity"] is not None or i["unit"] == "to_taste" for i in ing)
                )
                facts["content_hash"] = hashlib.sha256(
                    json.dumps([facts["title"], ing, steps], ensure_ascii=False).encode()
                ).hexdigest()
                return facts | {"_steps": steps}
    return None


def recipe_urls(c: Client) -> list[str]:
    idx = c.get("https://eda.rambler.ru/sitemap-index.xml")
    ns = {"s": "http://www.sitemaps.org/schemas/sitemap/0.9"}
    maps = [e.text for e in ET.fromstring(idx.body).findall("s:sitemap/s:loc", ns) if "RecipePagesGroup" in e.text]
    out = []
    for m in maps:
        pg = c.get(m)
        body = gzip.decompress(pg.body) if pg.body[:2] == b"\x1f\x8b" else pg.body
        out += [
            e.text
            for e in ET.fromstring(body).findall("s:url/s:loc", ns)
            if "/recepty/vypechka-deserty/" in (e.text or "")
        ]
    return out


def reextract() -> int:
    """Пересчёт фактов о духовке из закрытого хранилища новой версией разбора, без сети."""
    n = 0
    for p in FACTS.glob("*.json"):
        f = json.loads(p.read_text())
        raw = PRIVATE / f"{f['record_id']}.json.gz"
        if not raw.exists():
            continue
        steps = json.loads(gzip.decompress(raw.read_bytes()))["steps"]
        f["oven"], f["parser_version"] = oven_facts(steps), PARSER
        p.write_text(json.dumps(f, ensure_ascii=False, indent=1) + "\n")
        n += 1
    return n


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="food-baking import")
    ap.add_argument("--per-group", type=int, default=3)
    ap.add_argument("--reextract", action="store_true")
    a = ap.parse_args(argv)
    if a.reextract:
        print(json.dumps({"reextracted": reextract(), "parser": PARSER}))
        return 0
    FACTS.mkdir(parents=True, exist_ok=True)
    PRIVATE.mkdir(parents=True, exist_ok=True)
    os.chmod(PRIVATE, 0o700)
    c = Client(delay=2.0)
    urls = recipe_urls(c)
    known = {json.loads(p.read_text())["source_url"] for p in FACTS.glob("*.json")}
    stats = {
        "sitemap_baking_urls": len(urls),
        "fetched": 0,
        "extracted": 0,
        "complete": 0,
        "skipped_known": 0,
        "refused": 0,
    }
    for group, keys in GROUPS:
        cands = [u for u in urls if any(k in u.rsplit("/", 1)[-1] for k in keys)][: a.per_group]
        for u in cands:
            if u in known:
                stats["skipped_known"] += 1
                continue
            try:
                pg = c.get(u)
            except Refused:
                stats["refused"] += 1
                continue
            stats["fetched"] += 1
            f = extract(pg.text, u) if pg.status == 200 else None
            if not f:
                continue
            stats["extracted"] += 1
            stats["complete"] += int(f["complete"])
            rid = "fb-" + hashlib.sha256(u.encode()).hexdigest()[:12]
            steps = f.pop("_steps")
            (PRIVATE / f"{rid}.json.gz").write_bytes(
                gzip.compress(
                    json.dumps(
                        {
                            "source_url": u,
                            "steps": steps,
                            "fetched_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                        },
                        ensure_ascii=False,
                    ).encode()
                )
            )
            f.update(
                record_id=rid,
                group_hint=group,
                step_count=len(steps),
                fetched_at=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            )
            (FACTS / f"{rid}.json").write_text(json.dumps(f, ensure_ascii=False, indent=1) + "\n")
    print(json.dumps(stats | {"requests": c.requests}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
