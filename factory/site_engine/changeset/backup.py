#!/usr/bin/env python3
"""Копия и восстановление хранилища наборов изменений.

Копия снимается через backup API sqlite3, а не `cp`: копирование файла под
активной записью даёт склейку двух состояний, в которой часть набора уже
перешла в новое состояние, а часть ещё нет.

Восстановление всегда проверяется в изоляции. Копия, которую ни разу не
разворачивали, — это предположение о копии.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sqlite3
import sys
import tempfile
from pathlib import Path

from . import store as S

КАТАЛОГ = Path(os.environ.get(
    "CHANGESET_BACKUP_DIR", "/srv/site-factory/changeset-store/backups"))

#: Копия вне хоста — контракт, а не факт: второй хост не выделен.
OFF_HOST_BACKUP = "PLANNED"

#: Верхняя отметка живёт ВНЕ базы намеренно. Храни её внутри — и старая копия
#: принесла бы вместе с собой старую отметку, то есть ровно то забвение, от
#: которого отметка и защищает.
#:
#: Путь вычисляется при каждом обращении, а не запоминается при импорте:
#: каталог копий подменяем, и отметка обязана следовать за ним — иначе
#: проверка писала бы в рабочий каталог, думая, что работает во временном.
ИМЯ_ОТМЕТКИ = "high-water.json"


def файл_отметки() -> Path:
    return КАТАЛОГ / ИМЯ_ОТМЕТКИ

#: Восстановление поверх рабочего хранилища не предусмотрено ни одним путём в
#: этом модуле. Проверка разворачивает копию только во временный каталог:
#: «восстановили и посмотрим» — это потеря того, что было.
ПРОДУКТИВНОЕ_ВОССТАНОВЛЕНИЕ = "DENIED"


def отметка_базы(c: sqlite3.Connection) -> dict[str, int]:
    """Докуда дошла история в этой базе."""
    переходы = c.execute(
        "SELECT coalesce(max(seq), 0) FROM changeset_transition").fetchone()[0]
    ящик = c.execute(
        "SELECT coalesce(max(seq), 0) FROM changeset_outbox").fetchone()[0]
    return {"transition_seq": int(переходы), "outbox_seq": int(ящик)}


def прочитать_отметку() -> dict[str, int]:
    ф = файл_отметки()
    if not ф.is_file():
        return {"transition_seq": 0, "outbox_seq": 0}
    try:
        д = json.loads(ф.read_text(encoding="utf-8"))
    except ValueError:
        # Испорченная отметка — не повод считать, что истории не было.
        return {"transition_seq": 0, "outbox_seq": 0}
    return {k: int(д.get(k) or 0) for k in ("transition_seq", "outbox_seq")}


def поднять_отметку(значения: dict[str, int]) -> dict[str, int]:
    """Отметка растёт и никогда не опускается."""
    было = прочитать_отметку()
    стало = {k: max(было.get(k, 0), int(значения.get(k) or 0)) for k in было}
    ф = файл_отметки()
    ф.parent.mkdir(parents=True, exist_ok=True)
    ф.write_text(
        json.dumps({**стало, "updated_at": S.сейчас()}, ensure_ascii=False,
                   indent=2), encoding="utf-8")
    return стало


def _версии() -> dict:
    м = Path("/srv/site-factory/control-api/release-manifest.json")
    итог = {"source_commit": None, "artifact_sha256": None}
    if м.is_file():
        try:
            d = json.loads(м.read_text(encoding="utf-8"))
            итог = {"source_commit": d.get("sha"), "artifact_sha256": d.get("digest")}
        except ValueError:
            pass
    return итог


def _слепок(c: sqlite3.Connection) -> dict:
    по_состояниям = {r["status"]: r["n"] for r in c.execute(
        "SELECT status, count(*) n FROM changeset GROUP BY status")}
    наборов = c.execute("SELECT count(*) FROM changeset").fetchone()[0]
    переходов = c.execute("SELECT count(*) FROM changeset_transition").fetchone()[0]
    целей = c.execute("SELECT count(*) FROM changeset_target").fetchone()[0]
    ящик = c.execute("SELECT count(*) FROM changeset_outbox").fetchone()[0]
    задолженность = c.execute("SELECT count(*) FROM changeset_outbox "
                              "WHERE published_at IS NULL").fetchone()[0]
    dlq = c.execute("SELECT count(*) FROM changeset_dlq").fetchone()[0]
    замки = c.execute("SELECT count(*) FROM changeset_lock").fetchone()[0]
    # Отпечаток истории решений: восстановление обязано вернуть её целиком,
    # а не «столько же строк».
    строки = [tuple(r) for r in c.execute(
        "SELECT changeset_id, action, from_status, to_status, actor_id, "
        "occurred_at FROM changeset_transition ORDER BY seq")]
    отпечаток = hashlib.sha256(
        json.dumps(строки, ensure_ascii=False, sort_keys=True).encode()).hexdigest()
    return {"changesets": наборов, "by_status": по_состояниям,
            "transitions": переходов, "targets": целей,
            "outbox": ящик, "outbox_backlog": задолженность, "dlq": dlq,
            "locks": замки, "transition_digest": отпечаток,
            "high_water": отметка_базы(c)}


def создать() -> dict:
    КАТАЛОГ.mkdir(parents=True, exist_ok=True)
    # Метка до микросекунд, а не до секунды. Прежде две копии, снятые в одну
    # секунду, получали ОДНО имя, и вторая молча затирала первую вместе с её
    # манифестом: копия, которая по всем признакам есть, на деле исчезала.
    метка = S.сейчас().replace(":", "").replace("-", "").replace(".", "")
    метка = метка.rstrip("Z")[:21]
    цель = КАТАЛОГ / f"changesets-{метка}.sqlite3"
    if цель.exists():
        # Совпадение и после микросекунд означает, что метка перестала быть
        # различающей. Молчать тут нельзя: следующим шагом идёт перезапись.
        raise FileExistsError(
            f"копия {цель.name} уже существует: метка времени не различает "
            f"две копии, и вторая затёрла бы первую")
    ист = S.открыть()
    слепок = _слепок(ист)
    наз = sqlite3.connect(цель)
    with наз:
        ист.backup(наз)
    наз.close()
    ист.close()
    сумма = hashlib.sha256(цель.read_bytes()).hexdigest()
    отметка_до = прочитать_отметку()
    отметка_после = поднять_отметку(слепок["high_water"])
    манифест = {"backup_file": цель.name, "created_at": S.сейчас(),
                "sha256": сумма, "size": цель.stat().st_size,
                "source_snapshot": слепок, "versions": _версии(),
                "off_host_backup": OFF_HOST_BACKUP,
                "high_water_before": отметка_до,
                "high_water_after": отметка_после}
    цель.with_suffix(".manifest.json").write_text(
        json.dumps(манифест, ensure_ascii=False, indent=2), encoding="utf-8")
    return манифест


def восстановить(файл: Path) -> dict:
    манифест = json.loads(файл.with_suffix(".manifest.json")
                          .read_text(encoding="utf-8"))
    сумма = hashlib.sha256(файл.read_bytes()).hexdigest()
    с_манифестом = сумма == манифест["sha256"]
    with tempfile.TemporaryDirectory(prefix="changeset-restore-") as d:
        копия = Path(d) / "restored.sqlite3"
        копия.write_bytes(файл.read_bytes())
        c = sqlite3.connect(f"file:{копия}?mode=ro", uri=True)
        c.row_factory = sqlite3.Row
        восст = _слепок(c)
        триггеры = sorted(x[0] for x in c.execute(
            "SELECT name FROM sqlite_master WHERE type='trigger'"))
        c.close()
    исх = манифест["source_snapshot"]
    расхождения = {k: [исх[k], восст[k]] for k in исх if исх[k] != восст[k]}
    # Все сторожа обязаны пережить восстановление: копия без них — обычные
    # таблицы, а не машина состояний и не история, которую нельзя переписать.
    нет_сторожей = [с for с, _ in S.СТОРОЖА if с not in триггеры]
    if "cs_no_direct_status" not in триггеры:
        нет_сторожей.append("cs_no_direct_status")

    # Отметка — единственная проверка, которая смотрит НАРУЖУ копии. Копия
    # сама по себе непротиворечива; вопрос в том, не отбрасывает ли она
    # историю, которая уже была.
    отметка_сейчас = прочитать_отметку()
    отметка_копии = восст.get("high_water") or {"transition_seq": 0,
                                                "outbox_seq": 0}
    откат_отметки = {k: [отметка_сейчас[k], отметка_копии.get(k, 0)]
                     for k in отметка_сейчас
                     if отметка_копии.get(k, 0) < отметка_сейчас[k]}

    ok = с_манифестом and not расхождения and not нет_сторожей and not откат_отметки
    итог = {"restore_verdict": "PASS" if ok else "FAIL",
            "checksum_matches_manifest": с_манифестом,
            "restored_snapshot": восст, "manifest_snapshot": исх,
            "mismatches": расхождения, "guards": триггеры,
            "missing_guards": нет_сторожей,
            "high_water_now": отметка_сейчас,
            "high_water_in_backup": отметка_копии,
            "high_water_regression": откат_отметки,
            "production_restore": ПРОДУКТИВНОЕ_ВОССТАНОВЛЕНИЕ,
            "versions": манифест.get("versions", {}),
            "off_host_backup": OFF_HOST_BACKUP}
    if откат_отметки:
        итог["failure_reason"] = (
            "копия старше уже записанной истории: восстановление из неё "
            "потеряло бы переходы, которые уже произошли")
    return итог


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="копия хранилища наборов")
    ap.add_argument("режим", choices=["create", "restore", "cycle"])
    ap.add_argument("--file")
    a = ap.parse_args(argv)
    м = None
    if a.режим in ("create", "cycle"):
        м = создать()
        print("копия:", json.dumps(м, ensure_ascii=False, indent=2))
    if a.режим in ("restore", "cycle"):
        f = Path(a.file) if a.file else КАТАЛОГ / м["backup_file"]
        r = восстановить(f)
        print("восстановление:", json.dumps(r, ensure_ascii=False, indent=2))
        return 0 if r["restore_verdict"] == "PASS" else 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
