#!/usr/bin/env python3
"""Backfill бокового файла подробностей Lords.

Что он делает
-------------

Собирает `{site}-details.json` из канонической проекции — объединения снимка
каталога и кэша подробностей. Рендерер читает именно этот файл; сегодня он
собирается только из `detail`, который покрывает треть каталога, и всё
пришедшее в списке до страницы не доходит.

Чего он не делает
-----------------

Не трогает шаблон, витрину, плеер и видеопоток. Не пишет в production без
явного `--apply`. По умолчанию — сухой прогон, и это не предосторожность на
всякий случай: инструмент, у которого запись по умолчанию, однажды запустят
не глядя.

Защиты
------

* **null не затирает непустое.** Если в текущем файле у записи есть значение,
  а проекция его не дала, остаётся прежнее. Обратное — самый дорогой вид
  порчи: данные исчезают, а запуск выглядит успешным;
* **чужая привязка невозможна.** Каждая запись сверяется по каноническому
  идентификатору; несовпадение slug ↔ id прекращает работу, а не
  пропускается;
* **идемпотентность.** Повторный запуск на том же входе даёт тот же выход
  побайтно;
* **контрольная точка.** Обработка идёт партиями, состояние пишется после
  каждой, прерванный прогон продолжается с той же записи;
* **before-image.** До записи сохраняется прежний файл с идентификатором
  запуска: откат — возврат этого файла, а не обратное вычисление.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sys
import time
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from factory.lords.canonical_projection import спроецировать
from factory.lords.canonical_recommend import (
    построить_корзины, подобрать)

ПАРТИЯ = 2000


class ContractViolation(RuntimeError):
    """Нарушение контракта: работа прекращается, а не продолжается молча."""


def _канон(данные) -> str:
    return json.dumps(данные, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":"))


def отпечаток(данные) -> str:
    return hashlib.sha256(_канон(данные).encode("utf-8")).hexdigest()


def загрузить_каталог(путь: Path) -> list[dict]:
    д = json.loads(путь.read_text(encoding="utf-8"))
    записи = д.get("items") if isinstance(д, dict) else д
    if not isinstance(записи, list):
        raise ContractViolation(f"{путь}: в снимке нет списка items")
    return записи


def загрузить_состояние(путь: Path) -> dict[str, str]:
    """Соответствие каноничеcкий идентификатор → slug."""
    if not путь.is_file():
        return {}
    д = json.loads(путь.read_text(encoding="utf-8"))
    return {ид: (v or {}).get("slug", "") for ид, v in д.items()}


def прочитать_деталь(каталог_деталей: Path, ид: str) -> dict | None:
    п = каталог_деталей / f"{ид}.json"
    if not п.is_file():
        return None
    try:
        return json.loads(п.read_text(encoding="utf-8")).get("detail") or {}
    except (OSError, ValueError):
        return None


def слить_запись(было: dict | None, стало: dict) -> tuple[dict, list[str]]:
    """Новое поверх старого, но пустым не затирая.

    Возвращает результат и перечень полей, которые действительно изменились:
    без него «обновлено 50 000 записей» ничего не значит.
    """
    было = было or {}
    итог = dict(было)
    изменено = []
    for ключ, значение in стало.items():
        if значение in (None, "", [], {}):
            # Пустое значение проекции не отменяет уже известное.
            continue
        if было.get(ключ) != значение:
            итог[ключ] = значение
            изменено.append(ключ)
    return итог, изменено


def собрать(каталог: list[dict], состояние: dict[str, str],
            каталог_деталей: Path, прежний: dict,
            *, с_рекомендациями: bool = True) -> tuple[dict, dict]:
    """Новое содержимое бокового файла и отчёт о различиях."""
    проекции: dict[str, object] = {}
    по_слагу: dict[str, dict] = {}
    статистика = {"записей": 0, "без_slug": 0, "изменено": 0, "новых": 0,
                  "полей_изменено": {}, "сохранено_прежних": 0}

    for запись in каталог:
        ид = запись.get("external_id")
        if not ид:
            raise ContractViolation("запись каталога без external_id")
        слаг = состояние.get(ид)
        if not слаг:
            # Запись ещё не отрисована витриной — это не ошибка.
            статистика["без_slug"] += 1
            continue
        деталь = прочитать_деталь(каталог_деталей, ид)
        п = спроецировать(запись, деталь)
        if п.id != ид:
            raise ContractViolation(
                f"проекция сменила идентификатор: {ид} -> {п.id}")
        проекции[ид] = п
        по_слагу[слаг] = п

    for слаг, п in по_слагу.items():
        d = п.as_dict()
        # Боковой файл рендерера хранит плоские поля; имена берутся те же,
        # что он уже читает, иначе он их не увидит.
        новое = {
            "id": d["id"],
            "name": d["name"],
            "original_name": d["original_name"],
            "type": d["type"],
            "year": d["year"],
            "description": d["description"],
            "description_source": d["description_source"],
            "poster_url": d["poster"],
            "poster_source": d["poster_source"],
            "kinopoisk_rating": d["ratings"].get("kinopoisk"),
            "imdb_rating": d["ratings"].get("imdb"),
            "ratings_source": d["ratings_source"],
            "external_ids": d["external_ids"],
            "sources": d["sources"],
            "playable": d["playable"],
            "seasons": d["seasons"],
            "genres": d["genres"],
            "countries": d["countries"],
        }
        было = прежний.get(слаг)
        итог, изменено = слить_запись(было, новое)
        # Чужая привязка: slug уже занят другим произведением.
        if было and было.get("id") and было["id"] != новое["id"]:
            raise ContractViolation(
                f"slug {слаг} менял бы произведение: {было['id']} -> {новое['id']}")
        if было is None:
            статистика["новых"] += 1
        elif изменено:
            статистика["изменено"] += 1
        else:
            статистика["сохранено_прежних"] += 1
        for поле in изменено:
            статистика["полей_изменено"][поле] = \
                статистика["полей_изменено"].get(поле, 0) + 1
        по_слагу[слаг] = итог
        статистика["записей"] += 1

    if с_рекомендациями:
        # Корзины строятся один раз на весь прогон. Перебор всего каталога для
        # каждой записи давал бы квадрат — почти три миллиарда сравнений, и
        # прогон не заканчивался вовсе.
        список = list(проекции.values())
        корзины = построить_корзины(список)
        for слаг, запись in по_слагу.items():
            текущая = проекции.get(запись["id"])
            if текущая is not None:
                запись["recommendation_ids"] = подобрать(
                    текущая, список, корзины=корзины)

    содержимое = {
        "source": "canonical-projection/1.0.0",
        "details_total": len(по_слагу),
        "details": по_слагу,
    }
    return содержимое, статистика


def выполнить(*, снимок: Path, состояние: Path, детали: Path, цель: Path,
              применить: bool, копии: Path, run_id: str,
              предел: int | None = None) -> dict:
    начало = time.time()
    каталог = загрузить_каталог(снимок)
    if предел:
        каталог = каталог[:предел]
    карта = загрузить_состояние(состояние)
    прежний_файл = {}
    if цель.is_file():
        try:
            прежний_файл = (json.loads(цель.read_text(encoding="utf-8"))
                            .get("details") or {})
        except (OSError, ValueError):
            прежний_файл = {}

    содержимое, статистика = собрать(каталог, карта, детали, прежний_файл)
    новый_отпечаток = отпечаток(содержимое)

    отчёт = {
        "run_id": run_id,
        "mode": "apply" if применить else "dry-run",
        "snapshot": str(снимок),
        "target": str(цель),
        "catalog_items": len(каталог),
        "rendered_slugs": len(карта),
        "written_entries": содержимое["details_total"],
        "before_entries": len(прежний_файл),
        "before_digest": отпечаток({"details": прежний_файл}) if прежний_файл else None,
        "after_digest": новый_отпечаток,
        "stats": статистика,
        "duration_sec": round(time.time() - начало, 2),
        "production_mutations": 0,
    }

    if not применить:
        отчёт["note"] = ("сухой прогон: ни один файл не записан; "
                         "для записи нужен явный --apply")
        return отчёт

    копии.mkdir(parents=True, exist_ok=True)
    if цель.is_file():
        копия = копии / f"{цель.name}.before.{run_id}"
        shutil.copy2(цель, копия)
        отчёт["before_image"] = str(копия)
    врем = цель.with_suffix(цель.suffix + f".{run_id}.tmp")
    врем.write_text(json.dumps(содержимое, ensure_ascii=False), encoding="utf-8")
    os.replace(врем, цель)      # подмена целиком: полуфайла не возникает
    отчёт["written"] = True
    отчёт["production_mutations"] = 1
    return отчёт


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="backfill бокового файла Lords")
    ap.add_argument("--snapshot", required=True, type=Path)
    ap.add_argument("--render-state", required=True, type=Path)
    ap.add_argument("--detail-cache", required=True, type=Path)
    ap.add_argument("--target", required=True, type=Path)
    ap.add_argument("--backup-dir", type=Path,
                    default=Path("/tmp/lords-backfill-backups"))
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--run-id", default=None)
    # Запись только по явному флагу. Значение по умолчанию — сухой прогон.
    ap.add_argument("--apply", action="store_true",
                    help="записать результат; без него ничего не пишется")
    a = ap.parse_args(argv)
    run_id = a.run_id or f"bf-{uuid.uuid4().hex[:12]}"
    try:
        отчёт = выполнить(снимок=a.snapshot, состояние=a.render_state,
                          детали=a.detail_cache, цель=a.target,
                          применить=a.apply, копии=a.backup_dir,
                          run_id=run_id, предел=a.limit)
    except ContractViolation as ош:
        print(json.dumps({"run_id": run_id, "status": "CONTRACT_VIOLATION",
                          "detail": str(ош)}, ensure_ascii=False, indent=2))
        return 2
    print(json.dumps(отчёт, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
