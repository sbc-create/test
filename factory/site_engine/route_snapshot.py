"""Снимок маршрутов витрины: адрес страницы → устойчивый идентификатор записи.

Зачем он нужен. Очередь потребителя ключуется адресом страницы, каталог — устойчивым
идентификатором произведения. Это два пространства имён для двух разных вещей,
и прямого совпадения между ними нет: измерено — из 167 адресов очереди в
159 885 записях каталога не нашлось ни одного. Соединяет их снимок маршрутов,
и производит его ядро.

Как получается адрес. Витрина строит его сама объявленной функцией от названия.
Ядро вызывает **ту же функцию** — не похожую, не приблизительную, а ту же.
Поэтому снимок не угадывает адрес по названию: он воспроизводит вычисление,
которым адрес и был получен. Разница принципиальная. Угадывание по названию
запрещено и здесь не применяется: обратного хода — от адреса к названию —
не делается никогда.

Про совпадения адресов. Два произведения с разными названиями могут дать один
слаг. Выбрать «первое» нельзя: страница окажется приписана произвольной из
двух записей, и ошибка будет выглядеть как обычная страница. Такие адреса
уходят в перечень столкновений, а снимок объявляется неполным.
"""

from __future__ import annotations

import dataclasses
import datetime as dt
import enum
import hashlib
import json
from typing import Any

SNAPSHOT_SCHEMA = "core-route-snapshot/1.0.0"

#: Совместимый ряд для потребителя. Читается весь старший ряд 1.x.
COMPATIBILITY_RANGE = "core-route-snapshot/1.x"


class RouteState(str, enum.Enum):
    """Состояние одного маршрута."""

    ACTIVE = "ACTIVE"
    #: Маршрут исчез из источника. Запись остаётся с отметкой: исчезнувший
    #: молча маршрут выглядит как никогда не существовавший, и страница,
    #: которая вчера была, сегодня объясняется ошибкой потребителя.
    TOMBSTONE = "TOMBSTONE"
    #: Адрес принадлежит нескольким записям. Решать по нему нельзя.
    COLLISION = "COLLISION"


class Completeness(str, enum.Enum):
    COMPLETE = "COMPLETE"
    #: Часть записей не дала маршрута либо столкнулась. Такой снимок не
    #: заменяет прежний хороший.
    INCOMPLETE = "INCOMPLETE"


@dataclasses.dataclass(frozen=True)
class RouteRecord:
    """Один маршрут витрины."""

    site_id: str
    route_key: str
    canonical_url: str
    route_kind: str
    stable_work_id: str
    content_kind: str
    content_kind_state: str
    state: RouteState
    parent_work_id: str = ""
    #: Идентификаторы записей, столкнувшихся на этом адресе. Пусто у обычных
    #: маршрутов. Нужны в самой записи: разбирающий видит отказ там же, где и
    #: то, между чем предстоит выбирать.
    collided_work_ids: tuple[str, ...] = ()
    created_at: str = ""
    updated_at: str = ""
    provenance: str = ""
    reason: str = ""

    def as_dict(self) -> dict[str, Any]:
        return {"siteId": self.site_id, "routeKey": self.route_key,
                "canonicalUrl": self.canonical_url,
                "routeKind": self.route_kind,
                "stableWorkId": self.stable_work_id,
                "parentWorkId": self.parent_work_id,
                "collidedWorkIds": list(self.collided_work_ids),
                "contentKind": self.content_kind,
                "contentKindState": self.content_kind_state,
                "state": self.state.value, "createdAt": self.created_at,
                "updatedAt": self.updated_at, "provenance": self.provenance,
                "reason": self.reason}


#: Поля, не входящие в отпечаток. Время сборки говорит о нашем прогоне, а не
#: о маршрутах: включив его, мы объявляли бы изменением каждую пересборку.
DIGEST_EXCLUDED = ("createdAt", "updatedAt")


