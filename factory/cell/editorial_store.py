"""Хранение редакторских правок между управляющим слоем и витриной.

Зачем отдельный слой, а не запись из админки прямо в хранилище витрины.
Control API сам объявляет это решением: «Управляющий слой не должен иметь
доступа к данным витрин: тогда его ошибка останется ошибкой планирования, а не
порчей чужого состояния». Инвалидация кэша там уже идёт заданием в очередь, и
правки идут тем же путём.

Отсюда устройство из двух шагов:

    админка → черновик в подготовительном каталоге управляющего слоя
            → заявка в очередь (только site_id, коммит и digest содержимого)
            → исполнитель читает подготовленное, сверяет digest,
              атомарно кладёт в хранилище ячейки от имени учётной записи сайта

Схема заявки остаётся закрытой: ни путей, ни команд в ней нет. Путь
подготовленного файла выводится из `site_id` обеими сторонами по одному
правилу, а `digest` доказывает, что исполнитель применил именно то, что
подготовил управляющий слой, — не «файл по такому-то пути», а конкретное
содержимое.

Формат файла — тот, который читает витрина (`editorial_overlay.Правки`):
`site_id` внутри, правки по постоянному ID записи. `site_id` в содержимом
сверяется дважды: здесь при подготовке и на витрине при чтении. Область сайта
входит в данные, а не проверяется где-то потом.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any

#: Подготовительный каталог управляющего слоя. Витрина сюда не смотрит.
БАЗА = Path(os.environ.get("SITE_EDITORIAL_STAGING", "/var/lib/site-cells/editorial"))

#: Имя файла правок в хранилище витрины. То же имя объявлено `user_writable`
#: в `config/site.json` каждой подключённой витрины.
ИМЯ_ФАЙЛА = "editorial-overrides.json"

СХЕМА = 1

#: Поля, которые вправе менять редактор. Держится синхронно со стороной
#: витрины (`editorial_overlay.ВСЕ_ПОЛЯ`); расхождение ловит проверка.
ПОЛЯ = ("name", "original_name", "poster_url", "year", "kind",
        "description", "seo_title", "seo_description")


class StoreRejected(Exception):
    """Подготовка отвергнута до записи."""


def путь_подготовки(site_id: str, *, база: Path | None = None) -> Path:
    if not site_id or "/" in site_id or site_id.startswith("."):
        raise StoreRejected(f"негодный site_id: {site_id!r}")
    return (база or БАЗА) / f"{site_id}.json"


def собрать(site_id: str, правки: dict[str, dict[str, Any]], *,
            actor: str, reason: str) -> dict[str, Any]:
    """Содержимое файла правок. Чистая функция: ничего не пишет."""
    if not reason.strip():
        raise StoreRejected("правка без причины не принимается: журнал без "
                            "причины отвечает «что», но не «почему»")
    собрано: dict[str, Any] = {}
    for ключ, запись in (правки or {}).items():
        поля = (запись or {}).get("fields") or {}
        лишние = sorted(set(поля) - set(ПОЛЯ))
        if лишние:
            raise StoreRejected(
                f"поля {лишние} принадлежат поставщику и правке не подлежат")
        чистые = {к: з for к, з in поля.items() if з not in (None, "")}
        if чистые:
            собрано[str(ключ)] = {"fields": чистые,
                                  "actor": actor, "reason": reason.strip()}
    return {"schema_version": СХЕМА, "site_id": site_id, "overrides": собрано}


def отпечаток(содержимое: dict[str, Any]) -> str:
    """sha256 канонической записи. Тот же байт-в-байт текст и запишется."""
    return "sha256:" + hashlib.sha256(текст(содержимое).encode("utf-8")).hexdigest()


def текст(содержимое: dict[str, Any]) -> str:
    """Каноническая запись: отсортированные ключи, перевод строки в конце.

    Канон обязателен: иначе digest зависел бы от порядка словаря, и повтор той
    же правки давал бы новый идентификатор заявки — то есть вторую операцию
    вместо повтора.
    """
    return json.dumps(содержимое, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":")) + "\n"


def подготовить(site_id: str, правки: dict[str, dict[str, Any]], *,
                actor: str, reason: str, база: Path | None = None) -> dict[str, Any]:
    """Положить черновик в подготовительный каталог и вернуть его digest."""
    содержимое = собрать(site_id, правки, actor=actor, reason=reason)
    путь = путь_подготовки(site_id, база=база)
    путь.parent.mkdir(parents=True, exist_ok=True)
    врем = путь.with_suffix(".json.new")
    врем.write_text(текст(содержимое), encoding="utf-8")
    os.replace(врем, путь)
    return {"site_id": site_id, "path": str(путь), "digest": отпечаток(содержимое),
            "entries": len(содержимое["overrides"])}


def прочитать_подготовленное(site_id: str, *, база: Path | None = None) -> dict[str, Any]:
    путь = путь_подготовки(site_id, база=база)
    if not путь.is_file():
        raise StoreRejected(f"подготовленных правок для {site_id} нет")
    try:
        содержимое = json.loads(путь.read_text(encoding="utf-8"))
    except (OSError, ValueError) as ош:
        raise StoreRejected(f"подготовленное не читается: {ош}") from None
    if содержимое.get("site_id") != site_id:
        # Чужой файл в своём месте — это не опечатка, а перепутанная область.
        raise StoreRejected(
            f"подготовлено для сайта {содержимое.get('site_id')!r}, "
            f"а применяется к {site_id!r}")
    return содержимое
