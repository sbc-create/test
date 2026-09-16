"""Исполнение заявки: подтверждение, выкладка канарейки, проверка и откат.

План без исполнения — схема. Здесь план становится работающей витриной и, если
надо, полностью исчезает обратно.

Четыре правила, каждое написано на конкретный способ соврать.

**Подтверждают именно тот план, который выполнится.** Подтверждение хранит
отпечаток плана. Изменились ответы — подтверждение недействительно, и его
придётся дать заново. Иначе «сравните и подтвердите» подтверждает прошлое.

**Домен занимается атомарно.** Бронь создаётся с `O_EXCL`: второй процесс
получает отказ, а не вторую запись. Проверка «занят ли» с последующей записью
оставляет окно ровно там, где два пользователя нажимают кнопку одновременно.

**Канарейка живёт в наложении, а не в каталоге профилей.** Витрина, попавшая в
общий каталог, участвует в обходах, полках и выкладке раньше, чем её проверили.
Наложение видно оператору отдельной отметкой и не видно никому больше.

**Откат возвращает состояние полностью.** Он снимает всё, что создал, и
освобождает домен. Частичный откат хуже отсутствующего: он оставляет
непонятно чьё состояние и выглядит успешным.
"""

from __future__ import annotations

import errno
import json
import os
from pathlib import Path
from typing import Any

from factory import audit
from factory.site_engine import site_plan
from factory.site_engine.site_request import SiteRequestStore, Заявка

СОСТОЯНИЯ = ("DRAFT", "APPROVED", "PROVISIONED", "ROLLED_BACK")

НАЛОЖЕНИЕ = "var/state/canary-profiles"
БРОНИ = "var/state/domain-reservations"
КАНАРЕЙКИ = "var/state/canary"


class ProvisionError(Exception):
    def __init__(self, code: str, message: str, *, status: int = 409, **extra: Any) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status = status
        self.extra = extra


def _путь_брони(root: Path, домен: str) -> Path:
    # Имя брони — сам домен. Он уже проверен на вид в мастере, но здесь
    # проверяется ещё раз: файл с именем «../что-нибудь» ушёл бы мимо каталога.
    if not домен or "/" in домен or ".." in домен.split("."):
        raise ProvisionError("invalid_domain", "негодный домен для брони", status=400)
    return root / БРОНИ / f"{домен}.json"


def занять_домен(root: Path, домен: str, *, site_id: str, request_id: str) -> Path:
    """Атомарная бронь домена. Второй вызов на тот же домен — отказ."""
    путь = _путь_брони(root, домен)
    путь.parent.mkdir(parents=True, exist_ok=True)
    запись = json.dumps(
        {"domain": домен, "siteId": site_id, "requestId": request_id},
        ensure_ascii=False,
    )
    try:
        дескриптор = os.open(путь, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o644)
    except OSError as ошибка:
        if ошибка.errno == errno.EEXIST:
            существует = json.loads(путь.read_text(encoding="utf-8"))
            if существует.get("requestId") == request_id:
                return путь
            raise ProvisionError(
                "domain_taken",
                f"домен {домен} уже занят заявкой {существует.get('requestId', '?')}",
            ) from ошибка
        raise
    with os.fdopen(дескриптор, "w", encoding="utf-8") as файл:
        файл.write(запись + "\n")
    return путь


