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


@dataclass(frozen=True)
class Portfolio:
    id: str
    label: str
    purpose: str
    secret_scope: str
    blueprint: str

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
