"""Приём набора рецептов Qwen (QWEN-NIGHT-RECIPES-100X5-001) для bestreciept.site и myfood.mobi.

Набор лежит в среде Qwen; на этот сервер его кладут в каталог приёма INTAKE — архивом
<SET_ID>.tar.gz или каталогом <SET_ID>/. Инструмент только читает набор и публичный контент
сайтов и пишет в свой каталог вывода; сайты он не меняет — это делают адаптеры шаблонов
(fooddaily.set_import, bakebook.set_import) с резервной копией и пробной партией.

    python3 tools/qwen_recipes_intake.py inspect <архив|каталог>   # файлы, ключи, количества
    python3 tools/qwen_recipes_intake.py plan <архив|каталог> [--out DIR]
    python3 tools/qwen_recipes_intake.py check <архив|каталог>  # для Qwen: READY или что исправить

С 23.10.2026 основной формат поставки — qwen-dish/1: одно блюдо — одна редакционная версия,
источник, калорийность с основанием расчёта и задание на изображение (tools/qwen_contract/README.md,
образец tools/qwen_contract/example/). Форматы ниже читаются для совместимости.

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
EDITOR = "ED"  # редакционная версия (tools/qwen_editorial/<набор>.json)
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
EXAMPLE_HOSTS = {"example.org", "example.com", "example.net"}
# энциклопедии и справочники состава: статья о блюде или продукте — не опубликованный рецепт:
# количества, порции и время в ней не подтверждаются (контракт: source.url — страница рецепта)
REFERENCE_HOSTS = ("wikipedia.org", "wikimedia.org", "wiktionary.org", "wikibooks.org", "usda.gov")
UNREADABLE = "_unreadable"  # ключ в результате read_set: файлы, которые не разобрались как JSON


def _load(name: str, raw: bytes, out: dict) -> None:
    try:
        out[name] = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as e:
        out.setdefault(UNREADABLE, {})[name] = str(e)[:80]


def safe_path(name: str) -> str | None:
    """Путь внутри поставки без «./» и пустых частей; None — недопустимый: абсолютный, с «..»,
    с обратной косой чертой (в архиве из другой ОС это может быть выход из каталога)."""
    if (
        not isinstance(name, str)
        or not name
        or "\\" in name
        or name.startswith("/")
        or ".." in name.split("/")
    ):
        return None
    parts = [x for x in name.split("/") if x not in ("", ".")]
    return "/".join(parts) or None


def _strip_top(names: list[str]) -> str:
    """Общая внешняя папка поставки (QWEN-…/ любого набора), если все файлы в ней; иначе ''."""
    tops = {n.split("/", 1)[0] for n in names}
    return next(iter(tops)) + "/" if len(tops) == 1 and all("/" in n for n in names) else ""


def read_set(src: Path) -> dict[str, dict]:
    """{относительный путь: JSON} — из каталога или .tar.gz; только .json внутри набора.

    Пути — относительно корня поставки: «./» снимается, общая внешняя папка набора (любой set_id,
    не только 100X5-001) снимается. Неразборчивые файлы и недопустимые пути архива не роняют приём,
    а перечисляются под ключом UNREADABLE: счёт файлов не сойдётся, и это видно в отчёте."""
    raw: dict[str, bytes] = {}
    bad: dict[str, str] = {}
    if src.is_dir():
        for p in sorted(src.rglob("*.json")):
            if p.is_file() and not p.is_symlink():
                raw[str(p.relative_to(src))] = p.read_bytes()
    else:
        with tarfile.open(src) as t:
            for m in t.getmembers():
                if not m.name.endswith(".json"):
                    continue
                name = safe_path(m.name)
                if name is None or not m.isfile():
                    bad[m.name] = "недопустимый путь или не обычный файл в архиве"
                    continue
                raw[name] = t.extractfile(m).read()
    top = _strip_top(list(raw))
    out: dict[str, dict] = {}
    for name, data in raw.items():
        _load(name[len(top) :], data, out)
    if bad:
        out.setdefault(UNREADABLE, {}).update(bad)
    return out


# ---------------------------------------------------------------- формат qwen-night/1
def _clean(x) -> str:
    return re.sub(r"^\s*\d+[.)]\s*", "", str(x)).strip()


def variant_steps(v: dict) -> tuple[list[str] | None, str]:
    """Текст шагов варианта и поле, откуда он взят. Названия этапов и контрольные признаки
    (control_points) — не инструкция: из них шагов не получается."""
    st = v.get("steps")
    if isinstance(st, list) and st and all(isinstance(x, str) and x.strip() for x in st):
        return [_clean(x) for x in st], "steps"
    swe = v.get("steps_with_explanations")
    if isinstance(swe, list) and swe and all(isinstance(x, dict) for x in swe):
        out = [step_text(x) for x in swe]
        if all(out):
            return out, "steps_with_explanations"
    seq = v.get("step_sequence")
    if isinstance(seq, list) and seq and all(isinstance(x, dict) for x in seq):
        out = ["; ".join(_clean(y) for y in x.get("steps") or [] if str(y).strip()) for x in seq]
        out = [x for x in out if x]
        if out:
            return out, "step_sequence"
        return None, "step_sequence: только названия этапов"
    if v.get("control_points"):
        return None, "control_points: только признаки готовности"
    return None, "нет шагов"


def step_text(x: dict) -> str:
    """Шаг из пары instruction/explanation: действие — instruction, пояснение идёт следом и не
    заменяет его (раньше explanation вытесняло instruction, и действия терялись). Числа пояснения
    проверяются вместе с шагом: время или температура не из базы — ошибка шага."""
    ins, exp = _clean(x.get("instruction") or ""), _clean(x.get("explanation") or "")
    if ins and exp and norm(exp) not in norm(ins):
        return ins.rstrip(".") + ". " + exp[:1].upper() + exp[1:]
    return ins or exp


def variant_intro(v: dict) -> tuple[str, str]:
    """Вступление: intro или detailed_intro — первое, что не короче 40 знаков и без
    недопустимых формулировок; иначе самое длинное из имеющихся."""
    got = [(str(v[k]).strip(), k) for k in ("intro", "detailed_intro") if v.get(k)]
    ok = [x for x in got if len(x[0]) >= 40 and not CLAIM.search(x[0])]
    if ok:
        return ok[0]
    return max(got, key=lambda x: len(x[0])) if got else ("", "нет")


def _toks(s: str) -> set[str]:
    return {stem(w) for w in norm(s).split() if len(w) > 2}


def align(texts: list[str], base_steps: list[str]) -> list[list[int]]:
    """Сопоставление шагов варианта с шагами базы по содержанию, по порядку: шаг варианта
    покрывает подряд идущие шаги базы (объединение), соседние шаги варианта могут делить один
    шаг базы (разделение). Шаг без общего содержания с базой получает пустую ссылку."""
    k_n, n = len(texts), len(base_steps)
    if not k_n or not n:
        return [[] for _ in texts]
    if k_n == n:
        return [[i] for i in range(n)]
    tt, bt = [_toks(t) for t in texts], [_toks(x) for x in base_steps]

    def score(k, i, j):
        u = set().union(*bt[i : j + 1])
        return len(tt[k] & u) / max(1, len(tt[k])) - 0.05 * (j - i)

    neg = float("-inf")
    best: dict = {}  # (k, e) -> (сумма, путь): шаги 0..k разобраны, последний кончается на e
    for e in range(n):
        best[(0, e)] = (score(0, 0, e), [(0, e)])
    for k in range(1, k_n):
        for (pk, pe), (sc, path) in list(best.items()):
            if pk != k - 1:
                continue
            for st in {pe, pe + 1}:
                for e in range(st, n):
                    cand = sc + score(k, st, e)
                    if cand > best.get((k, e), (neg,))[0]:
                        best[(k, e)] = (cand, path + [(st, e)])
    sc_path = best.get((k_n - 1, n - 1))
    if not sc_path:
        return [[] for _ in texts]
    return [
        list(range(i, j + 1)) if tt[k] & set().union(*bt[i : j + 1]) else []
        for k, (i, j) in enumerate(sc_path[1])
    ]


DISH = "qwen-dish/1"


def normalize_dish(files: dict) -> dict:
    """Поставка qwen-dish/1 (одно блюдо — одна редакционная версия) → контракт qwen-recipes-set/1.
    Факты (состав, количества, время, источник, шаги источника) — в базу; текст редакции — в один
    вариант с меткой ED. Калорийность и задание на изображение переносятся как есть
    и проверяются в plan."""
    mans = [
        (n, d)
        for n, d in files.items()
        if n.rsplit("/", 1)[-1] == "manifest.json"
        and isinstance(d, dict)
        and d.get("format") == DISH
    ]
    out: dict = {UNREADABLE: files.get(UNREADABLE, {})} if files.get(UNREADABLE) else {}
    if len(mans) != 1:  # два манифеста — неясно, какой набор принимать: не угадываем
        out["manifest.json"] = {
            "format": DISH,
            "error": f"manifest.json формата {DISH}: {len(mans)}, нужен один",
        }
        return out
    man_name, man = mans[0]
    base_dir = man_name.rsplit("/", 1)[0] + "/" if "/" in man_name else ""
    items = []
    for it in man.get("items") or []:
        # путь файла — относительно manifest.json: «dishes/x.json», «./x.json», «x.json»
        rel = safe_path(it.get("file"))
        key = rel and safe_path(base_dir + rel)
        d = files.get(key) if key else None
        d = d if isinstance(d, dict) else {}
        did = it.get("dish_id") or d.get("dish_id")
        if not d:
            why = (
                f"недопустимый путь в manifest: {it.get('file')!r}"
                if not key
                else f"нет файла {key} из manifest"
            )
            items.append(
                {"base_id": did, "file": f"base/{did}.json", "variants": [], "missing_reason": why}
            )
            continue
        ed = d.get("editorial") or {}
        names = ed.get("display_names") or {}
        b = {
            "base_id": did,
            "title": d.get("title"),
            "category": d.get("category"),
            "servings": d.get("servings"),
            **{
                k: d.get(k)
                for k in ("prep_minutes", "cook_minutes", "total_minutes")
                if d.get(k) is not None
            },
            "ingredients": [
                {
                    k: i.get(k)
                    for k in ("name", "quantity", "quantity_max", "unit", "note")
                    if k in i
                }
                for i in d.get("ingredients") or []
            ],
            "steps": list(d.get("source_steps") or []),
            "source": d["source"]
            if str((d.get("source") or {}).get("url", "")).startswith("http")
            else {},
            "source_raw": (d.get("source") or {}).get("url") or "",
            **({"oven": d["oven"]} if d.get("oven") else {}),
            **({"nutrition": d["nutrition"]} if d.get("nutrition") else {}),
            **({"image_job": d["image_job"]} if d.get("image_job") else {}),
            **({"site": d["site"]} if d.get("site") else {}),
        }
        v = {
            "variant_id": f"{did}-{EDITOR}",
            "base_id": did,
            "label": EDITOR,
            "title": b["title"],
            "intro": str(ed.get("intro") or "").strip(),
            "ingredients": [
                {"base_index": k, "display_name": names.get(str(k), i.get("name"))}
                for k, i in enumerate(b["ingredients"])
            ],
            "steps": [
                {
                    "text": step_text(x),
                    "base_steps": x.get("base_steps") or [],
                    **({"readiness_cue": x["readiness_cue"]} if x.get("readiness_cue") else {}),
                }
                for x in ed.get("steps") or []
                if isinstance(x, dict)
            ],
            "format_fields": {"steps": "editorial.steps", "intro": "editorial.intro"},
        }
        out[f"base/{did}.json"] = b
        out[f"variants/{v['variant_id']}.json"] = v
        vs = [
            {
                "variant_id": v["variant_id"],
                "label": EDITOR,
                "file": f"variants/{v['variant_id']}.json",
            }
        ]
        items.append({"base_id": did, "file": f"base/{did}.json", "variants": vs})
    out["manifest.json"] = {
        "set_id": man.get("set_id"),
        "format": DISH,
        "base_count": len(items),
        "variant_count": len(items),
        "items": items,
    }
    return out


def normalize(files: dict) -> dict:
    """Поставка qwen-night/1 или qwen-dish/1 → контракт qwen-recipes-set/1; иной вход — как есть."""
    man = next((d for n, d in files.items() if n.rsplit("/", 1)[-1] == "manifest.json"), None)
    if isinstance(man, dict) and man.get("format") == DISH:
        return normalize_dish(files)
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
            "total_minutes": meta.get("cook_time_minutes"),  # сайт показывает общее время
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
            texts, steps_from = variant_steps(v)
            intro, intro_from = variant_intro(v)
            nv = {
                "variant_id": v["variant_id"],
                "base_id": bid,
                "label": v.get("variant_type"),
                "title": b["title"],
                "intro": intro,
                "ingredients": [
                    {"base_index": k, "display_name": i["name"]}
                    for k, i in enumerate(b["ingredients"])
                ],
                "steps": [
                    {"text": t, "base_steps": refs}
                    for t, refs in zip(texts or [], align(texts or [], b["steps"]), strict=True)
                ],
                "format_fields": {"steps": steps_from, "intro": intro_from},
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


PREFIX = re.compile(
    r"^(пере|разо|раз|рас|подо|под|при|про|ото|от|обо|об|по|за|на|вы|до|вз|вс|[сув](?=[бвгджзклмнпрстфхцчшщ]))"
)


ALTERNATION = (("мн", "мя"),)  # чередование основы: мну/мять («разомните» = «размять»)


def root(w: str) -> str:
    """Корень глагола для сравнения действий: без приставки, ж→з, две буквы — чтобы видовые пары
    совпадали («взбивайте» = «взбить», «нарежьте» = «нарезать», «обжарьте» = «жарить»)."""
    m = PREFIX.match(w)
    if m and len(w) - len(m.group(0)) >= 4:
        w = w[len(m.group(0)) :]
    w = w.replace("ж", "з")
    for a, b in ALTERNATION:
        if w.startswith(a):
            w = b + w[len(a) :]
    return w[:2] + "|" + re.sub(r"[аеёиоуыэюяьъй]", "", w)[:2]


def same_action(a: str, have: set[str]) -> bool:
    """Действие сохранено: совпали две первые буквы корня или два первых согласных
    («натрите» = «натереть»)."""
    x, y = root(a).split("|")
    return any(x == h.split("|")[0] or (len(y) == 2 and y == h.split("|")[1]) for h in have)


VERBISH = re.compile(r"(ть|ться|те|тесь|ив|ав|ыв|ая|яя|ясь|ая)$")


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
    host = str((b.get("source") or {}).get("url", "")).split("/")[2:3]
    h = re.sub(r"^www\.", "", host[0]).split(":")[0].lower() if host else ""
    if h in EXAMPLE_HOSTS:
        errs.append("BLOCKED_RIGHTS: источник-пример (example.org) — образец формата, не рецепт")
    elif any(h == r or h.endswith("." + r) for r in REFERENCE_HOSTS):
        errs.append(
            f"BLOCKED_RIGHTS: источник {h} — энциклопедия или справочник, не страница рецепта: "
            "количества, порции и время из него не подтверждаются"
        )
    for i, ing in enumerate(b.get("ingredients") or []):
        if not ing.get("name"):
            errs.append(f"ингредиент {i}: нет названия")
        elif UNSURE.search(ing.get("note") or ""):
            errs.append(f"количество «{ing['name']}» не подтверждено: {ing['note']}")
    if not all(isinstance(s, str) and s.strip() for s in b.get("steps") or []):
        errs.append("шаги базы — непустые строки")
    return errs


def check_nutrition(n: dict, b: dict) -> tuple[dict | None, list[str]]:
    """Калорийность публикуется только как примерный расчёт по составу с названным
    источником данных.
    Неполный расчёт не блокирует блюдо — он не переносится, а причина попадает в отчёт."""
    why = []
    kcal = n.get("kcal_per_serving")
    if not isinstance(kcal, int | float) or isinstance(kcal, bool) or not 0 < kcal < 3000:
        why.append("нет kcal_per_serving (число ккал на порцию)")
    for k in ("method", "data_source"):
        if not str(n.get(k) or "").strip():
            why.append(f"нет {k}: чем и по каким данным посчитано")
    if not b.get("servings"):
        why.append("число порций неизвестно — на порцию не посчитать")
    for k in ("protein_g", "fat_g", "carbs_g"):
        if k in n and not (isinstance(n[k], int | float) and n[k] >= 0):
            why.append(f"{k} — не число")
    per = n.get("per_ingredient")
    if per and not why:
        idx = sorted(x.get("index") for x in per if isinstance(x, dict))
        total = sum(float(x.get("kcal") or 0) for x in per if isinstance(x, dict))
        if idx != list(range(len(b.get("ingredients") or []))):
            why.append("per_ingredient: по строке на каждый ингредиент базы")
        elif abs(total / b["servings"] - kcal) > max(5, kcal * 0.05):
            why.append(
                f"per_ingredient: сумма {round(total)} ккал / {b['servings']} порц. ≠ {kcal}"
            )
    if why:
        return None, ["калорийность не перенесена: " + "; ".join(why)]
    keep = ("kcal_per_serving", "protein_g", "fat_g", "carbs_g", "method", "data_source")
    return {k: n[k] for k in keep if k in n} | {"approximate": True}, []


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
    if v["label"] not in LABELS + (EDITOR,):
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
    for r, src in enumerate(b["steps"]):
        mine = " ".join(
            s.get("text", "") + " " + (s.get("readiness_cue") or "")
            for s in v["steps"]
            if r in (s.get("base_steps") or [])
        )
        for num in LOST_NUM.findall(src.replace(",", ".")):
            if num not in mine.replace(",", "."):
                errs.append(f"шаг базы {r + 1}: потеряно {num}")
        verbs = [w for w in norm(src).split() if len(w) > 4 and re.search(r"(ть|ться|те|тесь)$", w)]
        have = {root(w) for w in norm(mine).split() if VERBISH.search(w)}
        if lost_v := [w for w in verbs if not same_action(w, have)]:
            errs.append(f"шаг базы {r + 1}: потеряны действия {', '.join(lost_v)}")
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
    """Публикуемый вариант: редакционная версия, если прошла проверки; затем больше признаков
    готовности, подробнее шаги; затем меньшая метка."""
    cues = sum(1 for s in v["steps"] if s.get("readiness_cue"))
    return (v["label"] != EDITOR, -cues, -len(v["steps"]), v["label"])


EDITORIAL_DIR = Path(__file__).resolve().parent / "qwen_editorial"


def load_editorial(set_id: str) -> dict:
    p = EDITORIAL_DIR / f"{set_id}.json"
    return {x["base_id"]: x for x in json.loads(p.read_text())["items"]} if p.exists() else {}


def editorial_variant(ed: dict, b: dict) -> dict:
    """Редакционная версия текста → вариант контракта (метка ED); факты — только из базы."""
    names = ed.get("display_names") or {}
    return {
        "variant_id": f"{b['base_id']}-{EDITOR}",
        "base_id": b["base_id"],
        "label": EDITOR,
        "title": b["title"],
        "intro": ed["intro"],
        "ingredients": [
            {"base_index": k, "display_name": names.get(str(k), i["name"])}
            for k, i in enumerate(b["ingredients"])
        ],
        "steps": [{"text": x["text"], "base_steps": x["base_steps"]} for x in ed["steps"]],
        "editorial": {"based_on": ed.get("based_on"), "batch": ed.get("batch")},
    }


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


def published_titles() -> dict[str, list[tuple]]:
    """(адрес, ключ названия, id материала) опубликованных рецептов каждого сайта."""
    out = {}
    for site, p in SITES.items():
        items = json.loads(p.read_text())["items"] if p.exists() else []
        out[site] = [
            (
                x["slug"],
                title_key(x.get("title") or x.get("draft", {}).get("title", "")),
                x.get("content_id") or x.get("record_id"),
            )
            for x in items
        ]
    return out


def own_ids(set_id: str, bid: str) -> set[str]:
    """Id, под которыми адаптеры сайтов сохраняют блюдо набора (fooddaily.set_import — fdq-,
    bakebook.set_import — fbq-): уже импортированное блюдо — не дубль самого себя."""
    return {
        "fdq-" + hashlib.sha256(f"qwen-set:{set_id}:{bid}".encode()).hexdigest()[:12],
        "fbq-" + hashlib.sha256(f"{set_id}:{bid}".encode()).hexdigest()[:12],
    }


def digest(obj) -> str:
    return hashlib.sha256(json.dumps(obj, ensure_ascii=False, sort_keys=True).encode()).hexdigest()[
        :16
    ]


# ---------------------------------------------------------------- план
def plan(
    files: dict[str, dict], existing: dict | None = None, editorial: dict | None = None
) -> dict:
    """Порядок отбора блюда: дубль (сайт, затем набор) → права → качество вариантов.

    Каждое непринятое блюдо — в deferred с kind (rights | duplicate | quality | missing)
    и причиной."""
    files = normalize(files)
    man = next(
        (d for n, d in files.items() if n.rsplit("/", 1)[-1].lower() == "manifest.json"), None
    )
    if man and man.get("error"):
        return {"status": "BLOCKED_INPUT", "reason": man["error"], "inspect": inspect(files)}
    if not man or not isinstance(man.get("items"), list):
        return {
            "status": "BLOCKED_INPUT",
            "reason": "нет manifest.json по контракту qwen-recipes-set/1",
            "inspect": inspect(files),
        }
    existing = published_titles() if existing is None else existing
    editorial = load_editorial(man.get("set_id", SET_ID)) if editorial is None else editorial
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
        if b is not None and bid in editorial:
            vs = vs + [editorial_variant(editorial[bid], b)]
        if b is None:
            defer(
                "missing",
                None,
                bid,
                item.get("missing_reason") or "нет файла базового рецепта",
                vs,
                lambda v: "нет базы",
            )
            continue
        if (
            man.get("format") != DISH
            and len([v for v in vs if v["label"] != EDITOR]) != EXPECTED["per_base"]
        ):
            counts.setdefault("bases_without_5_variants", []).append(bid)
        checked = {v["variant_id"]: check_variant(v, b) for v in vs}
        errs = check_base(b)
        site = b["site"] if b.get("site") in SITES else route(b, {})
        key = title_key(b["title"])
        mine = own_ids(man.get("set_id", SET_ID), bid)
        # одно блюдо — на одном сайте: совпадение ищется и на соседнем;
        # другой текст — не повод для второй страницы
        hit = next(
            (
                (other, x[0])
                for other in [site] + [o for o in SITES if o != site]
                for x in existing.get(other, [])
                if similar(x[1], key) and (x[2] if len(x) > 2 else None) not in mine
            ),
            None,
        )
        match = hit[1] if hit else None
        if hit and hit[0] != site:
            match, site = None, hit[0]
            defer(
                "duplicate",
                b,
                bid,
                f"блюдо уже есть на {hit[0]}/recept/{hit[1]}/ — на второй сайт не переносится",
                vs,
                lambda v: "блюдо есть на другом сайте",
                site=hit[0],
                update_candidate=hit[1],
            )
            seen_titles.append((bid, key))
            continue
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
                (
                    "редакционная версия не передаёт рецепт полностью"
                    if man.get("format") == DISH
                    else "ни один вариант V1–V5 не передаёт рецепт полностью"
                )
                + detail,
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
        warnings = []
        if b.get("nutrition"):
            kept, warnings = check_nutrition(b["nutrition"], b)
            b = {
                **{k: x for k, x in b.items() if k != "nutrition"},
                **({"nutrition": kept} if kept else {}),
            }
        dest = b["site"] if b.get("site") in SITES else route(b, pick)
        set_id = man.get("set_id", SET_ID)
        rec = {
            "set_id": set_id,
            "base_id": bid,
            "variant_id": pick["variant_id"],
            "label": pick["label"],
            "site": dest,
            # id материала на сайте: к нему привязываются задания на изображение и приём файлов
            "recipe_id": next(
                i
                for i in sorted(own_ids(set_id, bid))
                if i.startswith("fdq-" if dest == "bestreciept.site" else "fbq-")
            ),
            "base": b,
            "variant": pick,
            **({"warnings": warnings} if warnings else {}),
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


def check(files: dict[str, dict], existing: dict | None = None) -> dict:
    """Проверка поставки для Qwen до отправки: те же правила, что у plan, без записи и без
    редакционных версий этой стороны. По каждому блюду — ready или список исправлений."""
    res = plan(files, existing=existing, editorial={})
    if res["status"] != "OK":
        return {"status": res["status"], "reason": res.get("reason")}
    dishes = [
        {"dish_id": r["base_id"], "status": "ready", "site": r["site"], "recipe_id": r["recipe_id"]}
        | ({"warnings": r["warnings"]} if r.get("warnings") else {})
        for recs in res["_accepted"].values()
        for r in recs
    ]
    dishes += [
        {"dish_id": d["base_id"], "status": d["kind"], "fix": d["reason"]} for d in res["deferred"]
    ]
    bad = [d for d in dishes if d["status"] != "ready"]
    return {
        "status": "READY" if dishes and not bad else "NEEDS_FIX",
        "format": res["format"],
        "dishes": sorted(dishes, key=lambda d: str(d["dish_id"])),
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
    ap.add_argument("cmd", choices=("inspect", "plan", "check"))
    ap.add_argument("src", type=Path)
    ap.add_argument(
        "--out", type=Path, default=None, help="по умолчанию var/qwen-recipes/<set_id поставки>"
    )
    a = ap.parse_args(argv)
    if not a.src.exists():
        print(json.dumps({"status": "BLOCKED_ACCESS", "missing": str(a.src)}, ensure_ascii=False))
        return 2
    files = read_set(a.src)
    if a.out is None:  # результат каждой поставки — в своём каталоге, не в каталоге 100X5-001
        man = next(
            (
                d
                for n, d in files.items()
                if n.rsplit("/", 1)[-1] == "manifest.json" and isinstance(d, dict)
            ),
            {},
        )
        sid = str(man.get("set_id") or SET_ID)
        a.out = (
            REPO
            / "var"
            / "qwen-recipes"
            / (sid if re.fullmatch(r"[A-Za-z0-9._-]+", sid) else SET_ID)
        )
    if a.cmd == "inspect":
        print(json.dumps(inspect(files), ensure_ascii=False, indent=1))
        return 0
    if a.cmd == "check":
        out = check(files)
        print(json.dumps(out, ensure_ascii=False, indent=1))
        return 0 if out["status"] == "READY" else 1
    res = plan(files)
    if res["status"] != "OK":
        print(json.dumps(res, ensure_ascii=False, indent=1))
        return 3
    print(json.dumps(write(res, a.out), ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
