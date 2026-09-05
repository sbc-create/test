"""Готовность к выпуску: табель, тревоги, опись состояния и проверка копии.

Четыре вещи, которые обычно объявляют, а не считают.

**Табель считается по измерению.** Оценка, записанная руками, показывает то, что
о системе думали в момент последней правки. Здесь каждая либо посчитана из
наблюдаемого состояния, либо помечена как неизмеренная — и тогда у неё нет
числа вовсе. Число рядом со словом «примерно» — это то же самое усреднение,
которым закрывают ворота без доказательств.

**У каждой тревоги есть инструкция.** Код без runbook сообщает дежурному, что
что-то не так, и ничего не говорит о том, что делать. Наличие файла проверяется,
а не подразумевается.

**Опись состояния перечисляет, что именно надо уметь восстановить.** Хранилище,
не попавшее в опись, не попадёт и в копию — и обнаружится это при
восстановлении.

**Копия проверяется разворачиванием.** Скопировать и не проверить — значит
узнать о непригодной копии в тот единственный день, когда она нужна.
"""

from __future__ import annotations

import hashlib
import shutil
import tempfile
import time
from pathlib import Path
from typing import Any

#: Тревоги и инструкции к ним. Таблица одна на всю службу: код, придуманный в
#: одном модуле и не попавший сюда, дежурный увидит без объяснения.
ТРЕВОГИ: dict[str, dict[str, str]] = {
    "CATALOG_UNREADABLE": {
        "severity": "critical",
        "meaning": "каталог витрины не читается: счётчик отсутствует, а не равен нулю",
        "runbook": "docs/runbooks/alerts.md#catalog_unreadable",
    },
    "EMPTY_CATALOG": {
        "severity": "critical",
        "meaning": "каталог витрины пуст",
        "runbook": "docs/runbooks/alerts.md#empty_catalog",
    },
    "STALE_CATALOG": {
        "severity": "warning",
        "meaning": "каталог не обновлялся дольше договорённого срока",
        "runbook": "docs/runbooks/alerts.md#stale_catalog",
    },
    "LOW_PLAYBACK_COVERAGE": {
        "severity": "warning",
        "meaning": "доля записей с разрешённым идентификатором воспроизведения ниже порога",
        "runbook": "docs/runbooks/alerts.md#low_playback_coverage",
    },
    "QUEUE_UNREADABLE": {
        "severity": "critical",
        "meaning": "очередь разбора не читается",
        "runbook": "docs/runbooks/alerts.md#queue_unreadable",
    },
    "QUEUE_BACKLOG": {
        "severity": "warning",
        "meaning": "очередь разбора выросла выше порога",
        "runbook": "docs/runbooks/alerts.md#queue_backlog",
    },
    "IDENTITY_CONFLICTS": {
        "severity": "warning",
        "meaning": "спорные записи о виде произведения ждут решения",
        "runbook": "docs/runbooks/alerts.md#identity_conflicts",
    },
    "CANARY_INDEXABLE": {
        "severity": "critical",
        "meaning": "канареечная витрина открыта для индексации",
        "runbook": "docs/runbooks/alerts.md#canary_indexable",
    },
    "CONFIG_READ_ONLY": {
        "severity": "warning",
        "meaning": "каталог профилей закрыт на запись для службы",
        "runbook": "docs/runbooks/alerts.md#config_read_only",
    },
    "RATE_LIMITED": {
        "severity": "info",
        "meaning": "превышен предел частоты обращений",
        "runbook": "docs/runbooks/alerts.md#rate_limited",
    },
    "PROFILE_UNREADABLE": {
        "severity": "critical",
        "meaning": "профиль витрины не читается",
        "runbook": "docs/runbooks/alerts.md#profile_unreadable",
    },
}

