#!/usr/bin/env python3
"""Editorial cycle demonstration: announce -> release -> update / retire.

Shows the full lifecycle including the cases the operator must refuse: an
unsourced claim, a stale promise left on the site, and an expired pin.
All entities are synthetic.
"""

from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from seo_operator.editorial import (  # noqa: E402
    Announcement,
    AnnouncementState,
    BacklogItem,
    Claim,
    EditorialCalendar,
    EditorialSource,
    SourceTrust,
    UnsourcedClaimError,
    detect_cross_site_duplication,
    find_expired_pins,
    find_stale_promises,
)

OUT = REPO / "docs" / "seo-operator" / "demo-editorial-cycle.md"

OFFICIAL = EditorialSource(
    "src-studio",
    "Официальный канал студии",
    "https://studio.example-fixture.test/news",
    SourceTrust.OFFICIAL,
    rights_confirmed=True,
)
LICENSED = EditorialSource(
    "src-catalog",
    "Лицензированный каталог",
    "https://catalog.example-fixture.test",
    SourceTrust.LICENSED_FEED,
    rights_confirmed=True,
)
RUMOUR = EditorialSource(
    "src-forum",
    "Форум пользователей",
    "https://forum.example-fixture.test",
    SourceTrust.UNCONFIRMED,
    rights_confirmed=False,
)


