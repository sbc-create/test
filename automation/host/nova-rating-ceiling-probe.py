#!/usr/bin/env python3
"""Проверка потолка оценок у источника на свежих ответах, а не на кэше.

Вопрос, на который отвечает этот прогон, один: отдаёт ли detail-эндпоинт
оценку там, где её нет в списке. Ответ по кэшу уже был получен, но кэш собран
раньше и мог устареть; утверждать по нему «источник не отдаёт» — значит
выдавать давность за отсутствие.

Поэтому выборка берётся адресно: записи, у которых внешний идентификатор
Кинопоиска (или IMDb) ЕСТЬ, а оценки в списке НЕТ. Если источник где-то
держит оценки отдельно от списка, они обязаны найтись именно здесь.
"""
from __future__ import annotations

import json, os, random, sys, time
from pathlib import Path

sys.path.insert(0, "/srv/site-factory/repo")
from factory.lords import content_live

СНИМОК = Path("/srv/site-factory/repo/var/lords/lords/catalog-cache/lords-01.json")
ОТЧЁТ = Path("/srv/site-factory/repo/var/lords/rating-ceiling-probe.json")


def токен() -> str:
    к = os.environ.get("CREDENTIALS_DIRECTORY")
    и = os.environ.get("CDNVIDEOHUB_API_TOKEN_CREDENTIAL", "cdnvideohub_api_token")
    if not к:
        raise SystemExit("нет CREDENTIALS_DIRECTORY")
    return (Path(к) / и).read_text(encoding="utf-8").strip()


def оценка(v):
    try:
        x = float(v)
    except (TypeError, ValueError):
        return False
    return 0.0 < x <= 10.0


def main() -> int:
    размер = int(sys.argv[1]) if len(sys.argv) > 1 else 300
    записи = json.loads(СНИМОК.read_text(encoding="utf-8"))["items"]
    contract = content_live.load_live_contract()
    fetcher = content_live.Fetcher(contract=contract, token=токен())

    # Три отдельные группы: у каждой свой вопрос к источнику.
    группы = {
        "kp_id_no_kp_rating": [z for z in записи
                               if (z.get("external_ids") or {}).get("kinopoisk")
                               and not оценка(z.get("kinopoisk_rating"))],
        "imdb_id_no_imdb_rating": [z for z in записи
                                   if (z.get("external_ids") or {}).get("imdb")
                                   and not оценка(z.get("imdb_rating"))],
        "no_external_id_at_all": [z for z in записи
                                  if not (z.get("external_ids") or {})],
    }
    random.seed(1404)
    итог = {"snapshot_items": len(записи), "sample_per_group": размер, "groups": {}}
    все_ключи: set[str] = set()
    пример = None

    for имя, пул in группы.items():
        выборка = random.sample(пул, min(размер, len(пул)))
        добыто_кп = добыто_имдб = ошибок = 0
        for z in выборка:
            ид = str(z["external_id"])
            try:
                d = fetcher.get_json(contract.url("title_detail", id=ид))
            except Exception:
                ошибок += 1
                continue
            if пример is None:
                пример = sorted(d.keys())
            все_ключи |= set(d.keys())
            if оценка(d.get("kinopoisk_rating")) and not оценка(z.get("kinopoisk_rating")):
                добыто_кп += 1
            if оценка(d.get("imdb_rating")) and not оценка(z.get("imdb_rating")):
                добыто_имдб += 1
        итог["groups"][имя] = {
            "population": len(пул),
            "sampled": len(выборка),
            "detail_yielded_kp": добыто_кп,
            "detail_yielded_imdb": добыто_имдб,
            "errors": ошибок,
            "yield_pct_kp": round(добыто_кп * 100 / max(len(выборка), 1), 2),
            "yield_pct_imdb": round(добыто_имдб * 100 / max(len(выборка), 1), 2),
        }
        print(f"{имя}: population={len(пул)} sampled={len(выборка)} "
              f"+kp={добыто_кп} +imdb={добыто_имдб} errors={ошибок}", flush=True)

    итог["detail_response_fields"] = sorted(все_ключи)
    итог["rating_fields_present"] = sorted(
        k for k in все_ключи if "rat" in k.lower() or "score" in k.lower()
        or "vote" in k.lower())
    итог["requests_made"] = fetcher.requests_made
    итог["retries_made"] = fetcher.retries_made
    итог["checked_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    ОТЧЁТ.write_text(json.dumps(итог, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(итог, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
