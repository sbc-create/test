"""HTTP-слой Audit Ledger. Только append и чтение; изменение невозможно.

PUT, PATCH и DELETE не объявлены не по недосмотру: журнал фактов, который
умеет переписывать факт, перестаёт быть журналом. Исправление — новое
событие со ссылкой `corrects_event_id`.
"""

from __future__ import annotations

import json
import os
import sqlite3
import sys
from pathlib import Path
from typing import Any

from . import ledger_identity as ident
from . import ledger_store as store
from . import projection as proj

БД_ПО_УМОЛЧАНИЮ = "/srv/site-factory/audit-ledger/audit_ledger.sqlite3"
РЕЕСТР_ПО_УМОЛЧАНИЮ = "/srv/site-factory/registry-core/registry.sqlite3"

#: Поля, по которым разрешена фильтрация. Перечень закрыт: неизвестное имя
#: фильтра — ошибка вызывающего, а не повод отдать всё подряд.
ФИЛЬТРЫ = ("site_id", "producer_service", "actor_type", "event_type", "phase",
           "result", "action_id", "change_set_id", "correlation_id",
           "prompt_id", "environment", "resource_type", "resource_id")
ВРЕМЕННЫЕ = ("occurred_from", "occurred_to")
СЛУЖЕБНЫЕ = ("after", "limit")

#: Корни, из которых разрешено брать доказательства. Всё вне их — отказ.
ДОПУСТИМЫЕ_КОРНИ = ("/srv/site-factory/control-plane-contracts/evidence",
                    "/srv/site-factory/registry-core/evidence",
                    "/srv/site-factory/audit-ledger/evidence")


def _бд(путь: str | None = None) -> sqlite3.Connection:
    return store.открыть(os.environ.get("AUDIT_LEDGER_DB") or путь
                         or БД_ПО_УМОЛЧАНИЮ)


def известные_сайты() -> set[str]:
    п = os.environ.get("REGISTRY_DB") or РЕЕСТР_ПО_УМОЛЧАНИЮ
    if not Path(п).exists():
        return set()
    с = sqlite3.connect(f"file:{п}?mode=ro", uri=True)
    try:
        return {r[0] for r in с.execute("SELECT site_id FROM site")}
    finally:
        с.close()


def _ответ(код: int, тело: Any) -> tuple[int, Any]:
    return код, тело


def _проблема(код: int, error_code: str, detail: str,
              corr: str | None = None) -> tuple[int, Any]:
    return код, {
        "type": "https://contracts.site-factory.internal/problems/audit",
        "title": "Ошибка журнала аудита", "status": код, "detail": detail,
        "instance": "/api/v1/audit", "error_code": error_code,
        "retryable": код in (429, 503), "owner": "architect",
        "correlation_id": corr,
        "safe_public_detail": "запрос к журналу аудита не выполнен"}


def _строка(р: sqlite3.Row) -> dict[str, Any]:
    d = dict(р)
    d["evidence_refs"] = json.loads(d.get("evidence_refs") or "[]")
    return d


