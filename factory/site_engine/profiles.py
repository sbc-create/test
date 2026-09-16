"""Профиль сайта: всё, что отличает сайт от сайта.

Модуль умышленно скучный. Его ценность в том, что различия между шестью
сайтами живут здесь, а не в виде `if site == "lords-01"` по всему коду. Гейт
нейтральности ядра следит, чтобы так и оставалось.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from factory.site_engine.contracts import ContractError

PROFILE_DIR = Path("config/site-profiles")

#: Способы получить нормализованный контент. Список закрыт: неизвестный вид —
#: это не «ещё один вариант», а незамеченная опечатка.
NORMALIZED_CONTENT_KINDS = ("content-ingestion", "site-engine-api", "adapter")


class ProfileNotFound(ContractError):
    pass


class ProfileInvalid(ContractError):
    pass


@dataclass(frozen=True)
class NormalizedContentSource:
    kind: str
    ref: str

    def __post_init__(self) -> None:
        if self.kind not in NORMALIZED_CONTENT_KINDS:
            raise ProfileInvalid(
                f"источник нормализованного контента «{self.kind}» не из числа "
                f"разрешённых: {', '.join(NORMALIZED_CONTENT_KINDS)}"
            )
        if not self.ref.strip():
            # Объявить источник и не назвать его — то же, что не объявить.
            raise ProfileInvalid(f"источник «{self.kind}» объявлен без ссылки")


@dataclass(frozen=True)
class SiteProfile:
    site_id: str
    site_type: str
    domains: tuple[str, ...]
    locale: str
    timezone: str
    theme: str
    enabled_modules: frozenset[str]
    render_mode: str
    seo_enabled: bool
    indexing_enabled: bool
    canonical_host: str
    keep_releases: int
    cache_policy: dict[str, Any]
    content_providers: tuple[dict[str, Any], ...]
    normalized_content_source: NormalizedContentSource | None
    health_endpoint: str | None
    coverage_endpoint: str | None
    feature_flags: dict[str, Any]
    raw: dict[str, Any]

    def has(self, module: str) -> bool:
        return module in self.enabled_modules

    @property
    def primary_domain(self) -> str:
        return self.domains[0]

    def normalized_content_kind(self) -> str | None:
        """Чем закрыто требование нормализованного контента, если оно закрыто.

        Локальный загрузчик отвечает сам за себя и объявления не требует —
        поэтому у пяти из шести профилей поля источника нет вовсе.
        """
        if self.has("content-ingestion"):
            return "content-ingestion"
        if self.normalized_content_source is not None:
            return self.normalized_content_source.kind
        return None


def _source_from(raw: dict[str, Any]) -> NormalizedContentSource | None:
    source = raw.get("normalized_content_source")
    if source is None:
        return None
    if not isinstance(source, dict):
        raise ProfileInvalid("normalized_content_source должен быть объектом")
    return NormalizedContentSource(kind=source.get("kind", ""), ref=source.get("ref", "") or "")


def profile_from_dict(raw: dict[str, Any]) -> SiteProfile:
    try:
        seo = raw["seo_profile"]
        return SiteProfile(
            site_id=raw["site_id"],
            site_type=raw["site_type"],
            domains=tuple(raw["domains"]),
            locale=raw["locale"],
            timezone=raw["timezone"],
            theme=raw["theme"],
            enabled_modules=frozenset(raw["enabled_modules"]),
            render_mode=raw["render_strategy"]["mode"],
            seo_enabled=bool(seo.get("enabled", False)),
            indexing_enabled=bool(seo.get("indexing_enabled", False)),
            canonical_host=seo.get("canonical_host", ""),
            keep_releases=int(raw["release_policy"]["keep_releases"]),
            cache_policy=raw["cache_policy"],
            content_providers=tuple(raw.get("content_providers", ())),
            normalized_content_source=_source_from(raw),
            health_endpoint=raw.get("health_endpoint"),
            coverage_endpoint=raw.get("coverage_endpoint"),
            feature_flags=dict(raw.get("feature_flags") or {}),
            raw=raw,
        )
    except KeyError as exc:
        raise ProfileInvalid(f"в профиле нет обязательного поля {exc}") from exc


def load_profile(site_id: str, root: Path | str = ".") -> SiteProfile:
    path = Path(root) / PROFILE_DIR / f"{site_id}.json"
    if not path.exists():
        raise ProfileNotFound(f"профиля {site_id} нет: {path}")
    raw = json.loads(path.read_text(encoding="utf-8"))
    if raw.get("site_id") != site_id:
        # Имя файла и site_id обязаны совпадать, иначе профиль правит не тот
        # сайт, что ожидали, и заметить это можно только по результату.
        raise ProfileInvalid(
            f"файл называется {site_id}.json, а site_id внутри — {raw.get('site_id')!r}"
        )
    return profile_from_dict(raw)


def load_all(root: Path | str = ".") -> list[SiteProfile]:
    directory = Path(root) / PROFILE_DIR
    return [load_profile(path.stem, root) for path in sorted(directory.glob("*.json"))]
