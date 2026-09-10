"""Хранилище контентного контура Yummy: сущности, рейтинги, события, новости.

Почему отдельное хранилище, а не таблицы витрины
-----------------------------------------------

Канонический слой витрины (`Title`, `TitleExternalId`, `EditorialPost`) пуст
во всех трёх тенантах, и наполнять его здесь нельзя: это боевые базы, а
задание прямо запрещает менять production. Поэтому контур собирается в
собственном хранилище, наполняется из тех же источников и проверяется
целиком. Включение — отдельным решением владельца, по плану backfill.

Схема повторяет модель витрины по составу полей, чтобы перенос был
переносом, а не переписыванием.

Отдельно о рейтингах
--------------------

Внешний рейтинг и оценка пользователя — разные сущности и лежат в разных
таблицах. Смешать их один раз — значит навсегда потерять возможность
ответить, откуда взялось число на странице. У внешнего обязателен `scale`:
7,9 по десятибалльной и 7,9 по стобалльной — разные утверждения, и
приводить их к одному числу без шкалы нельзя.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

СХЕМА = "yummy-content-store/1.0.0"

DDL = """
PRAGMA journal_mode=WAL;

-- Каноническая сущность. entity_id — идентификатор произведения у поставщика,
-- он же ключ маршрута витрины. Своего суррогата не заводим: второй
-- идентификатор той же вещи неизбежно разойдётся с первым.
CREATE TABLE IF NOT EXISTS entity (
  entity_id      TEXT PRIMARY KEY,
  slug           TEXT,
  canonical_path TEXT,
  title_ru       TEXT NOT NULL,
  title_original TEXT,
  kind           TEXT NOT NULL,          -- MOVIE | SERIES | UNKNOWN
  kind_state     TEXT NOT NULL,          -- AUTHORITATIVE | CONFLICT | MISSING
  year           INTEGER,
  poster_path    TEXT,
  -- Статус показа. CONFIRMED_* ставится только по подтверждённому источнику;
  -- UNCONFIRMED — умолчание, и в «Сейчас выходит» такой тайтл не попадает.
  airing_status  TEXT NOT NULL DEFAULT 'UNCONFIRMED',
  airing_source  TEXT,
  airing_checked_at TEXT,
  airing_ttl_seconds INTEGER,
  episodes_released INTEGER,
  next_episode_at   TEXT,
  last_episode_at   TEXT,
  source_created_at TEXT,
  source_updated_at TEXT,
  first_seen_at  TEXT NOT NULL,          -- событие появления у нас
  published_at   TEXT,                   -- событие публикации на витрине
  updated_at     TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_entity_published ON entity(published_at DESC);
CREATE INDEX IF NOT EXISTS idx_entity_airing ON entity(airing_status);

-- Внешние рейтинги. Ключ — (provider, entity_id): один провайдер даёт по
-- произведению одно значение. Шкала хранится рядом со значением всегда.
CREATE TABLE IF NOT EXISTS external_rating (
  entity_id   TEXT NOT NULL,
  provider    TEXT NOT NULL,             -- kp | imdb | shikimori | mal | mdl
  external_id TEXT,
  value       REAL,
  scale       REAL NOT NULL,
  votes       INTEGER,
  fetched_at  TEXT NOT NULL,
  source      TEXT NOT NULL,
  status      TEXT NOT NULL,             -- OK | ABSENT | STALE | ERROR
  PRIMARY KEY (entity_id, provider)
);

-- Оценка пользователя. Отдельная сущность: одна строка на пару
-- (пользователь, произведение), изменение — обновление той же строки.
CREATE TABLE IF NOT EXISTS user_rating (
  user_id    TEXT NOT NULL,
  entity_id  TEXT NOT NULL,
  value      INTEGER NOT NULL,
  scale      REAL NOT NULL DEFAULT 10,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  PRIMARY KEY (user_id, entity_id)
);

-- Событие появления серии. Ключ включает сезон, серию и озвучку: одна и та
-- же серия в другой озвучке — другое событие, а повтор той же — не событие.
CREATE TABLE IF NOT EXISTS episode_event (
  entity_id       TEXT NOT NULL,
  season          INTEGER NOT NULL,
  episode         INTEGER NOT NULL,
  voice           TEXT NOT NULL DEFAULT '',
  source_event_at TEXT,
  published_at    TEXT NOT NULL,
  source          TEXT NOT NULL,
  PRIMARY KEY (entity_id, season, episode, voice)
);
CREATE INDEX IF NOT EXISTS idx_episode_published ON episode_event(published_at DESC);

-- Новости и анонсы. Стабильный идентификатор — не автоинкремент, а хэш
-- источника и ключа: повторная выборка того же материала обязана дать ту же
-- строку, иначе дедупликации не существует.
CREATE TABLE IF NOT EXISTS editorial_post (
  post_id        TEXT PRIMARY KEY,
  type           TEXT NOT NULL,          -- news | announcement
  source         TEXT NOT NULL,
  source_key     TEXT NOT NULL,
  title          TEXT NOT NULL,
  summary        TEXT,
  body           TEXT,
  image_path     TEXT,
  canonical_path TEXT,
  provenance     TEXT NOT NULL,
  published_at   TEXT NOT NULL,
  updated_at     TEXT NOT NULL,
  status         TEXT NOT NULL DEFAULT 'draft',
  UNIQUE (source, source_key)
);
CREATE TABLE IF NOT EXISTS editorial_post_entity (
  post_id   TEXT NOT NULL,
  entity_id TEXT NOT NULL,
  PRIMARY KEY (post_id, entity_id)
);

-- Состояние импорта: курсор, попытки, ошибки. Переживает рестарт.
CREATE TABLE IF NOT EXISTS import_state (
  stream        TEXT PRIMARY KEY,
  cursor        TEXT,
  checksum      TEXT,
  last_success  TEXT,
  last_attempt  TEXT,
  attempts      INTEGER NOT NULL DEFAULT 0,
  last_error    TEXT,
  error_code    TEXT,
  -- размер последней принятой выборки: по нему, а не по числу
  -- строк в таблице, обнаруживается обвал источника
  source_count  INTEGER
);

-- Мёртвые письма: запись, которую не удалось провести, с кодом и причиной.
CREATE TABLE IF NOT EXISTS dead_letter (
  id         INTEGER PRIMARY KEY AUTOINCREMENT,
  stream     TEXT NOT NULL,
  entity_id  TEXT,
  error_code TEXT NOT NULL,
  reason     TEXT NOT NULL,
  attempts   INTEGER NOT NULL,
  first_at   TEXT NOT NULL,
  last_at    TEXT NOT NULL,
  payload    TEXT
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_dlq_key ON dead_letter(stream, entity_id, error_code);
"""


def открыть(путь: str | Path) -> sqlite3.Connection:
    п = Path(путь)
    п.parent.mkdir(parents=True, exist_ok=True)
    соед = sqlite3.connect(п, timeout=30)
    соед.row_factory = sqlite3.Row
    соед.executescript(DDL)
    return соед
