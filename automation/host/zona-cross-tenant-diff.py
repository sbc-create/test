"""Побайтовое сравнение отдачи соседних семейств до и после ночной работы.

Один и тот же набор данных, один и тот же манифест, два разных файла рантайма:
стартовый HEAD и текущее дерево. Если байты совпали — витрина соседа не
изменилась. Это проверка результата, а не обещание в коммите.
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import sys
from pathlib import Path

import argparse

_р = argparse.ArgumentParser(description=__doc__)
_р.add_argument("--after", required=True, help="рантайм текущего дерева")
_р.add_argument("--before", required=True, help="рантайм стартового HEAD")
_р.add_argument("--data", required=True, help="каталог со снимком для обеих сторон")
_а, _ = _р.parse_known_args()

НОВЫЙ = Path(_а.after)
СТАРЫЙ = Path(_а.before)
ДАННЫЕ = Path(_а.data)

МАРШРУТЫ = ["/", "/catalog/", "/new/", "/movies/", "/series/", "/animation/",
            "/search/?q=%D0%B0", "/search/?q=zzzzzzzzzz", "/collections/",
            "/title/poteryannyy-v-momente/", "/title/troe-papash/",
            "/title/troe-papash/season-1/",
            "/title/troe-papash/season-1/episode-1/", "/takogo-adresa-net/"]


def поднять(исходник: Path, family: str, design: str, метка: str):
    манифест = ДАННЫЕ / f"manifest-{family}-{метка}.json"
    манифест.write_text(json.dumps({
        "schema_version": 1, "template_family": family, "design_version": design,
        "source_commit": "cmp", "build_id": f"cmp-{family}", "artifact_sha256": "0" * 64,
        "profile": f"{family}-cmp", "built_at": "2026-09-20T00:00:00Z",
    }), encoding="utf-8")
    старое = dict(os.environ)
    os.environ.update({
        "LORDS_TEMPLATE_MANIFEST": str(манифест),
        "LORDS_CATALOG": str(ДАННЫЕ / "zona-01-catalog.json"),
        "LORDS_DETAILS": str(ДАННЫЕ / "zona-01-details.json"),
        "LORDS_POPULAR_WEEKLY": str(ДАННЫЕ / "zona-01-popular-weekly.json"),
        "LORDS_LEGACY_ROOT": str(ДАННЫЕ / "net-takogo"),
        "LORDS_SITE_NAME": family.capitalize(),
        "LORDS_CLOCK_ISO": "2026-09-22T06:00:00Z",
        "PYTHONDONTWRITEBYTECODE": "1",
    })
    os.environ.pop("LORDS_LEGACY_UPSTREAM", None)
    os.environ.pop("LORDS_METRIKA_COUNTER", None)
    try:
        имя = f"cmp_{family}_{метка}"
        спец = importlib.util.spec_from_file_location(имя, исходник)
        модуль = importlib.util.module_from_spec(спец)
        sys.modules[имя] = модуль
        спец.loader.exec_module(модуль)
    finally:
        os.environ.clear()
        os.environ.update(старое)
    модуль.Обработчик.данные = модуль.Данные(str(ДАННЫЕ / "zona-01-catalog.json"))
    модуль.Обработчик.подробности = модуль.Подробности(str(ДАННЫЕ / "zona-01-details.json"))
    модуль.Обработчик.индекс = модуль.построить_индекс(
        модуль.Обработчик.данные, модуль.Обработчик.подробности)
    return модуль


def отдать(модуль, путь: str):
    собрано = {"статус": 200, "тело": b""}

    class Заглушка(модуль.Обработчик):
        def __init__(self):
            self.path = путь
            self.command = "GET"
            self.headers = {"Host": "cmp.example"}

        def _отдать(self, тело, тип="text/html; charset=utf-8", код=200):
            собрано["статус"] = код
            собрано["тело"] = тело

        def send_response(self, код):
            собрано["статус"] = код

        def send_header(self, имя, значение):
            pass

        def end_headers(self):
            pass

    Заглушка().do_GET()
    т = собрано["тело"]
    if isinstance(т, str):
        т = т.encode()
    return собрано["статус"], т


def сравнить(family: str, design: str) -> dict:
    старый = поднять(СТАРЫЙ, family, design, "old")
    новый = поднять(НОВЫЙ, family, design, "new")
    строки = []
    расхождения = []
    for путь in МАРШРУТЫ:
        с1, т1 = отдать(старый, путь)
        с2, т2 = отдать(новый, путь)
        h1 = hashlib.sha256(т1).hexdigest()
        h2 = hashlib.sha256(т2).hexdigest()
        совпало = (с1 == с2 and h1 == h2)
        строки.append({"route": путь, "status_before": с1, "status_after": с2,
                       "sha256_before": h1, "sha256_after": h2, "identical": совпало,
                       "bytes": len(т1)})
        if not совпало:
            расхождения.append(путь)
    return {"family": family, "design_version": design, "routes": строки,
            "identical_routes": sum(1 for с in строки if с["identical"]),
            "total_routes": len(строки), "diverged": расхождения}


if __name__ == "__main__":
    итог = {"runtime_before": str(СТАРЫЙ), "runtime_after": str(НОВЫЙ),
            "families": []}
    for family, design in (("lords", "1.1.0"), ("animedia", "1.2.1"),
                           ("animedia", "1.2.0")):
        итог["families"].append(сравнить(family, design))
    итог["all_identical"] = all(not f["diverged"] for f in итог["families"])
    print(json.dumps(итог, ensure_ascii=False, indent=1))
