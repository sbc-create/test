"""Импорт принятых блюд набора Qwen (QWEN-NIGHT-RECIPES-100X5-001) в редакционную базу food-daily.

Вход — каталог batches/bestreciept.site/ из приёмника набора (tools/qwen_recipes_intake.py в корне репозитория):
по файлу на блюдо, один выбранный вариант подачи. Остальные варианты остаются во внутреннем архиве приёмника.

    python3 -m fooddaily.set_import <каталог партии> --dry-run          # что будет сделано, без записи
    python3 -m fooddaily.set_import <каталог партии> --limit 3          # пробная партия
    python3 -m fooddaily.set_import <каталог партии>                    # вся партия
    python3 -m fooddaily.editorial snapshot                              # снимок для сайта

Правила:
* перед любой записью — копия БД в var/food-daily/backups/<время>.sqlite3;
* материал опознаётся по dedupe_key qwen-set:<набор>:<base_id> — повтор не размножает записи; тот же текст — no-op;
* если после импорта материал правил редактор (последняя версия не от импортёра), импорт его не трогает;
* адрес (slug) занят другим материалом — блюдо откладывается, адрес существующей страницы не меняется;
* происхождение (набор, база, вариант, digest) пишется в версию и в editor_notes — на страницы не выводится.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sqlite3
import time
from pathlib import Path

import jsonschema

from . import editorial
from .pipeline import DB_PATH, VAR, open_store
from .quality import publish_blockers
from .store import Store, VersionConflict
from .views import norm

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = json.loads((ROOT / "schemas" / "recipe-draft.schema.json").read_text())["properties"]["draft"]
ACTOR = "qwen-set-import"
UNITS = {
    "g": "g",
    "г": "g",
    "гр": "g",
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
    "clove": "clove",
    "зубчик": "clove",
    "зубчика": "clove",
    "pinch": "pinch",
    "щепотка": "pinch",
    "slice": "slice",
    "ломтик": "slice",
    "ломтика": "slice",
    "ломтиков": "slice",
    "can": "can",
    "банка": "can",
    "банки": "can",
    "head": "head",
    "кочан": "head",
    "bunch": "bunch",
    "пучок": "bunch",
    "to_taste": "to_taste",
    "по вкусу": "to_taste",
}
CATEGORY = [
    ("supy", r"суп|борщ|щи\b|солянк|уха\b|рассольник|окрошк|бульон"),
    ("salaty", r"салат|винегрет"),
    ("zavtraki", r"сырник|оладь|блин|каш|омлет|яичниц|запеканк|гренк|скрэмбл|шакшук|вареники ленив"),
    ("zakuski", r"закуск|бутерброд|лаваш|шаурм|паштет|рулетик|тартинк"),
    ("garniry", r"гарнир|пюре\b|картофельное пюре|рис отварн|гречк(а|у) отварн|овощи на гарнир"),
]
MEAL = {"zavtraki": "breakfast", "supy": "lunch", "zakuski": "snack"}
TAG_STEMS = {
    "tvorog": "творог",
    "kefir": "кефир",
    "moloko": "молок",
    "yajca": "яйц",
    "tykva": "тыкв",
    "pshyono": r"пшен(?!ичн)",  # «мука пшеничная» — не пшено
    "kurica": r"\bкур(?:иц|ин|ятин)",
    "syr": r"\bсыр(?!ник|ой\b|ая\b|ое\b|ые\b)",  # «сырники», «лук сырой» — не сыр
    "farsh": "фарш",
    "chechevica": "чечевиц",
    "pomidory": "помидор|томат",
    "ris": r"\bрис",
    "makarony": "макарон|спагетт|паст[аы]\b",
    "svinina": "свинин",
    "ryba": "рыб|минтай|треск|лосос|горбуш",
    "grechka": "гречк|гречнев",
    "griby": "гриб|шампиньон",
    "kapusta": "капуст",
}
METHOD_STEMS = {"na-skovorode": "сковород", "v-duhovke": "духовк", "tushenie": "туш", "varka": r"\bвар"}
TR = dict(
    zip(
        "абвгдеёжзийклмнопрстуфхцчшщыэюя",
        "a b v g d e e zh z i j k l m n o p r s t u f h c ch sh shch y e yu ya".split(),
        strict=False,
    )
)
TR.update({"ъ": "", "ь": ""})


def slugify(title: str) -> str:
    s = "".join(TR.get(c, c) for c in title.lower())
    return re.sub(r"[^a-z0-9]+", "-", s).strip("-")[:80].rstrip("-")


def category_of(title: str) -> str:
    t = title.lower()
    return next((k for k, rx in CATEGORY if re.search(rx, t)), "vtorye-blyuda")


def to_payload(rec: dict) -> dict:
    """Запись приёмника → payload версии {draft, facts, source}; ValueError — блюдо не принимается."""
    b, v = rec["base"], rec["variant"]
    ings = []
    for i in b["ingredients"]:
        unit = UNITS.get(str(i.get("unit") or "").strip().lower()) if i.get("unit") is not None else None
        if i.get("unit") is not None and unit is None:
            raise ValueError(f"неизвестная единица {i.get('unit')!r} у «{i['name']}»")
        ings.append(
            {
                "raw": i.get("raw") or f"{i['name']}, {i.get('quantity')} {i.get('unit') or ''}".strip(),
                "name": i["name"],
                "quantity": i.get("quantity"),
                "quantity_max": i.get("quantity_max"),
                "unit": unit,
                "scalable": unit not in (None, "to_taste", "pinch"),
                "note": None,
            }
        )
    facts = {
        "title": b["title"],
        "servings": b["servings"],
        "servings_raw": str(b["servings"]),
        "prep_minutes": b.get("prep_minutes"),
        "cook_minutes": b.get("cook_minutes"),
        "total_minutes": b.get("total_minutes"),
        "ingredients": ings,
        "method_hints": [],
        "topic_id": None,
    }
    cat = category_of(b["title"] + " " + (b.get("category") or ""))
    text = norm_text(" ".join([b["title"]] + [i["name"] for i in b["ingredients"]]))
    steps_text = norm_text(" ".join(b["steps"]))
    tags = [k for k, rx in TAG_STEMS.items() if re.search(rx, text)][:4]
    tags += [k for k, rx in METHOD_STEMS.items() if re.search(rx, steps_text)][: 6 - len(tags)]
    intro = v["intro"].strip()
    draft = {
        "title": v["title"][:90],
        "slug": slugify(v["title"]),
        "seo_title": v["title"][:70],
        "seo_description": (intro if len(intro) <= 170 else intro[:167].rsplit(" ", 1)[0] + "…"),
        "intro": intro,
        "ingredients": [{"fact_index": x["base_index"], "display_name": x["display_name"]} for x in v["ingredients"]],
        "steps": [
            {
                "text": s["text"],
                "source_steps": s["base_steps"],
                **({"readiness_cue": s["readiness_cue"]} if s.get("readiness_cue") else {}),
            }
            for s in v["steps"]
        ],
        "tips": [],
        "substitutions": [],
        "category": cat,
        "meal": MEAL.get(cat, "dinner"),
        "tags": tags,
        "editor_notes": [f"Набор {rec['set_id']}: база {rec['base_id']}, вариант {rec['label']} ({rec['variant_id']})"],
    }
    if len(draft["seo_description"]) < 50:
        draft["seo_description"] = (intro + " " + b["title"])[:170]
    jsonschema.validate(draft, SCHEMA)
    src = b["source"]
    source = {
        "url": src["url"],
        "host": re.sub(r"^www\.", "", src["url"].split("/")[2]),
        # дата получения — только из набора; не «сейчас»: иначе повтор импорта не узнаёт тот же текст
        "fetched_at": src.get("fetched_at") or rec.get("received_at"),
    }
    return {"draft": draft, "facts": facts, "source": source}


def norm_text(s: str) -> str:
    return norm(s)  # «куриное яйцо» → «яйцо»: яйца не делают блюдо «с курицей»


def backup(st: Store) -> Path:
    dst = VAR / "backups" / f"{time.strftime('%Y%m%dT%H%M%S')}.sqlite3"
    dst.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(dst) as out:
        st.db.backup(out)
    return dst


def run(batch: Path, *, limit: int | None = None, dry_run: bool = False, st: Store | None = None) -> dict:
    st = st or open_store()
    files = sorted(batch.glob("*.json"))[: limit or None]
    res = {"files": len(files), "created": [], "updated": [], "unchanged": [], "deferred": [], "backup": None}
    if not dry_run and files:
        res["backup"] = str(backup(st))
    for f in files:
        rec = json.loads(f.read_text())
        if rec.get("site") != "bestreciept.site":
            res["deferred"].append({"base_id": rec.get("base_id"), "reason": "партия другого сайта"})
            continue
        try:
            payload = to_payload(rec)
        except (ValueError, KeyError, jsonschema.ValidationError) as e:
            res["deferred"].append({"base_id": rec["base_id"], "reason": str(e).splitlines()[0][:200]})
            continue
        if blockers := publish_blockers(payload):
            res["deferred"].append({"base_id": rec["base_id"], "reason": "; ".join(blockers)})
            continue
        key = f"qwen-set:{rec['set_id']}:{rec['base_id']}"
        slug = payload["draft"]["slug"]
        row = st.db.execute("SELECT * FROM content WHERE dedupe_key=?", (key,)).fetchone()
        taken = st.db.execute("SELECT content_id FROM content WHERE slug=? AND dedupe_key<>?", (slug, key)).fetchone()
        if taken:
            res["deferred"].append({"base_id": rec["base_id"], "reason": f"адрес /recept/{slug}/ занят"})
            continue
        producer = {
            "provider": "qwen",
            "model": "qwen-night-set",
            "mode": "qwen_manual_export",
            "note": f"{rec['set_id']}/{rec['variant_id']} digest {rec['digest']}",
        }
        if row and row["current_version"]:
            last = st.version(row["content_id"])
            if last["created_by"] != ACTOR:
                res["deferred"].append({"base_id": rec["base_id"], "reason": "материал правил редактор — не трогаем"})
                continue
        if dry_run:
            res["updated" if row else "created"].append({"base_id": rec["base_id"], "slug": slug})
            continue
        cid = row["content_id"] if row else "fdq-" + hashlib.sha256(key.encode()).hexdigest()[:12]
        if not row:
            st.ensure_content(content_id=cid, slug=slug, dedupe_key=key)
        cur = st.current(cid)["current_version"]
        try:
            new = st.add_version(
                cid,
                payload,
                base_version=cur,
                source_ids=[rec["base_id"]],
                producer=producer,
                actor=ACTOR,
                reason=f"набор {rec['set_id']}, вариант {rec['label']}",
            )
        except VersionConflict as e:
            res["deferred"].append({"base_id": rec["base_id"], "reason": str(e)})
            continue
        if new == cur:
            res["unchanged"].append({"base_id": rec["base_id"], "slug": slug})
            continue
        pub = editorial.publish_preview(st, cid, actor=ACTOR)
        (res["updated"] if row else res["created"]).append(
            {"base_id": rec["base_id"], "slug": slug, "version": new, "published": pub["published"]}
        )
    for k in ("created", "updated", "unchanged", "deferred"):
        res[f"n_{k}"] = len(res[k])
    return res


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="food-daily set-import")
    ap.add_argument("batch", type=Path)
    ap.add_argument("--limit", type=int)
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args(argv)
    if not a.batch.is_dir():
        raise SystemExit(f"нет каталога партии {a.batch}")
    print(json.dumps(run(a.batch, limit=a.limit, dry_run=a.dry_run), ensure_ascii=False, indent=1))
    print(f"дальше: python3 -m fooddaily.editorial snapshot  (БД {DB_PATH})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
