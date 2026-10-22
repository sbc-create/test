"""Приём набора рецептов Qwen (QWEN-NIGHT-RECIPES-100X5-001) для bestreciept.site и myfood.mobi.

Набор лежит в среде Qwen; на этот сервер его кладут в каталог приёма INTAKE — архивом
<SET_ID>.tar.gz или каталогом <SET_ID>/. Инструмент только читает набор и публичный контент
сайтов и пишет в свой каталог вывода; сайты он не меняет — это делают адаптеры шаблонов
(fooddaily.set_import, bakebook.set_import) с резервной копией и пробной партией.

    python3 tools/qwen_recipes_intake.py inspect <архив|каталог>   # файлы, ключи, количества
    python3 tools/qwen_recipes_intake.py plan <архив|каталог> [--out DIR]

Ожидаемая структура (контракт qwen-recipes-set/1). Если пришло другое, `inspect` показывает
фактическую структуру, а `plan` останавливается с BLOCKED_INPUT — без догадок о полях:

    manifest.json  {"set_id", "base_count", "variant_count", "items": [{"base_id", "file",
                    "variants": [{"variant_id", "label": "V1".."V5", "file"}]}]}
    base           {"base_id", "title", "servings", "prep_minutes"?, "cook_minutes"?,
                    "total_minutes"?, "ingredients": [{"name", "quantity", "quantity_max"?,
                    "unit", "raw"?}], "steps": ["текст шага", …], "category"?,
                    "oven"?: {"temperatures_c": [..], "bake_minutes": [..], "form"?},
                    "source": {"url"}}
    variant        {"variant_id", "base_id", "label", "title", "intro",
                    "ingredients": [{"base_index", "display_name"}],
                    "steps": [{"text", "base_steps": [i, …], "readiness_cue"?}]}

Фактический формат поставки 22.10.2026 (qwen-night/1) читается тем же инструментом — `normalize`
переводит его в контракт выше, ничего не досочиняя:

    manifest/manifest-*.json     {"run_id", "scope": {"total_themes", "total_variants"}, …}
    recipes/base_recipes/*.json  {"base_recipe_id", "theme", "source_url"?,
                                  "metadata": {"servings", "cook_time_minutes"},
                                  "locked_ingredients": [{"original_name", "quantity",
                                                          "unit", "notes"}],
                                  "locked_steps": [{"instruction"}]}
    variants/<base>-V<n>.json    {"variant_id", "base_recipe_id", "variant_type", "title",
                                  "intro"?, "ingredients"?, "steps"?: ["текст", …], …}

  * название страницы — название блюда из базы (заголовки вариантов — подписи подачи);
  * количества и единицы — только из базы; список ингредиентов варианта не публикуется;
  * шаг варианта сопоставляется с шагом базы по порядку, только при равном числе шагов;
  * вариант без списка шагов строками (V2–V4 без steps) не публикуется: публиковать нечего.

Правила (сверх структуры):
* 100 базовых рецептов и 500 вариантов подтверждаются файлами, а не манифестом.
* Вариант подачи — не самостоятельный рецепт: на блюдо публикуется один вариант,
  остальные — во внутренний архив.
* Вариант не меняет факты базы: каждый ингредиент базы ровно один раз, без новых продуктов;
  шаги покрывают шаги базы по порядку; числа времени и температуры — только из шага базы,
  на который ссылается шаг варианта.
* Без источника фактов (source.url) рецепт не публикуется — BLOCKED_RIGHTS.
* Блюдо, совпадающее с опубликованным на сайте, не создаёт дубль: уходит на сверку
  редактору (update_candidate).
* Источник-заглушка (не http) — то же BLOCKED_RIGHTS; количество, которое сама база помечает как
  неясное («вероятно», «уточнить»), — черновик.
* Текст варианта — пересказ, а не текст источника: шаги, дословно повторяющие шаги базы,
  не публикуются.
* Шаг варианта не теряет время и температуру шага базы; продукт, который база называет в шагах,
  называется и в шагах варианта; вступление — не короче 40 знаков, без «я», «проверенный»,
  «полезный».
* Повторный план даёт тот же результат (digest); вывод не содержит секретов.
"""

from __future__ import annotations

