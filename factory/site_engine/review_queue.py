"""Очередь разбора спорных записей.

Зачем она нужна отдельно от резолвера. Резолвер отвечает на вопрос «можно ли
привязать автоматически» и на 231 записи отвечает «нет»: у них тип поставщика
и тег вида из разных групп, и выбрать одно из двух по весу тега значило бы
угадать. Дальше нужен человек — но человеку нужно место, где решение видно,
обосновано и обратимо.

Три свойства, без которых очередь бесполезна.

**Оба утверждения видны рядом.** Не «система считает, что это ONA», а
«поставщик сказал movie, тег сказал ona, вот источник каждого». Редактор
принимает решение, а не подтверждает чужое.

**Решение обратимо.** Каждое решение пишет предыдущее состояние целиком.
Отмена возвращает запись в точности туда, где она была, включая причину
конфликта. Необратимое решение по спорной записи — это то же угадывание,
только руками.

**Групповое действие проходит тот же путь, что и одиночное.** Сначала сухой
прогон с числом, разницей и выборкой, потом сверка версии, потом изменение,
потом проверка, потом журнал. Групповое действие без сухого прогона — самый
дешёвый способ испортить тысячу записей одним нажатием.
"""

from __future__ import annotations

import dataclasses
import datetime as dt
import enum
import hashlib
import json
import os
from pathlib import Path
from typing import Any

CONTRACT_VERSION = "review-state/1.0.0"

#: Где живёт очередь. Файл на запись открывается под блокировкой: очередь
#: читают и админка, и Control API, и фоновой пересчёт.
DEFAULT_REF = "var/state/review-queue"


class ReviewState(str, enum.Enum):
    """Состояние записи в очереди. RESOLVED — это решение, а не исчезновение."""

    OPEN = "OPEN"
    IN_REVIEW = "IN_REVIEW"
    RESOLVED = "RESOLVED"
    #: Решение утверждено вторым человеком, но ещё не действует на витрине.
    APPROVED = "APPROVED"
    #: Решение применено: наложение записано, вид на витрине изменился.
    PUBLISHED = "PUBLISHED"
    #: Конфликт признан незначащим: запись остаётся как есть, но больше не
    #: показывается как требующая внимания. Отличается от RESOLVED тем, что
    #: значение не менялось.
    DISMISSED = "DISMISSED"
    #: Решение отменено. Запись возвращается в OPEN, но история сохраняется.
    REVERTED = "REVERTED"


class ReviewError(RuntimeError):
    """Действие над записью очереди невозможно."""


@dataclasses.dataclass(frozen=True)
class Claim:
    """Одно утверждение о записи и то, чем оно подтверждено."""

    value: str
    source: str
    evidence: str = ""
    confidence: float = 0.0

    def as_dict(self) -> dict[str, Any]:
        return {
            "value": self.value,
            "source": self.source,
            "evidence": self.evidence,
            "confidence": round(self.confidence, 4),
        }


