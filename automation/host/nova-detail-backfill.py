#!/usr/bin/env python3
"""Добор подробностей каталога из detail API CDNVideoHub.

Зачем отдельный инструмент
--------------------------

Обогащение живёт внутри сборки сайта и ограничено бюджетом в 300–400 запросов
за прогон: полный каталог за раз — это десятки тысяч запросов подряд, и для
пятнадцатиминутного цикла это отказ источника, а не обогащение.

Но у бюджета есть следствие, которое видно только на длинной дистанции: при
400 записях в сутки каталог из 53 390 записей набирает покрытие сто тридцать
дней. Описание, жанры, страны и состав сезонов до страниц всё это время не
доходят — не потому, что источник их не отдаёт, а потому, что их не успели
спросить.

Этот инструмент закрывает разрыв один раз: он проходит весь каталог с
ограничением частоты, складывает ответы в тот же кэш и после этого суточному
циклу остаётся только приращение.

Чего он не делает
-----------------

Не трогает каталог витрин, шаблоны, плеер и оценки. Пишет только в кэш
подробностей; публикация — отдельный шаг, и запускается она явно.

Оценок тут ждать не следует. Detail отдаёт те же `kinopoisk_rating` и
`imdb_rating`, что и список: на выборке в 3 000 записей detail добавил одну
оценку Кинопоиска и одну IMDb. Инструмент добирает описания и метаданные, а
не рейтинги, и обещать обратное значило бы объяснять невыполнимый порог
незавершённой работой.
"""
from __future__ import annotations

import argparse
import fcntl
import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from factory.lords import content_live, detail_enrichment  # noqa: E402

СНИМОК = Path("/srv/site-factory/repo/var/lords/lords/catalog-cache/lords-01.json")
КЭШ = Path("/srv/site-factory/repo/var/lords/detail-cache")
ОТЧЁТ = Path("/srv/site-factory/repo/var/lords/detail-backfill-report.json")
ЗАМОК = Path("/srv/site-factory/repo/var/lords/nova-detail-backfill.lock")


def токен() -> str:
    """Токен из systemd credential. В окружении и журнале его нет.

    Значение не печатается и не возвращается наружу ни при каких условиях:
    единственный его потребитель — Fetcher.
    """
    каталог = os.environ.get("CREDENTIALS_DIRECTORY")
    имя = os.environ.get("CDNVIDEOHUB_API_TOKEN_CREDENTIAL", "cdnvideohub_api_token")
    if not каталог:
        raise SystemExit("нет CREDENTIALS_DIRECTORY: запускать через systemd с LoadCredential")
    путь = Path(каталог) / имя
    if not путь.is_file():
        raise SystemExit(f"credential {имя} не передан")
    return путь.read_text(encoding="utf-8").strip()


def покрытие_кэша(идентификаторы: list[str], кэш: Path) -> dict:
    есть = сописанием = 0
    for ид in идентификаторы:
        п = кэш / f"{ид}.json"
        if not п.is_file():
            continue
        есть += 1
        try:
            д = json.loads(п.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        текст = ((д.get("detail") or {}).get("description") or "").strip()
        if len(текст) >= 40:
            сописанием += 1
    всего = len(идентификаторы) or 1
    return {"titles": len(идентификаторы), "cached": есть,
            "cached_pct": round(есть * 100 / всего, 2),
            "with_description": сописанием,
            "description_pct": round(сописанием * 100 / всего, 2)}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="добор подробностей каталога")
    ap.add_argument("--snapshot", type=Path, default=СНИМОК)
    ap.add_argument("--cache", type=Path, default=КЭШ)
    ap.add_argument("--budget", type=int, default=2000,
                    help="предел сетевых запросов за прогон")
    ap.add_argument("--report", type=Path, default=ОТЧЁТ)
    ap.add_argument("--order", choices=("uncached-first", "catalog"),
                    default="uncached-first",
                    help="кого спрашивать первым")
    a = ap.parse_args(argv)

    # Один добор за раз. Два процесса, идущих по одному кэшу, тратят бюджет
    # источника на одни и те же записи и мешают друг другу считать покрытие.
    ЗАМОК.parent.mkdir(parents=True, exist_ok=True)
    замок = open(ЗАМОК, "w")
    try:
        fcntl.flock(замок, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        print(json.dumps({"status": "SKIPPED_LOCKED",
                          "detail": f"другой добор уже идёт ({ЗАМОК})"},
                         ensure_ascii=False))
        return 0

    начало = time.time()
    записи = json.loads(a.snapshot.read_text(encoding="utf-8")).get("items") or []
    идентификаторы = [str(з["external_id"]) for з in записи if з.get("external_id")]
    до = покрытие_кэша(идентификаторы, a.cache)

    contract = content_live.load_live_contract()
    fetcher = content_live.Fetcher(contract=contract, token=токен())
    cache = detail_enrichment.DetailCache(a.cache)

    # Порядок решает, что вырастет за прогон. По умолчанию модуль идёт по
    # каталогу, и устаревшая запись съедает запрос наравне с той, которой в
    # кэше нет вовсе. На каталоге, где кэш покрывает треть, это значит, что
    # бюджет уходит на обновление уже известного, а покрытие стоит на месте:
    # замер показал 2 069 обновлённых записей и ноль новых за полчаса.
    #
    # Поэтому сначала спрашиваются те, кого в кэше нет. Обновление устаревшего
    # никуда не девается — оно идёт следом, когда добирать уже нечего.
    порядок = None
    if a.order == "uncached-first":
        нет_в_кэше, есть_в_кэше = [], []
        for ид in идентификаторы:
            (есть_в_кэше if (a.cache / f"{ид}.json").is_file() else нет_в_кэше).append(ид)
        порядок = нет_в_кэше + есть_в_кэше
        print(f"[порядок] нет в кэше: {len(нет_в_кэше)}, обновление: {len(есть_в_кэше)}",
              file=sys.stderr)

    _, отчёт = detail_enrichment.enrich_items(
        записи, fetcher=fetcher, contract=contract, cache=cache,
        budget=a.budget, order=порядок)

    после = покрытие_кэша(идентификаторы, a.cache)
    итог = {
        "started_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(начало)),
        "finished_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "duration_sec": round(time.time() - начало, 1),
        "budget": a.budget,
        "requests_made": getattr(fetcher, "requests_made", None),
        "retries_made": getattr(fetcher, "retries_made", None),
        "enrichment": {k: v for k, v in vars(отчёт).items()
                       if isinstance(v, (int, float, str))},
        "before": до,
        "after": после,
        "gained_cached": после["cached"] - до["cached"],
        "gained_description": после["with_description"] - до["with_description"],
    }
    a.report.parent.mkdir(parents=True, exist_ok=True)
    a.report.write_text(json.dumps(итог, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(итог, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
