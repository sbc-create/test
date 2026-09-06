"""Оценки из действующего договорного фида поставщика.

Владелец разрешил ровно одно: использовать и показывать оценки, которые **уже
приходят** в договорном фиде. Скрапинг сторонних сайтов и подключение новых
внешних источников без отдельного разрешения запрещены
(`docs/rights/provider-feed-ratings.md`).

Отсюда устройство модуля, и оно не случайно.

**Наружу он не ходит и не может.** Значения лежат в фиде, который забирает
штатное обновление каталога; здесь только чтение уже загруженного файла.
Сетевой клиент не импортируется вовсе, и это проверяется тестом по исходному
коду: соединитель, способный сделать запрос, однажды его сделает — при отладке,
в спешке, «временно».

**Происхождение хранится рядом со значением.** Не «7.6», а «7.6, метрика imdb,
из фида поставщика, фид забран тогда-то, основание — действующий договор».
Число без происхождения через месяц неотличимо от скачанного со стороны.

**Две метрики не сводятся в одну.** `imdb_rating` и `kinopoisk_rating` меряют
разные совокупности зрителей. Выбор между ними — решение о представлении,
которого владелец не принимал; пока не принято, отдаются обе, а главного
значения нет. Среднее не считается никогда: это третье число, которого не
сообщал никто.

**Невышедшее — не пробел.** Произведение будущего года не имеет оценки не
потому, что мы её не нашли, а потому, что её ещё нет. Оно исключается из
знаменателя охвата: иначе охват падает от появления анонсов.
"""

from __future__ import annotations

import datetime as dt
import json
import time
from pathlib import Path
from typing import Any

ВЕРСИЯ = "rating-feed/1.0.0"
ИСТОЧНИК = "provider-feed"

#: Поле фида → имя метрики. Имя метрики совпадает с именем сайта, откуда она
#: родом, и это единственное, что их связывает: значение приходит из фида, а не
#: с сайта. Разрешение на фид не является разрешением на сайт.
ПОЛЯ = {"imdb_rating": "imdb", "kinopoisk_rating": "kinopoisk"}

#: Шкала обеих метрик. Записывается рядом со значением: «7.6» без шкалы
#: одинаково похоже на оценку из десяти и из ста.
ШКАЛА = "0-10"

#: Виды, для которых зрительские оценки не ведутся вовсе.
БЕЗ_ОЦЕНОК = frozenset({"EPISODE", "SEASON", "MUSIC"})

ПАМЯТЬ = "var/state/rating-feed"

#: Правовое основание, сопровождающее каждое значение. Одна строка на весь слой:
#: два места, где она записана, однажды разойдутся.
ОСНОВАНИЕ = "действующий договор с поставщиком контента"


def _отметка(секунды: float) -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(секунды))


def _число(значение: Any) -> float | None:
    """Оценка как число. Строка «7,6» и пустая строка — не оценка.

    Приведение строки к числу здесь намеренно отсутствует: поставщик присылает
    числа, и если однажды пришлёт строку, это надо заметить, а не молча
    разобрать по догадке о десятичном разделителе.
    """
    if isinstance(значение, bool) or значение is None:
        return None
    if isinstance(значение, int | float):
        return float(значение)
    return None


def _вышло(запись: dict[str, Any], сегодня: dt.date) -> bool | None:
    """Вышло ли произведение. None — год неизвестен, и судить не о чем."""
    год = запись.get("year")
    if not isinstance(год, int) or год < 1870:
        return None
    return год <= сегодня.year


def _значения(запись: dict[str, Any], *, забран: str, основание: str) -> list[dict[str, Any]]:
    сейчас = _отметка(time.time())
    найдено = []
    for поле, метрика in ПОЛЯ.items():
        значение = _число(запись.get(поле))
        if значение is None:
            continue
        найдено.append(
            {
                "metric": метрика,
                "value": значение,
                "scale": ШКАЛА,
                "source": ИСТОЧНИК,
                "field": поле,
                "legalBasis": основание,
                "feedFetchedAt": забран,
                "capturedAt": сейчас,
            }
        )
    return найдено


def значения_записи(запись: dict[str, Any], *, забран: str = "") -> list[dict[str, Any]]:
    """Оценки одной записи фида. Отдельно от обхода витрины: карточка каталога
    показывает одну запись и не должна ради этого читать весь фид."""
    return _значения(запись, забран=забран, основание=ОСНОВАНИЕ)


def _память(root: Path, site_id: str) -> Path:
    return Path(root) / ПАМЯТЬ / f"{site_id}.json"


def _запомнить(root: Path, site_id: str, тело: dict[str, Any]) -> None:
    путь = _память(root, site_id)
    путь.parent.mkdir(parents=True, exist_ok=True)
    временный = путь.with_suffix(".json.tmp")
    временный.write_text(
        json.dumps({**тело, "rememberedAtRaw": time.time()}, ensure_ascii=False),
        encoding="utf-8",
    )
    временный.replace(путь)


