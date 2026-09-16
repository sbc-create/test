"""Содержимое витрины из её собственного пакета.

Три семейства из пяти объявляют источник `fixture`: набор записей лежит в пакете
самой витрины, а не приходит от поставщика. Движок читать такой источник не
умел — каталог он брал только из кэша поставщика. Админка семейства работала
целиком, а управлять было нечем: пустой каталог, пустая очередь, публиковать
нечего.

Три правила, каждое написано на конкретный способ соврать.

**Отпечаток проверяется, если объявлен.** Пакет объявляет sha256 набора. Чтение
без сверки означает, что подменённый набор попадёт на витрину молча — и разница
обнаружится по содержимому страниц, а не по отказу.

**Отсутствующий набор — отказ, а не пустой каталог.** Пустой каталог отвечает
200 и выглядит исправной витриной без материалов; именно так каталог
тридцатипятичасовой давности месяцами считался работающим.

**Перенос ничего не выдумывает.** Записи без идентификатора отвергаются целиком,
а не получают выдуманный: придуманный идентификатор нельзя сопоставить ни с
чем, и первое же обновление создаст дубль.
"""

from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path
from typing import Any

ВЕРСИЯ = "content-fixture/1.0.0"

#: Как называется вид в наборе и как — в каталоге движка. Соответствие явное:
#: молчаливое совпадение имён однажды разойдётся, и вид приедет пустым.
ПОЛЕ_ВИДА = ("kind", "type")
ПОЛЕ_НАЗВАНИЯ = ("title", "name")
ПОЛЕ_ИДЕНТИФИКАТОРА = ("id", "external_id", "slug")


class FixtureError(Exception):
    """Набор недоступен, подменён или непригоден. Пустой каталог — не ответ."""


def _пакет(root: Path, site_id: str) -> dict[str, Any]:
    import yaml

    путь = Path(root) / "sites" / site_id / "package.yaml"
    if not путь.is_file():
        raise FixtureError(f"пакета витрины {site_id} нет: {путь}")
    try:
        return yaml.safe_load(путь.read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError) as ошибка:
        raise FixtureError(f"пакет витрины {site_id} не читается: {ошибка}") from ошибка


def _первое(запись: dict[str, Any], имена: tuple[str, ...]) -> Any:
    for имя in имена:
        значение = запись.get(имя)
        if значение not in (None, ""):
            return значение
    return None


def ingest(
    root: Path | str, site_id: str, *, env: dict[str, str] | None = None
) -> dict[str, Any]:
    """Перенести набор из пакета витрины в каталог движка."""
    корень = Path(root)
    пакет = _пакет(корень, site_id)
    источник = пакет.get("content_source") or {}
    вид_источника = str(источник.get("kind") or "")
    if вид_источника != "fixture":
        raise FixtureError(
            f"источник витрины {site_id} — {вид_источника!r}, а не fixture: "
            "подменять путь поставщика набором из пакета нельзя"
        )

    ссылка = str(пакет.get("content_package_ref") or "content/catalog.json")
    файл = корень / "sites" / site_id / ссылка
    if not файл.is_file():
        raise FixtureError(f"набор витрины {site_id} не найден: {ссылка}")
    тело = файл.read_text(encoding="utf-8")

    # Ровно `is not None`, а не `or ""`: значение из YAML может оказаться
    # числом (строка из одних нулей разбирается как ноль), а ноль ложен — и
    # объявленный отпечаток молча перестал бы проверяться.
    сырой = пакет.get("content_package_sha256")
    объявлен = "" if сырой is None else str(сырой).strip()
    if объявлен:
        отпечаток = hashlib.sha256(тело.encode("utf-8")).hexdigest()
        if отпечаток != объявлен:
            raise FixtureError(
                f"отпечаток набора не совпадает с объявленным в пакете: "
                f"{отпечаток[:12]}… вместо {объявлен[:12]}…"
            )

    try:
        набор = json.loads(тело)
    except ValueError as ошибка:
        raise FixtureError(f"набор витрины {site_id} не разбирается: {ошибка}") from ошибка

    записи: list[dict[str, Any]] = []
    for сырая in набор.get("titles") or []:
        внешний = _первое(сырая, ПОЛЕ_ИДЕНТИФИКАТОРА)
        if not внешний:
            raise FixtureError(
                "в наборе есть запись без идентификатора; выдуманный идентификатор "
                "нельзя сопоставить ни с чем, и первое обновление создаст дубль"
            )
        запись: dict[str, Any] = {
            "external_id": str(внешний),
            "name": str(_первое(сырая, ПОЛЕ_НАЗВАНИЯ) or ""),
            "type": str(_первое(сырая, ПОЛЕ_ВИДА) or ""),
            # Полей, которых в наборе нет, не выдумываем: пустое значение
            # честнее правдоподобного.
            "tags": list(сырая.get("tags") or []),
            "external_ids": dict(сырая.get("external_ids") or {}),
            "playback": сырая.get("playback"),
        }
        год = сырая.get("year")
        if isinstance(год, int):
            запись["year"] = год
        записи.append(запись)

    подкаталог = str((env or {}).get("SITE_ENGINE_CATALOG_DIR", "")).strip()
    if not подкаталог:
        raise FixtureError("каталог движка не настроен: SITE_ENGINE_CATALOG_DIR")
    основа = Path(подкаталог)
    if not основа.is_absolute():
        основа = корень / основа
    основа.mkdir(parents=True, exist_ok=True)
    цель = основа / f"{site_id}.json"
    временный = цель.with_suffix(".json.tmp")
    временный.write_text(
        json.dumps(
            {
                "fetched_at_ms": int(time.time() * 1000),
                # Происхождение записано в самом каталоге: через месяц набор из
                # пакета неотличим от выдачи поставщика.
                "source": f"fixture:{ссылка}",
                "contractVersion": ВЕРСИЯ,
                "items": записи,
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    временный.replace(цель)
    return {
        "siteId": site_id,
        "records": len(записи),
        "source": f"fixture:{ссылка}",
        "digestVerified": bool(объявлен),
    }
