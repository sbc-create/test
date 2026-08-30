"""Источник позиций Topvisor: чтение проектов, кэш с TTL и last-known-good.

Topvisor — система измерения, а не источник SEO-работы. Отсюда три свойства,
ради которых написан этот модуль:

* **Отказ вместо пустоты.** Недоступный источник поднимает исключение. Пустой
  список, дошедший до отчёта, будет нарисован как «ноль запросов в TOP-10» —
  и это утверждение о позициях, которого никто не измерял.
* **Возраст всегда назван.** Если свежий запрос не удался, отдаётся последний
  удачный снимок, но помеченный ``stale`` с возрастом в секундах. Молча
  выданные вчерашние позиции — это ложь о сегодняшнем дне.
* **Ни одной платной операции.** Модуль вызывает только чтение списка
  проектов. Съём позиций (``get/positions_2/checker/go``) и аудит стоят денег
  и здесь недостижимы: клиент их не вызывает, а этот источник не умеет.

Чтение **сохранённых** позиций сюда намеренно не добавлено: имя метода истории
позиций не подтверждено ни официальной документацией в ``knowledge/``, ни
ответом API (без авторизации он отвечает одинаково на существующий и
несуществующий метод). Догадка об имени метода — выдуманный контракт, а не
интеграция. Пункт остаётся в backlog до появления документа или credential.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from factory.topvisor import manifest
from seo_operator.datasources.base import (
    Availability,
    CredentialedSource,
    SourceStatus,
    UnavailableSourceError,
)

#: Позиции обновляются раз в сутки, поэтому шесть часов — заведомо свежо и при
#: этом не превращает каждый прогон оператора в поход в чужой API.
DEFAULT_TTL_SECONDS = 21600.0

ENDPOINT = "https://api.topvisor.com/v2/json/"


@dataclass
class TopvisorCache:
    """Снимок проектов на диске. Битый файл равен отсутствующему."""

    path: Path
    ttl_seconds: float = DEFAULT_TTL_SECONDS

    def read(self) -> dict | None:
        try:
            return json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            # Битый кэш не повод падать и тем более не повод выдумать данные:
            # он просто считается отсутствующим и будет перезаписан.
            return None

    def write(self, payload: dict) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(self.path.suffix + ".tmp")
        tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        # rename атомарен в пределах одной ФС: читатель не увидит половину файла.
        tmp.replace(self.path)

    def fresh(self, snapshot: dict, now: float) -> bool:
        return (now - float(snapshot.get("fetched_at_epoch", 0))) < self.ttl_seconds


def _default_credential_check() -> tuple[bool, str]:
    """Есть ли доступ к учётным данным. Значение секрета не читается наружу."""
    try:
        from factory.topvisor import credentials

        credentials.load()
        return True, "учётные данные доступны"
    except Exception as exc:  # BlockedSecret и всё, что мешает их прочитать
        # Наружу уходит только причина, без пути к значению и без значения.
        return False, str(exc).split("\n", 1)[0]


def _default_client_factory():
    from factory.topvisor.client import TopvisorClient

    return TopvisorClient(apply_changes=False)


class TopvisorSource(CredentialedSource):
    """Источник проектов Topvisor с кэшем, TTL и last-known-good."""

    name = "topvisor"
    kind = "positions"
    endpoint = ENDPOINT

    def __init__(
        self,
        cache_path: Path,
        *,
        ttl_seconds: float = DEFAULT_TTL_SECONDS,
        credential_check: Callable[[], tuple[bool, str]] | None = None,
        client_factory: Callable[[], object] | None = None,
        now: Callable[[], float] = time.time,
    ) -> None:
        self.cache = TopvisorCache(Path(cache_path), ttl_seconds)
        self._credential_check = credential_check or _default_credential_check
        self._client_factory = client_factory or _default_client_factory
        self._now = now

    # ------------------------------------------------------------- probe

    def probe(self) -> Availability:
        ok, detail = self._credential_check()
        if not ok:
            return Availability(SourceStatus.MISSING_CREDENTIALS, detail)
        return Availability(SourceStatus.AVAILABLE, detail)

    def _fetch(self, site_id: str, **kwargs) -> dict:
        snapshot = self.snapshot()
        projects = [p for p in snapshot["projects"] if p["domain"] == site_id]
        return {**snapshot, "projects": projects}

    # ---------------------------------------------------------- snapshot

    def snapshot(self) -> dict:
        """Проекты Topvisor: из кэша, если свежо, иначе из API.

        При неудачном обновлении отдаётся последний удачный снимок с пометкой
        ``stale`` и возрастом. Если удачного снимка не было ни разу — отказ.
        """
        availability = self.probe()
        cached = self.cache.read()
        now = self._now()

        if not availability.usable:
            if cached:
                return self._stale(cached, now, availability.detail)
            raise UnavailableSourceError(f"{self.name} недоступен: {availability.detail}")

        if cached and self.cache.fresh(cached, now):
            return {**cached, "stale": False, "age_seconds": now - float(cached["fetched_at_epoch"])}

        try:
            fresh = self._collect(now)
        except Exception as exc:
            if cached:
                return self._stale(cached, now, str(exc))
            raise UnavailableSourceError(f"{self.name}: обновление не удалось и кэша нет — {exc}") from exc

        self.cache.write(fresh)
        return {**fresh, "stale": False, "age_seconds": 0.0}

    def _collect(self, now: float) -> dict:
        client = self._client_factory()
        raw = client.projects()

        by_id: dict[object, dict] = {}
        seen_domains: dict[str, int] = {}
        for entry in raw:
            project_id = entry.get("id")
            domain = str(entry.get("site") or entry.get("url") or "").strip().lower()
            domain = domain.removeprefix("https://").removeprefix("http://").removeprefix("www.").rstrip("/")
            if project_id is not None and project_id in by_id:
                # Дубль по идентификатору — это один и тот же проект, отданный
                # дважды. Схлопывается молча: новой информации в нём нет.
                continue
            # Отсутствующий идентификатор — не признак одинаковости. Раньше все
            # такие записи получали общий ключ `None` и схлопывались в одну,
            # унося с собой чужие домены. Ключ подменяется на уникальный, чтобы
            # запись дожила до healthcheck и была там видна.
            key = project_id if project_id is not None else f"__no_id__{len(by_id)}"
            by_id[key] = {"project_id": project_id, "domain": domain}
            seen_domains[domain] = seen_domains.get(domain, 0) + 1

        # Два РАЗНЫХ проекта на один домен — совсем другое дело: непонятно,
        # какой из них измеряет сайт, и молчать об этом нельзя.
        duplicates = sorted(d for d, count in seen_domains.items() if count > 1)

        return {
            "source": self.name,
            "fetched_at_epoch": now,
            "projects": list(by_id.values()),
            "duplicate_domains": duplicates,
        }

    def _stale(self, cached: dict, now: float, reason: str) -> dict:
        return {
            **cached,
            "stale": True,
            "age_seconds": now - float(cached.get("fetched_at_epoch", 0)),
            "refresh_error": reason,
        }


def healthcheck(source: TopvisorSource) -> dict:
    """Готовность интеграции: сколько из шести доменов реально прочитано.

    Статус ``CONNECTED`` выдаётся только когда все шесть доменов сопоставлены
    с проектами по фактическому ответу API. Частичное чтение — ``INCOMPLETE``,
    и это не придирка: отчёт по шести сайтам, построенный на четырёх, врёт про
    два оставшихся.
    """
    expected = list(manifest.domains())
    availability = source.probe()

    if not availability.usable:
        return {
            "status": "BLOCKED_CREDENTIAL",
            "detail": availability.detail,
            "expected": len(expected),
            "matched": 0,
            "missing_domains": expected,
            "owner_action": (
                "запустить от учётной записи в группе-владельце каталога секретов Topvisor"
            ),
        }

    try:
        snapshot = source.snapshot()
    except UnavailableSourceError as exc:
        return {
            "status": "ERROR",
            "detail": str(exc),
            "expected": len(expected),
            "matched": 0,
            "missing_domains": expected,
        }

    found = {p["domain"] for p in snapshot["projects"]}
    missing = [d for d in expected if d not in found]
    return {
        "status": "CONNECTED" if not missing else "INCOMPLETE",
        "detail": f"прочитано проектов: {len(snapshot['projects'])}",
        "expected": len(expected),
        "matched": len(expected) - len(missing),
        "missing_domains": missing,
        "duplicate_domains": snapshot.get("duplicate_domains", []),
        "stale": snapshot.get("stale", False),
        "age_seconds": snapshot.get("age_seconds", 0.0),
    }
