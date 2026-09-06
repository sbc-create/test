"""Контракт CORE → SEO: authoritative запись, привязанная к публичной странице.

До этого контракта у SEO была очередь страниц, у ядра — каталог с видом
произведения и состоянием воспроизведения, и соединить одно с другим было
нечем. SEO измерил цену: 159 записей очереди из 268 остались без решения
(`SEO_TO_CORE-026`), потому что состояние воспроизведения не к чему было
привязать.

**Связь детерминирована, а не угадана.** Маршрут страницы вычисляет сама
витрина — `factory.lords.live_catalog` — одной функцией и одним правилом
разведения совпадений. Контракт вызывает **ту же функцию того же движка**, а
не воспроизводит её похожим кодом. Это существенно: при изменении правила
адресации сломается и витрина, и связь, и сломаются они одинаково, а не
разойдутся тихо.

**Адрес не является идентичностью.** Витрина разводит одинаковые адреса
номером — `-2`, `-3` — в порядке ответа источника. На боевом снимке такой
номер получают 5 603 записи из 53 232. Стоит источнику переставить две записи
с одинаковым названием, и они молча меняются адресами. Поэтому идентичность
здесь — `contentId`, устойчивый ключ записи, а `routeId` из него выводится и
может меняться, не разрывая связи.

**Отказ закрыт наглухо.** Неоднозначный адрес не даёт выбрать «первого
подходящего»: обе записи получают состояние `ROUTE_COLLISION` и код причины и
уходят в очередь разбора. Молчаливый выбор означал бы приписать странице чужое
состояние воспроизведения — то есть обещание просмотра, которого никто не
проверял.

Секретов, токенов поставщика и приватных адресов потока контракт не несёт:
`playbackState` отвечает на вопрос «можно ли обещать просмотр», а не «где
лежит файл».
"""

from __future__ import annotations

import dataclasses
import enum
import hashlib
import json
from collections.abc import Iterable, Sequence
from typing import Any

from factory.site_engine.catalog_identity import KindDecision
from factory.site_engine.content_kind import ContentKind, emits_schema, schema_type_for

#: Версия схемы. SemVer; `latest` запрещён и здесь, и у потребителя: контракт,
#: на который ссылаются словом «последний», нельзя ни закрепить, ни откатить.
SCHEMA_VERSION = "seo-route-binding/1.0.0"

#: Версия самого контракта, отдельно от версии схемы. Схема описывает форму,
#: контракт — обещания о содержимом; они меняются по разным поводам.
CONTRACT_VERSION = "1.0.0"

#: Файл с перечнем пространств имён внешних идентификаторов.
#:
#: Перечень живёт настройкой, а не кодом: имена поставщиков — знание
#: предметной области, и ядру их перечислять не следует. Гейт нейтральности
#: это и потребовал. Ядро умеет работать с любым перечнем и не знает
#: конкретного.
ID_NAMESPACES_REF = "config/external-id-namespaces.yaml"


def _загрузить_пространства() -> tuple[tuple[str, ...], str]:
    """Пространства имён из настройки. Без настройки — пустой перечень и причина.

    Пустой, а не «какой-нибудь встроенный»: подставить свой список значило бы
    молча дать права пространствам, о которых эксплуатация не знает.

    Причина возвращается вместе с перечнем, потому что пустой перечень сам по
    себе не отвечает на вопрос «почему». Отсутствие файла и сломанный файл
    выглядели одинаково, и это не догадка: так меня обманула собственная
    проверка — ошибка в ней ушла в широкий `except` и вернулась пустотой,
    которую я прочитал как незавершённую установку. То же самое случилось бы с
    эксплуатацией, только дороже.
    """
    from pathlib import Path

    from factory.paths import PATHS

    путь = Path(PATHS.root, ID_NAMESPACES_REF)
    if not путь.exists():
        return (), f"{ID_NAMESPACES_REF} нет в корне состояния"
    try:
        import yaml

        сырьё = yaml.safe_load(путь.read_text(encoding="utf-8"))
        значения = (сырьё or {}).get("namespaces") or []
        перечень = tuple(str(v).strip() for v in значения if str(v).strip())
    except Exception as ошибка:  # noqa: BLE001 — сломанная настройка не роняет разбор
        return (), f"{ID_NAMESPACES_REF} не разобран: {ошибка}"
    if not перечень:
        return (), f"{ID_NAMESPACES_REF} не называет ни одного пространства"
    return перечень, ""