import argparse
import difflib
import hashlib
import json
import re
import sys
import tarfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SET_ID = "QWEN-NIGHT-RECIPES-100X5-001"
INTAKE = (
    REPO / "var" / "qwen-intake"
)  # каталог приёма (вне git): /home/claude/wt-template-food-daily/var/qwen-intake
EXPECTED = {"base": 100, "variants": 500, "per_base": 5}
LABELS = ("V1", "V2", "V3", "V4", "V5")
SITES = {  # публичный контент сайтов: только чтение, для поиска совпадений
    "bestreciept.site": REPO.parent
    / "wt-template-food-daily-c/templates/food-daily/data/content-snapshot.json",
    "myfood.mobi": REPO.parent
    / "wt-template-food-baking-b/templates/food-baking/data/content.json",
}
BAKING = re.compile(
    r"выпеч|пирог|пирож|торт|кекс|маффин|печень[еяю]|печений|булоч|булк|хлеб|багет|чиабат|фокач|лепёшк|лепешк|слойк|круассан|"
    r"эклер|профитрол|тесто|дрожж|бисквит|рулет|шарлотк|ватрушк|чизкейк|брауни|штрудель|десерт|пудинг|мусс|"
    r"панна-котт|тирамису|безе|меренг|зефир|пастил|печёное|кулич",
    re.I,
)
NOT_BAKING = re.compile(
    r"блин|оладь|сырник|пицц|пельмен|вареник|лаваш|шаурм", re.I
)  # тесто, но повседневная еда
FORBIDDEN = re.compile(
    r"\bИИ\b|нейросет|\bQwen\b|\bмодел[иьяей]\b|черновик|сгенерирован|\bV[1-5]\b|рейтинг|отзыв|калори|"
    r"проверено (поваром|редакцией)|наш(а|ей) редакци",
    re.I,
)
NUM_UNIT = re.compile(r"(\d+(?:[.,]\d+)?)\s*(?:°|градус|мин|час|ч\b|сек)", re.I)
STOP = {"с", "и", "на", "из", "в", "по", "для", "без", "под", "к", "со", "а"}


# ---------------------------------------------------------------- чтение набора
UNREADABLE = "_unreadable"  # ключ в результате read_set: файлы, которые не разобрались как JSON


def _load(name: str, raw: bytes, out: dict) -> None:
    try:
        out[name] = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as e:
        out.setdefault(UNREADABLE, {})[name] = str(e)[:80]


def read_set(src: Path) -> dict[str, dict]:
    """{относительный путь: JSON} — из каталога или .tar.gz; только .json внутри набора.

    Неразборчивые файлы не роняют приём, а перечисляются под ключом UNREADABLE: если среди них
    окажется рецепт, счёт файлов не сойдётся и это будет видно в отчёте."""
    out: dict[str, dict] = {}
    if src.is_dir():
        for p in sorted(src.rglob("*.json")):
            if p.is_file() and not p.is_symlink():
                _load(str(p.relative_to(src)), p.read_bytes(), out)
        return out
    with tarfile.open(src) as t:
        for m in t.getmembers():
            if (
                not m.isfile()
                or not m.name.endswith(".json")
                or m.name.startswith("/")
                or ".." in m.name.split("/")
            ):
                continue
            name = m.name.split("/", 1)[1] if m.name.startswith(SET_ID + "/") else m.name
            _load(name, t.extractfile(m).read(), out)
    return out


