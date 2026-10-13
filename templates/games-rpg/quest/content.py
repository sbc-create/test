"""Материалы games-rpg: проверка против фактов источника и реестра владения играми, сборка data/content.json.

Правила (нарушение = гайд не публикуется):
- игра гайда принадлежит этому сайту по реестру `config/ownership.yaml` (games-ownership/1) — один гайд не размножается;
- материал ссылается на страницу вики; каждое число в тексте — из фактов этой страницы или связанных источников;
- билд — только то, что класс получает по таблице источника; без «лучших» сборок;
- запрещены рейтинги, «лучший гайд», выдуманные таймкоды.

Запуск: python3 -m quest.content validate | build
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import time
from pathlib import Path

import yaml

from quest.sources import fact_text, load_all

ROOT = Path(__file__).resolve().parents[1]
MATERIALS = ROOT / "data" / "materials"
CONTENT = ROOT / "data" / "content.json"
HISTORY = ROOT / "data" / "history.jsonl"
SITE_ID = "games-rpg"
TYPES = {
    "character": "Персонажи",
    "build": "Билды",
    "mechanic": "Механики",
    "item": "Предметы",
    "quest": "Квесты",
    "version": "Версия игры",
}
FORBIDDEN = re.compile(
    r"(?i)рейтинг|лучший гайд|лучший билд|имба|мета-билд|tier|\d{1,2}:\d{2}|таймкод|₽|\bруб(?:\b|\.|л)"
)  # «руб», «руб.», «рублей»; не «рубящего»
NUM = re.compile(r"\d+(?:[.,]\d+)?")


def ownership() -> dict:
    return yaml.safe_load((ROOT / "config" / "ownership.yaml").read_text())


def _num(s: str) -> str:
    v = float(s.replace(",", "."))
    return str(int(v)) if v == int(v) else str(v)


def texts(m: dict) -> list[tuple[str, str]]:
    out = [("title", m["title"]), ("summary", m["summary"])]
    out += [(f"points[{i}]", x) for i, x in enumerate(m.get("points", []))]
    out += [(f"tips[{i}]", x) for i, x in enumerate(m.get("tips", []))]
    out += [(f"checklist[{i}]", x) for i, x in enumerate(m.get("checklist", []))]
    return out


def validate(m: dict, sources: dict, slugs: set[str]) -> list[str]:
    err = [f"пустое поле {k}" for k in ("slug", "game", "type", "src", "title", "summary") if not m.get(k)]
    if m.get("type") not in TYPES:
        err.append(f"неизвестный тип {m.get('type')}")
    if err:
        return err
    reg = ownership()
    owner = reg["games"].get(m["game"], {}).get("owner")
    if owner != SITE_ID:
        err.append(f"игра {m['game']} принадлежит сайту {owner}, не {SITE_ID} (реестр {reg['contract']})")
    used = [m["src"], *m.get("also", [])]
    err += [f"источник не найден: {s}" for s in used if s not in sources]
    if err:
        return err
    if sources[m["src"]].get("game") != m["game"]:
        err.append("источник относится к другой игре")
    if m.get("producer", {}).get("mode") != "manual_standin":
        err.append("producer.mode должен быть manual_standin")
    err += [f"связанный гайд не найден: {r}" for r in m.get("related", []) if r not in slugs or r == m["slug"]]
    for v in m.get("videos", []):
        if v not in sources or sources[v]["kind"] != "video" or not sources[v].get("embeddable"):
            err.append(f"видео {v} не проверено через oEmbed")
    facts = " ".join(fact_text(sources[s]) for s in used)
    allowed = {_num(n) for n in NUM.findall(facts)}
    for where, t in texts(m):
        f = FORBIDDEN.search(t)
        if f:
            err.append(f"{where}: запрещённое утверждение «{f.group(0)}»")
        for n in NUM.findall(t):
            if _num(n) not in allowed:
                err.append(f"{where}: число {n} не подтверждено источником")
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
    CONTENT.write_text(
        json.dumps(
            {"site_id": SITE_ID, "ownership": ownership(), "items": items, "sources": sources},
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
        rep = {m["slug"]: validate(m, sources, {x["slug"] for x in mats}) or "ok" for m in mats}
    print(json.dumps(rep, ensure_ascii=False, indent=1))
    return 0 if all(v == "ok" for v in rep.values()) else 1


if __name__ == "__main__":
    sys.exit(main())
