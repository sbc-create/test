"""HTTP-поверхность контура изменений.

Клиент просит выполнить ДЕЙСТВИЕ и никогда не записывает состояние. Поля
`status` в теле запроса не существует: состояние — вывод сервера, а не
утверждение отправителя. Попытка изменить набор целиком (PUT/PATCH) или
удалить его отклоняется — история решений не переписывается.

Личность выводится из служебного токена тем же механизмом, что и в журнале
аудита. Вторая схема прав рядом с первой означала бы, что однажды сработает
не та.
"""
from __future__ import annotations

import json
import os
from typing import Any

from ..audit import ledger_identity as ident
from . import audit_bridge as AB
from . import engine as E
from . import model as M
from . import policy as POL
from . import store as S

ФИЛЬТРЫ = ("status", "resource_type", "resource_id", "producer_service",
           "actor_id", "risk_class", "impact_level", "site_id",
           "correlation_id")

СЛУЖЕБНЫЕ = ("after", "limit")

#: Действия и роль, которой они требуют.
ДЕЙСТВИЯ = {
    "validate": M.VALIDATOR,
    "approve": M.APPROVER,
    "reject": M.APPROVER,
    "apply": M.EXECUTOR,
    "rollback": M.EXECUTOR,
    "cancel": M.PROPOSER,
    "revoke-approval": M.APPROVER,
}


def _ответ(код: int, тело: Any) -> tuple[int, Any]:
    return код, тело


def _проблема(код: int, error_code: str, detail: str,
              correlation_id: str | None = None) -> tuple[int, Any]:
    return код, {
        "type": "https://contracts.site-factory.internal/problems/changeset",
        "title": "Ошибка контура изменений", "status": код, "detail": detail,
        "instance": "/api/v1/changesets", "error_code": error_code,
        "retryable": код in (409, 503), "owner": "control-plane",
        "correlation_id": correlation_id,
        "safe_public_detail": "запрос к контуру изменений не выполнен",
    }


def _соед():
    return S.открыть()


def _версия_из_etag(значение: str) -> int:
    """Разобрать If-Match. Принимается и слабая форма: W/"7"."""
    з = значение.strip()
    if з.startswith("W/"):
        з = з[2:].strip()
    return int(з.strip('"'))


def _ожидаемая_версия(тело: dict, заг: dict) -> int | None:
    """Версия ресурса, на которую опирается клиент.

    Принимается и полем тела, и заголовком If-Match: первым удобно клиенту
    контура, вторым — обычному HTTP-посреднику. Когда заданы оба и они
    расходятся, запрос отклоняется: выбрать за клиента, какое из двух его
    намерений настоящее, нельзя — а угадав, можно применить изменение поверх
    той картины, которую он как раз и не подтверждал.
    """
    из_тела = тело.get("expected_resource_version")
    сырой = заг.get("if-match")
    из_заг = None
    if сырой not in (None, "", "*"):
        try:
            из_заг = _версия_из_etag(str(сырой))
        except ValueError:
            raise ValueError(f"If-Match не версия ресурса: {сырой!r}") from None
    if из_тела is not None:
        if isinstance(из_тела, bool) or not isinstance(из_тела, int):
            raise ValueError("expected_resource_version — целое число")
        if из_заг is not None and из_заг != из_тела:
            raise ValueError(
                f"expected_resource_version={из_тела} и If-Match={из_заг} "
                f"расходятся")
        return из_тела
    return из_заг


def _идентификатор_запроса(тело: dict, заг: dict) -> str:
    return str(тело.get("request_id") or заг.get("x-request-id") or "")[:200]


