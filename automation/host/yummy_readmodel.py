"""Read-model контентного контура Yummy — то, что читает шаблон.

Каждая поверхность отвечает на свой вопрос и наполняется своим источником.
Подменять их общим каталогом запрещено: раздел, показывающий каталог под
именем «Новые серии», выглядит работающим и потому не чинится годами.

Все поверхности отдают `entity_id` и `canonical_path`. Шаблон не собирает
адрес сам — ни из названия, ни из слага: собранный адрес однажды разойдётся
с объявленным, и карточка поведёт в никуда.
"""

from __future__ import annotations

import datetime as dt
import math
import sqlite3
from typing import Any

КОНТРАКТ = "yummy-read-model/1.0.0"

# --- «Актуальное»: формула, а не вкус ---------------------------------------
#
# Оценка складывается из трёх слагаемых с объявленными весами. Формула
# зафиксирована здесь, а не подбирается на месте: раздел, собранный «по
# ощущению», невозможно ни воспроизвести, ни оспорить.
ВЕС_СВЕЖЕСТИ = 0.5
ВЕС_РЕЙТИНГА = 0.35
ВЕС_ПОКАЗА = 0.15
#: Период полураспада свежести: за столько суток вклад свежести падает вдвое.
ПОЛУРАСПАД_ДНЕЙ = 14.0
#: Байесовское сглаживание: сколько голосов нужно, чтобы рейтингу верить.
#: Источник с тремя голосами и оценкой 10 не должен обгонять источник с
#: тысячей голосов и оценкой 8 — именно от этого сглаживание и защищает.
ПОРОГ_ГОЛОСОВ = 500.0
#: Априорная оценка, к которой стягиваются рейтинги с малым числом голосов.
АПРИОРИ = 7.0


def _время(строка: str | None) -> dt.datetime | None:
    if not строка:
        return None
    try:
        return dt.datetime.fromisoformat(строка.replace("Z", "+00:00"))
    except ValueError:
        return None


def свежесть(published_at: str | None, сейчас: dt.datetime) -> float:
    """От 1 (только что) до 0 (давно). Экспоненциальный спад."""
    т = _время(published_at)
    if т is None:
        return 0.0
    дней = max((сейчас - т).total_seconds() / 86400.0, 0.0)
    return math.pow(0.5, дней / ПОЛУРАСПАД_ДНЕЙ)


def сглаженный_рейтинг(value: float | None, votes: int | None,
                       scale: float) -> float | None:
    """Рейтинг в долях единицы с поправкой на число голосов.

    Голоса неизвестны — это НЕ повод считать их достаточными. Неизвестность
    трактуется как ноль голосов, и оценка стягивается к априорной полностью:
    иначе источник без счётчика голосов автоматически обгонял бы источник с
    ним, и «Актуальное» заполнялось бы тем, о чём меньше всего известно.
    """
    if value is None or not scale:
        return None
    n = float(votes or 0)
    v = float(value) * (10.0 / scale)          # к общей десятибалльной
    сглажено = (n * v + ПОРОГ_ГОЛОСОВ * АПРИОРИ) / (n + ПОРОГ_ГОЛОСОВ)
    return max(0.0, min(сглажено / 10.0, 1.0))


def _строки(соед: sqlite3.Connection, sql: str, *п: Any) -> list[dict]:
    return [dict(с) for с in соед.execute(sql, п).fetchall()]


def карточка(с: dict) -> dict:
    """Единый вид карточки. Адрес — только объявленный."""
    return {"entityId": с["entity_id"], "canonicalPath": с["canonical_path"],
            "title": с["title_ru"], "poster": с["poster_path"],
            "year": с["year"], "kind": с["kind"],
            "publishedAt": с["published_at"], "contract": КОНТРАКТ}


