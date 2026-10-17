"""
Сборка портфеля из НЕСКОЛЬКИХ источников с выявлением расхождений.

Предыдущая версия реестра читала один файл и объявляла его истиной. Так и был
получен неверный итог PORTFOLIO_SITES_TOTAL=1: `config/portfolio.json` пуст,
но `config/analytics.json` содержит три домена Yami с рабочими счётчиками,
а `config/directions/lords.json` — три домена Lords с подтверждённой делегацией.

Правило модуля: если один источник содержит сайт, а другой нет — это
INVENTORY_DRIFT, а не повод молча выбрать один список.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Iterable, Sequence

import yaml

from .statuses import Status


class _Conflict:
    """Маркер «источники не согласны». Отличается от None, который значит
    «источник сообщил, что значения нет» — это разные факты."""

    def __repr__(self) -> str:
        return "CONFLICT"

    def __bool__(self) -> bool:
        return False


CONFLICT = _Conflict()


class SourceKind(str, Enum):
    """Источники фактов ТЗ. Порядок не означает приоритет — приоритета нет."""

    PORTFOLIO_REGISTRY = "portfolio_registry"      # config/portfolio.json
    ANALYTICS_REGISTRY = "analytics_registry"      # config/analytics.json
    DIRECTION_REGISTRY = "direction_registry"      # config/directions/*.json
    PACKAGES = "packages"                          # sites/*, blueprints
    TARGETS = "targets"                            # inventory/targets.yaml
    NGINX = "nginx"                                # /etc/nginx/sites-*
    SYSTEMD = "systemd"                            # units на хосте
    DEPLOYMENT = "deployment_manifest"             # deployment каталоги
    SECRET_HUB = "secret_hub"                      # status/verified/fingerprint
    LIVE_HTTPS = "live_https"                      # read-only проверка домена


# Источники, доступные только на реальном хосте. В контейнере разработки они
# не «пустые», а НЕДОСТУПНЫЕ — разница принципиальна для трактовки drift.
HOST_ONLY_SOURCES = frozenset({
    SourceKind.NGINX, SourceKind.SYSTEMD, SourceKind.DEPLOYMENT, SourceKind.LIVE_HTTPS,
})


class DriftKind(str, Enum):
    MISSING_IN_SOURCE = "missing_in_source"        # есть в одном, нет в другом
    FIELD_CONFLICT = "field_conflict"              # разные значения одного поля
    ORPHAN = "orphan"                              # есть только в одном источнике
    UNREACHABLE_SOURCE = "unreachable_source"      # источник недоступен отсюда


@dataclass(frozen=True)
class Fact:
    """Значение поля с указанием источника. Факт без источника не существует."""

    field: str
    value: Any
    source: SourceKind
    origin: str                                    # конкретный файл/путь/эндпоинт

    def __str__(self) -> str:
        return f"{self.field}={self.value!r} [{self.source.value}: {self.origin}]"


@dataclass
class DomainRecord:
    """Собранная карточка домена. Все поля — списки фактов, а не одиночные значения."""

    domain: str
    facts: dict[str, list[Fact]] = field(default_factory=dict)
    seen_in: set[SourceKind] = field(default_factory=set)

    def add(self, fact: Fact) -> None:
        self.facts.setdefault(fact.field, []).append(fact)
        self.seen_in.add(fact.source)

    def value(self, field_name: str, default: Any = None) -> Any:
        """
        Единственное значение, если источники согласны; иначе default.

        `None` — легитимное значение поля (например, webmaster_host_id у
        неподтверждённого хоста), поэтому «нет согласия» обозначается
        отдельным маркером CONFLICT, а не None.
        """
        facts = self.facts.get(field_name, [])
        if not facts:
            return default
        values = {json.dumps(f.value, sort_keys=True, default=str) for f in facts}
        return facts[0].value if len(values) == 1 else CONFLICT

    def conflicts(self) -> list[str]:
        out = []
        for name, facts in self.facts.items():
            distinct = {json.dumps(f.value, sort_keys=True, default=str) for f in facts}
            if len(distinct) > 1:
                out.append(name)
        return sorted(out)

    def render_field(self, field_name: str, absent: str = Status.NOT_MEASURED.value) -> str:
        facts = self.facts.get(field_name)
        if not facts:
            return absent
        v = self.value(field_name)
        if v is CONFLICT:
            return "CONFLICT: " + " | ".join(str(f) for f in facts)
        if v is None:
            # Источник явно сообщил «значения нет» — это факт, а не пробел в данных.
            return f"null [{facts[0].source.value}]"
        return f"{v} [{facts[0].source.value}]"


@dataclass(frozen=True)
class Drift:
    kind: DriftKind
    domain: str | None
    detail: str
    sources: tuple[str, ...]
    blocking: bool = False

    def __str__(self) -> str:
        scope = self.domain or "portfolio"
        return f"{self.kind.value}[{scope}]: {self.detail}"


@dataclass
class Inventory:
    domains: dict[str, DomainRecord] = field(default_factory=dict)
    drift: list[Drift] = field(default_factory=list)
    sources_read: set[SourceKind] = field(default_factory=set)
    sources_unavailable: dict[SourceKind, str] = field(default_factory=dict)

    def record(self, domain: str) -> DomainRecord:
        return self.domains.setdefault(domain, DomainRecord(domain=domain))

    def add_facts(self, domain: str, facts: Iterable[Fact]) -> None:
        rec = self.record(domain)
        for f in facts:
            rec.add(f)

    @property
    def total(self) -> int:
        return len(self.domains)

    def by_portfolio(self, portfolio: str) -> list[DomainRecord]:
        return [r for r in self.domains.values() if r.value("portfolio") == portfolio]

    def detect_drift(self) -> list[Drift]:
        """
        Расхождения считаются только между ФАКТИЧЕСКИ прочитанными источниками.
        Недоступный источник даёт отдельный вид drift и не выдаёт себя за пустой:
        «источник не читался» и «в источнике пусто» — разные утверждения.
        """
        out: list[Drift] = []

        for kind, reason in sorted(self.sources_unavailable.items()):
            out.append(Drift(
                kind=DriftKind.UNREACHABLE_SOURCE, domain=None,
                detail=f"источник {kind.value} не прочитан: {reason}",
                sources=(kind.value,),
                blocking=kind in HOST_ONLY_SOURCES))

        # Источники, которые вообще что-то сообщили о доменах.
        contributing = {s for r in self.domains.values() for s in r.seen_in}

        for domain, rec in sorted(self.domains.items()):
            missing = sorted(s.value for s in contributing - rec.seen_in
                             if s not in self.sources_unavailable)
            if missing and len(rec.seen_in) == 1:
                only = next(iter(rec.seen_in))
                out.append(Drift(
                    kind=DriftKind.ORPHAN, domain=domain,
                    detail=f"домен присутствует только в {only.value}; "
                           f"отсутствует в: {', '.join(missing)}",
                    sources=(only.value, *missing)))
            elif missing:
                out.append(Drift(
                    kind=DriftKind.MISSING_IN_SOURCE, domain=domain,
                    detail=f"есть в {', '.join(sorted(s.value for s in rec.seen_in))}; "
                           f"нет в: {', '.join(missing)}",
                    sources=tuple(missing)))

            for conflicted in rec.conflicts():
                values = " | ".join(str(f) for f in rec.facts[conflicted])
                out.append(Drift(
                    kind=DriftKind.FIELD_CONFLICT, domain=domain,
                    detail=f"поле '{conflicted}' различается: {values}",
                    sources=tuple(f.source.value for f in rec.facts[conflicted]),
                    blocking=True))

        self.drift = out
        return out


# --------------------------------------------------------------------------
# Считыватели источников
# --------------------------------------------------------------------------

def read_portfolio_registry(path: Path, inv: Inventory) -> None:
    """config/portfolio.json — реестр переданных владельцем сайтов."""
    if not path.exists():
        inv.sources_unavailable[SourceKind.PORTFOLIO_REGISTRY] = f"нет файла {path}"
        return
    data = json.loads(path.read_text(encoding="utf-8"))
    inv.sources_read.add(SourceKind.PORTFOLIO_REGISTRY)
    for site in data.get("sites") or []:
        domain = site.get("domain")
        if not domain:
            continue
        inv.add_facts(domain, [
            Fact("portfolio", site.get("portfolio") or site.get("tenant"),
                 SourceKind.PORTFOLIO_REGISTRY, str(path)),
            Fact("environment", site.get("environment"), SourceKind.PORTFOLIO_REGISTRY, str(path)),
            Fact("repository", site.get("repository"), SourceKind.PORTFOLIO_REGISTRY, str(path)),
        ])


def read_analytics_registry(path: Path, inv: Inventory) -> None:
    """config/analytics.json — счётчики Метрики и статус Вебмастера."""
    if not path.exists():
        inv.sources_unavailable[SourceKind.ANALYTICS_REGISTRY] = f"нет файла {path}"
        return
    data = json.loads(path.read_text(encoding="utf-8"))
    inv.sources_read.add(SourceKind.ANALYTICS_REGISTRY)
    global_indexing = data.get("seo_indexing_enabled")

    for prop in data.get("properties") or []:
        domain = prop.get("domain")
        if not domain:
            continue
        wm = prop.get("webmaster") or {}
        facts = [
            Fact("metrika_counter_id", prop.get("counter_id"),
                 SourceKind.ANALYTICS_REGISTRY, str(path)),
            Fact("metrika_counter_state", prop.get("counter_state"),
                 SourceKind.ANALYTICS_REGISTRY, str(path)),
            Fact("webvisor", prop.get("webvisor"), SourceKind.ANALYTICS_REGISTRY, str(path)),
            Fact("analytics_enabled", prop.get("analytics_enabled"),
                 SourceKind.ANALYTICS_REGISTRY, str(path)),
            Fact("webmaster_host_id", wm.get("host_id"),
                 SourceKind.ANALYTICS_REGISTRY, str(path)),
            Fact("webmaster_verification_status", wm.get("verification_status"),
                 SourceKind.ANALYTICS_REGISTRY, str(path)),
            Fact("indexing_enabled",
                 prop.get("seo_indexing_enabled", global_indexing),
                 SourceKind.ANALYTICS_REGISTRY, str(path)),
        ]
        inv.add_facts(domain, facts)


def read_direction_registry(path: Path, inv: Inventory) -> None:
    """config/directions/<name>.json — домены направления с подтверждённой делегацией."""
    if not path.exists():
        inv.sources_unavailable[SourceKind.DIRECTION_REGISTRY] = f"нет файла {path}"
        return
    data = json.loads(path.read_text(encoding="utf-8"))
    inv.sources_read.add(SourceKind.DIRECTION_REGISTRY)
    direction = data.get("direction")

    for entry in data.get("domains") or []:
        domain = entry.get("apex")
        if not domain:
            continue
        inv.add_facts(domain, [
            Fact("portfolio", direction, SourceKind.DIRECTION_REGISTRY, str(path)),
            Fact("profile", entry.get("proposed_profile"),
                 SourceKind.DIRECTION_REGISTRY, str(path)),
            Fact("profile_status", data.get("mapping_status"),
                 SourceKind.DIRECTION_REGISTRY, str(path)),
            Fact("dns_a_record", entry.get("a_apex"), SourceKind.DIRECTION_REGISTRY, str(path)),
            Fact("launched", entry.get("launched"), SourceKind.DIRECTION_REGISTRY, str(path)),
            Fact("direction_status", data.get("status"),
                 SourceKind.DIRECTION_REGISTRY, str(path)),
        ])


def read_targets(path: Path, inv: Inventory) -> dict[str, Any]:
    """
    inventory/targets.yaml — цели выкладки. Возвращает сводку, а не факты по доменам:
    target привязан к окружению, а не к домену.
    """
    if not path.exists():
        inv.sources_unavailable[SourceKind.TARGETS] = f"нет файла {path}"
        return {}
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    inv.sources_read.add(SourceKind.TARGETS)
    targets = data.get("targets") or []
    production = [t for t in targets if t.get("production_capable")]
    return {
        "total": len(targets),
        "refs": [t.get("ref") for t in targets],
        "production_capable": [t.get("ref") for t in production],
        "has_production_target": bool(production),
    }


def read_secret_hub_status(path: Path, inv: Inventory) -> dict[str, Any]:
    """
    config/secret-hub.json — ТОЛЬКО описания направлений и потребителей.
    Значения, отпечатки и токены отсюда не читаются: оператору доступны
    лишь status / verified / fingerprint / consumer status через API хаба.
    """
    if not path.exists():
        inv.sources_unavailable[SourceKind.SECRET_HUB] = f"нет файла {path}"
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    inv.sources_read.add(SourceKind.SECRET_HUB)
    out = {"provider": (data.get("provider") or {}).get("name"),
           "store_dir": data.get("store_dir"), "portfolios": []}
    for p in data.get("portfolios") or []:
        out["portfolios"].append({
            "id": p.get("id"), "enabled": p.get("enabled"),
            "consumers": [c.get("id") for c in (p.get("consumers") or [])],
            # Ни одного поля со значением секрета — только идентификаторы.
        })
    return out


def mark_host_sources_unavailable(inv: Inventory, reason: str) -> None:
    """
    Источники, которые читаются только на реальном хосте. Пометить их
    недоступными обязательно: иначе их отсутствие будет истолковано как
    «на хосте ничего нет», что и произошло в предыдущем аудите.
    """
    for kind in sorted(HOST_ONLY_SOURCES, key=lambda k: k.value):
        inv.sources_unavailable[kind] = reason


def build(*, repo_root: Path, host_available: bool,
          host_unavailable_reason: str = "") -> tuple[Inventory, dict[str, Any]]:
    """Собирает инвентарь из всех доступных источников и считает drift."""
    inv = Inventory()

    read_portfolio_registry(repo_root / "config" / "portfolio.json", inv)
    read_analytics_registry(repo_root / "config" / "analytics.json", inv)

    directions_dir = repo_root / "config" / "directions"
    if directions_dir.is_dir():
        for path in sorted(directions_dir.glob("*.json")):
            read_direction_registry(path, inv)
    else:
        inv.sources_unavailable[SourceKind.DIRECTION_REGISTRY] = f"нет каталога {directions_dir}"

    targets = read_targets(repo_root / "inventory" / "targets.yaml", inv)
    secret_hub = read_secret_hub_status(repo_root / "config" / "secret-hub.json", inv)

    if not host_available:
        mark_host_sources_unavailable(
            inv, host_unavailable_reason or "сессия выполняется не на целевом хосте")

    inv.detect_drift()
    inv.drift.extend(_portfolio_coverage_drift(inv, secret_hub))
    return inv, {"targets": targets, "secret_hub": secret_hub}


def _portfolio_coverage_drift(inv: Inventory, secret_hub: dict[str, Any]) -> list[Drift]:
    """
    Направление, объявленное в Secret Hub, но не имеющее ни одного домена
    в реестрах — расхождение, а не пустота. Именно так теряются целые
    направления: секреты для них заведены, а инвентаря нет.
    """
    known = {r.value("portfolio") for r in inv.domains.values()}
    known.discard(None)
    known.discard(CONFLICT)

    # Домены без атрибуции портфеля вообще: их нельзя сопоставить ни с одним
    # направлением, и это отдельный дефект реестра, а не отсутствие доменов.
    unattributed = [d for d, r in inv.domains.items() if not r.facts.get("portfolio")]

    out: list[Drift] = []
    if unattributed:
        out.append(Drift(
            kind=DriftKind.MISSING_IN_SOURCE, domain=None,
            detail=(f"{len(unattributed)} доменов не имеют поля portfolio ни в одном "
                    f"реестре ({', '.join(sorted(unattributed)[:6])}): сопоставить их "
                    "с направлениями Secret Hub невозможно"),
            sources=("analytics_registry", "portfolio_registry")))

    for p in secret_hub.get("portfolios") or []:
        name = p.get("id")
        if not name or not p.get("enabled") or name in known:
            continue
        consumers = p.get("consumers") or []
        suffix = f" ({len(consumers)} потребителей)" if consumers else " (без потребителей)"
        if unattributed:
            detail = (f"направление '{name}' объявлено в Secret Hub{suffix}; "
                      "ни один домен не помечен этим портфелем — возможно, из-за "
                      "отсутствия атрибуции выше, а не из-за отсутствия доменов")
        else:
            detail = (f"направление '{name}' объявлено в Secret Hub{suffix}, "
                      "но ни одного его домена нет в реестрах портфеля")
        out.append(Drift(
            kind=DriftKind.MISSING_IN_SOURCE, domain=None, detail=detail,
            sources=("secret_hub", "portfolio_registry", "direction_registry")))
    return out


def render_table(inv: Inventory) -> str:
    """Карточка по каждому домену со всеми полями, требуемыми ТЗ."""
    fields = [
        ("portfolio", "portfolio"), ("profile", "профиль"), ("repository", "repository"),
        ("deployment_target", "deployment target"), ("environment", "environment"),
        ("https", "HTTPS"), ("metrika_counter_id", "Metrika counter"),
        ("webmaster_host_id", "Webmaster host"), ("indexing_enabled", "indexing"),
        ("analytics_data_status", "analytics data"), ("content_status", "content"),
        ("live_url", "фактический URL"),
    ]
    lines = ["| Домен | " + " | ".join(label for _, label in fields) + " |",
             "|" + "---|" * (len(fields) + 1)]
    for domain, rec in sorted(inv.domains.items()):
        cells = [rec.render_field(name) for name, _ in fields]
        lines.append(f"| {domain} | " + " | ".join(cells) + " |")
    return "\n".join(lines)
