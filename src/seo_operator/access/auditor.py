"""
Первичный аудит доступов (ТЗ §3.3).

Матрица строится ДО любых изменений. Проверяется не наличие записи в конфиге,
а фактическая работоспособность: счётчик, у которого есть ID, но нет входящих
данных, — это BLOCKED_ACCESS, а не READY.

Секреты сюда не попадают: проверка обращается к Secret Hub за фактом наличия
и работоспособности, но не за значением.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from enum import Enum
from typing import Any, Callable, Iterable

from ..statuses import Status

# Порядок строк матрицы фиксирован — он совпадает с таблицей ТЗ §3.3.
CHECK_ORDER = (
    "domain_dns", "https", "metrika", "webmaster", "repository",
    "deployment", "indexing", "content_rights", "analytics_data",
)

CHECK_RU = {
    "domain_dns": "Домен и DNS",
    "https": "HTTPS",
    "metrika": "Метрика",
    "webmaster": "Вебмастер",
    "repository": "Репозиторий",
    "deployment": "Выкладка",
    "indexing": "Индексация",
    "content_rights": "Контентные права",
    "analytics_data": "Аналитические данные",
}

CHECK_WHAT = {
    "domain_dns": "владелец, NS, A/AAAA, доступность",
    "https": "сертификат, срок, автопродление",
    "metrika": "счётчик, права, цели, поступление данных",
    "webmaster": "хост, права, подтверждение, данные API",
    "repository": "ветка, CI, связь сайта с commit",
    "deployment": "target, rollback, backup",
    "indexing": "явное решение владельца",
    "content_rights": "источник и разрешение",
    "analytics_data": "дата последнего полного дня",
}

# Индексация и права имеют собственные словари статусов (ТЗ §3.3).
INDEXING_STATES = ("ENABLED", "DISABLED")
RIGHTS_STATES = ("CONFIRMED", "BLOCKED")
DATA_STATES = ("FRESH", "DELAYED", "MISSING")


@dataclass(frozen=True)
class CheckResult:
    check: str
    state: str                       # READY/BLOCKED или спец-словарь строки
    detail: str
    remediation: str = ""            # ровно одна безопасная процедура подключения

    @property
    def is_blocking(self) -> bool:
        return self.state in {"BLOCKED", "MISSING", Status.BLOCKED_ACCESS.value,
                              Status.BLOCKED_SECRET.value, Status.BLOCKED_RIGHTS.value,
                              Status.BLOCKED_DEPLOYMENT.value}


@dataclass
class SiteAccessReport:
    site_id: str
    domain: str
    checks: dict[str, CheckResult] = field(default_factory=dict)

    @property
    def ready(self) -> bool:
        """Сайт готов к работе, если ни одна строка не блокирует."""
        return not any(c.is_blocking for c in self.checks.values())

    @property
    def blocking_checks(self) -> list[CheckResult]:
        return [c for c in self.checks.values() if c.is_blocking]

    @property
    def collectable(self) -> bool:
        """Можно ли собирать данные — для этого достаточно Метрики или Вебмастера."""
        m = self.checks.get("metrika")
        w = self.checks.get("webmaster")
        return bool((m and not m.is_blocking) or (w and not w.is_blocking))


@dataclass
class Probe:
    """
    Набор фактических проверок. Каждая — callable, возвращающий (state, detail).
    Отсутствие probe означает «не проверяли», и это BLOCKED, а не READY:
    непроверенный доступ нельзя считать рабочим.
    """

    domain_dns: Callable[[str], tuple[str, str]] | None = None
    https: Callable[[str], tuple[str, str]] | None = None
    metrika: Callable[[str], tuple[str, str]] | None = None
    webmaster: Callable[[str], tuple[str, str]] | None = None
    repository: Callable[[str], tuple[str, str]] | None = None
    deployment: Callable[[str], tuple[str, str]] | None = None
    analytics_data: Callable[[str], tuple[str, str]] | None = None


REMEDIATION = {
    "domain_dns": "Передать домен под управление и указать NS; проверить A/AAAA командой `seo access probe --site <id>`.",
    "https": "Выпустить сертификат и включить автопродление на хосте выкладки.",
    "metrika": "Создать счётчик, выдать оператору read-доступ, положить OAuth в Secret Hub как `metrika/<site_id>`.",
    "webmaster": "Добавить хост в Вебмастер, подтвердить права, положить OAuth в Secret Hub как `webmaster/<site_id>`.",
    "repository": "Связать сайт с репозиторием и веткой в PORTFOLIO_REGISTRY, включить CI.",
    "deployment": "Указать target выкладки, проверить rollback и backup на staging.",
    "indexing": "Решение владельца: SEO_INDEXING_ENABLED. Оператор не включает индексацию самостоятельно.",
    "content_rights": "Подтвердить источник контента и право публикации, указать rights_ref.",
    "analytics_data": "Дождаться первого полного дня после подключения счётчика.",
}


def _run(probe_fn: Callable[[str], tuple[str, str]] | None, arg: str,
         check: str) -> CheckResult:
    if probe_fn is None:
        return CheckResult(check, "BLOCKED", "проверка не выполнялась — доступ не подтверждён",
                           REMEDIATION[check])
    try:
        state, detail = probe_fn(arg)
    except Exception as exc:  # noqa: BLE001 — падение probe это BLOCKED, а не крах аудита
        return CheckResult(check, "BLOCKED", f"проверка упала: {type(exc).__name__}: {exc}",
                           REMEDIATION[check])
    remediation = REMEDIATION[check] if state in {"BLOCKED", "MISSING", "DELAYED"} else ""
    return CheckResult(check, state, detail, remediation)


def audit_site(site: Any, probe: Probe, indexing_enabled: bool,
               rights_confirmed: bool) -> SiteAccessReport:
    """
    site — объект с site_id и domain (config.Site или совместимый).
    indexing_enabled и rights_confirmed приходят из manifest владельца, а не из probe:
    это решения, а не измерения.
    """
    report = SiteAccessReport(site_id=site.site_id, domain=site.domain)

    report.checks["domain_dns"] = _run(probe.domain_dns, site.domain, "domain_dns")
    report.checks["https"] = _run(probe.https, site.domain, "https")
    report.checks["metrika"] = _run(probe.metrika, site.site_id, "metrika")
    report.checks["webmaster"] = _run(probe.webmaster, site.site_id, "webmaster")
    report.checks["repository"] = _run(probe.repository, site.site_id, "repository")
    report.checks["deployment"] = _run(probe.deployment, site.site_id, "deployment")
    report.checks["analytics_data"] = _run(probe.analytics_data, site.site_id, "analytics_data")

    report.checks["indexing"] = CheckResult(
        "indexing", "ENABLED" if indexing_enabled else "DISABLED",
        "включено владельцем" if indexing_enabled else "выключено; оператор не включает сам",
        "" if indexing_enabled else REMEDIATION["indexing"])

    report.checks["content_rights"] = CheckResult(
        "content_rights", "CONFIRMED" if rights_confirmed else "BLOCKED",
        "права подтверждены" if rights_confirmed else "нет подтверждённого источника и разрешения",
        "" if rights_confirmed else REMEDIATION["content_rights"])

    return report


def render_matrix(reports: Iterable[SiteAccessReport]) -> str:
    """Матрица в формате ТЗ §3.3."""
    reports = list(reports)
    lines = ["| Сайт | Объект | Статус | Что проверяется | Деталь |", "|---|---|---|---|---|"]
    for r in reports:
        for check in CHECK_ORDER:
            res = r.checks.get(check)
            if res is None:
                continue
            mark = "🔴 " if res.is_blocking else ""
            lines.append(f"| {r.site_id} | {CHECK_RU[check]} | {mark}{res.state} | "
                         f"{CHECK_WHAT[check]} | {res.detail} |")
    return "\n".join(lines)


def missing_access_summary(reports: Iterable[SiteAccessReport]) -> list[dict[str, Any]]:
    """
    Перечень отсутствующих доступов и ОДНА безопасная процедура подключения
    для каждого — как требует ТЗ §3.3. Дубли схлопываются: одна и та же
    процедура на 100 сайтов не должна печататься 100 раз.
    """
    grouped: dict[tuple[str, str], list[str]] = {}
    for r in reports:
        for res in r.blocking_checks:
            grouped.setdefault((res.check, res.remediation), []).append(r.site_id)
    out = []
    for (check, remediation), sites in sorted(grouped.items()):
        out.append({"check": check, "check_ru": CHECK_RU.get(check, check),
                    "sites_affected": len(sites), "sites": sorted(sites)[:20],
                    "remediation": remediation})
    return sorted(out, key=lambda d: -d["sites_affected"])
