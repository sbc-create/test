#!/usr/bin/env python3
"""Офлайн-пересчёт метрик FLEET-TPL-005 по закреплённым артефактам.

Ни одного обращения к сайтам, браузерам и сети: считаются только файлы,
снятые в ходе того аудита. Каждое число сопровождается определением единицы,
предикатом пригодности, знаменателем, правилом нормализации и ключом
дедупликации — иначе «49» и «166 из 169» остаются словами, которые нельзя
проверить.

Доказательства делятся на три класса и не смешиваются:

* observed_http — есть сохранённый код ответа для КОНКРЕТНОГО адреса;
* deterministic_release_membership — адрес детерминированно отсутствует в
  закреплённом перечне маршрутов выложенного релиза;
* inferred — вывод по выборке.

Вывод по выборке метрикой не является. Тридцать проверенных ссылок не
превращаются в сто шестьдесят шесть оттого, что остальные похожи.
"""
from __future__ import annotations

import hashlib
import json
import pathlib
import sys
from typing import Any

ФАЙЛЫ = ("routes.json", "card-links.json", "browser-matrix.json",
         "functional.json", "measurements.json", "audit-manifest.json")

#: Семейство по домену — из манифеста аудита, а не по имени.
СЕМЕЙСТВО_ПО_ДОМЕНУ: dict[str, str] = {}


def sha256_файла(п: pathlib.Path) -> str:
    return hashlib.sha256(п.read_bytes()).hexdigest()


def sha256_множества(значения) -> str:
    сырое = "\n".join(sorted(значения))
    return hashlib.sha256(сырое.encode("utf-8")).hexdigest()


def нормализовать(маршрут: str) -> str:
    """Единое написание адреса.

    Схема и хост отбрасываются: единица — маршрут в пределах витрины. Хвостовой
    слэш сохраняется значащим: `/new` и `/new/` у этих витрин разные адреса, и
    их слияние скрыло бы часть отказов.
    """
    м = (маршрут or "").strip()
    for префикс in ("https://", "http://"):
        if м.startswith(префикс):
            м = "/" + м[len(префикс):].partition("/")[2]
    м = м.split("#", 1)[0].split("?", 1)[0]
    return м or "/"


def ключ_маршрута(домен: str, маршрут: str) -> str:
    return f"{домен}|{нормализовать(маршрут)}"


def разобрать(корень: pathlib.Path) -> dict[str, Any]:
    сведения = {}
    for имя in ФАЙЛЫ:
        п = корень / имя
        if not п.is_file():
            сведения[имя] = {"path": str(п), "present": False}
            continue
        сведения[имя] = {"path": str(п), "present": True,
                         "sha256": sha256_файла(п),
                         "bytes": п.stat().st_size,
                         "data": json.loads(п.read_text("utf-8"))}
    return сведения


# --- метрика 1: сломанные существующие маршруты ------------------------------

