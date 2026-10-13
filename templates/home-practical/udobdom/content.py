"""Материалы home-practical: проверка против фактов источников и сборка data/content.json.

Правила (нарушение = материал не публикуется):
- каждое число в тексте материала есть в фактах источников, на которые он ссылается,
  или получено явным расчётом из блока `calc` (выражение пересчитывается);
- требование производителя (`manufacturer`) ссылается на источник-производителя,
  требование организации (`organization`) — на организацию; редакционный совет (`editorial`)
  на источник не ссылается и не выдаётся за требование;
- нет цены, рейтинга, отзывов и времени выполнения;
- помещение, задача, теги, связанные материалы — из реестров сайта.

Запуск: python3 -m udobdom.content validate | build
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

from udobdom.sources import fact_strings, load_all

ROOT = Path(__file__).resolve().parents[1]
MATERIALS = ROOT / "data" / "materials"
CONTENT = ROOT / "data" / "content.json"
HISTORY = ROOT / "data" / "history.jsonl"
SITE_ID = "home-practical"

ROOMS = {
    "kuhnya": "Кухня",
    "prihozhaya": "Прихожая",
    "spalnya": "Спальня",
    "gostinaya": "Гостиная",
    "vannaya": "Ванная",
    "rabochee-mesto": "Рабочее место",
}
TASKS = {
    "hranenie": "Хранение",
    "organizaciya": "Организация",
    "mebel": "Мебель",
    "uluchsheniya": "Небольшие улучшения",
}
TAGS = {
    "krepezh-k-stene": "Крепление к стене",
    "opasnost-padeniya": "Опасность падения или опрокидывания",
    "yashchiki-i-korobki": "Ящики и коробки",
    "obuv": "Обувь",
    "sverlenie": "Нужно сверлить",
    "bez-sverleniya": "Без сверления",
    "vlazhnye-pomeshcheniya": "Влажные помещения",
    "uhod": "Уход по инструкции производителя",
}
FORBIDDEN = re.compile(r"(?i)рейтинг|отзыв|₽|\bруб|стоимост|\bцен[аеуы]\b|за \d+ мин|\bминут")
NUM = re.compile(r"\d+(?:[.,]\d+)?")
OPS = {ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul, ast.Div: operator.truediv}


def _num(s: str) -> str:
    v = float(s.replace(",", "."))
    return str(int(v)) if v == int(v) else str(v)


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


def texts(m: dict) -> list[tuple[str, str]]:
    out = [("title", m["title"]), ("summary", m["summary"]), ("applies", m["applies"])]
    if m.get("not_for"):
        out.append(("not_for", m["not_for"]))
    out += [(f"need[{i}]", x["text"]) for i, x in enumerate(m["need"])]
    out += [(f"steps[{i}]", x["text"]) for i, x in enumerate(m["steps"])]
    out += [(f"limits[{i}]", x["text"]) for i, x in enumerate(m["limits"])]
    out += [(f"checklist[{i}]", x) for i, x in enumerate(m["checklist"])]
    out += [(f"calc[{i}]", x["label"] + " " + x.get("conclusion", "")) for i, x in enumerate(m.get("calc", []))]
    return out


def validate(m: dict, sources: dict, slugs: set[str]) -> list[str]:
    err = []
    for k in ("slug", "title", "room", "task", "summary", "applies", "need", "steps", "limits", "checklist", "sources"):
        if not m.get(k):
            err.append(f"пустое поле {k}")
    if err:
        return err
    if m["room"] not in ROOMS:
        err.append(f"неизвестное помещение {m['room']}")
    if m["task"] not in TASKS:
        err.append(f"неизвестная задача {m['task']}")
    err += [f"неизвестный тег {t}" for t in m.get("tags", []) if t not in TAGS]
    err += [f"связанный материал не найден: {r}" for r in m.get("related", []) if r not in slugs or r == m["slug"]]
    if m.get("producer", {}).get("mode") != "manual_standin":
        err.append("producer.mode должен быть manual_standin (тексты сессии Claude, не Qwen)")
    used = set(m["sources"])
    err += [f"источник не найден: {s}" for s in used if s not in sources]
    if err:
        return err
    allowed = {_num(n) for s in used for line in fact_strings(sources[s]) for n in NUM.findall(line)}
    for i, c in enumerate(m.get("calc", [])):
        nums = [_num(n) for n in NUM.findall(c["expr"])]
        bad = [n for n in nums if n not in allowed]
        if bad:
            err.append(f"calc[{i}]: исходные числа не из фактов: {bad}")
        if abs(_eval(c["expr"]) - float(c["result"])) > 1e-9:
            err.append(f"calc[{i}]: {c['expr']} ≠ {c['result']}")
        allowed.add(_num(c["result"]))
    for where, t in texts(m):
        if FORBIDDEN.search(t):
            err.append(f"{where}: запрещённое утверждение (цена/рейтинг/время): «{FORBIDDEN.search(t).group(0)}»")
        for n in NUM.findall(t):
            if _num(n) not in allowed:
                err.append(f"{where}: число {n} не подтверждено фактами источников материала")
    for i, x in enumerate(m["need"] + m["steps"]):
        for s in x.get("src", []):
            if s not in used:
                err.append(f"шаг/материал {i}: источник {s} не указан в sources")
    for i, x in enumerate(m["limits"]):
        kind, src = x.get("kind"), x.get("src")
        if kind not in ("manufacturer", "organization", "editorial"):
            err.append(f"limits[{i}]: неизвестный вид {kind}")
        elif kind == "editorial":
            if src:
                err.append(f"limits[{i}]: редакционный совет не может ссылаться на источник как на требование")
        elif not src or src not in used:
            err.append(f"limits[{i}]: требование без источника")
        elif sources[src]["kind"] != kind:
            err.append(f"limits[{i}]: вид {kind} не совпадает с источником ({sources[src]['kind']})")
    return err


def load_materials() -> list[dict]:
    return [json.loads(p.read_text()) for p in sorted(MATERIALS.glob("*.json"))]


def text_hash(m: dict) -> str:
    keep = {k: v for k, v in m.items() if k not in ("version", "published_at", "updated_at")}
    return hashlib.sha256(json.dumps(keep, ensure_ascii=False, sort_keys=True).encode()).hexdigest()


def build(published_at: str | None = None) -> dict:
    sources = load_all()
    mats = load_materials()
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
        item = {
            **m,
            "version": version,
            "text_hash": h,
            "published_at": old["published_at"] if old else now,
            "updated_at": now if not old or old["text_hash"] != h else old["updated_at"],
            "review_status": "ai_draft",
        }
        if not old or old["text_hash"] != h:
            with HISTORY.open("a") as f:
                f.write(json.dumps({"slug": m["slug"], "version": version, "text_hash": h, "at": now}) + "\n")
        items.append(item)
    used = sorted({s for m in items for s in m["sources"]})
    CONTENT.write_text(
        json.dumps(
            {"site_id": SITE_ID, "items": items, "sources": {s: sources[s] for s in used}},
            ensure_ascii=False,
            indent=1,
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
