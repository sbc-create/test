"""Паспорт ячейки: куда именно адресована задача.

Реестр отвечает на один вопрос — «этот домен, этот site_id: какой репозиторий,
какой шаблон, какие закреплённые версии, какой сервер». Ошибка в этом ответе
дороже всех прочих: задача про поиск на одном домене, выполненная в соседнем
проекте, обнаруживается уже на живом сайте.

Поэтому разрешение имени здесь нарочито негибкое:

* совпадение только точное — ни по префиксу, ни по похожести;
* неоднозначность — отказ, а не выбор первого подходящего;
* отсутствие записи — отказ, а не создание записи на лету.

Реестр не заводит вторую правду о сайте. Идентичность (site_id, домены) живёт в
`config/site-profiles/*.json`; здесь добавлено только то, чего там нет:
репозиторий, закреплённые версии, цель выката и последний известный релиз.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from factory.cell import ledger
from factory.paths import PATHS

SCHEMA_VERSION = "1.0"
REGISTRY_PATH = "config/site-cells.json"

#: Идентификаторы издателя, отозванные поставщиком. Подставить такой в плеер
#: значит получить пустой плеер на живом сайте, поэтому запрет проверяется, а не
#: описывается в документации.
RETIRED_PUBLISHER_IDS = frozenset({"10331", "10332", "10333"})

SITE_ID_RE = re.compile(r"^[a-z][a-z0-9-]{1,62}$")
DOMAIN_RE = re.compile(r"^(?!-)[a-z0-9-]{1,63}(?<!-)(\.(?!-)[a-z0-9-]{1,63}(?<!-))+$")


class RegistryError(RuntimeError):
    pass


class UnknownCell(RegistryError):
    """Записи нет. Догадка по похожему имени здесь запрещена намеренно."""


class AmbiguousCell(RegistryError):
    """Под запрос подходит больше одной ячейки — значит останавливаемся."""


class RetiredPublisherId(RegistryError):
    pass


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def registry_path() -> Path:
    return PATHS.root / REGISTRY_PATH


@dataclass(frozen=True)
class Cell:
    """Паспорт одного сайта."""

    site_id: str
    domain: str
    aliases: tuple[str, ...]
    repo: dict[str, Any]
    template: dict[str, Any]
    pins: dict[str, Any]
    deploy_target: dict[str, Any]
    publisher: dict[str, Any]
    data: dict[str, Any]
    deployed: dict[str, Any] = field(default_factory=dict)
    content_revision: str | None = None
    last_update: str | None = None
    backup: dict[str, Any] = field(default_factory=dict)
    resources: dict[str, Any] = field(default_factory=dict)
    status: str = "planned"

    @property
    def domains(self) -> tuple[str, ...]:
        return (self.domain, *self.aliases)

    @property
    def repo_path(self) -> Path:
        path = self.repo.get("path")
        if not path:
            raise RegistryError(f"{self.site_id}: у ячейки не записан путь репозитория")
        p = Path(path)
        return p if p.is_absolute() else PATHS.root / p

    def to_dict(self) -> dict[str, Any]:
        return {
            "site_id": self.site_id,
            "domain": self.domain,
            "aliases": list(self.aliases),
            "status": self.status,
            "repo": dict(self.repo),
            "template": dict(self.template),
            "pins": dict(self.pins),
            "deploy_target": dict(self.deploy_target),
            "publisher": dict(self.publisher),
            "data": dict(self.data),
            "deployed": dict(self.deployed),
            "content_revision": self.content_revision,
            "last_update": self.last_update,
            "backup": dict(self.backup),
            "resources": dict(self.resources),
        }


def _cell(raw: dict[str, Any]) -> Cell:
    return Cell(
        site_id=raw["site_id"],
        domain=raw["domain"],
        aliases=tuple(raw.get("aliases") or ()),
        repo=raw.get("repo") or {},
        template=raw.get("template") or {},
        pins=raw.get("pins") or {},
        deploy_target=raw.get("deploy_target") or {},
        publisher=raw.get("publisher") or {},
        data=raw.get("data") or {},
        deployed=raw.get("deployed") or {},
        content_revision=raw.get("content_revision"),
        last_update=raw.get("last_update"),
        backup=raw.get("backup") or {},
        resources=raw.get("resources") or {},
        status=raw.get("status", "planned"),
    )


def load(path: Path | None = None) -> dict[str, Any]:
    target = path or registry_path()
    return ledger.read(target, default={"schema_version": SCHEMA_VERSION, "cells": []})


def all_cells(path: Path | None = None) -> tuple[Cell, ...]:
    return tuple(_cell(raw) for raw in load(path).get("cells", []))


def resolve(query: str, path: Path | None = None) -> Cell:
    """Ячейка по домену или site_id. Только точное совпадение.

    Отдельно ловится случай, когда запрос похож на существующую запись: сказать
    «не найдено» и промолчать о похожем — значит заставить человека угадывать,
    а подставить похожее — значит выполнить задачу не на том сайте.
    """
    if not query or not query.strip():
        raise RegistryError("пустой запрос к реестру ячеек")
    needle = query.strip().lower()
    cells = all_cells(path)
    matches = [c for c in cells
               if c.site_id.lower() == needle or needle in {d.lower() for d in c.domains}]
    if len(matches) == 1:
        return matches[0]
    if len(matches) > 1:
        raise AmbiguousCell(
            f"под «{query}» подходит несколько ячеек: "
            f"{sorted(c.site_id for c in matches)}; уточните site_id"
        )
    similar = sorted(
        c.site_id for c in cells
        if needle in c.site_id.lower() or any(needle in d.lower() for d in c.domains)
    )
    hint = f"; похожие записи: {similar} — выбирать за вас реестр не будет" if similar else ""
    raise UnknownCell(f"в реестре ячеек нет записи «{query}»{hint}")


def check_publisher_id(value: str) -> str:
    """Отозванный идентификатор издателя не проходит дальше этой функции."""
    cleaned = (value or "").strip()
    if not cleaned:
        raise RegistryError("publisher_id пуст: подставлять значение по умолчанию нельзя")
    if cleaned in RETIRED_PUBLISHER_IDS:
        raise RetiredPublisherId(
            f"publisher_id {cleaned} отозван поставщиком "
            f"(отозваны: {sorted(RETIRED_PUBLISHER_IDS)}); плеер с ним не заработает"
        )
    return cleaned


def register(cell: Cell, *, path: Path | None = None, replace: bool = False) -> Cell:
    """Записать паспорт ячейки.

    Домен принадлежит ровно одной ячейке: это то самое «один домен — один сайт»,
    и проверяется оно здесь, а не в обещании.
    """
    if not SITE_ID_RE.match(cell.site_id):
        raise RegistryError(f"недопустимый site_id: {cell.site_id!r}")
    for domain in cell.domains:
        if not DOMAIN_RE.match(domain):
            raise RegistryError(f"{cell.site_id}: недопустимый домен {domain!r}")
    publisher_id = (cell.publisher or {}).get("publisher_id")
    if publisher_id:
        check_publisher_id(str(publisher_id))

    target = path or registry_path()

    def change(data: dict[str, Any]) -> dict[str, Any]:
        cells = data.setdefault("cells", [])
        data.setdefault("schema_version", SCHEMA_VERSION)
        existing = [i for i, raw in enumerate(cells) if raw["site_id"] == cell.site_id]
        mine = {d.lower() for d in cell.domains}
        for i, raw in enumerate(cells):
            if i in existing:
                continue
            theirs = {raw["domain"].lower(), *(d.lower() for d in raw.get("aliases") or ())}
            clash = mine & theirs
            if clash:
                raise RegistryError(
                    f"домен(ы) {sorted(clash)} уже принадлежат ячейке {raw['site_id']}; "
                    "один домен — один сайт"
                )
        if existing:
            if not replace:
                raise RegistryError(
                    f"ячейка {cell.site_id} уже зарегистрирована; "
                    "для изменения используйте update() или replace=True"
                )
            cells[existing[0]] = cell.to_dict()
        else:
            cells.append(cell.to_dict())
        cells.sort(key=lambda raw: raw["site_id"])
        return data

    ledger.mutate(target, change, default={"schema_version": SCHEMA_VERSION, "cells": []})
    return cell


def update(site_id: str, changes: dict[str, Any], *, path: Path | None = None) -> Cell:
    """Точечно обновить поля паспорта: релиз, ревизию содержимого, бэкап."""
    target = path or registry_path()
    result: dict[str, Any] = {}
    allowed = {"status", "deployed", "content_revision", "last_update", "backup",
               "resources", "pins", "deploy_target", "repo", "data", "publisher",
               "template", "aliases"}
    unknown = set(changes) - allowed
    if unknown:
        raise RegistryError(f"эти поля паспорта не обновляются точечно: {sorted(unknown)}")
    if "publisher" in changes:
        pid = (changes["publisher"] or {}).get("publisher_id")
        if pid:
            check_publisher_id(str(pid))

    def change(data: dict[str, Any]) -> dict[str, Any]:
        for raw in data.get("cells", []):
            if raw["site_id"] != site_id:
                continue
            raw.update(changes)
            raw["last_update"] = changes.get("last_update") or utc_now()
            result["cell"] = raw
            return data
        raise UnknownCell(f"в реестре ячеек нет записи {site_id}")

    ledger.mutate(target, change, default={"schema_version": SCHEMA_VERSION, "cells": []})
    return _cell(result["cell"])


def route(query: str, path: Path | None = None) -> dict[str, Any]:
    """Маршрут задачи: куда её нести. Ровно то, что нужно исполнителю."""
    cell = resolve(query, path)
    return {
        "site_id": cell.site_id,
        "domain": cell.domain,
        "repo": cell.repo.get("path") or cell.repo.get("remote"),
        "template_id": cell.template.get("template_id"),
        "pins": cell.pins,
        "deploy_target": cell.deploy_target.get("ref"),
        "server": cell.deploy_target.get("server"),
        "deployed_digest": cell.deployed.get("release_digest"),
        "content_revision": cell.content_revision,
    }


def consistency_report(path: Path | None = None) -> list[str]:
    """Расхождения между реестром ячеек и профилями сайтов.

    Реестр не владеет идентичностью — он на неё ссылается. Если ссылка
    разъехалась с профилем, это должно быть видно отсюда, а не с домена.
    """
    problems: list[str] = []
    known: dict[str, set[str]] = {}

    # Профиль движка витрин есть не у каждого сайта: направления на DLE
    # описываются пакетом, а не профилем. Поэтому источников два, и отсутствие
    # одного из них расхождением не является — расхождением является
    # противоречие между ними.
    profiles_dir = PATHS.root / "config" / "site-profiles"
    for profile in sorted(profiles_dir.glob("*.json")):
        data = json.loads(profile.read_text(encoding="utf-8"))
        known.setdefault(data["site_id"], set()).update(data.get("domains") or ())

    for package in sorted(PATHS.sites.glob("*/package.yaml")):
        try:
            import yaml

            data = yaml.safe_load(package.read_text(encoding="utf-8")) or {}
        except Exception:  # noqa: BLE001 — нечитаемый пакет разбирает валидатор пакета
            continue
        site_id = data.get("site_id")
        domain = data.get("domain")
        if site_id and domain:
            known.setdefault(site_id, set()).add(domain)

    for cell in all_cells(path):
        declared = known.get(cell.site_id)
        if not declared:
            problems.append(
                f"{cell.site_id}: ни профиля, ни пакета сайта — реестр ссылается "
                "на сайт, которого фабрика не знает"
            )
            continue
        if cell.domain not in declared:
            problems.append(
                f"{cell.site_id}: реестр называет домен {cell.domain}, "
                f"источники идентичности — {sorted(declared)}"
            )
    return problems
