#!/usr/bin/env python3
"""Связь authoritative записи каталога с публичной страницей — без догадок.

Задача, ради которой файл существует, звучит так: SEO держит очередь страниц,
ядро держит каталог с видом произведения и состоянием воспроизведения, и до
сих пор соединить одно с другим было нечем. SEO измерил это прямо
(`SEO_TO_CORE-026`): 159 записей очереди из 268 остались без решения именно
потому, что состояние воспроизведения не к чему было привязать.

**Почему связь детерминирована, а не угадана.** Адрес страницы строит сам
движок витрины, и строит его одной функцией:

    slug = slugify(name) or slugify(external_id) or external_id.lower()
    path = f"/title/{slug}/"

Здесь используется **та же самая функция того же движка**, а не похожее на неё
преобразование. Это не сопоставление по названию и не нечёткий поиск: это
воспроизведение вычисления производителя. Разница принципиальна — при
изменении правила адресации сломается и витрина, и связь, и сломаются они
одинаково, а не разойдутся тихо.

**Коллизии закрываются наглухо.** Два разных произведения с одинаковым адресом
— это не повод выбрать одно: адрес перестал быть однозначным, и обе записи
уходят в разбор с кодом причины. Молчаливый выбор «первого» здесь означал бы
приписать странице чужое состояние воспроизведения.
"""

from __future__ import annotations

import argparse
import collections
import dataclasses
import datetime as dt
import hashlib
import json
import sys
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from factory.lords.live_catalog import slugify  # noqa: E402

#: Идентификаторы, разрешённые как основание воспроизведения. Список закрыт
#: решением владельца контракта (`CORE_TO_OWNER-014`); `imdb` и `cvh` в него
#: не входят и наличие видео не подтверждают.
AUTHORISED = ("kp", "mali", "mdl")


def route_of(name: str, external_id: str) -> str:
    """Путь страницы. Ровно то, что вычисляет витрина, и ничего сверх."""
    slug = slugify(name) or slugify(external_id) or external_id.lower()
    return f"/title/{slug}/"


@dataclasses.dataclass(frozen=True)
class Binding:
    """Одна связь: запись каталога ↔ маршрут страницы."""

    content_id: str
    name: str
    route_id: str
    canonical_path: str
    content_kind_wire: str
    is_series: bool | None
    tags: tuple[str, ...]
    playback_state: str
    playback_reason: str
    aggregator: str
    external_ids: dict[str, str]

    def as_dict(self) -> dict[str, Any]:
        return dataclasses.asdict(self)


def playback_of(entry: dict) -> tuple[str, str, str]:
    """Состояние, код причины и агрегатор. Без догадок о том, чего нет."""
    playback = entry.get("playback")
    if isinstance(playback, dict) and playback.get("aggregator"):
        агрегатор = str(playback["aggregator"])
        if агрегатор in AUTHORISED:
            return "PLAYABLE", "OK", агрегатор
        # Идентификатор есть, но контрактом не разрешён.
        return "BLOCKED_BY_CONTRACT", "IDENTIFIER_FORBIDDEN_BY_CONTRACT", агрегатор
    ids = entry.get("external_ids") or {}
    if not isinstance(ids, dict) or not ids:
        return "NO_IDENTIFIER", "MISSING_PROVIDER_ID", ""
    if set(ids) & set(AUTHORISED):
        # Разрешённый идентификатор есть, а потока нет: это другое состояние.
        return "NO_STREAM", "PROVIDER_NOT_PLAYABLE", ""
    return "BLOCKED_BY_CONTRACT", "IDENTIFIER_FORBIDDEN_BY_CONTRACT", ""


def build(entries: list[dict]) -> tuple[dict[str, list[Binding]], dict[str, int]]:
    """Связи по маршруту. Второе значение — счётчики для отчёта.

    Разведение одинаковых адресов воспроизводится ровно так, как это делает
    витрина (`live_catalog.load`): второму и последующим совпадениям слага
    приписывается номер — `-2`, `-3` и далее, **в порядке каталога**.

    Здесь и обнаруживается свойство, ради которого контракту нужен отдельный
    устойчивый идентификатор: адрес зависит от порядка записей в ответе
    источника. Стоит источнику переставить две записи с одинаковым названием —
    и они молча меняются адресами. Слаг поэтому идентичностью быть не может;
    идентичность — `external_id`, а адрес из неё выводится.
    """
    по_маршруту: dict[str, list[Binding]] = collections.defaultdict(list)
    счёт = collections.Counter()
    видели: dict[str, int] = {}
    for entry in entries:
        external_id = str(entry.get("external_id") or "").strip()
        name = str(entry.get("name") or "").strip()
        if not external_id or not name:
            счёт["неадресуемых"] += 1
            continue
        база = route_of(name, external_id)
        сколько = видели.get(база, 0)
        видели[база] = сколько + 1
        if сколько:
            счёт["адрес разведён номером"] += 1
            путь = f"{база.rstrip('/')}-{сколько + 1}/"
        else:
            путь = база
        состояние, причина, агрегатор = playback_of(entry)
        ids = entry.get("external_ids") or {}
        по_маршруту[путь].append(Binding(
            content_id=external_id, name=name, route_id=путь,
            canonical_path=путь,
            content_kind_wire=str(entry.get("type") or ""),
            is_series=entry.get("is_series"),
            tags=tuple(str(t) for t in (entry.get("tags") or [])),
            playback_state=состояние, playback_reason=причина,
            aggregator=агрегатор,
            external_ids={str(k): str(v) for k, v in ids.items()}
            if isinstance(ids, dict) else {}))
        счёт[состояние] += 1
    return по_маршруту, dict(счёт)


