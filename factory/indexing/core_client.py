"""Чтение состояния индексации у Fleet Core. Только чтение.

SEO не владеет решением «открыт ли сайт». Владелец — Core: у него журнал,
разрешение владельца, ревизия и команды ``OPEN_INDEXING``/``CLOSE_INDEXING``.
Здесь — клиент его публичной поверхности ``GET /api/v1/indexing/state`` и
ничего больше. Метода, меняющего состояние, в модуле нет и появиться не может.

Почему через HTTP, а не импортом. Раньше контракт Core принимал соединение с
базой, и потребителю оставалось либо открыть чужое хранилище, либо втянуть
внутренние модули Core к себе в процесс. Первый путь привязывает SEO к схеме
хранения навсегда; второй превращает SEO во второго вычислителя того же
состояния. Второй вычислитель — это второй ответ на один вопрос.

Правила старшинства ревизий (они же — защита от ABA):

* меньшая ревизия — отказ;
* та же ревизия и тот же отпечаток — повтор, ничего не меняется;
* та же ревизия и другой отпечаток — жёсткий конфликт;
* большая ревизия — полная замена снимка целиком.

Сравнение идёт по ревизии, а не по значению состояния: цикл
``OPEN r10 → CLOSED r11 → OPEN r12`` возвращает то же значение, и клиент,
уснувший на r10, не имеет права считать себя актуальным.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

#: Версия контракта, которую этот клиент умеет читать. Иная мажорная версия
#: означает «читать нельзя», а не «читать как раньше».
ПОДДЕРЖИВАЕМЫЙ_КОНТРАКТ = "fleet-indexing-read/1.0.0"
ПОДДЕРЖИВАЕМАЯ_СХЕМА = "fleet-indexing-state/1.0.0"

OPEN = "OPEN"
CLOSED = "CLOSED"

ОБЯЗАТЕЛЬНЫЕ_ПОЛЯ = (
    "site_id", "desired_state", "revision", "snapshot_digest", "schema_version",
)

ЗДОРОВ = "HEALTHY"
НЕДОСТУПЕН = "UNAVAILABLE"

LKG_НЕ_НУЖЕН = "NOT_USED"
LKG_ПРИМЕНЁН = "SERVING_LAST_KNOWN_GOOD"
LKG_ОТСУТСТВУЕТ = "NONE_AVAILABLE"
LKG_ОТКЛОНЁН = "REJECTED"


class CoreError(RuntimeError):
    """Ответ Core непригоден. Выпуск блокируется."""


class CoreUnavailable(CoreError):
    """Core не ответил. Это не «все закрыты» — это отсутствие ответа."""


class ContractDrift(CoreError):
    """Версия контракта или схемы не та, что клиент умеет читать."""


class RevisionRegression(CoreError):
    """Пришла ревизия меньше уже принятой. Старое не переписывает новое."""


class RevisionConflict(CoreError):
    """Та же ревизия с другим отпечатком. Одно решение — один отпечаток."""


@dataclass(frozen=True)
class Envelope:
    """Атомарный ответ Core: состояние и ревизия вместе.

    Вместе — не удобство, а требование. Два запроса дают два разных момента, и
    склеенный из них ответ не соответствует ни одному.
    """

    contract_version: str
    schema_version: str
    provider_health: str
    snapshot_digest: str
    taken_at: str | None
    sites: dict[str, dict[str, Any]] = field(default_factory=dict)
    lkg_status: str = LKG_НЕ_НУЖЕН
    release_blocked: bool = False
    blockers: tuple[str, ...] = ()

    def состояние(self, site_id: str) -> str:
        """Решение по сайту. Неизвестный — закрыт: разрешение выдаётся поимённо."""
        запись = self.sites.get(site_id)
        return запись["desired_state"] if запись else CLOSED

    def revision(self, site_id: str) -> int:
        запись = self.sites.get(site_id)
        return int(запись["revision"]) if запись else 0

    @property
    def open_sites(self) -> tuple[str, ...]:
        return tuple(sorted(s for s, з in self.sites.items()
                            if з["desired_state"] == OPEN))

    @property
    def closed_sites(self) -> tuple[str, ...]:
        return tuple(sorted(s for s, з in self.sites.items()
                            if з["desired_state"] == CLOSED))

    def matrix(self) -> dict:
        return {"open": list(self.open_sites), "closed": list(self.closed_sites),
                "open_count": len(self.open_sites),
                "closed_count": len(self.closed_sites),
                "snapshot_digest": self.snapshot_digest}

    def to_json(self) -> str:
        """Детерминированная запись: одинаковый ответ — одинаковые байты."""
        return json.dumps({
            "contract_version": self.contract_version,
            "schema_version": self.schema_version,
            "provider_health": self.provider_health,
            "snapshot_digest": self.snapshot_digest,
            "taken_at": self.taken_at,
            "lkg_status": self.lkg_status,
            "sites": self.sites,
        }, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _разобрать(данные: dict) -> Envelope:
    """Проверить ответ целиком до того, как хоть что-то из него использовать."""
    if not isinstance(данные, dict):
        raise ContractDrift("ответ Core не является объектом")
    версия = данные.get("contract_version")
    if версия != ПОДДЕРЖИВАЕМЫЙ_КОНТРАКТ:
        raise ContractDrift(
            f"контракт {версия!r}, поддерживается {ПОДДЕРЖИВАЕМЫЙ_КОНТРАКТ!r}")
    схема = данные.get("schema_version")
    if схема != ПОДДЕРЖИВАЕМАЯ_СХЕМА:
        raise ContractDrift(
            f"схема состояния {схема!r}, поддерживается {ПОДДЕРЖИВАЕМАЯ_СХЕМА!r}")
    отпечаток = данные.get("snapshot_digest")
    if not отпечаток:
        raise ContractDrift("в снимке нет отпечатка: подтвердить его нечем")

    сайты: dict[str, dict[str, Any]] = {}
    for запись in данные.get("sites") or []:
        нет = [п for п in ОБЯЗАТЕЛЬНЫЕ_ПОЛЯ if п not in запись]
        if нет:
            raise ContractDrift(
                f"запись {запись.get('site_id')!r} неполна, нет полей {нет}: "
                "частичный ответ не является ответом")
        if запись["desired_state"] not in (OPEN, CLOSED):
            raise ContractDrift(
                f"{запись['site_id']}: состояние {запись['desired_state']!r} не объявлено")
        if запись["site_id"] in сайты:
            raise ContractDrift(
                f"{запись['site_id']}: сайт встречается дважды — одна личность, "
                "два решения")
        сайты[запись["site_id"]] = dict(запись)

    return Envelope(
        contract_version=версия, schema_version=схема,
        provider_health=данные.get("provider_health", ЗДОРОВ),
        snapshot_digest=отпечаток, taken_at=данные.get("taken_at"),
        sites=сайты,
    )


def прочитать(
    base_url: str, token: str, *, timeout: float = 10.0, opener=None
) -> Envelope:
    """Забрать снимок у Core. Любая неполнота — исключение, а не догадка."""
    адрес = base_url.rstrip("/") + "/api/v1/indexing/state"
    запрос = urllib.request.Request(адрес, headers={
        "Authorization": f"Bearer {token}",
        "Accept": "application/json",
    })
    открыть = opener or urllib.request.urlopen
    try:
        with открыть(запрос, timeout=timeout) as ответ:
            тело = ответ.read().decode("utf-8")
    except urllib.error.HTTPError as ош:
        if ош.code in (500, 502, 503, 504):
            raise CoreUnavailable(f"Core ответил {ош.code}") from ош
        raise CoreError(f"Core отказал: {ош.code}") from ош
    except (urllib.error.URLError, OSError, TimeoutError) as ош:
        raise CoreUnavailable(f"Core недоступен: {ош}") from ош
    try:
        данные = json.loads(тело)
    except ValueError as ош:
        raise ContractDrift(f"ответ Core не разбирается: {ош}") from ош
    return _разобрать(данные)


def сверить_ревизии(принятый: Envelope | None, новый: Envelope) -> Envelope:
    """Старшинство ревизий. Сравнение по ревизии, не по значению.

    Возвращает снимок, который следует считать действующим.
    """
    if принятый is None:
        return новый
    for site_id, запись in новый.sites.items():
        было = принятый.sites.get(site_id)
        if было is None:
            continue
        старая, новая = int(было["revision"]), int(запись["revision"])
        if новая < старая:
            raise RevisionRegression(
                f"{site_id}: пришла ревизия {новая}, принята {старая}. "
                "Старый артефакт, кеш или копия не переписывают новое решение")
        if новая == старая and запись["snapshot_digest"] != было["snapshot_digest"]:
            raise RevisionConflict(
                f"{site_id}: ревизия {новая} с другим отпечатком. "
                "Одно решение — один отпечаток")
    return новый


def разрешить(
    base_url: str, token: str, *, last_known_good: Envelope | None = None,
    принятый: Envelope | None = None, timeout: float = 10.0, opener=None,
) -> Envelope:
    """Действующее состояние вместе с тем, можно ли выпускать релиз.

    Три исхода, и все три названы:

    * Core ответил — работаем с его снимком;
    * Core недоступен, есть подтверждённый снимок — берём его и **блокируем
      выпуск**: действующий production продолжает работать как был;
    * Core недоступен и подтверждённого снимка нет — блокируем и не публикуем
      ничего. Пустая матрица означала бы «все закрыты».
    """
    try:
        снимок = прочитать(base_url, token, timeout=timeout, opener=opener)
    except CoreUnavailable as ош:
        if last_known_good is None:
            return Envelope(
                contract_version=ПОДДЕРЖИВАЕМЫЙ_КОНТРАКТ,
                schema_version=ПОДДЕРЖИВАЕМАЯ_СХЕМА, provider_health=НЕДОСТУПЕН,
                snapshot_digest="", taken_at=None, sites={},
                lkg_status=LKG_ОТСУТСТВУЕТ, release_blocked=True,
                blockers=(f"{ош}; подтверждённого снимка нет",),
            )
        return Envelope(
            contract_version=last_known_good.contract_version,
            schema_version=last_known_good.schema_version,
            provider_health=НЕДОСТУПЕН, snapshot_digest=last_known_good.snapshot_digest,
            taken_at=last_known_good.taken_at, sites=dict(last_known_good.sites),
            lkg_status=LKG_ПРИМЕНЁН, release_blocked=True,
            blockers=(f"{ош}; отдаётся подтверждённый снимок",),
        )
    return сверить_ревизии(принятый, снимок)


def сохранить_lkg(снимок: Envelope, путь: Path) -> Path:
    """Сохранить подтверждённый снимок. Это кеш чтения, а не источник решений.

    Обратно в Core он не записывается никогда: SEO не владеет состоянием.
    """
    цель = Path(путь)
    цель.parent.mkdir(parents=True, exist_ok=True)
    цель.write_text(снимок.to_json() + "\n", encoding="utf-8")
    return цель


def загрузить_lkg(путь: Path) -> Envelope:
    """Прочитать подтверждённый снимок. Непроверяемый не применяется."""
    текст = Path(путь).read_text(encoding="utf-8")
    if not текст.strip():
        raise ContractDrift("подтверждённый снимок пуст")
    try:
        данные = json.loads(текст)
    except ValueError as ош:
        raise ContractDrift(f"подтверждённый снимок не разбирается: {ош}") from ош
    # Сохранённый снимок хранит сайты словарём, ответ Core — списком.
    сайты = данные.get("sites")
    if isinstance(сайты, dict):
        данные = {**данные, "sites": list(сайты.values())}
    снимок = _разобрать(данные)
    return Envelope(**{**снимок.__dict__, "lkg_status": LKG_ПРИМЕНЁН})
