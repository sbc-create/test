"""Аудит референсов «техника на кухне»: серверный HTML без JS, только измерения."""

from __future__ import annotations

import json
import re
import time
import urllib.parse
from pathlib import Path

from .net import Client, Refused

ROOT = Path(__file__).resolve().parents[1]
FEATURES = {
    "appliance_words": r"(air fryer|ninja foodi|multicooker|pressure cook|мультиварк|аэрогрил|гриль|grill)",
    "mode_words": r"(режим|program|setting|function|air crisp|bake|roast|pressure)",
    "temp": r"(\d{3}\s?°\s?[FC]|\d{3}\s?градус|\d{3}°)",
    "time": r"(\d+\s?(?:min|minutes|мин))",
    "model_words": r"(model|модел|compatible|подходит для)",
    "recipe_jsonld": r'"@type"\s*:\s*"Recipe"',
    "ads": r"(adsbygoogle|googlesyndication|yandex_rtb|adfox|data-ad-)",
}


def measure(html: str) -> dict:
    out = {"html_kb": round(len(html.encode()) / 1024), "has_h1": bool(re.search(r"<h1[\s>]", html, re.I))}
    for k, rx in FEATURES.items():
        out[k] = len(re.findall(rx, html, re.I))
    return out


def links(base: str, html: str, rx: str) -> list[str]:
    return list(
        dict.fromkeys(
            u for u in (urllib.parse.urljoin(base, h) for h in re.findall(r'href="([^"#]+)"', html)) if re.search(rx, u)
        )
    )


def run() -> dict:
    c = Client(delay=2.5)
    res = {"at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "mode": "server_html_no_js", "hosts": {}}
    plan = [
        (
            "www.sharkninja.com",
            "https://www.sharkninja.com/discover/recipes",
            r"sharkninja\.com/.*recipe[s]?/[a-z0-9-]{6,}",
        ),
        ("1000.menu", "https://1000.menu/", r"1000\.menu/.*(multivark|aerogril)"),
        (
            "eda.rambler.ru",
            "https://eda.rambler.ru/recepty/osnovnye-blyuda",
            r"eda\.rambler\.ru/recepty/[a-z-]+/[a-z0-9-]*(multivark|aerogril|gril)[a-z0-9-]*-\d+",
        ),
    ]
    for host, start, rx in plan:
        rows = {}
        try:
            st, final, body = c.get(start)
            html = body.decode("utf-8", "replace")
            rows["start"] = {"url": final, "status": st, **measure(html)}
            for i, u in enumerate(links(final, html, rx)[:3]):
                try:
                    st2, f2, b2 = c.get(u)
                    rows[f"page{i}"] = {"url": f2, "status": st2, **measure(b2.decode("utf-8", "replace"))}
                except Refused as e:
                    rows[f"page{i}"] = {"url": u, "error": str(e)}
        except Refused as e:
            rows["start"] = {"url": start, "error": str(e)}
        res["hosts"][host] = rows
    res["requests"] = c.requests
    return res


if __name__ == "__main__":
    out = run()
    (ROOT / "docs").mkdir(exist_ok=True)
    (ROOT / "docs" / "audit-measurements.json").write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n")
    for h, rows in out["hosts"].items():
        for k, v in rows.items():
            print(
                h,
                k,
                v.get("status"),
                v.get("url", "")[:90],
                v.get("error", ""),
                {
                    x: v.get(x)
                    for x in (
                        "html_kb",
                        "appliance_words",
                        "mode_words",
                        "temp",
                        "time",
                        "model_words",
                        "recipe_jsonld",
                        "ads",
                    )
                },
            )
