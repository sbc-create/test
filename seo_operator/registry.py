"""Registries: the portfolio of sites and the data sources behind them.

A registry is data, not code, so that adding a site is a reviewable diff rather
than a deployment. Every registry validates against a schema before it is used.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker

REPO_ROOT = Path(__file__).resolve().parent.parent
CONFIG_DIR = REPO_ROOT / "config"
SCHEMA_DIR = REPO_ROOT / "schemas"


class RegistryError(RuntimeError):
    pass


def _validate(data: dict, schema_name: str) -> None:
    schema_path = SCHEMA_DIR / schema_name
    if not schema_path.exists():
        raise RegistryError(f"схема не найдена: {schema_path}")
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    errors = sorted(validator.iter_errors(data), key=lambda e: list(e.path))
    if errors:
        detail = "; ".join(
            f"{'/'.join(str(p) for p in e.path) or '(root)'}: {e.message}" for e in errors[:5]
        )
        raise RegistryError(f"{schema_name}: реестр не проходит валидацию: {detail}")


@dataclass(frozen=True)
class Site:
    site_id: str
    name: str
    base_url: str
    risk_tier: str
    tone_of_voice: str
    rubrics: tuple[str, ...] = ()
    editorial_account: str | None = None
    moderation_enabled: bool = False
    synthetic: bool = False

    @property
    def domain(self) -> str:
        from urllib.parse import urlsplit

        return urlsplit(self.base_url).hostname or ""


@dataclass
class Portfolio:
    sites: list[Site] = field(default_factory=list)
    note: str = ""

    def __len__(self) -> int:
        return len(self.sites)

    @property
    def real_sites(self) -> list[Site]:
        return [s for s in self.sites if not s.synthetic]

    @property
    def synthetic_sites(self) -> list[Site]:
        return [s for s in self.sites if s.synthetic]

    @property
    def approved_domains(self) -> frozenset[str]:
        return frozenset(s.domain for s in self.sites if s.domain)

    def get(self, site_id: str) -> Site:
        for site in self.sites:
            if site.site_id == site_id:
                return site
        raise RegistryError(f"сайт {site_id!r} не найден в реестре")

    def lowest_risk(self) -> Site:
        order = {"low": 0, "medium": 1, "high": 2}
        if not self.sites:
            raise RegistryError("портфель пуст — canary выбирать не из чего")
        return sorted(self.sites, key=lambda s: order.get(s.risk_tier, 99))[0]


def load_portfolio(path: Path | None = None) -> Portfolio:
    path = Path(path or CONFIG_DIR / "portfolio.json")
    if not path.exists():
        raise RegistryError(f"реестр портфеля не найден: {path}")
    data = json.loads(path.read_text(encoding="utf-8"))
    _validate(data, "portfolio-registry.schema.json")
    sites = [
        Site(
            site_id=s["site_id"],
            name=s["name"],
            base_url=s["base_url"],
            risk_tier=s["risk_tier"],
            tone_of_voice=s.get("tone_of_voice", ""),
            rubrics=tuple(s.get("rubrics", [])),
            editorial_account=s.get("editorial_account"),
            moderation_enabled=s.get("moderation_enabled", False),
            synthetic=s.get("synthetic", False),
        )
        for s in data.get("sites", [])
    ]
    return Portfolio(sites=sites, note=data.get("note", ""))


def load_data_sources(path: Path | None = None) -> dict:
    path = Path(path or CONFIG_DIR / "data-sources.json")
    if not path.exists():
        raise RegistryError(f"реестр источников не найден: {path}")
    data = json.loads(path.read_text(encoding="utf-8"))
    _validate(data, "data-source-registry.schema.json")
    return data