#: Пространства имён внешних идентификаторов. Идентификатор из неизвестного
#: пространства не отбрасывается тихо, но и разрешением на воспроизведение не
#: становится: право обещать просмотр даёт отдельный перечень.
ID_NAMESPACES, ID_NAMESPACES_REASON = _загрузить_пространства()

#: Файл с перечнем идентификаторов, которыми разрешено адресовать плеер.
PLAYBACK_POLICY_REF = "config/playback-identifiers.yaml"


def _загрузить_разрешённые() -> tuple[frozenset[str], str]:
    """Идентификаторы, дающие право обещать просмотр.

    Берутся из политики воспроизведения, а не перечисляются здесь: включение
    идентификатора — решение владельца контракта с записью авторизации
    (`CORE_TO_OWNER-014`), и дублировать его в коде значило бы завести вторую
    копию, которая разъедется с первой.
    """
    try:
        from factory.site_engine.playback_policy import resolve

        разрешённые = frozenset(resolve().allowed)
    except Exception as ошибка:  # noqa: BLE001 — сломанная политика не роняет разбор
        return frozenset(), f"политика воспроизведения не прочитана: {ошибка}"
    if not разрешённые:
        return frozenset(), "политика не разрешает ни одного идентификатора"
    return разрешённые, ""


#: Идентификаторы, разрешённые как основание воспроизведения.
PLAYBACK_AUTHORISED, PLAYBACK_AUTHORISED_REASON = _загрузить_разрешённые()


class BindingState(str, enum.Enum):
    """Состояние связи записи каталога с публичной страницей."""

    #: Связь однозначна: один маршрут, одна запись.
    BOUND = "BOUND"
    #: Маршрут принадлежит более чем одной записи. Выбирать нельзя.
    ROUTE_COLLISION = "ROUTE_COLLISION"
    #: Запись не адресуема: нет ключа или названия.
    NOT_ADDRESSABLE = "NOT_ADDRESSABLE"
    #: Вид произведения не установлен или конфликтен.
    KIND_UNRESOLVED = "KIND_UNRESOLVED"


#: Состояния, при которых потребителю разрешено строить страницу.
USABLE = (BindingState.BOUND,)


class ReasonCode(str, enum.Enum):
    """Коды причин. Один код — одна причина, без «прочего»."""

    OK = "OK"
    ROUTE_AMBIGUOUS = "ROUTE_AMBIGUOUS"
    MISSING_CONTENT_ID = "MISSING_CONTENT_ID"
    MISSING_TITLE = "MISSING_TITLE"
    KIND_CONFLICTED = "KIND_CONFLICTED"
    KIND_MISSING = "KIND_MISSING"
    PLAYBACK_OK = "PLAYBACK_OK"
    IDENTIFIER_FORBIDDEN_BY_CONTRACT = "IDENTIFIER_FORBIDDEN_BY_CONTRACT"
    MISSING_PROVIDER_ID = "MISSING_PROVIDER_ID"
    PROVIDER_NOT_PLAYABLE = "PROVIDER_NOT_PLAYABLE"
    PLAYBACK_STALE = "PLAYBACK_STALE"


class PlaybackState(str, enum.Enum):
    """Состояние воспроизведения. Новое состояние обязано попасть в запрет."""

    PLAYABLE = "PLAYABLE"
    BLOCKED_BY_CONTRACT = "BLOCKED_BY_CONTRACT"
    NO_IDENTIFIER = "NO_IDENTIFIER"
    NO_STREAM = "NO_STREAM"
    UNKNOWN = "UNKNOWN"


class KindState(str, enum.Enum):
    """Установлен ли вид и можно ли на него опираться."""

    RESOLVED = "RESOLVED"
    CONFLICTED = "CONFLICTED"
    MISSING = "MISSING"


class RatingState(str, enum.Enum):
    """Состояние оценки — отдельно от числа."""

    RATED = "RATED"
    UNRATED = "UNRATED"
    NOT_APPLICABLE = "NOT_APPLICABLE"
    UNKNOWN = "UNKNOWN"


class ContractViolation(ValueError):
    """Значения нарушают обещания контракта."""


