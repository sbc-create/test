"""Минимальный адаптер единого модуля оценок для витрины animedia.icu.

Витрина подключает адаптер одной строкой и вызывает ``merge_into_detail``
там, где уже собирает данные произведения. Больше от неё ничего не
требуется: разметку внешних оценок она умеет рисовать сама, а блок
пользовательской оценки монтируется готовым партиалом.

Адаптер отказывает молча и в пользу страницы. Нет файла проекции, нет
флага, тайтл вне когорты, файл повреждён — возвращается тот же самый
``detail``, и страница выглядит ровно так, как до подключения. Модуль
оценок не должен уметь сломать карточку произведения: оценка — часть
страницы, а не условие её существования.

Адаптер ничего не пишет и не ходит в базу. Он читает два файла, которые
готовит общий модуль, и держит их в памяти до изменения mtime.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

#: Файлы готовит общий модуль (factory/unified_ratings/site_projection.py).
RUNTIME_DIR = Path(os.environ.get("UNIFIED_RATINGS_RUNTIME_DIR", "/srv/lords/.frontend"))
PROJECTION_PATH = RUNTIME_DIR / "unified-ratings-projection-animedia.json"
FLAGS_PATH = RUNTIME_DIR / "unified-ratings-flags-animedia.json"

SPACE = "animedia"
READ_FLAG = "RATINGS_PUBLIC_READ_ANIMEDIA"
WRITE_FLAG = "RATINGS_PUBLIC_WRITE_ANIMEDIA"

_cache: dict[str, Any] = {"flags": None, "proj": None, "stamps": None}


def _stamps() -> tuple:
    def mtime(path: Path) -> float:
        try:
            return path.stat().st_mtime
        except OSError:
            return 0.0

    return (mtime(PROJECTION_PATH), mtime(FLAGS_PATH))


def _load() -> tuple[dict[str, Any], dict[str, Any]]:
    stamps = _stamps()
    if _cache["stamps"] == stamps and _cache["flags"] is not None:
        return _cache["flags"], _cache["proj"]
    flags: dict[str, Any] = {}
    proj: dict[str, Any] = {}
    try:
        if FLAGS_PATH.is_file():
            flags = json.loads(FLAGS_PATH.read_text(encoding="utf-8"))
        if PROJECTION_PATH.is_file():
            proj = (json.loads(PROJECTION_PATH.read_text(encoding="utf-8")) or {}).get("titles") or {}
    except (OSError, json.JSONDecodeError, ValueError):
        # Повреждённый файл — это отсутствие данных, а не повод уронить
        # страницу произведения.
        flags, proj = {}, {}
    _cache.update({"flags": flags, "proj": proj, "stamps": stamps})
    return flags, proj


def kill_switch_active() -> bool:
    flags, _ = _load()
    return bool(int(flags.get("KILL_SWITCH") or 0))


def public_read_enabled() -> bool:
    flags, _ = _load()
    return bool(int(flags.get(READ_FLAG) or 0)) and not kill_switch_active()


def public_write_enabled() -> bool:
    flags, _ = _load()
    return bool(int(flags.get(WRITE_FLAG) or 0)) and not kill_switch_active()


def _in_cohort(flags: dict[str, Any], subject: str) -> bool:
    allow = (flags.get("allowlist") or {}).get(SPACE)
    if allow is None:
        return False
    if "*" in allow:
        return True
    bare = subject.replace("nova:", "")
    return bare in allow or f"nova:{bare}" in allow


def entry_for(detail: dict[str, Any]) -> dict[str, Any] | None:
    """Готовая запись оценок произведения или ``None``."""
    if not isinstance(detail, dict):
        return None
    if not public_read_enabled():
        return None
    subject = str(detail.get("id") or "").strip()
    if not subject:
        return None
    flags, proj = _load()
    if not _in_cohort(flags, subject):
        return None
    bare = subject.replace("nova:", "")
    node = proj.get(bare) or proj.get(f"nova:{bare}")
    if not node:
        return None
    return node.get(SPACE)


def merge_into_detail(detail: dict[str, Any]) -> dict[str, Any]:
    """Добавить оценки в данные произведения.

    Внешние оценки кладутся в ``ratings_by_source`` — витрина уже умеет
    их рисовать. Сводная, зрительская и редакционная оценки кладутся
    отдельными ключами: смешать их с внешними значило бы выдать одно за
    другое.
    """
    entry = entry_for(detail)
    if entry is None:
        return detail

    out = dict(detail)
    rbs = dict(out.get("ratings_by_source") or {})
    for external in entry.get("external") or []:
        source = external.get("source")
        value = external.get("score")
        if not source or value in (None, ""):
            # Отсутствующее значение не превращается в ноль и не
            # добавляется вовсе.
            continue
        rbs[source] = {
            "value": value,
            "scale": 10.0,
            "votes": external.get("votes"),
            "source": source,
            "label": external.get("label") or source,
            "url": external.get("url") or "",
            "unified_module": True,
            "not_native_vote": True,
        }
    out["ratings_by_source"] = rbs

    composite = entry.get("composite")
    if composite:
        out["unified_composite"] = composite
    native = entry.get("native")
    if native:
        out["unified_community"] = native
    editorial = entry.get("editorial")
    if editorial:
        out["unified_editorial"] = editorial

    out["unified_ratings_write_enabled"] = public_write_enabled()
    # Схема AggregateRating не выпускается: витрина закрыта от индексации,
    # и разметка оценок на noindex-странице смысла не имеет.
    out["aggregate_rating_schema_org"] = False
    return out


def widget_context(detail: dict[str, Any]) -> dict[str, Any] | None:
    """Контекст для партиала виджета. ``None`` — не монтировать."""
    entry = entry_for(detail)
    if entry is None:
        return None
    return {
        "space": SPACE,
        "subject_id": str(detail.get("id") or ""),
        "write_enabled": public_write_enabled(),
        "composite": entry.get("composite"),
        "community": entry.get("native"),
        "editorial": entry.get("editorial"),
        "external": entry.get("external") or [],
        "api_base": "/api/unified-ratings",
    }


def runtime_status() -> dict[str, Any]:
    """Состояние адаптера для проверки после выкладки."""
    flags, proj = _load()
    return {
        "projection_path": str(PROJECTION_PATH),
        "projection_present": PROJECTION_PATH.is_file(),
        "projection_titles": len(proj),
        "flags_path": str(FLAGS_PATH),
        "flags_present": FLAGS_PATH.is_file(),
        "public_read_enabled": public_read_enabled(),
        "public_write_enabled": public_write_enabled(),
        "kill_switch": kill_switch_active(),
        "cohort_size": len((flags.get("allowlist") or {}).get(SPACE) or []),
    }
