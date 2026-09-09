"""Мост CORE → SEO: передача разрешённых данных без секретов.

Почему экспорт, а не прямое чтение. SEO не должен читать базу ядра: чтение
чужой базы означает знание её схемы, и всякая правка схемы ломает потребителя
молча. Не должен и получать боевой секрет — ключ, выданный ради чтения,
остаётся выданным.

Почему детерминированный пакет, а не только живой вызов. Живой вызов отвечает
о состоянии на момент вызова, и повторить вчерашний ответ нельзя. Пакет
воспроизводим: тот же вход даёт тот же выход, и разбор вчерашнего расхождения
не требует машины времени.

Что мост **не** делает. Он не добывает данных, которых нет. Измерено на
159 882 записях каталога: из пятнадцати описательных полей продукта каталог
несёт `year` (94,85 %) и возрастную метку в тегах (1,84 %). Остальные
тринадцать не несёт ни одна запись. Мост поэтому возвращает для них честное
`MISSING` с причиной, а не пустой успешный факт: пустое поле в успешном ответе
читается как «источник проверен, данных нет», а верное здесь — «источника для
этого поля не существует».
"""

from __future__ import annotations

import dataclasses
import datetime as dt
import hashlib
import json
from typing import Any

import pathlib

from factory.site_engine import route_snapshot

#: Корень репозитория: словарь тегов объявлен файлом, а не кодом.
_КОРЕНЬ = pathlib.Path(__file__).resolve().parents[2]

#: Версия контракта передачи. Старшая часть — совместимость.
BRIDGE_SCHEMA = "core-seo-bridge/1.1.0"

#: Описательные поля продукта. Перечень принадлежит SEO и повторён здесь
#: намеренно как **ожидание потребителя**: мост обязан ответить про каждое, в
#: том числе про те, которых у ядра нет. Расхождение перечней — сигнал о
#: рассинхронизации версий, и проверка его ловит.
DESCRIPTIVE_FIELDS: tuple[str, ...] = (
    "year", "genres", "countries", "studio", "director", "cast", "duration",
    "episodesTotal", "seasonsTotal", "ageRating", "originalTitle",
    "alternativeTitles", "description", "synopsis", "plot",
)

#: Что каталог действительно отдаёт. Измерено, а не предположено.
SUPPLIED_FIELDS: frozenset[str] = frozenset({"year", "ageRating"})

#: Вид произведения в перечень описательных полей не входит: он не описывает
#: произведение, а определяет, чем оно является. От него зависит разметка и
#: то, что странице разрешено обещать, поэтому он идёт отдельным блоком и
#: обязателен, а не «поставляется при наличии».

#: Возрастные метки, которые каталог несёт тегом. Единственное описательное
#: сведение, приходящее не полем.
AGE_TAGS = frozenset({"0+", "6+", "12+", "13+", "16+", "17+", "18+", "NR"})

#: Поля записи каталога, которые **никогда** не покидают ядро. Перечень
#: закрыт и проверяется: `licensed` — правовой признак нашей стороны,
#: `playback` несёт адресацию потока, `poster_url` — чужой ресурс.
NEVER_EXPORTED: frozenset[str] = frozenset({
    "licensed", "playback", "poster_url", "created_at",
})

#: Наибольшее число записей в одной странице пакета.
MAX_PAGE = 500


class BridgeRefusal(Exception):
    """Мост отказался отдавать. Отказ несёт причину."""


class FieldState:
    PRESENT = "PRESENT"
    #: Поля нет у этой записи, но источник его в принципе несёт.
    ABSENT = "ABSENT"
    #: Источника для поля не существует вовсе. Это не «пусто».
    MISSING_NO_SOURCE = "MISSING_NO_SOURCE"


@dataclasses.dataclass(frozen=True, slots=True)
class FieldValue:
    """Одно поле с состоянием и причиной."""

    key: str
    state: str
    value: Any = None
    reason: str = ""

    def as_dict(self) -> dict[str, Any]:
        return {"key": self.key, "state": self.state, "value": self.value,
                "reason": self.reason}


def _age_from_tags(теги: Any) -> str | None:
    if not isinstance(теги, list):
        return None
    for т in теги:
        значение = str(т).strip()
        if значение in AGE_TAGS:
            return значение
    return None


