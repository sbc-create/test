"""Операционная проекция журнала.

Проекция — это индекс над сырым журналом, а не его копия. В ней хранится одна
строка на позицию журнала: исключена она из рабочих решений или нет, и по
какому решению. Содержимое событий не дублируется намеренно: копия немедленно
стала бы вторым источником истины, который можно поправить отдельно от
оригинала, и расхождение между ними никто бы не заметил.

Отсюда же следует главное свойство: проекция полностью пересобирается из
сырого журнала в любой момент. Потеря проекции — это потеря кэша, а не потеря
истории.

Переключение пересобранной проекции атомарно: активная таблица названа в
строке состояния, и подмена имени — одна транзакция. Промежуточного состояния,
в котором часть запросов видит старый индекс, а часть новый, не возникает.
"""
from __future__ import annotations

import json
import sqlite3
from typing import Any

from . import ledger_store as store
from . import quarantine as qr

ИМЯ_ПРОЕКЦИИ = "operational"
ОСНОВНАЯ = "operational_index"
ТЕНЕВАЯ = "operational_index_shadow"

СХЕМА = """
CREATE TABLE IF NOT EXISTS projection_state (
  name           TEXT PRIMARY KEY,
  active_table   TEXT NOT NULL,
  rollback_table TEXT,
  watermark_seq  INTEGER NOT NULL,
  event_count    INTEGER NOT NULL,
  excluded_count INTEGER NOT NULL,
  built_at       TEXT NOT NULL,
  source_commit  TEXT
);
"""

ТАБЛИЦА = """
CREATE TABLE IF NOT EXISTS {имя} (
  ledger_seq          INTEGER PRIMARY KEY,
  excluded            INTEGER NOT NULL DEFAULT 0,
  exclusion_reason    TEXT,
  quarantine_event_id TEXT
);
CREATE INDEX IF NOT EXISTS {имя}_excluded ON {имя}(excluded);
"""


def подготовить(соед: sqlite3.Connection) -> None:
    соед.executescript(СХЕМА)
    соед.executescript(ТАБЛИЦА.format(имя=ОСНОВНАЯ))
    соед.commit()


def активная(соед: sqlite3.Connection) -> str:
    р = соед.execute("SELECT active_table FROM projection_state WHERE name=?",
                     (ИМЯ_ПРОЕКЦИИ,)).fetchone()
    return р["active_table"] if р else ОСНОВНАЯ


def состояние(соед: sqlite3.Connection) -> dict[str, Any] | None:
    р = соед.execute("SELECT * FROM projection_state WHERE name=?",
                     (ИМЯ_ПРОЕКЦИИ,)).fetchone()
    return dict(р) if р else None


def _наполнить(соед: sqlite3.Connection, таблица: str, *,
               до_позиции: int) -> dict[str, int]:
    """Построить индекс до указанной отметки по решениям из самого журнала."""
    решения = qr.прочитать_решения(соед)
    соед.execute(f"DELETE FROM {таблица}")
    всего = исключено = 0
    for (seq,) in соед.execute(
            "SELECT ledger_seq FROM ledger_event WHERE ledger_seq <= ? "
            "ORDER BY ledger_seq", (до_позиции,)):
        решение = решения.get(seq)
        соед.execute(
            f"INSERT INTO {таблица}(ledger_seq, excluded, exclusion_reason, "
            "quarantine_event_id) VALUES(?,?,?,?)",
            (seq, 1 if решение else 0,
             qr.ПРИЧИНА_HARNESS if решение else None, решение))
        всего += 1
        исключено += 1 if решение else 0
    return {"total": всего, "excluded": исключено}