def обработать(метод: str, путь: str, *, query: dict | None = None,
               body: dict | None = None,
               headers: dict | None = None) -> tuple[int, Any, dict[str, str]]:
    """Разобрать запрос и вернуть (код, тело, заголовки).

    Заголовки отделены от тела намеренно: версия ресурса нужна посреднику,
    который тела не разбирает, — иначе условный запрос пришлось бы собирать,
    предварительно распарсив ответ.
    """
    итог = _маршрутизировать(метод, путь, query=query, body=body,
                             headers=headers)
    if len(итог) == 3:
        return итог  # type: ignore[return-value]
    код, тело = итог
    return код, тело, {}


def _маршрутизировать(метод: str, путь: str, *, query: dict | None = None,
                      body: dict | None = None,
                      headers: dict | None = None) -> tuple:
    заг = {str(k).lower(): v for k, v in (headers or {}).items()}
    части = [c for c in путь.strip("/").split("/") if c]
    метод = метод.upper()
    if части[:2] != ["api", "v1"]:
        return _проблема(404, "NOT_FOUND", "не маршрут контура изменений")
    rest = части[2:]

    if метод in ("PUT", "PATCH", "DELETE"):
        return _проблема(
            405, "ACTION_ONLY",
            "набор изменений не редактируется и не удаляется: состояние "
            "меняется только действиями, а история решений сохраняется")

    if rest[:1] == ["workflows"]:
        return _процессы(rest, метод)

    if rest[:1] != ["changesets"]:
        return _проблема(404, "NOT_FOUND", "не маршрут контура изменений")

    try:
        кто = ident.опознать(заг)
    except ident.IdentityError as e:
        return _проблема(e.status, e.error_code, e.detail)
    служба = кто["producer_service"]
    actor_id = кто["actor_id"]
    actor_type = кто["actor_type"]

    try:
        ожидаемая = _ожидаемая_версия(body or {}, заг)
    except ValueError as e:
        return _проблема(422, "EXPECTED_VERSION_INVALID", str(e))
    request_id = _идентификатор_запроса(body or {}, заг)

    соед = _соед()
    try:
        if метод == "POST" and rest == ["changesets"]:
            return _создать(соед, body or {}, служба, actor_id, actor_type)
        if метод == "GET" and rest == ["changesets"]:
            return _список(соед, query or {})
        if метод == "GET" and len(rest) == 2:
            набор = S.получить(соед, rest[1])
            if not набор:
                return _проблема(404, "CHANGESET_NOT_FOUND", "набора нет")
            # Версия ресурса отдаётся так, чтобы её можно было вернуть
            # обратно в If-Match, не вычитывая из тела.
            return 200, набор, {"ETag": f'"{набор["version"]}"'}
        if метод == "GET" and len(rest) == 3 and rest[2] == "transitions":
            набор = S.получить(соед, rest[1])
            if not набор:
                return _проблема(404, "CHANGESET_NOT_FOUND", "набора нет")
            return _ответ(200, {"changeset_id": rest[1],
                                "items": набор["transitions"],
                                "count": len(набор["transitions"])})
        if метод == "POST" and len(rest) == 3 and rest[2] in ДЕЙСТВИЯ:
            return _действие(соед, rest[1], rest[2], body or {},
                             служба, actor_id, actor_type,
                             ожидаемая_версия=ожидаемая, request_id=request_id)
        return _проблема(404, "NOT_FOUND", "маршрут контура изменений не найден")
    except S.ChangeSetError as e:
        return _проблема(e.status, e.error_code, e.detail)
    finally:
        соед.close()


def _создать(соед, тело: dict, служба: str, actor_id: str,
             actor_type: str) -> tuple[int, Any]:
    if "status" in тело:
        # Прямая запись состояния — не опечатка клиента, а попытка обойти
        # машину переходов; отвечаем об этом прямо.
        return _проблема(422, "STATUS_NOT_WRITABLE",
                         "состояние вычисляется сервером и в запросе не задаётся")
    обязательные = ("resource_type", "resource_id", "operation_type",
                    "target_site_ids", "idempotency_key")
    нет = [k for k in обязательные if not тело.get(k)]
    if нет:
        return _проблема(422, "FIELD_REQUIRED", f"не заданы поля: {нет}")
    if M.PROPOSER not in M.роли_службы(служба):
        return _проблема(403, "ROLE_NOT_GRANTED",
                         f"служба {служба} не вправе предлагать изменения")
    итог = S.создать(соед, тело, producer_service=служба, actor_id=actor_id,
                     actor_type=actor_type)
    return _ответ(200 if итог["idempotent_replay"] else 201, итог)


