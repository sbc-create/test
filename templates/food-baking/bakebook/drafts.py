"""Черновики рецептов выпечки: схема, проверки, версии, снимок контента.

Черновик хранится в data/drafts/<record_id>.json (наш текст + ссылки на факты).
Проверки сверяются с фактами и закрытым исходником шагов:
* каждый ингредиент фактов использован ровно один раз;
* шаги покрывают исходные по порядку;
* числа в тексте шагов и разборов — только из исходных шагов, на которые
  они ссылаются (температура, время, размеры формы не придумываются);
* нет 8 слов подряд из исходника;
* разбор ошибки ссылается на исходный шаг-предупреждение.
Вид теста определяется правилами по составу (`dough_type`), а не черновиком.
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
OPTIONAL = ("editor_notes", "record_id")
REQUIRED = (
    "title",
    "slug",
    "seo_title",
    "seo_description",
    "intro",
    "ingredients",
    "steps",
    "pitfalls",
    "tags",
    "producer",
)
FORBIDDEN = ("рейтинг", "отзыв", "ккал", "калорийн", "проверено на нашей кухне", "мы испекли", "мы приготовили")

DOUGH_RULES = [  # (вид, признак в названиях ингредиентов или шагах), порядок — приоритет
    ("bez-vypechki", lambda f, s: not f["oven"]["temperatures"] and "духовк" not in s),
    ("zavarnoe", lambda f, s: "завар" in s or "завар" in f["title"].lower()),
    ("drozhzhevoe", lambda f, s: any("дрожж" in i["name"].lower() for i in f["ingredients"])),
    ("sloenoe", lambda f, s: any("слоен" in i["name"].lower() for i in f["ingredients"])),
    ("pesochnoe", lambda f, s: "песочн" in s),
    ("biskvitnoe", lambda f, s: "бисквит" in s),
    (
        "keksovoe",
        lambda f, s: bool(re.search(r"разрыхлител|\bсод[аыуеой]\b", s))
        and any("яйц" in i["name"].lower() for i in f["ingredients"]),
    ),
]
DOUGH_LABELS = {
    "drozhzhevoe": (
        "Дрожжевое тесто",
        "Тесто на дрожжах: ему нужно время на подъём, а рецепт держится на тёплой жидкости и расстойке.",
    ),
    "keksovoe": (
        "Кексовое тесто на разрыхлителе",
        "Тесто на яйцах, муке и разрыхлителе или соде: поднимается в духовке, без расстойки.",
    ),
    "zavarnoe": (
        "Заварное тесто",
        "Тесто, которое заваривают на огне перед выпечкой: из него делают эклеры, пирожные и коржи.",
    ),
    "sloenoe": ("Слоёное тесто", "Выпечка из готового или домашнего слоёного теста."),
    "pesochnoe": ("Песочное тесто", "Рассыпчатое тесто на масле."),
    "biskvitnoe": ("Бисквитное тесто", "Взбитые яйца держат воздух: тесто поднимается без дрожжей."),
    "bez-vypechki": ("Без выпечки", "Десерты, которые собирают и охлаждают, а не пекут."),
}


def dough_type(facts: dict, steps: list[str]) -> str | None:
    text = " ".join(steps).lower()
    for key, rule in DOUGH_RULES:
        if rule(facts, text):
            return key
    return None


def source_steps(record_id: str) -> list[str]:
    return json.loads(gzip.decompress((PRIVATE / f"{record_id}.json.gz").read_bytes()))["steps"]


def _grams(text: str, n: int = 8) -> set[tuple]:
    w = [x.lower() for x in WORDS.findall(text)]
    return {tuple(w[i : i + n]) for i in range(len(w) - n + 1)}


def validate(draft: dict) -> list[str]:
    errs = [f"нет поля {k}" for k in REQUIRED if k not in draft]
    if errs:
        return errs
    f = json.loads((FACTS / f"{draft['record_id']}.json").read_text())
    src = source_steps(draft["record_id"])
    n_ing, n_src = len(f["ingredients"]), len(src)
    idx = sorted(i["fact_index"] for i in draft["ingredients"])
    if idx != list(range(n_ing)):
        errs.append(f"ингредиенты: нужны индексы 0..{n_ing - 1} ровно по разу, получено {idx}")
    flat, last = [], -1
    src_grams = set().union(*(_grams(s) for s in src))
    for k, st in enumerate(draft["steps"]):
        refs = st["source_steps"]
        if not refs or any(not 0 <= r < n_src for r in refs):
            errs.append(f"шаг {k + 1}: ссылки вне 0..{n_src - 1}")
            continue
        if min(refs) < last:
            errs.append(f"шаг {k + 1}: порядок исходных шагов нарушен")
        last = max(refs)
        flat += refs
        allowed = {x.replace(",", ".") for r in refs for x in NUM.findall(src[r])}
        for x in NUM.findall(st["text"] + " " + st.get("cue", "")):
            if x.replace(",", ".") not in allowed:
                errs.append(f"шаг {k + 1}: число {x} отсутствует в исходных шагах {refs}")
        if _grams(st["text"]) & src_grams:
            errs.append(f"шаг {k + 1}: дословный фрагмент исходника")
    if sorted(set(flat)) != list(range(n_src)):
        errs.append(f"шаги: не покрыты исходные {sorted(set(range(n_src)) - set(flat))}")
    for k, p in enumerate(draft["pitfalls"]):
        r = p["source_step"]
        if not 0 <= r < n_src:
            errs.append(f"разбор {k + 1}: шаг {r} вне диапазона")
            continue
        allowed = {x.replace(",", ".") for x in NUM.findall(src[r])}
        if any(x.replace(",", ".") not in allowed for x in NUM.findall(p["text"])):
            errs.append(f"разбор {k + 1}: число, которого нет в шаге {r}")
    text = " ".join([draft["intro"], draft["title"]] + [p["text"] for p in draft["pitfalls"]]).lower()
    errs += [f"запрещённое утверждение «{b}»" for b in FORBIDDEN if b in text]
    if draft["producer"].get("mode") not in ("qwen_api", "qwen_manual_export", "manual_standin"):
        errs.append("producer.mode обязателен")
    return errs


def build(published_at: str) -> dict:
    """Снимок контента из проверенных черновиков. Новая версия — при изменении
    текста; история версий в data/history.jsonl (дописывается)."""
    prev = {x["slug"]: x for x in json.loads(CONTENT.read_text())["items"]} if CONTENT.exists() else {}
    items, report = [], {"ok": 0, "rejected": {}}
    for p in sorted(DRAFTS.glob("*.json")):
        d = json.loads(p.read_text())
        errs = validate(d)
        if errs:
            report["rejected"][p.name] = errs
            continue
        f = json.loads((FACTS / f"{d['record_id']}.json").read_text())
        src = source_steps(d["record_id"])
        text_hash = hashlib.sha256(json.dumps(d, ensure_ascii=False, sort_keys=True).encode()).hexdigest()
        old = prev.get(d["slug"])
        version = old["version"] if old and old["text_hash"] == text_hash else (old["version"] + 1 if old else 1)
        if not old or old["text_hash"] != text_hash:
            with HISTORY.open("a") as h:
                h.write(
                    json.dumps(
                        {
                            "at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                            "slug": d["slug"],
                            "version": version,
                            "text_hash": text_hash,
                            "facts_hash": f["content_hash"],
                            "producer": d["producer"],
                        },
                        ensure_ascii=False,
                    )
                    + "\n"
                )
        ingr = [
            {"name": i["display_name"], **{k: f["ingredients"][i["fact_index"]][k] for k in ("quantity", "unit")}}
            for i in d["ingredients"]
        ]
        items.append(
            {
                "slug": d["slug"],
                "record_id": d["record_id"],
                "version": version,
                "text_hash": text_hash,
                "published_at": (old or {}).get("published_at", published_at),
                "updated_at": published_at if not old or old["text_hash"] != text_hash else old["updated_at"],
                "title": d["title"],
                "seo_title": d["seo_title"],
                "seo_description": d["seo_description"],
                "intro": d["intro"],
                "group": f["group_hint"],
                "dough": dough_type(f, src),
                "tags": d["tags"],
                "servings": f["servings"],
                "times": {k: f[k] for k in ("prep_minutes", "cook_minutes", "total_minutes")},
                "oven": f["oven"],
                "ingredients": ingr,
                "steps": [{"text": s["text"], "cue": s.get("cue"), "src": s["source_steps"]} for s in d["steps"]],
                "pitfalls": [
                    {
                        "text": p["text"],
                        "step_index": next(
                            (k for k, s in enumerate(d["steps"]) if p["source_step"] in s["source_steps"]), None
                        ),
                    }
                    for p in d["pitfalls"]
                ],
                "source": {"url": f["source_url"], "fetched_at": f["fetched_at"], "parser": f["parser_version"]},
                **({"nutrition": f["nutrition"]} if (f.get("nutrition") or {}).get("data_source") else {}),
                **({"image_job": f["image_job"]} if f.get("image_job") else {}),
                "review_status": "ai_draft",
                "baked_by_editor": False,
                "producer_mode": d["producer"]["mode"],
            }
        )
        report["ok"] += 1
    items.sort(key=lambda x: (x["published_at"], x["slug"]), reverse=True)
    CONTENT.write_text(json.dumps({"site_id": "food-baking", "items": items}, ensure_ascii=False, indent=1) + "\n")
    return report


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="food-baking drafts")
    ap.add_argument("cmd", choices=["validate", "build"])
    ap.add_argument("--published-at", default=time.strftime("%Y-%m-%d"))
    a = ap.parse_args(argv)
    if a.cmd == "validate":
        out = {p.name: validate(json.loads(p.read_text())) for p in sorted(DRAFTS.glob("*.json"))}
        print(
            json.dumps(
                {k: v for k, v in out.items() if v} or {"all": "ok", "n": len(out)}, ensure_ascii=False, indent=1
            )
        )
    else:
        print(json.dumps(build(a.published_at), ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
