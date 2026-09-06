"""Пересборка очереди разбора из каталога витрины.

Очередь умела читать, решать, утверждать, публиковать и откатывать — и ничто её
не наполняло. Записи появлялись однажды и вручную: пересчёт каталога их не
обновлял, а новое противоречие в новых данных до редактора не доходило вовсе.
Для флота это то же самое, что не иметь очереди: заводить её руками на каждой
витрине никто не станет.

Три правила, каждое написано на конкретный способ навредить.

**Решение редактора переживает пересборку.** Обновляются только утверждения и
рекомендация; состояние, решение и история остаются. Иначе повторный обход
стирает работу людей, и очередь становится опасной.

**Пересборка не выдумывает конфликтов.** В очередь попадает только названное
противоречие: спор в данных поставщика или название, объявляющее эпизод при
виде «фильм». Всё остальное — не спор, а обычная запись.

**Очередь принадлежит витрине.** Пересборка одной витрины не трогает записи
другой: у флота своя очередь у каждого сайта.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from factory.site_engine.content_kind import ВИДЫ_БЕЗ_ЭПИЗОДОВ, ЭПИЗОД_В_НАЗВАНИИ
from factory.site_engine.review_queue import Claim, ReviewItem, ReviewQueue, item_id_for

ПОЛЕ = "contentKind"


class ReviewBuildError(Exception):
    """Каталог витрины недоступен. Пустая очередь на его месте — ложь."""


def _вид_по_типу(тип: str) -> str:
    """Вид, который следует из типа поставщика. Договор, а не сырая строка."""
    from factory.site_engine.content_kind import ALIASES, normalise_alias

    вид = ALIASES.get(normalise_alias(тип))
    return вид.value if вид is not None else "UNKNOWN"


def _виды_по_тегам(теги) -> list[str]:
    """Виды, которые следуют из тегов записи."""
    from factory.site_engine.content_kind import KIND_TAGS, normalise_alias

    найдено = []
    for тег in теги or ():
        вид = KIND_TAGS.get(normalise_alias(str(тег)))
        if вид is not None and вид.value not in найдено:
            найдено.append(вид.value)
    return найдено


def _противоречие_названия(название: str, вид: str) -> tuple[str, str]:
    """Название объявляет эпизод, а вид — не эпизод.

    Проверяется явная форма с номером: догадка по одному слову дала бы ложные
    срабатывания на названиях вроде «Эпизод неудачи».
    """
    совпадение = ЭПИЗОД_В_НАЗВАНИИ.search(название or "")
    if совпадение and вид in ВИДЫ_БЕЗ_ЭПИЗОДОВ:
        return "EPISODE", f"название объявляет эпизод {совпадение.group(2)}, а вид — {вид}"
    return "", ""


def rebuild(
    root: Path | str, site_id: str, *, env: dict[str, str] | None = None, limit: int = 1000
) -> dict[str, Any]:
    """Пересобрать очередь разбора витрины из её каталога."""
    from factory.site_engine.api import overview as _overview
    from factory.site_engine.catalog_identity import decide

    корень = Path(root)
    данные, _ = _overview._каталог_витрины(корень, env, site_id)
    if данные is None:
        raise ReviewBuildError(f"каталог витрины {site_id} не читается")

    очередь = ReviewQueue(корень)
    создано = 0
    обновлено = 0
    просмотрено = 0
    for запись in (данные.get("items") or [])[:limit]:
        просмотрено += 1
        внешний = str(запись.get("external_id") or "")
        если_id = f"{site_id}:{внешний}"
        решение = decide(
            provider_type=str(запись.get("type") or ""),
            tags=запись.get("tags") or [],
            episode_count=запись.get("episode_count"),
            entity_id=если_id,
            root=корень,
        )
        вид = решение.kind.value if hasattr(решение.kind, "value") else str(решение.kind)
        название = str(запись.get("name") or "")

        утверждения: list[Claim] = []
        код = ""
        рекомендация = ""
        основание = ""

        if решение.conflicts:
            код = решение.conflicts[0]
            основание = решение.reason or "источник противоречит сам себе"
            # Стороны спора — это виды из договора, а не сырые строки источника.
            # «TV» и «UNKNOWN» в качестве вариантов выбора бесполезны: первого
            # нет в договоре, второй и есть исходное состояние конфликта.
            от_поставщика = _вид_по_типу(str(запись.get("type") or ""))
            от_тегов = _виды_по_тегам(запись.get("tags") or [])
            варианты = [в for в in ([от_поставщика] + от_тегов) if в and в != "UNKNOWN"]
            варианты = list(dict.fromkeys(варианты))
            if len(варианты) < 2:
                # Спор без двух названных сторон разбирать нечем: показывать
                # редактору выбор из одного значения — просить нажать кнопку.
                continue
            рекомендация = варианты[0]
            утверждения = [
                Claim(
                    value=от_поставщика,
                    source="provider.type",
                    evidence=f"тип поставщика: {запись.get('type')!r}",
                ),
            ] + [
                Claim(
                    value=в,
                    source="provider.tags",
                    evidence=f"теги: {', '.join(запись.get('tags') or []) or 'нет'}",
                )
                for в in от_тегов
                if в != от_поставщика and в != "UNKNOWN"
            ]
        else:
            предложение, почему = _противоречие_названия(название, вид)
            if предложение and вид != "UNKNOWN":
                код = "KIND_CONTRADICTS_TITLE"
                рекомендация = предложение
                основание = почему
                утверждения = [
                    Claim(value=вид, source="catalog.kind", evidence=f"вид записи: {вид}"),
                    Claim(
                        value=предложение,
                        source="catalog.title",
                        evidence=f"название: {название}",
                    ),
                ]

        if not код:
            continue

        элемент = ReviewItem(
            item_id=item_id_for(если_id, ПОЛЕ),
            internal_entity_id=если_id,
            site_id=site_id,
            conflict_code=код,
            field=ПОЛЕ,
            claims=tuple(утверждения),
            title=название,
            year=запись.get("year") if isinstance(запись.get("year"), int) else None,
            external_ids=dict(запись.get("external_ids") or {}),
            recommendation=рекомендация,
            # Рекомендация без основания бесполезна: редактор не может её
            # проверить и либо принимает вслепую, либо игнорирует.
            recommendation_reason=основание,
        )
        # Записи очереди нет открытой проверки на существование; читаем и
        # ловим отсутствие. Отдельный метод ради этого заводить незачем.
        try:
            очередь.get(элемент.item_id)
            существовала = True
        except Exception:  # noqa: BLE001
            существовала = False
        очередь.upsert(элемент)
        обновлено += 1 if существовала else 0
        создано += 0 if существовала else 1

    return {
        "siteId": site_id,
        "scanned": просмотрено,
        "created": создано,
        "updated": обновлено,
    }
