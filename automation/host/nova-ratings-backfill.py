#!/usr/bin/env python3
"""Добор оценок из внешних источников в хранилище витрин Nova.

Почему добор и публикация разделены
-----------------------------------

Добор ходит в источники и складывает результат в хранилище по каноническому
идентификатору. Публикация берёт из хранилища готовое и в сеть не ходит.

Иначе каждая пересборка витрины означала бы новый обход внешних источников, а
временный отказ любого из них — исчезновение оценок с публичных страниц. Так
отказ источника стоит ровно одного непополненного прогона, а не витрины без
оценок.

Что делает
----------

Спрашивает только то, чего не хватает: записи, у которых уже есть оценка от
основного поставщика, не тревожат внешние источники вовсе. Соединение идёт по
стабильному внешнему идентификатору, для Shikimori совпадение дополнительно
проверяется названием.

Чего не делает
--------------

Не пишет в витрину. Не занимает чужое поле: оценка Shikimori не станет
оценкой IMDb. Не считает ноль оценкой. Не выдумывает значений: чего источник
не дал, того в хранилище не появится.
"""
from __future__ import annotations

import argparse
import fcntl
import json
import os
import sys
import time
import unicodedata
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from factory.lords import rating_gateway as rg          # noqa: E402
from factory.lords import rating_sources as rs          # noqa: E402

ВАР = Path("/srv/site-factory/repo/var/lords")
СНИМОК = ВАР / "lords" / "catalog-cache" / "lords-01.json"
ХРАНИЛИЩЕ = ВАР / "ratings-store.json"
КАРАНТИН = ВАР / "ratings-quarantine.json"
ДАТАСЕТ = ВАР / "rating-sources" / "title.ratings.tsv.gz"
ОТЧЁТ = ВАР / "ratings-backfill-report.json"
ЗАМОК = ВАР / "nova-ratings-backfill.lock"

#: Насколько названия должны совпасть, чтобы соответствие считалось
#: подтверждённым. Полное равенство требовать нельзя: «Ван-Пис» и «Любовный
#: Ван-Пис» — разные произведения, а «Наруто» и «НАРУТО» — одно.
ПОРОГ_СХОДСТВА = 0.34


def _нормализовать(текст: str) -> set:
    текст = unicodedata.normalize("NFKD", (текст or "").lower())
    очищено = "".join(с if с.isalnum() else " " for с in текст)
    return {с for с in очищено.split() if len(с) > 2}


def названия_похожи(а: str, б: str) -> bool:
    """Подтверждение соответствия вторым признаком, а не основанием для него.

    Основание — совпадение стабильного идентификатора. Название проверяется
    затем: идентификатор совпал, а произведение другое — ровно тот случай,
    ради которого проверка и нужна.
    """
    на, нб = _нормализовать(а), _нормализовать(б)
    if not на or not нб:
        # Сравнивать не с чем. Отвергать на этом основании нельзя: отсутствие
        # названия у одной из сторон — не признак чужой сущности.
        return True
    общие = на & нб
    return bool(общие) and len(общие) / min(len(на), len(нб)) >= ПОРОГ_СХОДСТВА


def оценка_есть(значение) -> bool:
    try:
        ч = float(значение)
    except (TypeError, ValueError):
        return False
    return 0.0 < ч <= 10.0