# ---------------------------------------------------------------- формат qwen-night/1
def normalize(files: dict) -> dict:
    """Поставка qwen-night/1 → контракт qwen-recipes-set/1; иной вход возвращается как есть."""
    bases = {
        n: d
        for n, d in files.items()
        if n.startswith("recipes/") and isinstance(d, dict) and "base_recipe_id" in d
    }
    if not bases or any(n.rsplit("/", 1)[-1].lower() == "manifest.json" for n in files):
        return files
    out: dict = {UNREADABLE: files.get(UNREADABLE, {})} if files.get(UNREADABLE) else {}
    raw_man = next((d for n, d in files.items() if n.startswith("manifest/")), {}) or {}
    variants = [
        d
        for n, d in files.items()
        if n.startswith("variants/") and isinstance(d, dict) and "variant_id" in d
    ]
    items = []
    for _, d in sorted(bases.items()):
        bid = d["base_recipe_id"]
        meta = d.get("metadata") or {}
        url = d.get("source_url") or ""
        b = {
            "base_id": bid,
            "title": d.get("theme"),
            "servings": meta.get("servings"),
            "cook_minutes": meta.get("cook_time_minutes"),
            "ingredients": [
                {
                    "name": i.get("original_name"),
                    "quantity": i.get("quantity"),
                    "unit": i.get("unit"),
                    "note": i.get("notes") or None,
                }
                for i in d.get("locked_ingredients") or []
            ],
            "steps": [s.get("instruction") for s in d.get("locked_steps") or []],
            "source": {"url": url} if url.startswith("http") else {},
            "source_raw": url,
        }
        out[f"base/{bid}.json"] = b
        vs = []
        for v in sorted(
            (v for v in variants if v.get("base_recipe_id") == bid), key=lambda v: v["variant_id"]
        ):
            steps = v.get("steps")
            texts = (
                [re.sub(r"^\s*\d+[.)]\s*", "", x).strip() for x in steps]
                if isinstance(steps, list) and steps and all(isinstance(x, str) for x in steps)
                else None
            )
            same_len = texts is not None and len(texts) == len(b["steps"])
            nv = {
                "variant_id": v["variant_id"],
                "base_id": bid,
                "label": v.get("variant_type"),
                "title": b["title"],
                "intro": (v.get("intro") or "").strip(),
                "ingredients": [
                    {"base_index": k, "display_name": i["name"]}
                    for k, i in enumerate(b["ingredients"])
                ],
                "steps": [
                    {"text": t, "base_steps": [k] if same_len else []}
                    for k, t in enumerate(texts or [])
                ],
            }
            out[f"variants/{v['variant_id']}.json"] = nv
            vs.append(
                {
                    "variant_id": v["variant_id"],
                    "label": nv["label"],
                    "file": f"variants/{v['variant_id']}.json",
                }
            )
        items.append({"base_id": bid, "file": f"base/{bid}.json", "variants": vs})
    out["manifest.json"] = {
        "set_id": raw_man.get("run_id", SET_ID),
        "format": "qwen-night/1",
        "base_count": (raw_man.get("scope") or {}).get("total_themes"),
        "variant_count": (raw_man.get("scope") or {}).get("total_variants"),
        "items": items,
    }
    return out


def inspect(files: dict[str, dict]) -> dict:
    bad = files.get(UNREADABLE, {})
    files = {k: v for k, v in files.items() if k != UNREADABLE}
    shapes: dict[str, int] = {}
    for d in files.values():
        k = ",".join(sorted(d)) if isinstance(d, dict) else type(d).__name__
        shapes[k] = shapes.get(k, 0) + 1
    labels: dict[str, int] = {}
    for d in files.values():
        if isinstance(d, dict) and isinstance(d.get("label"), str):
            labels[d["label"]] = labels.get(d["label"], 0) + 1
    return {
        "json_files": len(files),
        "unreadable": bad,
        "manifest": next(
            (n for n in files if n.rsplit("/", 1)[-1].lower() in ("manifest.json",)), None
        ),
        "key_sets": dict(sorted(shapes.items(), key=lambda kv: -kv[1])[:12]),
        "labels": labels,
        "with_base_id_no_label": sum(
            1 for d in files.values() if isinstance(d, dict) and "base_id" in d and "label" not in d
        ),
    }


# ---------------------------------------------------------------- проверки
def norm(s: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^\w\s]+", " ", s.lower().replace("ё", "е"))).strip()


def title_key(s: str) -> frozenset:
    return frozenset(w for w in norm(s).split() if w not in STOP and not w.isdigit())


def similar(a: frozenset, b: frozenset) -> bool:
    """То же блюдо: по основам слов — почти одинаковые названия или короткое целиком входит
    в длинное («Плов с курицей» ⊂ «Плов с курицей на сковороде»; «с творогом» = «из творога»)."""
    a, b = frozenset(stem(w) for w in a), frozenset(stem(w) for w in b)
    if not (a and b):
        return False
    return len(a & b) / len(a | b) >= 0.75 or (min(len(a), len(b)) >= 2 and (a <= b or b <= a))


UNSURE = re.compile(r"вероятно|возможно|уточн|неясн|не указан", re.I)
CLAIM = re.compile(
    r"\bя\b|\bмо[йяеё]\b|делюсь|проверенн|полезн|диетич|идеальн|секрет|самы[хй] популярн", re.I
)
LOST_NUM = re.compile(r"(\d+(?:[.,]\d+)?(?:-\d+)?)\s*(?:°|градус|мин|час|ч\b|сек)", re.I)
VERB = {  # продукт назван глаголом: «посолить» — соль, «поперчить» — перец
    "сол": r"сол[ьиея]|посол|подсол",
    "пер": r"перец|перц|поперч",
}


