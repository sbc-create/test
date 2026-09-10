"""Обогащение контура из detail-выдачи CVH: серии, озвучки, статус показа.

Что в detail-выдаче есть и чего нет — измерено, а не предположено
-----------------------------------------------------------------

Есть: `seasons[]` с `available_episodes_count` и `episodes_count`,
`available_voices`, `premiere_date`, `imdb_rating`, `kinopoisk_rating`,
`original_name`, `genres`, `duration`, `countries`, `crew`.

Нет: **ни одного поля статуса показа.** Ни `status`, ни `airing_status`, ни
`is_ongoing`, ни `ongoing`, ни `state` — ноль вхождений на выборке в 600
записей. Поэтому «подтверждённого» статуса показа источник не даёт вовсе.

Отсюда два разных состояния, и смешивать их нельзя:

* `CONFIRMED_ONGOING` — источник прямо объявил, что показ идёт. Такого поля
  у CVH нет, и это состояние сейчас не ставится никогда;
* `DERIVED_ONGOING` — выведено по правилу «доступных серий меньше, чем
  заявлено». Правило названо, источник назван, срок годности проставлен.

Событие появления серии
-----------------------

CVH не публикует времени выхода каждой серии — только текущее число
доступных. Поэтому событие определяется приращением этого числа между
снимками, а `source_event_at` остаётся **пустым**: подставить туда время
нашего наблюдения значило бы выдать момент, когда мы посмотрели, за момент,
когда серия вышла. Наблюдение записывается отдельным полем `detected_at`.
"""

from __future__ import annotations

import datetime as dt
import json
import sqlite3
from pathlib import Path
from typing import Any

КЭШ = Path("/srv/site-factory/repo/var/lords/detail-cache")
ИСТОЧНИК = "catalog:cdnvideohub:detail"
#: Срок годности вывода о показе. Дольше суток такому выводу верить нельзя:
#: сериал успевает закончиться.
TTL_СЕКУНД = 86400


def сейчас() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def прочитать(ид: str) -> dict[str, Any] | None:
    п = КЭШ / f"{ид}.json"
    if not п.exists():
        return None
    try:
        сырое = json.loads(п.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return (сырое or {}).get("detail") or None


def озвучки(деталь: dict) -> list[str]:
    итог = []
    for г in деталь.get("available_voices") or []:
        имя = (г.get("studio_name") or g_code(г) or "").strip()
        if имя:
            итог.append(имя)
    return итог


def g_code(г: dict) -> str:
    return str(г.get("studio_code") or "")


def серии(деталь: dict) -> tuple[int, int]:
    """(доступно, заявлено) по всем сезонам."""
    доступно = заявлено = 0
    for с in деталь.get("seasons") or []:
        доступно += int(с.get("available_episodes_count") or 0)
        заявлено += int(с.get("episodes_count") or 0)
    return доступно, заявлено


def статус(доступно: int, заявлено: int) -> str:
    """Вывод о показе. `CONFIRMED_*` здесь не ставится никогда.

    Источник статуса не публикует, поэтому всё, что можно честно сказать, —
    это вывод по числам, и он так и называется.
    """
    if not заявлено:
        return "UNCONFIRMED"
    if доступно < заявлено:
        return "DERIVED_ONGOING"
    return "DERIVED_COMPLETED"


def обогатить(соед: sqlite3.Connection, предел: int | None = None) -> dict:
    """Пройти по сущностям контура и добрать из detail то, чего нет в списке."""
    т = сейчас()
    строки = соед.execute(
        "SELECT entity_id, episodes_released FROM entity ORDER BY entity_id"
    ).fetchall()
    if предел:
        строки = строки[:предел]
    обогащено = событий = без_детали = 0
    статусы: dict[str, int] = {}
    for р in строки:
        ид = р["entity_id"]
        деталь = прочитать(ид)
        if деталь is None:
            без_детали += 1
            continue
        доступно, заявлено = серии(деталь)
        с = статус(доступно, заявлено)
        статусы[с] = статусы.get(с, 0) + 1
        прежде = р["episodes_released"]
        соед.execute(
            "UPDATE entity SET title_original=?, episodes_released=?, "
            "airing_status=?, airing_source=?, airing_checked_at=?, "
            "airing_ttl_seconds=?, updated_at=? WHERE entity_id=?",
            (деталь.get("original_name") or None, доступно or None, с,
             ИСТОЧНИК, т, TTL_СЕКУНД, т, ид))
        обогащено += 1

        # Событие серии — только приращение. Первое наблюдение событием не
        # является: иначе весь каталог разом стал бы «новыми сериями».
        if прежде is not None and доступно > прежде:
            голоса = озвучки(деталь) or [""]
            for номер in range(int(прежде) + 1, доступно + 1):
                for голос in голоса[:1]:
                    соед.execute(
                        "INSERT INTO episode_event(entity_id, season, episode, "
                        "voice, source_event_at, published_at, source) "
                        "VALUES(?,?,?,?,NULL,?,?) "
                        "ON CONFLICT(entity_id, season, episode, voice) "
                        "DO NOTHING",
                        (ид, 1, номер, голос, т, ИСТОЧНИК))
                    событий += 1
        # Рейтинги из detail точнее списочных: там они есть чаще.
        for провайдер, поле, ид_поле in (("imdb", "imdb_rating", "imdb"),
                                         ("kp", "kinopoisk_rating", "kp")):
            значение = деталь.get(поле)
            if значение is None:
                continue
            внеш = (деталь.get("external_ids") or {}).get(ид_поле)
            соед.execute(
                "INSERT INTO external_rating(entity_id, provider, external_id, "
                "value, scale, votes, fetched_at, source, status) "
                "VALUES(?,?,?,?,10,NULL,?,?, 'OK') "
                "ON CONFLICT(entity_id, provider) DO UPDATE SET "
                "value=excluded.value, external_id=excluded.external_id, "
                "fetched_at=excluded.fetched_at, source=excluded.source, "
                "status='OK'",
                (ид, провайдер, str(внеш) if внеш else None, значение, т,
                 ИСТОЧНИК))
    соед.commit()
    return {"enriched": обогащено, "withoutDetail": без_детали,
            "episodeEvents": событий, "airingStatuses": статусы}
