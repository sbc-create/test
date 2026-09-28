#!/usr/bin/env python3
"""Отпечаток кандидата и сверка двух сборок.

Отпечаток считается по содержимому и ОТНОСИТЕЛЬНЫМ путям: абсолютный путь в
отпечатке означал бы, что один и тот же срез в двух каталогах даёт разные
значения, и сравнение «собрано дважды одинаково» ломалось бы на пустом месте.

    python3 automation/host/zone-r2-candidate-manifest.py var/build-a/zona-cinema [var/build-b/zona-cinema]
"""
from __future__ import annotations

import hashlib
import json
import pathlib
import sys

КОРЕНЬ = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(КОРЕНЬ))

from factory.lords import artifact as artifact_mod  # noqa: E402


def отпечаток(корень: pathlib.Path) -> tuple[str, int]:
    """Правило одно на всех: `factory.lords.artifact`."""
    return artifact_mod.отпечаток(корень), len(artifact_mod.файлы_артефакта(корень))


def сведения(корень: pathlib.Path) -> dict:
    отчёт = json.loads((корень / "preview-report.json").read_text("utf-8"))
    карта = json.loads((корень / "route-map.json").read_text("utf-8"))
    цифра, файлов = отпечаток(корень)
    страниц = len([x for x in (корень / "title").iterdir()
                   if (x / "index.html").is_file()])
    return {"root": str(корень), "artifact_sha256": цифра, "files": файлов,
            "routes": len(карта["routes"]),
            "route_map_sha256": отчёт["route_map"]["route_map_sha256"],
            "title_pages": отчёт["title_pages"], "rendered_dirs": страниц,
            "orphan_targets": отчёт["route_map"]["orphan_targets"],
            "card_targets": отчёт["route_map"]["card_targets"],
            "catalog_records": отчёт["data_provenance"]["records"],
            "seconds": отчёт["seconds"]}


def главное(аргв=None) -> int:
    пути = [pathlib.Path(а) if pathlib.Path(а).is_absolute() else КОРЕНЬ / а
            for а in (аргв if аргв is not None else sys.argv[1:])]
    if not пути:
        print(__doc__)
        return 2
    сводка = [сведения(п) for п in пути]
    for с in сводка:
        assert с["routes"] == с["rendered_dirs"] == с["title_pages"], (
            f"{с['root']}: маршрутов {с['routes']}, страниц {с['rendered_dirs']}, "
            f"в отчёте {с['title_pages']}")
    манифест_кандидатов(пути, КОРЕНЬ / "artifacts" / "zone-tpl-001-r2" /
                        "candidate-artifacts.json")
    вывод = {"builds": сводка}
    # Детерминизм сравнивается ПО ВИТРИНАМ. Сравнивать вместе сборки разных
    # витрин бессмысленно: они и обязаны различаться, а общий флаг «не
    # совпало» выглядел бы как дефект сборки и заставил бы искать несуществующую
    # причину.
    по_витрине: dict = {}
    for путь, с in zip(пути, сводка):
        по_витрине.setdefault(путь.name, []).append(с)
    детерминизм = {}
    for продукт, сборки in по_витрине.items():
        if len(сборки) < 2:
            continue
        детерминизм[продукт] = {
            "builds": len(сборки),
            "artifact_sha256_match": len({с["artifact_sha256"] for с in сборки}) == 1,
            "route_map_sha256_match": len({с["route_map_sha256"] for с in сборки}) == 1,
        }
    if детерминизм:
        вывод["determinism"] = детерминизм
    print(json.dumps(вывод, ensure_ascii=False, indent=1))
    return 0



def манифест_кандидатов(пути, файл: pathlib.Path) -> dict:
    """Сводка кандидатов в том виде, который читают проверки контура."""
    САЙТЫ = {"zona-cinema": ["zona-01"],
             "animedia-portal": ["animedia-01", "animedia-02"]}
    свод = {}
    for п in пути:
        с = сведения(п)
        продукт = п.name
        свод[продукт] = {"artifact_sha256": с["artifact_sha256"],
                         "files": с["files"], "site_ids": САЙТЫ.get(продукт, []),
                         "route_map_sha256": с["route_map_sha256"],
                         "routes": с["routes"], "orphans": с["orphan_targets"],
                         "catalog_records": с["catalog_records"],
                         "published_entities": с["rendered_dirs"]}
    файл.parent.mkdir(parents=True, exist_ok=True)
    файл.write_text(json.dumps(свод, ensure_ascii=False, indent=1) + "\n",
                    encoding="utf-8")
    return свод


if __name__ == "__main__":
    raise SystemExit(главное())