def пересобрать_в_тени(соед: sqlite3.Connection, *,
                       source_commit: str | None = None) -> dict[str, Any]:
    """Собрать проекцию заново в теневой таблице и сверить со старой.

    Отметка фиксируется ДО сборки: события, пришедшие во время работы, не
    должны попадать в сравнение как расхождение — их догоняет отдельный шаг.
    """
    подготовить(соед)
    отметка = соед.execute(
        "SELECT coalesce(max(ledger_seq), 0) s FROM ledger_event").fetchone()["s"]
    соед.executescript(ТАБЛИЦА.format(имя=ТЕНЕВАЯ))
    итог = _наполнить(соед, ТЕНЕВАЯ, до_позиции=отметка)
    соед.commit()

    текущая = активная(соед)
    было = {r[0] for r in соед.execute(
        f"SELECT ledger_seq FROM {текущая} WHERE excluded=1")} \
        if текущая != ТЕНЕВАЯ else set()
    стало = {r[0] for r in соед.execute(
        f"SELECT ledger_seq FROM {ТЕНЕВАЯ} WHERE excluded=1")}
    return {"watermark_seq": отметка, "event_count": итог["total"],
            "excluded_count": итог["excluded"],
            "newly_excluded": sorted(стало - было),
            "no_longer_excluded": sorted(было - стало),
            "shadow_table": ТЕНЕВАЯ, "active_table": текущая}


def догнать(соед: sqlite3.Connection, таблица: str, *,
            с_позиции: int) -> int:
    """Добавить в индекс события, пришедшие после отметки."""
    решения = qr.прочитать_решения(соед)
    добавлено = 0
    for (seq,) in соед.execute(
            "SELECT ledger_seq FROM ledger_event WHERE ledger_seq > ? "
            "ORDER BY ledger_seq", (с_позиции,)):
        решение = решения.get(seq)
        соед.execute(
            f"INSERT OR REPLACE INTO {таблица}(ledger_seq, excluded, "
            "exclusion_reason, quarantine_event_id) VALUES(?,?,?,?)",
            (seq, 1 if решение else 0,
             qr.ПРИЧИНА_HARNESS if решение else None, решение))
        добавлено += 1
    соед.commit()
    return добавлено


def переключить(соед: sqlite3.Connection, *,
                source_commit: str | None = None) -> dict[str, Any]:
    """Сделать теневую проекцию активной одной транзакцией."""
    отметка = соед.execute(
        f"SELECT coalesce(max(ledger_seq), 0) s FROM {ТЕНЕВАЯ}").fetchone()["s"]
    догнать(соед, ТЕНЕВАЯ, с_позиции=отметка)
    итог = соед.execute(
        f"SELECT count(*) n, sum(excluded) e FROM {ТЕНЕВАЯ}").fetchone()
    прежняя = активная(соед)
    with соед:
        соед.execute(
            "INSERT INTO projection_state(name, active_table, rollback_table, "
            "watermark_seq, event_count, excluded_count, built_at, source_commit) "
            "VALUES(?,?,?,?,?,?,?,?) ON CONFLICT(name) DO UPDATE SET "
            "active_table=excluded.active_table, "
            "rollback_table=excluded.rollback_table, "
            "watermark_seq=excluded.watermark_seq, "
            "event_count=excluded.event_count, "
            "excluded_count=excluded.excluded_count, "
            "built_at=excluded.built_at, source_commit=excluded.source_commit",
            (ИМЯ_ПРОЕКЦИИ, ТЕНЕВАЯ, прежняя,
             соед.execute(f"SELECT coalesce(max(ledger_seq),0) s FROM {ТЕНЕВАЯ}")
             .fetchone()["s"], итог["n"], итог["e"] or 0, store.сейчас(),
             source_commit))
    return {"active_table": ТЕНЕВАЯ, "rollback_table": прежняя,
            "event_count": итог["n"], "excluded_count": итог["e"] or 0}


def пересобрать(соед: sqlite3.Connection, *,
                source_commit: str | None = None) -> dict[str, Any]:
    """Полная пересборка с переключением — обычный путь обслуживания."""
    тень = пересобрать_в_тени(соед, source_commit=source_commit)
    итог = переключить(соед, source_commit=source_commit)
    return {**тень, **итог}


def позиции_в_карантине(соед: sqlite3.Connection) -> set[int]:
    т = активная(соед)
    try:
        return {r[0] for r in соед.execute(
            f"SELECT ledger_seq FROM {т} WHERE excluded=1")}
    except sqlite3.OperationalError:
        return set()


def условие(соед: sqlite3.Connection, *, включая_карантин: bool) -> str:
    """Фрагмент SQL, ограничивающий выборку рабочими событиями."""
    if включая_карантин:
        return ""
    т = активная(соед)
    return (f" AND ledger_seq NOT IN (SELECT ledger_seq FROM {т} "
            "WHERE excluded=1)")