def descriptive_of(entry: dict[str, Any]) -> list[FieldValue]:
    """Все пятнадцать полей с честным состоянием каждого.

    Перечень полный всегда. Поле, выпавшее из ответа, читается потребителем
    как «про него не спрашивали», и он не узнает, что источника нет.
    """
    год = entry.get("year")
    возраст = _age_from_tags(entry.get("tags"))
    итог: list[FieldValue] = []
    for поле in DESCRIPTIVE_FIELDS:
        if поле == "year":
            итог.append(FieldValue(поле, FieldState.PRESENT, год)
                        if год not in (None, "", 0)
                        else FieldValue(поле, FieldState.ABSENT,
                                        reason="у этой записи года нет"))
        elif поле == "ageRating":
            итог.append(FieldValue(поле, FieldState.PRESENT, возраст)
                        if возраст
                        else FieldValue(поле, FieldState.ABSENT,
                                        reason="возрастной метки нет в тегах"))
        else:
            итог.append(FieldValue(
                поле, FieldState.MISSING_NO_SOURCE,
                reason="каталог этого поля не несёт: измерено на 159 882 "
                       "записях, ноль вхождений. Это не пустое значение, а "
                       "отсутствие источника"))
    return итог


def rating_of(entry: dict[str, Any]) -> dict[str, Any]:
    """Оценка с состоянием отдельно от числа и без выдумывания шкалы.

    Шкала каталогом не передаётся, и объявлять её «наверное, из десяти»
    нельзя: 7,8 из десяти и 7,8 из ста — разные утверждения. Число голосов не
    передаётся тоже, и разметку по такой оценке выпускать нечем.
    """
    for поле, поставщик in (("kinopoisk_rating", "kp"), ("imdb_rating", "imdb")):
        сырое = entry.get(поле)
        if сырое is None:
            continue
        try:
            значение = float(str(сырое).replace(",", "."))
        except (TypeError, ValueError):
            return {"ratingState": "UNKNOWN", "value": None,
                    "reason": f"{поле}={сырое!r} — не число"}
        return {
            "ratingState": "RATED", "value": значение, "provider": поставщик,
            "scaleMin": None, "scaleMax": None, "votesCount": None,
            "reason": ("шкала и число голосов каталогом не передаются: "
                       "разметку по такой оценке выпускать нечем"),
        }
    return {"ratingState": "UNRATED", "value": None,
            "reason": "оценки нет; это утверждение о произведении, а не о "
                      "наших сведениях, и нулём не отображается"}


def content_kind_of(entry: dict[str, Any]) -> dict[str, Any]:
    """Вид произведения для пакета фактов.

    Прежде мост отдавал `providerType` и `isSeries` — сырые поля поставщика.
    Потребитель ими не пользовался, и правильно делал: истолковать чужое поле
    значит догадаться, а вид произведения решает, какую разметку выпустить и
    что странице разрешено обещать.

    Ось объявлена вместе со значением. `taxonomy` говорит, что различаются
    ровно два класса: назвать аниме аниме каталог не умеет, и притворяться
    обратным здесь нечем.
    """
    словарь = route_snapshot.load_tag_vocabulary(_КОРЕНЬ)
    вид, состояние = route_snapshot.catalog_kind(entry)
    return {
        "kind": вид,
        "state": состояние,
        "taxonomy": route_snapshot.KIND_TAXONOMY,
        "form": route_snapshot.catalog_form(entry, словарь),
        # `None` — не измерено. `False` не бывает: тег есть или его нет, а
        # отличить «не анимация» от «не помечено» нечем.
        "isAnimation": route_snapshot.catalog_animation(entry, словарь),
    }


def export_record(entry: dict[str, Any], *, site_id: str) -> dict[str, Any]:
    """Одна запись пакета. Только разрешённые поля.

    Витрина проставляется вызывающим и входит в запись: без неё потребитель
    не сможет проверить, что запись принадлежит той витрине, для которой он её
    запросил.
    """
    утечка = NEVER_EXPORTED & set(entry)
    подготовлено = {
        "siteId": site_id,
        "contentId": str(entry.get("external_id") or ""),
        "externalIds": {str(k): str(v) for k, v
                        in (entry.get("external_ids") or {}).items()},
        "displayTitle": str(entry.get("name") or ""),
        "providerType": str(entry.get("type") or ""),
        "isSeries": entry.get("is_series"),
        # Вид считается **той же функцией**, какой его считает снимок
        # маршрутов. Две реализации одного правила рано или поздно разойдутся,
        # и тогда один контракт назовёт произведение фильмом, а другой
        # сериалом — про одну и ту же запись.
        "contentKind": content_kind_of(entry),
        "contentRevision": str(entry.get("updated_at") or ""),
        "descriptive": [п.as_dict() for п in descriptive_of(entry)],
        "rating": rating_of(entry),
    }
    if not подготовлено["contentId"]:
        raise BridgeRefusal(
            "запись без устойчивого идентификатора: связать её с "
            "произведением потребитель не сможет")
    # Проверка ищет **значения**, а не имена полей. Имя в списке снятого —
    # это запись о том, что поле не ушло; проверка по именам поймала бы саму
    # эту запись и молчала бы о настоящей утечке.
    вынесено = json.dumps(подготовлено, ensure_ascii=False, sort_keys=True)
    просочилось = []
    for поле in sorted(NEVER_EXPORTED & set(entry)):
        значение = entry[поле]
        строкой = (json.dumps(значение, ensure_ascii=False, sort_keys=True)
                   if isinstance(значение, (dict, list))
                   else str(значение))
        # Короткие значения вроде True в текст попадают случайно; проверяются
        # только различимые, длиной от четырёх знаков.
        if len(строкой) >= 4 and строкой in вынесено:
            просочилось.append(поле)
    if просочилось:
        raise BridgeRefusal(
            f"значения запрещённых полей попали в пакет: {просочилось}")

    # Имена снятых полей остаются: потребителю важно знать, что поле было и
    # снято намеренно, а не отсутствовало у источника.
    подготовлено["droppedFieldNames"] = sorted(утечка)
    return подготовлено


