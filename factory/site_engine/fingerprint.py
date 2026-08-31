"""Отпечаток входных данных рендера: решать до дорогой работы, а не после.

Нынешний сценарий считает идентификатор релиза от содержимого **уже собранной**
витрины. Поэтому цикл всегда платит полную цену — два с четвертью часа на
витрину, — и лишь потом узнаёт, менять ли что-нибудь. Отпечаток входа
переворачивает порядок: сравнение стоит секунды и делается первым.

Что входит, и почему именно это. Вывод HTML зависит не от одного каталога:
меняются шаблоны, версия рендерера, профиль сайта, состав полок, реестр
адресов, редакторские правки. Отпечаток, учитывающий один каталог, скрыл бы
правку шаблона — и витрина осталась бы со старой вёрсткой, а прогон отчитался
бы, что менять нечего. Это опаснее лишнего рендера.

Отпечаток детерминирован и не зависит ни от порядка полей JSON, ни от порядка
записей в каталоге: всё нормализуется перед подсчётом.
"""
from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "1.0"

#: Части отпечатка. Список закрыт: молча добавленная часть меняет все отпечатки
#: разом и заставляет пересобрать всё, а молча забытая — прячет изменение.
PARTS = (
    "catalog",
    "renderer_version",
    "template_version",
    "site_profile",
    "shelf_configuration",
    "route_registry",
    "schema_version",
    "seo_contract_version",
    "editorial_overrides",
    "assets",
)


def _stable(value: Any) -> str:
    """Каноническое представление: порядок ключей и пробелы не влияют."""
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def digest(value: Any) -> str:
    return hashlib.sha256(_stable(value).encode("utf-8")).hexdigest()


def catalog_digest(entries: Iterable[dict], *, fields: tuple[str, ...] | None = None) -> str:
    """Отпечаток каталога, не зависящий от порядка записей.

    Берутся только поля, влияющие на HTML. Служебные метки вроде времени
    выборки в отпечаток не входят: иначе он менялся бы каждый прогон и обесценил
    бы всю проверку.
    """
    fields = fields or (
        "external_id", "name", "original_name", "year", "type", "is_series",
        "genres", "countries", "tags", "poster_url", "playback", "licensed",
        "kinopoisk_rating", "imdb_rating", "external_ids", "seasons",
        "episodes_count", "available_episodes_count", "updated_at",
    )
    записи = sorted(
        (_stable({f: e.get(f) for f in fields if f in e}) for e in entries),
    )
    h = hashlib.sha256()
    for запись in записи:
        h.update(запись.encode("utf-8"))
        h.update(b"\n")
    return h.hexdigest()


def tree_digest(root: Path, patterns: tuple[str, ...] = ("*",)) -> str:
    """Отпечаток дерева файлов: имена и содержимое, без времён и прав.

    Время изменения намеренно не учитывается: скопированный файл с новой меткой
    времени — это тот же файл, и заставлять из-за него пересобирать витрину
    незачем.
    """
    if not root.exists():
        return digest(None)
    файлы: list[tuple[str, str]] = []
    for pattern in patterns:
        for path in sorted(root.rglob(pattern)):
            if path.is_file():
                отн = path.relative_to(root).as_posix()
                файлы.append((отн, hashlib.sha256(path.read_bytes()).hexdigest()))
    return digest(sorted(set(файлы)))


@dataclass(frozen=True)
class RenderInputs:
    """Всё, от чего зависит вывод. Ничего сверх того."""

    catalog: str
    renderer_version: str
    template_version: str
    site_profile: str
    shelf_configuration: str
    route_registry: str
    schema_version: str = SCHEMA_VERSION
    seo_contract_version: str = "1.0"
    editorial_overrides: str = ""
    assets: str = ""

    def as_dict(self) -> dict[str, str]:
        return {part: getattr(self, part) for part in PARTS}

    def fingerprint(self) -> str:
        return digest(self.as_dict())


@dataclass
class FingerprintDiff:
    """Чем именно отличаются два отпечатка.

    Знать, что «что-то изменилось», недостаточно: от того, какая часть
    изменилась, зависит объём пересборки. Правка одного тайтла и правка шаблона
    требуют разного.
    """

    changed: tuple[str, ...] = ()
    previous: dict[str, str] = field(default_factory=dict)
    current: dict[str, str] = field(default_factory=dict)

    @property
    def any_change(self) -> bool:
        return bool(self.changed)

    @property
    def needs_full_rebuild(self) -> bool:
        """Полная пересборка оправдана только при общих изменениях.

        Шаблон, версия рендерера, схема, профиль сайта и состав полок влияют на
        каждую страницу. Каталог и реестр адресов — нет: их изменения
        отрабатывает инкрементальный путь.
        """
        общие = {
            "renderer_version", "template_version", "schema_version",
            "site_profile", "shelf_configuration", "seo_contract_version",
        }
        return bool(общие & set(self.changed))

    def describe(self) -> str:
        if not self.changed:
            return "ничего не изменилось"
        return "изменилось: " + ", ".join(self.changed)


def compare(previous: RenderInputs | None, current: RenderInputs) -> FingerprintDiff:
    if previous is None:
        # Первый прогон: сравнивать не с чем, и это не «всё изменилось», а
        # «неизвестно». Полная сборка нужна, но причину надо назвать честно.
        return FingerprintDiff(changed=tuple(PARTS), previous={}, current=current.as_dict())
    было, стало = previous.as_dict(), current.as_dict()
    изменилось = tuple(part for part in PARTS if было.get(part) != стало.get(part))
    return FingerprintDiff(changed=изменилось, previous=было, current=стало)


def load(path: Path) -> RenderInputs | None:
    if not path.exists():
        return None
    raw = json.loads(path.read_text(encoding="utf-8"))
    if raw.get("schema_version") != SCHEMA_VERSION:
        # Смена версии схемы отпечатка — законный повод пересобрать всё, но об
        # этом надо сказать, а не сделать вид, что ничего не было.
        return None
    return RenderInputs(**{k: raw[k] for k in PARTS if k in raw})


def save(path: Path, inputs: RenderInputs) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = inputs.as_dict() | {"fingerprint": inputs.fingerprint()}
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    tmp.replace(path)
    return path
