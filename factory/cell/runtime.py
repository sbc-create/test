"""Где витрина живёт на самом деле — один ответ для всех, кто её трогает.

Зачем
-----

Производители содержимого знали про службы по собственным спискам: таблица в
`content-pipeline/refresh.py`, массив `SITES` в `nova-daily-refresh.sh`. После
переноса сайта в свою ячейку эти списки продолжали звать прежний unit по имени
и писать снимок каталога по прежнему пути. Снаружи это выглядело как сайт,
который «перестал пополняться», и никакой ошибки нигде не появлялось.

Здесь один ответ на три вопроса, которые производитель обязан задать перед
доставкой:

1. **куда** класть снимок — каталог данных ячейки или прежний общий путь;
2. **кого** уведомлять — и нужно ли уведомлять вообще;
3. **чем** уведомлять — перезапуском службы или ничем.

Третий вопрос не косметический. Витрина Zona перечитывает снимок сама, по
mtime, на ближайшем запросе: перезапуск ей не нужен, а стоит он минут — она
читает каталог 16.7 МБ и detail 78.3 МБ. Производитель, ходящий раз в пять
минут, превращал бы это в постоянную недоступность. Остальные семейства такого
перечитывания не умеют, и для них перезапуск обязателен. Разницу нельзя
угадывать — она объявлена в реестре полем `runtime.reload`.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from factory.cell import registry

#: Режим, который производитель обязан принять, если сайт про себя молчит.
#: Осторожный по построению: лишний перезапуск заметен и дорог, пропущенный —
#: незаметен и оставляет витрину на вчерашнем каталоге.
РЕЖИМ_ПО_УМОЛЧАНИЮ = "restart"


class RuntimeUnknown(Exception):
    """Про размещение витрины в реестре ничего не записано."""


@dataclass(frozen=True)
class Размещение:
    """Ответ производителю. Ровно то, что ему нужно, и ничего больше."""

    site_id: str
    domain: str
    #: Каталог, куда класть снимки. None — писать по прежнему общему пути.
    data_dir: str | None
    #: Служба, которую можно уведомлять. None — уведомлять некого.
    unit: str | None
    #: Служба до переноса. Её звать нельзя: она закрыта от ручного запуска.
    previous_unit: str | None
    port: int | None
    account: str | None
    reload: str
    managed_by: str

    @property
    def нужен_перезапуск(self) -> bool:
        """Перезапуск нужен только там, где витрина не перечитывает сама."""
        return self.reload != "mtime"

    def as_dict(self) -> dict[str, Any]:
        return {"site_id": self.site_id, "domain": self.domain,
                "data_dir": self.data_dir, "unit": self.unit,
                "previous_unit": self.previous_unit, "port": self.port,
                "account": self.account,
                "reload": self.reload, "managed_by": self.managed_by,
                "restart_required": self.нужен_перезапуск}


def размещение(site_id: str, *, path: Path | None = None) -> Размещение:
    """Размещение зарегистрированной витрины."""
    cell = registry.resolve(site_id, path) if path else registry.resolve(site_id)
    блок = cell.runtime or {}
    if not блок:
        raise RuntimeUnknown(
            f"{site_id}: в реестре нет блока runtime. Производитель не должен "
            "догадываться, куда доставлять и кого перезапускать: отсутствие "
            "записи — повод остановиться, а не выбрать прежний путь по привычке")
    return Размещение(
        site_id=cell.site_id, domain=cell.domain,
        data_dir=блок.get("data_dir"), unit=блок.get("unit"),
        previous_unit=блок.get("previous_unit"), port=блок.get("port"),
        account=блок.get("account"),
        reload=блок.get("reload") or РЕЖИМ_ПО_УМОЛЧАНИЮ,
        managed_by=блок.get("managed_by") or "monolith",
    )


def все_размещения(path: Path | None = None) -> dict[str, Размещение]:
    итог = {}
    for cell in registry.all_cells(path):
        try:
            итог[cell.site_id] = размещение(cell.site_id, path=path)
        except (RuntimeUnknown, registry.RegistryError):
            continue
    return итог


def для_производителя(path: Path | None = None) -> dict[str, dict[str, Any]]:
    """Плоский словарь для тех, кто не может импортировать фабрику.

    Производители — отдельные процессы с собственными зависимостями; тянуть в
    них весь пакет ради трёх полей неправильно. Они читают этот же реестр
    файлом, а формат ответа задан здесь, чтобы он был один.
    """
    return {s: р.as_dict() for s, р in все_размещения(path).items()}


def прочитать_реестр_файлом(путь: str | Path) -> dict[str, dict[str, Any]]:
    """Тот же ответ, но без импорта фабрики — для сторонних процессов.

    Намеренно повторяет минимум логики и ничего не проверяет сверх формата:
    производитель, не сумевший прочитать реестр, обязан остановиться, а не
    чинить его на ходу.
    """
    данные = json.loads(Path(путь).read_text(encoding="utf-8"))
    итог: dict[str, dict[str, Any]] = {}
    for c in данные.get("cells") or []:
        блок = c.get("runtime") or {}
        if not блок:
            continue
        режим = блок.get("reload") or РЕЖИМ_ПО_УМОЛЧАНИЮ
        итог[c["site_id"]] = {
            "site_id": c["site_id"], "domain": c.get("domain"),
            "data_dir": блок.get("data_dir"), "unit": блок.get("unit"),
            "previous_unit": блок.get("previous_unit"), "port": блок.get("port"),
            "account": блок.get("account"), "reload": режим, "managed_by": блок.get("managed_by") or "monolith",
            "restart_required": режим != "mtime",
        }
    return итог