def обработать(метод: str, путь: str, *, query: dict | None = None,
               body: dict | None = None,
               headers: dict | None = None) -> tuple[int, Any]:
    заг = {str(k).lower(): v for k, v in (headers or {}).items()}
    части = [c for c in путь.strip("/").split("/") if c]
    if части[:3] != ["api", "v1", "audit"]:
        return _проблема(404, "NOT_FOUND", "не маршрут журнала")
    rest = части[3:]
    метод = метод.upper()

    if метод in ("PUT", "PATCH", "DELETE"):
        # Отвечаем 405, а не 404: маршрут существует, но изменение факта
        # запрещено по устройству, и об этом лучше сказать прямо.
        return _проблема(405, "APPEND_ONLY",
                         "журнал только для добавления: изменение и удаление "
                         "события невозможны; исправление — новым событием")

    if метод == "POST" and rest == ["events"]:
        try:
            кто = ident.опознать(заг)
        except ident.IdentityError as e:
            return _проблема(e.status, e.error_code, e.detail)
        тело = body or {}
        полномочие = str(тело.get("authority") or "OBSERVE").upper()
        соед = _бд()
        try:
            итог = store.append(соед, тело,
                                producer_service=кто["producer_service"],
                                actor_id=кто["actor_id"],
                                actor_type=кто["actor_type"],
                                authority=полномочие,
                                известные_сайты=известные_сайты() or None)
        except store.LedgerError as e:
            return _проблема(e.status, e.error_code, e.detail,
                             тело.get("correlation_id"))
        finally:
            соед.close()
        return _ответ(201 if not итог["idempotent_replay"] else 200, итог)

    if метод != "GET":
        return _проблема(405, "METHOD_NOT_ALLOWED", "метод не поддержан")

    q = {k: (v[-1] if isinstance(v, (list, tuple)) else v)
         for k, v in (query or {}).items()}
    multi = getattr(query, "multi", None) or {}

    # Две поверхности с разными правами. Сырая лента показывает полную историю
    # вместе с собственными ошибками системы — её читают разбирающие историю.
    # Рабочая проекция открыта всем опознанным службам: по ней принимаются
    # решения, и закрывать её значило бы закрыть работу.
    открытые = (["health"], ["integrity"], ["checkpoints", "latest"],
                ["projection"])
    операционный = rest[:1] == ["operational"]
    if операционный:
        rest = rest[1:]
    if rest not in открытые:
        роль = "producer" if операционный or rest[:1] in (
            ["actions"], ["correlations"], ["sites"], ["resources"]) \
            else "audit-admin"
        try:
            читатель = ident.требовать_роль(заг, роль)
        except ident.IdentityError as e:
            return _проблема(e.status, e.error_code, e.detail)
    else:
        читатель = None

    # Карантинные события показываются только по явному запросу и только
    # audit/admin: иначе «полная картина» незаметно вернулась бы в рабочие
    # решения через параметр, который удобно передать.
    просят_карантин = str(q.pop("include_quarantined", "")).lower() in (
        "1", "true", "yes")
    if просят_карантин and (not читатель
                            or "audit-admin" not in читатель["roles"]):
        return _проблема(403, "ROLE_DENIED",
                         "include_quarantined доступен только роли audit-admin")
    включая = просят_карантин or (not операционный and rest == ["events"])

    соед = _бд()
    try:
        if rest == ["health"]:
            п = store.проверить_цепь(соед)
            n = соед.execute("SELECT count(*) c FROM ledger_event").fetchone()["c"]
            bl = соед.execute("SELECT count(*) c FROM ledger_outbox "
                              "WHERE published_at IS NULL").fetchone()["c"]
            # Разорванная цепь снимает готовность: писать в журнал, чья
            # история уже под сомнением, значит углублять сомнение.
            return _ответ(200 if п["ok"] else 503,
                          {"status": "ok" if п["ok"] else "chain_broken",
                           "ready": п["ok"], "event_count": n,
                           "outbox_backlog": bl,
                           "tamper_evidence_level": "LOCAL_HASH_CHAIN"})
        if rest == ["integrity"]:
            п = store.проверить_цепь(соед)
            return _ответ(200 if п["ok"] else 409, п)
        if rest == ["checkpoints", "latest"]:
            р = соед.execute("SELECT * FROM ledger_checkpoint "
                             "ORDER BY ledger_seq DESC LIMIT 1").fetchone()
            return _ответ(200, dict(р) if р else {"checkpoint_id": None})
        if rest[:1] == ["events"] and len(rest) == 2:
            р = соед.execute("SELECT * FROM ledger_event WHERE event_id=?",
                             (rest[1],)).fetchone()
            return _ответ(200, _строка(р)) if р else _проблема(
                404, "EVENT_NOT_FOUND", "события с таким идентификатором нет")
        if rest == ["projection"]:
            сост = proj.состояние(соед) or {}
            return _ответ(200, {
                "projection": proj.ИМЯ_ПРОЕКЦИИ,
                "active_table": proj.активная(соед),
                "rebuildable_from": "ledger_event",
                **сост})
        if rest[:1] == ["actions"] and len(rest) == 2:
            return _нить(соед, "action_id", rest[1], включая=включая)
        if rest[:1] == ["correlations"] and len(rest) == 2:
            return _нить(соед, "correlation_id", rest[1], включая=включая)
        if rest[:1] == ["sites"] and len(rest) == 2:
            строки = [_строка(r) for r in соед.execute(
                "SELECT * FROM ledger_event WHERE site_id=? ORDER BY ledger_seq",
                (rest[1],))]
            return _ответ(200, {"site_id": rest[1], "items": строки,
                                "count": len(строки)})
        if rest[:1] == ["resources"] and len(rest) == 3:
            строки = [_строка(r) for r in соед.execute(
                "SELECT * FROM ledger_event WHERE resource_type=? AND "
                "resource_id=? ORDER BY ledger_seq", (rest[1], rest[2]))]
            return _ответ(200, {"resource_type": rest[1],
                                "resource_id": rest[2], "items": строки,
                                "count": len(строки)})
        if rest[:1] == ["evidence"] and len(rest) == 3 and rest[2] == "metadata":
            return _доказательство(соед, rest[1])
        if rest == ["events"]:
            return _список(соед, q, multi, включая=включая,
                           поверхность="raw" if включая and not операционный
                           else "operational")
        return _проблема(404, "NOT_FOUND", "маршрут журнала не найден")
    finally:
        соед.close()