def digest_of(records: list[dict[str, Any]]) -> str:
    """Отпечаток набора маршрутов. Время сборки в него не входит."""
    очищено = [{к: v for к, v in з.items() if к not in DIGEST_EXCLUDED}
               for з in records]
    сырьё = json.dumps(очищено, ensure_ascii=False, sort_keys=True,
                       separators=(",", ":"))
    return hashlib.blake2b(сырьё.encode("utf-8"), digest_size=16).hexdigest()


def observation_id(site_id: str, source_digest: str, day: str) -> str:
    сырьё = f"{site_id}|{source_digest}|{day}"
    return hashlib.blake2b(сырьё.encode("utf-8"), digest_size=12).hexdigest()


@dataclasses.dataclass(frozen=True)
class Snapshot:
    """Снимок маршрутов одной витрины целиком."""

    site_id: str
    records: tuple[RouteRecord, ...]
    collisions: tuple[dict[str, Any], ...]
    rejected: tuple[dict[str, Any], ...]
    observed_at: dt.datetime
    producer_sha: str
    source_digest: str
    generation_reason: str
    previous_digest: str = ""
    schema_version: str = SNAPSHOT_SCHEMA

    @property
    def completeness(self) -> Completeness:
        return (Completeness.INCOMPLETE
                if self.collisions or self.rejected else Completeness.COMPLETE)

    @property
    def digest(self) -> str:
        return digest_of([з.as_dict() for з in self.records])

    @property
    def observation_id(self) -> str:
        return observation_id(self.site_id, self.source_digest,
                              self.observed_at.date().isoformat())

    def as_dict(self) -> dict[str, Any]:
        return {
            "schemaVersion": self.schema_version,
            "compatibilityRange": COMPATIBILITY_RANGE,
            "observationId": self.observation_id,
            "siteId": self.site_id,
            "observedAt": self.observed_at.isoformat(),
            "producerSha": self.producer_sha,
            "sourceDigest": self.source_digest,
            "generationReason": self.generation_reason,
            "previousDigest": self.previous_digest,
            "recordCount": len(self.records),
            "collisionCount": len(self.collisions),
            "rejectedCount": len(self.rejected),
            "completeness": self.completeness.value,
            "digest": self.digest,
            "orderedBy": "routeKey",
            "records": [з.as_dict() for з in self.records],
            "collisions": [dict(с) for с in self.collisions],
            "rejected": [dict(о) for о in self.rejected],
        }