def stem(w: str) -> str:
    return w[:4] if len(w) > 5 else w[:3]


def mentions(text: str, name: str) -> bool:
    words = [w for w in norm(name).split() if len(w) > 2]
    if not words:
        return True
    head = stem(words[0])
    if head in VERB:
        return bool(re.search(VERB[head], text))
    return any(stem(t) == stem(w) for t in text.split() for w in words)


def check_base(b: dict) -> list[str]:
    errs = []
    for k in ("base_id", "title", "servings", "ingredients", "steps"):
        if not b.get(k):
            errs.append(f"нет поля {k}")
    if not (b.get("source") or {}).get("url", "").startswith("http"):
        raw = b.get("source_raw") or ""
        errs.append(
            f"BLOCKED_RIGHTS: источник — заглушка {raw!r}"
            if raw
            else "BLOCKED_RIGHTS: нет источника фактов (source.url)"
        )
    for i, ing in enumerate(b.get("ingredients") or []):
        if not ing.get("name"):
            errs.append(f"ингредиент {i}: нет названия")
        elif UNSURE.search(ing.get("note") or ""):
            errs.append(f"количество «{ing['name']}» не подтверждено: {ing['note']}")
    if not all(isinstance(s, str) and s.strip() for s in b.get("steps") or []):
        errs.append("шаги базы — непустые строки")
    return errs


def check_variant(v: dict, b: dict) -> list[str]:
    errs = []
    for k in ("variant_id", "base_id", "label", "title", "ingredients", "steps"):
        if not v.get(k):
            errs.append("нет текста шагов" if k == "steps" else f"нет поля {k}")
    if errs:
        return errs
    v = {**v, "intro": v.get("intro") or ""}
    if v["base_id"] != b["base_id"]:
        errs.append("base_id не совпадает с базой")
    if v["label"] not in LABELS:
        errs.append(f"метка {v['label']!r} не из V1–V5")
    idx = [i.get("base_index") for i in v["ingredients"]]
    if sorted(x for x in idx if isinstance(x, int)) != list(range(len(b["ingredients"]))) or len(
        idx
    ) != len(b["ingredients"]):
        errs.append("ингредиенты: каждый ингредиент базы ровно один раз, без новых продуктов")
    covered: list[int] = []
    if not any(s.get("base_steps") for s in v["steps"]):
        return errs + [
            f"шагов {len(v['steps'])} при {len(b['steps'])} в базе — не сопоставить по порядку"
        ]
    for n, s in enumerate(v["steps"]):
        refs = s.get("base_steps") or []
        if not refs or not all(isinstance(r, int) and 0 <= r < len(b["steps"]) for r in refs):
            errs.append(f"шаг {n + 1}: нет ссылки на шаги базы")
            continue
        covered += refs
        src = " ".join(b["steps"][r] for r in refs)
        for num in NUM_UNIT.findall(s.get("text", "") + " " + (s.get("readiness_cue") or "")):
            if num.replace(",", ".") not in src.replace(",", "."):
                errs.append(f"шаг {n + 1}: число {num} не из шага базы")
    if covered != sorted(covered) or sorted(set(covered)) != list(range(len(b["steps"]))):
        errs.append("шаги не покрывают шаги базы по порядку")
    for n, s in enumerate(v["steps"]):
        refs = [
            r for r in s.get("base_steps") or [] if isinstance(r, int) and 0 <= r < len(b["steps"])
        ]
        src = " ".join(b["steps"][r] for r in refs).replace(",", ".")
        mine = (s.get("text", "") + " " + (s.get("readiness_cue") or "")).replace(",", ".")
        for num in LOST_NUM.findall(src):
            if num not in mine:
                errs.append(f"шаг {n + 1}: потеряно {num} из шага базы")
    base_text, var_text = (
        norm(" ".join(b["steps"])),
        norm(" ".join(s.get("text", "") for s in v["steps"])),
    )
    lost = [
        i["name"]
        for i in b["ingredients"]
        if mentions(base_text, i["name"]) and not mentions(var_text, i["name"])
    ]
    if lost:
        errs.append("в шагах не используются: " + ", ".join(lost))
    same = sum(
        1
        for s in v["steps"]
        for r in (s.get("base_steps") or [])[:1]
        if isinstance(r, int)
        and r < len(b["steps"])
        and difflib.SequenceMatcher(None, norm(s.get("text", "")), norm(b["steps"][r])).ratio()
        > 0.9
    )
    if v["steps"] and same * 2 > len(v["steps"]):
        errs.append("шаги дословно повторяют текст источника")
    if len(v["intro"].strip()) < 40:
        errs.append("вступление короче 40 знаков")
    elif m := CLAIM.search(v["intro"]):
        errs.append(f"во вступлении недопустимое: {m.group(0)!r}")
    text = " ".join(
        [v["title"], v["intro"]]
        + [s.get("text", "") + " " + (s.get("readiness_cue") or "") for s in v["steps"]]
    )
    if m := FORBIDDEN.search(text):
        errs.append(f"служебная или недопустимая формулировка: {m.group(0)!r}")
    return errs