def digest_of(records: list[dict[str, Any]]) -> str:
    """Отпечаток пакета. Время сборки в него не входит.

    Время сборки говорит о нашем прогоне, а не о данных: включив его, мы
    объявляли бы изменением каждую повторную выгрузку.
    """
    сырьё = json.dumps(records, ensure_ascii=False, sort_keys=True,
                       separators=(",", ":"))
    return hashlib.blake2b(сырьё.encode("utf-8"), digest_size=16).hexdigest()


def export_page(entries: list[dict[str, Any]], *, site_id: str,
                offset: int = 0, limit: int = 100,
                now: dt.datetime | None = None) -> dict[str, Any]:
    """Одна страница пакета: детерминированная, воспроизводимая, с отпечатком.

    Порядок задаётся идентификатором записи, а не порядком в источнике:
    порядок источника меняется при перестроении кэша, и постраничный обход
    тогда теряет записи между страницами.
    """
    if not isinstance(offset, int) or isinstance(offset, bool) or offset < 0:
        raise BridgeRefusal("offset — целое не меньше нуля")
    if not isinstance(limit, int) or isinstance(limit, bool) \
            or not 1 <= limit <= MAX_PAGE:
        raise BridgeRefusal(f"limit — целое от 1 до {MAX_PAGE}")
    if not site_id:
        raise BridgeRefusal("витрина не названа: пакет без витрины нельзя "
                            "проверить на принадлежность")

    упорядочено = sorted(entries, key=lambda з: str(з.get("external_id") or ""))
    окно = упорядочено[offset:offset + limit]
    записи = [export_record(з, site_id=site_id) for з in окно]
    момент = now or dt.datetime.now(dt.timezone.utc)
    return {
        "schemaVersion": BRIDGE_SCHEMA,
        "siteId": site_id,
        "offset": offset,
        "limit": limit,
        "returned": len(записи),
        "total": len(упорядочено),
        "hasMore": offset + len(окно) < len(упорядочено),
        "orderedBy": "contentId",
        "generatedAt": момент.isoformat(),
        "digest": digest_of(записи),
        "supplied": sorted(SUPPLIED_FIELDS),
        "notSupplied": sorted(set(DESCRIPTIVE_FIELDS) - SUPPLIED_FIELDS),
        "records": записи,
    }


def handshake(consumer_schema: str) -> dict[str, Any]:
    """Согласование версий до передачи чего бы то ни было.

    Несовместимость обязана обнаруживаться до работы, а не в её середине: на
    середине половина пакета уже разобрана чужими правилами.
    """
    ожидаемое = BRIDGE_SCHEMA.rsplit("/", 1)[0]
    объявлено = (consumer_schema or "").rsplit("/", 1)[0]
    наша_старшая = BRIDGE_SCHEMA.rsplit("/", 1)[-1].split(".", 1)[0]
    их_старшая = (consumer_schema or "").rsplit("/", 1)[-1].split(".", 1)[0]
    совместимо = объявлено == ожидаемое and их_старшая == наша_старшая
    return {
        "producerSchema": BRIDGE_SCHEMA,
        "consumerSchema": consumer_schema,
        "compatible": совместимо,
        "reason": "" if совместимо else (
            f"потребитель объявляет {consumer_schema!r}, производится "
            f"{BRIDGE_SCHEMA!r}: молча читать чужую старшую версию значит "
            "угадывать, что в ней изменилось"),
        "descriptiveFields": list(DESCRIPTIVE_FIELDS),
        "suppliedFields": sorted(SUPPLIED_FIELDS),
    }
