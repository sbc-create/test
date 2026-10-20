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
* Повторный план даёт тот же результат (digest); вывод не содержит секретов.
"""

from __future__ import annotations

import argparse
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
    r"выпеч|пирог|пирож|торт|кекс|маффин|печень|булоч|булк|хлеб|багет|чиабат|фокач|лепёшк|лепешк|слойк|круассан|"
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
def read_set(src: Path) -> dict[str, dict]:
    """{относительный путь: JSON} — из каталога или .tar.gz; только .json внутри набора."""
    out: dict[str, dict] = {}
    if src.is_dir():
        for p in sorted(src.rglob("*.json")):
            if p.is_file() and not p.is_symlink():
                out[str(p.relative_to(src))] = json.loads(p.read_text(encoding="utf-8"))
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
            out[name] = json.loads(t.extractfile(m).read().decode("utf-8"))
    return out


def inspect(files: dict[str, dict]) -> dict:
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
    return bool(a and b) and len(a & b) / len(a | b) >= 0.75


def check_base(b: dict) -> list[str]:
    errs = []
    for k in ("base_id", "title", "servings", "ingredients", "steps"):
        if not b.get(k):
            errs.append(f"нет поля {k}")
    if not (b.get("source") or {}).get("url", "").startswith("http"):
        errs.append("BLOCKED_RIGHTS: нет источника фактов (source.url)")
    for i, ing in enumerate(b.get("ingredients") or []):
        if not ing.get("name"):
            errs.append(f"ингредиент {i}: нет названия")
    if not all(isinstance(s, str) and s.strip() for s in b.get("steps") or []):
        errs.append("шаги базы — непустые строки")
    return errs


def check_variant(v: dict, b: dict) -> list[str]:
    errs = []
    for k in ("variant_id", "base_id", "label", "title", "intro", "ingredients", "steps"):
        if not v.get(k):
            errs.append(f"нет поля {k}")
    if errs:
        return errs
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
        for d in files.values()
        if isinstance(d, dict) and "label" not in d and "base_id" in d
    }
    variants = [d for d in files.values() if isinstance(d, dict) and "label" in d]
    counts = {
        "manifest_base": man.get("base_count"),
        "manifest_variants": man.get("variant_count"),
        "files_base": len(by_id),
        "files_variants": len(variants),
    }
    accepted: dict[str, list] = {s: [] for s in SITES}
    deferred, archive, seen_titles = [], [], []
    for item in man["items"]:
        bid = item.get("base_id")
        b = by_id.get(bid)
        vs = [d for d in variants if d.get("base_id") == bid]
        if b is None:
            deferred.append({"base_id": bid, "reason": "нет файла базового рецепта"})
            continue
        errs = check_base(b)
        if errs:
            deferred.append({"base_id": bid, "title": b.get("title"), "reason": "; ".join(errs)})
            archive += [
                {"variant_id": v.get("variant_id"), "base_id": bid, "why": "база не принята"}
                for v in vs
            ]
            continue
        if len(vs) != EXPECTED["per_base"]:
            counts.setdefault("bases_without_5_variants", []).append(bid)
        checked = [(v, check_variant(v, b)) for v in vs]
        good = sorted((v for v, e in checked if not e), key=score)
        for v, e in checked:
            if e:
                archive.append(
                    {"variant_id": v.get("variant_id"), "base_id": bid, "why": "; ".join(e)}
                )
        if not good:
            deferred.append(
                {
                    "base_id": bid,
                    "title": b["title"],
                    "reason": "ни один вариант V1–V5 не прошёл проверки",
                }
            )
            continue
        pick, rest = good[0], good[1:]
        archive += [
            {"variant_id": v["variant_id"], "base_id": bid, "why": "вариант подачи того же блюда"}
            for v in rest
        ]
        site = route(b, pick)
        key = title_key(b["title"])
        dup_set = next((t for t, k in seen_titles if similar(k, key)), None)
        if dup_set:
            deferred.append(
                {
                    "base_id": bid,
                    "title": b["title"],
                    "reason": f"дубль блюда внутри набора: {dup_set}",
                }
            )
            continue
        seen_titles.append((bid, key))
        match = next((slug for slug, k in existing.get(site, []) if similar(k, key)), None)
        rec = {
            "set_id": man.get("set_id", SET_ID),
            "base_id": bid,
            "variant_id": pick["variant_id"],
            "label": pick["label"],
            "site": site,
            "base": b,
            "variant": pick,
        }
        rec["digest"] = digest({"base": b, "variant": pick})
        if match:
            deferred.append(
                {
                    "base_id": bid,
                    "title": b["title"],
                    "site": site,
                    "update_candidate": match,
                    "reason": "совпадает с опубликованным — сверка редактором, без дубля",
                }
            )
            archive.append(
                {
                    "variant_id": pick["variant_id"],
                    "base_id": bid,
                    "why": f"кандидат на обновление {match}",
                }
            )
            continue
        accepted[site].append(rec)
    return {
        "status": "OK",
        "set_id": man.get("set_id", SET_ID),
        "counts": counts,
        "accepted": {s: len(v) for s, v in accepted.items()},
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
