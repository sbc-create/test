#!/usr/bin/env python3
"""Проверенные тексты очереди — видны ли они на живых страницах.

Повод. В реестре оператора 847 записей со статусом `READY_VERIFIED`: текст
написан и проверен, `published_at` пуст. Выборка 25.10 показала, что это ДВА
разных случая, и путать их нельзя:

* `yummyani.site/anime/3x3-glaza-skazanie-seymy` — на странице ровно тот же
  текст (473 знака), то есть материал доставлен, а пустой `published_at` —
  пробел учёта;
* `animedia.space/title/ranma-1-2-ova` — на странице описания нет вовсе, а в
  очереди лежит проверенные 662 знака: это недоставленный полезный выход.

Отсюда правило инструмента: истина — ЖИВАЯ СТРАНИЦА, а не поле учёта. Снимок
подробностей поставщика для этого не годится: доставка идёт накладкой
(`editorial-overrides.json`), и «в снимке описания нет» ещё не значит, что его
нет у посетителя.

Три исхода, третий обязателен: `ВИДНО` (на странице тот же текст или текст той
же длины), `НЕ ВИДНО` (страница прочитана, описания нет или оно чужое),
`НЕ ПРОВЕРЕНО` (страница не ответила). Последнее не считается ни доставкой, ни
потерей.

    python3 automation/local/ready-verified-visibility.py [--site <домен>]
        [--limit N] [--json out.json] [--pause 0.4]
"""
from __future__ import annotations

import argparse
import collections
import json
import pathlib
import sys
import time

РЕЕСТР = pathlib.Path("/var/lib/seo-content-operator/registry.json")
#: Насколько может разойтись длина живого текста с готовым, чтобы считать его
#: тем же материалом: витрина добавляет типографику и обрезает пробелы.
ДОПУСК_ЗНАКОВ = 40