def актуальное(соед: sqlite3.Connection, предел: int = 24,
               сейчас: dt.datetime | None = None) -> dict:
    сейчас = сейчас or dt.datetime.now(dt.timezone.utc)
    строки = _строки(соед, "SELECT * FROM entity WHERE canonical_path IS NOT NULL")
    рейтинги: dict[str, list[dict]] = {}
    for р in _строки(соед, "SELECT * FROM external_rating WHERE status='OK'"):
        рейтинги.setdefault(р["entity_id"], []).append(р)
    оценённые = []
    for с in строки:
        f = свежесть(с["published_at"], сейчас)
        свои = рейтинги.get(с["entity_id"], [])
        части = [сглаженный_рейтинг(р["value"], р["votes"], р["scale"])
                 for р in свои]
        части = [ч for ч in части if ч is not None]
        r = sum(части) / len(части) if части else None
        a = 1.0 if с["airing_status"] == "CONFIRMED_ONGOING" else 0.0
        балл = ВЕС_СВЕЖЕСТИ * f + ВЕС_ПОКАЗА * a
        балл += ВЕС_РЕЙТИНГА * (r if r is not None else 0.0)
        к = карточка(с)
        к["score"] = round(балл, 6)
        к["scoreParts"] = {"freshness": round(f, 6),
                           "rating": None if r is None else round(r, 6),
                           "airing": a, "ratingsUsed": len(части)}
        оценённые.append(к)
    оценённые.sort(key=lambda к: (-к["score"], к["entityId"]))
    return {"contract": КОНТРАКТ, "surface": "актуальное",
            "formula": {"weights": {"freshness": ВЕС_СВЕЖЕСТИ,
                                    "rating": ВЕС_РЕЙТИНГА,
                                    "airing": ВЕС_ПОКАЗА},
                        "halfLifeDays": ПОЛУРАСПАД_ДНЕЙ,
                        "votePrior": ПОРОГ_ГОЛОСОВ, "ratingPrior": АПРИОРИ,
                        "note": ("голоса неизвестны — считаются нулём, "
                                 "рейтинг стягивается к априорному")},
            "items": оценённые[:предел], "total": len(оценённые)}


def новые_серии(соед: sqlite3.Connection, предел: int = 24) -> dict:
    строки = _строки(соед,
        "SELECT e.*, s.season, s.episode, s.voice, s.source_event_at, "
        "s.published_at AS event_published_at, s.source "
        "FROM episode_event s JOIN entity e ON e.entity_id = s.entity_id "
        "ORDER BY COALESCE(s.source_event_at, s.published_at) DESC LIMIT ?",
        предел)
    items = []
    for с in строки:
        к = карточка(с)
        к.update({"season": с["season"], "episode": с["episode"],
                  "voice": с["voice"] or None,
                  "sourceEventAt": с["source_event_at"],
                  "publishedAt": с["event_published_at"],
                  "source": с["source"]})
        items.append(к)
    return {"contract": КОНТРАКТ, "surface": "новые-серии", "items": items,
            "note": ("только события появления серии; время выхода не "
                     "подменяется временем пересборки сайта")}


def сейчас_выходит(соед: sqlite3.Connection, предел: int = 24) -> dict:
    """Только подтверждённый статус показа.

    Недавняя загрузка файла статусом показа не является и сюда не приводит.
    Неподтверждённый и завершённый тайтл исключены — оба.
    """
    # Допускаются два состояния и только они: подтверждённое источником и
    # выведенное по объявленному правилу. Завершённые и неподтверждённые
    # исключены — оба, как и требовалось.
    #
    # Разделение существенно: CVH статуса показа не публикует вовсе (измерено:
    # ноль вхождений status/airing_status/is_ongoing на выборке 600), поэтому
    # CONFIRMED_ONGOING сейчас не ставится никогда, а DERIVED_ONGOING выведен
    # из «доступных серий меньше, чем заявлено». Смешивать их в одно значение
    # нельзя: тогда витрина не отличит знание от вывода.
    строки = _строки(соед,
        "SELECT * FROM entity WHERE airing_status IN "
        "('CONFIRMED_ONGOING','DERIVED_ONGOING') "
        "ORDER BY COALESCE(next_episode_at, last_episode_at, updated_at) DESC "
        "LIMIT ?", предел)
    items = []
    for с in строки:
        к = карточка(с)
        к.update({"airingStatus": с["airing_status"],
                  "confidence": ("CONFIRMED" if с["airing_status"].startswith("CONFIRMED")
                                 else "DERIVED"),
                  "lastEpisodeAt": с["last_episode_at"],
                  "nextEpisodeAt": с["next_episode_at"],
                  "episodesReleased": с["episodes_released"],
                  "source": с["airing_source"],
                  "checkedAt": с["airing_checked_at"],
                  "ttlSeconds": с["airing_ttl_seconds"]})
        items.append(к)
    return {"contract": КОНТРАКТ, "surface": "сейчас-выходит", "items": items,
            "note": ("включаются подтверждённые источником и выведенные по "
                     "правилу «доступных серий меньше заявленного»; "
                     "завершённые и неподтверждённые исключены. "
                     "confidence различает знание и вывод: CVH статуса показа "
                     "не публикует, поэтому CONFIRMED сейчас не встречается")}


