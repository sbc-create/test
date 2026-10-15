"""Черновики рецептов для техники: проверки и снимок контента.

Сверх общих правил (ингредиенты ровно по разу, шаги по порядку и полностью,
нет 8 слов подряд из исходника) для приборов:
* числа в шаге (температура, минуты) — только из исходных шагов, на которые он ссылается;
* название режима в кавычках «…» — только если оно есть в этих исходных шагах;
* параметры прибора не переносятся между моделями: страница показывает режимы
  ровно этого рецепта с номером шага и пометкой «по данным источника».
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import re
import time
from pathlib import Path

from .importer import FACTS, PRIVATE

ROOT = Path(__file__).resolve().parents[1]
DRAFTS = ROOT / "data" / "drafts"
CONTENT = ROOT / "data" / "content.json"
HISTORY = ROOT / "data" / "history.jsonl"
WORDS = re.compile(r"[а-яёa-z0-9]+", re.I)
NUM = re.compile(r"\d+(?:[.,]\d+)?")
QUOTED = re.compile(r"[«\"“]([^»\"”]{2,30})[»\"”]")
FORBIDDEN = (
    "рейтинг",
    "отзыв",
    "ккал",
    "калорийн",
    "проверено на нашей кухне",
    "подходит для всех моделей",
    "любой модели",
)


def source_steps(rid: str) -> list[str]:
    return json.loads(gzip.decompress((PRIVATE / f"{rid}.json.gz").read_bytes()))["steps"]


def grams(text: str, n: int = 8) -> set[tuple]:
    w = [x.lower() for x in WORDS.findall(text)]
    return {tuple(w[i : i + n]) for i in range(len(w) - n + 1)}


def validate(d: dict) -> list[str]:
    errs = [
        f"нет поля {k}"
        for k in (
            "record_id",
            "title",
            "slug",
            "seo_title",
            "seo_description",
            "intro",
            "ingredients",
            "steps",
            "tags",
            "producer",
        )
        if k not in d
    ]
    if errs:
        return errs
    f = json.loads((FACTS / f"{d['record_id']}.json").read_text())
    src = source_steps(d["record_id"])
    if sorted(i["fact_index"] for i in d["ingredients"]) != list(range(len(f["ingredients"]))):
        errs.append("ингредиенты: нужны все индексы фактов ровно по разу")
    flat, last, sg = [], -1, set().union(*(grams(s) for s in src))
    for k, st in enumerate(d["steps"]):
        refs = st["source_steps"]
        if not refs or any(not 0 <= r < len(src) for r in refs):
            errs.append(f"шаг {k + 1}: ссылки вне диапазона")
            continue
        if min(refs) < last:
            errs.append(f"шаг {k + 1}: порядок исходных шагов нарушен")
        last = max(refs)
        flat += refs
        ref_text = " ".join(src[r] for r in refs)
        allowed = {x.replace(",", ".") for x in NUM.findall(ref_text)}
        for x in NUM.findall(st["text"] + " " + st.get("cue", "")):
            if x.replace(",", ".") not in allowed:
                errs.append(f"шаг {k + 1}: число {x} отсутствует в исходных шагах {refs}")
        for q in QUOTED.findall(st["text"]):
            if q.lower() not in ref_text.lower():
                errs.append(f"шаг {k + 1}: режим «{q}» не назван в исходных шагах {refs}")
        if grams(st["text"]) & sg:
            errs.append(f"шаг {k + 1}: дословный фрагмент исходника")
    if sorted(set(flat)) != list(range(len(src))):
        errs.append(f"шаги: не покрыты исходные {sorted(set(range(len(src))) - set(flat))}")
    text = (d["intro"] + " " + d["title"]).lower()
    errs += [f"запрещённое утверждение «{b}»" for b in FORBIDDEN if b in text]
    return errs


def build(published_at: str) -> dict:
    prev = {x["slug"]: x for x in json.loads(CONTENT.read_text())["items"]} if CONTENT.exists() else {}
    items, rep = [], {"ok": 0, "rejected": {}}
    for p in sorted(DRAFTS.glob("*.json")):
        d = json.loads(p.read_text())
        e = validate(d)
        if e:
            rep["rejected"][p.name] = e
            continue
        f = json.loads((FACTS / f"{d['record_id']}.json").read_text())
        h = hashlib.sha256(json.dumps(d, ensure_ascii=False, sort_keys=True).encode()).hexdigest()
        old = prev.get(d["slug"])
        changed = not old or old["text_hash"] != h
        version = (old["version"] + 1 if old else 1) if changed else old["version"]
        if changed:
            with HISTORY.open("a") as hf:
                hf.write(
                    json.dumps(
                        {
                            "at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                            "slug": d["slug"],
                            "version": version,
                            "text_hash": h,
                            "producer": d["producer"],
                        },
                        ensure_ascii=False,
                    )
                    + "\n"
                )
        a = f["appliance"]
        steps = [{"text": s["text"], "cue": s.get("cue"), "src": s["source_steps"]} for s in d["steps"]]

        def our_step(src_i: int, steps=steps) -> int | None:
            return next((k + 1 for k, s in enumerate(steps) if src_i in s["src"]), None)

        items.append(
            {
                "slug": d["slug"],
                "record_id": d["record_id"],
                "version": version,
                "text_hash": h,
                "published_at": (old or {}).get("published_at", published_at),
                "updated_at": published_at if changed else old["updated_at"],
                "title": d["title"],
                "seo_title": d["seo_title"],
                "seo_description": d["seo_description"],
                "intro": d["intro"],
                "appliance": a["appliance"],
                "tags": d["tags"],
                "servings": f["servings"],
                "times": {k: f[k] for k in ("prep_minutes", "cook_minutes", "total_minutes")},
                "modes": [{"name": m["name"], "step": our_step(m["step"])} for m in a["modes"]],
                "temperatures": [{"value_c": t["value_c"], "step": our_step(t["step"])} for t in a["temperatures"]],
                "appliance_times": [
                    {"min": t["min"], "max": t["max"], "step": our_step(t["step"])} for t in a["times"]
                ],
                "ingredients": [
                    {
                        "name": i["display_name"],
                        **{k: f["ingredients"][i["fact_index"]][k] for k in ("quantity", "unit")},
                    }
                    for i in d["ingredients"]
                ],
                "steps": steps,
                "source": {"url": f["source_url"], "fetched_at": f["fetched_at"], "parser": f["parser_version"]},
                "review_status": "ai_draft",
                "producer_mode": d["producer"]["mode"],
            }
        )
        rep["ok"] += 1
    items.sort(key=lambda x: (x["published_at"], x["slug"]), reverse=True)
    CONTENT.write_text(json.dumps({"site_id": "food-appliances", "items": items}, ensure_ascii=False, indent=1) + "\n")
    return rep


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["validate", "build"])
    ap.add_argument("--published-at", default=time.strftime("%Y-%m-%d"))
    a = ap.parse_args()
    if a.cmd == "validate":
        out = {p.name: validate(json.loads(p.read_text())) for p in sorted(DRAFTS.glob("*.json"))}
        print(json.dumps({k: v for k, v in out.items() if v} or {"ok": len(out)}, ensure_ascii=False, indent=1))
    else:
        print(json.dumps(build(a.published_at), ensure_ascii=False, indent=1))
