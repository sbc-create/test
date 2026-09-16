"""Ревизионированный артефакт политики: то, что читает витрина.

Зачем он между Core и приложением. Витрина обязана знать, открыта ли она для
поиска, на каждый отрисованный ответ. Ходить за этим в Core на каждый
пользовательский запрос нельзя: сеть отказывает, а отказ сети не является
решением закрыть сайт. Поэтому Core читает управляющий слой, а приложение —
готовый файл.

Файл неизменяем и несёт ревизию. Из него видно, из какого решения Core собраны
``robots.txt``, мета-теги, заголовок и карта сайта, — и если они собраны из
разных ревизий, это видно тоже.

Что артефакт **не** делает: не принимает решений. Он переносит уже принятое.
Записать в него состояние, которого нет в Core, нельзя — публикация начинается
с чтения Core и падает, если прочитать не удалось.
"""

from __future__ import annotations

import json
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from factory.indexing.core_client import (
    CLOSED,
    OPEN,
    ПОДДЕРЖИВАЕМАЯ_СХЕМА,
    ПОДДЕРЖИВАЕМЫЙ_КОНТРАКТ,
    ContractDrift,
    Envelope,
    RevisionRegression,
)

#: Версия формата самого артефакта. Отличается от версии состояния: формат
#: файла может смениться, когда состояние осталось прежним.
ФОРМАТ = "fleet-indexing-artifact/1.0.0"

#: Поля, без которых артефакт не является артефактом.
ОБЯЗАТЕЛЬНЫЕ = (
    "artifact_format", "schema_version", "contract_version", "site_id",
    "desired_state", "indexing_revision", "event_id", "state_digest",
)


class ArtifactError(RuntimeError):
    """Артефакт непригоден. Публикация или чтение блокируются."""


@dataclass(frozen=True)
class PolicyArtifact:
    """Решение по одному сайту вместе с ревизией, из которой оно взято."""

    artifact_format: str
    schema_version: str
    contract_version: str
    site_id: str
    desired_state: str
    indexing_revision: int
    event_id: str
    state_digest: str
    taken_at: str | None = None
    source: str = "CORE"

    @property
    def open(self) -> bool:
        return self.desired_state == OPEN

    def to_json(self) -> str:
        """Детерминированная запись: одно решение — один файл, байт в байт."""
        return json.dumps({
            "artifact_format": self.artifact_format,
            "schema_version": self.schema_version,
            "contract_version": self.contract_version,
            "site_id": self.site_id,
            "desired_state": self.desired_state,
            "indexing_revision": self.indexing_revision,
            "event_id": self.event_id,
            "state_digest": self.state_digest,
            "taken_at": self.taken_at,
            "source": self.source,
        }, ensure_ascii=False, sort_keys=True, indent=2) + "\n"


def собрать(envelope: Envelope, site_id: str, *, source: str = "CORE") -> PolicyArtifact:
    """Построить артефакт из ответа Core.

    Сайт, которого в ответе нет, артефакта не получает. Подставить ему
    ``CLOSED`` было бы решением, которого никто не принимал: закрытый по
    недоразумению сайт исчезает из поиска так же надёжно, как закрытый нарочно.
    """
    запись = envelope.sites.get(site_id)
    if запись is None:
        raise ArtifactError(
            f"{site_id}: в ответе Core такого сайта нет. Публиковать решение, "
            "которого не принимали, нельзя")
    if запись["desired_state"] not in (OPEN, CLOSED):
        raise ArtifactError(
            f"{site_id}: состояние {запись['desired_state']!r} не объявлено")
    return PolicyArtifact(
        artifact_format=ФОРМАТ,
        schema_version=envelope.schema_version,
        contract_version=envelope.contract_version,
        site_id=site_id,
        desired_state=запись["desired_state"],
        indexing_revision=int(запись["revision"]),
        event_id=str(запись.get("source_event_id") or ""),
        state_digest=str(запись["snapshot_digest"]),
        taken_at=envelope.taken_at,
        source=source,
    )