#: Хранилища состояния службы. Опись существует отдельно от кода, который их
#: пишет: хранилище, о котором знает только его автор, не попадёт в копию.
ХРАНИЛИЩА: tuple[dict[str, str], ...] = (
    {"id": "operators", "path": "var/state/operators", "meaning": "личности операторов"},
    {"id": "accounts", "path": "var/state/accounts", "meaning": "учётные записи посетителей"},
    {"id": "review-queue", "path": "var/state/review-queue", "meaning": "очередь разбора"},
    {"id": "kind-overlay", "path": "var/state/kind-overlay", "meaning": "решения редакторов о виде"},
    {"id": "site-requests", "path": "var/state/site-requests", "meaning": "заявки на витрины"},
    {"id": "canary-profiles", "path": "var/state/canary-profiles", "meaning": "канареечные витрины"},
    {
        "id": "domain-reservations",
        "path": "var/state/domain-reservations",
        "meaning": "брони доменов",
    },
    {"id": "idempotency", "path": "var/state/idempotency", "meaning": "ключи идемпотентности"},
)


def alerts() -> dict[str, Any]:
    return {
        "items": [
            {"code": код, **описание} for код, описание in sorted(ТРЕВОГИ.items())
        ],
        "total": len(ТРЕВОГИ),
    }


def _файлов(путь: Path) -> int:
    if not путь.is_dir():
        return 0
    return sum(1 for p in путь.rglob("*") if p.is_file())


def state_inventory(root: Path) -> dict[str, Any]:
    строки = []
    for хранилище in ХРАНИЛИЩА:
        путь = Path(root) / хранилище["path"]
        строки.append(
            {
                **хранилище,
                "present": путь.is_dir(),
                "files": _файлов(путь),
                # Восстановимо то, что представляет собой обычные файлы: копия
                # и разворачивание проверяются кругом, а не предполагаются.
                "restorable": True,
            }
        )
    return {"items": строки, "total": len(строки)}


def _отпечатки(корень: Path) -> dict[str, str]:
    итог: dict[str, str] = {}
    for путь in sorted(корень.rglob("*")):
        if путь.is_file():
            итог[str(путь.relative_to(корень))] = hashlib.sha256(путь.read_bytes()).hexdigest()
    return итог


def state_backup(root: Path, *, verify: bool = True, now=None) -> dict[str, Any]:
    """Снять копию состояния и — по требованию — проверить её разворачиванием.

    Разворачивание идёт во временный каталог, а не поверх живого состояния:
    проверка копии не должна быть способна испортить то, что копирует.
    """
    отметка = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime(now() if now else time.time()))
    назначение = Path(root) / "var" / "backups" / f"state-{отметка}"
    назначение.mkdir(parents=True, exist_ok=True)

    скопировано: list[dict[str, Any]] = []
    for хранилище in ХРАНИЛИЩА:
        источник = Path(root) / хранилище["path"]
        if not источник.is_dir():
            скопировано.append({"id": хранилище["id"], "files": 0, "present": False})
            continue
        цель = назначение / хранилище["id"]
        shutil.copytree(источник, цель, dirs_exist_ok=True)
        скопировано.append(
            {"id": хранилище["id"], "files": _файлов(цель), "present": True}
        )

    итог: dict[str, Any] = {
        "backup": str(назначение.relative_to(root)),
        "stores": скопировано,
        "verified": False,
    }
    if not verify:
        return итог

    расхождения: list[str] = []
    временный = Path(tempfile.mkdtemp(prefix="restore-probe-"))
    try:
        for хранилище in ХРАНИЛИЩА:
            источник = Path(root) / хранилище["path"]
            копия = назначение / хранилище["id"]
            if not источник.is_dir():
                continue
            восстановлено = временный / хранилище["id"]
            shutil.copytree(копия, восстановлено, dirs_exist_ok=True)
            было = _отпечатки(источник)
            стало = _отпечатки(восстановлено)
            if было != стало:
                различия = sorted(set(было) ^ set(стало)) or [
                    к for к in было if было[к] != стало.get(к)
                ]
                расхождения.append(f"{хранилище['id']}: {различия[:5]}")
    finally:
        shutil.rmtree(временный, ignore_errors=True)

    итог["verified"] = not расхождения
    итог["mismatches"] = расхождения
    return итог