def _список(соед, q: dict) -> tuple[int, Any]:
    q = {k: (v[-1] if isinstance(v, (list, tuple)) else v) for k, v in q.items()}
    неизвестные = [k for k in q if k not in ФИЛЬТРЫ + СЛУЖЕБНЫЕ]
    if неизвестные:
        return _проблема(422, "FILTER_UNKNOWN",
                         f"неизвестные параметры: {sorted(неизвестные)}")
    for k in ФИЛЬТРЫ:
        if k in q and not str(q[k]).strip():
            return _проблема(422, "FILTER_VALUE_EMPTY", f"{k} задан пустым")
    где, знач = [], []
    for k in ФИЛЬТРЫ:
        if k not in q:
            continue
        if k == "site_id":
            где.append("changeset_id IN (SELECT changeset_id FROM "
                       "changeset_target WHERE site_id=?)")
        else:
            где.append(f"{k}=?")
        знач.append(q[k])
    допустимые = {"status": M.СОСТОЯНИЯ, "risk_class": M.КЛАССЫ_РИСКА,
                  "impact_level": M.УРОВНИ_ВЛИЯНИЯ}
    for имя, значения in допустимые.items():
        if имя in q and q[имя] not in значения:
            return _проблема(
                422, "FILTER_VALUE_UNKNOWN",
                f"неизвестное значение {имя}={q[имя]!r}; "
                f"допустимы {sorted(значения)}")
    try:
        after = int(q.get("after", 0))
        limit = min(int(q.get("limit", 100)), 1000)
    except (TypeError, ValueError):
        return _проблема(422, "FILTER_VALUE_INVALID", "after и limit — целые")
    где.append("rowid > ?")
    знач.append(after)
    sql = ("SELECT rowid AS cursor, * FROM changeset WHERE "
           + " AND ".join(где) + " ORDER BY rowid LIMIT ?")
    строки = [dict(r) for r in соед.execute(sql, знач + [limit])]
    return _ответ(200, {
        "items": строки, "count": len(строки),
        "next_cursor": строки[-1]["cursor"] if строки else after,
        "filters_applied": {k: q[k] for k in ФИЛЬТРЫ if k in q}})