@dataclasses.dataclass(frozen=True)
class RouteBinding:
    """Одна запись контракта: что это, где это и что об этом можно обещать."""

    site_id: str
    #: Устойчивый ключ записи. Не меняется при смене адреса.
    content_id: str
    #: Внешние идентификаторы с пространством имён.
    external_ids: dict[str, str]
    #: Маршрут в терминах витрины. Выводится из идентичности, не наоборот.
    route_id: str
    page_type: str
    canonical_path: str
    content_kind: ContentKind
    content_kind_state: KindState
    #: Чем установлен вид: полем поставщика, тегом, решением редактора.
    content_kind_provenance: str
    playback_state: PlaybackState
    playback_reason_code: ReasonCode
    #: Момент, когда состояние воспроизведения наблюдалось. Не момент выгрузки.
    playback_observed_at: str
    #: Ревизия записи: меняется вместе с содержимым, не вместе с выгрузкой.
    content_revision: str
    binding_state: BindingState
    reason_codes: tuple[ReasonCode, ...]
    provenance: str
    snapshot_at: str
    #: Кандидаты вида при конфликте. Меньше двух — не конфликт, а отсутствие:
    #: редактору нечего разбирать, если выбор не из чего делать.
    kind_candidates: tuple[ContentKind, ...] = ()
    rating_state: RatingState = RatingState.UNKNOWN
    rating_value: float | None = None
    is_animation: bool | None = None
    display_title: str = ""
    schema_version: str = SCHEMA_VERSION
    contract_version: str = CONTRACT_VERSION

    def __post_init__(self) -> None:
        if not self.reason_codes:
            raise ContractViolation("запись без кода причины непроверяема")

        # Неизвестный и конфликтный вид не превращается в фильм ни при каких
        # обстоятельствах: 231 конфликтная запись каталога должна остаться
        # конфликтной, а не стать Movie.
        if self.content_kind_state is not KindState.RESOLVED \
                and self.content_kind is not ContentKind.UNKNOWN:
            raise ContractViolation(
                f"состояние вида {self.content_kind_state.value} несёт вид "
                f"{self.content_kind.value}: неустановленный вид обязан "
                "выглядеть как отсутствие вида")
        if self.content_kind_state is KindState.RESOLVED \
                and self.content_kind is ContentKind.UNKNOWN:
            raise ContractViolation(
                "вид объявлен установленным и равен UNKNOWN одновременно")

        # Отсутствие оценки не превращается в ноль.
        if self.rating_state is not RatingState.RATED \
                and self.rating_value is not None:
            raise ContractViolation(
                f"оценка в состоянии {self.rating_state.value} несёт значение "
                f"{self.rating_value}: ноль здесь означал бы оценку «ноль»")
        if self.rating_state is RatingState.RATED and self.rating_value is None:
            raise ContractViolation("RATED без числа: оценка есть или её нет")

        # Отсутствие воспроизведения не превращается в обещание просмотра.
        if self.playback_state is PlaybackState.PLAYABLE:
            if self.playback_reason_code is not ReasonCode.PLAYBACK_OK:
                raise ContractViolation(
                    "PLAYABLE с кодом причины "
                    f"{self.playback_reason_code.value}")
            if not self.playback_observed_at:
                raise ContractViolation(
                    "PLAYABLE без момента наблюдения: неподтверждённая "
                    "доступность неотличима от неизвестной")

        # Связь объявлена — значит она однозначна.
        if self.binding_state is BindingState.BOUND:
            if not self.content_id:
                raise ContractViolation("BOUND без устойчивого ключа записи")
            if not self.route_id or not self.canonical_path:
                raise ContractViolation("BOUND без маршрута")
            if ReasonCode.ROUTE_AMBIGUOUS in self.reason_codes:
                raise ContractViolation(
                    "BOUND с признаком неоднозначного маршрута")

        if self.content_kind_state is KindState.CONFLICTED \
                and len(self.kind_candidates) < 2:
            raise ContractViolation(
                "конфликт вида без двух кандидатов не является конфликтом: "
                "разбирать нечего")

        неизвестные = set(self.external_ids) - set(ID_NAMESPACES)
        if неизвестные:
            raise ContractViolation(
                f"идентификаторы без объявленного пространства имён: "
                f"{sorted(неизвестные)}. Пространство добавляется правкой "
                "контракта, а не молчаливым принятием")

    # --- что разрешено потребителю -----------------------------------------

    @property
    def usable(self) -> bool:
        return self.binding_state in USABLE

    @property
    def may_promise_playback(self) -> bool:
        """Можно ли обещать просмотр. Свежесть проверяет потребитель.

        Право зависит от двух вещей и намеренно не зависит от третьей.
        Нужно, чтобы поток был подтверждён и чтобы страница однозначно
        принадлежала этой записи: при неоднозначном адресе обещание досталось
        бы чужой странице.

        А вот установленность вида здесь ни при чём, и первая редакция этого
        свойства ошибалась, требуя её. Стенд поймал случай: у записи
        `Re:Zero. Перерыв с нуля 4` поток подтверждён агрегатором `mali`, но
        вид не разрешён — и контракт запрещал обещать просмотр, которого нет
        только у вида. Неизвестный вид не отменяет существующего видео; он
        отменяет разметку и типоспецифичный текст, а это разные запреты.
        """
        return (self.binding_state in (BindingState.BOUND,
                                       BindingState.KIND_UNRESOLVED)
                and self.playback_state is PlaybackState.PLAYABLE)

    @property
    def schema_type(self) -> str:
        """Тип Schema.org. Пустая строка — разметку не выпускать."""
        if self.content_kind_state is not KindState.RESOLVED:
            return ""
        return schema_type_for(self.content_kind) if emits_schema(self.content_kind) else ""

    def canonical_url(self, profile: Any) -> str:
        """Полный адрес из версионированного профиля витрины.

        Адрес не передаётся в контракте готовым намеренно: он принадлежит
        профилю, а профиль версионируется отдельно и может меняться без
        изменения каталога. Потребитель строит адрес сам и всегда из
        действующего профиля — иначе выгрузка недельной давности несла бы
        вчерашний домен.
        """
        host = (getattr(profile, "canonical_host", "")
                or getattr(profile, "primary_domain", ""))
        if not host:
            raise ContractViolation(
                f"профиль {getattr(profile, 'site_id', '?')} не называет "
                "канонический хост: адрес построить не из чего")
        if getattr(profile, "site_id", "") != self.site_id:
            raise ContractViolation(
                f"профиль витрины {getattr(profile, 'site_id', '?')} не "
                f"соответствует записи витрины {self.site_id}")
        схема = "https://"
        host = host.removeprefix("https://").removeprefix("http://").rstrip("/")
        return f"{схема}{host}{self.canonical_path}"

    def as_dict(self) -> dict[str, Any]:
        return {
            "schemaVersion": self.schema_version,
            "contractVersion": self.contract_version,
            "siteId": self.site_id,
            "contentId": self.content_id,
            "externalIds": dict(self.external_ids),
            "routeId": self.route_id,
            "pageType": self.page_type,
            "canonicalPath": self.canonical_path,
            "contentKind": self.content_kind.value,
            "contentKindState": self.content_kind_state.value,
            "contentKindProvenance": self.content_kind_provenance,
            "isAnimation": self.is_animation,
            "displayTitle": self.display_title,
            "playbackState": self.playback_state.value,
            "playbackReasonCode": self.playback_reason_code.value,
            "playbackObservedAt": self.playback_observed_at,
            "ratingState": self.rating_state.value,
            "ratingValue": self.rating_value,
            "contentRevision": self.content_revision,
            "bindingState": self.binding_state.value,
            "reasonCodes": [c.value for c in self.reason_codes],
            "schemaType": self.schema_type,
            "mayPromisePlayback": self.may_promise_playback,
            "kindCandidates": [k.value for k in self.kind_candidates],
            "provenance": self.provenance,
            "snapshotAt": self.snapshot_at,
            "contentIdentity": self.as_identity_payload(),
        }

    def as_identity_payload(self) -> dict[str, Any]:
        """Тот же вид произведения в форме `content-identity/1.0.0`.

        Нужен, чтобы потребитель, написанный до этого контракта, продолжал
        работать без единой правки. Новые поля он просто не прочитает, а вид,
        состояние и основания конфликта получит там же, где получал раньше.
        Совместимость, проверяемая только словами, кончается на первой правке
        любой из сторон.
        """
        статус = {KindState.RESOLVED: "RESOLVED",
                  KindState.CONFLICTED: "CONFLICTED",
                  KindState.MISSING: "MISSING"}[self.content_kind_state]
        return {
            "schemaVersion": "content-identity/1.0.0",
            "identityStatus": статус,
            "contentKind": self.content_kind.value,
            "candidateKinds": [k.value for k in self.kind_candidates],
            "conflictState": [c.value for c in self.reason_codes
                              if c is not ReasonCode.OK],
            "isAnimation": self.is_animation,
            "displayedTitle": self.display_title,
            "internalEntityId": f"{self.site_id}:{self.content_id}",
            "providerAssetId": self.content_id,
            "mappingMethod": self.content_kind_provenance,
            "mappingConfidence": 1.0 if self.content_kind_state is KindState.RESOLVED else 0.0,
            "payloadHash": self.content_revision,
            "resolverVersion": f"seo-route-binding/{self.contract_version}",
        }


