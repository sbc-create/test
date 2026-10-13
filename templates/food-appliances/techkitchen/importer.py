"""Импорт фактов рецептов для техники (мультиварка, аэрогриль, гриль) с eda.rambler.ru.

Факты прибора берутся только из текста шагов источника: название режима
(«режим „Тушение“»), температура, время — с номером шага. Если прибор
не упомянут в шагах, рецепт не считается рецептом для прибора.
Исходные шаги — только в var/food-appliances/private (вне git).
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
PRIVATE = REPO / "var" / "food-appliances" / "private"
PARSER = "fa-extract/1.2"
APPLIANCES = {
    "multivarka": {"slug": r"multivark", "step": r"мультиварк"},
    "aerogril": {"slug": r"aerogril", "step": r"аэрогрил|аэрофритюр"},
    "gril": {"slug": r"(^|-)(na-)?gril(e|ya)?(-|$)", "step": r"\bгрил[ьеяю]|решетк\w* гриля|гриль-сковород"},
}
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
    "зубчик": "clove",
    "зубчика": "clove",
    "зубчиков": "clove",
    "пучок": "bunch",
    "веточка": "sprig",
    "веточки": "sprig",
    "по вкусу": "to_taste",
    "головка": "head",
    "кусок": "piece",
}
URX = "|".join(sorted((re.escape(u) for u in UNITS), key=len, reverse=True))
MODE_ANCHOR = re.compile(r"режим|программ", re.I)
QUOTED = re.compile(r"[«\"“]([^»\"”]{2,30})[»\"”]")


def mode_names(step: str) -> list[str]:
    """Все названия в кавычках в 60 знаках после «режим»/«программа»: «плов» или «крупы», режим на «Тушение»."""
    out = []
    for m in MODE_ANCHOR.finditer(step):
        for q in QUOTED.findall(step[m.end() : m.end() + 60]):
            q = re.sub(r"[\u200b-\u200f\u2060\ufeff]", "", q).strip()
            if q and q not in out:
                out.append(q)
    return out


TEMP = re.compile(r"(\d{2,3})\s*(?:°\s*C|°С|°|градус)", re.I)
TIME = re.compile(r"(?:(\d{1,2})\s*час\w*\s*(?:(\d{1,2})\s*мин\w*)?|(\d{1,3})\s*(?:[-–]\s*(\d{1,3}))?\s*мин)", re.I)


def ingredient(raw: str) -> dict:
    t = re.sub(r"\s+", " ", htmllib.unescape(raw)).strip(" .")
    m = re.match(rf"^(.*?),\s*(\d+(?:[.,]\d+)?|½|¼|¾)\s*({URX})?\s*$", t)
    if m:
        q = {"½": 0.5, "¼": 0.25, "¾": 0.75}.get(m.group(2)) or float(m.group(2).replace(",", "."))
        return {"name": m.group(1).strip(), "quantity": q, "unit": UNITS.get(m.group(3) or "", "pcs")}
    m = re.match(rf"^(.*?),\s*({URX})\s*$", t)
    if m:
        u = UNITS[m.group(2)]
        return {"name": m.group(1).strip(), "quantity": None if u == "to_taste" else 1.0, "unit": u}
    return {"name": t, "quantity": None, "unit": None}


def appliance_facts(appliance: str, steps: list[str]) -> dict:
    rx = re.compile(APPLIANCES[appliance]["step"], re.I)
    modes, temps, times, mentions = [], [], [], []
    for i, s in enumerate(steps):
        # шаг относится к прибору, если назван прибор или его режим/программа
        if not (rx.search(s) or re.search(r"режим|программ", s, re.I)):
            continue
        mentions.append(i)
        modes += [{"name": m, "step": i} for m in mode_names(s)]
        temps += [{"value_c": int(t), "step": i} for t in TEMP.findall(s) if 40 <= int(t) <= 300]
        for h, hm, a, b in TIME.findall(s):
            mins = int(h) * 60 + int(hm or 0) if h else int(a)
            times.append({"min": mins, "max": int(b) if b else None, "step": i})
    return {"appliance": appliance, "mention_steps": mentions, "modes": modes, "temperatures": temps, "times": times}


def iso_min(v):
    m = re.fullmatch(r"P(?:(\d+)D)?T?(?:(\d+)H)?(?:(\d+)M)?", v or "") if isinstance(v, str) else None
    if not m or not any(m.groups()):
        return None
    d, h, mi = (int(x or 0) for x in m.groups())
    return d * 1440 + h * 60 + mi or None


def extract(page: str, url: str, appliance: str) -> dict | None:
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
                ing = [ingredient(i) for i in x.get("recipeIngredient") or []]
                y = re.search(r"\d+", str(x.get("recipeYield") or ""))
                app = appliance_facts(appliance, steps)
                f = {
                    "source_url": url,
                    "title": htmllib.unescape(x.get("name") or "").strip(),
                    "servings": int(y.group()) if y else None,
                    "prep_minutes": iso_min(x.get("prepTime")),
                    "cook_minutes": iso_min(x.get("cookTime")),
                    "total_minutes": iso_min(x.get("totalTime")),
                    "ingredients": ing,
                    "source_category": x.get("recipeCategory"),
                    "appliance": app,
                    "parser_version": PARSER,
                }
                f["complete"] = bool(
                    f["title"]
                    and f["servings"]
                    and len(ing) >= 2
                    and len(steps) >= 2
                    and all(i["quantity"] is not None or i["unit"] == "to_taste" for i in ing)
                    and app["mention_steps"]
                    and (app["modes"] or app["temperatures"])
                    and app["times"]
                )
                f["content_hash"] = hashlib.sha256(
                    json.dumps([f["title"], ing, steps], ensure_ascii=False).encode()
                ).hexdigest()
                return f | {"_steps": steps}
    return None


def candidates(c: Client) -> dict[str, list[str]]:
    st, _, body = c.get("https://eda.rambler.ru/sitemap-index.xml")
    ns = {"s": "http://www.sitemaps.org/schemas/sitemap/0.9"}
    maps = [e.text for e in ET.fromstring(body).findall("s:sitemap/s:loc", ns) if "RecipePagesGroup" in e.text]
    urls = []
    for m in maps:
        _, _, b = c.get(m)
        b = gzip.decompress(b) if b[:2] == b"\x1f\x8b" else b
        urls += [e.text for e in ET.fromstring(b).findall("s:url/s:loc", ns)]
    out = {}
    for a, cfg in APPLIANCES.items():
        out[a] = [u for u in urls if re.search(cfg["slug"], u.rsplit("/", 1)[-1])]
    return out


def reextract() -> int:
    """Пересчёт фактов прибора из закрытого хранилища текущей версией разбора, без сети."""
    n = 0
    for p in FACTS.glob("*.json"):
        f = json.loads(p.read_text())
        raw = PRIVATE / f"{f['record_id']}.json.gz"
        if raw.exists():
            steps = json.loads(gzip.decompress(raw.read_bytes()))["steps"]
            f["appliance"] = appliance_facts(f["appliance"]["appliance"], steps)
            p.write_text(json.dumps(f, ensure_ascii=False, indent=1) + "\n")
            n += 1
    return n


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="food-appliances import")
    ap.add_argument("--per-appliance", type=int, default=12)
    ap.add_argument("--only", choices=list(APPLIANCES))
    ap.add_argument("--reextract", action="store_true")
    a = ap.parse_args(argv)
    if a.reextract:
        print(json.dumps({"reextracted": reextract()}))
        return 0
    FACTS.mkdir(parents=True, exist_ok=True)
    PRIVATE.mkdir(parents=True, exist_ok=True)
    os.chmod(PRIVATE, 0o700)
    c = Client(delay=2.0)
    cands = candidates(c)
    known = {json.loads(p.read_text())["source_url"] for p in FACTS.glob("*.json")}
    stats = {"candidates": {k: len(v) for k, v in cands.items()}, "fetched": 0, "extracted": 0, "complete": 0}
    for appliance, urls in cands.items():
        if a.only and appliance != a.only:
            continue
        for u in urls[: a.per_appliance]:
            if u in known:
                continue
            try:
                st, final, body = c.get(u)
            except Refused:
                continue
            stats["fetched"] += 1
            f = extract(body.decode("utf-8", "replace"), u, appliance) if st == 200 else None
            if not f:
                continue
            stats["extracted"] += 1
            stats["complete"] += int(f["complete"])
            rid = "fa-" + hashlib.sha256(u.encode()).hexdigest()[:12]
            steps = f.pop("_steps")
            (PRIVATE / f"{rid}.json.gz").write_bytes(
                gzip.compress(json.dumps({"source_url": u, "steps": steps}, ensure_ascii=False).encode())
            )
            f.update(
                record_id=rid, step_count=len(steps), fetched_at=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
            )
            (FACTS / f"{rid}.json").write_text(json.dumps(f, ensure_ascii=False, indent=1) + "\n")
    print(json.dumps(stats | {"requests": c.requests}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
