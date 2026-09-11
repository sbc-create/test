"""Команды реестра: аутентификация, идемпотентность, сверка.

Идемпотентность — не «не сломается при повторе», а «повтор вернёт тот же
ответ и не создаст второй записи». Поэтому ключ и ответ хранятся в той же
БД: память процесса повтор после перезапуска не переживёт.
"""
from __future__ import annotations

import datetime as dt, hashlib, hmac, json, os, sqlite3, time, uuid
from typing import Any

import registry_store as rs

#: Имя ссылки на секрет, а не сам секрет. Значение берётся из окружения
#: службы и в отчёты, логи и артефакты не попадает никогда.
ТОКЕН_REF = "REGISTRY_COMMAND_TOKEN"


class AuthError(RuntimeError):
    """Вызывающий не подтвердил право на команду."""


def проверить_доступ(заголовки: dict[str, str]) -> str:
    """Служебная аутентификация. Возвращает имя вызывающей службы."""
    ожидаемый = os.environ.get(ТОКЕН_REF, "")
    if not ожидаемый:
        raise AuthError("команды выключены: токен службы не настроен")
    дано = (заголовки.get("authorization") or "").removeprefix("Bearer ").strip()
    # Сравнение постоянного времени: обычное сравнение строк утекает длину
    # совпавшего префикса и превращает подбор в линейный.
    if not дано or not hmac.compare_digest(дано, ожидаемый):
        raise AuthError("неверный или отсутствующий служебный токен")
    return (заголовки.get("x-service-name") or "service:unknown").strip()


def выполнить(соед: sqlite3.Connection, *, команда: str, site_id: str,
              поля: dict[str, Any], заголовки: dict[str, str],
              expected_version: int | None = None,
              aliases: list[str] | None = None) -> dict[str, Any]:
    """Команда с проверкой прав и идемпотентностью по Idempotency-Key."""
    actor = проверить_доступ(заголовки)
    ключ = (заголовки.get("idempotency-key") or "").strip()
    if not ключ:
        raise ValueError("Idempotency-Key обязателен")
    ранее = соед.execute("SELECT response FROM idempotency WHERE key=?",
                         (ключ,)).fetchone()
    if ранее:
        ответ = json.loads(ранее["response"])
        ответ["idempotent_replay"] = True
        return ответ
    итог = rs.применить(соед, команда=команда, site_id=site_id, поля=поля,
                        actor=actor, expected_version=expected_version,
                        aliases=aliases)
    соед.execute(
        "INSERT INTO idempotency(key, command, site_id, response, created_at) "
        "VALUES(?,?,?,?,?)",
        (ключ, команда, site_id, json.dumps(итог, ensure_ascii=False),
         rs.сейчас()))
    итог["idempotent_replay"] = False
    return итог


# ------------------------------------------------------------------ сверка

#: Предельная длительность цикла. Сверка без границы однажды зависает и
#: числится работающей.
ПРЕДЕЛ_СЕКУНД = 120


def сверка(соед: sqlite3.Connection, *, ожидаемые_домены: set[str],
           манифесты: dict[str, dict] | None = None) -> dict[str, Any]:
    """Один цикл сверки. Терминальный исход обязателен.

    Таймаут и устаревший heartbeat НЕ дают SUCCESS: незавершённая сверка,
    объявленная успешной, — это худший из возможных отчётов, потому что она
    выглядит проверкой.
    """
    run_id = str(uuid.uuid4())
    t0 = time.monotonic()
    начало = rs.сейчас()
    версия_на_входе = соед.execute(
        "SELECT version FROM registry_version WHERE id=1").fetchone()["version"]
    находки: list[dict[str, Any]] = []

    активные = {р["canonical_domain"]: dict(р) for р in соед.execute(
        "SELECT * FROM site WHERE environment='production' "
        "AND lifecycle_state='ACTIVE'")}
    пропущенные = ожидаемые_домены - set(активные)
    лишние = set(активные) - ожидаемые_домены
    for д in sorted(пропущенные):
        находки.append({"kind": "MISSING", "domain": д})
    for д in sorted(лишние):
        находки.append({"kind": "EXTRA", "domain": д,
                        "site_id": активные[д]["site_id"]})

    # Дубликаты канонического домена — уникальность держит БД, но сверка
    # обязана уметь их найти и тогда, когда ограничение кто-то ослабил.
    for р in соед.execute(
            "SELECT canonical_domain, count(*) n FROM site "
            "GROUP BY canonical_domain HAVING n > 1"):
        находки.append({"kind": "DUPLICATE", "domain": р["canonical_domain"],
                        "count": р["n"]})

    # Расхождение с фактическим развёртыванием.
    for д, зап in sorted(активные.items()):
        м = (манифесты or {}).get(зап["site_id"])
        if not м:
            continue
        if м.get("build_id") and зап["build_id"] != м["build_id"]:
            находки.append({"kind": "DRIFT", "site_id": зап["site_id"],
                            "field": "build_id", "registry": зап["build_id"],
                            "manifest": м["build_id"]})

    отставание = соед.execute(
        "SELECT count(*) c FROM outbox WHERE published_at IS NULL"
    ).fetchone()["c"]
    старейшее = соед.execute(
        "SELECT min(occurred_at) a FROM outbox WHERE published_at IS NULL"
    ).fetchone()["a"]

    прошло = time.monotonic() - t0
    таймаут = прошло > ПРЕДЕЛ_СЕКУНД
    вердикт = ("TIMEOUT" if таймаут else
               "SUCCESS" if not находки else "DIVERGENCE_FOUND")
    return {"run_id": run_id, "started_at": начало, "finished_at": rs.сейчас(),
            "duration_seconds": round(прошло, 3),
            "input_registry_version": версия_на_входе,
            "verdict": вердикт, "findings": находки,
            "metrics": {"active_production": len(активные),
                        "expected": len(ожидаемые_домены),
                        "outbox_backlog": отставание,
                        "outbox_oldest_unpublished": старейшее},
            "heartbeat_at": rs.сейчас(), "timed_out": таймаут}