# --- сборка -----------------------------------------------------------------

def kind_state_of(decision: KindDecision) -> tuple[KindState, ContentKind, str]:
    """Состояние вида, сам вид и чем он установлен.

    Конфликт и отсутствие приводят к `UNKNOWN` — не потому, что «ничего не
    нашли», а потому, что найденного недостаточно для однозначного ответа.
    """
    if decision.conflicted:
        return KindState.CONFLICTED, ContentKind.UNKNOWN, decision.reason or "конфликт"
    if decision.kind is ContentKind.UNKNOWN:
        return KindState.MISSING, ContentKind.UNKNOWN, decision.reason or "вида нет"
    происхождение = ("решение редактора " + decision.decided_by
                     if decision.decided_by_editor
                     else decision.reason or "данные источника")
    return KindState.RESOLVED, decision.kind, происхождение


def playback_of(entry: dict) -> tuple[PlaybackState, ReasonCode]:
    """Состояние воспроизведения по записи каталога. Без догадок."""
    playback = entry.get("playback")
    if isinstance(playback, dict) and playback.get("aggregator"):
        агрегатор = str(playback["aggregator"])
        if агрегатор in PLAYBACK_AUTHORISED:
            return PlaybackState.PLAYABLE, ReasonCode.PLAYBACK_OK
        return (PlaybackState.BLOCKED_BY_CONTRACT,
                ReasonCode.IDENTIFIER_FORBIDDEN_BY_CONTRACT)
    ids = entry.get("external_ids")
    if not isinstance(ids, dict) or not ids:
        return PlaybackState.NO_IDENTIFIER, ReasonCode.MISSING_PROVIDER_ID
    if set(ids) & PLAYBACK_AUTHORISED:
        return PlaybackState.NO_STREAM, ReasonCode.PROVIDER_NOT_PLAYABLE
    return (PlaybackState.BLOCKED_BY_CONTRACT,
            ReasonCode.IDENTIFIER_FORBIDDEN_BY_CONTRACT)


