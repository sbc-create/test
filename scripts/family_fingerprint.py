#!/usr/bin/env python3
"""Отпечаток семейства шаблонов: чем одна витрина отличается от другой.

Вопрос, на который отвечает файл: два ли это шаблона или один с другим
акцентным цветом. Сравнивается не название в манифесте, а то, что получает
браузер: состав и порядок разделов, классы блоков, набор компонентов,
раскладочные токены и типографика.

Совпадение цвета не считается различием, и различие только в цвете не
считается двумя шаблонами: перекрашенная копия — это копия.

    python3 scripts/family_fingerprint.py var/lords-candidate var/zona-candidate/zona-cinema
"""
from __future__ import annotations

import argparse
import collections
import hashlib
import json
import pathlib
import re

КОРЕНЬ = pathlib.Path(__file__).resolve().parents[1]

СЕКЦИЯ = re.compile(r'<section[^>]*class="([^"]*)"', re.I)
ЗАГОЛОВОК2 = re.compile(r"<h2[^>]*>(.*?)</h2>", re.S | re.I)
КЛАСС = re.compile(r'class="([^"]+)"')
ТОКЕН = re.compile(r"--([a-z0-9-]+):\s*([^;]+);")
ПРАВИЛО = re.compile(r"([^{}]+)\{([^{}]*)\}")


def текст(с: str) -> str:
    return re.sub(r"<[^>]+>", " ", с).strip()


def отпечаток_страницы(тело: str) -> dict:
    секции = СЕКЦИЯ.findall(тело)
    заголовки = [текст(з) for з in ЗАГОЛОВОК2.findall(тело)]
    классы = collections.Counter()
    for кусок in КЛАСС.findall(тело):
        for к in кусок.split():
            классы[к] += 1
    return {"section_classes": секции,
            "h2_order": заголовки,
            "top_classes": [к for к, _ in классы.most_common(25)],
            "class_vocabulary": sorted(классы)[:200]}


def отпечаток_витрины(корень: pathlib.Path) -> dict:
    страницы = {}
    for имя, отн in (("home", "index.html"), ("catalog", "catalog/index.html")):
        ф = корень / отн
        if ф.is_file():
            страницы[имя] = отпечаток_страницы(ф.read_text("utf-8", "replace"))
    каталог = корень / "title"
    if каталог.is_dir():
        первый = sorted(x for x in каталог.iterdir() if (x / "index.html").is_file())
        if первый:
            страницы["title"] = отпечаток_страницы(
                (первый[0] / "index.html").read_text("utf-8", "replace"))
    css = корень / "assets" / "site.css"
    токены, правил = {}, 0
    if css.is_file():
        тело = css.read_text("utf-8", "replace")
        токены = {к: v.strip() for к, v in ТОКЕН.findall(тело)}
        правил = len(ПРАВИЛО.findall(тело))
    return {"root": str(корень), "pages": страницы, "tokens": токены,
            "css_rules": правил,
            "css_sha256": hashlib.sha256(css.read_bytes()).hexdigest() if css.is_file() else None}


def сравнить(а: dict, б: dict) -> dict:
    #: Токены, различие которых само по себе НЕ делает шаблоны разными.
    ТОЛЬКО_ЦВЕТ = {"accent", "accent-text", "bg", "surface", "surface-alt",
                    "text", "muted", "border", "link"}
    ключи = set(а["tokens"]) | set(б["tokens"])
    цветные = {к for к in ключи if к in ТОЛЬКО_ЦВЕТ}
    раскладочные = ключи - цветные
    различия_цвета = {к for к in цветные if а["tokens"].get(к) != б["tokens"].get(к)}
    различия_раскладки = {к for к in раскладочные if а["tokens"].get(к) != б["tokens"].get(к)}

    страницы = {}
    for имя in set(а["pages"]) & set(б["pages"]):
        па, пб = а["pages"][имя], б["pages"][имя]
        страницы[имя] = {
            "section_classes_equal": па["section_classes"] == пб["section_classes"],
            "h2_order_equal": па["h2_order"] == пб["h2_order"],
            "class_vocabulary_equal": па["class_vocabulary"] == пб["class_vocabulary"],
            "a_sections": па["section_classes"][:8],
            "b_sections": пб["section_classes"][:8],
            "a_h2": па["h2_order"][:8],
            "b_h2": пб["h2_order"][:8],
        }
    одинаковая_структура = all(
        с["section_classes_equal"] and с["h2_order_equal"]
        and с["class_vocabulary_equal"] for с in страницы.values()) if страницы else None
    return {
        "color_only_token_differences": sorted(различия_цвета),
        "layout_token_differences": sorted(различия_раскладки),
        "pages": страницы,
        "structure_identical": одинаковая_структура,
        # Главный вывод: отличаются ли шаблоны чем-то кроме цвета.
        "differs_beyond_color": bool(различия_раскладки) or (одинаковая_структура is False),
    }


def главное(аргв=None) -> int:
    р = argparse.ArgumentParser(description=__doc__)
    р.add_argument("а")
    р.add_argument("б")
    р.add_argument("--out", default="artifacts/family-fingerprint.json")
    а = р.parse_args(аргв)
    па = отпечаток_витрины(pathlib.Path(а.а))
    пб = отпечаток_витрины(pathlib.Path(а.б))
    итог = {"a": па["root"], "b": пб["root"],
            "css_sha256": {"a": па["css_sha256"], "b": пб["css_sha256"]},
            "css_rules": {"a": па["css_rules"], "b": пб["css_rules"]},
            **сравнить(па, пб)}
    путь = КОРЕНЬ / а.out
    путь.parent.mkdir(parents=True, exist_ok=True)
    путь.write_text(json.dumps(итог | {"tokens_a": па["tokens"], "tokens_b": пб["tokens"]},
                               ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(итог, ensure_ascii=False, indent=1)[:2400])
    return 0


if __name__ == "__main__":
    raise SystemExit(главное())
