"""Выдача контракта `seo-route-binding` через Site View API.

Без этого модуля контракт существовал только в виде кода и файлов: его можно
было собрать у себя, но нельзя было получить у работающего движка. Потребитель
при этом обязан читать контракт у движка, а не воспроизводить сборку — иначе
у контракта два источника, и они разъедутся на первой же правке любого из них.

Модуль ничего не вычисляет сам и не знает ни одной витрины по имени. Он
читает из настройки (`config/seo-binding-sources.yaml`), какой **способ
адресации** у витрины, и просит пакет адаптеров выгрузить связи этим способом.
Добавление витрины — правка настройки; новый способ адресации — новый адаптер.

Выдача постраничная намеренно. Каталог — пятьдесят три тысячи записей, и ответ
целиком означал бы, что потребитель либо держит его в памяти, либо не получает
вовсе. Отпечаток выгрузки при этом считается по всему набору, а не по
странице: иначе он перестал бы отвечать на вопрос «изменились ли данные».
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

#: Файл, описывающий, какая витрина каким производителем обслуживается.
SOURCES_REF = "config/seo-binding-sources.yaml"

#: Предел размера страницы. Больше пятисот записей ответ становится тяжелее
#: любого разумного разбора, меньше единицы — бессмысленным.
LIMIT_RANGE = (1, 500)
DEFAULT_LIMIT = 100


class BindingSourceUnknown(LookupError):
    """Витрина не описана в настройке источников."""


def _sources(root: Path) -> dict[str, Any]:
    import yaml

    путь = root / SOURCES_REF
    if not путь.exists():
        return {}
    return yaml.safe_load(путь.read_text(encoding="utf-8")) or {}


def описание(root: Path, site_id: str) -> dict[str, Any]:
    """Как собирать связи для этой витрины. Отказ — если не описана."""
    источники = (_sources(root).get("sites") or {})
    описано = источники.get(site_id)
    if not isinstance(описано, dict):
        raise BindingSourceUnknown(
            f"витрина {site_id!r} не описана в {SOURCES_REF}: производитель "
            "связей выбирается настройкой, а не догадкой по имени")
    return описано


def выгрузка(root: Path, site_id: str) -> dict[str, Any]:
    """Полная выгрузка связей витрины через её производителя.

    Какой адаптер обслуживает какой способ адресации, знает пакет адаптеров:
    он для того и существует, чтобы знать про конкретную реализацию. Здесь
    известен только вид производителя, и это правильно — универсальный модуль
    не должен называть ни одной витрины.
    """
    from factory.site_engine import adapters

    описано = описание(root, site_id)
    вид = str(описано.get("producer") or "")
    try:
        return adapters.export_bindings(вид, root=root, site_id=site_id,
                                        spec=описано)
    except LookupError as error:
        raise BindingSourceUnknown(str(error)) from error


def страница(root: Path, site_id: str, *, offset: int = 0,
             limit: int = DEFAULT_LIMIT,
             binding_state: str | None = None) -> dict[str, Any]:
    """Страница выгрузки. Отпечаток считается по всему набору.

    `binding_state` сужает выдачу до одного состояния связи — так очередь
    разбора получается одним запросом, а не вычиткой всего каталога.
    """
    низ, верх = LIMIT_RANGE
    if not isinstance(limit, int) or isinstance(limit, bool) or not низ <= limit <= верх:
        raise ValueError(f"limit — целое от {низ} до {верх}")
    if not isinstance(offset, int) or isinstance(offset, bool) or offset < 0:
        raise ValueError("offset — целое не меньше нуля")

    полная = выгрузка(root, site_id)
    записи = полная["bindings"]
    if binding_state:
        записи = [b for b in записи if b["bindingState"] == binding_state]

    окно = записи[offset:offset + limit]
    return {
        "schemaVersion": полная["schemaVersion"],
        "contractVersion": полная["contractVersion"],
        "siteId": полная["siteId"],
        "snapshotAt": полная["snapshotAt"],
        "provenance": полная["provenance"],
        # Отпечаток всего набора, а не страницы: он отвечает на вопрос
        # «изменились ли данные», и по странице такой ответ был бы ложным.
        "digest": полная["digest"],
        "records": полная["records"],
        "byBindingState": полная["byBindingState"],
        "filter": {"bindingState": binding_state} if binding_state else {},
        "offset": offset,
        "limit": limit,
        "returned": len(окно),
        "hasMore": offset + len(окно) < len(записи),
        "bindings": окно,
    }


def каталог_витрин(root: Path) -> dict[str, Any]:
    """Какие витрины умеют отдавать связи и каким производителем."""
    источники = (_sources(root).get("sites") or {})
    return {
        "contract": "seo-route-binding/1.0.0",
        "sites": [
            {"siteId": имя, "producer": (описано or {}).get("producer", "")}
            for имя, описано in sorted(источники.items())
        ],
    }
