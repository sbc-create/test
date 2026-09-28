"""Фикстура расширенного контента Yummy: доказательство готовности шаблона.

Зачем она
---------

Контентный контур сегодня отдаёт название, год, тип, постер и немного оценок.
Полная карточка, рекомендации, новости, анонсы, подтверждённый онгоинг и
расписание ждут Архитектора. Проверить на живых данных нечего — а объявлять
компонент готовым без единого прогона нельзя.

Фикстура собирает базу **того контура, который придёт**: базовые таблицы 1.0.0
плюс расширения (жанры, студии, страны, персоны, озвучки, альтернативные
названия, рекомендации, материалы редакции). На ней компоненты рисуются
целиком, и если после подключения живых данных что-то не сойдётся — разойдётся
именно контракт, а не разметка.

Данные заведомо синтетические: названия начинаются с «Фикстура». Ни одна
строка отсюда не должна попасть на публичный домен, и тест это проверяет.
"""

from __future__ import annotations

import sqlite3

МЕТКА = "Фикстура"

СХЕМА = """
CREATE TABLE entity (
  entity_id TEXT PRIMARY KEY, slug TEXT, canonical_path TEXT,
  title_ru TEXT NOT NULL, title_original TEXT, kind TEXT NOT NULL,
  kind_state TEXT NOT NULL DEFAULT 'AUTHORITATIVE', year INTEGER,
  poster_path TEXT, airing_status TEXT NOT NULL DEFAULT 'UNCONFIRMED',
  airing_source TEXT, airing_checked_at TEXT, airing_ttl_seconds INTEGER,
  episodes_released INTEGER, next_episode_at TEXT, last_episode_at TEXT,
  source_created_at TEXT, source_updated_at TEXT,
  first_seen_at TEXT NOT NULL, published_at TEXT, updated_at TEXT NOT NULL,
  -- расширение контракта: поля полной карточки
  description TEXT, backdrop_path TEXT, age_rating TEXT,
  duration_minutes INTEGER, seasons INTEGER, episodes_total INTEGER,
  aired_from TEXT, aired_to TEXT
);
CREATE TABLE external_rating (
  entity_id TEXT NOT NULL, provider TEXT NOT NULL, external_id TEXT,
  value REAL, scale REAL NOT NULL, votes INTEGER, fetched_at TEXT NOT NULL,
  source TEXT NOT NULL, status TEXT NOT NULL, PRIMARY KEY (entity_id, provider));
CREATE TABLE user_rating (
  user_id TEXT NOT NULL, entity_id TEXT NOT NULL, value INTEGER NOT NULL,
  scale REAL NOT NULL DEFAULT 10, created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL, PRIMARY KEY (user_id, entity_id));
CREATE TABLE episode_event (
  entity_id TEXT NOT NULL, season INTEGER NOT NULL, episode INTEGER NOT NULL,
  voice TEXT NOT NULL DEFAULT '', source_event_at TEXT, published_at TEXT NOT NULL,
  source TEXT NOT NULL, PRIMARY KEY (entity_id, season, episode, voice));
CREATE TABLE editorial_post (
  post_id TEXT PRIMARY KEY, type TEXT NOT NULL, source TEXT NOT NULL,
  source_key TEXT NOT NULL, title TEXT NOT NULL, summary TEXT, body TEXT,
  image_path TEXT, canonical_path TEXT, provenance TEXT NOT NULL,
  published_at TEXT NOT NULL, updated_at TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'draft', UNIQUE (source, source_key));
CREATE TABLE editorial_post_entity (
  post_id TEXT NOT NULL, entity_id TEXT NOT NULL, PRIMARY KEY (post_id, entity_id));
-- расширение контракта: связки
CREATE TABLE entity_title  (entity_id TEXT NOT NULL, title TEXT NOT NULL, position INTEGER);
CREATE TABLE entity_genre  (entity_id TEXT NOT NULL, genre TEXT NOT NULL, position INTEGER);
CREATE TABLE entity_studio (entity_id TEXT NOT NULL, studio TEXT NOT NULL);
CREATE TABLE entity_country(entity_id TEXT NOT NULL, country TEXT NOT NULL);
CREATE TABLE entity_dub    (entity_id TEXT NOT NULL, dub TEXT NOT NULL);
CREATE TABLE entity_person (entity_id TEXT NOT NULL, person TEXT NOT NULL,
                            role TEXT NOT NULL, position INTEGER);
CREATE TABLE recommendation(entity_id TEXT NOT NULL, target_entity_id TEXT NOT NULL,
                            reason TEXT, source TEXT, weight REAL,
                            PRIMARY KEY (entity_id, target_entity_id));
CREATE TABLE read_model_meta(contract TEXT NOT NULL);
"""

