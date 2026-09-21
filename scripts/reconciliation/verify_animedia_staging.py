#!/usr/bin/env python3
"""Сверяет заряженный релиз Animedia с его исходником и с целью отката.

Манифест, RELEASE.json и символическая ссылка утверждают одно и то же тремя
голосами. Совпадение голосов между собой ничего не доказывает: их писал один
и тот же прогон. Независимая опора одна — объекты git: файл на ревизии
`source_commit` обязан иметь ровно тот digest, который манифест выдаёт за
артефакт. Если это так, цепочка «ревизия → артефакт → ссылка → манифест»
сходится целиком, а не по кругу.

Скрипт только читает.
"""

from __future__ import annotations

import hashlib
import json
import pathlib
import subprocess
import sys

FRONT = pathlib.Path("/srv/lords/.frontend")
РЕПО = pathlib.Path(__file__).resolve().parents[2]

ВИТРИНЫ = {
    "animedia-01": {"порт": 9121, "домен": "animedia.icu",
                    "манифест": FRONT / "template-manifest-animedia-01.json"},
    "animedia-02": {"порт": 9122, "домен": "animedia.space",
                    "манифест": FRONT / "template-manifest-animedia-02.json"},
}

ОТКАТ = FRONT / "releases/20260921T154512Z-8966632-animedia-rollback"
#: Файлы релиза и их место в репозитории — из RELEASE.json самого релиза.
ОЖИДАЕМЫЕ_ФАЙЛЫ = ("lords-frontend.py", "seo_layer.py", "collection_contract.py")


def sha_файла(p: pathlib.Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def sha_из_git(ревизия: str, путь: str) -> str | None:
    try:
        данные = subprocess.check_output(
            ["git", "show", f"{ревизия}:{путь}"], cwd=РЕПО, stderr=subprocess.DEVNULL)
    except subprocess.CalledProcessError:
        return None
    return hashlib.sha256(данные).hexdigest()


def проверить_релиз(каталог: pathlib.Path) -> dict[str, object]:
    паспорт = json.loads((каталог / "RELEASE.json").read_text(encoding="utf-8"))
    ревизия = паспорт["source_commit"]
    файлы: dict[str, object] = {}
    все_совпали = True
    for имя, запись in (паспорт.get("files") or {}).items():
        на_диске = каталог / имя
        есть = на_диске.is_file()
        диск = sha_файла(на_диске) if есть else None
        из_git = sha_из_git(ревизия, запись["repo_path"])
        совпало = bool(диск and диск == запись["sha256"] and диск == из_git)
        все_совпали = все_совпали and совпало
        файлы[имя] = {
            "repo_path": запись["repo_path"],
            "паспорт": запись["sha256"],
            "на_диске": диск,
            "из_git": из_git,
            "совпало": совпало,
        }
    недостающие = [и for и in ОЖИДАЕМЫЕ_ФАЙЛЫ if not (каталог / и).is_file()]
    return {
        "release_dir": str(каталог),
        "build_id": паспорт["build_id"],
        "source_commit": ревизия,
        "artifact_sha256": паспорт["artifact_sha256"],
        "source_dirty": паспорт.get("source_dirty"),
        "файлы": файлы,
        "недостающие_файлы": недостающие,
        "ВСЕ_ФАЙЛЫ_СОШЛИСЬ_С_GIT": все_совпали and not недостающие,
    }


def main() -> int:
    отчёт: dict[str, object] = {}

    for витрина, данные in ВИТРИНЫ.items():
        ссылка = FRONT / "sites" / витрина / "current"
        цель = ссылка.resolve() if ссылка.exists() else None
        манифест = json.loads(данные["манифест"].read_text(encoding="utf-8"))
        релиз = проверить_релиз(цель) if цель else None

        сошлось = bool(
            релиз
            and манифест["artifact_sha256"] == релиз["artifact_sha256"]
            and манифест["build_id"] == релиз["build_id"]
            and манифест["source_commit"] == релиз["source_commit"]
            and релиз["ВСЕ_ФАЙЛЫ_СОШЛИСЬ_С_GIT"]
        )
        отчёт[витрина] = {
            "домен": данные["домен"],
            "порт": данные["порт"],
            "ссылка": str(ссылка),
            "ссылка_ведёт_на": str(цель) if цель else None,
            "ссылка_это_симлинк": ссылка.is_symlink(),
            "манифест": {
                "build_id": манифест["build_id"],
                "artifact_sha256": манифест["artifact_sha256"],
                "source_commit": манифест["source_commit"],
                "profile": манифест.get("profile"),
            },
            "релиз": релиз,
            "МАНИФЕСТ_И_НАЗНАЧЕНИЕ_СОГЛАСОВАНЫ": сошлось,
        }

    отчёт["откат"] = проверить_релиз(ОТКАТ) if ОТКАТ.is_dir() else {"отсутствует": True}

    ворота = {
        "ASSIGNMENT_IS_SYMLINK": all(
            отчёт[в]["ссылка_это_симлинк"] for в in ВИТРИНЫ),
        "MANIFEST_MATCHES_ASSIGNMENT": all(
            отчёт[в]["МАНИФЕСТ_И_НАЗНАЧЕНИЕ_СОГЛАСОВАНЫ"] for в in ВИТРИНЫ),
        "BOTH_SITES_SAME_RELEASE": len({
            отчёт[в]["ссылка_ведёт_на"] for в in ВИТРИНЫ}) == 1,
        "ARTIFACT_MATCHES_SOURCE_REVISION": all(
            отчёт[в]["релиз"]["ВСЕ_ФАЙЛЫ_СОШЛИСЬ_С_GIT"] for в in ВИТРИНЫ),
        "ROLLBACK_PRESENT_AND_VERIFIED": bool(
            отчёт["откат"].get("ВСЕ_ФАЙЛЫ_СОШЛИСЬ_С_GIT")),
    }
    отчёт["ворота"] = ворота
    отчёт["VERDICT"] = "PASS" if all(ворота.values()) else "FAIL"

    print(json.dumps(отчёт, ensure_ascii=False, indent=2))
    return 0 if all(ворота.values()) else 2


if __name__ == "__main__":
    raise SystemExit(main())
