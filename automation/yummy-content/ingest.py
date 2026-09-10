"""Импорт контентного контура: идемпотентный, с курсором, DLQ и retry.

Правила, которые здесь соблюдаются
----------------------------------

* повторный импорт тех же данных не создаёт вторых строк и не двигает
  `first_seen_at`: событие появления случается один раз;
* пустая или обвалившаяся выборка НЕ затирает уже импортированное —
  last-known-good остаётся;
* запись, которую не удалось провести, уходит в `dead_letter` с кодом,
  причиной, числом попыток и полезной нагрузкой, а не теряется молча;
* в контур попадают только произведения, для которых витрина объявила
  канонический адрес. Сущность без адреса опубликовать нельзя, а держать её
  в проекции — значит однажды показать карточку, ведущую в никуда.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import sqlite3
from pathlib import Path
from typing import Any, Iterable

import canonical

ПОТОК_СУЩНОСТЕЙ = "entities"
#: Обвал источника больше чем на эту долю — порча, а не правка ассортимента.
ДОПУСК_ОБВАЛА = 0.10


def сейчас() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def вид(запись: dict) -> tuple[str, str]:
    """Вид произведения и состояние знания о нём.

    Расхождение `type` и `is_series` не сглаживается: если они разошлись,
    это сообщение о порче данных, а не повод выбрать одно из двух.
    """
    т, с = запись.get("type"), запись.get("is_series")
    if т == "movie" and с is False:
        return "MOVIE", "AUTHORITATIVE"
    if т == "tv" and с is True:
        return "SERIES", "AUTHORITATIVE"
    if т in ("movie", "tv"):
        return "UNKNOWN", "CONFLICT"
    return "UNKNOWN", "MISSING"


def отпечаток(записи: list[dict]) -> str:
    основа = sorted(
        (str(з.get("external_id")), str(з.get("name")), str(з.get("updated_at")))
        for з in записи)
    return hashlib.blake2b(json.dumps(основа, ensure_ascii=False).encode(),
                           digest_size=16).hexdigest()


def в_dlq(соед: sqlite3.Connection, поток: str, ид: str | None, код: str,
          причина: str, нагрузка: Any = None) -> None:
    т = сейчас()
    соед.execute(
        "INSERT INTO dead_letter(stream, entity_id, error_code, reason, "
        "attempts, first_at, last_at, payload) VALUES(?,?,?,?,1,?,?,?) "
        "ON CONFLICT(stream, entity_id, error_code) DO UPDATE SET "
        "attempts = attempts + 1, last_at = excluded.last_at, "
        "reason = excluded.reason",
        (поток, ид, код, причина[:500], т, т,
         json.dumps(нагрузка, ensure_ascii=False)[:2000] if нагрузка else None))


def импорт_сущностей(соед: sqlite3.Connection, записи: list[dict],
                     маршруты: list[dict]) -> dict[str, Any]:
    """Провести каталог поставщика через резолвер в канонические сущности."""
    т = сейчас()
    состояние = соед.execute(
        "SELECT checksum, attempts, source_count FROM import_state WHERE stream=?",
        (ПОТОК_СУЩНОСТЕЙ,)).fetchone()
    прежний_отпечаток = состояние["checksum"] if состояние else None
    было = соед.execute("SELECT count(*) c FROM entity").fetchone()["c"]

    if not записи:
        соед.execute(
            "INSERT INTO import_state(stream, last_attempt, attempts, "
            "last_error, error_code) VALUES(?,?,1,?,?) "
            "ON CONFLICT(stream) DO UPDATE SET last_attempt=excluded.last_attempt, "
            "attempts=import_state.attempts+1, last_error=excluded.last_error, "
            "error_code=excluded.error_code",
            (ПОТОК_СУЩНОСТЕЙ, т, "источник вернул пустую выборку", "EMPTY_SOURCE"))
        в_dlq(соед, ПОТОК_СУЩНОСТЕЙ, None, "EMPTY_SOURCE",
              "источник вернул пустую выборку; уже импортированное сохранено")
        соед.commit()
        return {"imported": 0, "skipped": "EMPTY_SOURCE", "kept": было}

    резолвер = canonical.Резолвер(маршруты)
    новый_отпечаток = отпечаток(записи)

    проведено = новых = обновлено = отклонено = 0
    for з in записи:
        ид = str(з.get("external_id") or "")
        ссылка = резолвер.разрешить(ид)
        if not ссылка.публикуема:
            # Не ошибка источника: витрина просто не публикует это
            # произведение. В DLQ уходят только неожиданные исходы.
            if ссылка.outcome is canonical.Исход.СТОЛКНОВЕНИЕ:
                в_dlq(соед, ПОТОК_СУЩНОСТЕЙ, ид, "ROUTE_COLLISION",
                      ссылка.reason, {"name": з.get("name")})
            отклонено += 1
            continue
        к, кс = вид(з)
        слаг = ссылка.canonical_path.strip("/").split("/")[-1]
        прежняя = соед.execute(
            "SELECT first_seen_at, published_at FROM entity WHERE entity_id=?",
            (ид,)).fetchone()
        # `first_seen_at` ставится один раз и никогда не переписывается:
        # иначе каждый повторный импорт объявлял бы весь каталог новым.
        first_seen = прежняя["first_seen_at"] if прежняя else т
        published = (прежняя["published_at"] if прежняя
                     else (з.get("created_at") or т))
        соед.execute(
            "INSERT INTO entity(entity_id, slug, canonical_path, title_ru, "
            "title_original, kind, kind_state, year, poster_path, "
            "episodes_released, source_created_at, source_updated_at, "
            "first_seen_at, published_at, updated_at) "
            "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?) "
            "ON CONFLICT(entity_id) DO UPDATE SET slug=excluded.slug, "
            "canonical_path=excluded.canonical_path, title_ru=excluded.title_ru, "
            "kind=excluded.kind, kind_state=excluded.kind_state, "
            "year=excluded.year, poster_path=excluded.poster_path, "
            "source_updated_at=excluded.source_updated_at, "
            "updated_at=excluded.updated_at",
            (ид, слаг, ссылка.canonical_path, str(з.get("name") or ""),
             None, к, кс, з.get("year"), з.get("poster_url"), None,
             з.get("created_at"), з.get("updated_at"), first_seen, published, т))
        проведено += 1
        новых += 0 if прежняя else 1
        обновлено += 1 if прежняя else 0
        импорт_рейтингов(соед, ид, з, т)

    # Обвал считается по РАЗМЕРУ ВЫБОРКИ, а не по числу строк в таблице.
    # Импорт никогда не удаляет строки, поэтому таблица не уменьшается даже
    # тогда, когда источник отдал вчетверо меньше, — и проверка по таблице
    # не срабатывала никогда. Ровно так она и не сработала на первом прогоне.
    прежний_размер = состояние["source_count"] if состояние else None
    if прежний_размер and len(записи) < прежний_размер * (1 - ДОПУСК_ОБВАЛА):
        соед.rollback()
        в_dlq(соед, ПОТОК_СУЩНОСТЕЙ, None, "SOURCE_SHRINK",
              f"источник отдал {len(записи)} записей вместо {прежний_размер}: "
              f"импорт отклонён целиком, прежние данные сохранены")
        соед.commit()
        return {"imported": 0, "skipped": "SOURCE_SHRINK", "kept": было,
                "sourceCount": len(записи), "previousSourceCount": прежний_размер}

    соед.execute(
        "INSERT INTO import_state(stream, cursor, checksum, last_success, "
        "last_attempt, attempts, last_error, error_code, source_count) "
        "VALUES(?,?,?,?,?,0,NULL,NULL,?) ON CONFLICT(stream) DO UPDATE SET "
        "cursor=excluded.cursor, checksum=excluded.checksum, "
        "last_success=excluded.last_success, last_attempt=excluded.last_attempt, "
        "attempts=0, last_error=NULL, error_code=NULL, "
        "source_count=excluded.source_count",
        (ПОТОК_СУЩНОСТЕЙ, т, новый_отпечаток, т, т, len(записи)))
    соед.commit()
    return {"imported": проведено, "new": новых, "updated": обновлено,
            "rejected": отклонено, "checksum": новый_отпечаток,
            "unchanged": новый_отпечаток == прежний_отпечаток}


#: Провайдеры внешних рейтингов и их шкалы. Шкала объявлена рядом с
#: провайдером: 7,9 по десятибалльной и 7,9 по стобалльной — разные
#: утверждения, и хранить их в одном столбце без шкалы нельзя.
ПРОВАЙДЕРЫ = {
    "kp":   {"поле": "kinopoisk_rating", "ид": "kinopoisk", "scale": 10.0},
    "imdb": {"поле": "imdb_rating",      "ид": "imdb",      "scale": 10.0},
}


def импорт_рейтингов(соед: sqlite3.Connection, ид: str, з: dict,
                     т: str) -> None:
    """Внешние рейтинги — раздельно по провайдерам, без приведения шкал.

    Отсутствие рейтинга записывается состоянием `ABSENT`, а не нулём и не
    пропуском строки: ноль — это утверждение о плохом произведении, а
    отсутствие строки неотличимо от «не спрашивали».
    """
    внешние = з.get("external_ids") or {}
    for провайдер, опис in ПРОВАЙДЕРЫ.items():
        значение = з.get(опис["поле"])
        соед.execute(
            "INSERT INTO external_rating(entity_id, provider, external_id, "
            "value, scale, votes, fetched_at, source, status) "
            "VALUES(?,?,?,?,?,?,?,?,?) "
            "ON CONFLICT(entity_id, provider) DO UPDATE SET "
            "external_id=excluded.external_id, value=excluded.value, "
            "votes=excluded.votes, fetched_at=excluded.fetched_at, "
            "status=excluded.status",
            (ид, провайдер, str(внешние.get(опис["ид"]) or "") or None,
             значение, опис["scale"], None, т, "catalog:cdnvideohub",
             "OK" if значение is not None else "ABSENT"))


def импорт_серий(соед: sqlite3.Connection, события: Iterable[dict]) -> dict:
    """События появления серий. Повтор того же события — не событие.

    Ключ включает озвучку: та же серия в другой озвучке — отдельное событие
    для зрителя, который ждал именно её. Повторная подача той же четвёрки
    обновляет строку, но не создаёт вторую.
    """
    т, добавлено, повторов, отклонено = сейчас(), 0, 0, 0
    for с in события:
        ид = str(с.get("entity_id") or "")
        есть = соед.execute("SELECT 1 FROM entity WHERE entity_id=?",
                            (ид,)).fetchone()
        if not есть:
            в_dlq(соед, "episodes", ид, "ENTITY_UNKNOWN",
                  "событие серии для неизвестного произведения", с)
            отклонено += 1
            continue
        было = соед.execute(
            "SELECT 1 FROM episode_event WHERE entity_id=? AND season=? "
            "AND episode=? AND voice=?",
            (ид, с["season"], с["episode"], с.get("voice") or "")).fetchone()
        соед.execute(
            "INSERT INTO episode_event(entity_id, season, episode, voice, "
            "source_event_at, published_at, source) VALUES(?,?,?,?,?,?,?) "
            "ON CONFLICT(entity_id, season, episode, voice) DO UPDATE SET "
            "source_event_at=excluded.source_event_at",
            (ид, с["season"], с["episode"], с.get("voice") or "",
             с.get("source_event_at"), с.get("published_at") or т,
             с.get("source") or "unknown"))
        повторов += 1 if было else 0
        добавлено += 0 if было else 1
    соед.commit()
    return {"added": добавлено, "duplicates": повторов, "rejected": отклонено}


def маршруты_витрины(контейнер: str) -> list[dict]:
    return canonical.маршруты_из_базы(контейнер)


def каталог_поставщика(путь: str | Path) -> list[dict]:
    return json.loads(Path(путь).read_text(encoding="utf-8"))["items"]
