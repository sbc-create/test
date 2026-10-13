"""Аудит референсов выпечки: структура серверного HTML (без JS).

Сохраняются только собственные измерения и адреса — без текстов, фото и
идентификаторов источников (inventory/reference-sources.yaml — тот же принцип).
"""

from __future__ import annotations

import json
import re
import time
import urllib.parse
from pathlib import Path

from .net import Client, Refused

ROOT = Path(__file__).resolve().parents[1]

PLAN = {
    "www.kingarthurbaking.com": {
        "start": "https://www.kingarthurbaking.com/recipes",
        "recipe_rx": r"https://www\.kingarthurbaking\.com/recipes/[a-z0-9-]+-recipe",
        "category_rx": r"https://www\.kingarthurbaking\.com/recipes/(bread|cookies|cakes|pie|muffins)[a-z-]*$",
    },
    "sallysbakingaddiction.com": {
        "start": "https://sallysbakingaddiction.com/",
        "recipe_rx": r"https://sallysbakingaddiction\.com/[a-z0-9-]+-recipe/?|https://sallysbakingaddiction\.com/(?!category|tag|page|about|contact|recipe-index)[a-z0-9-]{12,}/$",
        "category_rx": r"https://sallysbakingaddiction\.com/category/[a-z0-9/-]+/?$",
    },
    "eda.rambler.ru": {
        "start": "https://eda.rambler.ru/recepty/vypechka-deserty",
        "recipe_rx": r"https://eda\.rambler\.ru/recepty/vypechka-deserty/[a-z0-9-]+-\d+",
        "category_rx": r"https://eda\.rambler\.ru/recepty/vypechka-deserty/[a-z-]+$",
    },
}

FEATURES = {
    "weight_units": r"\b(grams?|граммах|ounces|oz\b|в граммах)",
    "unit_toggle": r"(volume|ounces|grams)\s*(?:<[^>]+>\s*)*(?:/|\|)?\s*(?:<[^>]+>\s*)*(volume|ounces|grams)",
    "pan_size": r"(\d+[\"″]?\s?x\s?\d+|\d+\s?-?inch|\d+\s?см)\s*(pan|форм|tin|baking dish)?",
    "oven_temp": r"(\d{3}\s?°\s?[FC]|\d{3}\s?degrees|\d{3}\s?градус)",
    "tips_section": r">(Tips|Baking Tips|Советы|Хитрости|Notes|Recipe Notes)<",
    "troubleshooting": r"(troubleshoot|why did my|common mistakes|почему не получ|ошибк)",
    "jump_to_recipe": r"(jump to recipe|перейти к рецепту)",
    "print_recipe": r"(print recipe|распечатать)",
    "video": r"(<video|youtube\.com/embed|player\.vimeo|rutube)",
    "ads": r"(adthrive|mediavine|googlesyndication|adsbygoogle|yandex_rtb|adfox|data-ad-)",
}


def measure(html: str) -> dict:
    h1 = re.search(r"<h1[^>]*>(.*?)</h1>", html, re.S | re.I)
    ld = sorted(set(re.findall(r'"@type"\s*:\s*"([A-Za-z]+)"', html)))
    out = {
        "html_kb": round(len(html.encode()) / 1024),
        "has_h1": bool(h1),
        "jsonld_types": ld[:15],
        "recipe_jsonld": "Recipe" in ld,
        "links": len(re.findall(r"<a\s", html, re.I)),
    }
    for k, rx in FEATURES.items():
        out[k] = len(re.findall(rx, html, re.I))
    return out


def run() -> dict:
    c = Client(delay=2.5)
    res = {"at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "mode": "server_html_no_js", "hosts": {}}
    for host, plan in PLAN.items():
        rows = {}
        try:
            start = c.get(plan["start"])
        except Refused as e:
            res["hosts"][host] = {"error": str(e)}
            continue
        links = [urllib.parse.urljoin(start.url, h) for h in re.findall(r'href="([^"#]+)"', start.text)]
        recipes = list(dict.fromkeys(u for u in links if re.fullmatch(plan["recipe_rx"], u)))[:3]
        cats = list(dict.fromkeys(u for u in links if re.fullmatch(plan["category_rx"], u)))[:1]
        rows["start"] = {
            "url": start.url,
            "status": start.status,
            "redirects": len(start.redirects),
            **measure(start.text),
        }
        for i, u in enumerate(cats + recipes):
            key = "category" if u in cats else f"recipe{i}"
            try:
                pg = c.get(u)
                rows[key] = {"url": pg.url, "status": pg.status, **measure(pg.text)}
            except Refused as e:
                rows[key] = {"url": u, "error": str(e)}
        res["hosts"][host] = rows
    res["requests"] = c.requests
    return res


if __name__ == "__main__":
    out = run()
    (ROOT / "docs").mkdir(exist_ok=True)
    (ROOT / "docs" / "audit-measurements.json").write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n")
    for h, rows in out["hosts"].items():
        for k, v in rows.items():
            if isinstance(v, dict):
                print(
                    h,
                    k,
                    v.get("status"),
                    v.get("url", "")[:70],
                    {
                        x: v.get(x)
                        for x in (
                            "html_kb",
                            "recipe_jsonld",
                            "weight_units",
                            "unit_toggle",
                            "pan_size",
                            "oven_temp",
                            "tips_section",
                            "troubleshooting",
                            "jump_to_recipe",
                            "video",
                            "ads",
                        )
                    },
                )
