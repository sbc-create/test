"""Локальная проекция сайтов: восстановимый кэш, а не источник правды.

Проекция существует ровно для двух вещей: ответить, когда Registry
недоступен, и не спрашивать Registry на каждый чих. Всё остальное про неё —
запреты.

Она обязана уметь сказать о себе правду. Ответ несёт `свежая`: `False`
означает, что данные взяты из кэша и Registry в этот момент не отвечал. На
такой проекции разрешено только наблюдение; план, применение и откат
блокируются вызывающим кодом. Тихо выдать вчерашний список за сегодняшний
— это тот самый случай, когда система выглядит работающей и потому не
чинится.

Хранилище — SQLite: курсор и проекция обязаны пережить перезапуск и
падение. Файл в памяти процесса этого не умеет.
"""

from __future__ import annotations

import json
import sqlite3
import time
from dataclasses import dataclass
from typing import Iterable

from factory.templates_cp.registry_client import Сайт, Снимок

СХЕМА = """
CREATE TABLE IF NOT EXISTS site (
  site_id          TEXT PRIMARY KEY,
  family           TEXT,
  canonical_domain TEXT,
  aliases          TEXT NOT NULL DEFAULT '[]',
  environment      TEXT,
  lifecycle_state  TEXT,
  registry_version INTEGER,
  -- Сайт, ушедший из production ACTIVE, отключается, но не удаляется:
  -- Registry его помнит, и проекция обязана помнить тоже.
  active           INTEGER NOT NULL DEFAULT 1,
  updated_at       TEXT NOT NULL,
  raw              TEXT NOT NULL DEFAULT '{}'
);
CREATE TABLE IF NOT EXISTS meta (
  key   TEXT PRIMARY KEY,
  value TEXT NOT NULL
);
-- Обработанные события: идемпотентность по event_id. Повтор доставки —
-- норма для at-least-once, и он не должен создавать второй эффект.
CREATE TABLE IF NOT EXISTS seen_event (
  event_id    TEXT PRIMARY KEY,
  seq         INTEGER NOT NULL,
  event_type  TEXT NOT NULL,
  processed_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS dlq (
  event_id   TEXT PRIMARY KEY,
  seq        INTEGER,
  payload    TEXT NOT NULL,
  reason     TEXT NOT NULL,
  attempts   INTEGER NOT NULL,
  first_at   TEXT NOT NULL,
  last_at    TEXT NOT NULL
);
"""


@dataclass(frozen=True)
class Ответ:
    """Список сайтов вместе с честным признаком свежести."""
    сайты: tuple[Сайт, ...]
    registry_version: int | None
    свежая: bool
    источник: str

    @property
    def идентификаторы(self) -> frozenset[str]:
        return frozenset(с.site_id for с in self.сайты)


def _сейчас() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