def внешние_рейтинги(соед: sqlite3.Connection, entity_id: str) -> dict:
    строки = _строки(соед,
        "SELECT * FROM external_rating WHERE entity_id=? ORDER BY provider",
        entity_id)
    return {"contract": КОНТРАКТ, "surface": "внешние-рейтинги",
            "entityId": entity_id,
            "providers": [{"provider": с["provider"],
                           "externalId": с["external_id"], "value": с["value"],
                           "scale": с["scale"], "votes": с["votes"],
                           "fetchedAt": с["fetched_at"], "source": с["source"],
                           "status": с["status"]} for с in строки],
            "note": "шкалы не приводятся к общей и не смешиваются"}


def пользовательский_рейтинг(соед: sqlite3.Connection, entity_id: str,
                             user_id: str | None = None) -> dict:
    агрегат = соед.execute(
        "SELECT count(*) n, avg(value) v FROM user_rating WHERE entity_id=?",
        (entity_id,)).fetchone()
    своя = None
    if user_id:
        с = соед.execute(
            "SELECT value, updated_at FROM user_rating WHERE entity_id=? "
            "AND user_id=?", (entity_id, user_id)).fetchone()
        своя = {"value": с["value"], "updatedAt": с["updated_at"]} if с else None
    return {"contract": КОНТРАКТ, "surface": "пользовательские-рейтинги",
            "entityId": entity_id,
            "aggregate": {"count": агрегат["n"],
                          "average": round(агрегат["v"], 3) if агрегат["v"] else None,
                          "scale": 10},
            "mine": своя,
            "note": "оценка пользователя и внешний рейтинг — разные сущности"}


def поставить_оценку(соед: sqlite3.Connection, user_id: str, entity_id: str,
                     value: int) -> dict:
    if not соед.execute("SELECT 1 FROM entity WHERE entity_id=?",
                        (entity_id,)).fetchone():
        return {"ok": False, "error": "ENTITY_UNKNOWN",
                "reason": "оценка произведению, которого нет в контуре"}
    if not 1 <= int(value) <= 10:
        return {"ok": False, "error": "VALUE_OUT_OF_RANGE",
                "reason": "оценка вне шкалы 1..10"}
    т = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    соед.execute(
        "INSERT INTO user_rating(user_id, entity_id, value, scale, created_at, "
        "updated_at) VALUES(?,?,?,10,?,?) "
        "ON CONFLICT(user_id, entity_id) DO UPDATE SET value=excluded.value, "
        "updated_at=excluded.updated_at",
        (user_id, entity_id, int(value), т, т))
    соед.commit()
    return {"ok": True, "entityId": entity_id, "value": int(value)}


def новости(соед: sqlite3.Connection, тип: str = "news",
            предел: int = 24) -> dict:
    строки = _строки(соед,
        "SELECT * FROM editorial_post WHERE type=? AND status='published' "
        "ORDER BY published_at DESC LIMIT ?", тип, предел)
    items = []
    for с in строки:
        связанные = [р["entity_id"] for р in _строки(
            соед, "SELECT entity_id FROM editorial_post_entity WHERE post_id=?",
            с["post_id"])]
        items.append({"postId": с["post_id"], "type": с["type"],
                      "source": с["source"], "title": с["title"],
                      "summary": с["summary"], "image": с["image_path"],
                      "canonicalPath": с["canonical_path"],
                      "publishedAt": с["published_at"],
                      "updatedAt": с["updated_at"],
                      "provenance": с["provenance"],
                      "relatedEntityIds": связанные})
    return {"contract": КОНТРАКТ, "surface": тип, "items": items,
            "note": ("SEO-модуль получает подтверждённые данные и не "
                     "выдумывает ни новостей, ни дат")}


def разрешить_адрес(соед: sqlite3.Connection, entity_id: str) -> dict:
    с = соед.execute(
        "SELECT entity_id, canonical_path FROM entity WHERE entity_id=?",
        (entity_id,)).fetchone()
    if not с:
        return {"contract": КОНТРАКТ, "entityId": entity_id,
                "canonicalPath": None, "outcome": "ENTITY_UNKNOWN",
                "reason": "произведения нет в контуре; адрес выдумывать нельзя"}
    return {"contract": КОНТРАКТ, "entityId": с["entity_id"],
            "canonicalPath": с["canonical_path"], "outcome": "RESOLVED",
            "reason": "адрес объявлен витриной"}