def revision_of(entry: dict) -> str:
    """Ревизия записи: отпечаток её содержимого, а не времени выгрузки.

    Повторная выгрузка неизменившейся записи обязана дать ту же ревизию —
    иначе потребитель не сможет отличить «данные изменились» от «выгрузку
    сделали заново».
    """
    значимое = {k: entry.get(k) for k in sorted((
        "external_id", "name", "type", "is_series", "tags", "year",
        "playback", "external_ids", "kinopoisk_rating", "imdb_rating"))}
    сырьё = json.dumps(значимое, sort_keys=True, ensure_ascii=False,
                       default=str)
    return hashlib.sha256(сырьё.encode("utf-8")).hexdigest()[:16]


def digest(bindings: Iterable[RouteBinding]) -> str:
    """Отпечаток выгрузки. От порядка записей не зависит."""
    строки = sorted(
        f"{b.site_id}|{b.content_id}|{b.route_id}|{b.content_kind.value}|"
        f"{b.playback_state.value}|{b.binding_state.value}|{b.content_revision}"
        for b in bindings)
    return hashlib.sha256("\n".join(строки).encode("utf-8")).hexdigest()


def envelope(bindings: Sequence[RouteBinding], *, site_id: str,
             snapshot_at: str, provenance: str) -> dict[str, Any]:
    """Выгрузка целиком со всем, что нужно для её проверки."""
    по_состоянию: dict[str, int] = {}
    for b in bindings:
        по_состоянию[b.binding_state.value] = по_состоянию.get(
            b.binding_state.value, 0) + 1
    return {
        "schemaVersion": SCHEMA_VERSION,
        "contractVersion": CONTRACT_VERSION,
        "siteId": site_id,
        "snapshotAt": snapshot_at,
        "provenance": provenance,
        "records": len(bindings),
        "byBindingState": по_состоянию,
        "digest": digest(bindings),
        "bindings": [b.as_dict() for b in bindings],
    }
