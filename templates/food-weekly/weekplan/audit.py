"""Аудит планировщиков меню: серверный HTML без JS, только измерения."""

from __future__ import annotations

import json
import re
import time
import urllib.parse
from pathlib import Path

from .net import Client, Refused

ROOT = Path(__file__).resolve().parents[1]
START = {
    "menunedeli.ru": ["https://menunedeli.ru/", "https://menunedeli.ru/menyu-na-nedelyu/"],
    "www.mealime.com": ["https://www.mealime.com/", "https://www.mealime.com/meal-plans"],
    "www.plantoeat.com": ["https://www.plantoeat.com/", "https://www.plantoeat.com/meal-planner"],
}
PLAN_RX = {
    "menunedeli.ru": r"https://menunedeli\.ru/menyu-na-nedelyu/[a-z0-9-]+/?",
    "www.mealime.com": r"https://www\.mealime\.com/meal-plans?/[a-z0-9-]+",
    "www.plantoeat.com": r"https://www\.plantoeat\.com/(?:blog/)?[a-z0-9-]*meal-plan[a-z0-9-]*/?",
}
FEATURES = {
    "weekdays_ru": r"(понедельник|вторник|среда|четверг|пятница|суббота|воскресенье)",
    "weekdays_en": r"\b(monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b",
    "shopping_list": r"(список покупок|список продуктов|grocery list|shopping list)",
    "servings_people": r"(на \d+ (?:человек|персон)|порци|servings|people|serves)",
    "swap": r"(заменить|замена|swap|replace)",
    "signup_wall": r"(sign up|create (?:an )?account|зарегистр|войти|log in|download (?:the )?app)",
    "ads": r"(adsbygoogle|googlesyndication|yandex_rtb|adfox|data-ad-|mediavine|adthrive)",
    "video": r"(<video|youtube\.com/embed|rutube)",
}


def measure(html: str) -> dict:
    h1 = re.search(r"<h1[^>]*>(.*?)</h1>", html, re.S | re.I)
    out = {
        "html_kb": round(len(html.encode()) / 1024),
        "has_h1": bool(h1),
        "jsonld": sorted(set(re.findall(r'"@type"\s*:\s*"([A-Za-z]+)"', html)))[:12],
    }
    for k, rx in FEATURES.items():
        out[k] = len(re.findall(rx, html, re.I))
    return out


def run() -> dict:
    c = Client()
    res = {"at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "mode": "server_html_no_js", "hosts": {}}
    for host, starts in START.items():
        rows, links = {}, []
        for i, u in enumerate(starts):
            try:
                st, final, body = c.get(u)
            except Refused as e:
                rows[f"start{i}"] = {"url": u, "error": str(e)}
                continue
            rows[f"start{i}"] = {"url": final, "status": st, **measure(body)}
            links += [urllib.parse.urljoin(final, h) for h in re.findall(r'href="([^"#]+)"', body)]
        plans = [u for u in dict.fromkeys(links) if re.fullmatch(PLAN_RX[host], u)][:2]
        for i, u in enumerate(plans):
            try:
                st, final, body = c.get(u)
                rows[f"plan{i}"] = {"url": final, "status": st, **measure(body)}
            except Refused as e:
                rows[f"plan{i}"] = {"url": u, "error": str(e)}
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
                v.get("url", "")[:80],
                v.get("error", ""),
                {
                    x: v.get(x)
                    for x in (
                        "html_kb",
                        "weekdays_ru",
                        "weekdays_en",
                        "shopping_list",
                        "servings_people",
                        "swap",
                        "signup_wall",
                        "ads",
                    )
                },
            )
