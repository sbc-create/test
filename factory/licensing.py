"""Лицензионный гейт DLE.

Одна лицензия покрывает один домен второго уровня и его поддомены. Production-job
без подходящей лицензии завершается статусом BLOCKED_LICENSE и не ставит сайт.
"""
from __future__ import annotations

import datetime as _dt
from dataclasses import dataclass

from factory import inventory
from factory.errors import BlockedLicense


@dataclass(frozen=True)
class LicenseCheck:
    covered: bool
    registrable_domain: str
    license_ref: str | None
    reason: str


def registrable_domain(domain: str) -> str | None:
    """Домен второго уровня (eTLD+1) по сокращённому списку суффиксов.

    Возвращает None, если определить однозначно нельзя — вызывающий обязан
    трактовать это как отсутствие покрытия, а не как совпадение.
    """
    host = (domain or "").strip().lower().rstrip(".")
    if not host or host.count(".") < 1:
        return None
    labels = host.split(".")
    suffixes = inventory.multi_label_suffixes()
    if len(labels) >= 3 and ".".join(labels[-2:]) in suffixes:
        return ".".join(labels[-3:])
    if ".".join(labels[-2:]) in suffixes:
        return None  # сам публичный суффикс не является регистрируемым доменом
    return ".".join(labels[-2:])


def _expired(entry: dict, today: _dt.date) -> bool:
    expires = entry.get("expires_at")
    if not expires:
        return False
    try:
        return _dt.date.fromisoformat(str(expires)) < today
    except ValueError:
        return True  # нечитаемая дата = нельзя доказать действительность


def check_domain(domain: str, *, license_ref: str | None = None, today: _dt.date | None = None) -> LicenseCheck:
    today = today or _dt.date.today()
    rd = registrable_domain(domain)
    if rd is None:
        return LicenseCheck(False, "", license_ref, f"Не удалось однозначно определить домен второго уровня для «{domain}». Расширь inventory/public-suffixes.yaml или укажи covered_domain явно.")

    candidates = inventory.all_licenses()
    if not license_ref:
        # Без явной ссылки покрытие могла бы дать чужая лицензия из инвентаря,
        # которую пакет не называл.
        return LicenseCheck(False, rd, None,
                            "В пакете не указан dle_license_ref: лицензия обязана быть названа явно.")
    if license_ref:
        candidates = [e for e in candidates if e.get("ref") == license_ref]
        if not candidates:
            return LicenseCheck(False, rd, license_ref, f"Лицензия «{license_ref}» отсутствует в inventory/dle-licenses.yaml.")

    for entry in candidates:
        covered = str(entry.get("covered_domain", "")).lower().strip()
        if not covered:
            continue
        if covered != rd:
            continue
        if _expired(entry, today):
            return LicenseCheck(False, rd, entry.get("ref"), f"Лицензия «{entry.get('ref')}» истекла {entry.get('expires_at')}.")
        if str(entry.get("version", "")) not in ("", "20.0"):
            return LicenseCheck(False, rd, entry.get("ref"), f"Лицензия «{entry.get('ref')}» выдана на версию {entry.get('version')}, а не 20.0.")
        if host_is_subdomain(domain, covered) and not entry.get("covers_subdomains", True):
            return LicenseCheck(False, rd, entry.get("ref"), f"Лицензия «{entry.get('ref')}» не покрывает поддомены.")
        return LicenseCheck(True, rd, entry.get("ref"), "ok")

    return LicenseCheck(False, rd, license_ref, f"Нет лицензии DLE, покрывающей домен второго уровня «{rd}».")


def host_is_subdomain(domain: str, covered: str) -> bool:
    d = domain.lower().rstrip(".")
    return d != covered and d.endswith("." + covered)


def require_license(domain: str, *, license_ref: str | None, environment: str) -> LicenseCheck:
    """Гейт: для production отсутствие покрытия — жёсткая остановка."""
    result = check_domain(domain, license_ref=license_ref)
    if environment == "production" and not result.covered:
        raise BlockedLicense(
            result.reason,
            field="dle_license_ref",
            required_input="Запись в inventory/dle-licenses.yaml с covered_domain, равным домену второго уровня сайта",
            blocks_stage="PRODUCTION_DEPLOY",
        )
    return result