def main() -> int:
    lines: list[str] = []
    a = lines.append
    today = date(2026, 8, 22)

    a("# Демонстрация редакционного цикла")
    a("")
    a(
        "Сгенерировано `scripts/demo_editorial.py`. Все произведения, даты и источники "
        "синтетические."
    )
    a("")
    a(f"Условная дата прогона: **{today.isoformat()}**")
    a("")

    # --- 1. Анонс ----------------------------------------------------
    a("## 1. Анонс на подтверждённом источнике")
    a("")
    announcement = Announcement(
        site_id="fixture-anime",
        entity_id="title-42",
        title_claim=Claim("title", "Условный тайтл", OFFICIAL),
        release_date_claim=Claim("release_date", "2026-09-05", OFFICIAL),
        pinned_until="2026-09-12",
    )
    a(f"- Создан анонс `{announcement.announcement_id}`")
    a(f"- Состояние: **{announcement.state.value}**")
    a(
        f"- Дата релиза: **{announcement.release_date}** (источник: {OFFICIAL.name}, "
        f"уровень доверия `{OFFICIAL.trust.value}`, права подтверждены)"
    )
    a(f"- Закреплён в блоке «Скоро» до **{announcement.pinned_until}**")
    a("")

    # --- 2. Отказ от непроверенного --------------------------------
    a("## 2. Попытка анонса по неподтверждённому источнику")
    a("")
    try:
        Claim("release_date", "2026-10-01", RUMOUR)
        a("- ОШИБКА: непроверенное утверждение прошло")
    except UnsourcedClaimError as exc:
        a(f"- Отклонено: `{exc}`")
    a("")
    a(
        "Оператор не может создать дату выхода, сюжет, актёрский состав или рейтинг "
        "в обход этой проверки: объект утверждения просто не конструируется."
    )
    a("")

    # --- 3. Релиз ----------------------------------------------------
    a("## 3. Выход: перевод анонса в релиз")
    a("")
    announcement.transition(
        AnnouncementState.RELEASED, source=LICENSED, note="появилось в лицензированном каталоге"
    )
    a(f"- Состояние: **{announcement.state.value}**")
    a(f"- Источник перехода: {LICENSED.name}")
    a(
        "- Действия на витрине: карточка переносится из «Скоро» в «Новинки», "
        "обновляются title/H1/intro, снимается формулировка про ожидание."
    )
    a("")

    # --- 4. Просроченное обещание -----------------------------------
    a("## 4. Просроченное обещание на другом тайтле")
    a("")
    stale = Announcement(
        site_id="fixture-anime",
        entity_id="title-77",
        title_claim=Claim("title", "Другой условный тайтл", OFFICIAL),
        release_date_claim=Claim("release_date", "2026-08-01", OFFICIAL),
        pinned_until="2026-08-10",
    )
    found = find_stale_promises([announcement, stale], today)
    a(f"- Найдено просроченных обещаний: **{len(found)}**")
    for item in found:
        a(
            f"  - `{item.entity_id}`: обещан {item.release_date}, "
            f"состояние всё ещё `{item.state.value}`"
        )
    a("")
    a(
        "Оператор обязан либо подтвердить выход, либо зафиксировать перенос/отмену. "
        "Оставлять на сайте обещание с прошедшей датой запрещено."
    )
    a("")

    stale.transition(
        AnnouncementState.DELAYED, source=OFFICIAL, note="студия объявила перенос без новой даты"
    )
    a(f"- После обработки: `{stale.entity_id}` → **{stale.state.value}**")
    a(
        f"- Просроченных обещаний осталось: "
        f"**{len(find_stale_promises([announcement, stale], today))}**"
    )
    a("")

    # --- 5. Просроченные пины ---------------------------------------
    a("## 5. Просроченные закрепления")
    a("")
    expired = find_expired_pins([announcement, stale], today)
    a(f"- Найдено просроченных пинов: **{len(expired)}**")
    for item in expired:
        a(f"  - `{item.entity_id}`: закрепление истекло {item.pinned_until}")
    a("")
    for item in expired:
        item.transition(
            AnnouncementState.RETIRED, source=OFFICIAL, note="снят с витрины, промо-блоки очищены"
        )
    a(f"- После очистки состояние `{stale.entity_id}`: **{stale.state.value}**")
    a("")

    # --- 6. История ---------------------------------------------------
    a("## 6. История переходов (audit trail)")
    a("")
    a("| entity | из | в | источник | примечание |")
    a("| --- | --- | --- | --- | --- |")
    for item in (announcement, stale):
        for h in item.history:
            a(f"| `{item.entity_id}` | {h['from']} | {h['to']} | {h['source']} | {h['note']} |")
    a("")

    # --- 7. Календарь и защита от одинакового контента ---------------
    a("## 7. Календарь и защита от одинаковых материалов на разных сайтах")
    a("")
    calendar = EditorialCalendar("fixture-anime")
    item = BacklogItem(
        "fixture-anime",
        "Что выходит в сентябре: подтверждённые даты",
        "Подборки",
        "informational",
        rationale="Спрос концентрируется вокруг окна релиза",
    )
    calendar.schedule(item, date(2026, 8, 26))
    a(
        f"- В календаре `{calendar.site_id}` запланировано на ближайшую неделю: "
        f"**{len(calendar.due(today))}** материал(ов)"
    )
    a("")

    duplicates = detect_cross_site_duplication(
        [
            BacklogItem("fixture-anime", "Топ новинок сезона", "Подборки", "informational"),
            BacklogItem("fixture-serials", "Топ новинок сезона", "Подборки", "informational"),
            BacklogItem(
                "fixture-serials",
                "Порядок просмотра: с чего начать",
                "Watch order",
                "informational",
            ),
        ]
    )
    a(f"- Обнаружено дублей плана между сайтами: **{len(duplicates)}**")
    for title, sites in duplicates:
        a(
            f"  - «{title}» запланирован на: {', '.join(sorted(set(sites)))} — "
            "требуется переработка под каждый сайт или отказ"
        )
    a("")
    a(
        "Одинаковый материал на нескольких сайтах не публикуется. Синонимичный "
        "рерайт ради формальной уникальности также запрещён — материал либо имеет "
        "самостоятельную ценность для конкретного сайта, либо не выходит."
    )
    a("")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("\n".join(lines), encoding="utf-8")
    print(f"записано: {OUT.relative_to(REPO)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
