#!/usr/bin/env python3
"""Единый манифест свидетельств: отпечаток каждого файла и сводные числа.

Манифест — единственный авторитетный источник чисел отчёта. Всё, что в отчёте
названо цифрой, обязано прослеживаться сюда: иначе цифра живёт только в тексте,
и проверить её нельзя.

Сводка собирается ИЗ отчётов, а не переписывается руками рядом с ними. Две
копии одного числа расходятся молча, и расходится именно та, которую реже
открывают.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path


def _sha(п: Path) -> str:
    ч = hashlib.sha256()
    with п.open("rb") as ф:
        for кусок in iter(lambda: ф.read(1 << 20), b""):
            ч.update(кусок)
    return ч.hexdigest()


def _прочитать(п: Path):
    try:
        return json.loads(п.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def сводка(корень: Path) -> dict:
    итог: dict = {}

    аудит = _прочитать(корень / "browser-audit" / "audit.json")
    if аудит:
        страницы = [с for сайт in аудит["sites"].values() for с in сайт["pages"]]
        клики = [к for сайт in аудит["sites"].values() for к in сайт["clicks"]]
        по_сайтам = {и: len(с["clicks"]) for и, с in аудит["sites"].items()}
        итог["browser"] = {
            "pages_measured": len(страницы),
            "viewports": sorted({с["viewport"] for с in страницы}),
            "clicks_total": len(клики),
            "clicks_by_site": по_сайтам,
            "click_failures": sum(1 for к in клики if not к.get("ok")),
            "back_navigation_ok": sum(1 for к in клики if к.get("back_ok") is True),
            "contrast_failures": sum(len(с["contrast_failures"]) for с in страницы),
            "horizontal_overflow_pages": sum(1 for с in страницы if с["overflow"] > 1),
            "broken_images": sum(len(с["broken_images"]) for с in страницы),
            "covered_text": sum(len(с.get("covered_text") or []) for с in страницы),
            "small_touch_targets": sum(len(с["small_touch_targets"]) for с in страницы),
            "focus_visible_pages": sum(1 for с in страницы if с["focus_visible"].get("ok")),
            "console_errors_total": sum(len(с["console_errors"]) for с in страницы),
            "console_errors_outside_404": sum(
                len(с["console_errors"]) for с in страницы if с["tag"] != "not-found"),
        }

    for имя, файл in (("routes_lords", "route-crawl-lords.json"),
                      ("routes_zona", "route-crawl-zona.json")):
        отчёт = _прочитать(корень / файл)
        if отчёт:
            итог[имя] = отчёт["counters"]

    for имя, файл in (("entity_lords", "entity-parity-lords-local.json"),
                      ("entity_zona", "entity-parity-zona-local.json")):
        отчёт = _прочитать(корень / файл)
        if отчёт:
            итог[имя] = отчёт["counters"]

    for имя, файл in (("archetypes_lords", "archetypes-lords-local.json"),
                      ("archetypes_zona", "archetypes-zona-local.json")):
        отчёт = _прочитать(корень / файл)
        if отчёт:
            итог[имя] = отчёт["counters"]

    плеер = _прочитать(корень / "player-states" / "player-six-states.json")
    if плеер:
        итог["player"] = {
            "checked": len(плеер["results"]),
            "passed": sum(1 for р in плеер["results"] if р.get("ok")),
            "states": [р["state"] for р in плеер["results"]],
        }

    разн = _прочитать(корень / "distinctness" / "distinctness.json")
    if разн:
        итог["distinctness"] = {
            "verdict": разн["verdict"],
            "distinct_features": разн["distinct_features"],
            "shared_classes": next(
                (п["общие"] for п in разн["features"] if п["признак"] == "словарь классов"), []),
            "style_differs_without_colour": разн["style_differs_without_colour"],
        }

    сравн = _прочитать(корень / "reference-compare" / "reference-compare.json")
    if сравн:
        близко = расх = нет = 0
        по_признаку: dict[str, int] = {}
        for п in сравн["pairs"]:
            for с in п.get("comparison") or []:
                if с["вердикт"] == "БЛИЗКО":
                    близко += 1
                elif с["вердикт"] == "РАСХОЖДЕНИЕ":
                    расх += 1
                    по_признаку[с["признак"]] = по_признаку.get(с["признак"], 0) + 1
                else:
                    нет += 1
        итог["reference_compare"] = {
            "reference": сравн["reference"], "close": близко,
            "divergent": расх, "no_data": нет, "divergent_by_feature": по_признаку,
        }

    цепь = _прочитать(корень / "serving-chain.json")
    if цепь:
        итог["serving_chain"] = {
            ц["domain"]: {"verdict": ц["verdict"], "unit": ц.get("unit"),
                          "port": ц.get("upstream_port")}
            for ц in цепь["chains"]}

    суита = корень / "suite" / "exit_code"
    лог = корень / "suite" / "pytest.log"
    if суита.is_file() and лог.is_file():
        текст = лог.read_text(encoding="utf-8", errors="replace")
        хвост = [с for с in текст.splitlines() if " passed" in с or " failed" in с]
        итог["suite"] = {
            "exit_code": int(суита.read_text().strip() or -1),
            "summary_line": хвост[-1].strip() if хвост else "",
            "failed": sorted({с[len("FAILED "):].split(" - ")[0].strip()
                              for с in текст.splitlines() if с.startswith("FAILED ")}),
        }
    return итог


def main(argv=None) -> int:
    р = argparse.ArgumentParser(description=__doc__)
    р.add_argument("--root", required=True)
    р.add_argument("--prompt-id", required=True)
    р.add_argument("--branch", required=True)
    р.add_argument("--commit", required=True)
    арг = р.parse_args(argv)

    корень = Path(арг.root)
    файлы = []
    for п in sorted(корень.rglob("*")):
        if п.is_file() and п.name != "evidence-manifest.json":
            файлы.append({"path": str(п.relative_to(корень)), "bytes": п.stat().st_size,
                          "sha256": _sha(п)})
    манифест = {
        "prompt_id": арг.prompt_id,
        "generated_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "task_branch": арг.branch, "task_commit": арг.commit,
        "files_total": len(файлы),
        "summary": сводка(корень),
        "files": файлы,
    }
    текст = json.dumps(манифест, ensure_ascii=False, indent=1) + "\n"
    (корень / "evidence-manifest.json").write_text(текст, encoding="utf-8")
    print(json.dumps(манифест["summary"], ensure_ascii=False, indent=1))
    print(f"\nфайлов: {len(файлы)}")
    print(f"EVIDENCE_MANIFEST_SHA256 = {hashlib.sha256(текст.encode()).hexdigest()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
