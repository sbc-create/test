"""Эфемерное хранилище черновиков.

Своё, а не общее. Общий Changeset Store в этой работе не изменяется ни на
строку: в нём остался хвост предыдущего этапа, и убирать его — работа
владельца хранилища, а не наша. Поэтому здесь отдельная база, путь к которой
задаётся вызывающим и по умолчанию не существует.

Устройство отвечает на два вопроса, которые обычно выясняются поздно:

* что произойдёт, если одно и то же событие придёт дважды — одновременно;
* что останется в базе, если процесс умрёт посреди записи.

Ответ на первый — уникальность ключа идемпотентности на уровне схемы, а не
проверка «нет ли уже такого» перед вставкой: между проверкой и вставкой
помещается второй процесс. Ответ на второй — одна транзакция на черновик и
связанное с ним предложение: половины записи не бывает, потому что
записывается всё сразу либо ничего.
"""
from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator, Mapping

from .draft import GateStatus, SEOContentDraft
from .factpack import SEOFactPack, canonical_json

СХЕМА = """
PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;

CREATE TABLE IF NOT EXISTS seo_fact_pack (
  fact_pack_sha256 TEXT PRIMARY KEY,
  site_id          TEXT NOT NULL,
  entity_type      TEXT NOT NULL,
  entity_id        TEXT NOT NULL,
  version          INTEGER NOT NULL,
  event_type       TEXT NOT NULL,
  event_id         TEXT NOT NULL,
  payload          TEXT NOT NULL,
  created_at       TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS seo_content_draft (
  draft_id            TEXT PRIMARY KEY,
  idempotency_key     TEXT NOT NULL,
  site_id             TEXT NOT NULL,
  entity_type         TEXT NOT NULL,
  entity_id           TEXT NOT NULL,
  locale              TEXT NOT NULL,
  fact_pack_sha256    TEXT NOT NULL REFERENCES seo_fact_pack(fact_pack_sha256),
  fact_pack_version   INTEGER NOT NULL,
  prompt_version      TEXT NOT NULL,
  model_version       TEXT NOT NULL,
  revision            INTEGER NOT NULL,
  quality_gate_status TEXT NOT NULL,
  content_sha256      TEXT NOT NULL,
  payload             TEXT NOT NULL,
  created_at          TEXT NOT NULL,
  UNIQUE (idempotency_key)
);
CREATE INDEX IF NOT EXISTS scd_entity
  ON seo_content_draft(site_id, entity_type, entity_id);

CREATE TABLE IF NOT EXISTS seo_editorial_note (
  note_id     TEXT PRIMARY KEY,
  draft_id    TEXT NOT NULL REFERENCES seo_content_draft(draft_id),
  site_id     TEXT NOT NULL,
  entity_id   TEXT NOT NULL,
  text_sha256 TEXT NOT NULL,
  payload     TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS seo_draft_event (
  seq        INTEGER PRIMARY KEY AUTOINCREMENT,
  draft_id   TEXT NOT NULL,
  kind       TEXT NOT NULL,
  detail     TEXT NOT NULL,
  created_at TEXT NOT NULL
);
"""


def открыть(путь: str | Path) -> sqlite3.Connection:
    п = Path(путь)
    п.parent.mkdir(parents=True, exist_ok=True)
    соед = sqlite3.connect(str(п), timeout=30, isolation_level=None)
    соед.row_factory = sqlite3.Row
    соед.executescript(СХЕМА)
    соед.execute("PRAGMA busy_timeout=30000")
    return соед


class DraftExists(Exception):
    """Черновик с этим ключом уже есть. Возвращается существующий."""

    def __init__(self, draft_id: str):
        super().__init__(draft_id)
        self.draft_id = draft_id


@contextmanager
def транзакция(соед: sqlite3.Connection) -> Iterator[sqlite3.Connection]:
    """IMMEDIATE: замок берётся сразу, а не при первой записи.

    С отложенным замком два процесса успевают прочитать одинаковое пустое
    состояние и разойтись в решении — и один из них проиграет уже после
    того, как счёл себя победителем.
    """
    соед.execute("BEGIN IMMEDIATE")
    try:
        yield соед
    except BaseException:
        соед.execute("ROLLBACK")
        raise
    соед.execute("COMMIT")


def draft_id_of(черновик: SEOContentDraft) -> str:
    return "draft-" + черновик.idempotency_key.removeprefix("seo-draft-")[:32]