СЕЙЧАС = "2026-09-10T12:00:00+00:00"
ГЛАВНЫЙ = "ent-fixture-0001"


def _сущность(соед, ид, номер, **поля):
    база = dict(
        entity_id=ид, slug=f"fixture-{номер}",
        canonical_path=f"/anime/fixture-{номер}",
        title_ru=f"{МЕТКА} {номер}", title_original=f"Fixture Title {номер}",
        kind="SERIES", kind_state="AUTHORITATIVE", year=2024,
        poster_path=f"/poster/fixture-{номер}.webp",
        first_seen_at=СЕЙЧАС, updated_at=СЕЙЧАС, published_at=СЕЙЧАС)
    база.update(поля)
    колонки = ", ".join(база)
    соед.execute(f"INSERT INTO entity ({колонки}) VALUES "
                 f"({', '.join('?' * len(база))})", list(база.values()))


def построить(соед: sqlite3.Connection) -> sqlite3.Connection:
    """Контур в том виде, в каком шаблон обязан его принять."""
    соед.executescript(СХЕМА)
    соед.execute("INSERT INTO read_model_meta (contract) VALUES ('yummy-read-model/1.1.0')")

    # Главный тайтл: заполнено ВСЁ, что умеет показать полная карточка.
    _сущность(
        соед, ГЛАВНЫЙ, "0001",
        title_ru=f"{МЕТКА}: полная карточка",
        title_original="Fixture: Complete Entity",
        airing_status="CONFIRMED_ONGOING", airing_source="fixture",
        episodes_released=8, episodes_total=24, seasons=2,
        next_episode_at="2026-09-14T18:00:00+00:00",
        last_episode_at="2026-09-07T18:00:00+00:00",
        description=("Синтетическое описание фикстуры. Существует только для "
                     "проверки вёрстки полной карточки и наружу не выходит."),
        backdrop_path="/backdrop/fixture-0001.webp", age_rating="16+",
        duration_minutes=24, aired_from="2025-04-05", aired_to="2026-09-30")
    for провайдер, значение, шкала, голоса in (
            ("imdb", 8.2, 10, 15321), ("kp", 8.1, 10, 4210),
            ("shikimori", 7.9, 10, None), ("anilist", 84.0, 100, 9002)):
        соед.execute(
            "INSERT INTO external_rating (entity_id, provider, value, scale, votes,"
            " fetched_at, source, status) VALUES (?,?,?,?,?,?,?, 'OK')",
            (ГЛАВНЫЙ, провайдер, значение, шкала, голоса, СЕЙЧАС, "fixture"))
    # Провайдер без значения: строка есть, показывать нечего — и не должно.
    соед.execute(
        "INSERT INTO external_rating (entity_id, provider, value, scale, votes,"
        " fetched_at, source, status) VALUES (?,?,NULL,10,NULL,?,?,'ABSENT')",
        (ГЛАВНЫЙ, "kitsu", СЕЙЧАС, "fixture"))

    for поз, т in enumerate(("Fixture Alternative", "フィクスチャ", "Фикстура (альт.)")):
        соед.execute("INSERT INTO entity_title VALUES (?,?,?)", (ГЛАВНЫЙ, т, поз))
    for поз, ж in enumerate(("приключения", "фантастика", "драма")):
        соед.execute("INSERT INTO entity_genre VALUES (?,?,?)", (ГЛАВНЫЙ, ж, поз))
    соед.execute("INSERT INTO entity_studio VALUES (?,?)", (ГЛАВНЫЙ, "Fixture Studio"))
    соед.execute("INSERT INTO entity_country VALUES (?,?)", (ГЛАВНЫЙ, "Япония"))
    for д in ("Fixture Dub One", "Fixture Dub Two", "Субтитры"):
        соед.execute("INSERT INTO entity_dub VALUES (?,?)", (ГЛАВНЫЙ, д))
    for поз, (имя, роль) in enumerate((
            ("Фикстура Режиссёров", "director"), ("Фикстура Актёрова", "actor"),
            ("Фикстура Актёров", "actor"), ("Фикстура Персонажев", "character"))):
        соед.execute("INSERT INTO entity_person VALUES (?,?,?,?)",
                     (ГЛАВНЫЙ, имя, роль, поз))

    # Шесть рекомендаций — ровно тот минимум, который обязан отрисоваться.
    for i in range(1, 7):
        ид = f"ent-fixture-rec-{i}"
        _сущность(соед, ид, f"rec-{i}", title_ru=f"{МЕТКА} рекомендация {i}",
                  year=2020 + i, kind="MOVIE" if i % 2 else "SERIES")
        соед.execute(
            "INSERT INTO external_rating (entity_id, provider, value, scale, votes,"
            " fetched_at, source, status) VALUES (?, 'imdb', ?, 10, ?, ?, 'fixture', 'OK')",
            (ид, 7.0 + i / 10, 1000 * i, СЕЙЧАС))
        соед.execute("INSERT INTO recommendation VALUES (?,?,?,?,?)",
                     (ГЛАВНЫЙ, ид, "совпадение по жанру и студии", "fixture",
                      1.0 - i / 100))

    # Поверхности лент. У каждой — свои сущности: пересечение запрещено и
    # проверяется тестом.
    for i in range(1, 5):
        ид = f"ent-fixture-ep-{i}"
        _сущность(соед, ид, f"ep-{i}", title_ru=f"{МЕТКА} серия {i}")
        соед.execute("INSERT INTO episode_event VALUES (?,?,?,?,?,?,?)",
                     (ид, 1, i, "Fixture Dub One", f"2026-09-0{i}T10:00:00+00:00",
                      СЕЙЧАС, "fixture"))
    for i in range(1, 4):
        ид = f"ent-fixture-on-{i}"
        _сущность(соед, ид, f"on-{i}", title_ru=f"{МЕТКА} онгоинг {i}",
                  airing_status="CONFIRMED_ONGOING", airing_source="fixture",
                  episodes_released=i * 3, last_episode_at=СЕЙЧАС)
    for i in range(1, 4):
        ид = f"ent-fixture-sc-{i}"
        _сущность(соед, ид, f"sc-{i}", title_ru=f"{МЕТКА} расписание {i}",
                  next_episode_at=f"2026-09-1{i}T18:00:00+00:00")
    for тип, сколько in (("news", 3), ("announcement", 2)):
        for i in range(1, сколько + 1):
            соед.execute(
                "INSERT INTO editorial_post (post_id, type, source, source_key,"
                " title, summary, image_path, canonical_path, provenance,"
                " published_at, updated_at, status) VALUES (?,?,?,?,?,?,?,?,?,?,?,'published')",
                (f"post-{тип}-{i}", тип, "fixture", f"{тип}-{i}",
                 f"{МЕТКА}: материал {тип} {i}",
                 "Синтетический анонс для проверки вёрстки ленты.",
                 None, f"/posts/fixture-{тип}-{i}", "fixture://contract-test",
                 СЕЙЧАС, СЕЙЧАС))
    соед.commit()
    return соед


def база() -> sqlite3.Connection:
    соед = sqlite3.connect(":memory:")
    соед.row_factory = sqlite3.Row
    return построить(соед)