def готовые(реестр: pathlib.Path | None = None, статус: str = "READY_VERIFIED") -> list[dict]:
    try:
        д = json.loads((реестр or РЕЕСТР).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    итог = []
    for з in д.get("items") or []:
        if з.get("status") != статус:
            continue
        адрес = з.get("canonical_url") or ""
        итог.append({
            "content_id": з.get("content_id"),
            "site": з.get("target_site") or (адрес.split("/")[2] if "//" in адрес else ""),
            "slug": з.get("title_id"),
            "url": адрес,
            "знаков": len((з.get("body") or "").strip()),
            "published_at": з.get("published_at") or "",
        })
    return итог


def видно(готово: int, живое: int | None, *, допуск: int = ДОПУСК_ЗНАКОВ) -> str:
    """Исход по длине готового и живого текста."""
    if живое is None:
        return "НЕ ПРОВЕРЕНО"
    if живое == 0:
        return "НЕ ВИДНО"
    return "ВИДНО" if abs(живое - готово) <= допуск else "НЕ ВИДНО"


#: Корень фабрики: инструмент запускается из любого каталога, а читает факты
#: тем же модулем, которым их читает редактор.
КОРЕНЬ = pathlib.Path(__file__).resolve().parents[2]


def _после_перенаправления(адрес: str) -> str:
    """Конечный адрес страницы. Нужен из-за 308, которого urllib 3.10 не следует.

    Измерено 25.10: у 173 записей `READY_VERIFIED` витрины yummyani.site в
    реестре стоит UUID вместо слага, и страница `/anime/<uuid>` отвечает
    **308 Permanent Redirect** на настоящий адрес. `urllib` в Python 3.10 этот
    код не следует (поддержка добавлена в 3.11), поэтому первая сверка
    записала 173 материала в «НЕ ПРОВЕРЕНО» — и это было бы честно, но
    бесполезно: материал доставлен, адрес просто другой.
    """
    import urllib.error
    import urllib.parse
    import urllib.request
    запрос = urllib.request.Request(адрес, headers={"User-Agent": "qwen-site-tool"})
    try:
        urllib.request.urlopen(запрос, timeout=20).read(1)
        return адрес
    except urllib.error.HTTPError as ош:
        куда = (ош.headers or {}).get("Location") if ош.code in (301, 302, 307, 308) else None
        return urllib.parse.urljoin(адрес, куда) if куда else адрес
    except Exception:  # noqa: BLE001 — сеть не ответила: адрес оставляем прежним
        return адрес


def _живое(запись: dict) -> int | None:
    """Длина описания НА СТРАНИЦЕ. Снимок подробностей здесь не годится.

    `editorial.факты` для семейств со снимком (animedia, animego, lords, zona)
    читает снимок поставщика, а доставка идёт накладкой
    (`editorial-overrides.json`), которую витрина подмешивает при отдаче
    страницы. Первая редакция этого инструмента спросила `факты` и получила на
    animedia.space «12 из 12 не видно» — по снимку, где описаний не бывает
    вовсе. Поэтому читается ровно то, что видит посетитель: разметка
    schema.org страницы.
    """
    if str(КОРЕНЬ) not in sys.path:
        sys.path.insert(0, str(КОРЕНЬ))
    from factory.qwen import editorial
    try:
        с = editorial._сайт(запись["site"])
    except Exception:  # noqa: BLE001 — витрины нет в реестре
        return None
    try:
        ф = editorial._факты_со_страницы(с, запись["slug"])
        return len(str((ф.get("facts") or {}).get("description") or "").strip())
    except Exception:  # noqa: BLE001 — не прочиталось: пробуем конечный адрес
        pass
    адрес = запись.get("url") or ""
    конечный = _после_перенаправления(адрес) if адрес else ""
    if not конечный or конечный == адрес:
        return None
    слаг = конечный.rstrip("/").rsplit("/", 1)[-1]
    try:
        ф = editorial._факты_со_страницы(с, слаг)
    except Exception:  # noqa: BLE001 — и конечный адрес не дал разметки
        return None
    return len(str((ф.get("facts") or {}).get("description") or "").strip())


def сверить(записи: list[dict], *, читатель=None, пауза: float = 0.0) -> dict:
    читать = читатель or _живое
    счёт: collections.Counter = collections.Counter()
    по_сайту: dict[str, collections.Counter] = collections.defaultdict(collections.Counter)
    строки = []
    for з in записи:
        живое = читать(з)
        исход = видно(з["знаков"], живое)
        счёт[исход] += 1
        по_сайту[з["site"]][исход] += 1
        строки.append({**з, "живых_знаков": живое, "исход": исход})
        if пауза:
            time.sleep(пауза)
    return {"итог": dict(счёт), "по_сайту": {к: dict(v) for к, v in по_сайту.items()},
            "строки": строки}


def главное(аргв=None) -> int:
    р = argparse.ArgumentParser(description=__doc__)
    р.add_argument("--site", default="")
    р.add_argument("--limit", type=int, default=0)
    р.add_argument("--pause", type=float, default=0.4)
    р.add_argument("--json", type=pathlib.Path)
    а = р.parse_args(аргв)
    записи = готовые()
    if not записи:
        print("НЕ ПРОВЕРЕНО: реестр оператора не прочитан или готовых записей нет")
        return 2
    if а.site:
        записи = [з for з in записи if з["site"] == а.site]
    if а.limit:
        записи = записи[:а.limit]
    print(f"проверенных записей к сверке: {len(записи)}")
    с = сверить(записи, пауза=а.pause)
    for сайт in sorted(с["по_сайту"]):
        д = с["по_сайту"][сайт]
        print(f"  {сайт:20} видно {д.get('ВИДНО', 0):4}  НЕ ВИДНО {д.get('НЕ ВИДНО', 0):4}"
              f"  не проверено {д.get('НЕ ПРОВЕРЕНО', 0):4}")
    и = с["итог"]
    print(f"\nитог: видно {и.get('ВИДНО', 0)}, НЕ ВИДНО {и.get('НЕ ВИДНО', 0)},"
          f" не проверено {и.get('НЕ ПРОВЕРЕНО', 0)} из {len(записи)}")
    знаков = sum(з["знаков"] for з in с["строки"] if з["исход"] == "НЕ ВИДНО")
    print(f"недоставленный проверенный текст: {знаков:,} знаков"
          .replace(",", " "))
    print("«НЕ ПРОВЕРЕНО» — не доставка и не потеря: страница не ответила")
    if а.json:
        а.json.parent.mkdir(parents=True, exist_ok=True)
        а.json.write_text(json.dumps(с, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"свод записан: {а.json}")
    return 0


if __name__ == "__main__":
    sys.exit(главное())
