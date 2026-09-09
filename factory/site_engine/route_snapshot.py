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
import pathlib
import re
from typing import Any

SNAPSHOT_SCHEMA = "core-route-snapshot/1.1.0"

#: Совместимый ряд для потребителя. Читается весь старший ряд 1.x.
COMPATIBILITY_RANGE = "core-route-snapshot/1.x"

#: Полный SHA производителя и ничего короче. Сокращённый SHA неоднозначен и
#: не отличает производителя от его собственной базы — ровно эта ошибка и была
#: допущена в первом снимке: восемь знаков, и то была база. Проверка стоит
#: здесь, у производителя: у него значение есть, а у потребителя только
#: догадка о нём.
FULL_SHA = re.compile(r"\A[0-9a-f]{40}\Z")

#: Правило вычисления отпечатка источника. Объявлено, потому что потребитель
#: не может проверить поле, о правиле которого не сказано.
SOURCE_DIGEST_ALGORITHM = "blake2b-128/json-sorted-compact"

#: Версия приведения адреса. Производитель и потребитель обязаны приводить
#: адрес одинаково, а «одинаково» без версии не проверяется.
NORMALIZATION_VERSION = "core-route-normalization/1.0.0"

#: Ось вида произведения. Каталог различает два класса и сходится с
#: `is_series` на всех записях без исключения. Третьего значения у него нет,
#: и объявить его тоньше значило бы объявить то, чего каталог не знает.
KIND_TAXONOMY = "core-catalog/type:2"

#: Где объявлен словарь тегов поставщика. В коде его нет намеренно: какие
#: метки означают анимацию или форму — свойство каталога, а не движка, и
#: условие «если аниме» внутри общего кода означало бы, что следующий тип
#: витрины потребует правки ядра.
TAG_VOCABULARY_PATH = "config/catalog-tag-vocabulary.json"


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
    #: Форма произведения, если каталог её пометил: ONA, OVA, SPECIAL.
    #: Пусто — не помечено, а не «обычное».
    content_form: str = ""
    #: Анимация: `True` или `None`. `False` не бывает — тег есть или его нет,
    #: а отличить «не анимация» от «не помечено» нечем.
    is_animation: bool | None = None
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
                "contentForm": self.content_form,
                "isAnimation": self.is_animation,
                "state": self.state.value, "createdAt": self.created_at,
                "updatedAt": self.updated_at, "provenance": self.provenance,
                "reason": self.reason}


#: Поля, не входящие в отпечаток. Время сборки говорит о нашем прогоне, а не
#: о маршрутах: включив его, мы объявляли бы изменением каждую пересборку.
DIGEST_EXCLUDED = ("createdAt", "updatedAt")


def catalog_kind(entry: dict[str, Any]) -> tuple[str, str]:
    """Вид произведения так, как его знает каталог.

    Два поля описывают одну вещь: `type` и `is_series`. Они сходятся на всех
    53 310 записях, и именно поэтому расхождение между ними здесь не
    сглаживается, а объявляется конфликтом: если они разойдутся, это
    сообщение об испорченных данных, а не повод выбрать одно из двух.
    """
    тип = entry.get("type")
    сериал = entry.get("is_series")
    if тип == "movie" and сериал is False:
        return "MOVIE", "AUTHORITATIVE"
    if тип == "tv" and сериал is True:
        return "SERIES", "AUTHORITATIVE"
    if тип in ("movie", "tv"):
        return "UNKNOWN", "CONFLICT"
    return "UNKNOWN", "MISSING"


def load_tag_vocabulary(root: str | pathlib.Path = ".") -> dict[str, Any]:
    """Прочитать объявленный словарь тегов. Нет файла — пустой словарь.

    Пустой словарь означает, что про форму и анимацию мы не знаем ничего, и
    поля останутся незаполненными. Это верное умолчание: выдуманный словарь
    заполнил бы их уверенно и неправильно.
    """
    путь = pathlib.Path(root) / TAG_VOCABULARY_PATH
    if not путь.exists():
        return {"animation_tags": [], "form_tags": {}}
    return json.loads(путь.read_text(encoding="utf-8"))


def catalog_form(entry: dict[str, Any], vocabulary: dict[str, Any]) -> str:
    """Форма произведения по объявленному словарю. Пусто — не помечено."""
    теги = {str(т).lower() for т in (entry.get("tags") or ())}
    for тег, форма in (vocabulary.get("form_tags") or {}).items():
        if str(тег).lower() in теги:
            return str(форма)
    return ""


def catalog_animation(entry: dict[str, Any],
                      vocabulary: dict[str, Any]) -> bool | None:
    """Анимация: `True` или `None`.

    `False` не возвращается никогда. Теги заполнены у малой доли записей,
    поэтому отсутствие метки говорит о том, что запись не помечали, а не о
    том, что произведение — не анимация. Вернуть здесь `False` значило бы
    превратить наше молчание в утверждение о мире.
    """
    метки = {str(т).lower() for т in (vocabulary.get("animation_tags") or ())}
    теги = {str(т).lower() for т in (entry.get("tags") or ())}
    return True if теги & метки else None


