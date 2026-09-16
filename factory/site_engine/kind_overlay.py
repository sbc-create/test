"""Наложение редакторских решений о виде произведения.

Зачем отдельное хранилище, а не запись в каталог. Каталог поставщика
перезаписывается обновлением целиком — раз в десять минут приращением и раз в
шесть часов полным обходом. Решение, записанное прямо в него, исчезло бы при
следующем прогоне, и редактор разбирал бы один и тот же конфликт снова и снова.

Наложение читается при построении вида и побеждает конфликт: если по данным
поставщика вид установить нельзя, а редактор решил, действует решение
редактора. Обратное неверно — наложение не переопределяет непротиворечивые
данные источника: там, где поставщик сам себе не противоречит, редактору нечего
решать, и «исправление» означало бы подмену данных.

Хранится вид из контракта, а не произвольная строка: наложение — это выбор
между утверждениями источника, а не способ ввести третье значение.
"""

from __future__ import annotations

import dataclasses
import datetime as dt
import json
import os
from pathlib import Path
from typing import Any

CONTRACT_VERSION = "kind-overlay/1.0.0"
DEFAULT_REF = "var/state/kind-overlay"


@dataclasses.dataclass
class OverlayEntry:
    entity_id: str
    kind: str
    actor: str
    decided_at: str
    note: str = ""
    batch: str = ""

    def as_dict(self) -> dict[str, Any]:
        return {
            "entityId": self.entity_id,
            "kind": self.kind,
            "actor": self.actor,
            "decidedAt": self.decided_at,
            "note": self.note,
            "batch": self.batch,
            "contractVersion": CONTRACT_VERSION,
        }


class KindOverlay:
    """Решения редактора на диске. Одна запись — один файл."""

    def __init__(self, root: Path | str, *, subdir: str = DEFAULT_REF) -> None:
        self.dir = Path(root) / subdir
        self.dir.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _имя(entity_id: str) -> str:
        import hashlib

        if not entity_id:
            raise ValueError("пустой идентификатор сущности")
        # Имя файла — отпечаток: идентификатор сущности содержит двоеточие и
        # приходит снаружи, и класть его в путь как есть нельзя.
        return hashlib.sha256(entity_id.encode("utf-8")).hexdigest()[:32]

    def _путь(self, entity_id: str) -> Path:
        return self.dir / f"{self._имя(entity_id)}.json"

    def set(
        self, entity_id: str, *, kind: str, actor: str, note: str = "", batch: str = ""
    ) -> OverlayEntry:
        from factory.site_engine.content_kind import ContentKind

        try:
            вид = ContentKind(kind)
        except ValueError as ошибка:
            raise ValueError(
                f"вид {kind!r} вне контракта: наложение хранит выбор между "
                f"утверждениями источника, а не произвольную строку"
            ) from ошибка
        if вид is ContentKind.UNKNOWN:
            raise ValueError(
                "наложение с UNKNOWN бессмысленно: это и есть "
                "исходное состояние конфликтной записи"
            )
        запись = OverlayEntry(
            entity_id=entity_id,
            kind=вид.value,
            actor=actor,
            decided_at=dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            note=note,
            batch=batch,
        )
        путь = self._путь(entity_id)
        врем = путь.with_name(f".{путь.name}.tmp")
        врем.write_text(
            json.dumps(запись.as_dict(), ensure_ascii=False, indent=1), encoding="utf-8"
        )
        os.replace(врем, путь)
        return запись

    def get(self, entity_id: str) -> OverlayEntry | None:
        путь = self._путь(entity_id)
        if not путь.is_file():
            return None
        try:
            д = json.loads(путь.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None
        return OverlayEntry(
            entity_id=д.get("entityId", entity_id),
            kind=д.get("kind", ""),
            actor=д.get("actor", ""),
            decided_at=д.get("decidedAt", ""),
            note=д.get("note", ""),
            batch=д.get("batch", ""),
        )

    def kind_for(self, entity_id: str) -> str | None:
        запись = self.get(entity_id)
        return запись.kind if запись and запись.kind else None

    def unset(self, entity_id: str, *, actor: str = "") -> bool:
        путь = self._путь(entity_id)
        if not путь.is_file():
            return False
        путь.unlink()
        return True

    def list(self, *, batch: str = "") -> list[dict[str, Any]]:
        итог = []
        for файл in sorted(self.dir.glob("*.json")):
            try:
                д = json.loads(файл.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            if batch and д.get("batch") != batch:
                continue
            итог.append(д)
        return итог

    def count(self) -> int:
        return sum(1 for _ in self.dir.glob("*.json"))
