#!/usr/bin/env python3
"""Обязательная версионность шаблонов: манифест, сверка, матрица.

Правило владельца от 2026-09-10. Версия шаблона больше не определяется по
косвенным признакам — ни по классу в CSS, ни по размеру файла, ни по имени
изменяемого тега, ни по ссылке, ни по коду 200, ни по факту, что контейнер
запущен. Версия — это объявленное значение, которое обязано совпадать во всех
местах сразу.

Семейства версионируются раздельно: Lords, Yummy, Zona, Animedia.

Старый неподтверждённый дизайн обозначается `LEGACY_UNVERSIONED`. Присваивать
ему версию задним числом запрещено: это было бы объявлением о проверке,
которой не было.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
import time
from pathlib import Path

КОРЕНЬ = Path("/home/claude/wt-integration-28")
МАТРИЦА = КОРЕНЬ / "status" / "template-versions.json"
ЛЕГАСИ = "LEGACY_UNVERSIONED"
СЕМЕЙСТВА = ("lords", "yummy", "zona", "animedia")
SEMVER = re.compile(r"^\d+\.\d+\.\d+(?:-[0-9A-Za-z.-]+)?(?:\+[0-9A-Za-z.-]+)?$")
ХЕКС40 = re.compile(r"^[0-9a-f]{40}$")
ХЕКС64 = re.compile(r"^[0-9a-f]{64}$")

ОБЯЗАТЕЛЬНЫЕ = ("schema_version", "template_family", "design_version", "source_commit",
                "build_id", "artifact_sha256", "profile", "built_at")


def отпечаток_текста(т: str) -> str:
    return hashlib.sha256(т.encode("utf-8")).hexdigest()


def собрать_манифест(*, family: str, design_version: str, source_commit: str,
                     profile: str, artifact_sha256: str, build_suffix: str) -> dict:
    if family not in СЕМЕЙСТВА:
        raise SystemExit(f"неизвестное семейство: {family}")
    if not SEMVER.match(design_version):
        raise SystemExit(f"design_version не по SemVer: {design_version}")
    if not ХЕКС40.match(source_commit):
        raise SystemExit("source_commit обязан быть полным SHA из сорока знаков")
    if not ХЕКС64.match(artifact_sha256):
        raise SystemExit("artifact_sha256 обязан быть шестьюдесятью четырьмя знаками")
    когда = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    return {
        "schema_version": 1,
        "template_family": family,
        "design_version": design_version,
        "source_commit": source_commit,
        # Уникален для каждой сборки: время плюс суффикс плюс начало коммита.
        "build_id": f"{когда}-{source_commit[:8]}-{build_suffix}",
        "artifact_sha256": artifact_sha256,
        "profile": profile,
        "built_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }


def проверить_манифест(м: dict) -> list[str]:
    беды = [f"нет поля {п}" for п in ОБЯЗАТЕЛЬНЫЕ if п not in м]
    if "design_version" in м and м["design_version"] != ЛЕГАСИ \
            and not SEMVER.match(str(м["design_version"])):
        беды.append("design_version не по SemVer")
    if "source_commit" in м and not ХЕКС40.match(str(м["source_commit"])):
        беды.append("source_commit не полный SHA")
    if "artifact_sha256" in м and not ХЕКС64.match(str(м["artifact_sha256"])):
        беды.append("artifact_sha256 не 64 знака")
    if "build_id" in м and not str(м["build_id"]).strip():
        беды.append("build_id пуст")
    return беды


def публичная_версия(домен: str) -> dict:
    """Что домен объявляет о себе САМ. Ничего не выводится по косвенным признакам."""
    итог = {"domain": домен}
    # Тело и заголовки берутся ОТДЕЛЬНЫМИ запросами.
    #
    # `curl -D -` кладёт в stdout и то и другое, а разбор по первому пустому
    # разделителю ломается на редиректах и HTTP/2: первый прогон сверки объявил
    # «endpoint молчит» при полностью исправном endpoint.
    метка = int(time.time())
    тело = subprocess.run(
        ["curl", "-sS", "-L", "--max-time", "20", "-H", "Cache-Control: no-cache",
         f"https://{домен}/__template_version?cb={метка}"],
        capture_output=True, text=True).stdout
    try:
        итог["endpoint"] = json.loads(тело)
    except ValueError:
        итог["endpoint"] = None
    заголовки = subprocess.run(
        ["curl", "-sS", "-D", "-", "-o", "/dev/null", "-L", "--max-time", "20",
         "-H", "Cache-Control: no-cache", f"https://{домен}/?cb={метка}"],
        capture_output=True, text=True).stdout
    for имя in ("x-site-factory-template-revision", "x-site-factory-template-version",
                "x-site-factory-template-family", "x-site-factory-build-id"):
        m = re.search(rf"^{имя}:\s*(.+)$", заголовки, re.I | re.M)
        итог[имя] = m.group(1).strip() if m else None
    страница = subprocess.run(
        ["curl", "-sS", "-L", "--max-time", "20", "-H", "Cache-Control: no-cache",
         f"https://{домен}/?cb={метка}"], capture_output=True, text=True).stdout
    for поле in ("site-factory-template-revision", "site-factory-design-version",
                 "site-factory-build-id", "site-factory-template-family"):
        m = re.search(rf'<meta name="{поле}" content="([^"]*)"', страница)
        итог[f"meta:{поле}"] = m.group(1) if m else None
    m = re.search(r'<html[^>]+data-template-version="([^"]*)"', страница)
    итог["data-template-version"] = m.group(1) if m else None
    return итог


def сверить(цель: dict, публичное: dict) -> tuple[bool, list[str]]:
    """DEPLOYED только когда сходится всё сразу."""
    беды = []
    к = публичное.get("endpoint") or {}
    пары = [
        ("design_version", к.get("design_version"),
         публичное.get("meta:site-factory-design-version")),
        ("source_commit", к.get("source_commit"),
         публичное.get("meta:site-factory-template-revision")),
        ("build_id", к.get("build_id"), публичное.get("meta:site-factory-build-id")),
    ]
    for имя, из_endpoint, из_meta in пары:
        if из_endpoint is None:
            беды.append(f"{имя}: endpoint молчит")
            continue
        if str(из_endpoint) != str(цель.get(имя)):
            беды.append(f"{имя}: публично {из_endpoint}, целевое {цель.get(имя)}")
        if из_meta is not None and str(из_meta) != str(из_endpoint):
            беды.append(f"{имя}: meta {из_meta} против endpoint {из_endpoint}")
    зг = публичное.get("x-site-factory-template-version")
    if зг and зг != цель.get("design_version"):
        беды.append(f"заголовок версии {зг} против целевого {цель.get('design_version')}")
    return (not беды), беды


def обновить_матрицу(записи: list[dict]) -> None:
    МАТРИЦА.parent.mkdir(parents=True, exist_ok=True)
    прежнее = {}
    if МАТРИЦА.is_file():
        try:
            прежнее = {з["domain"]: з for з in json.loads(
                МАТРИЦА.read_text(encoding="utf-8")).get("domains", [])}
        except ValueError:
            прежнее = {}
    for з in записи:
        прежнее[з["domain"]] = з
    МАТРИЦА.write_text(json.dumps({
        "schema_version": 1,
        "note": ("Матрица версий шаблонов по девяти доменам. Публичная версия берётся "
                 "из самого домена, а не выводится по классам, размерам или ссылкам."),
        "updated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "domains": sorted(прежнее.values(), key=lambda з: з["domain"]),
    }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    р = argparse.ArgumentParser(description=__doc__)
    под = р.add_subparsers(dest="верб", required=True)

    b = под.add_parser("build", help="собрать манифест шаблона")
    b.add_argument("--family", required=True)
    b.add_argument("--design-version", required=True)
    b.add_argument("--source-commit", required=True)
    b.add_argument("--profile", required=True)
    b.add_argument("--artifact-sha256", required=True)
    b.add_argument("--build-suffix", default="test")
    b.add_argument("--out", required=True)

    v = под.add_parser("verify", help="сверить публичное с целевым")
    v.add_argument("--manifest", required=True)
    v.add_argument("--domain", required=True)
    v.add_argument("--update-matrix", action="store_true")

    s = под.add_parser("scan", help="снять публичные версии со списка доменов")
    s.add_argument("--domains", nargs="+", required=True)

    args = р.parse_args()

    if args.верб == "build":
        м = собрать_манифест(family=args.family, design_version=args.design_version,
                             source_commit=args.source_commit, profile=args.profile,
                             artifact_sha256=args.artifact_sha256,
                             build_suffix=args.build_suffix)
        беды = проверить_манифест(м)
        if беды:
            raise SystemExit("манифест негоден: " + "; ".join(беды))
        Path(args.out).write_text(json.dumps(м, ensure_ascii=False, indent=2) + "\n",
                                  encoding="utf-8")
        print(json.dumps(м, ensure_ascii=False))
        return 0

    if args.верб == "verify":
        цель = json.loads(Path(args.manifest).read_text(encoding="utf-8"))
        публичное = публичная_версия(args.domain)
        сошлось, беды = сверить(цель, публичное)
        запись = {
            "domain": args.domain,
            "template_family": цель.get("template_family"),
            "target_design_version": цель.get("design_version"),
            "public_design_version": (публичное.get("endpoint") or {}).get("design_version"),
            "target_commit": цель.get("source_commit"),
            "public_commit": (публичное.get("endpoint") or {}).get("source_commit"),
            "artifact_sha256": цель.get("artifact_sha256"),
            "build_id": цель.get("build_id"),
            "public_build_id": (публичное.get("endpoint") or {}).get("build_id"),
            "public_match": сошлось,
            "problems": беды,
            "checked_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        }
        if args.update_matrix:
            обновить_матрицу([запись])
        print(json.dumps(запись, ensure_ascii=False))
        if сошлось:
            print(f"{args.domain} | {цель['template_family']} | {цель['design_version']} | "
                  f"{цель['source_commit']} | {цель['artifact_sha256']} | PUBLIC_MATCH=YES")
        else:
            print(f"{args.domain} | VERSION_MISMATCH | " + "; ".join(беды))
        return 0 if сошлось else 1

    if args.верб == "scan":
        записи = []
        for д in args.domains:
            п = публичная_версия(д)
            к = п.get("endpoint") or {}
            записи.append({
                "domain": д,
                "template_family": к.get("template_family"),
                "target_design_version": None,
                "public_design_version": к.get("design_version") or ЛЕГАСИ,
                "target_commit": None,
                "public_commit": к.get("source_commit"),
                "artifact_sha256": к.get("artifact_sha256"),
                "build_id": None,
                "public_build_id": к.get("build_id"),
                "public_match": None,
                "problems": [] if к else ["домен не отдаёт /__template_version"],
                "checked_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            })
            print(json.dumps(записи[-1], ensure_ascii=False))
        обновить_матрицу(записи)
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main())
