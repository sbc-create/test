#!/usr/bin/env python3
"""Топ по оценкам для Animedia — из утверждённого снимка, без выдумок.

Чем это НЕ является. Это не «Топ‑100» оригинала: там ранжирование по
популярности, а данных о популярности — просмотрах, добавлениях в списки,
позиции в чарте — витрине не передано ни в снимке, ни в боковом файле. Пока
их нет, блок популярности остаётся объявленным пробелом; собрать его из
чего-нибудь похожего значило бы выдать одну величину за другую.

Чем это является. Упорядочение по той самой сводной оценке, которую витрина
уже показывает на карточке и на странице произведения: те же источники, та же
методика `weighted-log-votes/1.0`, тот же снимок. Здесь не появляется ни одной
новой цифры — только порядок по уже показанным.

Порог голосов. Без него наверх встают записи с оценкой 10 от шести голосов, и
список перестаёт что-либо означать. Порог записан в файле рядом с результатом,
чтобы читатель отчёта видел, что именно отсекли, а не догадывался.

    python3 automation/host/animedia-ratings-top.py --site animedia-01
    python3 automation/host/animedia-ratings-top.py --site animedia-01 --dry-run
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import sys
import tempfile
import time
from pathlib import Path

КОРЕНЬ = Path(__file__).resolve().parents[2]
РАНТАЙМ = Path(os.environ.get("ANIMEDIA_RUNTIME_ROOT", "/srv/lords/.frontend"))
#: Результат кладётся рядом со снимком каталога: витрина работает от другого
#: пользователя и внутрь репозитория не смотрит, а корень рантайма читает.
ХРАНИЛИЩЕ = РАНТАЙМ
#: Право на чтение всем — иначе файл, написанный этой учётной записью, для
#: пользователя витрины не существует, и блок молча не появится.
РЕЖИМ_ФАЙЛА = 0o644

#: Минимум голосов, ниже которого запись в топ не берётся. Значение выбрано по
#: живому снимку: медиана голосов 359, поэтому 500 оставляет верхнюю половину
#: записей с настоящим числом голосов и убирает единичные оценки.
ПОРОГ_ГОЛОСОВ = 500

#: Сколько мест в списке. Столько же, сколько у оригинального блока, — чтобы
#: место под него на странице не менялось, когда появятся данные популярности.
МЕСТ = 100


def _рантайм():
    """Модуль витрины: методика сводной оценки берётся из него, а не копируется."""
    манифест = ХРАНИЛИЩЕ / "_манифест-топа.json"
    манифест.parent.mkdir(parents=True, exist_ok=True)
    манифест.write_text(json.dumps({
        "schema_version": 1, "template_family": "animedia", "design_version": "0",
        "source_commit": "0" * 40, "build_id": "ratings-top",
        "artifact_sha256": "0" * 64, "profile": "animedia-icu",
        "built_at": "1970-01-01T00:00:00Z"}), encoding="utf-8")
    os.environ["ANIMEDIA_TEMPLATE_MANIFEST"] = str(манифест)
    os.environ.pop("LORDS_TEMPLATE_MANIFEST", None)
    спец = importlib.util.spec_from_file_location(
        "animedia_runtime_top", Path(__file__).with_name("animedia-frontend.py"))
    модуль = importlib.util.module_from_spec(спец)
    sys.modules[спец.name] = модуль
    спец.loader.exec_module(модуль)
    манифест.unlink(missing_ok=True)
    return модуль


def собрать(детали: dict, каталог: dict, сводная, *,
            порог: int = ПОРОГ_ГОЛОСОВ, мест: int = МЕСТ) -> tuple[list, dict]:
    """Список мест и сводка о том, из чего он получился."""
    кандидаты = []
    без_оценок = 0
    ниже_порога = 0
    for slug, деталь in (детали or {}).items():
        if slug not in каталог:
            continue
        свод = сводная(деталь)
        if not свод:
            без_оценок += 1
            continue
        голосов = int(свод.get("всего_голосов") or 0)
        if голосов < порог:
            ниже_порога += 1
            continue
        кандидаты.append({
            "slug": slug,
            "title": каталог[slug].get("title") or slug,
            "url": каталог[slug].get("url") or f"/title/{slug}/",
            "value": float(str(свод["значение"]).replace(",", ".")),
            "votes": голосов,
            "sources": свод["источников"],
            "method": свод["методика"],
        })
    # Порядок: оценка, затем число голосов, затем slug. Последнее — ради
    # устойчивости: без него два одинаковых результата меняются местами между
    # сборками, и «место 17» перестаёт что-либо значить.
    кандидаты.sort(key=lambda к: (-к["value"], -к["votes"], к["slug"]))
    места = кандидаты[:мест]
    for н, к in enumerate(места, 1):
        к["rank"] = н
    сводка = {
        "candidates": len(кандидаты),
        "without_ratings": без_оценок,
        "below_threshold": ниже_порога,
        "threshold_votes": порог,
        "places": len(места),
    }
    return места, сводка


def _записать_атомарно(путь: Path, данные: dict) -> None:
    путь.parent.mkdir(parents=True, exist_ok=True)
    с, врем = tempfile.mkstemp(dir=str(путь.parent), prefix=путь.name, suffix=".tmp")
    try:
        with os.fdopen(с, "w", encoding="utf-8") as ф:
            json.dump(данные, ф, ensure_ascii=False, indent=1)
            ф.write("\n")
        os.chmod(врем, РЕЖИМ_ФАЙЛА)
        os.replace(врем, путь)
    except BaseException:
        Path(врем).unlink(missing_ok=True)
        raise


def main() -> int:
    р = argparse.ArgumentParser(description=__doc__)
    р.add_argument("--site", default="animedia-01")
    р.add_argument("--threshold", type=int, default=ПОРОГ_ГОЛОСОВ)
    р.add_argument("--places", type=int, default=МЕСТ)
    р.add_argument("--dry-run", action="store_true")
    a = р.parse_args()

    детали_файл = РАНТАЙМ / f"{a.site}-details.json"
    каталог_файл = РАНТАЙМ / f"{a.site}-catalog.json"
    if not детали_файл.is_file():
        raise SystemExit(f"нет снимка подробностей: {детали_файл}")
    сырое = json.loads(детали_файл.read_text(encoding="utf-8"))
    детали = сырое.get("details") or {}
    каталог_сырое = json.loads(каталог_файл.read_text(encoding="utf-8"))
    записи = (каталог_сырое.get("items") if isinstance(каталог_сырое, dict)
              else каталог_сырое)
    каталог = {з["slug"]: з for з in записи if з.get("slug")}

    модуль = _рантайм()
    места, сводка = собрать(детали, каталог, модуль.сводная_оценка,
                            порог=a.threshold, мест=a.places)

    отпечаток = hashlib.sha256(
        json.dumps([(м["slug"], м["value"]) for м in места],
                   ensure_ascii=False).encode("utf-8")).hexdigest()
    документ = {
        "schema_version": 1,
        "site": a.site,
        "basis": "ratings-aggregate",
        "method": "weighted-log-votes/1.0",
        "method_note": ("Порядок по сводной оценке витрины. Это не популярность: "
                        "данных о просмотрах и добавлениях в списки в снимке нет."),
        "threshold_votes": a.threshold,
        "catalog_revision": str(сырое.get("catalog_revision") or ""),
        "catalog_built_at": str(сырое.get("catalog_built_at") or ""),
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "digest": отпечаток,
        "summary": сводка,
        "places": места,
    }
    отчёт = dict(сводка, site=a.site, digest=отпечаток,
                 top3=[(м["rank"], м["title"], м["value"], м["votes"]) for м in места[:3]])
    if a.dry_run:
        print(json.dumps(отчёт, ensure_ascii=False, indent=1))
        return 0
    путь = ХРАНИЛИЩЕ / f"{a.site}-ratings-top.json"
    _записать_атомарно(путь, документ)
    отчёт["file"] = str(путь)
    print(json.dumps(отчёт, ensure_ascii=False, indent=1))
    if not места:
        print("мест нет: ни одна запись не прошла порог голосов — "
              "блок останется объявленным пробелом, а не пустым списком")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
