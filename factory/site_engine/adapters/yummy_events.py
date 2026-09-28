"""Перевод событий наблюдателя Yummy в контракт Site Engine.

Наблюдатель пишет события в своём формате: `kind` вместо `event_type`,
`titleId` вместо пары «поставщик и его идентификатор», без ключа
идемпотентности и без версии схемы. Формат сложился раньше контракта и
работает; переписывать его на живой витрине в рамках этой задачи запрещено, да
и незачем — разницу закрывает переводчик.

Что при этом проверяется, а не предполагается: наблюдатель уже различает время
наблюдения и время поставщика (`observedAt` и `providerTimestamp`). Это главное
свойство контракта, и оно у него есть.
"""
from __future__ import annotations

import json
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from factory.site_engine.contracts import (
    ContentEvent,
    ContractError,
    EventType,
    idempotency_key,
)
from factory.site_engine.providers import ProviderUnavailable, canonical_id

PROVIDER = "cdnvideohub"

#: Роды событий наблюдателя, названные иначе, чем в контракте.
#:
#: `METADATA_UPDATED` и `TITLE_UPDATED` — одно и то же утверждение: у тайтла
#: изменились данные. Заводить в контракте второе имя для того же понятия
#: значило бы ухудшить контракт ради совпадения строк; сведение имён — как раз
#: работа переводчика.
ALIASES: dict[str, EventType] = {
    "METADATA_UPDATED": EventType.TITLE_UPDATED,
}

#: Полный словарь наблюдателя на 2026-08-30, снятый с его собственного кода
#: (`EVENT_KINDS` в `watcher-events.ts`), а не с попавшихся в ленте записей:
#: род события, ещё ни разу не выпущенный, всё равно обязан переводиться.
WATCHER_KINDS = (
    "TITLE_CREATED",
    "SEASON_ADDED",
    "EPISODE_ADDED",
    "VOICEOVER_ADDED",
    "PLAYBACK_AVAILABLE",
    "METADATA_UPDATED",
    "SOURCE_ANOMALY",
)


class UnknownEventKind(ContractError):
    """Наблюдатель выпустил событие, которого нет в контракте.

    Отдельный тип, а не пропуск: незнакомый род события означает, что
    наблюдатель ушёл вперёд контракта, и знать об этом надо сразу.
    """


def _moment(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def _marker(raw: dict[str, Any]) -> str:
    """Что именно отличает это событие от соседних.

    Для выхода серии — сезон и номер серии: повторное наблюдение той же серии
    обязано дать тот же ключ. Для прочих родов — переход «из чего во что».
    """
    if raw.get("season") is not None and raw.get("episode") is not None:
        return f"s{raw['season']}e{raw['episode']}"
    return f"{raw.get('from')}->{raw.get('to')}"


def event_from_watcher(raw: dict[str, Any]) -> ContentEvent:
    kind = raw.get("kind")
    event_type = ALIASES.get(kind)
    if event_type is None:
        try:
            event_type = EventType(kind)
        except ValueError:
            raise UnknownEventKind(
                f"наблюдатель выпустил род события «{kind}», которого нет в контракте"
            ) from None

    provider_id = str(raw.get("titleId") or "")
    if not provider_id:
        raise ContractError("в событии наблюдателя нет идентификатора тайтла")

    observed = _moment(raw.get("observedAt"))
    if observed is None:
        # Время наблюдения — единственная метка, за которую отвечаем мы.
        # Событие без неё бессмысленно, и подставлять «сейчас» нельзя: это
        # была бы уже другая метка.
        raise ContractError(f"в событии {kind} по тайтлу {provider_id} нет времени наблюдения")

    canonical = canonical_id(PROVIDER, provider_id)
    payload = {
        key: raw[key]
        for key in ("name", "from", "to", "season", "episode", "playable", "endpoint")
        if key in raw
    }
    return ContentEvent(
        event_id=idempotency_key(event_type, canonical, _marker(raw))[:16],
        event_type=event_type,
        provider=PROVIDER,
        provider_id=provider_id,
        canonical_title_id=canonical,
        observed_at=observed,
        provider_timestamp=_moment(raw.get("providerTimestamp")),
        idempotency_key=idempotency_key(event_type, canonical, _marker(raw)),
        source_fingerprint={"value": raw["fingerprint"]} if raw.get("fingerprint") else None,
        payload=payload,
    )


@dataclass
class YummyEventLog:
    """Лента событий наблюдателя, приведённая к контракту."""

    path: Path

    def read(self, *, strict: bool = True) -> Iterator[ContentEvent]:
        if not self.path.exists():
            raise ProviderUnavailable(f"ленты событий нет: {self.path}")
        for number, line in enumerate(self.path.read_text(encoding="utf-8").splitlines(), 1):
            line = line.strip()
            if not line:
                continue
            try:
                raw = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ContractError(f"строка {number} ленты не разбирается: {exc}") from exc
            try:
                yield event_from_watcher(raw)
            except UnknownEventKind:
                # Нестрогий разбор нужен разбору задним числом: старая лента
                # может содержать роды событий, которых уже нет. Умолчание всё
                # же строгое — молчаливый пропуск прячет расхождение.
                if strict:
                    raise
