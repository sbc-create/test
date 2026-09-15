"""Карантин записей без видео у поставщика.

Задача простая на словах и коварная в деталях: карточку, за которой нет видео,
нельзя показывать публично, но и терять её нельзя — видео может появиться
завтра. Поэтому запись остаётся во внутреннем каталоге со своим статусом, но
исчезает из всего, что видит посетитель и поисковик: главной, листингов,
подборок, поиска, рекомендаций и карты сайта.

Отдельного внимания стоят рекомендации. Если вычистить запись из витрины, но
оставить её идентификатор в `recommendation_ids` соседних карточек, блок
«Смотрите также» начнёт вести на 404 — вместо одной спрятанной карточки
получится десяток битых ссылок.

Гейт выключен по умолчанию. Включение — отдельное решение владельца и отдельная
выкладка: при `включено=False` каталог возвращается неизменным, а отчёт всё
равно считается, чтобы можно было увидеть будущий эффект, ничего не меняя.
"""

from __future__ import annotations

import hashlib
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from factory.lords.source_availability import (
    AVAILABLE,
    SOURCE_UNAVAILABLE,
    UNKNOWN,
)

#: Поле статуса в канонических подробностях витрины.
ПОЛЕ_СТАТУСА = "source_status"

#: Флаг в заголовке опубликованного каталога. Рендерер читает именно его, а не
#: конфигурацию: артефакт самодостаточен, и витрина не может разойтись с тем,
#: что ей выложили.
ПОЛЕ_ФЛАГА = "availability_gate"


@dataclass
class Отчёт:
    """Что гейт сделал бы или сделал. Цифры считаются всегда."""

    site: str = ""
    enabled: bool = False
    total_canonical_titles: int = 0
    published_titles: int = 0
    quarantined_titles: int = 0
    unknown_titles: int = 0
    available_titles: int = 0
    recommendation_links_removed: int = 0
    published_checksum: str = ""
    quarantined_slugs: list[str] = field(default_factory=list)

    @property
    def published_playable_coverage(self) -> float:
        """Доля играющих среди опубликованных.

        Знаменатель — опубликованный набор, и это честно ровно до тех пор, пока
        рядом показан разрыв поставщика. Одна эта цифра без второй превращает
        карантин в скрытый успех.
        """
        if not self.published_titles:
            return 0.0
        return 100.0 * self.available_titles / self.published_titles

    def как_словарь(self) -> dict[str, Any]:
        return {
            "site": self.site,
            "enabled": self.enabled,
            "TOTAL_CANONICAL_TITLES": self.total_canonical_titles,
            "PUBLISHED_TITLES": self.published_titles,
            "QUARANTINED_TITLES": self.quarantined_titles,
            "UNKNOWN_TITLES": self.unknown_titles,
            "PUBLISHED_PLAYABLE_COVERAGE": round(self.published_playable_coverage, 4),
            "RECOMMENDATION_LINKS_REMOVED": self.recommendation_links_removed,
            "PUBLISHED_CHECKSUM": self.published_checksum,
        }


def контрольная_сумма(слаги: list[str]) -> str:
    """Отпечаток опубликованного набора.

    Считается по отсортированным слагам: публикация не должна зависеть от того,
    в каком порядке поставщик перечислил записи.
    """
    основа = "\n".join(sorted(слаги)).encode("utf-8")
    return hashlib.sha256(основа).hexdigest()


def _идентификатор(запись: dict[str, Any]) -> str:
    return str(запись.get("id") or "").strip().lower()


def применить(
    каталог: dict[str, Any],
    подробности: dict[str, Any],
    статус: Callable[[str], str],
    *,
    включено: bool,
    site: str = "",
) -> tuple[dict[str, Any], dict[str, Any], Отчёт]:
    """Проставить статусы и, если гейт включён, убрать карантин из публикации.

    Возвращает новые каталог и подробности — исходные словари не изменяются,
    чтобы вызывающий мог сравнить «до» и «после» и отказаться от применения.
    """
    записи = dict(подробности.get("details") or {})
    отчёт = Отчёт(site=site or str(каталог.get("site") or ""), enabled=включено)

    # 1. Статус проставляется всем записям независимо от флага: внутренний
    #    каталог должен знать правду даже при выключенном гейте.
    новые_записи: dict[str, Any] = {}
    в_карантине: set[str] = set()
    for слаг, запись in записи.items():
        if not isinstance(запись, dict):
            новые_записи[слаг] = запись
            continue
        копия = dict(запись)
        с = статус(_идентификатор(запись))
        копия[ПОЛЕ_СТАТУСА] = с
        новые_записи[слаг] = копия
        if с == SOURCE_UNAVAILABLE:
            в_карантине.add(слаг)
        elif с == UNKNOWN:
            отчёт.unknown_titles += 1
        elif с == AVAILABLE:
            отчёт.available_titles += 1

    отчёт.total_canonical_titles = sum(
        1 for з in новые_записи.values() if isinstance(з, dict)
    )
    отчёт.quarantined_titles = len(в_карантине)
    отчёт.quarantined_slugs = sorted(в_карантине)

    элементы = list(каталог.get("items") or [])
    новый_каталог = dict(каталог)

    if not включено:
        # Флаг выключен: публикуемый набор прежний, цифры посчитаны как прогноз.
        отчёт.published_titles = len(элементы)
        отчёт.published_checksum = контрольная_сумма(
            [str(э.get("slug") or "") for э in элементы if isinstance(э, dict)]
        )
        новый_каталог[ПОЛЕ_ФЛАГА] = False
        новые_подробности = dict(подробности)
        новые_подробности["details"] = новые_записи
        return новый_каталог, новые_подробности, отчёт

    # 2. Убираем карантин из публичного набора.
    оставшиеся = [
        э for э in элементы
        if not (isinstance(э, dict) and str(э.get("slug") or "") in в_карантине)
    ]
    слаги_оставшихся = {
        str(э.get("slug") or "") for э in оставшиеся if isinstance(э, dict)
    }

    # 3. Чистим рекомендации: ссылка на спрятанную запись — это будущая 404.
    #    Рекомендации хранятся идентификаторами поставщика, поэтому сначала
    #    нужен перевод «идентификатор → слаг» по всему каталогу.
    слаг_по_ид: dict[str, str] = {}
    for слаг, запись in новые_записи.items():
        if isinstance(запись, dict):
            ид = _идентификатор(запись)
            if ид:
                слаг_по_ид[ид] = слаг

    убрано = 0
    for запись in новые_записи.values():
        if not isinstance(запись, dict):
            continue
        ссылки = запись.get("recommendation_ids")
        if not isinstance(ссылки, list) or not ссылки:
            continue
        отфильтрованные = []
        for ид in ссылки:
            цель = слаг_по_ид.get(str(ид).strip().lower())
            if цель is not None and цель not in слаги_оставшихся:
                убрано += 1
                continue
            отфильтрованные.append(ид)
        if len(отфильтрованные) != len(ссылки):
            запись["recommendation_ids"] = отфильтрованные
    отчёт.recommendation_links_removed = убрано

    отчёт.published_titles = len(оставшиеся)
    отчёт.published_checksum = контрольная_сумма(sorted(слаги_оставшихся))

    новый_каталог["items"] = оставшиеся
    новый_каталог["count"] = len(оставшиеся)
    новый_каталог[ПОЛЕ_ФЛАГА] = True
    новый_каталог["published_checksum"] = отчёт.published_checksum

    новые_подробности = dict(подробности)
    новые_подробности["details"] = новые_записи
    return новый_каталог, новые_подробности, отчёт
