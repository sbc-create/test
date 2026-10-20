"""Изображения блюд: приём файла с правами и сборка адаптивных размеров.

Изображение попадает на сайт только с происхождением: вид (photo — фотография
этого блюда, illustration — иллюстрация, фотографией не считается), источник,
лицензия или основание использования, alt. Исходник берётся из каталога приёма
вне git (storage.media/incoming), в git — только уменьшенные WebP и запись в
data/media/images.json.

    python3 -m bakebook.media add --slug limonnyj-keks --file var/.../incoming/keks.jpg \\
        --kind photo --alt "Лимонный кекс на доске" --source "съёмка владельца 2026-10" \\
        --license "собственность владельца сайта" [--author "…"]
    python3 -m bakebook.media missing      # рецепты без изображения
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .site import IMAGE_KINDS, ROOT, Site

WIDTHS = (400, 800, 1200)
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


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="food-baking media")
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
    a = ap.parse_args(argv)
    if a.cmd == "add":
        print(json.dumps(add(a), ensure_ascii=False))
    else:
        site = Site()
        miss = [r.slug for r in site.recipes if not r.image]
        print(json.dumps({"recipes": len(site.recipes), "without_image": len(miss), "slugs": miss}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