def _вспомнить(root: Path, site_id: str, ttl: int) -> dict[str, Any] | None:
    путь = _память(root, site_id)
    if not путь.is_file():
        return None
    try:
        данные = json.loads(путь.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    возраст = time.time() - float(данные.pop("rememberedAtRaw", 0) or 0)
    данные["state"] = "LAST_KNOWN_GOOD"
    данные["ageSeconds"] = возраст
    # Значение не выбрасывается по истечении срока: оно перестаёт быть свежим.
    # Молча стареющее значение — ложь с задержкой, а выброшенное лишает
    # оператора единственного, что было.
    данные["stale"] = возраст > ttl
    return данные


def ratings(
    root: Path | str,
    site_id: str,
    *,
    env: dict[str, str] | None = None,
    offset: int = 0,
    limit: int = 500,
    remember: bool = False,
    today: dt.date | None = None,
) -> dict[str, Any]:
    """Оценки по записям одной витрины из уже загруженного фида."""
    from factory.site_engine import rating_sources
    from factory.site_engine.api import overview as _overview

    корень = Path(root)
    решение = rating_sources.resolve(корень)
    описание = next((и for и in решение.known if и["id"] == ИСТОЧНИК), None)
    разрешение = (описание or {}).get("authorization", {}).get("status", "absent")
    основа: dict[str, Any] = {
        "contractVersion": ВЕРСИЯ,
        "siteId": site_id,
        "source": ИСТОЧНИК,
        "items": [],
        "total": 0,
        "eligible": 0,
        "withRating": 0,
        "coverage": None,
    }

    if разрешение != "granted":
        return {
            **основа,
            "state": "SOURCE_NOT_AUTHORIZED",
            "reason": (описание or {}).get("authorization", {}).get(
                "reason", "источник не разрешён"
            ),
        }
    if ИСТОЧНИК not in решение.authorized:
        # Право есть, но источник выключен. Это другая причина, чем «прав нет»,
        # и путать их нельзя: в первом случае достаточно вернуть флаг.
        return {
            **основа,
            "state": "SOURCE_DISABLED",
            "reason": "источник разрешён, но выключен полем enabled в реестре",
        }

    ttl = int((описание or {}).get("ttlSeconds") or 3600)
    основание = ОСНОВАНИЕ
    # Расположение фида берётся оттуда же, откуда его читает весь остальной
    # движок. Собственный путь здесь означал бы, что оценки читаются из одного
    # файла, а каталог — из другого, и однажды они разойдутся.
    данные, _ = _overview._каталог_витрины(корень, env, site_id)
    if данные is None:
        запомненное = _вспомнить(корень, site_id, ttl)
        if запомненное is not None:
            return запомненное
        return {
            **основа,
            "state": "FEED_UNREADABLE",
            "reason": f"фид витрины {site_id} не читается, и запомненного значения нет",
        }

    забран = ""
    отметка = данные.get("fetched_at_ms")
    if isinstance(отметка, int | float) and отметка > 0:
        забран = _отметка(float(отметка) / 1000.0)
    сегодня = today or dt.date.today()

    строки: list[dict[str, Any]] = []
    подходящих = 0
    с_оценкой = 0
    for запись in данные.get("items") or []:
        значения = _значения(запись, забран=забран, основание=основание)
        вышло = _вышло(запись, сегодня)
        вид = str(запись.get("type") or "").upper()
        if вид in БЕЗ_ОЦЕНОК:
            состояние = "NOT_APPLICABLE"
        elif вышло is False:
            состояние = "NOT_RELEASED"
        elif значения:
            состояние = "AVAILABLE"
        else:
            состояние = "NO_RATING_IN_FEED"

        главное = None
        причина_главного = ""
        if len(значения) == 1:
            главное = значения[0]
        elif len(значения) > 1:
            причина_главного = "MULTIPLE_METRICS_NOT_RECONCILED"

        if состояние not in {"NOT_RELEASED", "NOT_APPLICABLE"}:
            подходящих += 1
            if значения:
                с_оценкой += 1

        строки.append(
            {
                "externalId": str(запись.get("external_id") or ""),
                "internalEntityId": f"{site_id}:{запись.get('external_id') or ''}",
                "title": str(запись.get("name") or ""),
                "state": состояние,
                "values": значения,
                "primary": главное,
                "primaryReason": причина_главного,
            }
        )

    тело = {
        **основа,
        "state": "AVAILABLE",
        "reason": "",
        "feedFetchedAt": забран,
        "legalBasis": основание,
        "total": len(строки),
        "eligible": подходящих,
        "withRating": с_оценкой,
        "coverage": (с_оценкой / подходящих) if подходящих else None,
        "offset": offset,
        "limit": limit,
        "items": строки[offset : offset + limit],
    }
    if remember:
        _запомнить(корень, site_id, тело)
    return тело