def _действие(соед, cid: str, действие: str, тело: dict, служба: str,
              actor_id: str, actor_type: str, *,
              ожидаемая_версия: int | None = None,
              request_id: str = "") -> tuple[int, Any]:
    роль = ДЕЙСТВИЯ[действие]
    POL.проверить_действие_модели(
        actor_type, {"approve": "approve", "apply": "apply",
                     "rollback": "rollback"}.get(действие, действие))
    if роль not in M.роли_службы(служба):
        return _проблема(403, "ROLE_NOT_GRANTED",
                         f"служба {служба} не имеет роли {роль}")
    дв = E.Engine(соед)

    if действие == "validate":
        return _ответ(200, дв.валидировать(
            cid, actor_id=actor_id, служба=служба,
            ожидаемая_версия=ожидаемая_версия, request_id=request_id))
    if действие == "approve":
        срок = тело.get("expires_at")
        if not срок:
            return _проблема(422, "FIELD_REQUIRED",
                             "expires_at обязателен: бессрочное одобрение "
                             "не отличается от его отсутствия")
        набор = S.получить(соед, cid)
        if набор and набор["status"] == M.VALIDATED:
            дв.запросить_одобрение(cid, actor_id=actor_id, служба=служба,
                                   expires_at=срок,
                                   ожидаемая_версия=ожидаемая_версия,
                                   request_id=request_id)
            # Версия уже сдвинулась этим же запросом: сверять её второй раз
            # значило бы отказать клиенту за им же сделанный шаг.
            ожидаемая_версия = None
        return _ответ(200, дв.одобрить(cid, approver_id=actor_id, служба=служба,
                                       actor_type=actor_type, expires_at=срок,
                                       reason=тело.get("reason", ""),
                                       ожидаемая_версия=ожидаемая_версия,
                                       request_id=request_id))
    if действие == "reject":
        return _ответ(200, S.применить_переход(
            соед, cid, "reject", actor_id=actor_id, служба=служба,
            роль=M.APPROVER, reason=тело.get("reason", ""),
            ожидаемая_версия=ожидаемая_версия, request_id=request_id))
    if действие == "revoke-approval":
        return _ответ(200, дв.отозвать_одобрение(cid, actor_id=actor_id))
    if действие == "cancel":
        набор = S.получить(соед, cid)
        карта = {M.PROPOSED: "cancel", M.VALIDATED: "cancel_validated",
                 M.AWAITING_APPROVAL: "cancel_awaiting"}
        д = карта.get(набор["status"] if набор else "")
        if not д:
            return _проблема(409, "TRANSITION_NOT_ALLOWED",
                             "в текущем состоянии отмена не предусмотрена")
        return _ответ(200, S.применить_переход(
            соед, cid, д, actor_id=actor_id, служба=служба, роль=M.PROPOSER,
            reason=тело.get("reason", ""),
            ожидаемая_версия=ожидаемая_версия, request_id=request_id))
    if действие in ("apply", "rollback"):
        аренда = S.взять_аренду(соед, cid, тело.get("worker_id") or actor_id)
        if действие == "apply":
            return _ответ(200, дв.применить(
                cid, actor_id=actor_id, служба=служба,
                fencing_token=аренда["fencing_token"],
                ожидаемая_версия=ожидаемая_версия, request_id=request_id))
        return _ответ(200, дв.откатить(
            cid, actor_id=actor_id, служба=служба,
            fencing_token=аренда["fencing_token"],
            ожидаемая_версия=ожидаемая_версия, request_id=request_id))
    return _проблема(404, "NOT_FOUND", "действие не найдено")


def _процессы(rest: list[str], метод: str) -> tuple[int, Any]:
    """Состояние рабочего процесса. Только чтение."""
    if метод != "GET":
        return _проблема(405, "METHOD_NOT_ALLOWED", "маршрут только для чтения")
    соед = _соед()
    try:
        по_состояниям = {r["status"]: r["n"] for r in соед.execute(
            "SELECT status, count(*) n FROM changeset GROUP BY status")}
        backlog = соед.execute("SELECT count(*) c FROM changeset_outbox "
                               "WHERE published_at IS NULL").fetchone()["c"]
        dlq = соед.execute("SELECT count(*) c FROM changeset_dlq").fetchone()["c"]
        аренды = [dict(r) for r in соед.execute(
            "SELECT changeset_id, worker_id, fencing_token FROM changeset_lease")]
        замки = соед.execute("SELECT count(*) c FROM changeset_lock").fetchone()["c"]
        return _ответ(200, {
            "workflow": "changeset",
            "schema_version": M.SCHEMA_VERSION,
            "by_status": по_состояниям,
            "outbox_backlog": backlog,
            "dlq_size": dlq,
            "active_locks": замки,
            "leases": аренды,
            "autonomous_production_apply":
                "ENABLED" if POL.AUTONOMOUS_PRODUCTION_APPLY else "DISABLED",
            "audit_ledger_available": AB.доступен(),
            "adapters": sorted(__import__(
                "factory.site_engine.changeset.adapter", fromlist=["РЕЕСТР"]
            ).РЕЕСТР),
        })
    finally:
        соед.close()