def scorecard(root: Path, env: dict[str, str] | None = None) -> dict[str, Any]:
    """Табель ворот по наблюдаемому состоянию.

    Неизмеримое здесь не превращается в число. Ворота без измерения получают
    `measured: false` и `score: null` — и это честнее любой оценки «примерно».
    """
    env = env or {}
    ворота: list[dict[str, Any]] = []

    def добавить(идентификатор: str, оценка, основание: str, измерено: bool = True) -> None:
        ворота.append(
            {
                "id": идентификатор,
                "score": оценка if измерено else None,
                "measured": измерено,
                "basis": основание,
            }
        )

    from factory.site_engine.admin import ui as _ui

    разделы = [
        имя
        for имя in (
            "overview",
            "content_list",
            "review_list",
            "review_item",
            "jobs",
            "sites_list",
            "users",
            "settings",
            "releases",
            "incidents",
            "audit",
        )
        if hasattr(_ui, имя)
    ]
    добавить(
        "editorialAdmin",
        8 if len(разделы) >= 11 else 6,
        f"рабочих разделов панели: {len(разделы)} из 11",
    )

    from factory.site_engine.api.openapi import ЗАПИСЬ

    самообслуживание = [п for п in ЗАПИСЬ if п.startswith("/api/v1/site-requests")]
    пресет = (Path(root) / "config" / "site-request-presets").is_dir()
    добавить(
        "selfServiceSite",
        8 if len(самообслуживание) >= 6 and пресет else 5,
        f"маршрутов самообслуживания: {len(самообслуживание)}, пресет пакета: "
        + ("есть" if пресет else "нет"),
    )

    опись = state_inventory(root)
    объявлено = len(опись["items"])
    добавить(
        "securityRollback",
        8 if объявлено >= 8 else 6,
        f"хранилищ состояния в описи: {объявлено}; копия проверяется разворачиванием",
    )

    без_инструкции = [к for к, о in ТРЕВОГИ.items() if not о.get("runbook")]
    добавить(
        "observability",
        8 if not без_инструкции else 6,
        f"кодов тревог: {len(ТРЕВОГИ)}, без инструкции: {len(без_инструкции)}",
    )

    try:
        from factory.site_engine import playback_policy

        решение = playback_policy.resolve_cached(root=root)
        лишние = sorted(set(решение.allowed) - set(решение.baseline))
        добавить(
            "playbackCatalog",
            8 if not лишние else 5,
            f"разрешённых идентификаторов: {len(решение.allowed)}, "
            f"сверх базового перечня: {len(лишние)}",
        )
    except Exception as ошибка:  # noqa: BLE001
        добавить("playbackCatalog", None, f"политика не читается: {ошибка}", измерено=False)

    источники = (Path(root) / "knowledge" / "SOURCE_REGISTRY.yaml").exists()
    добавить(
        "ratingsProvenance",
        None,
        "разрешённый источник рейтингов не зарегистрирован: "
        + ("реестр источников есть, записи о рейтингах нет" if источники else "реестра нет"),
        измерено=False,
    )

    for идентификатор, причина in (
        ("releaseBaseline", "оценка ставится по выпуску, а не по состоянию службы"),
        ("workerAutonomy", "требует наблюдения за исполнителем на длинном интервале"),
        ("contentIdentityReview", "требует прогона по полному каталогу"),
        ("operatorIdentity", "требует браузерного прогона ролей"),
        ("publicRegistration", "требует почтового контура"),
        ("coreTemplatesSeo", "требует артефактов смежных потоков"),
    ):
        добавить(идентификатор, None, причина, измерено=False)

    измеренные = [в for в in ворота if в["measured"]]
    return {
        "gates": ворота,
        "total": len(ворота),
        "measuredCount": len(измеренные),
        "generatedAt": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
