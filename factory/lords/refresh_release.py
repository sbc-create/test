"""Обновление каталога, которое не подменяет шаблон.

Прежний порядок: обновление каталога отрисовывало витрину из развёрнутого
checkout и переносило старый `bundle-manifest.json` в новый релиз. Отрисовка
шла тем шаблоном, что лежал в рабочем дереве, а манифест утверждал прежнее.
Канареечный релиз, выложенный руками, жил до ближайшего таймера.

Новый порядок ровно один:

    закреплённый артефакт шаблона текущего релиза + новый снимок каталога
    → новый атомарный релиз

Отрисовка идёт из распакованного артефакта, названного манифестом текущего
релиза. Рабочее дерево, ветка и незакреплённый HEAD не участвуют вовсе.

Три места, где раньше можно было потерять выложенное, закрыты здесь:

**Замок на витрину.** Обновление, канареечное переключение, ручная публикация
и откат больше не идут одновременно. Замок берётся на витрину, а не на весь
рантайм: остановка обновления всех трёх витрин ради одной — не архитектура.

**Ожидаемый предыдущий релиз.** Переключение выполняется, только если `current`
указывает туда, где его оставили. Иначе отказ: состояние изменилось между
решением и действием, и переключение затёрло бы чужую работу.

**Инварианты до переключения.** Манифест проверяется перед сменой ссылки, а не
после. Отказ оставляет действующий релиз нетронутым.
"""

from __future__ import annotations

import fcntl
import json
import os
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from factory.lords import release_manifest as рм
from factory.lords import template_artifact as та

МАНИФЕСТ = "release-manifest.json"
ЖУРНАЛ = "release-log.jsonl"


class RefreshRefused(Exception):
    """Обновление отказано до переключения. Действующий релиз не тронут."""


@contextmanager
def замок(runtime: Path | str, *, timeout: float = 300.0):
    """Замок на витрину. Ожидание конечно: вечное ожидание — это остановка."""
    путь = Path(runtime) / ".refresh.lock"
    путь.parent.mkdir(parents=True, exist_ok=True)
    ф = open(путь, "a+")
    край = time.monotonic() + timeout
    try:
        while True:
            try:
                fcntl.flock(ф.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except BlockingIOError:
                if time.monotonic() >= край:
                    raise RefreshRefused(
                        f"витрина занята другой операцией дольше {timeout:.0f} с: "
                        "одновременное переключение затёрло бы чужую работу"
                    ) from None
                time.sleep(0.2)
        ф.seek(0)
        ф.truncate()
        ф.write(f"{os.getpid()} {time.time():.0f}\n")
        ф.flush()
        yield путь
    finally:
        try:
            fcntl.flock(ф.fileno(), fcntl.LOCK_UN)
        finally:
            ф.close()


def текущий_релиз(runtime: Path | str) -> Path | None:
    ссылка = Path(runtime) / "current"
    if not ссылка.exists():
        return None
    return ссылка.resolve()


def манифест_текущего(runtime: Path | str) -> dict[str, Any]:
    релиз = текущий_релиз(runtime)
    if релиз is None:
        raise RefreshRefused(f"у витрины нет действующего релиза: {runtime}")
    return рм.прочитать(релиз / МАНИФЕСТ)


def план(runtime: Path | str, *, artifact_root: Path | str) -> dict[str, Any]:
    """Из чего собирать следующий релиз. Ничего не меняет.

    Отдельный шаг именно потому, что решение принимается до действия: план
    можно показать, записать и проверить, не трогая витрину.
    """
    релиз = текущий_релиз(runtime)
    if релиз is None:
        raise RefreshRefused(f"у витрины нет действующего релиза: {runtime}")
    манифест = рм.прочитать(релиз / МАНИФЕСТ)
    беды = рм.нарушения(манифест, artifact_root=artifact_root)
    if беды:
        raise RefreshRefused(
            f"действующий релиз {релиз.name} не удовлетворяет инвариантам: "
            + "; ".join(беды)
        )
    корень = та.корень_шаблона(манифест, runtime=runtime, artifact_root=artifact_root)
    return {
        "runtime": str(runtime),
        "currentRelease": релиз.name,
        "currentPath": str(релиз),
        "manifest": манифест,
        "templateRoot": str(корень),
        "templateDigest": манифест["template_digest"],
        "rendererRevision": манифест["renderer_revision"],
        "tenant": манифест["tenant_id"],
    }


def записать_манифест(
    target: Path | str,
    план_: dict[str, Any],
    *,
    content_snapshot_id: str,
    content_count: int,
    created_by: str,
    artifact_root: Path | str,
    release_reason: str = "content-refresh",
) -> dict[str, Any]:
    """Манифест нового релиза. Шаблонная часть переносится, а не пересчитывается."""
    новый = рм.следующий(
        план_["manifest"],
        content_snapshot_id=content_snapshot_id,
        content_count=content_count,
        created_at=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        created_by=created_by,
        previous_release=план_["currentRelease"],
        release_reason=release_reason,
    )
    беды = рм.нарушения(новый, artifact_root=artifact_root)
    if беды:
        raise RefreshRefused("новый релиз не удовлетворяет инвариантам: " + "; ".join(беды))
    разошлось = рм.шаблон_сохранён(план_["manifest"], новый)
    if разошлось:
        raise RefreshRefused("обновление каталога изменило шаблон: " + "; ".join(разошлось))
    путь = Path(target) / МАНИФЕСТ
    путь.parent.mkdir(parents=True, exist_ok=True)
    путь.write_text(json.dumps(новый, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return новый


def переключить(
    runtime: Path | str,
    target: Path | str,
    *,
    expected_current: str | None,
    reason: str,
    actor: str,
) -> dict[str, Any]:
    """Атомарная смена `current` с проверкой ожидаемого предыдущего релиза."""
    рантайм = Path(runtime)
    цель = Path(target)
    if not (цель / МАНИФЕСТ).is_file():
        raise RefreshRefused(f"у релиза {цель.name} нет манифеста — переключение отказано")
    было = текущий_релиз(рантайм)
    имя_было = было.name if было else None
    if expected_current is not None and имя_было != expected_current:
        raise RefreshRefused(
            f"состояние изменилось: current={имя_было}, ожидалось {expected_current}. "
            "Переключение затёрло бы чужую операцию"
        )
    if имя_было == цель.name:
        # Повтор той же операции — не ошибка и не действие.
        return {"switched": False, "current": имя_было, "idempotent": True}
    временная = рантайм / ".current.new"
    if временная.exists() or временная.is_symlink():
        временная.unlink()
    временная.symlink_to(цель)
    os.replace(временная, рантайм / "current")
    запись = {
        "at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "tenant": рантайм.name,
        "from": имя_было,
        "to": цель.name,
        "reason": reason,
        "actor": actor,
        "pid": os.getpid(),
        "uid": os.getuid(),
    }
    with open(рантайм / ЖУРНАЛ, "a", encoding="utf-8") as ф:
        ф.write(json.dumps(запись, ensure_ascii=False) + "\n")
    return {"switched": True, "current": цель.name, "previous": имя_было, "record": запись}