def загрузить(путь: Path, умолчание):
    if not путь.is_file():
        return умолчание
    try:
        return json.loads(путь.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return умолчание


def записать_атомарно(путь: Path, данные) -> None:
    путь.parent.mkdir(parents=True, exist_ok=True)
    врем = путь.with_suffix(путь.suffix + f".{os.getpid()}.tmp")
    врем.write_text(json.dumps(данные, ensure_ascii=False, sort_keys=True),
                    encoding="utf-8")
    os.replace(врем, путь)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="добор оценок из внешних источников")
    ap.add_argument("--snapshot", type=Path, default=СНИМОК)
    ap.add_argument("--store", type=Path, default=ХРАНИЛИЩЕ)
    ap.add_argument("--dataset", type=Path, default=ДАТАСЕТ)
    ap.add_argument("--report", type=Path, default=ОТЧЁТ)
    ap.add_argument("--quarantine", type=Path, default=КАРАНТИН)
    ap.add_argument("--refresh-dataset", action="store_true",
                    help="скачать свежую выгрузку IMDb")
    ap.add_argument("--shikimori-limit", type=int, default=None,
                    help="предел идентификаторов за прогон")
    ap.add_argument("--only", choices=("imdb", "shikimori"), default=None)
    a = ap.parse_args(argv)

    ЗАМОК.parent.mkdir(parents=True, exist_ok=True)
    замок = open(ЗАМОК, "w")
    try:
        fcntl.flock(замок, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        print(json.dumps({"status": "SKIPPED_LOCKED"}, ensure_ascii=False))
        return 0

    начало = time.time()
    записи = json.loads(a.snapshot.read_text(encoding="utf-8"))["items"]
    по_ид = {str(з["external_id"]): з for з in записи if з.get("external_id")}
    хранилище = загрузить(a.store, {})
    карантин = загрузить(a.quarantine, {"entries": []})
    всего = len(по_ид)

    def покрыто(ид: str) -> bool:
        з = по_ид[ид]
        if оценка_есть(з.get("kinopoisk_rating")) or оценка_есть(з.get("imdb_rating")):
            return True
        for о in (хранилище.get(ид) or {}).values():
            if оценка_есть(о.get("value_on_ten", о.get("value"))):
                return True
        return False

    до = sum(1 for ид in по_ид if покрыто(ид))
    отчёт = {"run_id": time.strftime("rb-%Y%m%dT%H%M%SZ", time.gmtime()),
             "started_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(начало)),
             "catalog_total": всего,
             "coverage_before": {"count": до, "pct": round(до * 100 / всего, 2)},
             "sources": {}, "providers": []}

    # ---------------------------------------------------------- IMDb
    if a.only in (None, "imdb"):
        сведения = {}
        if a.refresh_dataset or not a.dataset.is_file():
            сведения = rs.ИсточникIMDb.скачать(a.dataset)
        источник = rs.ИсточникIMDb(путь=a.dataset).загрузить()
        отчёт["providers"].append(источник.имя)
        нужны = {}
        нет_ид = 0
        for ид, з in по_ид.items():
            if покрыто(ид):
                continue
            сырое = (з.get("external_ids") or {}).get("imdb")
            if not сырое:
                нет_ид += 1
                continue
            нужны.setdefault(str(сырое), []).append(ид)
        ответ = источник.оценки(sorted(нужны))
        добавлено = отклонено = 0
        for ключ, оценки in ответ.items():
            for о in оценки:
                причина = rg.проверить_значение(о)
                if причина:
                    отклонено += 1
                    карантин["entries"].append(
                        {"source": о.source, "external_id": ключ,
                         "reason": причина, "value": о.value})
                    continue
                for ид in нужны[ключ]:
                    хранилище.setdefault(ид, {})[о.source] = {
                        **о.as_dict(), "value_on_ten": round(float(о.value), 2),
                        "canonical_title_id": ид,
                        "match_state": "external_id_exact"}
                    добавлено += 1
        отчёт["sources"][rs.ИСТОЧНИК_IMDB] = {
            "provider": источник.имя, "dataset": сведения or {"path": str(a.dataset)},
            "dataset_rows": источник.загружено_строк,
            "fetched": len(нужны), "matched": len(ответ),
            "ratings_added": добавлено, "rejected": отклонено,
            "missing_external_id": нет_ид,
            "provider_errors": 0,
            "license_note": источник.лицензия}

    # ------------------------------------------------------ Shikimori
    if a.only in (None, "shikimori"):
        источник = rs.ИсточникShikimori()
        отчёт["providers"].append(источник.имя)
        нужны = {}
        нет_ид = 0
        for ид, з in по_ид.items():
            if покрыто(ид):
                continue
            сырое = (з.get("external_ids") or {}).get("myanimelist")
            if not сырое:
                нет_ид += 1
                continue
            нужны.setdefault(str(сырое), []).append(ид)
        ключи = sorted(нужны)
        if a.shikimori_limit:
            ключи = ключи[:a.shikimori_limit]
        ответ = источник.оценки(ключи)
        добавлено = отклонено = чужие = 0
        for ключ, оценки in ответ.items():
            for о in оценки:
                причина = rg.проверить_значение(о)
                if причина:
                    отклонено += 1
                    карантин["entries"].append(
                        {"source": о.source, "external_id": ключ,
                         "reason": причина, "value": о.value})
                    continue
                название_источника = источник.названия.get(ключ, "")
                for ид in нужны[ключ]:
                    наше = по_ид[ид].get("name") or ""
                    if название_источника and not названия_похожи(наше, название_источника):
                        чужие += 1
                        карантин["entries"].append(
                            {"source": о.source, "external_id": ключ,
                             "canonical_title_id": ид, "reason": rg.ЧУЖОЙ_ИД,
                             "our_title": наше, "source_title": название_источника})
                        continue
                    хранилище.setdefault(ид, {})[о.source] = {
                        **о.as_dict(), "value_on_ten": round(float(о.value), 2),
                        "canonical_title_id": ид,
                        "source_title": название_источника,
                        "match_state": "external_id_exact+title_verified"}
                    добавлено += 1
        отчёт["sources"][rs.ИСТОЧНИК_SHIKIMORI] = {
            "provider": источник.имя, "endpoint": источник.база,
            "requests": источник.запросов, "provider_errors": источник.ошибок,
            "fetched": len(ключи), "matched": len(ответ),
            "ratings_added": добавлено, "rejected": отклонено,
            "quarantined_wrong_entity": чужие,
            "missing_external_id": нет_ид}

    после = sum(1 for ид in по_ид if покрыто(ид))
    отчёт["coverage_after"] = {"count": после, "pct": round(после * 100 / всего, 2)}
    отчёт["store_entries"] = len(хранилище)
    отчёт["quarantined_total"] = len(карантин["entries"])
    отчёт["completed_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    отчёт["duration_sec"] = round(time.time() - начало, 1)

    if not отчёт["providers"]:
        отчёт["status"] = "NO_PROVIDERS"
        print(json.dumps(отчёт, ensure_ascii=False, indent=2))
        return 1

    записать_атомарно(a.store, хранилище)
    карантин["entries"] = карантин["entries"][-5000:]
    записать_атомарно(a.quarantine, карантин)
    записать_атомарно(a.report, отчёт)
    fcntl.flock(замок, fcntl.LOCK_UN)
    print(json.dumps(отчёт, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