def score(v: dict) -> tuple:
    """Публикуемый вариант: больше признаков готовности, подробнее шаги; затем меньшая метка."""
    cues = sum(1 for s in v["steps"] if s.get("readiness_cue"))
    return (-cues, -len(v["steps"]), v["label"])


def route(b: dict, v: dict) -> str:
    text = " ".join([b.get("category") or "", b["title"], v.get("title", "")])
    oven = bool((b.get("oven") or {}).get("temperatures_c"))
    if NOT_BAKING.search(text):
        return "bestreciept.site"
    return (
        "myfood.mobi"
        if BAKING.search(text) or (oven and BAKING.search(" ".join(b["steps"])))
        else "bestreciept.site"
    )


def published_titles() -> dict[str, list[tuple[str, frozenset]]]:
    out = {}
    for site, p in SITES.items():
        items = json.loads(p.read_text())["items"] if p.exists() else []
        out[site] = [
            (x["slug"], title_key(x.get("title") or x.get("draft", {}).get("title", "")))
            for x in items
        ]
    return out


def digest(obj) -> str:
    return hashlib.sha256(json.dumps(obj, ensure_ascii=False, sort_keys=True).encode()).hexdigest()[
        :16
    ]


# ---------------------------------------------------------------- план
def plan(files: dict[str, dict], existing: dict | None = None) -> dict:
    """Порядок отбора блюда: дубль (сайт, затем набор) → права → качество вариантов.

    Каждое непринятое блюдо — в deferred с kind (rights | duplicate | quality | missing)
    и причиной."""
    files = normalize(files)
    man = next(
        (d for n, d in files.items() if n.rsplit("/", 1)[-1].lower() == "manifest.json"), None
    )
    if not man or not isinstance(man.get("items"), list):
        return {
            "status": "BLOCKED_INPUT",
            "reason": "нет manifest.json по контракту qwen-recipes-set/1",
            "inspect": inspect(files),
        }
    existing = published_titles() if existing is None else existing
    by_id = {
        d.get("base_id"): d
        for n, d in files.items()
        if n != UNREADABLE and isinstance(d, dict) and "label" not in d and "base_id" in d
    }
    variants = [
        d for n, d in files.items() if n != UNREADABLE and isinstance(d, dict) and "label" in d
    ]
    counts = {
        "manifest_base": man.get("base_count"),
        "manifest_variants": man.get("variant_count"),
        "files_base": len(by_id),
        "files_variants": len(variants),
    }
    if files.get(UNREADABLE):
        counts["unreadable_files"] = sorted(files[UNREADABLE])
    accepted: dict[str, list] = {s: [] for s in SITES}
    deferred, archive, seen_titles = [], [], []

    def defer(kind, b, bid, reason, vs, why, **extra):
        deferred.append(
            {
                "base_id": bid,
                "title": (b or {}).get("title"),
                "kind": kind,
                "reason": reason,
                **extra,
            }
        )
        archive.extend(
            {"variant_id": v.get("variant_id"), "base_id": bid, "why": why(v)} for v in vs
        )

    for item in man["items"]:
        bid = item.get("base_id")
        b = by_id.get(bid)
        vs = [d for d in variants if d.get("base_id") == bid]
        if b is None:
            defer("missing", None, bid, "нет файла базового рецепта", vs, lambda v: "нет базы")
            continue
        if len(vs) != EXPECTED["per_base"]:
            counts.setdefault("bases_without_5_variants", []).append(bid)
        checked = {v["variant_id"]: check_variant(v, b) for v in vs}
        errs = check_base(b)
        site = route(b, {})
        key = title_key(b["title"])
        match = next((slug for slug, k in existing.get(site, []) if similar(k, key)), None)
        dup_set = next((t for t, k in seen_titles if similar(k, key)), None)
        seen_titles.append((bid, key))
        if match or dup_set:
            reason = (
                f"совпадает с опубликованным {site}/recept/{match}/ — сверка редактором, без дубля"
                if match
                else f"дубль блюда внутри набора: {dup_set}"
            )
            extra = {"site": site, "update_candidate": match} if match else {"site": site}
            defer(
                "duplicate",
                b,
                bid,
                reason,
                vs,
                lambda v, c=checked: "; ".join(c[v["variant_id"]]) or "дубль блюда",
                **extra,
            )
            continue
        if any(e.startswith("BLOCKED_RIGHTS") for e in errs):
            defer("rights", b, bid, "; ".join(errs), vs, lambda v: "база не принята: права")
            continue
        if errs:
            defer("quality", b, bid, "; ".join(errs), vs, lambda v: "база не принята")
            continue
        good = sorted((v for v in vs if not checked[v["variant_id"]]), key=score)
        if not good:
            near = sorted(
                (v for v in vs if v.get("steps")),
                key=lambda v: (len(checked[v["variant_id"]]), v["label"]),
            )
            detail = (
                f"; ближе всех {near[0]['label']}: " + "; ".join(checked[near[0]["variant_id"]][:4])
                if near
                else ""
            )
            defer(
                "quality",
                b,
                bid,
                "ни один вариант V1–V5 не передаёт рецепт полностью" + detail,
                vs,
                lambda v, c=checked: "; ".join(c[v["variant_id"]]),
                site=site,
            )
            continue
        pick = good[0]
        archive += [
            {
                "variant_id": v["variant_id"],
                "base_id": bid,
                "why": "; ".join(checked[v["variant_id"]]) or "вариант подачи того же блюда",
            }
            for v in vs
            if v is not pick
        ]
        rec = {
            "set_id": man.get("set_id", SET_ID),
            "base_id": bid,
            "variant_id": pick["variant_id"],
            "label": pick["label"],
            "site": route(b, pick),
            "base": b,
            "variant": pick,
        }
        rec["digest"] = digest({"base": b, "variant": pick})
        accepted[rec["site"]].append(rec)
    kinds: dict[str, int] = {}
    for d in deferred:
        kinds[d["kind"]] = kinds.get(d["kind"], 0) + 1
    return {
        "status": "OK",
        "set_id": man.get("set_id", SET_ID),
        "format": man.get("format", "qwen-recipes-set/1"),
        "counts": counts,
        "accepted": {s: len(v) for s, v in accepted.items()},
        "deferred_by_kind": kinds,
        "deferred": deferred,
        "archived_variants": len(archive),
        "_accepted": accepted,
        "_archive": archive,
    }


