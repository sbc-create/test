"""Долговечное состояние индексации: одно решение, одна revision, один писатель.

Дефект, ради которого модуль существует. Решение «открыт ли сайт для поиска»
жило в профиле сайта, в реестре оператора и в списке доменов прямо в коде
посредника. Совпадали они случайно, и обычная выкладка возвращала посредника,
безусловно закрывающего витрину: живой сайт с поисковым трафиком закрывался
молча, без единой ошибки в логах.

Здесь решение одно и живёт в Action Ledger — том же самом, что и все остальные
решения флота. Второго журнала, второй базы и второй проекции не заводится:
``indexing.py`` не пишет события сам, он вызывает :func:`ledger_store.append` и
обновляет проекцию **внутри его транзакции**. Поэтому событие и состояние
появляются вместе или не появляются вовсе.

Кто что может, следует из уже объявленной модели полномочий журнала:

* у службы ``seo`` есть только ``OBSERVE`` и ``PROPOSE`` — записать состояние
  она не может структурно, а не по договорённости;
* у ``human_owner`` есть только ``AUTHORIZE`` — владелец разрешает, но не
  исполняет;
* исполняет служба с ``EXECUTE``, и только предъявив разрешение владельца.

Это и есть maker-checker: предложение, разрешение и исполнение — три разных
записи трёх разных акторов.

Что модуль сознательно НЕ делает: не строит карту сайта, не считает ``lastmod``,
не рисует мета-теги и не хранит наблюдаемое состояние рядом с желаемым. Желаемое
и наблюдаемое смешивать нельзя — система, где они равны по определению, не может
сообщить о расхождении.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
import uuid
from typing import Any

from factory.site_engine.audit.ledger_store import LedgerError, append, канон, сейчас

#: Версия схемы состояния. Потребитель обязан её проверять: неизвестная версия
#: означает «читать нельзя», а не «читать как раньше».
СХЕМА_СОСТОЯНИЯ = "fleet-indexing-state/1.0.0"

OPEN = "OPEN"
CLOSED = "CLOSED"
СОСТОЯНИЯ = (OPEN, CLOSED)

#: Тип события в общем журнале. Отдельного журнала под индексацию нет.
ТИП_ОТКРЫТЬ = "fleet.indexing.open.v1"
ТИП_ЗАКРЫТЬ = "fleet.indexing.close.v1"
ТИП_ДРЕЙФ = "fleet.indexing.drift_observed.v1"

#: Основание для сайта, о котором решения не принимали. Новый сайт закрыт, и
#: это записанный факт, а не умолчание «наверное, нельзя».
БЕЗ_РЕШЕНИЯ = "решения об индексации не принимали"

СХЕМА_SQL = """
CREATE TABLE IF NOT EXISTS indexing_state (
  site_id            TEXT PRIMARY KEY,
  desired_state      TEXT NOT NULL CHECK(desired_state IN ('OPEN','CLOSED')),
  revision           INTEGER NOT NULL CHECK(revision > 0),
  event_id           TEXT NOT NULL,
  source_event_id    TEXT,
  idempotency_key    TEXT NOT NULL,
  actor              TEXT NOT NULL,
  approval_id        TEXT NOT NULL,
  reason             TEXT NOT NULL,
  updated_at         TEXT NOT NULL,
  migration_batch_id TEXT,
  snapshot_digest    TEXT NOT NULL,
  schema_version     TEXT NOT NULL
);

-- История ревизий: проекция хранит текущее, журнал — как к нему пришли.
-- Таблица нужна для воспроизведения и для доказательства монотонности:
-- ревизия обязана расти независимо от того, совпало ли значение состояния.
CREATE TABLE IF NOT EXISTS indexing_revision (
  site_id       TEXT NOT NULL,
  revision      INTEGER NOT NULL,
  desired_state TEXT NOT NULL,
  event_id      TEXT NOT NULL,
  -- Разрешение хранится здесь, а не только в текущей строке проекции:
  -- проекция помнит лишь последнее решение, и по ней нельзя узнать, что
  -- прежнее разрешение уже израсходовано. Без этого одно разрешение
  -- открывало бы сайт повторно после любого промежуточного закрытия.
  approval_id   TEXT NOT NULL,
  ledger_seq    INTEGER NOT NULL,
  applied_at    TEXT NOT NULL,
  PRIMARY KEY (site_id, revision)
);

-- Одно разрешение — одно изменение. Ограничение на уровне хранилища, а не
-- проверки в коде: проверку можно обойти новой точкой входа, ограничение нет.
CREATE UNIQUE INDEX IF NOT EXISTS indexing_revision_approval
  ON indexing_revision(approval_id);

