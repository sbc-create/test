"""Ключ связи: адрес страницы витрины ↔ запись каталога.

Три входящих запроса от смежного потока просят одно и то же с разных сторон:
состояние воспроизведения по записи, ключ связи между адресом и записью и
разбор записей, чей вид противоречит их собственному названию. Общее у них —
отсутствие связи: адрес страницы и запись каталога нельзя было сопоставить ни
по одному полю.

Связь существует и лежит в состоянии отрисовки (`external_id → slug`). Отдать
её — вся работа. Сопоставлять по транслитерации названия нельзя: имена не
уникальны, и ровно поэтому у ядра есть реестр адресов.

Два правила ответа, каждое написано на конкретный способ соврать.

**Запись без адреса называется, а не выбрасывается.** Тихо выброшенная запись
отдаёт неполную карту и оставляет расхождение необнаруженным.

**Отсутствие карты адресов — не пустая карта.** Если состояния отрисовки нет,
это сказано словами, а записи каталога всё равно перечислены.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

#: Название, объявляющее запись эпизодом. Проверяется только явная форма с
#: номером: «Эпизод 13» — это утверждение записи о самой себе, а не догадка по
#: одному слову. Догадка по слову дала бы ложные срабатывания на «Эпизод
#: неудачи» и подобных названиях.
ЭПИЗОД_В_НАЗВАНИИ = re.compile(r"(?i)\b(эпизод|серия|episode|ep\.?)\s*№?\s*(\d{1,3})\b")

#: Виды, для которых «эпизод N» в названии — противоречие. Для SERIES и EPISODE
#: это нормально.
ВИДЫ_БЕЗ_ЭПИЗОДОВ = {"MOVIE", "DOCUMENTARY", "SHORT"}

#: Где лежит соответствие «запись → адрес». Путь задаётся средой: он
#: принадлежит конкретной сборке витрин, а не универсальному ядру. Имя каталога
#: в коде ядра означало бы, что ядро знает про одну конкретную семью сайтов.
ПЕРЕМЕННАЯ_АДРЕСОВ = "SITE_ENGINE_RENDER_STATE_DIR"


class JoinKeyError(Exception):
    """Витрины нет или её каталог нечитаем."""


def _карта_адресов(
    root: Path, site_id: str, env: dict[str, str] | None = None
) -> tuple[dict[str, str], str]:
    """Соответствие `external_id → slug` и причина, если его нет."""
    подкаталог = str((env or {}).get(ПЕРЕМЕННАЯ_АДРЕСОВ, "")).strip()
    if not подкаталог:
        return {}, f"каталог адресов не настроен: {ПЕРЕМЕННАЯ_АДРЕСОВ}"
    основа = Path(подкаталог)
    if not основа.is_absolute():
        основа = Path(root) / основа
    путь = основа / f"{site_id}.titles.json"
    if not путь.is_file():
        return {}, f"состояние отрисовки не найдено: {путь.name}"
    try:
        данные = json.loads(путь.read_text(encoding="utf-8"))
    except (OSError, ValueError) as ошибка:
        return {}, f"состояние отрисовки не читается: {ошибка}"
    карта: dict[str, str] = {}
    for ключ, значение in данные.items():
        адрес = значение.get("slug") if isinstance(значение, dict) else значение
        if адрес:
            карта[str(ключ)] = str(адрес)
    return карта, ""


def _политика(root: Path):
    """Действующий перечень разрешённых идентификаторов воспроизведения."""
    from factory.site_engine import playback_policy

    try:
        return playback_policy.resolve_cached(root=root)
    except Exception:  # noqa: BLE001
        # Нечитаемая политика не должна превращать всю карту в ошибку: причина
        # показа станет неизвестной, и это будет видно, а связь адресов —
        # главное, ради чего карта нужна, — сохранится.
        return None


def _состояние_показа(запись: dict[str, Any], решение) -> tuple[str, list[str]]:
    """Причина по записи. Считается по политике, а не берётся из поля кэша.

    Поля с причиной в кэше поставщика нет: обновление перезаписывает записи
    целиком. Считать причину заново — единственный способ отвечать за неё; поле,
    которое иногда есть, а иногда нет, давало бы «нет идентификатора» там, где
    идентификатор есть и запрещён.
    """
    агрегатор = str((запись.get("playback") or {}).get("aggregator") or "")
    if агрегатор:
        return "PLAYABLE", []
    внешние = sorted((запись.get("external_ids") or {}).keys())
    if not внешние:
        return "NO_IDENTIFIER", []
    if решение is None:
        return "PLAYBACK_POLICY_UNREADABLE", внешние
    запрещённые = [и for и in внешние if и not in решение.allowed]
    if запрещённые:
        return "IDENTIFIER_FORBIDDEN_BY_CONTRACT", запрещённые
    return "NO_IDENTIFIER", внешние


def _противоречие(название: str, вид: str) -> tuple[str, str]:
    совпадение = ЭПИЗОД_В_НАЗВАНИИ.search(название or "")
    if совпадение and вид in ВИДЫ_БЕЗ_ЭПИЗОДОВ:
        return (
            "KIND_CONTRADICTS_TITLE",
            f"название объявляет эпизод {совпадение.group(2)}, а вид — {вид}",
        )
    return "", ""


def join_keys(
    root: Path,
    site_id: str,
    *,
    env: dict[str, str] | None = None,
    offset: int = 0,
    limit: int = 500,
) -> dict[str, Any]:
    """Карта связи по одной витрине: адрес, запись, вид и состояние показа."""
    from factory.site_engine.api import overview as _overview
    from factory.site_engine.catalog_identity import decide

    данные, _ = _overview._каталог_витрины(Path(root), env, site_id)
    if данные is None:
        raise JoinKeyError(f"каталог витрины {site_id} не читается")
    записи = данные.get("items") or []

    карта, причина = _карта_адресов(Path(root), site_id, env)
    решение_политики = _политика(Path(root))
    строки: list[dict[str, Any]] = []
    for запись in записи:
        внешний = str(запись.get("external_id") or "")
        адрес = карта.get(внешний, "")
        название = str(запись.get("name") or "")
        решение = decide(
            provider_type=str(запись.get("type") or ""),
            tags=запись.get("tags") or [],
            episode_count=запись.get("episode_count"),
            entity_id=f"{site_id}:{внешний}",
            root=Path(root),
        )
        вид = решение.kind.value if hasattr(решение.kind, "value") else str(решение.kind)
        причина_показа, идентификаторы = _состояние_показа(запись, решение_политики)
        конфликт, подробность = _противоречие(название, вид)
        строки.append(
            {
                "externalId": внешний,
                "internalEntityId": f"{site_id}:{внешний}",
                "slug": адрес,
                "path": f"/title/{адрес}/" if адрес else "",
                "title": название,
                "kind": вид,
                # Состояние показа по записи, а не сводкой: сводка отвечает на
                # вопрос «сколько», а решение принимается по вопросу «эта
                # страница — какая».
                "playbackReason": причина_показа,
                "identifiers": идентификаторы,
                "kindConflict": конфликт,
                "kindConflictDetail": подробность,
            }
        )

    без_адреса = sum(1 for с in строки if not с["slug"])
    окно = строки[offset : offset + limit]
    return {
        "siteId": site_id,
        "contractVersion": "join-keys/1.0.0",
        "pathsAvailable": bool(карта),
        "reason": причина,
        "total": len(строки),
        "withoutPath": без_адреса,
        "conflicts": sum(1 for с in строки if с["kindConflict"]),
        "offset": offset,
        "limit": limit,
        "items": окно,
    }