def write(result: dict, out: Path) -> dict:
    """Вывод: report.json (без текстов), batches/<сайт>/<base_id>.json, archive.json."""
    out.mkdir(parents=True, exist_ok=True)
    for site, recs in result.pop("_accepted", {}).items():
        d = out / "batches" / site
        d.mkdir(parents=True, exist_ok=True)
        for r in recs:
            (d / f"{r['base_id']}.json").write_text(
                json.dumps(r, ensure_ascii=False, indent=1) + "\n"
            )
    (out / "archive.json").write_text(
        json.dumps(result.pop("_archive", []), ensure_ascii=False, indent=1) + "\n"
    )
    (out / "report.json").write_text(json.dumps(result, ensure_ascii=False, indent=1) + "\n")
    return result


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="qwen_recipes_intake")
    ap.add_argument("cmd", choices=("inspect", "plan"))
    ap.add_argument("src", type=Path)
    ap.add_argument("--out", type=Path, default=REPO / "var" / "qwen-recipes" / SET_ID)
    a = ap.parse_args(argv)
    if not a.src.exists():
        print(json.dumps({"status": "BLOCKED_ACCESS", "missing": str(a.src)}, ensure_ascii=False))
        return 2
    files = read_set(a.src)
    if a.cmd == "inspect":
        print(json.dumps(inspect(files), ensure_ascii=False, indent=1))
        return 0
    res = plan(files)
    if res["status"] != "OK":
        print(json.dumps(res, ensure_ascii=False, indent=1))
        return 3
    print(json.dumps(write(res, a.out), ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