def маршруты(сведения: dict) -> dict[str, Any]:
    д = сведения["routes.json"]["data"]
    манифест = сведения["audit-manifest.json"]["data"]["records"]
    для_домена = {з["domain"]: з.get("site_id") for з in манифест if з.get("domain")}

    пригодные, сломанные, разбор = set(), set(), {}
    коды: dict[str, int] = {}
    исключено = {"не входит в перечень со стартовой страницы": 0}
    for домен, з in д.items():
        со_стартовой = {нормализовать(м) for м in з["routes_from_home"]}
        for зап in з["checked"]:
            маршрут = нормализовать(зап["route"])
            ключ = ключ_маршрута(домен, маршрут)
            if маршрут not in со_стартовой:
                # Зондовые адреса проверялись «есть ли вообще»; их отсутствие
                # дефектом существующего маршрута не является.
                исключено["не входит в перечень со стартовой страницы"] += 1
                continue
            пригодные.add(ключ)
            код = зап.get("final_status")
            коды[str(код)] = коды.get(str(код), 0) + 1
            if isinstance(код, int) and код >= 400:
                сломанные.add(ключ)
                разбор.setdefault(домен, {"site_id": для_домена.get(домен),
                                          "broken": 0})
                разбор[домен]["broken"] += 1
    return {
        "unit": "пара (домен, нормализованный маршрут), объявленный самой "
                "витриной на стартовой странице и отвечающий кодом >= 400",
        "source": "routes.json → <домен>.checked[].final_status",
        "eligibility": "маршрут присутствует в <домен>.routes_from_home",
        "denominator": len(пригодные),
        "exclusions": исключено,
        "normalization": "схема и хост отброшены; query и fragment отброшены; "
                         "хвостовой слэш значащий",
        "dedup_key": "домен|маршрут",
        "formula": "|{(домен,маршрут) : пригоден и final_status >= 400}|",
        "recomputed": len(сломанные),
        "status_codes": коды,
        "by_domain": разбор,
        "set_sha256": sha256_множества(сломанные),
        "eligible_set_sha256": sha256_множества(пригодные),
        "evidence_class": "observed_http",
        "members": sorted(сломанные),
    }


# --- метрика 2: затронутые уникальные ссылки ---------------------------------

def ссылки(сведения: dict) -> dict[str, Any]:
    д = сведения["card-links.json"]["data"]
    по_доменам = {}
    наблюдено = выведено = уникальных = 0
    for домен, з in д.items():
        уник = int(з.get("уникальных_карточек") or 0)
        проверено = int(з.get("проверено") or 0)
        коды = {str(к): int(v) for к, v in (з.get("коды") or {}).items()}
        сломано_наблюдаемо = sum(v for к, v in коды.items()
                                 if к.isdigit() and int(к) >= 400)
        по_доменам[домен] = {"unique_cards": уник, "checked": проверено,
                             "observed_broken": сломано_наблюдаемо,
                             "codes": коды,
                             "unchecked": max(0, уник - проверено)}
        уникальных += уник
        наблюдено += сломано_наблюдаемо
        выведено += max(0, уник - проверено)
    return {
        "unit": "уникальный адрес карточки на витрине",
        "source": "card-links.json → <домен>.{уникальных_карточек, проверено, коды}",
        "eligibility": "адрес карточки, обнаруженный на витрине",
        "denominator_per_domain": {д: з["unique_cards"] for д, з in по_доменам.items()},
        "exclusions": "ни одной: пофайловый перечень адресов отсутствует",
        "normalization": "неприменимо: адреса не сохранены",
        "dedup_key": "неприменимо: адреса не сохранены",
        "formula": "неприменима — множество построить не из чего",
        "by_domain": по_доменам,
        "observed_http_affected": наблюдено,
        "inferred_only_affected": выведено,
        "recomputable_set": False,
        "set_sha256": None,
        "evidence_class": "observed_http (30 на домен) + inferred (остальное)",
    }


def главное(корень: pathlib.Path) -> dict[str, Any]:
    сведения = разобрать(корень)
    отсутствуют = [и for и in ФАЙЛЫ if not сведения[и]["present"]]
    if отсутствуют:
        return {"error": "нет артефактов", "missing": отсутствуют}
    м = маршруты(сведения)
    л = ссылки(сведения)
    return {
        "artifacts": {и: {k: v for k, v in сведения[и].items() if k != "data"}
                      for и in ФАЙЛЫ},
        "broken_existing_routes": м,
        "affected_unique_links": л,
        "claims": {"broken_existing_routes_reported": 49,
                   "affected_unique_links_reported": 166,
                   "eligible_unique_links_reported": 169},
        "verdict": {
            "routes_reproduce": м["recomputed"] == 49,
            "links_reproduce": False,
            "same_unit": False,
        },
    }


if __name__ == "__main__":
    корень = pathlib.Path(sys.argv[1] if len(sys.argv) > 1
                          else "artifacts/fleet-audit")
    print(json.dumps(главное(корень), ensure_ascii=False, indent=1))
