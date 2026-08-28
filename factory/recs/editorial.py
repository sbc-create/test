"""Редакторское управление витриной: закрепить, скрыть, поднять, заменить.

Полноценная админка — следующий этап; здесь заложены сам интерфейс и правила,
поверх которых её можно построить. Формат хранения — YAML с валидацией, чтобы
правку можно было прочитать глазами и провести через review.

Два ограничения заданы намеренно:

* у каждого решения есть срок. Закрепление без срока переживает повод, по
  которому его поставили, и через месяц никто уже не помнит, почему тайтл висит
  первым;
* редактор не может показать то, что не играет. Закрепление — это порядок
  показа, а не право обойти проверку доступности.

Слой не получает доступа ни к credentials плеера, ни к инфраструктурным
секретам: он оперирует только идентификаторами и позициями.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone

import yaml

from factory.recs.model import parse_time


@dataclass(frozen=True)
class Decision:
    kind: str
    content_id: str
    domain: str | None = None
    shelf: str | None = None
    position: int | None = None
    value: float | None = None
    replacement_id: str | None = None
    expires_at: datetime | None = None
    reason: str = ""
    author: str = ""

    def active(self, now: datetime) -> bool:
        return self.expires_at is None or self.expires_at > now


@dataclass
class Editorial:
    """Набор редакторских решений и журнал их применения."""

    decisions: list[Decision] = field(default_factory=list)
    audit_log: list[dict] = field(default_factory=list)

    # -- чтение состояния -------------------------------------------------
    def _match(self, kind: str, content_id: str, now: datetime,
               domain: str | None = None, shelf: str | None = None):
        for decision in self.decisions:
            if decision.kind != kind or decision.content_id != content_id:
                continue
            if not decision.active(now):
                continue
            if decision.domain and domain and decision.domain != domain:
                continue
            if decision.shelf and shelf and decision.shelf != shelf:
                continue
            yield decision

    def is_banned(self, content_id: str, now: datetime, *, domain=None, shelf=None) -> bool:
        return any(self._match("ban", content_id, now, domain, shelf))

    def boost_for(self, content_id: str, now: datetime, *, domain=None, shelf=None) -> float:
        return sum(d.value or 0.0 for d in self._match("boost", content_id, now, domain, shelf))

    def replacement_for(self, content_id: str, now: datetime) -> str | None:
        for decision in self._match("replace", content_id, now):
            return decision.replacement_id
        return None

    def pins(self, now: datetime, *, domain=None, shelf=None) -> list[Decision]:
        found = [d for d in self.decisions
                 if d.kind == "pin" and d.active(now)
                 and (not d.domain or not domain or d.domain == domain)
                 and (not d.shelf or not shelf or d.shelf == shelf)]
        return sorted(found, key=lambda d: (d.position or 10**6, d.content_id))

    # -- применение -------------------------------------------------------
    def apply_pins(self, scored: list, now: datetime, *, domain=None, shelf=None) -> list:
        """Ставит закреплённые записи на заданные позиции.

        Закрепление переставляет уже допущенные записи. Если закреплённой
        записи среди допущенных нет — например, у неё пропал поток, — она не
        появляется: редактор управляет порядком, а не проверкой доступности.
        """
        by_id = {s.item.content_id: s for s in scored}
        result = list(scored)
        for pin in self.pins(now, domain=domain, shelf=shelf):
            target = by_id.get(pin.content_id)
            if target is None:
                self.audit_log.append({
                    "action": "pin_skipped", "content_id": pin.content_id,
                    "reason": "не прошёл допуск на витрину", "at": now.isoformat(),
                })
                continue
            result.remove(target)
            index = max(0, (pin.position or 1) - 1)
            result.insert(min(index, len(result)), target)
            self.audit_log.append({
                "action": "pin_applied", "content_id": pin.content_id,
                "position": pin.position, "at": now.isoformat(),
            })
        return result

    # -- ввод/вывод -------------------------------------------------------
    @classmethod
    def from_documents(cls, documents) -> Editorial:
        decisions = []
        for raw in documents or []:
            if not isinstance(raw, dict):
                continue
            kind = str(raw.get("action") or raw.get("kind") or "").strip()
            content_id = str(raw.get("content_id") or "").strip()
            if kind not in {"pin", "ban", "boost", "replace"} or not content_id:
                raise ValueError(f"непонятное редакторское решение: {raw!r}")
            decisions.append(Decision(
                kind=kind,
                content_id=content_id,
                domain=raw.get("domain"),
                shelf=raw.get("shelf"),
                position=raw.get("position"),
                value=raw.get("value"),
                replacement_id=raw.get("replacement_id"),
                expires_at=parse_time(raw.get("expires_at")),
                reason=str(raw.get("reason") or ""),
                author=str(raw.get("author") or ""),
            ))
        return cls(decisions=decisions)

    @classmethod
    def load(cls, path) -> Editorial:
        from pathlib import Path
        text = Path(path).read_text(encoding="utf-8")
        return cls.from_documents(yaml.safe_load(text) or [])

    def preview(self, scored: list, now: datetime | None = None, *,
                domain=None, shelf=None) -> list[dict]:
        """Что увидит посетитель, если применить решения прямо сейчас."""
        now = now or datetime.now(timezone.utc)
        arranged = self.apply_pins(scored, now, domain=domain, shelf=shelf)
        return [{"position": index + 1, "content_id": s.item.content_id,
                 "title": s.item.title, "score": round(s.score, 4)}
                for index, s in enumerate(arranged)]
