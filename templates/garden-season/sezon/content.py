"""Материалы garden-season: проверка против фактов и сборка data/content.json.

Правила (нарушение = материал не публикуется):
- у материала есть сроки `timing`: каждый — ссылка на конкретный пункт/цитату источника; месяц и регион срока
  обязаны совпасть с месяцем и регионом этого пункта (региональный срок не превращается в универсальный);
- названия месяцев в тексте — только из месяцев, подтверждённых сроками материала;
- каждое число — из фактов источников материала или из расчёта `calc` (перевод °F→°C, дюймы→см),
  который пересчитывается;
- шаги и ограничения ссылаются на пункты источников; совет редакции помечен и на источник не ссылается;
- запрещены обобщения сроков («везде», «в любом регионе», «по всей России») и цена/рейтинг.

Запуск: python3 -m sezon.content validate | build
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

from sezon.sources import load_all

ROOT = Path(__file__).resolve().parents[1]
MATERIALS = ROOT / "data" / "materials"
CONTENT = ROOT / "data" / "content.json"
HISTORY = ROOT / "data" / "history.jsonl"
SITE_ID = "garden-season"

MONTHS_RU = [
    "январь",
    "февраль",
    "март",
    "апрель",
    "май",
    "июнь",
    "июль",
    "август",
    "сентябрь",
    "октябрь",
    "ноябрь",
    "декабрь",
]
MONTH_SLUG = [
    "yanvar",
    "fevral",
    "mart",
    "aprel",
    "maj",
    "iyun",
    "iyul",
    "avgust",
    "sentyabr",
    "oktyabr",
    "noyabr",
    "dekabr",
]
MONTH_RX = [
    re.compile(r"(?i)\b" + p)
    for p in (
        r"январ",
        r"феврал",
        r"март",
        r"апрел",
        r"ма[йяе]\b",
        r"июн",
        r"июл",
        r"август",
        r"сентябр",
        r"октябр",
        r"ноябр",
        r"декабр",
    )
]
REGIONS = {
    "or-all": "Орегон (весь штат)",
    "or-west": "Западный Орегон",
    "or-east": "Центральный и восточный Орегон",
    "or-local": "Отдельные районы Орегона",
    "uk": "Великобритания",
}
TYPES = {
    "posadka": "Посадка и посев",
    "uhod": "Уход",
    "urozhaj": "Урожай и хранение",
    "zashchita": "Защита растений",
    "zima": "Подготовка к зиме",
    "pochva": "Почва",
}
CROPS = {
    "chesnok": "Чеснок",
    "kartofel": "Картофель",
    "tomaty": "Томаты",
    "reven": "Ревень",
    "klubnika": "Клубника",
    "malina": "Малина",
    "golubika": "Голубика",
    "yabloni": "Яблони",
}
KIND_OK = {"university", "organization"}
FORBIDDEN = re.compile(r"(?i)\bвезде\b|в любом регионе|по всей росси|во всех регионах|рейтинг|₽|\bруб|\bцен[аеуы]\b")
NUM = re.compile(r"\d+(?:[.,]\d+)?")
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
        raise ValueError(f"недопустимое выражение: {expr}")

    return ev(ast.parse(expr.replace(",", "."), mode="eval"))


CONSTANTS = {"32", "5", "9", "2.54"}  # перевод °F→°C и дюймов в сантиметры


def resolve(sources: dict, ref: dict) -> tuple[dict | None, dict | None]:
    src = sources.get(ref.get("src"))
    if not src:
        return None, None
    pool = src.get("items", []) + src.get("quotes", [])
    return src, next((x for x in pool if x["id"] == ref.get("item")), None)


def texts(m: dict) -> list[tuple[str, str]]:
    out = [("title", m["title"]), ("summary", m["summary"]), ("applies", m["applies"])]
    out += [(f"need[{i}]", x["text"]) for i, x in enumerate(m.get("need", []))]
    out += [(f"steps[{i}]", x["text"]) for i, x in enumerate(m["steps"])]
    out += [(f"limits[{i}]", x["text"]) for i, x in enumerate(m["limits"])]
    out += [(f"checklist[{i}]", x) for i, x in enumerate(m["checklist"])]
    out += [(f"calc[{i}]", x["label"] + " " + x.get("conclusion", "")) for i, x in enumerate(m.get("calc", []))]
    return out


def validate(m: dict, sources: dict, slugs: set[str]) -> list[str]:
    err = []
    for k in ("slug", "title", "type", "summary", "applies", "timing", "steps", "limits", "checklist", "sources"):
        if not m.get(k):
            err.append(f"пустое поле {k}")
    if err:
        return err
    if m["type"] not in TYPES:
        err.append(f"неизвестный тип {m['type']}")
    if m.get("crop") and m["crop"] not in CROPS:
        err.append(f"неизвестная культура {m['crop']}")
    err += [f"связанный материал не найден: {r}" for r in m.get("related", []) if r not in slugs or r == m["slug"]]
    if m.get("producer", {}).get("mode") != "manual_standin":
        err.append("producer.mode должен быть manual_standin")
    used = set(m["sources"])
    err += [f"источник не найден: {s}" for s in used if s not in sources]
    if err:
        return err
    months, refs = set(), []
    for i, t in enumerate(m["timing"]):
        src, item = resolve(sources, t)
        if not item or t["src"] not in used:
            err.append(f"timing[{i}]: пункт {t.get('item')} не найден в источнике {t.get('src')}")
            continue
        region = item.get("region")
        if t["region"] != region:
            err.append(f"timing[{i}]: регион {t['region']} не совпадает с регионом пункта ({region})")
        if "month" in src:
            if t.get("month") != src["month"]:
                err.append(f"timing[{i}]: месяц {t.get('month')} ≠ месяцу календаря ({src['month']})")
        elif t.get("month"):
            en = [
                "january",
                "february",
                "march",
                "april",
                "may",
                "june",
                "july",
                "august",
                "september",
                "october",
                "november",
                "december",
            ][t["month"] - 1]
            if en not in item["quote"].lower():
                err.append(f"timing[{i}]: месяц {t['month']} не назван в цитате")
        if t.get("month"):
            months.add(t["month"])
        refs.append((t["src"], t["item"]))
    for part in ("steps", "limits", "need"):
        for i, x in enumerate(m.get(part, [])):
            for r in x.get("refs", []):
                src, item = resolve(sources, r)
                if not item or r["src"] not in used:
                    err.append(f"{part}[{i}]: ссылка на несуществующий пункт {r}")
                else:
                    refs.append((r["src"], r["item"]))
    for i, x in enumerate(m["limits"]):
        if x.get("kind") == "editorial":
            if x.get("refs"):
                err.append(f"limits[{i}]: совет редакции не может ссылаться на источник как на требование")
        elif x.get("kind") not in KIND_OK or not x.get("refs"):
            err.append(f"limits[{i}]: рекомендация без источника или неизвестного вида")
    allowed: set[str] = set()
    en = [
        "january",
        "february",
        "march",
        "april",
        "may",
        "june",
        "july",
        "august",
        "september",
        "october",
        "november",
        "december",
    ]
    for s, it in refs:
        _, item = resolve(sources, {"src": s, "item": it})
        line = item.get("text") or item.get("quote") + " " + " ".join(map(str, item.get("values", [])))
        months |= {
            k + 1 for k, name in enumerate(en) if re.search(r"\b" + name, (line + " " + item.get("when", "")).lower())
        }
        allowed |= {
            _num(n) for n in NUM.findall(line + " " + item.get("region_label", "") + " " + item.get("when", ""))
        }
    for i, c in enumerate(m.get("calc", [])):
        bad = [n for n in (_num(x) for x in NUM.findall(c["expr"])) if n not in allowed | CONSTANTS]
        if bad:
            err.append(f"calc[{i}]: исходные числа не из фактов: {bad}")
        if abs(_eval(c["expr"]) - float(c["result"])) > 0.051:
            err.append(f"calc[{i}]: {c['expr']} ≠ {c['result']}")
        allowed.add(_num(c["result"]))
    for where, t in texts(m):
        f = FORBIDDEN.search(t)
        if f:
            err.append(f"{where}: запрещённое утверждение «{f.group(0)}»")
        for n in NUM.findall(t):
            if _num(n) not in allowed:
                err.append(f"{where}: число {n} не подтверждено фактами источников материала")
        for k, rx in enumerate(MONTH_RX):
            if rx.search(t) and (k + 1) not in months:
                err.append(f"{where}: месяц «{MONTHS_RU[k]}» не подтверждён сроками материала")
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
    # все прочитанные источники: календарь месяца без работ тоже нужен (ссылка «полный перечень» на странице месяца)
    CONTENT.write_text(
        json.dumps({"site_id": SITE_ID, "items": items, "sources": sources}, ensure_ascii=False, indent=1) + "\n"
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
