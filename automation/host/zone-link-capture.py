#!/usr/bin/env python3
"""Узкий снимок карточных ссылок шести витрин. Только чтение.

Почему источник — релиз, а не обход сайта
-----------------------------------------

Витрина раздаёт статические файлы: адрес существует тогда и только тогда,
когда в релизе лежит соответствующий index.html. Поэтому перечень
card-bearing маршрутов и множество целей берутся из самого релиза — это и
есть его route manifest. Общий обход сайта дал бы то же самое, но ценой
десятков тысяч запросов к боевым витринам.

Два класса доказательства, и они не смешиваются
-----------------------------------------------

* deterministic_release_membership — решается по составу релиза ПОЛНОСТЬЮ,
  без выборки: для статической раздачи наличие файла и есть ответ;
* observed_http — ограниченная объявленная выборка, которой проверяется, что
  правило «файл есть ⇔ ответ 200» действительно выполняется.

Выборка проверяет ПРАВИЛО, а не заменяет собой полный учёт. Распространять
результат тридцати запросов на четыре тысячи ссылок здесь нечем и незачем.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

КОРЕНЬ_ВИТРИН = Path("/srv/lords")
ССЫЛКА = re.compile(r'href="(/title/[^"#?]*)"')
#: Сколько адресов на витрину проверяется живым запросом. Число объявлено
#: заранее и одинаково для всех: выборка «сколько успеется» несопоставима.
ПРОВЕРЯЕМЫХ_НА_ВИТРИНУ = 40


def сейчас() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def нормализовать(цель: str) -> str:
    ц = (цель or "").split("#")[0].split("?")[0]
    while "//" in ц:
        ц = ц.replace("//", "/")
    if not ц.startswith("/"):
        ц = "/" + ц
    ц = ц.lower()
    if ц != "/" and "." not in ц.rsplit("/", 1)[-1] and not ц.endswith("/"):
        ц += "/"
    return ц


def сущность(цель: str) -> str:
    """Идентичность сущности из адреса: последний непустой сегмент."""
    куски = [к for к in нормализовать(цель).split("/") if к]
    return куски[-1] if куски else ""


def отпечаток_релиза(корень: Path) -> str:
    м = корень.parent / "release-manifest.json"
    if м.is_file():
        try:
            d = json.loads(м.read_text("utf-8"))
            return d.get("artifact_sha256") or d.get("digest") or d.get("sha") or ""
        except ValueError:
            return ""
    return ""


def снять(site_id: str, домен: str) -> dict:
    сайт = КОРЕНЬ_ВИТРИН / site_id / "current" / "site"
    if not сайт.is_dir():
        return {"site_id": site_id, "error": "релиза нет"}
    отпечаток = отпечаток_релиза(сайт)
    вхождения, цели = [], {}
    несущих = 0
    for страница in sorted(сайт.rglob("index.html")):
        текст = страница.read_text("utf-8", errors="replace")
        найденные = ССЫЛКА.findall(текст)
        if not найденные:
            continue
        несущих += 1
        маршрут = "/" + str(страница.parent.relative_to(сайт)).strip(".") + "/"
        маршрут = нормализовать(маршрут.replace("//", "/"))
        for сырой in найденные:
            цель = нормализовать(сырой)
            вхождения.append({
                "capture_id": "", "site_id": site_id, "source_url": маршрут,
                "entity": сущность(цель), "raw_href": сырой,
                "normalized_target": цель,
                "release_fingerprint": отпечаток, "captured_at": сейчас()})
            цели.setdefault(цель, 0)
            цели[цель] += 1

    # Детерминированный ответ по составу релиза: для статической раздачи
    # наличие файла и есть наличие маршрута.
    наблюдения = []
    существуют, отсутствуют = [], []
    for цель in sorted(цели):
        файл = сайт / цель.strip("/") / "index.html"
        есть = файл.is_file()
        (существуют if есть else отсутствуют).append(цель)
        наблюдения.append({
            "capture_id": "", "site_id": site_id, "normalized_target": цель,
            "evidence_class": "deterministic_release_membership",
            "route_present_in_release": есть,
            "expected_status": 200 if есть else 404,
            "http_status": None, "final_url": None, "redirect_chain": None,
            "content_type": None, "body_sha256": None,
            "resolved_entity": сущность(цель) if есть else None,
            "observed_at": сейчас()})
    return {"site_id": site_id, "domain": домен,
            "release_fingerprint": отпечаток,
            "card_bearing_routes": несущих,
            "occurrences": вхождения, "observations": наблюдения,
            "unique_targets": len(цели),
            "present": существуют, "absent": отсутствуют,
            "detail_pages": len([п for п in (сайт / "title").iterdir()
                                 if п.is_dir()]) if (сайт / "title").is_dir() else 0}


def проверить_правило(снимок: dict) -> list[dict]:
    """Живая проверка правила на объявленной выборке. Каждый адрес — один раз."""
    домен = снимок["домен"] if "домен" in снимок else снимок["domain"]
    половина = ПРОВЕРЯЕМЫХ_НА_ВИТРИНУ // 2
    выборка = снимок["present"][:половина] + снимок["absent"][:половина]
    итог = []
    for цель in выборка:
        адрес = f"https://{домен}{цель}"
        зпр = urllib.request.Request(адрес, headers={
            "User-Agent": "site-factory-zone-capture/1.0 (read-only)"})
        цепь, код, тип, тело = [], None, None, None
        try:
            with urllib.request.urlopen(зпр, timeout=20) as о:
                код, тип = о.status, о.headers.get("Content-Type")
                сырое = о.read()
                тело = hashlib.sha256(сырое).hexdigest()
                финал = о.geturl()
        except urllib.error.HTTPError as ош:
            код, тип = ош.code, ош.headers.get("Content-Type")
            тело = hashlib.sha256(ош.read() or b"").hexdigest()
            финал = адрес
        except Exception as ош:
            код, финал = None, f"error:{type(ош).__name__}"
        итог.append({
            "capture_id": "", "site_id": снимок["site_id"],
            "normalized_target": цель, "evidence_class": "observed_http",
            "route_present_in_release": цель in set(снимок["present"]),
            "expected_status": 200 if цель in set(снимок["present"]) else 404,
            "http_status": код, "final_url": финал, "redirect_chain": цепь,
            "content_type": тип, "body_sha256": тело,
            "resolved_entity": сущность(цель) if код == 200 else None,
            "observed_at": сейчас()})
    return итог


if __name__ == "__main__":
    вывод = Path(sys.argv[1])
    вывод.mkdir(parents=True, exist_ok=True)
    витрины = json.loads(Path(sys.argv[2]).read_text("utf-8"))
    все_вхождения, все_наблюдения, свод = [], [], []
    for site_id, домен in витрины:
        с = снять(site_id, домен)
        if "error" in с:
            свод.append(с); continue
        живые = проверить_правило(с)
        расхождения = [н for н in живые
                       if н["http_status"] != н["expected_status"]]
        все_вхождения.extend(с["occurrences"])
        все_наблюдения.extend(с["observations"] + живые)
        свод.append({"site_id": site_id, "domain": домен,
                     "release_fingerprint": с["release_fingerprint"],
                     "card_bearing_routes": с["card_bearing_routes"],
                     "link_occurrences": len(с["occurrences"]),
                     "unique_targets": с["unique_targets"],
                     "detail_pages": с["detail_pages"],
                     "routes_present": len(с["present"]),
                     "routes_absent": len(с["absent"]),
                     "http_checked": len(живые),
                     "rule_violations": len(расхождения),
                     "violations": расхождения[:3]})

    идентификатор = hashlib.sha256(
        json.dumps(свод, ensure_ascii=False, sort_keys=True).encode()).hexdigest()[:16]
    for строка in все_вхождения:
        строка["capture_id"] = идентификатор
    for строка in все_наблюдения:
        строка["capture_id"] = идентификатор

    (вывод / "link-occurrences.jsonl").write_text(
        "\n".join(json.dumps(с, ensure_ascii=False) for с in все_вхождения) + "\n",
        encoding="utf-8")
    (вывод / "target-observations.jsonl").write_text(
        "\n".join(json.dumps(с, ensure_ascii=False) for с in все_наблюдения) + "\n",
        encoding="utf-8")
    манифест = {
        "capture_id": идентификатор, "captured_at": сейчас(),
        "storefronts": свод,
        "http_budget_per_storefront": ПРОВЕРЯЕМЫХ_НА_ВИТРИНУ,
        "files": {},
    }
    for имя in ("link-occurrences.jsonl", "target-observations.jsonl"):
        манифест["files"][имя] = hashlib.sha256(
            (вывод / имя).read_bytes()).hexdigest()
    (вывод / "capture-manifest.json").write_text(
        json.dumps(манифест, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(json.dumps({"capture_id": идентификатор, "storefronts": свод},
                     ensure_ascii=False, indent=1))