def сохранить(соед: sqlite3.Connection, pack: SEOFactPack,
              черновик: SEOContentDraft, *,
              crash_hook=None) -> tuple[str, bool]:
    """Записать пакет, черновик и заметки одной транзакцией.

    Возврат: `(draft_id, создан_ли)`. Повтор того же ключа не создаёт второй
    записи и не является ошибкой вызывающего — это ожидаемый исход повторной
    доставки события.

    `crash_hook` вызывается внутри транзакции и нужен только испытаниям:
    брошенное из него исключение имитирует смерть процесса ровно в этой
    точке.
    """
    ид = draft_id_of(черновик)
    существующий = соед.execute(
        "SELECT draft_id FROM seo_content_draft WHERE idempotency_key = ?",
        (черновик.idempotency_key,)).fetchone()
    if существующий is not None:
        return существующий["draft_id"], False
    try:
        with транзакция(соед):
            соед.execute(
                "INSERT OR IGNORE INTO seo_fact_pack "
                "(fact_pack_sha256, site_id, entity_type, entity_id, version, "
                " event_type, event_id, payload, created_at) "
                "VALUES (?,?,?,?,?,?,?,?,?)",
                (pack.sha256, pack.site_id, pack.entity_type, pack.entity_id,
                 pack.version, pack.event_type, pack.event_id,
                 canonical_json(pack.payload()), черновик.created_at))
            if crash_hook is not None:
                crash_hook("after_fact_pack")
            соед.execute(
                "INSERT INTO seo_content_draft "
                "(draft_id, idempotency_key, site_id, entity_type, entity_id, "
                " locale, fact_pack_sha256, fact_pack_version, prompt_version, "
                " model_version, revision, quality_gate_status, content_sha256, "
                " payload, created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (ид, черновик.idempotency_key, черновик.site_id,
                 черновик.entity_type, черновик.entity_id, черновик.locale,
                 черновик.fact_pack_sha256, черновик.fact_pack_version,
                 черновик.prompt_version, черновик.model_version,
                 черновик.revision, черновик.quality_gate_status.value,
                 черновик.content_sha256,
                 canonical_json(черновик.payload()), черновик.created_at))
            if crash_hook is not None:
                crash_hook("after_draft")
            for н in черновик.editorial_notes:
                соед.execute(
                    "INSERT OR REPLACE INTO seo_editorial_note "
                    "(note_id, draft_id, site_id, entity_id, text_sha256, "
                    " payload) VALUES (?,?,?,?,?,?)",
                    (н.note_id, ид, н.site_id, н.entity_id, н.text_sha256,
                     canonical_json(н.to_dict())))
            if crash_hook is not None:
                crash_hook("after_notes")
            соед.execute(
                "INSERT INTO seo_draft_event (draft_id, kind, detail, created_at)"
                " VALUES (?,?,?,?)",
                (ид, "GATE_DECIDED", черновик.quality_gate_status.value,
                 черновик.created_at))
            if crash_hook is not None:
                crash_hook("after_event")
    except sqlite3.IntegrityError:
        # Второй процесс успел первым. Победитель один, и это не ошибка.
        строка = соед.execute(
            "SELECT draft_id FROM seo_content_draft WHERE idempotency_key = ?",
            (черновик.idempotency_key,)).fetchone()
        if строка is None:
            raise
        return строка["draft_id"], False
    return ид, True


def прочитать(соед: sqlite3.Connection, draft_id: str) -> dict[str, Any] | None:
    строка = соед.execute(
        "SELECT payload FROM seo_content_draft WHERE draft_id = ?",
        (draft_id,)).fetchone()
    return json.loads(строка["payload"]) if строка else None


def по_ключу(соед: sqlite3.Connection, ключ: str) -> dict[str, Any] | None:
    строка = соед.execute(
        "SELECT payload FROM seo_content_draft WHERE idempotency_key = ?",
        (ключ,)).fetchone()
    return json.loads(строка["payload"]) if строка else None


def счётчики(соед: sqlite3.Connection) -> dict[str, int]:
    """Состояние хранилища: дубли, сироты, распределение по исходам."""
    таблицы = {
        "fact_packs": "SELECT COUNT(*) FROM seo_fact_pack",
        "drafts": "SELECT COUNT(*) FROM seo_content_draft",
        "notes": "SELECT COUNT(*) FROM seo_editorial_note",
        "events": "SELECT COUNT(*) FROM seo_draft_event",
        "duplicate_drafts": (
            "SELECT COALESCE(SUM(n - 1), 0) FROM (SELECT COUNT(*) AS n FROM "
            "seo_content_draft GROUP BY idempotency_key HAVING n > 1)"),
        "orphan_notes": (
            "SELECT COUNT(*) FROM seo_editorial_note n LEFT JOIN "
            "seo_content_draft d ON d.draft_id = n.draft_id "
            "WHERE d.draft_id IS NULL"),
        "orphan_drafts": (
            "SELECT COUNT(*) FROM seo_content_draft d LEFT JOIN seo_fact_pack p "
            "ON p.fact_pack_sha256 = d.fact_pack_sha256 "
            "WHERE p.fact_pack_sha256 IS NULL"),
        "orphan_events": (
            "SELECT COUNT(*) FROM seo_draft_event e LEFT JOIN "
            "seo_content_draft d ON d.draft_id = e.draft_id "
            "WHERE d.draft_id IS NULL"),
    }
    итог = {имя: int(соед.execute(sql).fetchone()[0])
            for имя, sql in таблицы.items()}
    итог["orphan_records"] = (итог["orphan_notes"] + итог["orphan_drafts"]
                              + итог["orphan_events"])
    for исход in GateStatus:
        итог[f"status_{исход.value.lower()}"] = int(соед.execute(
            "SELECT COUNT(*) FROM seo_content_draft WHERE "
            "quality_gate_status = ?", (исход.value,)).fetchone()[0])
    return итог