def _нить(соед, поле: str, значение: str, *,
          включая: bool) -> tuple[int, Any]:
    """Нить действия или корреляции.

    По умолчанию нить рабочая. Число скрытых карантинных событий показывается
    отдельным счётчиком: молча укоротить нить значило бы спрятать от читателя
    сам факт, что часть истории к решениям не допущена.
    """
    исключены = proj.позиции_в_карантине(соед)
    все = [dict(r) for r in соед.execute(
        f"SELECT * FROM ledger_event WHERE {поле}=? ORDER BY ledger_seq",
        (значение,))]
    в_карантине = [r for r in все if r["ledger_seq"] in исключены]
    видимые = все if включая else [r for r in все
                                   if r["ledger_seq"] not in исключены]
    return _ответ(200, {
        поле: значение,
        "items": [_строка(r) for r in видимые],
        "count": len(видимые),
        "quarantined_count": len(в_карантине),
        "surface": "raw" if включая else "operational",
    })


def _список(соед, q: dict, multi: dict, *, включая: bool = True,
            поверхность: str = "raw") -> tuple[int, Any]:
    неизвестные = [k for k in q
                   if k not in ФИЛЬТРЫ + ВРЕМЕННЫЕ + СЛУЖЕБНЫЕ]
    if неизвестные:
        return _проблема(422, "FILTER_UNKNOWN",
                         f"неизвестные параметры фильтра: {sorted(неизвестные)}")
    for k, v in multi.items():
        if k in ФИЛЬТРЫ and len({str(x) for x in v}) > 1:
            return _проблема(422, "FILTER_VALUE_CONFLICT",
                             f"параметр {k} повторён с разными значениями")
    for k in ФИЛЬТРЫ + ВРЕМЕННЫЕ:
        if k in q and not str(q[k]).strip():
            return _проблема(422, "FILTER_VALUE_EMPTY",
                             f"параметр {k} задан пустым значением")
    где, знач = [], []
    for k in ФИЛЬТРЫ:
        if k in q:
            где.append(f"{k} = ?")
            знач.append(q[k])
    if "occurred_from" in q:
        где.append("received_at >= ?"); знач.append(q["occurred_from"])
    if "occurred_to" in q:
        где.append("received_at <= ?"); знач.append(q["occurred_to"])
    try:
        after = int(q.get("after", 0))
        limit = min(int(q.get("limit", 100)), 1000)
    except (TypeError, ValueError):
        return _проблема(422, "FILTER_VALUE_INVALID",
                         "after и limit обязаны быть целыми")
    где.append("ledger_seq > ?"); знач.append(after)
    sql = ("SELECT * FROM ledger_event WHERE " + " AND ".join(где)
           + proj.условие(соед, включая_карантин=включая)
           + " ORDER BY ledger_seq LIMIT ?")
    строки = [_строка(r) for r in соед.execute(sql, знач + [limit])]
    return _ответ(200, {
        "items": строки, "count": len(строки), "surface": поверхность,
        # Курсор по ledger_seq: он монотонен и не смещается при конкурентной
        # записи, в отличие от offset, который «съезжает» на каждой вставке.
        "next_cursor": строки[-1]["ledger_seq"] if строки else after,
        "filters_applied": {k: q[k] for k in ФИЛЬТРЫ if k in q}})


def _доказательство(соед, evidence_id: str) -> tuple[int, Any]:
    """Метаданные доказательства с проверкой хэша и границ корня."""
    for р in соед.execute("SELECT evidence_refs FROM ledger_event "
                          "WHERE evidence_refs != '[]'"):
        for e in json.loads(р["evidence_refs"]):
            if e.get("evidence_id") != evidence_id:
                continue
            uri = str(e.get("uri") or "")
            путь = os.path.realpath(uri)
            # Выход за пределы разрешённых корней запрещён: иначе ссылка в
            # событии становится произвольным чтением файлов службы.
            if not any(путь.startswith(os.path.realpath(k) + os.sep)
                       for k in ДОПУСТИМЫЕ_КОРНИ):
                return _проблема(403, "EVIDENCE_PATH_DENIED",
                                 "ссылка выходит за разрешённые корни")
            если_есть = Path(путь)
            метаданные = dict(e)
            if не_существует := (not если_есть.is_file()):
                метаданные["verified"] = False
                метаданные["verification"] = "MISSING"
            else:
                import hashlib as _h
                факт = _h.sha256(если_есть.read_bytes()).hexdigest()
                метаданные["verified"] = (факт == e.get("checksum"))
                метаданные["verification"] = (
                    "OK" if факт == e.get("checksum") else "HASH_MISMATCH")
                метаданные["actual_sha256"] = факт
            return _ответ(200, метаданные)
    return _проблема(404, "EVIDENCE_NOT_FOUND", "доказательства нет в журнале")
