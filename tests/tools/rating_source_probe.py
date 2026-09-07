"""Ответ на HANDOFF-043 §6: исчерпан ли источник оценок или теряет проекция.

Полоса TEMPLATES попросила сторону с доступом сделать ровно одно измерение:
спросить у поставщика его собственный счёт записей с оценкой и сравнить с
19 575, которые видит наш кэш. Совпадение означает, что источник исчерпан;
расхождение — что теряет проекция, и тогда это дефект, а не предел.

Запросов ровно столько, сколько нужно для счёта: `with_count=true&limit=1`
возвращает `total`, не выкачивая каталог. Ответы 401, 403 и 429 останавливают
измерение с указанием причины и не обходятся.

Токен читается из файла секрета и никуда не печатается.
"""
from __future__ import annotations

import json
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

sys.path.insert(0, "/home/claude/wt-prod-25")

import yaml

СЕКРЕТ = Path("/etc/site-factory/secrets/lords/lords-01/cdnvideohub-api-token")
КОНТРАКТ = Path("/home/claude/wt-prod-25/knowledge/cdnvideohub/content-api.yaml")

контракт = yaml.safe_load(КОНТРАКТ.read_text(encoding="utf-8"))
источник = контракт.get("source") or контракт
база = str(источник.get("base_url") or контракт.get("base_url") or "").rstrip("/")
if not база:
    print("BLOCKED_INPUT: в контракте нет base_url")
    raise SystemExit(2)

заголовок = str(контракт.get("auth", {}).get("header")
                or источник.get("auth_header") or "Authorization")
префикс = str(контракт.get("auth", {}).get("prefix")
              or контракт.get("auth", {}).get("value_prefix") or "Bearer ")
токен = СЕКРЕТ.read_text(encoding="utf-8").strip()


def счёт(параметры: dict[str, str]) -> tuple[int | None, str]:
    """Число записей по фильтру. Возвращает счёт и объяснение, если его нет."""
    запрос = dict(параметры)
    запрос.update({"with_count": "true", "limit": "1"})
    адрес = f"{база}/titles?{urllib.parse.urlencode(запрос)}"
    req = urllib.request.Request(адрес, method="GET")
    req.add_header(заголовок, f"{префикс}{токен}")
    req.add_header("Accept", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=30) as ответ:
            тело = json.loads(ответ.read().decode("utf-8"))
    except urllib.error.HTTPError as ошибка:
        # 401, 403 и 429 — это ответ источника, а не повод пробовать иначе.
        return None, f"источник ответил {ошибка.code}: измерение остановлено"
    except (urllib.error.URLError, ValueError, OSError) as ошибка:
        return None, f"запрос не выполнен: {type(ошибка).__name__}"
    итого = тело.get("total")
    if итого is None:
        return None, "в ответе нет поля total — счёт источником не объявлен"
    return int(итого), ""


измерения = [
    ("весь каталог", {}),
    ("оценка >= 0", {"rating_from": "0"}),
    ("оценка >= 1", {"rating_from": "1"}),
]
итог: dict[str, object] = {}
for имя, параметры in измерения:
    значение, причина = счёт(параметры)
    итог[имя] = значение if значение is not None else причина
    print(f"{имя:16} {итог[имя]}")
    if значение is None:
        break

print("\nнаш кэш, снимок 2026-09-07:")
print("  записей всего              53257")
print("  с оценкой Кинопоиска       19575")
print("  с оценкой IMDb             27003")
print("  хоть с какой-то оценкой    — считается ниже")

каталог = json.loads(
    Path("/srv/site-factory/repo/var/lords/lords/catalog-cache/lords-01.json")
    .read_text(encoding="utf-8"))
записи = каталог["items"] if isinstance(каталог, dict) else каталог
любая = sum(1 for з in записи
            if з.get("kinopoisk_rating") is not None or з.get("imdb_rating") is not None)
print(f"  хоть с какой-то оценкой    {любая}")
