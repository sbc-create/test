"""Карточки plants-home: проверка против фактов КОНКРЕТНОГО вида и сборка data/content.json.

Правила (нарушение = карточка не публикуется):
- карточка ссылается ровно на один источник-вид; научное название — из источника;
- каждое число в тексте — из фактов этого вида или из расчёта `calc` (°F→°C, дюймы→см), который пересчитывается;
- проблема (`problems[].tag`) допустима, только если источник этого вида её называет (регулярное выражение по тексту);
- месяцы в тексте — только если источник называет этот месяц;
- запрещены цена, рейтинг, «подходит всем растениям» и обобщения на другие виды.

Запуск: python3 -m flora.content validate | build
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import operator
import re
import sys
import time
from pathlib import Path

from flora.sources import fact_lines, load_all

ROOT = Path(__file__).resolve().parents[1]
MATERIALS = ROOT / "data" / "materials"
CONTENT = ROOT / "data" / "content.json"
HISTORY = ROOT / "data" / "history.jsonl"
SITE_ID = "plants-home"

LIGHT = {
    "Full sun (6 or more hours of direct sunlight a day)": (
        "solnce",
        "Солнце",
        "6 и более часов прямого солнца в день",
    ),
    "Partial Shade (Direct sunlight only part of the day, 2-6 hours)": (
        "poluten",
        "Полутень",
        "прямое солнце только часть дня, 2–6 часов",
    ),
    "Dappled Sunlight (Shade through upper canopy all day)": (
        "rasseyannyj",
        "Рассеянный свет",
        "весь день в тени верхнего яруса — свет пробивается сквозь листву",
    ),
    "Deep shade (Less than 2 hours to no direct sunlight)": (
        "ten",
        "Тень",
        "меньше 2 часов прямого солнца или совсем без него",
    ),
}
DRAINAGE = {
    "Good Drainage": "хороший дренаж",
    "Moist": "влажная почва",
    "Occasionally Dry": "допускает пересыхание",
    "Very Dry": "переносит очень сухую почву",
    "Occasionally Wet": "допускает переувлажнение",
}
MAINT = {"Low": "простой", "Medium": "средний", "High": "сложный"}
PROPAG = {
    "Division": "деление",
    "Stem Cutting": "стеблевые черенки",
    "Leaf Cutting": "листовые черенки",
    "Layering": "отводки",
    "Root Cutting": "корневые черенки",
    "Seed": "семена",
    "Grafting": "прививка",
}
POISON = {"Low": "низкая", "Medium": "средняя", "High": "высокая"}
PROBLEMS = {
    "korni-gniyut": ("Корни гниют от перелива", r"root rot|roots rotting|roots will rot|rotted|crown and root rot"),
    "muchnistyj-chervec": ("Мучнистый червец", r"mealybug"),
    "pautinnyj-kleshch": ("Паутинный клещ", r"spider mite"),
    "shchitovka": ("Щитовка", r"\bscales?\b|scale insects"),
    "tlya": ("Тля", r"aphid"),
    "opadayut-listya": ("Опадают листья", r"loss of leaves|leaf fall"),
    "opadayut-butony": ("Опадают бутоны", r"bud drop|buds to drop"),
}
TOPICS = {
    "svet": "Свет",
    "poliv": "Полив",
    "temperatura": "Температура",
    "vlazhnost": "Влажность воздуха",
    "pochva": "Почва и горшок",
    "podkormka": "Подкормка",
    "uhod": "Уход",
    "cvetenie": "Цветение",
    "razmnozhenie": "Размножение",
}
MONTH_RX = {
    "september": r"(?i)\bсентябр",
    "december": r"(?i)\bдекабр",
    "february": r"(?i)\bфеврал",
    "january": r"(?i)\bянвар",
    "march": r"(?i)\bмарт",
    "april": r"(?i)\bапрел",
    "may": r"(?i)\bма[йяе]\b",
    "june": r"(?i)\bиюн",
    "july": r"(?i)\bиюл",
    "august": r"(?i)\bавгуст",
    "october": r"(?i)\bоктябр",
    "november": r"(?i)\bноябр",
}
FORBIDDEN = re.compile(r"(?i)рейтинг|₽|\bруб|\bцен[аеуы]\b|всем растениям|любое растение|для всех растений")
NUM = re.compile(r"\d+(?:[.,]\d+)?")
CONSTANTS = {"32", "5", "9", "2.54"}
OPS = {ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul, ast.Div: operator.truediv}


def _num(s: str) -> str:
    v = float(s.replace(",", "."))
    return str(int(v)) if v == int(v) else str(round(v, 2))


def _eval(expr: str) -> float:
    def ev(n):
        if isinstance(n, ast.Expression):
            return ev(n.body)
        if isinstance(n, ast.BinOp) and type(n.op) in OPS:
            return OPS[type(n.op)](ev(n.left), ev(n.right))
        if isinstance(n, ast.Constant) and isinstance(n.value, int | float):
            return n.value
        raise ValueError(expr)

    return ev(ast.parse(expr.replace(",", "."), mode="eval"))


def texts(m: dict) -> list[tuple[str, str]]:
    out = [("ru_name", m["ru_name"]), ("summary", m["summary"])]
    out += [(f"care[{i}]", x["text"]) for i, x in enumerate(m["care"])]
    out += [(f"problems[{i}]", x["text"]) for i, x in enumerate(m.get("problems", []))]
    out += [(f"checklist[{i}]", x) for i, x in enumerate(m["checklist"])]
    out += [(f"calc[{i}]", x["label"]) for i, x in enumerate(m.get("calc", []))]
    return out


def validate(m: dict, sources: dict, slugs: set[str]) -> list[str]:
    err = [f"пустое поле {k}" for k in ("slug", "src", "ru_name", "summary", "care", "checklist") if not m.get(k)]
    if err:
        return err
    src = sources.get(m["src"])
    if not src:
        return [f"источник не найден: {m['src']}"]
    if m.get("producer", {}).get("mode") != "manual_standin":
        err.append("producer.mode должен быть manual_standin")
    err += [f"неизвестная тема {x['topic']}" for x in m["care"] if x.get("topic") not in TOPICS]
    err += [f"связанная карточка не найдена: {r}" for r in m.get("related", []) if r not in slugs or r == m["slug"]]
    facts = " ".join(fact_lines(src))
    for p in m.get("problems", []):
        if p["tag"] not in PROBLEMS:
            err.append(f"неизвестная проблема {p['tag']}")
        elif not re.search(PROBLEMS[p["tag"]][1], facts, re.I):
            err.append(f"проблема «{PROBLEMS[p['tag']][0]}» не названа источником этого вида")
    allowed = {_num(n) for n in NUM.findall(facts)}
    for i, c in enumerate(m.get("calc", [])):
        bad = [n for n in (_num(x) for x in NUM.findall(c["expr"])) if n not in allowed | CONSTANTS]
        if bad:
            err.append(f"calc[{i}]: исходные числа не из фактов вида: {bad}")
        if abs(_eval(c["expr"]) - float(c["result"])) > 0.051:
            err.append(f"calc[{i}]: {c['expr']} ≠ {c['result']}")
        allowed.add(_num(c["result"]))
    for where, t in texts(m):
        f = FORBIDDEN.search(t)
        if f:
            err.append(f"{where}: запрещённое утверждение «{f.group(0)}»")
        for n in NUM.findall(t):
            if _num(n) not in allowed:
                err.append(f"{where}: число {n} не подтверждено фактами вида")
        for en, rx in MONTH_RX.items():
            if re.search(rx, t) and en not in facts.lower():
                err.append(f"{where}: месяц не назван источником вида")
    return err


def load_materials() -> list[dict]:
    return [json.loads(p.read_text()) for p in sorted(MATERIALS.glob("*.json"))]


def text_hash(m: dict) -> str:
    keep = {k: v for k, v in m.items() if k not in ("version", "published_at", "updated_at")}
    return hashlib.sha256(json.dumps(keep, ensure_ascii=False, sort_keys=True).encode()).hexdigest()


def build(published_at: str | None = None) -> dict:
    sources, mats = load_all(), load_materials()
    slugs = {m["slug"] for m in mats}
    prev = {}
    if CONTENT.exists():
        prev = {m["slug"]: m for m in json.loads(CONTENT.read_text())["items"]}
    now = published_at or time.strftime("%Y-%m-%d", time.gmtime())
    items, report = [], {}
    for m in mats:
        e = validate(m, sources, slugs)
        report[m["slug"]] = e or "ok"
        if e:
            continue
        h, old = text_hash(m), prev.get(m["slug"])
        version = old["version"] + (old["text_hash"] != h) if old else 1
        items.append(
            {
                **m,
                "version": version,
                "text_hash": h,
                "published_at": old["published_at"] if old else now,
                "updated_at": now if not old or old["text_hash"] != h else old["updated_at"],
                "review_status": "ai_draft",
            }
        )
        if not old or old["text_hash"] != h:
            with HISTORY.open("a") as f:
                f.write(json.dumps({"slug": m["slug"], "version": version, "text_hash": h, "at": now}) + "\n")
    used = sorted({m["src"] for m in items})
    CONTENT.write_text(
        json.dumps(
            {"site_id": SITE_ID, "items": items, "sources": {s: sources[s] for s in used}}, ensure_ascii=False, indent=1
        )
        + "\n"
    )
    return report


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["validate", "build"])
    ap.add_argument("--published-at")
    a = ap.parse_args(argv)
    if a.cmd == "build":
        rep = build(a.published_at)
    else:
        sources, mats = load_all(), load_materials()
        slugs = {m["slug"] for m in mats}
        rep = {m["slug"]: validate(m, sources, slugs) or "ok" for m in mats}
    print(json.dumps(rep, ensure_ascii=False, indent=1))
    return 0 if all(v == "ok" for v in rep.values()) else 1


if __name__ == "__main__":
    sys.exit(main())
