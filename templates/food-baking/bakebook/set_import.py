"""Импорт принятых блюд набора Qwen (QWEN-NIGHT-RECIPES-100X5-001) в книгу выпечки.

Вход — каталог batches/myfood.mobi/ из приёмника набора (tools/qwen_recipes_intake.py в корне репозитория):
по файлу на блюдо, один выбранный вариант подачи. Остальные варианты остаются во внутреннем архиве приёмника.

    python3 -m bakebook.set_import <каталог партии> --dry-run      # что будет сделано, без записи
    python3 -m bakebook.set_import <каталог партии> --limit 3      # пробная партия
    python3 -m bakebook.set_import <каталог партии>                # вся партия
    python3 -m bakebook.drafts build                                # снимок data/content.json

Каждое блюдо пишется штатными файлами шаблона — data/facts/<id>.json (факты базы), data/drafts/<id>.json
(текст выбранного варианта), закрытые шаги базы в var/food-baking/private (вне git) — и проходит тот же
валидатор drafts.validate, что и остальные рецепты. Журнал data/qwen-set-ledger.json хранит хэш записанного
черновика: повтор не создаёт дублей, а черновик, изменённый редактором после импорта, не перезаписывается.
Перед записью — копия затрагиваемых файлов в var/food-baking/backups/<время>/.
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import re
import shutil
import time
from pathlib import Path

from . import drafts
from .importer import FACTS, PRIVATE
from .net import REPO

ROOT = Path(__file__).resolve().parents[1]
LEDGER = ROOT / "data" / "qwen-set-ledger.json"
BACKUPS = REPO / "var" / "food-baking" / "backups"
UNITS = {
    "g": "g",
    "г": "g",
    "kg": "kg",
    "кг": "kg",
    "ml": "ml",
    "мл": "ml",
    "l": "l",
    "л": "l",
    "pcs": "pcs",
    "шт": "pcs",
    "шт.": "pcs",
    "штука": "pcs",
    "штуки": "pcs",
    "штук": "pcs",
    "tbsp": "tbsp",
    "ст. л.": "tbsp",
    "ст.л.": "tbsp",
    "столовая ложка": "tbsp",
    "столовые ложки": "tbsp",
    "tsp": "tsp",
    "ч. л.": "tsp",
    "ч.л.": "tsp",
    "чайная ложка": "tsp",
    "чайные ложки": "tsp",
    "cup": "cup",
    "стакан": "cup",
    "стакана": "cup",
    "pinch": "pinch",
    "щепотка": "pinch",
    "pack": "pack",
    "пачка": "pack",
    "clove": "clove",
    "зубчик": "clove",
    "to_taste": "to_taste",
    "по вкусу": "to_taste",
}
GROUP_RX = [
    ("zavarnoe", r"эклер|профитрол|заварн"),
    ("tort", r"торт|бисквит|чизкейк|рулет"),
    ("keks", r"кекс|маффин|капкейк|брауни"),
    ("hleb", r"хлеб|батон\b|чиабатт|фокачч|лепёшк|лепешк|багет"),
    ("pirog", r"пирог|шарлотк|тарт|киш\b|штрудель|галет"),
    ("pechene", r"печень|кукис|пряник|галет"),
    ("bulochki", r"булоч|булк|сдоб|плюшк|рогалик|ватрушк|кулич"),
    ("sloyki", r"слойк|слоён|слоен|круассан"),
    ("deserty", r"десерт|мусс|пудинг|панна|тирамису|безе|меренг|зефир|пастил|желе"),
]
TAG_RX = {
    "limon": "лимон",
    "shokolad": "шоколад|какао",
    "sliva": r"слив(?!к)",
    "yabloki": "яблок",
    "tykva": "тыкв",
    "orehi": "орех|миндал|фундук",
    "banan": "банан",
    "vishnya": "вишн",
    "vinograd": "виноград",
    "syr": r"\bсыр",
}
TR = dict(
    zip(
        "абвгдеёжзийклмнопрстуфхцчшщыэюя",
        "a b v g d e e zh z i j k l m n o p r s t u f h c ch sh shch y e yu ya".split(), strict=False,
    )
)
TR.update({"ъ": "", "ь": ""})


def slugify(title: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", "".join(TR.get(c, c) for c in title.lower())).strip("-")[:80].rstrip("-")


def sha(obj) -> str:
    return hashlib.sha256(json.dumps(obj, ensure_ascii=False, sort_keys=True).encode()).hexdigest()


def first_step(steps: list[str], n) -> int | None:
    return next((k for k, s in enumerate(steps) if re.search(rf"(?<!\d){n}(?!\d)", s)), None)


def to_files(rec: dict) -> tuple[str, dict, dict]:
    """Запись приёмника → (record_id, факты, черновик) в формате шаблона; ValueError — блюдо не принимается."""
    b, v = rec["base"], rec["variant"]
    rid = "fbq-" + hashlib.sha256(f"{rec['set_id']}:{rec['base_id']}".encode()).hexdigest()[:12]
    ings = []
    for i in b["ingredients"]:
        u = i.get("unit")
        unit = UNITS.get(str(u).strip().lower()) if u is not None else None
        if u is not None and unit is None:
            raise ValueError(f"неизвестная единица {u!r} у «{i['name']}»")
        ings.append({"raw": i.get("raw") or i["name"], "name": i["name"], "quantity": i.get("quantity"), "unit": unit})
    group = next((g for g, rx in GROUP_RX if re.search(rx, b["title"].lower())), None)
    if group is None:
        raise ValueError("раздел книги не определён по названию")
    oven = b.get("oven") or {}
    temps = [{"value_c": t, "step": first_step(b["steps"], t)} for t in oven.get("temperatures_c") or []]
    bakes = []
    for m in oven.get("bake_minutes") or []:
        lo, hi = (m, None) if isinstance(m, int) else (m[0], m[1])
        bakes.append({"min": lo, "max": hi, "step": first_step(b["steps"], lo)})
    if any(x["step"] is None for x in temps + bakes):
        raise ValueError("температура или время духовки не названы в шагах базы")
    form = oven.get("form")
    facts = {
        "source_url": b["source"]["url"],
        "title": b["title"],
        "servings": b["servings"],
        "prep_minutes": b.get("prep_minutes"),
        "cook_minutes": b.get("cook_minutes"),
        "total_minutes": b.get("total_minutes"),
        "ingredients": ings,
        "source_category": b.get("category"),
        "oven": {
            "temperatures": temps,
            "bake_times": bakes,
            "caution_steps": [],
            "forms": [{"text": form, "diameter_cm": None, "step": 0}] if form else [],
        },
        "parser_version": "qwen-set/1",
        "remarks": [],
        "complete": all(i["quantity"] is not None for i in ings),
        "record_id": rid,
        "group_hint": group,
        "step_count": len(b["steps"]),
        "fetched_at": b["source"].get("fetched_at") or time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    facts["content_hash"] = sha({k: facts[k] for k in ("title", "servings", "ingredients", "oven")})
    text = (b["title"] + " " + " ".join(i["name"] for i in b["ingredients"])).lower().replace("ё", "е")
    intro = v["intro"].strip()
    draft = {
        "title": v["title"][:90],
        "slug": slugify(v["title"]),
        "seo_title": v["title"][:70],
        "seo_description": intro if len(intro) <= 170 else intro[:167].rsplit(" ", 1)[0] + "…",
        "intro": intro,
        "ingredients": [{"fact_index": x["base_index"], "display_name": x["display_name"]} for x in v["ingredients"]],
        "steps": [
            {
                "text": s["text"],
                "source_steps": s["base_steps"],
                **({"cue": s["readiness_cue"]} if s.get("readiness_cue") else {}),
            }
            for s in v["steps"]
        ],
        "pitfalls": [],
        "tags": [k for k, rx in TAG_RX.items() if re.search(rx, text)][:5],
        "producer": {
            "provider": "qwen",
            "model": "qwen-night-set",
            "mode": "qwen_manual_export",
            "note": f"{rec['set_id']}/{rec['variant_id']} digest {rec['digest']}",
        },
        "record_id": rid,
        "editor_notes": [f"Набор {rec['set_id']}: база {rec['base_id']}, вариант {rec['label']} ({rec['variant_id']})"],
    }
    return rid, facts, draft


def run(batch: Path, *, limit: int | None = None, dry_run: bool = False) -> dict:
    files = sorted(batch.glob("*.json"))[: limit or None]
    ledger = json.loads(LEDGER.read_text()) if LEDGER.exists() else {}
    taken = {x["slug"]: x["record_id"] for x in json.loads(drafts.CONTENT.read_text())["items"]}
    res = {"files": len(files), "created": [], "updated": [], "unchanged": [], "deferred": [], "backup": None}
    bk = BACKUPS / time.strftime("%Y%m%dT%H%M%S")
    for f in files:
        rec = json.loads(f.read_text())
        bid = rec.get("base_id")
        if rec.get("site") != "myfood.mobi":
            res["deferred"].append({"base_id": bid, "reason": "партия другого сайта"})
            continue
        try:
            rid, facts, draft = to_files(rec)
        except (ValueError, KeyError) as e:
            res["deferred"].append({"base_id": bid, "reason": str(e)})
            continue
        if taken.get(draft["slug"], rid) != rid:
            res["deferred"].append({"base_id": bid, "reason": f"адрес /recept/{draft['slug']}/ занят"})
            continue
        dpath, fpath, ppath = drafts.DRAFTS / f"{rid}.json", FACTS / f"{rid}.json", PRIVATE / f"{rid}.json.gz"
        new_hash = sha(draft)
        if dpath.exists():
            on_disk = sha(json.loads(dpath.read_text()))
            if on_disk == new_hash:
                res["unchanged"].append({"base_id": bid, "slug": draft["slug"]})
                continue
            if on_disk != ledger.get(bid, {}).get("draft_hash"):
                res["deferred"].append({"base_id": bid, "reason": "черновик правил редактор — не трогаем"})
                continue
        kind = "updated" if dpath.exists() else "created"
        if dry_run:
            res[kind].append({"base_id": bid, "slug": draft["slug"]})
            continue
        for p in (dpath, fpath, ppath):  # копия затрагиваемых файлов до записи
            if p.exists():
                (bk / p.parent.name).mkdir(parents=True, exist_ok=True)
                shutil.copy2(p, bk / p.parent.name / p.name)
        res["backup"] = str(bk)
        old = {p: p.read_bytes() for p in (fpath, ppath) if p.exists()}
        PRIVATE.mkdir(parents=True, exist_ok=True)
        fpath.write_text(json.dumps(facts, ensure_ascii=False) + "\n")
        ppath.write_bytes(gzip.compress(json.dumps({"steps": rec["base"]["steps"]}, ensure_ascii=False).encode()))
        errs = drafts.validate(draft)
        if errs:  # откат только своих файлов
            for p in (fpath, ppath):
                p.write_bytes(old[p]) if p in old else p.unlink()
            res["deferred"].append({"base_id": bid, "reason": "; ".join(errs)[:300]})
            continue
        dpath.write_text(json.dumps(draft, ensure_ascii=False, indent=1) + "\n")
        ledger[bid] = {
            "record_id": rid,
            "draft_hash": new_hash,
            "variant_id": rec["variant_id"],
            "digest": rec["digest"],
            "at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        }
        taken[draft["slug"]] = rid
        res[kind].append({"base_id": bid, "slug": draft["slug"]})
    if not dry_run and (res["created"] or res["updated"]):
        LEDGER.write_text(json.dumps(ledger, ensure_ascii=False, indent=1, sort_keys=True) + "\n")
    for k in ("created", "updated", "unchanged", "deferred"):
        res[f"n_{k}"] = len(res[k])
    return res


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="food-baking set-import")
    ap.add_argument("batch", type=Path)
    ap.add_argument("--limit", type=int)
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args(argv)
    if not a.batch.is_dir():
        raise SystemExit(f"нет каталога партии {a.batch}")
    print(json.dumps(run(a.batch, limit=a.limit, dry_run=a.dry_run), ensure_ascii=False, indent=1))
    print("дальше: python3 -m bakebook.drafts build")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