def освободить_домен(root: Path, домен: str, *, request_id: str) -> bool:
    путь = _путь_брони(root, домен)
    if not путь.exists():
        return False
    try:
        запись = json.loads(путь.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        запись = {}
    if запись.get("requestId") not in ("", None, request_id):
        # Чужую бронь не снимаем ни при каких обстоятельствах.
        raise ProvisionError("foreign_reservation", "бронь домена принадлежит другой заявке")
    путь.unlink()
    return True


def _канареечный_профиль(пакет: dict[str, Any]) -> dict[str, Any]:
    """Профиль канарейки. Индексация выключена дважды и по-разному.

    `indexing_enabled` читает ядро, `noindex` — слой разметки. Одно поле на два
    слоя однажды окажется прочитанным не тем из них.
    """
    return {
        "schema_version": "1.0",
        "site_id": пакет["site_id"],
        "site_type": "video-showcase",
        "domains": [пакет.get("domain", "")],
        "canonical_host": пакет.get("domain", ""),
        "locale": "ru-RU",
        "timezone": "Europe/Moscow",
        "theme": {"name": пакет.get("theme_ref", "")},
        "canary": True,
        "indexing_enabled": False,
        "noindex": True,
        "production_authorized": False,
        "content_directions": list(пакет.get("content_types") or []),
        "origin": {"requestJob": пакет.get("job_id", ""), "createdAt": пакет.get("created_at", "")},
    }


def approve(
    store: SiteRequestStore, request_id: str, plan_hash: str, root: Path, *, actor: str
) -> Заявка:
    заявка = store.get(request_id)
    if not заявка.complete:
        raise ProvisionError("request_incomplete", "заявка заполнена не полностью")
    текущий = site_plan.план(заявка, root)["planHash"]
    if plan_hash != текущий:
        raise ProvisionError(
            "plan_changed",
            "подтверждается не тот план: ответы изменились после показа",
            expected=текущий,
        )
    заявка.state = "APPROVED"
    заявка.approved_plan_hash = текущий
    заявка.approved_by = actor
    store.save(заявка)
    return заявка


def provision(
    store: SiteRequestStore,
    request_id: str,
    root: Path,
    *,
    actor: str,
    correlation_id: str,
    now: str,
) -> dict[str, Any]:
    """Выкладка канарейки. Ничего боевого не трогает."""
    заявка = store.get(request_id)
    if заявка.state != "APPROVED":
        raise ProvisionError(
            "not_approved",
            "выкладка возможна только после подтверждения плана",
            state=заявка.state,
        )
    план = site_plan.план(заявка, root)
    if план["planHash"] != заявка.approved_plan_hash:
        raise ProvisionError("plan_changed", "план изменился после подтверждения")
    if not план.get("canaryReady"):
        raise ProvisionError(
            "plan_not_ready", "план не готов к исполнению", requirements=план["requirements"]
        )

    пакет = план["package"]
    домен = пакет.get("domain", "")
    занять_домен(root, домен, site_id=заявка.site_id, request_id=заявка.request_id)

    шаги: list[dict[str, Any]] = [{"id": "reserve_domain", "detail": домен, "done": True}]

    наложение = root / НАЛОЖЕНИЕ / f"{заявка.site_id}.json"
    наложение.parent.mkdir(parents=True, exist_ok=True)
    временный = наложение.with_suffix(".json.tmp")
    временный.write_text(
        json.dumps(_канареечный_профиль(пакет), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    временный.replace(наложение)
    шаги.append({"id": "create_canary_profile", "detail": str(наложение.name), "done": True})

    состояние = root / КАНАРЕЙКИ / заявка.site_id
    состояние.mkdir(parents=True, exist_ok=True)
    job_id = f"{заявка.site_id}-{заявка.request_id[:8]}"
    (состояние / "state.json").write_text(
        json.dumps(
            {
                "siteId": заявка.site_id,
                "requestId": заявка.request_id,
                "jobId": job_id,
                "planHash": план["planHash"],
                "startedAt": now,
                "steps": шаги,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    _записать_задание(root, заявка.site_id, job_id, шаги, now)
    audit.record(
        job_id=correlation_id,
        site_id=заявка.site_id,
        environment="staging",
        action="control.site_request.provision",
        target=str(наложение.relative_to(root)),
        mutation=True,
        exit_code=0,
        extra={
            "correlation_id": correlation_id,
            "actor": actor,
            "request_id": заявка.request_id,
            "plan_hash": план["planHash"],
            "job_id": job_id,
        },
    )

    заявка.state = "PROVISIONED"
    заявка.job_id = job_id
    store.save(заявка)
    return {"jobId": job_id, "state": заявка.state, "steps": шаги, "canary": True}


def _записать_задание(
    root: Path, site_id: str, job_id: str, шаги: list[dict[str, Any]], now: str
) -> None:
    """Задание видно в разделе «Задания» так же, как любое другое.

    Отдельный список «заданий самообслуживания» означал бы, что оператор ищет
    их в другом месте — и не находит, когда что-то пошло не так.
    """
    каталог = root / "artifacts" / "jobs" / site_id
    каталог.mkdir(parents=True, exist_ok=True)
    (каталог / f"{job_id}.json").write_text(
        json.dumps(
            {
                "job_id": job_id,
                "site_id": site_id,
                "status": "SUCCEEDED",
                "started_at": now,
                "finished_at": now,
                "checks": [
                    {"id": ш["id"], "passed": True, "exit_code": 0, "artifact": ""} for ш in шаги
                ],
                "blockers": [],
                "notes": ["канареечная выкладка: индексация выключена"],
                "steps": шаги,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )


def verification(store: SiteRequestStore, request_id: str, root: Path) -> dict[str, Any]:
    """Проверки канарейки поимённо. Без списка проверок это не проверка."""
    заявка = store.get(request_id)
    if заявка.state != "PROVISIONED":
        raise ProvisionError("not_provisioned", "канарейка ещё не выложена", state=заявка.state)
    пакет = site_plan.собрать_пакет(заявка, root)
    наложение = root / НАЛОЖЕНИЕ / f"{заявка.site_id}.json"
    боевой = root / "config" / "site-profiles" / f"{заявка.site_id}.json"
    бронь = _путь_брони(root, пакет.get("domain", ""))
    профиль = {}
    if наложение.exists():
        try:
            профиль = json.loads(наложение.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            профиль = {}
    from factory.site_engine import site_plan as _план

    недостающие = _план.план(заявка, root).get("missingAssets") or []
    проверки = [
        # Недостающие файлы названы поимённо и здесь. Канарейка живёт без них
        # намеренно, но «живёт без них» и «про них забыли» должны выглядеть
        # по-разному.
        {
            "id": "assets_listed",
            "passed": True,
            "detail": (
                "не хватает: " + ", ".join(sorted(б["field"] for б in недостающие))
                if недостающие
                else "все файлы витрины на месте"
            ),
        },
        {
            "id": "ready_for_publication",
            "passed": not недостающие,
            "detail": "публикация требует всех файлов витрины",
        },
        {"id": "canary_profile_present", "passed": наложение.exists(),
         "detail": str(наложение.name)},
        {"id": "noindex_set", "passed": профиль.get("noindex") is True
         and профиль.get("indexing_enabled") is False,
         "detail": "индексация выключена в двух полях"},
        {"id": "domain_reserved", "passed": бронь.exists(), "detail": пакет.get("domain", "")},
        {"id": "not_in_production_catalog", "passed": not боевой.exists(),
         "detail": "канарейка не попала в общий каталог профилей"},
        {"id": "owner_authorization_absent", "passed": пакет.get("production_authorized") is False,
         "detail": "разрешение владельца не выдано мастером"},
    ]
    return {
        "requestId": заявка.request_id,
        "siteId": заявка.site_id,
        "checks": проверки,
        "passed": all(п["passed"] for п in проверки),
    }


def publish(store: SiteRequestStore, request_id: str, root: Path) -> dict[str, Any]:
    """Публикация канарейки в боевой контур.

    Всегда отказ: перевод витрины в production — решение владельца, и его нет ни
    в одном поле мастера. Отказ честный и с кодом, а не молчаливое бездействие.
    """
    заявка = store.get(request_id)
    if заявка.state != "PROVISIONED":
        raise ProvisionError("not_provisioned", "публиковать нечего", state=заявка.state)
    raise ProvisionError(
        "OWNER_AUTHORIZATION_REQUIRED",
        "перевод витрины в боевой контур требует разрешения владельца; "
        "мастер его не выдаёт",
        status=409,
        siteId=заявка.site_id,
    )


def rollback(
    store: SiteRequestStore, request_id: str, root: Path, *, actor: str, correlation_id: str
) -> dict[str, Any]:
    """Полный откат канарейки. Снимает всё, что создал."""
    заявка = store.get(request_id)
    if заявка.state != "PROVISIONED":
        raise ProvisionError("nothing_to_roll_back", "выкладки не было", state=заявка.state)
    пакет = site_plan.собрать_пакет(заявка, root)
    снято: list[str] = []

    наложение = root / НАЛОЖЕНИЕ / f"{заявка.site_id}.json"
    if наложение.exists():
        наложение.unlink()
        снято.append(str(наложение.relative_to(root)))

    состояние = root / КАНАРЕЙКИ / заявка.site_id
    if состояние.is_dir():
        for файл in sorted(состояние.iterdir()):
            файл.unlink()
        состояние.rmdir()
        снято.append(str(состояние.relative_to(root)))

    if освободить_домен(root, пакет.get("domain", ""), request_id=заявка.request_id):
        снято.append(f"бронь домена {пакет.get('domain', '')}")

    # Пустые каталоги наложений тоже убираются: оставленный пустой каталог
    # выглядит как «канарейка была и что-то от неё осталось».
    for каталог in (root / НАЛОЖЕНИЕ, root / БРОНИ, root / КАНАРЕЙКИ):
        if каталог.is_dir() and not any(каталог.iterdir()):
            каталог.rmdir()

    audit.record(
        job_id=correlation_id,
        site_id=заявка.site_id,
        environment="staging",
        action="control.site_request.rollback",
        target=f"var/state/canary/{заявка.site_id}",
        mutation=True,
        exit_code=0,
        extra={
            "correlation_id": correlation_id,
            "actor": actor,
            "request_id": заявка.request_id,
            "removed": снято,
        },
    )
    заявка.state = "ROLLED_BACK"
    store.save(заявка)
    return {"state": заявка.state, "removed": снято}
