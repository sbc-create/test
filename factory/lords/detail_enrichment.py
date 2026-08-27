"""Дополнение записей каталога из detail API CDNVideoHub.

Списочный ответ даёт имя, тип, год, постер, теги и две оценки. Всего остального,
из чего состоит страница фильма, там нет: описания, страны, настоящих жанров,
хронометража, съёмочной группы, сезонов и дат премьеры. Всё это отдаёт detail —
по одной записи на запрос.

Отсюда два ограничения, определяющие устройство модуля.

Первое: четыре тысячи восемьсот запросов на каждую пересборку — это отказ
источника, а не обогащение. Поэтому за один прогон дополняется ограниченное
число записей, а результат кэшируется на диске и переживает пересборку.
Покрытие растёт от прогона к прогону и не начинается заново.

Второе: обогащение не имеет права ничего отнимать. Пустое поле detail не
затирает заполненное поле списка, а отказ источника оставляет запись такой,
какой она была. Отдельно защищён `playback`: однажды уже случилось, что
обновление каталога сняло плеер со всех страниц, и повторять это через
обогащение нельзя.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path

from factory.lords import content_live

#: Сколько записей дополняется за один прогон. Ограничение защищает источник:
#: полный каталог за раз — это тысячи запросов подряд.
DEFAULT_BUDGET = 400

#: Сколько живёт удачный ответ. Описание и состав сезонов меняются редко,
#: и перезапрашивать их каждые десять минут незачем.
DEFAULT_TTL_SECONDS = 7 * 24 * 3600

#: Отдельный, короткий срок для отказов. Без него запись, которой у источника
#: временно нет, перезапрашивалась бы в каждом прогоне и съедала весь бюджет.
NEGATIVE_TTL_SECONDS = 6 * 3600

#: Поля, которые обогащение приносит. `playback` в списке отсутствует намеренно.
DETAIL_FIELDS = (
    "description", "original_name", "countries", "country_codes",
    "genres", "genre_codes", "crew", "duration", "premiere_date",
    "seasons", "seasons_count", "year_end", "available_voices",
    "voice_studios", "kinopoisk_rating", "imdb_rating",
)


def cache_dir(root: Path) -> Path:
    return Path(root) / "lords" / "detail-cache"


@dataclass
class EnrichmentReport:
    requested: int = 0
    fetched: int = 0
    from_cache: int = 0
    failed: int = 0
    skipped_negative: int = 0
    enriched: int = 0
    fields_filled: dict = field(default_factory=dict)

    def as_dict(self) -> dict:
        return {
            "requested": self.requested, "fetched": self.fetched,
            "from_cache": self.from_cache, "failed": self.failed,
            "skipped_negative": self.skipped_negative, "enriched": self.enriched,
            "fields_filled": dict(sorted(self.fields_filled.items())),
        }


def _is_empty(value) -> bool:
    """Пустое значение источника: его нельзя записывать поверх заполненного."""
    return value is None or value == "" or value == [] or value == {}


def merge_detail(item: dict, detail: dict) -> dict:
    """Запись списка, дополненная detail. Ничего не теряя.

    Правило одно и оно жёсткое: detail добавляет, но не отнимает. Пустое поле
    ответа не затирает заполненное поле записи, а `playback` не трогается
    вовсе — он собран из списка и из внешних идентификаторов, и обогащение к
    нему отношения не имеет.
    """
    merged = dict(item)
    for name in DETAIL_FIELDS:
        if name not in detail:
            continue
        value = detail[name]
        if _is_empty(value) and not _is_empty(merged.get(name)):
            # Источник промолчал — прежнее значение остаётся.
            continue
        if _is_empty(value):
            continue
        merged[name] = value
    # Явная защита: чем бы ни ответил detail, воспроизведение остаётся прежним.
    merged["playback"] = item.get("playback")
    merged["detail_fetched_at"] = detail.get("_fetched_at") or merged.get("detail_fetched_at")
    return merged


class DetailCache:
    """Кэш ответов detail на диске: удачные и отказы хранятся по-разному."""

    def __init__(self, directory: Path, *, ttl: int = DEFAULT_TTL_SECONDS,
                 negative_ttl: int = NEGATIVE_TTL_SECONDS, now=None):
        self.directory = Path(directory)
        self.ttl = ttl
        self.negative_ttl = negative_ttl
        self._now = now or time.time

    def _path(self, external_id: str) -> Path:
        safe = "".join(c for c in external_id if c.isalnum() or c in "-_")
        return self.directory / f"{safe}.json"

    def get(self, external_id: str) -> tuple[str, dict | None]:
        """`("hit", detail)`, `("negative", None)` или `("miss", None)`."""
        path = self._path(external_id)
        if not path.is_file():
            return "miss", None
        try:
            entry = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return "miss", None
        age = self._now() - float(entry.get("fetched_at") or 0)
        if entry.get("status") == "error":
            return ("negative", None) if age < self.negative_ttl else ("miss", None)
        if age >= self.ttl:
            return "miss", None
        return "hit", entry.get("detail")

    def put(self, external_id: str, detail: dict | None, *, error: str | None = None) -> None:
        self.directory.mkdir(parents=True, exist_ok=True)
        payload = {
            "fetched_at": self._now(),
            "status": "error" if error else "ok",
            "detail": detail,
        }
        if error:
            payload["error"] = str(error)[:200]
        content_live.write_atomic(self._path(external_id), payload)


def enrich_items(
    items: list[dict],
    *,
    fetcher,
    contract,
    cache: DetailCache,
    budget: int = DEFAULT_BUDGET,
    order=None,
) -> tuple[list[dict], EnrichmentReport]:
    """Дополняет записи, тратя не больше `budget` сетевых запросов.

    `order` задаёт, кого дополнять первым. По умолчанию — те, у кого нет
    описания: страница без описания выглядит незаконченной сильнее всего.
    """
    report = EnrichmentReport()
    by_id = {i.get("external_id"): i for i in items if i.get("external_id")}
    queue = list(order) if order is not None else [
        i.get("external_id") for i in items
        if i.get("external_id") and _is_empty(i.get("description"))
    ]

    spent = 0
    out: dict[str, dict] = {}
    for external_id in queue:
        item = by_id.get(external_id)
        if item is None:
            continue
        report.requested += 1
        state, detail = cache.get(external_id)
        if state == "negative":
            report.skipped_negative += 1
            continue
        if state == "miss":
            if spent >= budget:
                continue
            spent += 1
            try:
                url = contract.url("title_detail", id=external_id)
                detail = fetcher.get_json(url)
                detail["_fetched_at"] = time.time()
                cache.put(external_id, detail)
                report.fetched += 1
            except Exception as error:  # noqa: BLE001 — причина уходит в кэш отказов
                cache.put(external_id, None, error=repr(error))
                report.failed += 1
                continue
        else:
            report.from_cache += 1
        if not detail:
            continue
        before = {k for k in DETAIL_FIELDS if not _is_empty(item.get(k))}
        merged = merge_detail(item, detail)
        after = {k for k in DETAIL_FIELDS if not _is_empty(merged.get(k))}
        for name in after - before:
            report.fields_filled[name] = report.fields_filled.get(name, 0) + 1
        out[external_id] = merged
        report.enriched += 1

    result = [out.get(i.get("external_id"), i) for i in items]
    return result, report