CREATE TABLE IF NOT EXISTS indexing_outbox (
  seq          INTEGER PRIMARY KEY AUTOINCREMENT,
  event_id     TEXT NOT NULL UNIQUE,
  site_id      TEXT NOT NULL,
  revision     INTEGER NOT NULL,
  payload      TEXT NOT NULL,
  occurred_at  TEXT NOT NULL,
  published_at TEXT
);
"""


def подготовить(соед: sqlite3.Connection) -> None:
    """Создать таблицы проекции. Идемпотентно."""
    соед.executescript(СХЕМА_SQL)


def _отпечаток(строки: list[dict[str, Any]]) -> str:
    """Отпечаток всей матрицы. Меняется от решений, а не от порядка ключей."""
    тело = [
        {"site_id": с["site_id"], "desired_state": с["desired_state"],
         "revision": с["revision"]}
        for с in sorted(строки, key=lambda x: x["site_id"])
    ]
    return hashlib.sha256(канон({"m": тело}).encode("utf-8")).hexdigest()


def _текущее(соед: sqlite3.Connection, site_id: str) -> dict[str, Any] | None:
    строка = соед.execute(
        "SELECT * FROM indexing_state WHERE site_id=?", (site_id,)).fetchone()
    return dict(строка) if строка else None


def _проверить_одобрение(
    соед: sqlite3.Connection, approval_id: str, *, site_id: str, целевое: str
) -> dict[str, Any]:
    """Разрешение владельца обязано существовать, относиться к этому сайту и
    к этому состоянию, и не быть уже использованным.

    Без последней проверки одно разрешение открывало бы сайт сколько угодно раз
    — а разрешение выдаётся на изменение, а не на право менять впредь.
    """
    строка = соед.execute(
        "SELECT * FROM ledger_event WHERE event_id=?", (approval_id,)).fetchone()
    if строка is None:
        raise LedgerError("APPROVAL_NOT_FOUND",
                          f"разрешение {approval_id!r} в журнале не найдено", 403)
    о = dict(строка)
    if о.get("phase") != "AUTHORIZED":
        raise LedgerError(
            "APPROVAL_NOT_AUTHORIZED",
            f"событие {approval_id} имеет фазу {о.get('phase')!r}, а не AUTHORIZED", 403)
    if о.get("authority") != "AUTHORIZE":
        raise LedgerError("APPROVAL_WITHOUT_AUTHORITY",
                          "разрешение выдано без полномочия AUTHORIZE", 403)
    if (о.get("site_id") or "") != site_id:
        raise LedgerError(
            "APPROVAL_SITE_MISMATCH",
            f"разрешение выдано сайту {о.get('site_id')!r}, а применяется к {site_id!r}", 403)
    ожидаемый_тип = ТИП_ОТКРЫТЬ if целевое == OPEN else ТИП_ЗАКРЫТЬ
    if (о.get("event_type") or "") != ожидаемый_тип:
        raise LedgerError(
            "APPROVAL_TARGET_MISMATCH",
            f"разрешение выдано на {о.get('event_type')!r}, а применяется "
            f"{ожидаемый_тип!r}: разрешение открыть не является разрешением закрыть",
            403)
    использовано = соед.execute(
        "SELECT site_id FROM indexing_revision WHERE approval_id=?", (approval_id,)
    ).fetchone()
    if использовано is not None:
        raise LedgerError(
            "APPROVAL_ALREADY_USED",
            f"разрешение {approval_id} уже применено: оно выдано на изменение, "
            "а не на право менять впредь", 409)
    return о


def _применить(
    соед: sqlite3.Connection, тело: dict[str, Any], seq: int, *,
    site_id: str, целевое: str, expected_revision: int | None,
    approval_id: str, reason: str, migration_batch_id: str | None,
) -> None:
    """Проекция и outbox в транзакции журнала. Здесь же — CAS.

    Проверка выполняется внутри ``BEGIN IMMEDIATE`` журнала, то есть конкуренцию
    разрешает само хранилище. Блокировка внутри процесса не годится: два
    экземпляра писателя её не разделяют.
    """
    текущее = _текущее(соед, site_id)
    было_rev = текущее["revision"] if текущее else 0

    if expected_revision is None:
        raise LedgerError("EXPECTED_REVISION_REQUIRED",
                          "expected_revision обязателен: слепая запись перетирает чужое")
    if expected_revision != было_rev:
        # Сравнение идёт по ревизии, а не по значению состояния. Иначе клиент,
        # уснувший на OPEN rev10, применил бы команду после
        # OPEN rev10 → CLOSED rev11 → OPEN rev12 только потому, что значение
        # снова OPEN. Это и есть ABA.
        raise LedgerError(
            "CAS_CONFLICT",
            f"{site_id}: ожидалась revision {expected_revision}, "
            f"фактическая {было_rev}", 409)

    _проверить_одобрение(соед, approval_id, site_id=site_id, целевое=целевое)

    новая = было_rev + 1
    момент = тело["stored_at"]
    строки = [dict(r) for r in соед.execute(
        "SELECT site_id, desired_state, revision FROM indexing_state "
        "WHERE site_id<>?", (site_id,))]
    строки.append({"site_id": site_id, "desired_state": целевое, "revision": новая})
    digest = _отпечаток(строки)

    соед.execute(
        "INSERT INTO indexing_state(site_id, desired_state, revision, event_id, "
        "source_event_id, idempotency_key, actor, approval_id, reason, updated_at, "
        "migration_batch_id, snapshot_digest, schema_version) "
        "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?) "
        "ON CONFLICT(site_id) DO UPDATE SET desired_state=excluded.desired_state, "
        "revision=excluded.revision, event_id=excluded.event_id, "
        "source_event_id=excluded.source_event_id, "
        "idempotency_key=excluded.idempotency_key, actor=excluded.actor, "
        "approval_id=excluded.approval_id, reason=excluded.reason, "
        "updated_at=excluded.updated_at, migration_batch_id=excluded.migration_batch_id, "
        "snapshot_digest=excluded.snapshot_digest, schema_version=excluded.schema_version",
        (site_id, целевое, новая, тело["event_id"], тело.get("causation_id"),
         тело["idempotency_key"], тело["actor_id"], approval_id, reason, момент,
         migration_batch_id, digest, СХЕМА_СОСТОЯНИЯ))

    соед.execute(
        "INSERT INTO indexing_revision(site_id, revision, desired_state, event_id, "
        "approval_id, ledger_seq, applied_at) VALUES(?,?,?,?,?,?,?)",
        (site_id, новая, целевое, тело["event_id"], approval_id, seq, момент))

    соед.execute(
        "INSERT INTO indexing_outbox(event_id, site_id, revision, payload, occurred_at) "
        "VALUES(?,?,?,?,?)",
        (тело["event_id"], site_id, новая,
         json.dumps({"site_id": site_id, "desired_state": целевое,
                     "revision": новая, "snapshot_digest": digest,
                     "schema_version": СХЕМА_СОСТОЯНИЯ}, ensure_ascii=False),
         момент))


def _команда(
    соед: sqlite3.Connection, *, site_id: str, целевое: str,
    expected_revision: int | None, approval_id: str, reason: str,
    idempotency_key: str, correlation_id: str, producer_service: str,
    actor_id: str, actor_type: str, authority: str,
    известные_сайты=None, migration_batch_id: str | None = None,
    occurred_at: str | None = None, event_id: str | None = None,
) -> dict[str, Any]:
    if целевое not in СОСТОЯНИЯ:
        raise LedgerError("UNKNOWN_DESIRED_STATE", f"состояние {целевое!r} не объявлено")
    if not (reason or "").strip():
        raise LedgerError("REASON_REQUIRED",
                          "решение без основания нельзя проверить на обзоре")

    событие = {
        "event_type": ТИП_ОТКРЫТЬ if целевое == OPEN else ТИП_ЗАКРЫТЬ,
        "phase": "SUCCEEDED",
        "result": "SUCCESS",
        "scope": "SITE",
        "site_id": site_id,
        "idempotency_key": idempotency_key,
        "correlation_id": correlation_id,
        "approval_ref": approval_id,
        "summary": reason,
        # Время запроса принадлежит запросу, а не моменту его обработки.
        # Повтор после таймаута обязан прислать ТО ЖЕ значение: журнал
        # сравнивает содержимое, и заново проставленное время делает повтор
        # другим запросом с тем же ключом — то есть жёстким конфликтом.
        "occurred_at": occurred_at or сейчас(),
        "event_id": event_id or str(uuid.uuid4()),
    }

    def проектор(с, тело, seq):
        _применить(с, тело, seq, site_id=site_id, целевое=целевое,
                   expected_revision=expected_revision, approval_id=approval_id,
                   reason=reason, migration_batch_id=migration_batch_id)

    итог = append(
        соед, событие, producer_service=producer_service, actor_id=actor_id,
        actor_type=actor_type, authority=authority,
        известные_сайты=известные_сайты, проекция=проектор,
    )
    текущее = _текущее(соед, site_id) or {}
    итог.update({"site_id": site_id, "desired_state": текущее.get("desired_state"),
                 "revision": текущее.get("revision"),
                 "snapshot_digest": текущее.get("snapshot_digest")})
    return итог


def открыть_индексацию(соед: sqlite3.Connection, **kw) -> dict[str, Any]:
    """Единственная команда, открывающая сайт для индексации."""
    return _команда(соед, целевое=OPEN, **kw)


def закрыть_индексацию(соед: sqlite3.Connection, **kw) -> dict[str, Any]:
    """Единственная команда, закрывающая сайт от индексации."""
    return _команда(соед, целевое=CLOSED, **kw)


def записать_дрейф(
    соед: sqlite3.Connection, *, site_id: str, observed: str, desired: str,
    idempotency_key: str, correlation_id: str, producer_service: str,
    actor_id: str, actor_type: str, authority: str, известные_сайты=None,
) -> dict[str, Any]:
    """Расхождение наблюдаемого с желаемым — диагностическое событие.

    Желаемое состояние оно НЕ меняет. Автоматическое приведение факта к
    замыслу означало бы, что система сама решает, чему верить, — а расхождение
    как раз и говорит, что верить пока нечему.
    """
    событие = {
        "event_type": ТИП_ДРЕЙФ, "phase": "OBSERVED", "result": "FAILURE",
        "scope": "SITE", "site_id": site_id,
        "idempotency_key": idempotency_key, "correlation_id": correlation_id,
        "summary": f"наблюдается {observed}, решение {desired}",
        "occurred_at": сейчас(), "event_id": str(uuid.uuid4()),
    }
    return append(соед, событие, producer_service=producer_service,
                  actor_id=actor_id, actor_type=actor_type, authority=authority,
                  известные_сайты=известные_сайты)


# --- чтение --------------------------------------------------------------------

def состояние(соед: sqlite3.Connection, site_id: str) -> dict[str, Any]:
    """Состояние одного сайта.

    Сайт без записанного решения получает ``CLOSED`` с основанием. Это не то
    же самое, что недоступность провайдера: там ответа нет вовсе, здесь ответ
    есть и он отрицательный.
    """
    текущее = _текущее(соед, site_id)
    if текущее is None:
        return {
            "site_id": site_id, "desired_state": CLOSED, "revision": 0,
            "event_id": None, "source_event_id": None, "approval_id": None,
            "reason": БЕЗ_РЕШЕНИЯ, "updated_at": None,
            "snapshot_digest": None, "schema_version": СХЕМА_СОСТОЯНИЯ,
            "registered": False,
        }
    текущее["registered"] = True
    return текущее


def снимок(соед: sqlite3.Connection) -> dict[str, Any]:
    """Вся матрица одной точкой чтения, с общим отпечатком."""
    строки = [dict(r) for r in соед.execute(
        "SELECT * FROM indexing_state ORDER BY site_id")]
    открытые = sorted(с["site_id"] for с in строки if с["desired_state"] == OPEN)
    закрытые = sorted(с["site_id"] for с in строки if с["desired_state"] == CLOSED)
    return {
        "schema_version": СХЕМА_СОСТОЯНИЯ,
        "sites": строки,
        "open": открытые,
        "closed": закрытые,
        "open_count": len(открытые),
        "closed_count": len(закрытые),
        "snapshot_digest": _отпечаток(строки),
        "taken_at": сейчас(),
    }


def проверить_монотонность(соед: sqlite3.Connection) -> dict[str, Any]:
    """Ревизии растут на единицу и не повторяются.

    Пропуск означает потерянное изменение, повтор — два решения под одним
    номером. И то и другое делает ссылку на ревизию бессмысленной.
    """
    пробелы, дубли = [], []
    for (site_id,) in соед.execute(
            "SELECT DISTINCT site_id FROM indexing_revision ORDER BY site_id"):
        ревизии = [r[0] for r in соед.execute(
            "SELECT revision FROM indexing_revision WHERE site_id=? ORDER BY revision",
            (site_id,))]
        ожидаемые = list(range(1, len(ревизии) + 1))
        if ревизии != ожидаемые:
            пробелы.append({"site_id": site_id, "revisions": ревизии})
        if len(set(ревизии)) != len(ревизии):
            дубли.append(site_id)
    return {"gaps": пробелы, "duplicates": дубли,
            "ok": not пробелы and not дубли}
