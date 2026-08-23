"""Мост между пакетами сайтов фабрики и портфелем SEO-оператора.

Оператор не ведёт собственный список сайтов и не добавляет их по своей
инициативе: единственный источник истины о том, какие сайты существуют, — это
пакеты фабрики в ``sites/*/package.yaml``. Мост читает их и показывает как
записи портфеля.

Важное свойство: мост **ничего не записывает** в ``config/portfolio.json``.
Реальный реестр заполняет владелец, когда переданы домен, доступы к CMS и
подтверждены права. Пока этого нет, сайт виден оператору со статусом
``BLOCKED_INPUT_DOMAIN_TARGET`` и не считается инвентарём для live-работы.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

#: Статусы готовности сайта к работе оператора с живыми данными.
READY = "READY"
BLOCKED_DOMAIN_TARGET = "BLOCKED_INPUT_DOMAIN_TARGET"
BLOCKED_RIGHTS = "BLOCKED_INPUT_RIGHTS"

#: Домены стенда. Сайт на таком домене — не инвентарь, а локальная проверка.
STAND_SUFFIXES = (".localhost", "localhost", "127.0.0.1")


def _is_stand_domain(domain: str) -> bool:
    domain = (domain or "").strip().lower()
    return not domain or any(domain.endswith(suffix) for suffix in STAND_SUFFIXES)


def discover_packages(root: Path) -> list[dict[str, Any]]:
    """Все пакеты сайтов фабрики. Порядок стабильный — по имени каталога."""
    sites_dir = Path(root) / "sites"
    if not sites_dir.is_dir():
        return []
    packages: list[dict[str, Any]] = []
    for package_path in sorted(sites_dir.glob("*/package.yaml")):
        try:
            data = yaml.safe_load(package_path.read_text(encoding="utf-8")) or {}
        except yaml.YAMLError as exc:  # пакет с битым YAML не молчит
            raise ValueError(f"{package_path}: не разбирается как YAML: {exc}") from exc
        if isinstance(data, dict):
            data["_path"] = str(package_path)
            packages.append(data)
    return packages


def readiness(package: dict[str, Any]) -> str:
    """Готов ли сайт к работе оператора с живыми данными.

    Проверяется не одно поле, а связка: домен стенда, невыданная авторизация
    production и неподтверждённые права каждый по отдельности означают, что
    работать с живыми данными нельзя.
    """
    content_source = package.get("content_source") or {}
    if not content_source.get("rights_confirmed", False):
        return BLOCKED_RIGHTS
    if package.get("fixture", False):
        return BLOCKED_DOMAIN_TARGET
    if _is_stand_domain(str(package.get("domain", ""))):
        return BLOCKED_DOMAIN_TARGET
    if not package.get("production_authorized", False):
        return BLOCKED_DOMAIN_TARGET
    return READY


def to_portfolio_entry(package: dict[str, Any]) -> dict[str, Any]:
    """Запись портфеля по пакету сайта, в формате schemas/portfolio-registry."""
    site_id = str(package.get("site_id", "")).strip()
    brand = package.get("brand") or {}
    tenant = package.get("tenant") or {}
    comments = package.get("comments") or {}
    status = readiness(package)

    # Публичное название не придумывается: пока бренд не передан, показывается
    # внутренний код сайта, и это видно по полю `name`.
    name = str(brand.get("legal_name") or brand.get("name") or site_id).strip() or site_id

    base_url = str(package.get("canonical_url") or "").strip()
    if not base_url:
        domain = str(package.get("domain", "")).strip()
        base_url = f"https://{domain}/" if domain else ""

    return {
        "site_id": site_id,
        "name": name,
        "base_url": base_url,
        # Сайт на стенде не может быть высокого риска: он никому не виден.
        # Настоящий production — всегда высокий, пока не доказано обратное.
        "risk_tier": "high" if status == READY else "low",
        "tone_of_voice": str(tenant.get("seo_profile") or ""),
        "rubrics": list(tenant.get("owned_listings") or []),
        # Редакционный аккаунт назначает владелец вместе с доступами; до тех пор
        # автоматический ответ невозможен технически, а не по договорённости.
        "editorial_account": None,
        "moderation_enabled": bool(comments.get("premoderation", False)),
        "synthetic": bool(package.get("fixture", False)),
    }


def portfolio_view(root: Path) -> dict[str, Any]:
    """Портфель, каким его видит оператор поверх фабрики.

    Это представление, а не реестр: файл ``config/portfolio.json`` остаётся за
    владельцем. Оператор берёт отсюда список сайтов, но работать с живыми
    данными может только по тем, у кого статус READY.
    """
    packages = discover_packages(root)
    entries = []
    for package in packages:
        entry = to_portfolio_entry(package)
        entry["readiness"] = readiness(package)
        entry["package"] = package.get("_path", "")
        entries.append(entry)

    blocked = [e for e in entries if e["readiness"] != READY]
    return {
        "version": 1,
        "source": "sites/*/package.yaml",
        "note": (
            "Представление портфеля, построенное по пакетам фабрики. Оператор не "
            "добавляет сайты самостоятельно и ничего не пишет в config/portfolio.json. "
            "Сайты со статусом, отличным от READY, недоступны для работы с живыми "
            "данными: не переданы домен, цель выката, права или авторизация production."
        ),
        "sites": entries,
        "counts": {
            "total": len(entries),
            "ready": len(entries) - len(blocked),
            "blocked": len(blocked),
        },
    }


def live_allowed(root: Path) -> list[str]:
    """Сайты, по которым разрешена работа с живыми источниками."""
    return [e["site_id"] for e in portfolio_view(root)["sites"] if e["readiness"] == READY]