def envelope_digest_of(header: dict[str, Any]) -> str:
    """Отпечаток заголовка снимка.

    Отпечаток записей заверяет маршруты и только их: витрину, происхождение,
    время наблюдения и полноту можно переписать, не тронув его. Отпечаток, не
    покрывающий тождества артефакта, тождества не заверяет.
    """
    сырьё = json.dumps(header, ensure_ascii=False, sort_keys=True,
                       separators=(",", ":"))
    return hashlib.blake2b(сырьё.encode("utf-8"), digest_size=16).hexdigest()


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
    #: Когда снят сам источник. Снимок не может наблюдать то, что появилось
    #: позже него, и это единственный способ такое заметить.
    source_observed_at: str = ""
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

    def header(self) -> dict[str, Any]:
        """Заголовок — всё, чем снимок себя опознаёт, кроме самих маршрутов."""
        return {
            "schemaVersion": self.schema_version,
            "compatibilityRange": COMPATIBILITY_RANGE,
            "observationId": self.observation_id,
            "siteId": self.site_id,
            "observedAt": self.observed_at.isoformat(),
            "sourceObservedAt": self.source_observed_at,
            "producerSha": self.producer_sha,
            "sourceDigest": self.source_digest,
            "sourceDigestAlgorithm": SOURCE_DIGEST_ALGORITHM,
            "normalizationVersion": NORMALIZATION_VERSION,
            "kindTaxonomy": KIND_TAXONOMY,
            "generationReason": self.generation_reason,
            "previousDigest": self.previous_digest,
            "recordCount": len(self.records),
            "collisionCount": len(self.collisions),
            "rejectedCount": len(self.rejected),
            "completeness": self.completeness.value,
            "digest": self.digest,
            "orderedBy": "routeKey",
        }

    @property
    def envelope_digest(self) -> str:
        return envelope_digest_of(self.header())

    def as_dict(self) -> dict[str, Any]:
        return {
            **self.header(),
            "envelopeDigest": self.envelope_digest,
            "records": [з.as_dict() for з in self.records],
            "collisions": [dict(с) for с in self.collisions],
            "rejected": [dict(о) for о in self.rejected],
        }


class SnapshotRefused(ValueError):
    """Снимок не собирается: вход не годен."""


def build(entries: list[dict[str, Any]], *, site_id: str, route_of,
          observed_at: dt.datetime, producer_sha: str, source_digest: str,
          generation_reason: str, content_kind_of,
          source_observed_at: str = "",
          tag_vocabulary: dict[str, Any] | None = None,
          previous: dict[str, Any] | None = None,
          route_provenance: str = "catalog+slugify",
          canonical_host: str = "") -> Snapshot:
    """Построить снимок из записей каталога.

    `route_of` — функция витрины, дающая адрес. Она передаётся, а не
    вызывается по имени: снимок обязан строиться той же функцией, какой
    витрина строит адреса, и подмена её здесь была бы подменой самого адреса.

    `route_provenance` называет, ОТКУДА взят адрес. Прежде строка
    `catalog+slugify` стояла в теле жёстко и объявлялась для любого
    снимка. Для витрины, которая ведёт собственную таблицу маршрутов,
    это неправда: адрес там не вычислен из названия, а объявлен самой
    витриной. Умолчание сохраняет прежнее значение, поэтому снимки
    Lords не меняются ни на байт.

    `canonical_host` — узел, который попадёт в `canonicalUrl`. Прежде
    туда подставлялся `site_id`, и для витрины, чей идентификатор не
    совпадает с доменом, поле переставало быть адресом: `yummyani-site`
    это имя витрины, а не узел. Умолчание сохраняет прежнее поведение,
    поэтому снимки Lords не меняются.

    `content_kind_of` обязателен и умолчания не имеет. Прежде он был
    необязательным, и первый снимок собрали, не передав его: вид произведения
    вышел пустым у всех 47 684 записей, а потребитель из-за этого не смог
    допустить ни одной страницы. Забыть передать вид теперь нельзя —
    единственная причина, по которой параметр не имеет умолчания.
    """
    if not FULL_SHA.match(producer_sha or ""):
        raise SnapshotRefused(
            f"producerSha {producer_sha!r} — не полный SHA. Сокращённый "
            "неоднозначен и не отличает производителя от его базы; именно так "
            "в снимок и попала база вместо производителя")
    if source_observed_at:
        снят = dt.datetime.fromisoformat(source_observed_at.replace("Z", "+00:00"))
        if observed_at < снят:
            raise SnapshotRefused(
                f"наблюдение {observed_at.isoformat()} раньше снятия источника "
                f"{source_observed_at}: снимок не мог наблюдать то, что "
                "появилось позже него")

    словарь = tag_vocabulary or {"animation_tags": [], "form_tags": {}}
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
                provenance=route_provenance,
                reason=f"столкновение {len(группа)} записей"))
            continue

        запись = группа[0]
        идентификатор = str(запись.get("external_id"))
        вид, состояние_вида = content_kind_of(запись)
        прежняя = прежние.get(ключ)
        записи.append(RouteRecord(
            site_id=site_id, route_key=ключ,
            canonical_url=f"https://{canonical_host or site_id}{ключ}/",
            route_kind="title", stable_work_id=идентификатор,
            content_kind=вид, content_kind_state=состояние_вида,
            content_form=catalog_form(запись, словарь),
            is_animation=catalog_animation(запись, словарь),
            state=RouteState.ACTIVE,
            created_at=(прежняя or {}).get("createdAt")
            or observed_at.isoformat(),
            updated_at=observed_at.isoformat(),
            provenance=route_provenance))

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
                    source_observed_at=source_observed_at,
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
