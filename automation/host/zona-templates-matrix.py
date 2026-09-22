#!/usr/bin/env python3
"""Прогон всех шаблонов витрины Zona и сборка контактного листа.

Каждый шаблон поднимается отдельной витриной со своим манифестом и проходит ту
же приёмку, что и кандидат: одни и те же измерения, одни и те же пороги.
Шаблон, не прошедший общий контракт, помечается провалившимся — «зато красиво»
основанием не является.

Контактный лист — обычная страница со снимками; каждый снимок ведёт на
полноразмерный файл.
"""
from __future__ import annotations

import argparse
import html
import json
import subprocess
import sys
from pathlib import Path

КОРЕНЬ = Path(__file__).resolve().parents[2]
ПРОГОН = КОРЕНЬ / "automation/host/zona-candidate-run.py"


def шаблоны() -> dict:
    """Объявления шаблонов читаются из рантайма, а не дублируются здесь."""
    текст = (КОРЕНЬ / "automation/host/lords-frontend.py").read_text(encoding="utf-8")
    начало = текст.index("ЗОНА_ШАБЛОНЫ = {")
    конец = текст.index("\n}\n", начало) + 3
    пространство: dict = {}
    exec(текст[начало:конец], пространство)  # noqa: S102 — свой же исходник
    return пространство["ЗОНА_ШАБЛОНЫ"]


def контактный_лист(куда: Path, итоги: list, ширины: list) -> Path:
    строки = []
    for итог in итоги:
        снимки = []
        for ш in ширины:
            имя = f"{итог['profile']}/screenshots/home-{ш}.png"
            if (куда / имя).is_file():
                снимки.append(
                    f'<figure><a href="{html.escape(имя)}">'
                    f'<img src="{html.escape(имя)}" alt="{html.escape(итог["profile"])}'
                    f' на {ш}px" loading="lazy"></a>'
                    f'<figcaption>{ш}px</figcaption></figure>')
        значок = "PASS" if итог["verdict"] == "PASS" else "FAIL"
        беды = "".join(f"<li>{html.escape(str(б))}</li>" for б in итог["failures"][:6])
        строки.append(
            f'<section class="t"><h2>{html.escape(итог["title"])} '
            f'<code>{html.escape(итог["profile"])}</code> '
            f'<b class="{значок.lower()}">{значок}</b></h2>'
            f'<p>{html.escape(итог["description"])}</p>'
            f'<p class="s">Состав: {html.escape(" → ".join(итог["order"]))}; '
            f'герой — {html.escape(итог["hero"])}, неделя — '
            f'{html.escape(итог["weekly"])}, поступления — '
            f'{html.escape(итог["added"])}, сетка новинок — {итог["fresh"]}.</p>'
            f'<div class="g">{"".join(снимки)}</div>'
            + (f"<ul class=\"f\">{беды}</ul>" if беды else "")
            + "</section>")
    страница = (
        "<!doctype html><html lang=ru><head><meta charset=utf-8>"
        "<meta name=viewport content='width=device-width,initial-scale=1'>"
        "<title>Шаблоны витрины Zona — контактный лист</title><style>"
        "body{margin:0;padding:24px;background:#12161b;color:#e6edf3;"
        "font:15px/1.5 system-ui,sans-serif}"
        "h1{font-size:24px;margin:0 0 6px}p.lead{color:#9fb0c0;margin:0 0 24px}"
        ".t{border:1px solid #232c36;border-radius:10px;padding:16px;margin:0 0 20px}"
        ".t h2{font-size:18px;margin:0 0 4px;display:flex;gap:10px;align-items:baseline}"
        "code{color:#7fd1ff;font-size:13px}"
        "b.pass{color:#5ad18c}b.fail{color:#ff7b72}"
        ".s{color:#9fb0c0;font-size:13px}"
        ".g{display:flex;gap:14px;flex-wrap:wrap;margin-top:12px}"
        "figure{margin:0}figure img{max-width:320px;border:1px solid #2a343f;"
        "border-radius:6px;display:block}"
        "figcaption{color:#9fb0c0;font-size:12px;margin-top:4px}"
        "ul.f{color:#ff7b72;font-size:13px}"
        "</style></head><body>"
        "<h1>Шаблоны витрины Zona</h1>"
        "<p class=lead>Снимок открывается в полном размере по нажатию. "
        "Ни один шаблон не принят владельцем: это технические кандидаты.</p>"
        + "".join(строки) + "</body></html>")
    путь = куда / "index.html"
    путь.write_text(страница, encoding="utf-8")
    return путь


def main() -> int:
    р = argparse.ArgumentParser(description=__doc__)
    р.add_argument("--snapshot", required=True)
    р.add_argument("--out", required=True)
    р.add_argument("--widths", default="390,1440")
    р.add_argument("--pages", default="/,/catalog/")
    р.add_argument("--only", default="", help="через запятую: какие шаблоны")
    а = р.parse_args()

    куда = Path(а.out)
    куда.mkdir(parents=True, exist_ok=True)
    ширины = [int(ш) for ш in а.widths.split(",")]
    выбор = [и.strip() for и in а.only.split(",") if и.strip()]

    итоги = []
    for имя, шаблон in шаблоны().items():
        if выбор and имя not in выбор:
            continue
        каталог = куда / имя
        код = subprocess.call([
            sys.executable, str(ПРОГОН), "--snapshot", а.snapshot,
            "--out", str(каталог), "--tag", имя, "--profile", имя,
            "--widths", а.widths, "--pages", а.pages, "--shots"])
        отчёт = json.loads((каталог / f"audit-{имя}.json").read_text(encoding="utf-8"))
        итоги.append({
            "profile": имя, "title": шаблон["имя"], "description": шаблон["описание"],
            "order": шаблон["порядок"], "hero": шаблон["герой"],
            "weekly": шаблон["недельный"], "added": шаблон["новое"],
            "fresh": шаблон["свежие"],
            "verdict": отчёт["verdict"], "exit": код,
            "failures": отчёт["failures"],
        })
    (куда / "templates.json").write_text(
        json.dumps({"templates": итоги,
                    "passed": sum(1 for и in итоги if и["verdict"] == "PASS"),
                    "total": len(итоги), "widths": ширины},
                   ensure_ascii=False, indent=1), encoding="utf-8")
    лист = контактный_лист(куда, итоги, ширины)
    print(json.dumps({
        "passed": sum(1 for и in итоги if и["verdict"] == "PASS"),
        "total": len(итоги), "contact_sheet": str(лист),
        "failed": [и["profile"] for и in итоги if и["verdict"] != "PASS"],
    }, ensure_ascii=False, indent=1))
    return 0 if all(и["verdict"] == "PASS" for и in итоги) else 2


if __name__ == "__main__":
    sys.exit(main())
