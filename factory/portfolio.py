"""Направления портфеля: Amedia, Yami, Lords.

Реестр объявляет направления, пакет сайта объявляет своё направление полем
`portfolio`. Списка членства в реестре нет намеренно: два списка одного и того
же разошлись бы молча, и вопрос «где правда» решался бы каждый раз заново.

Направление задаёт общий blueprint и общую секретную область. Секреты сайтов
одного направления лежат в одной области, секреты разных направлений — в
разных, поэтому утечка токена одного направления не открывает другое.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml

from factory.paths import PATHS

REGISTRY = "inventory/portfolios.yaml"


#: Состояние сайта, направление которого владелец ещё не называл.
LEGACY_UNCLASSIFIED = "legacy/unclassified"


@dataclass(frozen=True)
class Portfolio:
    id: str
    label: str
    purpose: str
    secret_scope: str
    blueprint: str
    status: str = "registered"
    note: str = ""
    application_repository: str | None = None

    def secret_ref(self, name: str) -> str:
        """Ссылка на секрет направления. Значение секрета здесь не появляется."""
        return f"secret://{self.secret_scope}/{name}"


def registry_path(root: Path | None = None) -> Path:
    return (Path(root) if root else PATHS.root) / REGISTRY


def load(root: Path | None = None) -> dict[str, Portfolio]:
    """Направления по id. Отсутствие реестра — ошибка, а не пустой портфель."""
    path = registry_path(root)
    if not path.exists():
        raise FileNotFoundError(f"реестр направлений не найден: {path}")
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    out: dict[str, Portfolio] = {}
    for entry in data.get("portfolios") or []:
        missing = [k for k in ("id", "label", "secret_scope", "blueprint") if not entry.get(k)]
        if missing:
            raise ValueError(f"запись реестра без обязательных полей {missing}: {entry}")
        portfolio = Portfolio(
            id=entry["id"],
            label=entry["label"],
            purpose=entry.get("purpose", ""),
            secret_scope=entry["secret_scope"],
            blueprint=entry["blueprint"],
            status=entry.get("status", "registered"),
            note=entry.get("note", ""),
            application_repository=entry.get("application_repository"),
        )
        if portfolio.id in out:
            raise ValueError(f"направление {portfolio.id} объявлено дважды")
        out[portfolio.id] = portfolio
    return out


def of(package: dict, root: Path | None = None) -> Portfolio | None:
    """Направление пакета. None — направление не объявлено, и это не ошибка."""
    site_portfolio = package.get("portfolio")
    if not site_portfolio:
        return None
    portfolios = load(root)
    if site_portfolio not in portfolios:
        raise ValueError(
            f"пакет объявляет направление «{site_portfolio}», которого нет в {REGISTRY}"
        )
    return portfolios[site_portfolio]


def members(packages: list[dict], root: Path | None = None) -> dict[str, list[str]]:
    """Сайты по направлениям. Считается по пакетам, а не по второму списку."""
    portfolios = load(root)
    out: dict[str, list[str]] = {pid: [] for pid in portfolios}
    for package in packages:
        pid = package.get("portfolio")
        if pid in out:
            out[pid].append(str(package.get("site_id", "")))
    return {pid: sorted(sites) for pid, sites in out.items()}


def legacy_unclassified(root: Path | None = None) -> dict:
    """Сайты, направление которых владелец ещё не называл.

    Отдельная запись, а не пустое поле в пакете: «не классифицирован» — это
    состояние с причиной, а не отсутствие данных, и его видно в реестре.
    """
    path = registry_path(root)
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    entry = data.get("legacy_unclassified") or {}
    return {
        "status": entry.get("status", LEGACY_UNCLASSIFIED),
        "sites": list(entry.get("sites") or []),
        "reason": entry.get("reason", ""),
        "unblocks": entry.get("unblocks", ""),
    }


def classification(package: dict, root: Path | None = None) -> str:
    """Направление пакета или `legacy/unclassified`."""
    declared = package.get("portfolio")
    if declared:
        return declared
    site_id = str(package.get("site_id", ""))
    return LEGACY_UNCLASSIFIED if site_id in legacy_unclassified(root)["sites"] else ""
