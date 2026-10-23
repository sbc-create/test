"""Изображения блюд: приём файла с правами и сборка адаптивных размеров.

Изображение попадает на сайт только с происхождением: вид (photo — фотография
этого блюда, illustration — иллюстрация, фотографией не считается), источник,
лицензия или основание использования, alt. Исходник берётся из каталога приёма
вне git (storage.media/incoming), в git — только уменьшенные WebP и запись в
data/media/images.json.

    python3 -m fooddaily.media add --slug syrniki-s-ezhevikoj --file var/.../incoming/syrniki.jpg \\
        --kind photo --alt "Сырники с ежевикой на тарелке" --source "съёмка владельца 2026-10" \\
        --license "собственность владельца сайта" [--author "…"]
    python3 -m fooddaily.media missing      # рецепты без изображения
    python3 -m fooddaily.media jobs         # файл заданий data/media/image-jobs.json
    python3 -m fooddaily.media intake --dir <каталог приёма> --tool "<генератор, версия>" --license "<основание>"
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .views import IMAGE_KINDS, ROOT, Site

WIDTHS = (400, 800, 1200, 1600)  # 1600 — только из исходника не меньше 1600: крупный кадр рецепта на экранах ×2
MIN_WIDTH = 1200  # меньше — не принимается
REGISTRY = ROOT / "data" / "media" / "images.json"
OUT = ROOT / "static" / "media"
RATIO = (4, 3)


def add(a: argparse.Namespace) -> dict:
    from PIL import Image, ImageOps

    site = Site()
    if a.slug not in site.by_slug:
        raise SystemExit(f"рецепта {a.slug} нет на сайте")
    if a.kind not in IMAGE_KINDS:
        raise SystemExit("kind: photo или illustration")
    for k in ("alt", "source", "license"):
        if not getattr(a, k).strip():
            raise SystemExit(f"{k} обязателен: без происхождения изображение не публикуется")
    im = ImageOps.exif_transpose(Image.open(a.file)).convert("RGB")
    w, h = im.size
    tw, th = (w, w * RATIO[1] // RATIO[0]) if w * RATIO[1] <= h * RATIO[0] else (h * RATIO[0] // RATIO[1], h)
    left, top = (w - tw) // 2, (h - th) // 2
    im = im.crop((left, top, left + tw, top + th))  # единые пропорции 4:3 — сетка не прыгает
    widths = [x for x in WIDTHS if x <= tw] or [tw]
    OUT.mkdir(parents=True, exist_ok=True)
    for x in widths:
        im.resize((x, x * RATIO[1] // RATIO[0]), Image.LANCZOS).save(OUT / f"{a.slug}-{x}.webp", "WEBP", quality=80)
    reg = json.loads(REGISTRY.read_text())
    reg["items"][a.slug] = {
        "file": a.slug,
        "width": widths[-1],
        "height": widths[-1] * RATIO[1] // RATIO[0],
        "widths": widths,
        "kind": a.kind,
        "alt": a.alt.strip(),
        "source": a.source.strip(),
        "license": a.license.strip(),
        **({"author": a.author.strip()} if a.author else {}),
    }
    REGISTRY.write_text(json.dumps(reg, ensure_ascii=False, indent=2) + "\n")
    return reg["items"][a.slug]


def _recipe_bits(r) -> dict:
    steps = r.d["steps"]
    return {
        "recipe_id": r.raw["content_id"],
        "ingredients": [i.name for i, _ in r.ingredients],
        "last_step": steps[-1]["text"] if steps else "",
        "cue": next((x["readiness_cue"] for x in reversed(steps) if x.get("readiness_cue")), ""),
        "group": r.category_label,
    }


JOBS = ROOT / "data" / "media" / "image-jobs.json"


def job(site: Site, r) -> dict:
    """Задание на изображение блюда — только из состава и шагов опубликованного рецепта, без домыслов."""
    b = _recipe_bits(r)
    cue = b["cue"].rstrip(".")
    given = r.f.get("image_job") or {}  # подача, описанная в поставке рецепта, — точнее последнего шага
    look = (given.get("look") or "").strip().rstrip(".") + "." if given.get("look") else (
        b["last_step"] + (f" Готовность: {cue[:1].lower()}{cue[1:]}." if cue else "")
    )
    # подача из поставки описывает готовое блюдо; последний шаг рецепта — действие, и подписан как шаг
    serve = f"Блюдо готово и подано так: {look}" if given.get("look") else f"Последний шаг рецепта: {look}"
    main = ", ".join(n.lower() for n in b["ingredients"][:8])
    prompt = (
        f"Реалистичная фотография домашнего блюда «{r.title}» ({b['group'].lower()}). "
        f"{serve} Показать готовое блюдо после этого шага. "
        f"Состав по рецепту: {main}. В кадре только то, что входит в рецепт, без посторонних продуктов и гарниров. "
        "Естественный дневной свет, спокойный светлый фон, ракурс около 45°, кадр 4:3, блюдо по центру; "
        "без текста, надписей, логотипов, рук и людей."
    )
    return {
        "site": site.cfg["site_id"],
        "recipe_id": b["recipe_id"],
        "slug": r.slug,
        "url": r.url,
        "title": r.title,
        "ingredients": b["ingredients"],
        "look": look,
        "prompt": prompt,
        "file": f"{r.slug}.jpg",
        "alt": (given.get("alt") or "").strip() or f"{r.title}: готовое блюдо",
        "kind": "illustration",
    }


FIRST_DELIVERY = 6


def home_first(n: int) -> list[str]:
    """Первые n рецептов главной в порядке показа (по отрисованной главной: подборки зависят от сезона)."""
    import re

    from fooddaily.server import App

    _, html, _ = App().route("/", {})
    slugs = re.findall(r'class="b?card__link" href="/recept/([^/"]+)/"', html)
    return list(dict.fromkeys(slugs))[:n]


def jobs() -> dict:
    """Файл заданий для рецептов без изображения: data/media/image-jobs.json (перезаписывается целиком)."""
    site = Site()
    out = {
        "site": site.cfg["site_id"],
        "ratio": f"{RATIO[0]}:{RATIO[1]}",
        "min_width": MIN_WIDTH,
        "note": "Сгенерированное изображение публикуется как illustration (подпись «Иллюстрация»), не как фото.",
        "jobs": [job(site, r) for r in site.recipes if not r.image],
    }
    # первая поставка — блюда, которые посетитель видит первыми: первые карточки главной по порядку
    first = home_first(FIRST_DELIVERY)
    for j in out["jobs"]:
        j["priority"] = first.index(j["slug"]) + 1 if j["slug"] in first else None
    out["jobs"].sort(key=lambda j: (j["priority"] is None, j["priority"] or 0))
    out["first_delivery"] = [j["slug"] for j in out["jobs"] if j["priority"]]
    JOBS.write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n")
    return {"jobs": len(out["jobs"]), "file": str(JOBS)}


def fingerprint(path) -> dict:
    """Отпечаток файла: sha256 и усреднённый хеш 8×8 по кадру 4:3 — ловит одну и ту же картинку у разных блюд,
    даже пересохранённую или уменьшенную."""
    import hashlib

    from PIL import Image, ImageOps

    im = ImageOps.exif_transpose(Image.open(path)).convert("L")
    small = im.resize((8, 8), Image.LANCZOS)
    px = list(small.tobytes())
    mean = sum(px) / len(px)
    return {
        "sha256": hashlib.sha256(Path(path).read_bytes()).hexdigest(),
        "ahash": "".join("1" if v >= mean else "0" for v in px),
        "size": im.size,
    }


def _near(a: str, b: str, limit: int = 4) -> bool:
    return sum(x != y for x, y in zip(a, b, strict=True)) <= limit


def check_file(path, known: dict) -> tuple[dict, str | None]:
    """Проверка до публикации: размер кадра 4:3 не меньше min_width и не та же картинка, что у другого блюда."""
    fp = fingerprint(path)
    w, h = fp["size"]
    crop_w = w if w * RATIO[1] <= h * RATIO[0] else h * RATIO[0] // RATIO[1]
    if crop_w < MIN_WIDTH:
        return fp, f"мало пикселей: кадр 4:3 шириной {crop_w}, нужно не меньше {MIN_WIDTH}"
    for slug, other in known.items():
        if other.get("sha256") == fp["sha256"] or (other.get("ahash") and _near(other["ahash"], fp["ahash"])):
            return fp, f"то же изображение, что у «{slug}»: у каждого блюда своё"
    return fp, None


def intake(a: argparse.Namespace) -> dict:
    """Приём готовых файлов по файлу заданий: <dir>/<file> → add(kind=illustration). Инструмент и основание
    использования обязательны — без них BLOCKED_INPUT, значения по умолчанию не подставляются.
    --only <slug> — пробный прогон одного изображения через всю цепочку перед остальными."""
    for k in ("tool", "license"):
        if not (getattr(a, k) or "").strip():
            raise SystemExit(f"BLOCKED_INPUT: --{k} обязателен (чем создано и на каком основании используется)")
    spec = json.loads(JOBS.read_text())
    only = getattr(a, "only", None)
    if only and only not in {j["slug"] for j in spec["jobs"]}:
        raise SystemExit(f"задания для {only} нет в {JOBS.name}")
    known = dict(json.loads(REGISTRY.read_text())["items"])
    done, missing, rejected = [], [], {}
    for j in spec["jobs"]:
        if only and j["slug"] != only:
            continue
        f = Path(a.dir) / j["file"]
        if not f.is_file():
            missing.append(j["file"])
            continue
        fp, why = check_file(f, {s: e for s, e in known.items() if s != j["slug"]})
        if why:
            rejected[j["file"]] = why
            continue
        add(
            argparse.Namespace(
                slug=j["slug"],
                file=f,
                kind="illustration",
                alt=j["alt"],
                author=None,
                source=f"сгенерировано: {a.tool.strip()}; задание {JOBS.name}, {j['recipe_id']}",
                license=a.license.strip(),
            )
        )
        reg = json.loads(REGISTRY.read_text())
        reg["items"][j["slug"]].update(sha256=fp["sha256"], ahash=fp["ahash"], recipe_id=j["recipe_id"])
        REGISTRY.write_text(json.dumps(reg, ensure_ascii=False, indent=2) + "\n")
        known[j["slug"]] = reg["items"][j["slug"]]
        done.append(j["slug"])
    return {"added": done, "missing": missing, "rejected": rejected}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="food-daily media")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("add")
    p.add_argument("--slug", required=True)
    p.add_argument("--file", required=True, type=Path)
    p.add_argument("--kind", required=True, choices=IMAGE_KINDS)
    p.add_argument("--alt", required=True)
    p.add_argument("--source", required=True)
    p.add_argument("--license", required=True)
    p.add_argument("--author")
    sub.add_parser("missing")
    sub.add_parser("jobs")
    p = sub.add_parser("intake")
    p.add_argument("--dir", required=True, type=Path)
    p.add_argument("--tool")
    p.add_argument("--license")
    p.add_argument("--only", help="slug: пробный прогон одного изображения")
    a = ap.parse_args(argv)
    if a.cmd == "add":
        print(json.dumps(add(a), ensure_ascii=False))
    elif a.cmd == "jobs":
        print(json.dumps(jobs(), ensure_ascii=False))
    elif a.cmd == "intake":
        print(json.dumps(intake(a), ensure_ascii=False))
    else:
        site = Site()
        miss = [r.slug for r in site.recipes if not r.image]
        print(json.dumps({"recipes": len(site.recipes), "without_image": len(miss), "slugs": miss}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