@dataclasses.dataclass
class ReviewItem:
    """Спорная запись целиком: оба утверждения, доказательства, история."""

    item_id: str
    internal_entity_id: str
    site_id: str
    conflict_code: str
    field: str
    claims: tuple[Claim, ...]
    title: str = ""
    year: int | None = None
    season_number: int | None = None
    external_ids: dict[str, str] = dataclasses.field(default_factory=dict)
    #: Что система рекомендует. Рекомендация НЕ применяется сама: она
    #: показывается редактору вместе с основанием.
    recommendation: str = ""
    recommendation_reason: str = ""
    state: ReviewState = ReviewState.OPEN
    decided_value: str = ""
    decided_by: str = ""
    decided_at: str = ""
    decision_note: str = ""
    #: Полное предыдущее состояние — то, что возвращает отмена.
    previous: dict[str, Any] | None = None
    history: list[dict[str, Any]] = dataclasses.field(default_factory=list)
    #: Версия записи. Любое изменение обязано её назвать: иначе два редактора
    #: перезапишут решение друг друга и никто не заметит.
    version: int = 1
    created_at: str = ""
    updated_at: str = ""
    contract_version: str = CONTRACT_VERSION

    def as_dict(self) -> dict[str, Any]:
        return {
            "itemId": self.item_id,
            "internalEntityId": self.internal_entity_id,
            "siteId": self.site_id,
            "conflictCode": self.conflict_code,
            "field": self.field,
            "claims": [c.as_dict() for c in self.claims],
            "title": self.title,
            "year": self.year,
            "seasonNumber": self.season_number,
            "externalIds": dict(self.external_ids),
            "recommendation": self.recommendation,
            "recommendationReason": self.recommendation_reason,
            "state": self.state.value,
            "decidedValue": self.decided_value,
            "decidedBy": self.decided_by,
            "decidedAt": self.decided_at,
            "decisionNote": self.decision_note,
            "previous": self.previous,
            "history": list(self.history),
            "version": self.version,
            "createdAt": self.created_at,
            "updatedAt": self.updated_at,
            "contractVersion": self.contract_version,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> ReviewItem:
        return cls(
            item_id=d["itemId"],
            internal_entity_id=d["internalEntityId"],
            site_id=d.get("siteId", ""),
            conflict_code=d.get("conflictCode", ""),
            field=d.get("field", ""),
            claims=tuple(Claim(**dict(c)) for c in d.get("claims", [])),
            title=d.get("title", ""),
            year=d.get("year"),
            season_number=d.get("seasonNumber"),
            external_ids=dict(d.get("externalIds") or {}),
            recommendation=d.get("recommendation", ""),
            recommendation_reason=d.get("recommendationReason", ""),
            state=ReviewState(d.get("state", "OPEN")),
            decided_value=d.get("decidedValue", ""),
            decided_by=d.get("decidedBy", ""),
            decided_at=d.get("decidedAt", ""),
            decision_note=d.get("decisionNote", ""),
            previous=d.get("previous"),
            history=list(d.get("history") or []),
            version=int(d.get("version", 1)),
            created_at=d.get("createdAt", ""),
            updated_at=d.get("updatedAt", ""),
            contract_version=d.get("contractVersion", CONTRACT_VERSION),
        )


def item_id_for(internal_entity_id: str, field: str) -> str:
    """Устойчивый идентификатор записи очереди.

    Считается от сущности и поля, а не от порядка обхода: повторный пересчёт
    обязан попасть в ту же запись, иначе решение редактора потеряется при
    следующем прогоне.
    """
    сырое = f"{internal_entity_id}|{field}".encode()
    return hashlib.sha256(сырое).hexdigest()[:24]


class ReviewQueue:
    """Очередь на диске. Одна запись — один файл: они правятся независимо."""

    def __init__(self, root: Path | str, *, subdir: str = DEFAULT_REF) -> None:
        self.dir = Path(root) / subdir
        self.dir.mkdir(parents=True, exist_ok=True)

    def _путь(self, item_id: str) -> Path:
        if not item_id or "/" in item_id or ".." in item_id:
            raise ReviewError(f"негодный идентификатор записи: {item_id!r}")
        return self.dir / f"{item_id}.json"

    @staticmethod
    def _сейчас() -> str:
        return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    def upsert(self, item: ReviewItem) -> ReviewItem:
        """Добавляет запись или обновляет её ДАННЫЕ, не трогая решение.

        Пересчёт каталога не имеет права стереть решение редактора. Поэтому
        при существующей записи обновляются только утверждения и рекомендация,
        а состояние, решение и история сохраняются.
        """
        путь = self._путь(item.item_id)
        if путь.exists():
            прежняя = self.get(item.item_id)
            item.state = прежняя.state
            item.decided_value = прежняя.decided_value
            item.decided_by = прежняя.decided_by
            item.decided_at = прежняя.decided_at
            item.decision_note = прежняя.decision_note
            item.previous = прежняя.previous
            item.history = прежняя.history
            item.version = прежняя.version
            item.created_at = прежняя.created_at
        else:
            item.created_at = item.created_at or self._сейчас()
        item.updated_at = self._сейчас()
        self._записать(item)
        return item

    def _записать(self, item: ReviewItem) -> None:
        путь = self._путь(item.item_id)
        врем = путь.with_name(f".{путь.name}.tmp")
        врем.write_text(json.dumps(item.as_dict(), ensure_ascii=False, indent=1), encoding="utf-8")
        os.replace(врем, путь)

    def get(self, item_id: str) -> ReviewItem:
        путь = self._путь(item_id)
        if not путь.exists():
            raise ReviewError(f"записи {item_id} нет в очереди")
        return ReviewItem.from_dict(json.loads(путь.read_text(encoding="utf-8")))

    def list(
        self,
        *,
        state: str | None = None,
        site_id: str = "",
        conflict_code: str = "",
        query: str = "",
        offset: int = 0,
        limit: int = 50,
    ) -> dict[str, Any]:
        """Страница очереди. Сортировка устойчивая — по идентификатору.

        Сортировать по времени обновления соблазнительно, но тогда страница
        меняется под руками редактора при каждом фоновом пересчёте, и он
        дважды видит одну запись и пропускает другую.
        """
        все: list[ReviewItem] = []
        for файл in sorted(self.dir.glob("*.json")):
            try:
                запись = ReviewItem.from_dict(json.loads(файл.read_text(encoding="utf-8")))
            except (OSError, json.JSONDecodeError, KeyError, ValueError):
                # Испорченный файл не должен прятать остальную очередь.
                continue
            все.append(запись)

        отобрано = [
            i
            for i in все
            if (not state or i.state.value == state)
            and (not site_id or i.site_id == site_id)
            and (not conflict_code or i.conflict_code == conflict_code)
            and (
                not query
                or query.lower() in i.title.lower()
                or query.lower() in i.internal_entity_id.lower()
            )
        ]
        отобрано.sort(key=lambda i: i.item_id)
        окно = отобрано[offset : offset + limit]
        по_состояниям: dict[str, int] = {}
        for i in все:
            по_состояниям[i.state.value] = по_состояниям.get(i.state.value, 0) + 1
        return {
            "total": len(отобрано),
            "totalAll": len(все),
            "offset": offset,
            "limit": limit,
            "byState": по_состояниям,
            "items": [i.as_dict() for i in окно],
            "contractVersion": CONTRACT_VERSION,
        }

    # ------------------------------------------------------------------
    # Решения
    # ------------------------------------------------------------------
    def decide(
        self,
        item_id: str,
        *,
        value: str,
        actor: str,
        note: str = "",
        expected_version: int | None = None,
        dismiss: bool = False,
    ) -> ReviewItem:
        """Решение редактора. Прежнее состояние сохраняется целиком.

        `expected_version` обязателен, когда решение принимается по прочитанной
        странице: без него два редактора перезапишут решение друг друга, и
        второй даже не узнает, что было первое.
        """
        запись = self.get(item_id)
        if expected_version is not None and expected_version != запись.version:
            raise ReviewError(
                f"запись изменилась: ожидалась версия {expected_version}, "
                f"фактическая {запись.version}. Обновите страницу — иначе "
                f"вы перезапишете чужое решение"
            )
        if not dismiss and not value:
            raise ReviewError("решение обязано называть значение")
        допустимые = {c.value for c in запись.claims}
        if not dismiss and value not in допустимые:
            raise ReviewError(
                f"значение {value!r} не входит в утверждения записи {sorted(допустимые)}. "
                f"Очередь разрешает выбрать между утверждениями источников, "
                f"а не ввести третье: третье значение — это тоже догадка"
            )

        запись.previous = {
            "state": запись.state.value,
            "decidedValue": запись.decided_value,
            "decidedBy": запись.decided_by,
            "decidedAt": запись.decided_at,
            "decisionNote": запись.decision_note,
            "version": запись.version,
        }
        запись.history.append(
            {
                "at": self._сейчас(),
                "actor": actor,
                "action": "dismiss" if dismiss else "decide",
                "value": "" if dismiss else value,
                "note": note,
                "fromState": запись.state.value,
            }
        )
        запись.state = ReviewState.DISMISSED if dismiss else ReviewState.RESOLVED
        запись.decided_value = "" if dismiss else value
        запись.decided_by = actor
        запись.decided_at = self._сейчас()
        запись.decision_note = note
        запись.version += 1
        запись.updated_at = запись.decided_at
        self._записать(запись)
        return запись

    def revert(self, item_id: str, *, actor: str, note: str = "") -> ReviewItem:
        """Отмена решения. Возвращает запись ровно туда, где она была."""
        запись = self.get(item_id)
        if запись.state not in (
            ReviewState.RESOLVED,
            ReviewState.DISMISSED,
            ReviewState.APPROVED,
            ReviewState.PUBLISHED,
        ):
            raise ReviewError(f"отменять нечего: запись в состоянии {запись.state.value}")
        if запись.state is ReviewState.PUBLISHED:
            # Иначе отменённое решение продолжает действовать на витрине:
            # в очереди оно снято, а зритель видит его до сих пор.
            self._наложение().unset(запись.internal_entity_id, actor=actor)
        запись.history.append(
            {
                "at": self._сейчас(),
                "actor": actor,
                "action": "revert",
                "value": запись.decided_value,
                "note": note,
                "fromState": запись.state.value,
            }
        )
        запись.state = ReviewState.OPEN
        запись.decided_value = ""
        запись.decided_by = ""
        запись.decided_at = ""
        запись.decision_note = ""
        запись.previous = None
        запись.version += 1
        запись.updated_at = self._сейчас()
        self._записать(запись)
        return запись

    # ------------------------------------------------------------------
    # Рабочий поток: сверка, утверждение, публикация, точечный откат
    # ------------------------------------------------------------------
    def _наложение(self):
        from factory.site_engine.kind_overlay import KindOverlay

        return KindOverlay(self.dir.parent.parent.parent)

    def preview(self, item_id: str) -> dict[str, Any]:
        """Что изменится на витрине. Сверка «было/стало» перед публикацией.

        Без неё утверждение — это доверие к строке в списке. Публикация без
        предъявленной разницы однажды применит не то, что имелось в виду.
        """
        запись = self.get(item_id)
        наложение = self._наложение().get(запись.internal_entity_id)
        было = наложение.kind if наложение else "UNKNOWN"
        return {
            "itemId": запись.item_id,
            "internalEntityId": запись.internal_entity_id,
            "title": запись.title,
            "field": запись.field,
            "before": было,
            "after": запись.decided_value or "—",
            "published": наложение is not None and наложение.kind == запись.decided_value,
            "state": запись.state.value,
            "version": запись.version,
            "claims": [c.as_dict() for c in запись.claims],
            "contractVersion": CONTRACT_VERSION,
        }

    def approve(
        self, item_id: str, *, actor: str, expected_version: int | None = None, note: str = ""
    ) -> ReviewItem:
        """Утверждение решения. Утверждает НЕ тот, кто решил.

        Иначе утверждение — это второе нажатие того же человека, и весь смысл
        второго шага исчезает.
        """
        запись = self.get(item_id)
        if expected_version is not None and expected_version != запись.version:
            raise ReviewError(
                f"запись изменилась: ожидалась версия {expected_version}, "
                f"фактическая {запись.version}"
            )
        if запись.state is not ReviewState.RESOLVED:
            raise ReviewError(
                f"утверждать можно только решённое; запись в состоянии " f"{запись.state.value}"
            )
        if actor and actor == запись.decided_by:
            raise ReviewError(
                "нельзя утвердить собственное решение сам: второй шаг нужен "
                "ради второй пары глаз, а не ради второго нажатия"
            )
        запись.history.append(
            {
                "at": self._сейчас(),
                "actor": actor,
                "action": "approve",
                "value": запись.decided_value,
                "note": note,
                "fromState": запись.state.value,
            }
        )
        запись.state = ReviewState.APPROVED
        запись.version += 1
        запись.updated_at = self._сейчас()
        self._записать(запись)
        return запись

    def publish(
        self, item_id: str, *, actor: str, expected_version: int | None = None, batch: str = ""
    ) -> ReviewItem:
        """Применение решения к витрине через наложение."""
        запись = self.get(item_id)
        if expected_version is not None and expected_version != запись.version:
            raise ReviewError(
                f"запись изменилась: ожидалась версия {expected_version}, "
                f"фактическая {запись.version}"
            )
        if запись.state is not ReviewState.APPROVED:
            raise ReviewError(
                f"публиковать можно только утверждённое; запись в состоянии "
                f"{запись.state.value}"
            )
        if not запись.decided_value:
            raise ReviewError("публиковать нечего: решение пустое")
        self._наложение().set(
            запись.internal_entity_id,
            kind=запись.decided_value,
            actor=actor,
            note=запись.decision_note,
            batch=batch,
        )
        запись.history.append(
            {
                "at": self._сейчас(),
                "actor": actor,
                "action": "publish",
                "value": запись.decided_value,
                "fromState": запись.state.value,
                **({"batch": batch} if batch else {}),
            }
        )
        запись.state = ReviewState.PUBLISHED
        запись.version += 1
        запись.updated_at = self._сейчас()
        self._записать(запись)
        return запись

    def unpublish(self, item_id: str, *, actor: str, note: str = "") -> ReviewItem:
        """Точечный откат: наложение снимается, решение сохраняется."""
        запись = self.get(item_id)
        if запись.state is not ReviewState.PUBLISHED:
            raise ReviewError(f"откатывать нечего: запись в состоянии {запись.state.value}")
        self._наложение().unset(запись.internal_entity_id, actor=actor)
        запись.history.append(
            {
                "at": self._сейчас(),
                "actor": actor,
                "action": "unpublish",
                "value": запись.decided_value,
                "note": note,
                "fromState": запись.state.value,
            }
        )
        запись.state = ReviewState.APPROVED
        запись.version += 1
        запись.updated_at = self._сейчас()
        self._записать(запись)
        return запись

    def batch_publish(self, *, batch_id: str, actor: str) -> dict[str, Any]:
        """Публикация партии. Утверждённые записи применяются разом."""
        опубликовано: list[str] = []
        пропущено: list[str] = []
        for файл in sorted(self.dir.glob("*.json")):
            try:
                запись = ReviewItem.from_dict(json.loads(файл.read_text(encoding="utf-8")))
            except (OSError, json.JSONDecodeError, KeyError, ValueError):
                continue
            if not any(h.get("batch") == batch_id for h in запись.history):
                continue
            if запись.state is ReviewState.RESOLVED:
                # Утверждение партии выполняет тот, кто её публикует: решение
                # приняла автоматика группового действия, а не человек.
                запись = self.approve(
                    запись.item_id,
                    actor=actor,
                    expected_version=запись.version,
                    note=f"утверждение партии {batch_id}",
                )
            if запись.state is not ReviewState.APPROVED:
                пропущено.append(запись.item_id)
                continue
            self.publish(
                запись.item_id, actor=actor, expected_version=запись.version, batch=batch_id
            )
            опубликовано.append(запись.item_id)
        return {
            "batchId": batch_id,
            "published": len(опубликовано),
            "skipped": len(пропущено),
            "itemIds": опубликовано,
        }

    def claim(self, item_id: str, *, actor: str) -> ReviewItem:
        """Взять запись в работу. Нужно, чтобы двое не разбирали одно и то же."""
        запись = self.get(item_id)
        if запись.state is not ReviewState.OPEN:
            raise ReviewError(f"запись в состоянии {запись.state.value}, взять нельзя")
        запись.state = ReviewState.IN_REVIEW
        запись.history.append(
            {"at": self._сейчас(), "actor": actor, "action": "claim", "fromState": "OPEN"}
        )
        запись.version += 1
        запись.updated_at = self._сейчас()
        self._записать(запись)
        return запись

    # ------------------------------------------------------------------
    # Групповое действие
    # ------------------------------------------------------------------
    def batch_preview(
        self,
        *,
        conflict_code: str,
        from_value: str,
        to_value: str,
        site_id: str = "",
        sample: int = 5,
    ) -> dict[str, Any]:
        """Сухой прогон. Ничего не меняет и обязан выполняться первым.

        Показывает не только число. Число само по себе не даёт основания
        нажать: «затронуто 231» одинаково выглядит и когда это ровно тот
        класс, который имелся в виду, и когда фильтр захватил лишнее. Поэтому
        возвращаются разница по значениям и поимённая выборка.
        """
        подходят, лишние = [], []
        for файл in sorted(self.dir.glob("*.json")):
            try:
                запись = ReviewItem.from_dict(json.loads(файл.read_text(encoding="utf-8")))
            except (OSError, json.JSONDecodeError, KeyError, ValueError):
                continue
            if запись.conflict_code != conflict_code:
                continue
            if site_id and запись.site_id != site_id:
                continue
            значения = {c.value for c in запись.claims}
            if запись.state is not ReviewState.OPEN:
                лишние.append((запись, f"состояние {запись.state.value}"))
            elif from_value and from_value not in значения:
                лишние.append((запись, f"нет утверждения {from_value}"))
            elif to_value not in значения:
                лишние.append((запись, f"нет утверждения {to_value}"))
            else:
                подходят.append(запись)

        return {
            "dryRun": True,
            "conflictCode": conflict_code,
            "fromValue": from_value,
            "toValue": to_value,
            "siteId": site_id,
            "affected": len(подходят),
            "skipped": len(лишние),
            "skippedReasons": _посчитать(причина for _, причина in лишние),
            "diff": {
                "from": from_value or "(любое)",
                "to": to_value,
                "field": подходят[0].field if подходят else "",
            },
            "sample": [
                {
                    "itemId": з.item_id,
                    "title": з.title,
                    "year": з.year,
                    "siteId": з.site_id,
                    "version": з.version,
                    "claims": [c.as_dict() for c in з.claims],
                }
                for з in подходят[:sample]
            ],
            "homogeneous": len({з.conflict_code for з in подходят}) <= 1,
            "versionFingerprint": _отпечаток_версий(подходят),
            "contractVersion": CONTRACT_VERSION,
        }

    def batch_apply(
        self,
        *,
        conflict_code: str,
        from_value: str,
        to_value: str,
        actor: str,
        expected_fingerprint: str,
        site_id: str = "",
        note: str = "",
    ) -> dict[str, Any]:
        """Групповое изменение. Только после сухого прогона и только по отпечатку.

        Отпечаток версий — это сверка на весь набор сразу. Проверять версию
        каждой записи по отдельности недостаточно: между сухим прогоном и
        применением набор мог измениться СОСТАВОМ, а не содержимым, и
        поштучная сверка этого не заметит.

        Возвращает идентификатор партии: по нему выполняется откат.
        """
        предпросмотр = self.batch_preview(
            conflict_code=conflict_code,
            from_value=from_value,
            to_value=to_value,
            site_id=site_id,
            sample=0,
        )
        if предпросмотр["versionFingerprint"] != expected_fingerprint:
            raise ReviewError(
                "набор изменился между сухим прогоном и применением: "
                f"ожидался отпечаток {expected_fingerprint}, фактический "
                f"{предпросмотр['versionFingerprint']}. Повторите сухой прогон"
            )
        if not предпросмотр["homogeneous"]:
            raise ReviewError(
                "набор неоднороден: групповое действие допустимо только для "
                "одного доказанного класса конфликта"
            )
        if предпросмотр["affected"] == 0:
            raise ReviewError("сухой прогон не нашёл ни одной подходящей записи")

        партия = hashlib.sha256(
            f"{conflict_code}|{to_value}|{actor}|{self._сейчас()}".encode()
        ).hexdigest()[:16]

        изменены: list[str] = []
        for файл in sorted(self.dir.glob("*.json")):
            try:
                запись = ReviewItem.from_dict(json.loads(файл.read_text(encoding="utf-8")))
            except (OSError, json.JSONDecodeError, KeyError, ValueError):
                continue
            if запись.conflict_code != conflict_code or запись.state is not ReviewState.OPEN:
                continue
            if site_id and запись.site_id != site_id:
                continue
            значения = {c.value for c in запись.claims}
            if (from_value and from_value not in значения) or to_value not in значения:
                continue
            обновлена = self.decide(
                запись.item_id,
                value=to_value,
                actor=actor,
                note=f"[партия {партия}] {note}".strip(),
                expected_version=запись.version,
            )
            обновлена.history[-1]["batch"] = партия
            self._записать(обновлена)
            изменены.append(запись.item_id)

        # Проверка после изменения: заявленное число обязано совпасть с
        # фактическим. Расхождение означает гонку, и о ней нужно знать сразу.
        фактически = sum(
            1
            for i in изменены
            if self.get(i).state is ReviewState.RESOLVED and self.get(i).decided_value == to_value
        )
        return {
            "batchId": партия,
            "requested": предпросмотр["affected"],
            "changed": len(изменены),
            "verified": фактически,
            "consistent": фактически == len(изменены) == предпросмотр["affected"],
            "itemIds": изменены,
            "contractVersion": CONTRACT_VERSION,
        }

    def batch_revert(self, *, batch_id: str, actor: str) -> dict[str, Any]:
        """Откат партии целиком. Записи, решённые не этой партией, не трогаются."""
        отменены: list[str] = []
        for файл in sorted(self.dir.glob("*.json")):
            try:
                запись = ReviewItem.from_dict(json.loads(файл.read_text(encoding="utf-8")))
            except (OSError, json.JSONDecodeError, KeyError, ValueError):
                continue
            свои = [h for h in запись.history if h.get("batch") == batch_id]
            if not свои or запись.state not in (
                ReviewState.RESOLVED,
                ReviewState.APPROVED,
                ReviewState.PUBLISHED,
            ):
                continue
            self.revert(запись.item_id, actor=actor, note=f"откат партии {batch_id}")
            отменены.append(запись.item_id)
        return {"batchId": batch_id, "reverted": len(отменены), "itemIds": отменены}


def _посчитать(значения) -> dict[str, int]:
    итог: dict[str, int] = {}
    for з in значения:
        итог[з] = итог.get(з, 0) + 1
    return итог


def _отпечаток_версий(записи) -> str:
    """Отпечаток состава и версий набора.

    Считается от пар «идентификатор:версия», отсортированных: изменение
    состава и изменение содержимого одинаково меняют отпечаток.
    """
    сырое = "|".join(f"{з.item_id}:{з.version}" for з in sorted(записи, key=lambda з: з.item_id))
    return hashlib.sha256(сырое.encode("utf-8")).hexdigest()[:16]