def прочитать(путь: Path) -> PolicyArtifact:
    """Прочитать артефакт. Неполный или чужой не применяется."""
    цель = Path(путь)
    текст = цель.read_text(encoding="utf-8")
    if not текст.strip():
        raise ArtifactError(f"{цель.name}: артефакт пуст")
    try:
        данные: dict[str, Any] = json.loads(текст)
    except ValueError as ош:
        raise ArtifactError(f"{цель.name}: артефакт не разбирается — {ош}") from ош
    нет = [п for п in ОБЯЗАТЕЛЬНЫЕ if п not in данные]
    if нет:
        raise ArtifactError(f"{цель.name}: нет полей {нет}: частичный артефакт не применяется")
    if данные["artifact_format"] != ФОРМАТ:
        raise ArtifactError(
            f"{цель.name}: формат {данные['artifact_format']!r}, ожидается {ФОРМАТ!r}")
    if данные["schema_version"] != ПОДДЕРЖИВАЕМАЯ_СХЕМА:
        raise ContractDrift(
            f"{цель.name}: схема {данные['schema_version']!r}, "
            f"поддерживается {ПОДДЕРЖИВАЕМАЯ_СХЕМА!r}")
    if данные["contract_version"] != ПОДДЕРЖИВАЕМЫЙ_КОНТРАКТ:
        raise ContractDrift(
            f"{цель.name}: контракт {данные['contract_version']!r}, "
            f"поддерживается {ПОДДЕРЖИВАЕМЫЙ_КОНТРАКТ!r}")
    if данные["desired_state"] not in (OPEN, CLOSED):
        raise ArtifactError(f"{цель.name}: состояние {данные['desired_state']!r} не объявлено")
    ревизия = данные["indexing_revision"]
    if not isinstance(ревизия, int) or ревизия < 0:
        raise ArtifactError(f"{цель.name}: ревизия {ревизия!r} не является номером")
    return PolicyArtifact(
        artifact_format=данные["artifact_format"],
        schema_version=данные["schema_version"],
        contract_version=данные["contract_version"],
        site_id=данные["site_id"],
        desired_state=данные["desired_state"],
        indexing_revision=ревизия,
        event_id=данные["event_id"],
        state_digest=данные["state_digest"],
        taken_at=данные.get("taken_at"),
        source=данные.get("source", "CORE"),
    )


def опубликовать(артефакт: PolicyArtifact, путь: Path, *, allow_same: bool = True) -> Path:
    """Выложить артефакт атомарно, не допуская понижения ревизии.

    Атомарность — запись во временный файл рядом и ``rename``. Приложение
    читает файл целиком; увидеть его наполовину записанным оно не должно, иначе
    в момент выкладки витрина получит обрывок вместо решения.

    Понижение ревизии запрещено. Старый релиз, кеш или резервная копия, дойдя
    сюда, вернули бы прежнее решение владельца — ровно та авария, ради которой
    ревизия и существует.
    """
    цель = Path(путь)
    цель.parent.mkdir(parents=True, exist_ok=True)

    if цель.exists():
        прежний = прочитать(цель)
        if прежний.site_id != артефакт.site_id:
            raise ArtifactError(
                f"{цель.name}: артефакт сайта {прежний.site_id}, "
                f"публикуется {артефакт.site_id}: чужое решение не подменяет своё")
        if артефакт.indexing_revision < прежний.indexing_revision:
            raise RevisionRegression(
                f"{артефакт.site_id}: публикуется ревизия "
                f"{артефакт.indexing_revision}, выложена {прежний.indexing_revision}. "
                "Старый релиз не откатывает решение владельца")
        if артефакт.indexing_revision == прежний.indexing_revision:
            if артефакт.state_digest != прежний.state_digest:
                raise ArtifactError(
                    f"{артефакт.site_id}: ревизия {артефакт.indexing_revision} с другим "
                    "отпечатком. Одно решение — один отпечаток")
            if not allow_same:
                raise ArtifactError(
                    f"{артефакт.site_id}: ревизия {артефакт.indexing_revision} уже выложена")
            return цель

    тело = артефакт.to_json()
    с_расширением = tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", dir=цель.parent, prefix=цель.name + ".", suffix=".tmp",
        delete=False)
    try:
        with с_расширением as fh:
            fh.write(тело)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(с_расширением.name, цель)
    except BaseException:
        Path(с_расширением.name).unlink(missing_ok=True)
        raise
    return цель


def сверить(артефакты: list[PolicyArtifact]) -> None:
    """Все поверхности одного сайта обязаны быть одной ревизии.

    Смешение ревизий означает, что часть страниц собрана по прежнему решению,
    а часть по новому. Отличить это от нормальной работы потом невозможно.
    """
    if not артефакты:
        return
    ревизии = {а.indexing_revision for а in артефакты}
    отпечатки = {а.state_digest for а in артефакты}
    if len(ревизии) > 1:
        raise ArtifactError(f"поверхности собраны из разных ревизий: {sorted(ревизии)}")
    if len(отпечатки) > 1:
        raise ArtifactError("одна ревизия с разными отпечатками")