def measure(queue: list[dict], по_маршруту: dict[str, list[Binding]],
            *, домены: set[str]) -> dict[str, Any]:
    """Сколько записей очереди связывается, а сколько нет и почему."""
    итог = collections.Counter()
    несвязанные: list[dict[str, str]] = []
    связанные: list[dict[str, Any]] = []
    коллизии: list[dict[str, Any]] = []

    for row in queue:
        домен = str(row.get("domain") or "")
        адрес = str(row.get("content_id") or "")
        if домен not in домены or not адрес.startswith("http"):
            итог["вне области"] += 1
            continue
        путь = urlparse(адрес).path
        if not путь.endswith("/"):
            путь += "/"
        кандидаты = по_маршруту.get(путь, [])
        if not кандидаты:
            итог["не найдено"] += 1
            несвязанные.append({"url": адрес, "reason": "ROUTE_NOT_IN_CATALOG"})
            continue
        if len(кандидаты) > 1:
            итог["коллизия"] += 1
            коллизии.append({"url": адрес, "route": путь,
                             "candidates": [c.content_id for c in кандидаты]})
            continue
        b = кандидаты[0]
        итог["связано"] += 1
        итог[f"playback:{b.playback_state}"] += 1
        связанные.append({"url": адрес, "contentId": b.content_id,
                          "name": b.name, "kindWire": b.content_kind_wire,
                          "isSeries": b.is_series, "tags": list(b.tags),
                          "playbackState": b.playback_state,
                          "playbackReason": b.playback_reason})
    return {"counts": dict(итог), "matched": связанные,
            "unmatched": несвязанные, "collisions": коллизии}


def digest(по_маршруту: dict[str, list[Binding]]) -> str:
    """Отпечаток набора связей. От порядка записей не зависит."""
    строки = sorted(
        f"{b.route_id}|{b.content_id}|{b.playback_state}|{b.playback_reason}"
        for группа in по_маршруту.values() for b in группа)
    return hashlib.sha256("\n".join(строки).encode("utf-8")).hexdigest()


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--catalog", required=True)
    p.add_argument("--queue", required=True)
    p.add_argument("--domains", default="lordfilm47.space,lordserial33.biz,"
                                        "1lordserials1.online")
    p.add_argument("--json")
    a = p.parse_args()

    кэш = json.loads(Path(a.catalog).read_text("utf-8"))
    записи = кэш["items"] if isinstance(кэш, dict) else кэш
    снят = (dt.datetime.fromtimestamp(кэш["fetched_at_ms"] / 1000, dt.timezone.utc)
            .isoformat() if isinstance(кэш, dict) and кэш.get("fetched_at_ms")
            else "неизвестно")
    очередь = json.loads(Path(a.queue).read_text("utf-8"))

    по_маршруту, счёт = build(записи)
    коллизий = sum(1 for г in по_маршруту.values() if len(г) > 1)
    domains = set(a.domains.split(","))
    замер = measure(очередь, по_маршруту, домены=domains)

    итог = {
        "catalogSnapshotAt": снят,
        "catalogRecords": len(записи),
        "routes": len(по_маршруту),
        "routeCollisions": коллизий,
        "playbackCounts": счёт,
        "queueRecords": len(очередь),
        "queueDomains": sorted(domains),
        "bindingDigest": digest(по_маршруту),
        **{k: v for k, v in замер.items() if k == "counts"},
        "matchedCount": len(замер["matched"]),
        "unmatchedCount": len(замер["unmatched"]),
        "collisionCount": len(замер["collisions"]),
    }
    print(json.dumps(итог, ensure_ascii=False, indent=1))
    if a.json:
        Path(a.json).write_text(
            json.dumps({**итог, "matched": замер["matched"],
                        "unmatched": замер["unmatched"],
                        "collisions": замер["collisions"]},
                       ensure_ascii=False, indent=1), "utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
