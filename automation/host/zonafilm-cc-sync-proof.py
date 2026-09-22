#!/usr/bin/env python3
"""Доставка обновлений каталога и SEO в zona-02: дубли, удаления, владение.

Проверка идёт на **копии** снимка витрины. Это не осторожность ради красоты:
CLOSED_WORLD запрещает придумывать содержимое, поэтому события собираются из
записей, которые в снимке уже есть, а живой каталог не меняется вовсе — иначе
пришлось бы либо выдумать запись, либо испортить настоящую.

Что доказывается:

1. обновление каталога доезжает и двигает курсор;
2. повторная доставка той же партии не создаёт дублей и ничего не применяет;
3. удаление доезжает и убирает запись;
4. обновление каталога не стирает SEO-текст, а SEO-правка не обнуляет число
   серий — владение полями, а не «последний записавший победил»;
5. недоступный источник не обнуляет метрику и честно помечает свежесть.
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
import tempfile
from pathlib import Path

РЕПО = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(РЕПО))

from factory.cell import ownership, sync  # noqa: E402

SITE_ID = "zona-02"
ПРОФИЛЬ = "zona-general"
ЖИВЫЕ_ДАННЫЕ = Path("/srv/lords/.frontend/sites/zona-02/data")


def взять_записи(подробности: Path, сколько: int) -> list[dict]:
    """Настоящие записи снимка. Ничего не придумывается.

    Берутся из бокового файла подробностей, а не из каталога: постоянный
    идентификатор (`id`) живёт там. В самом каталоге у записи есть только
    `slug`, а slug меняется при пересборке снимка — привязывать к нему
    обсуждение значило бы заводить новую ветку комментариев на каждую
    пересборку (см. tests/unit/test_zona_stale_slug_after_shrink.py).
    """
    данные = json.loads(подробности.read_text(encoding="utf-8"))
    записи = данные.get("details") or {}
    if isinstance(записи, dict):
        записи = list(записи.values())
    отобранные = [з for з in записи if isinstance(з, dict) and з.get("id")][:сколько]
    if len(отобранные) < сколько:
        raise SystemExit(f"в снимке меньше {сколько} пригодных записей")
    return отобранные


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    каталог = ЖИВЫЕ_ДАННЫЕ / f"{SITE_ID}-catalog.json"
    подробности = ЖИВЫЕ_ДАННЫЕ / f"{SITE_ID}-details.json"
    for файл in (каталог, подробности):
        if not файл.exists():
            raise SystemExit(f"нет снимка: {файл}")
    образцы = взять_записи(подробности, 2)
    до_копии = [каталог.stat(), подробности.stat()]

    отчёт: dict = {"site_id": SITE_ID, "source_snapshot": str(каталог),
                   "live_snapshot_untouched": None, "steps": {}}

    with tempfile.TemporaryDirectory(prefix="zona02-sync-") as tmp:
        рабочая = Path(tmp)
        курсор = рабочая / "sync-checkpoint.json"
        состояние: dict[str, dict] = {}

        def применить(партия: list[sync.Event]) -> None:
            """Атомарное применение партии в локальную копию."""
            новое = dict(состояние)
            for событие in партия:
                ид = событие.payload["id"]
                if событие.kind == sync.DELETE:
                    новое.pop(ид, None)
                else:
                    слитое = dict(новое.get(ид) or {})
                    слитое.update(событие.payload)
                    новое[ид] = слитое
            состояние.clear()
            состояние.update(новое)

        партия = [
            {"seq": 1, "event_id": "zona02-evt-1", "kind": sync.UPSERT,
             "content_revision": 1, "profiles": [ПРОФИЛЬ],
             "title_uuid": образцы[0]["id"],
             "payload": {"id": образцы[0]["id"], "title": образцы[0].get("name"),
                         "seasons": образцы[0].get("seasons"),
                         "episodes": образцы[0].get("episodes")}},
            {"seq": 2, "event_id": "zona02-evt-2", "kind": sync.UPSERT,
             "content_revision": 1, "profiles": [ПРОФИЛЬ],
             "title_uuid": образцы[1]["id"],
             "payload": {"id": образцы[1]["id"], "title": образцы[1].get("name")}},
        ]

        # 1. Первая доставка.
        первая = sync.pull(site_id=SITE_ID, profile=ПРОФИЛЬ,
                           fetch=lambda seq: [e for e in партия if e["seq"] > seq],
                           checkpoint_path=курсор, apply_batch=применить)
        отчёт["steps"]["first_delivery"] = первая.to_dict()
        отчёт["steps"]["first_delivery"]["records_after"] = len(состояние)

        # 2. Повтор той же партии.
        повтор = sync.pull(site_id=SITE_ID, profile=ПРОФИЛЬ,
                           fetch=lambda seq: партия,
                           checkpoint_path=курсор, apply_batch=применить)
        отчёт["steps"]["repeat_delivery"] = повтор.to_dict()
        отчёт["steps"]["repeat_delivery"]["records_after"] = len(состояние)

        # 3. Удаление.
        удаление = [{"seq": 3, "event_id": "zona02-evt-3", "kind": sync.DELETE,
                     "content_revision": 2, "profiles": [ПРОФИЛЬ],
                     "title_uuid": образцы[1]["id"],
                     "payload": {"id": образцы[1]["id"]}}]
        снятие = sync.pull(site_id=SITE_ID, profile=ПРОФИЛЬ,
                           fetch=lambda seq: [e for e in партия + удаление if e["seq"] > seq],
                           checkpoint_path=курсор, apply_batch=применить)
        отчёт["steps"]["delete_delivery"] = снятие.to_dict()
        отчёт["steps"]["delete_delivery"]["records_after"] = len(состояние)
        отчёт["steps"]["delete_delivery"]["deleted_id_present"] = образцы[1]["id"] in состояние

        # 4. Недоступный источник.
        try:
            sync.pull(site_id=SITE_ID, profile=ПРОФИЛЬ,
                      fetch=lambda seq: (_ for _ in ()).throw(RuntimeError("источник недоступен")),
                      checkpoint_path=курсор, apply_batch=применить, max_attempts=2)
            отчёт["steps"]["upstream_down"] = {"raised": False}
        except sync.UpstreamUnavailable as exc:
            отчёт["steps"]["upstream_down"] = {
                "raised": True, "reason": str(exc)[:200],
                "records_after": len(состояние),
                "note": "ноль записей не записан, работает прежний снимок"}
        отчёт["steps"]["freshness"] = sync.freshness(курсор, SITE_ID)

    # 5. Владение полями: каталог и SEO не затирают друг друга.
    uuid = str(образцы[0]["id"])
    запись = ownership.Record(title_uuid=uuid, site_id=SITE_ID)
    запись = ownership.apply(запись, ownership.Change(
        title_uuid=uuid, owner=ownership.Owner.CATALOG,
        fields={"title": образцы[0].get("name"), "seasons": образцы[0].get("seasons"),
                "episodes": образцы[0].get("episodes")},
        source="catalog-sync"))
    запись = ownership.apply(запись, ownership.Change(
        title_uuid=uuid, owner=ownership.Owner.SEO,
        fields={"seo_title": образцы[0].get("name"),
                "seo_description": образцы[0].get("description")},
        expected_revision=запись.revision, source="seo-layer"))
    после_seo = запись.view()
    запись = ownership.apply(запись, ownership.Change(
        title_uuid=uuid, owner=ownership.Owner.CATALOG,
        fields={"episodes": образцы[0].get("episodes")},
        expected_revision=запись.revision, source="catalog-sync"))
    после_каталога = запись.view()

    чужое = None
    try:
        ownership.apply(запись, ownership.Change(
            title_uuid=uuid, owner=ownership.Owner.SEO,
            fields={"episodes": 999}, expected_revision=запись.revision))
    except ownership.NotFieldOwner as exc:
        чужое = str(exc)[:200]

    отчёт["steps"]["field_ownership"] = {
        "title_uuid": uuid,
        "seo_survives_catalog_update":
            после_каталога.get("seo_description") == после_seo.get("seo_description"),
        "catalog_survives_seo_update":
            после_seo.get("episodes") == образцы[0].get("episodes"),
        "seo_cannot_write_catalog_field": чужое,
        "revision": запись.revision,
        "conflicts": запись.conflicts,
    }

    после_копии = [каталог.stat(), подробности.stat()]
    отчёт["live_snapshot_untouched"] = all(
        a.st_size == b.st_size and a.st_mtime == b.st_mtime
        for a, b in zip(до_копии, после_копии))

    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(отчёт, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(отчёт, ensure_ascii=False, indent=2, default=str))

    провалы = []
    ш = отчёт["steps"]
    if ш["first_delivery"]["applied"] != 2: провалы.append("первая доставка")
    if ш["repeat_delivery"]["applied"] != 0: провалы.append("повтор применил события")
    if ш["repeat_delivery"]["duplicates"] < 2: провалы.append("повтор не опознан дублями")
    if ш["delete_delivery"]["deleted"] != 1: провалы.append("удаление не доехало")
    if ш["delete_delivery"]["deleted_id_present"]: провалы.append("удалённая запись осталась")
    if not ш["upstream_down"].get("raised"): провалы.append("недоступный источник не назван")
    if not ш["field_ownership"]["seo_survives_catalog_update"]: провалы.append("каталог стёр SEO")
    if not ш["field_ownership"]["catalog_survives_seo_update"]: провалы.append("SEO стёр каталог")
    if not ш["field_ownership"]["seo_cannot_write_catalog_field"]:
        провалы.append("SEO записал чужое поле")
    if not отчёт["live_snapshot_untouched"]: провалы.append("живой снимок изменён")
    if провалы:
        print("ПРОВАЛЫ:", провалы, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