def build(entries: list[dict[str, Any]], *, site_id: str, route_of,
          observed_at: dt.datetime, producer_sha: str, source_digest: str,
          generation_reason: str, previous: dict[str, Any] | None = None,
          content_kind_of=None) -> Snapshot:
    """Построить снимок из записей каталога.

    `route_of` — функция витрины, дающая адрес. Она передаётся, а не
    вызывается по имени: снимок обязан строиться той же функцией, какой
    витрина строит адреса, и подмена её здесь была бы подменой самого адреса.
    """
    по_ключу: dict[str, list[dict[str, Any]]] = {}
    отклонено: list[dict[str, Any]] = []

    for запись in entries:
        идентификатор = str(запись.get("external_id") or "")
        название = str(запись.get("name") or "")
        if not идентификатор:
            отклонено.append({"reason": "запись без устойчивого идентификатора",
                              "name": название[:60]})
            continue
        адрес = route_of(название, идентификатор)
        if not адрес or адрес.strip("/") in ("", "title", "вложенный раздел"):
            отклонено.append({"stableWorkId": идентификатор,
                              "reason": "адрес не выводится: пустое название и "
                                        "непригодный идентификатор"})
            continue
        по_ключу.setdefault(адрес.rstrip("/"), []).append(запись)

    записи: list[RouteRecord] = []
    столкновения: list[dict[str, Any]] = []
    прежние = {з["routeKey"]: з for з in (previous or {}).get("records", [])}

    for ключ in sorted(по_ключу):
        группа = по_ключу[ключ]
        if len(группа) > 1:
            # Выбор «первой записи» запрещён: страница окажется приписана
            # произвольной, и ошибка будет выглядеть обычной страницей.
            столкновения.append({
                "routeKey": ключ,
                "stableWorkIds": sorted(str(з.get("external_id")) for з in группа),
                "count": len(группа),
                "reason": "адрес принадлежит нескольким записям; выбор первой "
                          "приписал бы страницу произвольной из них"})
            записи.append(RouteRecord(
                site_id=site_id, route_key=ключ, canonical_url="",
                route_kind="title", stable_work_id="", content_kind="UNKNOWN",
                content_kind_state="MISSING", state=RouteState.COLLISION,
                collided_work_ids=tuple(sorted(
                    str(з.get("external_id")) for з in группа)),
                provenance="catalog+slugify",
                reason=f"столкновение {len(группа)} записей"))
            continue

        запись = группа[0]
        идентификатор = str(запись.get("external_id"))
        вид, состояние_вида = ("UNKNOWN", "MISSING")
        if content_kind_of is not None:
            вид, состояние_вида = content_kind_of(запись)
        прежняя = прежние.get(ключ)
        записи.append(RouteRecord(
            site_id=site_id, route_key=ключ,
            canonical_url=f"https://{site_id}{ключ}/",
            route_kind="title", stable_work_id=идентификатор,
            content_kind=вид, content_kind_state=состояние_вида,
            state=RouteState.ACTIVE,
            created_at=(прежняя or {}).get("createdAt")
            or observed_at.isoformat(),
            updated_at=observed_at.isoformat(),
            provenance="catalog+slugify"))

    # Надгробия: маршруты, бывшие в прежнем снимке и исчезнувшие теперь.
    живые = {з.route_key for з in записи}
    for ключ, прежняя in sorted(прежние.items()):
        if ключ in живые or прежняя.get("state") == RouteState.TOMBSTONE.value:
            continue
        записи.append(RouteRecord(
            site_id=site_id, route_key=ключ,
            canonical_url=прежняя.get("canonicalUrl", ""),
            route_kind=прежняя.get("routeKind", "title"),
            stable_work_id=прежняя.get("stableWorkId", ""),
            content_kind=прежняя.get("contentKind", "UNKNOWN"),
            content_kind_state=прежняя.get("contentKindState", "MISSING"),
            state=RouteState.TOMBSTONE,
            created_at=прежняя.get("createdAt", ""),
            updated_at=observed_at.isoformat(),
            provenance=прежняя.get("provenance", ""),
            reason="маршрут исчез из источника"))

    записи.sort(key=lambda з: з.route_key)
    return Snapshot(site_id=site_id, records=tuple(записи),
                    collisions=tuple(столкновения), rejected=tuple(отклонено),
                    observed_at=observed_at, producer_sha=producer_sha,
                    source_digest=source_digest,
                    generation_reason=generation_reason,
                    previous_digest=(previous or {}).get("digest", ""))


def lookup(snapshot: dict[str, Any], route_key: str) -> dict[str, Any]:
    """Найти устойчивый идентификатор по ключу маршрута.

    Отказ всегда несёт причину: «не нашлось» без причины неотличимо от «мы не
    искали», и разбирающий не узнает, чего не хватает.
    """
    ключ = (route_key or "").rstrip("/")
    for з in snapshot.get("records", []):
        if з.get("routeKey") != ключ:
            continue
        состояние = з.get("state")
        if состояние == RouteState.COLLISION.value:
            return {"found": False, "reason": "COLLISION",
                    "detail": з.get("reason", ""),
                    "candidates": з.get("collidedWorkIds", [])}
        if состояние == RouteState.TOMBSTONE.value:
            return {"found": False, "reason": "ROUTE_REMOVED",
                    "detail": "маршрут исчез из источника",
                    "stableWorkId": з.get("stableWorkId", "")}
        return {"found": True, "stableWorkId": з.get("stableWorkId"),
                "contentKind": з.get("contentKind"),
                "contentKindState": з.get("contentKindState"),
                "routeKind": з.get("routeKind")}
    return {"found": False, "reason": "NOT_IN_SNAPSHOT",
            "detail": f"ключа {ключ!r} в снимке нет"}