class Проекция:
    def __init__(self, путь: str) -> None:
        self.путь = путь
        self.соед = sqlite3.connect(путь, timeout=10)
        self.соед.row_factory = sqlite3.Row
        self.соед.execute("PRAGMA journal_mode=WAL")
        self.соед.executescript(СХЕМА)
        self.соед.commit()

    def закрыть(self) -> None:
        self.соед.close()

    # --- метаданные -----------------------------------------------------
    def _мета(self, ключ: str) -> str | None:
        с = self.соед.execute("SELECT value FROM meta WHERE key=?", (ключ,)).fetchone()
        return с["value"] if с else None

    def _записать_мета(self, ключ: str, значение: str) -> None:
        self.соед.execute(
            "INSERT INTO meta(key,value) VALUES(?,?) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value", (ключ, значение))

    @property
    def курсор(self) -> str | None:
        return self._мета("cursor")

    @property
    def registry_version(self) -> int | None:
        з = self._мета("registry_version")
        return int(з) if з else None

    @property
    def последняя_сверка(self) -> float:
        з = self._мета("last_reconcile_ts")
        return float(з) if з else 0.0

    # --- запись ---------------------------------------------------------
    def применить_снимок(self, снимок: Снимок) -> None:
        """Полная сверка: проекция приводится к снимку Registry.

        Сайты, которых в снимке нет, не удаляются — они отключаются.
        Удаление стирало бы факт, который Registry помнит.
        """
        активные = снимок.идентификаторы
        with self.соед:
            for с in снимок.сайты:
                self._записать_сайт(с, снимок.registry_version, активен=True)
            # Отключается всё, чего нет в снимке. Скобки здесь не украшение:
            # тернарный оператор связывает слабее %, и без них строка
            # форматировалась бы только в одной ветке.
            if активные:
                места = ",".join("?" * len(активные))
                self.соед.execute(
                    f"UPDATE site SET active=0, updated_at=? WHERE site_id NOT IN ({места})",
                    (_сейчас(), *sorted(активные)))
            else:
                self.соед.execute("UPDATE site SET active=0, updated_at=?", (_сейчас(),))
            self._записать_мета("registry_version", str(снимок.registry_version))
            self._записать_мета("last_reconcile_ts", str(time.time()))

    def _записать_сайт(self, с: Сайт, версия: int | None, активен: bool) -> None:
        self.соед.execute(
            "INSERT INTO site(site_id,family,canonical_domain,aliases,environment,"
            "lifecycle_state,registry_version,active,updated_at,raw) "
            "VALUES(?,?,?,?,?,?,?,?,?,?) "
            "ON CONFLICT(site_id) DO UPDATE SET family=excluded.family,"
            "canonical_domain=excluded.canonical_domain,aliases=excluded.aliases,"
            "environment=excluded.environment,lifecycle_state=excluded.lifecycle_state,"
            "registry_version=excluded.registry_version,active=excluded.active,"
            "updated_at=excluded.updated_at,raw=excluded.raw",
            (с.site_id, с.family, с.canonical_domain, json.dumps(list(с.aliases)),
             с.environment, с.lifecycle_state, версия, 1 if активен else 0,
             _сейчас(), json.dumps(с.сырое, ensure_ascii=False)))

    def отключить(self, site_id: str, версия: int | None) -> None:
        with self.соед:
            self.соед.execute(
                "UPDATE site SET active=0, lifecycle_state=?, registry_version=?, updated_at=? "
                "WHERE site_id=?", ("RETIRED", версия, _сейчас(), site_id))

    # --- идемпотентность и курсор ---------------------------------------
    def уже_обработано(self, event_id: str) -> bool:
        return self.соед.execute(
            "SELECT 1 FROM seen_event WHERE event_id=?", (event_id,)).fetchone() is not None

    def зафиксировать(self, событие: dict, курсор: str | None) -> None:
        """Одна транзакция: эффект события, отметка и курсор.

        Курсор двигается ТОЛЬКО вместе с сохранённой проекцией. Если
        подтвердить раньше записи, падение между ними потеряет событие
        навсегда — и никто об этом не узнает.
        """
        with self.соед:
            self.соед.execute(
                "INSERT OR IGNORE INTO seen_event(event_id,seq,event_type,processed_at) "
                "VALUES(?,?,?,?)",
                (событие["event_id"], событие.get("seq"), событие.get("event_type"), _сейчас()))
            if курсор is not None:
                self._записать_мета("cursor", str(курсор))
            if событие.get("registry_version") is not None:
                self._записать_мета("registry_version", str(событие["registry_version"]))

    def в_dlq(self, событие: dict, причина: str, попыток: int) -> None:
        with self.соед:
            self.соед.execute(
                "INSERT INTO dlq(event_id,seq,payload,reason,attempts,first_at,last_at) "
                "VALUES(?,?,?,?,?,?,?) ON CONFLICT(event_id) DO UPDATE SET "
                "attempts=excluded.attempts,last_at=excluded.last_at,reason=excluded.reason",
                (событие.get("event_id"), событие.get("seq"),
                 json.dumps(событие, ensure_ascii=False), причина, попыток,
                 _сейчас(), _сейчас()))

    @property
    def глубина_dlq(self) -> int:
        return self.соед.execute("SELECT COUNT(*) c FROM dlq").fetchone()["c"]

    # --- чтение ---------------------------------------------------------
    def производственные(self, свежая: bool, источник: str) -> Ответ:
        строки = self.соед.execute(
            "SELECT * FROM site WHERE active=1 AND environment='production' "
            "AND lifecycle_state='ACTIVE' ORDER BY site_id").fetchall()
        сайты = tuple(Сайт(site_id=с["site_id"], family=с["family"],
                           canonical_domain=с["canonical_domain"],
                           aliases=tuple(json.loads(с["aliases"])),
                           environment=с["environment"], lifecycle_state=с["lifecycle_state"],
                           сырое=json.loads(с["raw"])) for с in строки)
        return Ответ(сайты=сайты, registry_version=self.registry_version,
                     свежая=свежая, источник=источник)

    def все(self) -> Iterable[sqlite3.Row]:
        return self.соед.execute("SELECT * FROM site ORDER BY site_id").fetchall()
