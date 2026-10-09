"""Регулярный прогон SEO-модуля по сети: проверка, сутки, неделя.

Три режима и одна ответственность у каждого:

* ``check`` — раз в шесть часов. Короткая проверка: доступность главной и
  robots.txt, расхождение заявленного режима индексации с фактическим ответом,
  свежесть снимка аналитики, фактический результат последних публикаций.
  Полного обхода сети нет: два запроса на домен плюс проверка новых публикаций.
* ``daily`` — раз в сутки, к 09:00 МСК. Берёт результат последней проверки (не
  повторяет её, если она моложе семи часов), добавляет свежесть sitemap,
  остановившиеся обновления, сравнение НЕПЕРЕКРЫВАЮЩИХСЯ недель аналитики,
  гигиену редакционной очереди и раздел о самом модуле. Пишет ОДИН отчёт
  владельцу.
* ``weekly`` — раз в неделю. Пересмотр приоритетов и оценка опубликованного по
  исходным показателям. Отдельного уведомления не шлёт: результат входит в
  ближайший суточный отчёт.

Почему повторное чтение снимка не считается наблюдением. Сборщик кладёт снимок
Метрики раз в сутки, а окно снимка — «7 дней до вчера». Проверка каждые шесть
часов четыре раза прочтёт один и тот же файл; засчитать это как четыре
наблюдения значило бы выдать отсутствие новых данных за стабильность. Поэтому
у каждого домена хранится отпечаток значений, и наблюдением считается только
новый отпечаток из нового снимка. Сравнение «неделя к неделе» берёт снимок
ровно на семь дней старше: окна соседних суточных снимков перекрываются на
шесть дней из семи, и их разность — не изменение, а сдвиг окна.

Что модуль НЕ делает: ничего не публикует, не регистрирует и не берёт задания
очереди, не меняет режим индексации, nginx, реестры и данные сайтов. Он читает
и пишет только своё состояние в ``var/seo-regular``. Задания очереди берёт
редактор; SEO-исполнитель их только предлагает (см. docs/SEO_REGULAR_RUN.md).

Свойства фонового запуска:

* блокировка — ``FileLock`` из ``seo_operator.scheduler``: второй запуск
  получает ``LockBusy`` и выходит с кодом 75, ничего не делая;
* контрольные точки — шаги запуска отмечаются по мере завершения, результат
  каждого шага лежит на диске; прерванный запуск того же слота продолжает с
  первого незавершённого шага;
* бюджет — предел времени цикла и число HTTP-запросов; при исчерпании запуск
  завершается как ``PARTIAL`` (код 75), и следующий вызов слота продолжает;
* журнал — каждое действие, ошибка и проверка публикации пишется строкой JSON
  в ``var/seo-regular/journal/<дата>.jsonl``;
* повторы — временные сетевые ошибки (таймаут, обрыв, 502/503/504)
  повторяются с удвоением задержки.
"""

from __future__ import annotations

import argparse
import contextlib
import datetime as dt
import gzip
import hashlib
import html
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from seo_operator import page_audit
from seo_operator.scheduler import Checkpoint, FileLock, LockBusy

REPO_ROOT = Path(__file__).resolve().parents[1]
UTC = dt.timezone.utc
MSK = dt.timezone(dt.timedelta(hours=3))

#: Код «временно не выполнено»: systemd юнитов считает его успешным
#: (SuccessExitStatus=0 75), а следующий запуск слота продолжит работу.
EXIT_TEMPFAIL = 75
#: Новая КРИТИЧЕСКАЯ проблема: юнит завершается неуспехом, и это уведомление.
#: Та же проблема на следующей проверке юнит уже не роняет — второго
#: уведомления о ней нет.
EXIT_NEW_CRITICAL = 3

USER_AGENT = "site-factory-seo-regular/1 (read-only check)"

#: Источники. Все читаются, ни один не пишется.
SOURCES = {
    "cells": REPO_ROOT / "config" / "site-cells.json",
    "analytics_registry": REPO_ROOT / "config" / "analytics.json",
    "analytics_snapshots": REPO_ROOT / "artifacts" / "analytics",
    "indexing_states": Path("/srv/sites/indexing"),
    "queue_registry": Path("/var/lib/seo-content-operator/registry.json"),
    "queue_events": Path("/var/lib/seo-content-operator/queue_events.jsonl"),
    "content_operator_state": Path("/var/lib/seo-content-operator/state.json"),
    "defects": REPO_ROOT / "config" / "seo-module-defects.json",
    "changes_ledger": REPO_ROOT / "config" / "seo-changes.json",
    # Строки журнала изменений, которые дописывает фоновый редактор (в git не
    # коммитит — в репозиторий их переносит сессия).
    "changes_ledger_runs": REPO_ROOT / "var" / "editor-runs" / "ledger.jsonl",
    "facts_snapshots": Path("/srv/lords/.frontend"),
    "coverage_blockers": REPO_ROOT / "config" / "editor-coverage-blockers.json",
}

#: Домены Animedia и их снимки фактов: только у этого семейства есть факты,
#: доставка и отображение описаний.
ANIMEDIA = {"animedia.icu": "animedia-01", "animedia.space": "animedia-02"}

#: Домены, где редактор публикует описания с подтверждённым показом. Zona —
#: с 2026-10-09: первая видимая публикация zonafilm.space/title/ledyanaya-stena/.
EDITOR_SITES = {
    **ANIMEDIA,
    "zonafilm.space": "zona-01",
    # С 2026-10-09: контракт и читатель правок выпущены (f17b9f7/c387529, a1b5d71/4714e0a).
    "lordfilm47.space": "lords-01",
    "lordserial33.biz": "lords-02",
    # С 2026-10-09: тот же читатель выпущен сессией wt-portable-site-cell-01-97
    # (lords-03 e0b6d49, lords-05 a6de937), показ подтверждён на странице.
    "1lordserials1.online": "lords-03",
    "lordserials22.info": "lords-05",
    "zonafilm12.site": "zona-03",
    # С 2026-10-09: накладка AnimeGo перечитывается без перезапуска (71974e5),
    # показ подтверждён публикацией an1meg0.site/title/medalistka-2/.
    "an1meg0.site": "animego-04",
    # С 2026-10-09 после перезапуска моста (534118c): снимок — в каталоге данных
    # ячейки; показ подтверждён публикациями kletka-duha-2 и pesn-nochnyh-sov-2.
    "an1mego.site": "animego-02",
    "animeg0.site": "animego-03",
}

#: Снимки крупнее этого читаются по записи: полный json.loads снимка Zona
#: (82 МБ) не помещается в MemoryMax=512M суточной службы.
STREAM_DETAILS_BYTES = 40_000_000

#: Сколько пробелов-фильмов/сериалов (без Shikimori, с IMDb ID) держать на сайт
#: из крупного снимка: лучшие по рейтингу каталога и году. Рейтинг служит только
#: порядку работы, в текст он не попадает (EDITORIAL_RULES).
FILM_GAPS_KEPT = 150
_EDITOR_FIELDS = (
    "name",
    "original_name",
    "description",
    "playable",
    "year",
    "external_ids",
    "type",
    "countries",
    "imdb_rating",
)

#: Источник фактов по типу произведения. Одобрен только путь аниме (D199). Для
#: фильмов и сериалов источник не одобрен: предложение —
#: docs/editor/SOURCES_BY_TYPE.md; до решения владельца карточки копятся в учёте
#: «нужен источник», а не исключаются.
SOURCE_PLAN = {
    "movie": "фильм: нет IMDb ID — идентичность не установить (D200 требует совпадения IMDb)",
    "tv": "сериал: нет IMDb ID — идентичность не установить (D200 требует совпадения IMDb)",
    None: "тип не указан: сначала установить идентичность по ID каталога",
}

#: Хранилища опубликованных материалов по семействам и форма их адресов.
#: Пути — те же, что у factory.qwen.registry.КОРНИ_ХРАНИЛИЩ; форма адреса —
#: factory.qwen.registry.ФОРМА_АДРЕСА (проверена запросами там).
OVERLAY_ROOTS = {
    "animedia": (Path("/srv/sites/animedia/runtime/overlays"), "/title/{slug}/"),
    "lords": (Path("/srv/sites/lords/runtime/overlays"), "/title/{slug}/"),
    "animego": (Path("/srv/sites/animego/runtime/overlays"), "/title/{slug}/"),
    "yummy": (Path("/srv/sites/yummyani-staging/runtime/overlays"), "/anime/{slug}"),
}

#: Владельцы аренды очереди, по имени которых видно, что задание взяла
#: SEO-сторона, а не редактор. Используется только для отчёта о пересечении
#: ответственности — ничего не блокирует.
SEO_OWNER_PATTERN = re.compile(r"seo|analy|audit", re.IGNORECASE)

MODES = ("check", "daily", "weekly", "hourly")


# --------------------------------------------------------------------- время


def utcnow() -> dt.datetime:
    return dt.datetime.now(tz=UTC)


def iso(moment: dt.datetime) -> str:
    return moment.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_iso(text: str | None) -> dt.datetime | None:
    if not text:
        return None
    raw = str(text).strip().replace("Z", "+00:00")
    try:
        moment = dt.datetime.fromisoformat(raw)
    except ValueError:
        try:
            moment = dt.datetime.strptime(raw[:10], "%Y-%m-%d")
        except ValueError:
            return None
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=UTC)
    return moment


#: Расписание проверки — automation/host/seo-regular/seo-regular-check.timer.
CHECK_ANCHOR_HOUR = 5
CHECK_ANCHOR_MINUTE = 25


def slot_id(mode: str, moment: dt.datetime) -> str:
    """Идентификатор слота: один запуск на слот, прерванный — продолжается."""
    if mode == "check":
        # Слот начинается в момент расписания (05:25, 11:25, 17:25, 23:25 UTC), а
        # не на шестичасовой отметке от полуночи. Измерено 2026-10-08: при
        # границах 00/06/12/18 плановая проверка 17:25 попала в слот 12:00–18:00,
        # уже закрытый ручным запуском в 12:06, и ничего не проверила.
        utc = moment.astimezone(UTC)
        start = utc.replace(minute=CHECK_ANCHOR_MINUTE, second=0, microsecond=0)
        start -= dt.timedelta(hours=(utc.hour - CHECK_ANCHOR_HOUR) % 6)
        if start > utc:
            start -= dt.timedelta(hours=6)
        return f"check-{start:%Y-%m-%dT%H%M}"
    if mode == "daily":
        return f"daily-{moment.astimezone(MSK):%Y-%m-%d}"
    if mode == "hourly":
        return f"hourly-{moment.astimezone(UTC):%Y-%m-%dT%H}"
    year, week, _ = moment.astimezone(MSK).isocalendar()
    return f"weekly-{year}-W{week:02d}"


# ---------------------------------------------------------------- состояние


def _read_json(path: Path, default: Any) -> Any:
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return default


def _write_json(path: Path, data: Any) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    tmp.replace(path)


class Journal:
    """Журнал фактических действий: одна строка JSON на событие."""

    def __init__(self, root: Path, run_id: str) -> None:
        self.dir = Path(root) / "journal"
        self.dir.mkdir(parents=True, exist_ok=True)
        self.run_id = run_id

    def write(self, event: str, **fields: Any) -> None:
        now = utcnow()
        record = {"at": iso(now), "run_id": self.run_id, "event": event, **fields}
        with (self.dir / f"{now:%Y-%m-%d}.jsonl").open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, ensure_ascii=False) + "\n")


class BudgetExceeded(RuntimeError):
    """Исчерпан бюджет времени или запросов. Слот продолжит следующий вызов."""


@dataclass
class Budget:
    seconds: float
    requests: int
    started: float = field(default_factory=time.monotonic)
    used_requests: int = 0

    def remaining(self) -> float:
        return self.seconds - (time.monotonic() - self.started)

    def check_time(self) -> None:
        if self.remaining() <= 0:
            raise BudgetExceeded(f"предел времени цикла {self.seconds:.0f} с исчерпан")

    def take_request(self) -> None:
        self.check_time()
        if self.used_requests >= self.requests:
            raise BudgetExceeded(f"предел запросов {self.requests} исчерпан")
        self.used_requests += 1


# ---------------------------------------------------------------------- HTTP


@dataclass
class Response:
    url: str
    status: int | None
    headers: dict[str, str]
    body: bytes
    elapsed: float
    error: str = ""
    attempts: int = 1


TRANSIENT_STATUS = {502, 503, 504}


class Http:
    """GET с ограничением частоты, бюджетом и повторами временных ошибок."""

    def __init__(
        self,
        budget: Budget,
        journal: Journal | None = None,
        *,
        timeout: float = 15.0,
        attempts: int = 3,
        backoff: float = 2.0,
        min_interval: float = 0.3,
        max_bytes: int = 20 * 1024 * 1024,
        opener: Callable[..., Any] | None = None,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self.budget = budget
        self.journal = journal
        self.timeout = timeout
        self.attempts = attempts
        self.backoff = backoff
        self.min_interval = min_interval
        self.max_bytes = max_bytes
        self._open = opener or urllib.request.urlopen
        self._sleep = sleep
        self._last = 0.0

    def get(self, url: str, *, timeout: float | None = None) -> Response:
        last: Response | None = None
        for attempt in range(1, self.attempts + 1):
            self.budget.take_request()
            pause = self.min_interval - (time.monotonic() - self._last)
            if pause > 0:
                self._sleep(pause)
            self._last = time.monotonic()
            last = self._once(url, timeout or self.timeout)
            last.attempts = attempt
            transient = last.status is None or last.status in TRANSIENT_STATUS
            if not transient:
                return last
            if self.journal:
                self.journal.write(
                    "http_retry" if attempt < self.attempts else "http_failed",
                    url=url,
                    attempt=attempt,
                    status=last.status,
                    error=last.error,
                )
            if attempt < self.attempts:
                self._sleep(self.backoff * (2 ** (attempt - 1)))
        assert last is not None
        return last

    def _once(self, url: str, timeout: float) -> Response:
        request = urllib.request.Request(
            url, headers={"User-Agent": USER_AGENT, "Accept-Encoding": "gzip"}
        )
        started = time.monotonic()
        try:
            with self._open(request, timeout=timeout) as resp:
                body = resp.read(self.max_bytes)
                headers = {k.lower(): v for k, v in resp.headers.items()}
                status = resp.status
        except urllib.error.HTTPError as exc:
            body = exc.read(self.max_bytes) if hasattr(exc, "read") else b""
            headers = {k.lower(): v for k, v in (exc.headers or {}).items()}
            status = exc.code
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            reason = getattr(exc, "reason", exc)
            return Response(
                url,
                None,
                {},
                b"",
                time.monotonic() - started,
                error=f"{type(exc).__name__}: {reason}",
            )
        if headers.get("content-encoding") == "gzip":
            with contextlib.suppress(OSError):
                body = gzip.decompress(body)
        return Response(url, status, headers, body, time.monotonic() - started)


# ---------------------------------------------------------------- домены


def discover_domains(sources: dict[str, Path] = SOURCES) -> list[dict]:
    """Публичные домены сети из реестра ячеек и реестра аналитики.

    Тестовые имена (`*.localhost`, `*.test`) не являются сайтами сети.
    """
    cells = _read_json(sources["cells"], {}).get("cells") or []
    analytics = {
        p.get("domain"): p
        for p in (_read_json(sources["analytics_registry"], {}).get("properties") or [])
    }
    out: dict[str, dict] = {}
    for cell in cells:
        domain = str(cell.get("domain") or "")
        if not domain or domain.endswith((".localhost", ".test")) or domain == "localhost":
            continue
        out[domain] = {
            "domain": domain,
            "site_id": cell.get("site_id"),
            "open_authorized": bool((cell.get("indexing") or {}).get("open_authorized")),
        }
    for domain in analytics:
        if domain and domain not in out:
            out[domain] = {"domain": domain, "site_id": None, "open_authorized": None}
    for domain, item in out.items():
        prop = analytics.get(domain) or {}
        webmaster = prop.get("webmaster") or {}
        item["counter_id"] = prop.get("counter_id")
        item["webmaster_host_id"] = webmaster.get("host_id")
        item["webmaster_status"] = webmaster.get("verification_status")
        state = _read_json(sources["indexing_states"] / f"{domain}.json", None)
        item["indexing_desired"] = (state or {}).get("desired_state")
    return [out[d] for d in sorted(out)]


# -------------------------------------------------------------- проверки


ROBOTS_META = re.compile(
    rb"<meta[^>]+name=[\"']robots[\"'][^>]*content=[\"']([^\"']*)[\"']", re.IGNORECASE
)
COUNTER_ON_PAGE = re.compile(rb"(?:mc\.yandex\.ru/watch/|ym\()\s*(\d{6,10})")
CANONICAL = re.compile(
    rb"<link[^>]+rel=[\"']canonical[\"'][^>]*href=[\"']([^\"']+)[\"']", re.IGNORECASE
)


def robots_disallows_all(text: str) -> bool:
    """`Disallow: /` в группе `User-agent: *` — сайт закрыт целиком."""
    group_all = False
    for raw in text.splitlines():
        line = raw.split("#", 1)[0].strip()
        if not line or ":" not in line:
            continue
        key, value = (part.strip() for part in line.split(":", 1))
        key = key.lower()
        if key == "user-agent":
            group_all = value == "*"
        elif key == "disallow" and group_all and value == "/":
            return True
    return False


DNS_FAILURE = re.compile(
    r"Name or service not known|nodename nor servname|No address associated|"
    r"Temporary failure in name resolution",
    re.IGNORECASE,
)


def check_domain(http: Http, item: dict, *, was_reachable: bool = False) -> dict:
    """Две выборки на домен: главная и robots.txt. Выводы — только из ответа.

    Имя, которое НИКОГДА не разрешалось (serverHold, нет делегирования), — это
    известное внешнее состояние, а не авария: каждые шесть часов объявлять его
    критическим значило бы приучить читателя пропускать критическое. Критическим
    отказ DNS становится у домена, который раньше отвечал.
    """
    domain = item["domain"]
    home = http.get(f"https://{domain}/")
    result: dict[str, Any] = {
        "domain": domain,
        "checked_at": iso(utcnow()),
        "home_status": home.status,
        "home_error": home.error,
        "home_seconds": round(home.elapsed, 2),
        "attempts": home.attempts,
        "issues": [],
    }
    head = home.body[:262144]
    header_robots = home.headers.get("x-robots-tag", "")
    meta = ROBOTS_META.search(head)
    canonical = CANONICAL.search(head)
    result["x_robots_tag"] = header_robots
    result["meta_robots"] = meta.group(1).decode("utf-8", "replace") if meta else ""
    result["home_canonical"] = canonical.group(1).decode("utf-8", "replace") if canonical else ""

    robots = http.get(f"https://{domain}/robots.txt")
    robots_text = robots.body.decode("utf-8", "replace") if robots.status == 200 else ""
    result["robots_status"] = robots.status
    result["robots_disallow_all"] = robots_disallows_all(robots_text) if robots_text else None
    result["robots_sitemaps"] = re.findall(r"(?im)^\s*sitemap:\s*(\S+)", robots_text)

    issues = result["issues"]
    if home.status is None and DNS_FAILURE.search(home.error or ""):
        issues.append(
            {
                "code": "DNS_UNRESOLVED",
                "severity": "critical" if was_reachable else "blocked",
                "detail": (
                    "имя перестало разрешаться: "
                    if was_reachable
                    else "имя не разрешается (домен ни разу не отвечал этой проверке): "
                )
                + home.error,
            }
        )
    elif home.status != 200:
        issues.append(
            {
                "code": "HOME_UNAVAILABLE",
                "severity": "critical",
                "detail": f"главная: {home.status or home.error}",
            }
        )
    elif home.elapsed > 5:
        issues.append(
            {
                "code": "HOME_SLOW",
                "severity": "warning",
                "detail": f"главная ответила за {home.elapsed:.1f} с",
            }
        )
    noindex = "noindex" in (header_robots + "," + result["meta_robots"]).lower()
    closed = noindex or bool(result["robots_disallow_all"])
    result["observed_indexing"] = None if home.status != 200 else ("CLOSED" if closed else "OPEN")
    desired = item.get("indexing_desired")
    if home.status == 200 and desired == "OPEN" and closed:
        issues.append(
            {
                "code": "INDEXING_MISMATCH",
                "severity": "critical",
                "detail": "состояние OPEN, а ответ запрещает индексацию "
                f"(X-Robots-Tag={header_robots!r}, meta={result['meta_robots']!r}, "
                f"Disallow: / = {result['robots_disallow_all']})",
            }
        )
    if home.status == 200 and result["home_canonical"]:
        host = re.sub(r"^https?://", "", result["home_canonical"]).split("/", 1)[0]
        if host and host != domain:
            issues.append(
                {
                    "code": "CANONICAL_FOREIGN_HOST",
                    "severity": "critical",
                    "detail": f"canonical главной указывает на {host}",
                }
            )
    # Привязка счётчика: на странице должен стоять ТОТ счётчик, что в реестре.
    # Чужой счётчик — данные домена уходят в отчёт другого сайта.
    on_page = sorted({int(x) for x in COUNTER_ON_PAGE.findall(home.body[:524288])})
    result["counters_on_page"] = on_page
    expected = item.get("counter_id")
    if home.status == 200 and expected:
        if on_page and expected not in on_page:
            issues.append(
                {
                    "code": "COUNTER_MISMATCH",
                    "severity": "critical",
                    "detail": f"в реестре {expected}, на главной {on_page}",
                }
            )
        elif not on_page:
            issues.append(
                {
                    "code": "COUNTER_NOT_ON_PAGE",
                    "severity": "warning",
                    "detail": f"счётчик {expected} из реестра на главной не найден",
                }
            )
    elif home.status == 200 and on_page and not expected:
        issues.append(
            {
                "code": "COUNTER_NOT_IN_REGISTRY",
                "severity": "warning",
                "detail": f"на главной счётчик {on_page}, в реестре аналитики его нет",
            }
        )
    if robots.status == 200 and not result["robots_sitemaps"] and desired == "OPEN":
        issues.append(
            {
                "code": "ROBOTS_WITHOUT_SITEMAP",
                "severity": "warning",
                "detail": "robots.txt не называет sitemap",
            }
        )
    return result


def analytics_freshness(snapshots_dir: Path, seen: dict, now: dt.datetime) -> dict:
    """Свежесть снимка и новизна наблюдения по каждому домену.

    `seen` — отпечатки, засчитанные раньше: {домен: {fingerprint, snapshot}}.
    Возвращает новые отпечатки отдельно, чтобы вызывающий сохранил их ТОЛЬКО
    после успешного шага.
    """
    files = sorted(snapshots_dir.glob("analytics-????-??-??.json"))
    if not files:
        return {
            "status": "MISSING",
            "reason": f"снимков нет в {snapshots_dir}",
            "domains": {},
            "seen_update": {},
        }
    latest = files[-1]
    data = _read_json(latest, {})
    collected = parse_iso(data.get("collected_at"))
    age_h = round((now - collected).total_seconds() / 3600, 1) if collected else None
    status = "FRESH" if age_h is not None and age_h <= 30 else "STALE"
    domains: dict[str, dict] = {}
    seen_update: dict[str, dict] = {}
    for entry in data.get("domains") or []:
        domain = entry.get("domain")
        values = {
            m.get("key"): m.get("value")
            for m in entry.get("measurements") or []
            if m.get("measured")
        }
        fingerprint = hashlib.sha256(
            json.dumps(values, sort_keys=True, ensure_ascii=False).encode()
        ).hexdigest()[:16]
        before = seen.get(domain) or {}
        if not values:
            observation = "NOT_MEASURED"
        elif before.get("fingerprint") == fingerprint:
            observation = "SAME_SNAPSHOT_REREAD"
        else:
            observation = "NEW_OBSERVATION"
            seen_update[domain] = {"fingerprint": fingerprint, "snapshot": latest.name}
        domains[domain] = {
            "observation": observation,
            "measured": len(values),
            "total": len(entry.get("measurements") or []),
        }
    return {
        "status": status,
        "snapshot": latest.name,
        "collected_at": data.get("collected_at"),
        "age_hours": age_h,
        "period": data.get("period"),
        "domains": domains,
        "seen_update": seen_update,
    }


def _text_fragment(body: str, size: int = 60) -> str:
    text = re.sub(r"\s+", " ", body or "").strip()
    return text[:size]


def _visible(html_bytes: bytes) -> str:
    text = html_bytes.decode("utf-8", "replace")
    text = re.sub(r"(?is)<(script|style)[^>]*>.*?</\1>", " ", text)
    text = re.sub(r"(?s)<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", html.unescape(text))


def _publish_times(history: Path) -> dict[str, str]:
    """Время последней публикации каждого slug по журналу хранилища."""
    out: dict[str, str] = {}
    try:
        lines = history.read_text(encoding="utf-8").splitlines()
    except OSError:
        return out
    for line in lines:
        try:
            rec = json.loads(line)
        except ValueError:
            continue
        if rec.get("op") == "publish" and rec.get("slug") and rec.get("at"):
            out[rec["slug"]] = rec["at"]
    return out


def published_items(roots: dict[str, tuple[Path, str]] | None = None) -> list[dict]:
    """Опубликованные материалы из хранилищ доставки. Только чтение.

    Описания карточек — `title-overlays.json`, новости — `editorial-posts.json`.
    Отпечаток тела нужен, чтобы проверять страницу заново только после правки.
    """
    out: list[dict] = []
    for family, (root, form) in (roots if roots is not None else OVERLAY_ROOTS).items():
        if not root.is_dir():
            continue
        for site_dir in sorted(p for p in root.iterdir() if p.is_dir()):
            domain = site_dir.name
            published = _publish_times(site_dir / "history.jsonl")
            overlays = _read_json(site_dir / "title-overlays.json", {})
            if not overlays.get("items"):
                # Доставка очередью (Lords/Zona): витрина читает editorial-overrides.json
                # сайта, а копия опубликованного в той же форме — published.json.
                overlays = _read_json(site_dir / "published.json", {})
            for entry in overlays.get("items") or []:
                slug, body = entry.get("slug"), entry.get("body") or ""
                if not slug or not body:
                    continue
                out.append(
                    {
                        "kind": "title_description",
                        "family": family,
                        "domain": domain,
                        "slug": slug,
                        "url": f"https://{domain}" + form.format(slug=slug),
                        "fragment": _text_fragment(body),
                        "digest": hashlib.sha256(body.encode()).hexdigest()[:16],
                        # Время ЭТОГО материала — из журнала публикаций. generated_at
                        # хранилища сдвигается при любой правке соседнего текста.
                        "published_at": published.get(slug),
                    }
                )
            posts = _read_json(site_dir / "editorial-posts.json", {})
            entries = posts.get("items") if isinstance(posts, dict) else posts
            for entry in entries or []:
                if not isinstance(entry, dict):
                    continue
                slug = entry.get("slug")
                body = entry.get("body") or entry.get("text") or ""
                if not slug or not body:
                    continue
                out.append(
                    {
                        "kind": "post",
                        "family": family,
                        "domain": domain,
                        "slug": slug,
                        "url": f"https://{domain}/posts/{slug}",
                        "fragment": _text_fragment(body),
                        "digest": hashlib.sha256(body.encode()).hexdigest()[:16],
                        "published_at": entry.get("published_at") or entry.get("updated_at"),
                    }
                )
    return out


def verify_publication(http: Http, item: dict) -> dict:
    """Фактический публичный результат: код ответа и видимый фрагмент текста."""
    resp = http.get(item["url"])
    visible = _visible(resp.body) if resp.status == 200 else ""
    fragment = item["fragment"]
    found = bool(fragment) and fragment in visible
    if resp.status != 200:
        verdict = "PAGE_NOT_200"
    elif not found:
        verdict = "TEXT_NOT_VISIBLE"
    else:
        verdict = "VISIBLE"
    return {
        "url": item["url"],
        "status": resp.status,
        "error": resp.error,
        "verdict": verdict,
        "digest": item["digest"],
        "checked_at": iso(utcnow()),
        "published_at": item.get("published_at"),
    }


# ---------------------------------------------------------- суточные шаги


SITEMAP_LOC = re.compile(rb"<loc>\s*([^<\s]+)\s*</loc>", re.IGNORECASE)
SITEMAP_LASTMOD = re.compile(rb"<lastmod>\s*([^<\s]+)\s*</lastmod>", re.IGNORECASE)


#: Sitemap собирается приложением по запросу: у Yummy холодная сборка
#: titles.xml шла дольше 45 с (три попытки по 15 с), тёплая — 0,3 с. Для
#: sitemap предел выше, а сама долгая отдача — находка, а не сбой проверки.
SITEMAP_TIMEOUT = 60.0
SITEMAP_SLOW_SECONDS = 10.0


def sitemap_snapshot(
    http: Http, domain: str, sitemap_urls: list[str], *, max_children: int = 8
) -> dict:
    """Число адресов, самая свежая дата lastmod и самая долгая отдача части."""
    start = sitemap_urls[0] if sitemap_urls else f"https://{domain}/sitemap.xml"
    index = http.get(start, timeout=SITEMAP_TIMEOUT)
    if index.status != 200:
        return {"status": "NOT_MEASURED", "reason": f"{start}: {index.status or index.error}"}
    body = index.body
    lastmods = [m.decode() for m in SITEMAP_LASTMOD.findall(body)]
    slowest = (start, index.elapsed)
    if b"<sitemapindex" in body[:2000]:
        children = [m.decode() for m in SITEMAP_LOC.findall(body)]
        urls = 0
        for child in children[:max_children]:
            part = http.get(child, timeout=SITEMAP_TIMEOUT)
            if part.status != 200:
                return {
                    "status": "NOT_MEASURED",
                    "reason": f"{child}: {part.status or part.error}",
                    "attempts": part.attempts,
                }
            if part.elapsed > slowest[1]:
                slowest = (child, part.elapsed)
            urls += len(SITEMAP_LOC.findall(part.body))
            lastmods += [m.decode() for m in SITEMAP_LASTMOD.findall(part.body)]
        truncated = len(children) > max_children
    else:
        urls = len(SITEMAP_LOC.findall(body))
        truncated = False
    dates = sorted(d for d in (parse_iso(x) for x in lastmods) if d)
    return {
        "status": "MEASURED",
        "urls": urls,
        "children_truncated": truncated,
        "max_lastmod": iso(dates[-1]) if dates else None,
        "lastmod_present": bool(dates),
        "slowest_url": slowest[0],
        "slowest_seconds": round(slowest[1], 2),
    }


def sitemap_findings(snap: dict, now: dt.datetime, *, max_age_days: int = 7) -> list[dict]:
    """Выводы из одного измерения: старый lastmod и долгая отдача."""
    out = []
    if snap.get("status") != "MEASURED":
        return out
    newest = parse_iso(snap.get("max_lastmod"))
    if newest and (now - newest).days > max_age_days:
        out.append(
            {
                "code": "SITEMAP_LASTMOD_OLD",
                "severity": "warning",
                "detail": f"самый свежий lastmod {snap['max_lastmod'][:10]} — "
                f"{(now - newest).days} дн. назад при {snap['urls']} адресах",
            }
        )
    if (snap.get("slowest_seconds") or 0) > SITEMAP_SLOW_SECONDS:
        out.append(
            {
                "code": "SITEMAP_SLOW",
                "severity": "warning",
                "detail": f"{snap['slowest_url']} отдан за {snap['slowest_seconds']} с",
            }
        )
    return out


def stalled_updates(history: dict, today: str, *, days: int = 3) -> dict | None:
    """Обновления остановились: адресов не прибавилось и lastmod не сдвинулся.

    `history` — {дата: снимок sitemap}. Нужны `days`+1 измеренных дней подряд,
    иначе вывод не делается: два одинаковых дня — ещё не остановка.
    """
    measured = [(d, h) for d, h in sorted(history.items()) if h.get("status") == "MEASURED"]
    window = [x for x in measured if x[0] <= today][-(days + 1) :]
    if len(window) < days + 1:
        return None
    counts = {h["urls"] for _, h in window}
    lastmods = {h.get("max_lastmod") for _, h in window}
    if len(counts) == 1 and len(lastmods) == 1:
        newest = window[-1][1].get("max_lastmod")
        return {
            "code": "UPDATES_STALLED",
            "severity": "warning",
            "detail": f"{window[0][0]}…{window[-1][0]}: адресов {window[-1][1]['urls']} без "
            f"изменений, самый свежий lastmod {newest or 'не указан'}",
        }
    return None


SEARCH_ENGINE_KEY = "search_engines"


def _rows(value: Any) -> dict[str, float]:
    out: dict[str, float] = {}
    for row in value if isinstance(value, list) else []:
        name = ((row.get("dimensions") or [{}])[0].get("name")) or "?"
        metric = (row.get("metrics") or [None])[0]
        if isinstance(metric, int | float):
            out[name] = out.get(name, 0.0) + metric
    return out


def _source_deltas(before: Any, now: Any) -> list[dict]:
    """Изменение визитов по источникам, крупнейшее по модулю первым.

    Без разложения «640 → 60» у animeg0.site читалось как потеря трафика, а
    это вышел из окна разовый всплеск «Cached page traffic» 447 → 0.
    """
    a, b = _rows(before), _rows(now)
    rows = [
        {
            "source": k,
            "before": a.get(k, 0.0),
            "now": b.get(k, 0.0),
            "delta": b.get(k, 0.0) - a.get(k, 0.0),
        }
        for k in sorted(set(a) | set(b))
    ]
    return sorted(rows, key=lambda r: -abs(r["delta"]))


def _metric(entry: dict | None, key: str) -> tuple[bool, Any, str]:
    for m in (entry or {}).get("measurements") or []:
        if m.get("key") == key:
            return bool(m.get("measured")), m.get("value"), m.get("reason") or ""
    return False, None, "показателя нет в снимке"


def _search_visits(value: Any) -> float | None:
    if not isinstance(value, list):
        return None
    total = 0.0
    for row in value:
        metrics = row.get("metrics") or []
        if metrics and isinstance(metrics[0], int | float):
            total += metrics[0]
    return total


def week_over_week(snapshots_dir: Path, today: dt.date) -> dict:
    """Сравнение НЕПЕРЕКРЫВАЮЩИХСЯ окон: снимок дня D против снимка D-7.

    Окно снимка — «7daysAgo…yesterday», то есть дни D-7…D-1; у снимка D-7 —
    D-14…D-8. Пересечения нет, и разность — настоящее изменение.
    Отсутствие показателя в одном из окон даёт «не измерено» с причиной, а не 0.
    """
    current = snapshots_dir / f"analytics-{today:%Y-%m-%d}.json"
    base_day = today - dt.timedelta(days=7)
    base = snapshots_dir / f"analytics-{base_day:%Y-%m-%d}.json"
    if not current.is_file():
        files = sorted(snapshots_dir.glob("analytics-????-??-??.json"))
        if not files:
            return {"status": "NOT_MEASURED", "reason": "снимков нет", "domains": {}}
        current = files[-1]
        base_day = dt.date.fromisoformat(current.name[10:20]) - dt.timedelta(days=7)
        base = snapshots_dir / f"analytics-{base_day:%Y-%m-%d}.json"
    cur = {d["domain"]: d for d in _read_json(current, {}).get("domains") or []}
    if not base.is_file():
        return {
            "status": "NOT_MEASURED",
            "current": current.name,
            "reason": f"снимка {base.name} нет — непересекающейся недели для сравнения нет",
            "domains": {},
        }
    old = {d["domain"]: d for d in _read_json(base, {}).get("domains") or []}
    from factory.analytics.collected import разрешить_период

    cur_raw, old_raw = _read_json(current, {}), _read_json(base, {})
    out: dict[str, dict] = {}
    for domain in sorted(set(cur) | set(old)):
        row: dict[str, Any] = {}
        for key in ("visits", "visitors"):
            ok_new, new, why_new = _metric(cur.get(domain), key)
            ok_old, was, why_old = _metric(old.get(domain), key)
            if ok_new and ok_old:
                row[key] = {"now": new, "before": was, "delta": round(new - was, 2)}
            else:
                row[key] = {"not_measured": why_new if not ok_new else why_old}
        ok_new, new, why_new = _metric(cur.get(domain), SEARCH_ENGINE_KEY)
        ok_old, was, why_old = _metric(old.get(domain), SEARCH_ENGINE_KEY)
        if ok_new and ok_old:
            a, b = _search_visits(new), _search_visits(was)
            row["search_visits"] = {
                "now": a,
                "before": b,
                "delta": None if a is None or b is None else round(a - b, 2),
            }
        else:
            row["search_visits"] = {"not_measured": why_new if not ok_new else why_old}
        ok_new, new, _ = _metric(cur.get(domain), "traffic_sources")
        ok_old, was, _ = _metric(old.get(domain), "traffic_sources")
        if ok_new and ok_old:
            row["sources"] = _source_deltas(was, new)
        out[domain] = row
    return {
        "status": "MEASURED",
        "current": current.name,
        "base": base.name,
        "current_period": разрешить_период(
            cur_raw.get("period") or {}, cur_raw.get("collected_at") or ""
        ),
        "base_period": разрешить_период(
            old_raw.get("period") or {}, old_raw.get("collected_at") or ""
        ),
        "domains": out,
    }


def _absolute(url: str, site: str | None) -> str:
    if url.startswith("/") and site:
        return f"https://{site}{url}"
    return url


def _url_key(url: str) -> str:
    return url.rstrip("/").lower()


#: Что умеет семейство витрин (factory.qwen.registry.ВОЗМОЖНОСТИ_АДАПТЕРА):
#: без доставки описание карточки опубликовать нельзя, без фактов — не из чего
#: писать. Семейство определяется по префиксу site_id реестра ячеек.
FAMILY_CAN = {
    "animedia": {"facts", "deliver", "display"},
    "yummy": {"deliver"},
    "lords": {"facts"},
    "animego": {"facts"},
    "zona": set(),
}


def family_of(site: str, cells: dict[str, str]) -> str:
    site_id = cells.get(site, "")
    for family in FAMILY_CAN:
        if site_id.startswith(family):
            return family
    return "?"


def editor_process(
    events_path: Path, registry_path: Path, cells: dict[str, str], *, since: dt.datetime
) -> dict:
    """Где теряется работа редактора: выдачи без результата, повторы, тупиковые задания."""
    claims: dict[str, int] = {}
    results: dict[str, int] = {}
    outcomes: dict[str, int] = {}
    site_of: dict[str, str] = {}
    gate: dict[str, int] = {}
    if events_path.is_file():
        for line in events_path.read_text(encoding="utf-8").splitlines():
            try:
                e = json.loads(line)
            except ValueError:
                continue
            if e.get("task_id") and e.get("site"):
                site_of[e["task_id"]] = e["site"]
            moment = parse_iso(e.get("at"))
            if not moment or moment < since:
                continue
            if e.get("event") == "task_claimed":
                claims[e["task_id"]] = claims.get(e["task_id"], 0) + 1
            elif e.get("event") == "task_result":
                results[e["task_id"]] = results.get(e["task_id"], 0) + 1
                fam = family_of(site_of.get(e["task_id"], ""), cells)
                key = f"{fam}:{e.get('outcome')}"
                outcomes[key] = outcomes.get(key, 0) + 1
                status = (e.get("gate") or {}).get("status")
                if e.get("outcome") == "TEXT_WRITTEN" and status:
                    gate[status] = gate.get(status, 0) + 1
    registry = _read_json(registry_path, {})
    items = registry.get("items") or []
    if isinstance(items, dict):
        items = list(items.values())
    finished = {
        "PUBLISHED",
        "ALREADY_LIVE",
        "DUPLICATE",
        "SUPPRESSED_NEAR_DUPLICATE",
        "NEAR_DUPLICATE",
        "READY_VERIFIED",
    }
    dead_end = []
    for item in items:
        site = item.get("target_site") or ""
        fam = family_of(site, cells)
        if item.get("status") in finished or fam == "?":
            continue
        if (
            item.get("content_type") in (None, "TITLE_DESCRIPTION")
            and "deliver" not in FAMILY_CAN[fam]
        ):
            dead_end.append(
                {
                    "content_id": item.get("content_id"),
                    "site": site,
                    "family": fam,
                    "status": item.get("status"),
                }
            )
    looping = sorted(
        (
            (t, n, results.get(t, 0), site_of.get(t))
            for t, n in claims.items()
            if n >= 5 and results.get(t, 0) * 3 < n
        ),
        key=lambda x: -x[1],
    )
    total_claims, total_results = sum(claims.values()), sum(results.values())
    return {
        "since": iso(since),
        "claims": total_claims,
        "results": total_results,
        "claims_without_result": total_claims - total_results,
        "outcomes": dict(sorted(outcomes.items())),
        "text_gate": gate,
        "looping": [
            {"task_id": t, "claims": n, "results": r, "site": s} for t, n, r, s in looping[:10]
        ],
        "dead_end_tasks": dead_end,
    }


def queue_hygiene(registry_path: Path, events_path: Path, *, since: dt.datetime) -> dict:
    """Дубли и неверные адреса заданий, пересечение ролей. Только чтение.

    * одна страница — несколько ЖИВЫХ заданий (адрес относительный и
      абсолютный, со слешем и без);
    * задание заведено на относительный адрес — его нельзя проверить на сайте;
    * задание SEO-стороны взято SEO-владельцем — конкурент редактору.
    """
    registry = _read_json(registry_path, {})
    items = registry.get("items") or []
    if isinstance(items, dict):
        items = list(items.values())
    done = {"PUBLISHED", "ALREADY_LIVE", "DUPLICATE", "SUPPRESSED_NEAR_DUPLICATE", "NEAR_DUPLICATE"}
    by_key: dict[str, list[dict]] = {}
    relative: list[dict] = []
    for item in items:
        url = str(item.get("canonical_url") or "")
        if not url:
            continue
        site = item.get("target_site")
        if url.startswith("/"):
            relative.append(
                {
                    "content_id": item.get("content_id"),
                    "site": site,
                    "url": url,
                    "status": item.get("status"),
                }
            )
        if item.get("status") in done:
            continue
        by_key.setdefault(_url_key(_absolute(url, site)), []).append(
            {"content_id": item.get("content_id"), "url": url, "status": item.get("status")}
        )
    duplicates = []
    for key, tasks in sorted(by_key.items()):
        ids = [str(t["content_id"]) for t in tasks]
        # Правка записи (`buffer-<id>-rev1` к `<id>`) — цепочка версий одной
        # записи, а не второе задание на страницу.
        roots = [i for i in ids if not any(i != j and i in j for j in ids)]
        if len(roots) > 1:
            duplicates.append({"page": key, "tasks": tasks})

    seo_claims: list[dict] = []
    registered_recent: list[dict] = []
    owners_per_url: dict[str, set] = {}
    if events_path.is_file():
        for line in events_path.read_text(encoding="utf-8").splitlines():
            try:
                event = json.loads(line)
            except ValueError:
                continue
            moment = parse_iso(event.get("at"))
            if not moment or moment < since:
                continue
            if event.get("event") == "task_registered":
                registered_recent.append(
                    {
                        "content_id": event.get("content_id") or event.get("task_id"),
                        "site": event.get("site"),
                        "url": str(event.get("canonical_url") or ""),
                        "status": event.get("status"),
                    }
                )
            if event.get("event") != "task_claimed":
                continue
            owner = str(event.get("owner") or "")
            owners_per_url.setdefault(str(event.get("canonical_url")), set()).add(owner)
            if SEO_OWNER_PATTERN.search(owner):
                seo_claims.append(
                    {
                        "at": event.get("at"),
                        "owner": owner,
                        "task_id": event.get("task_id"),
                        "url": event.get("canonical_url"),
                    }
                )
    contested = sum(1 for owners in owners_per_url.values() if len(owners) > 1)
    return {
        "live_duplicates": duplicates,
        "relative_urls": relative,
        "registered_recent": registered_recent,
        "seo_side_claims": seo_claims,
        "urls_claimed": len(owners_per_url),
        "urls_claimed_by_several_owners": contested,
        "since": iso(since),
    }


def verify_task_targets(http: Http, hygiene: dict, *, limit: int = 20) -> list[dict]:
    """Целевая страница задания существует? 404 — задание неверно заведено."""
    out = []
    seen: set[str] = set()
    candidates = (hygiene.get("registered_recent") or []) + (hygiene.get("relative_urls") or [])
    for task in candidates[:limit]:
        url = _absolute(task["url"], task.get("site"))
        if url in seen or not url.startswith("https://"):
            continue
        seen.add(url)
        resp = http.get(url)
        out.append(
            {
                "content_id": task["content_id"],
                "url": url,
                "status": resp.status,
                "task_status": task.get("status"),
            }
        )
    return out


# ------------------------------------------- изменение -> исходные -> оценка


def page_metrics(snapshot: Path, domain: str, url: str) -> dict:
    """Показатели страницы и домена из ОДНОГО снимка.

    Разбивки по страницам — первые N строк. Страница вне списка получает
    «вне первых N», а не 0: её трафик неизвестен, а не нулевой.
    """
    data = _read_json(snapshot, {})
    entry = next((d for d in data.get("domains") or [] if d.get("domain") == domain), None)
    path = urllib.parse.urlsplit(url).path.rstrip("/") or "/"
    out: dict[str, Any] = {"snapshot": snapshot.name, "collected_at": data.get("collected_at")}
    if entry is None:
        out["not_measured"] = "домена нет в снимке"
        return out
    for key in ("landing_pages", "popular_pages"):
        ok, value, reason = _metric(entry, key)
        if not ok:
            out[key] = {"not_measured": reason}
            continue
        top_n = (
            next((m.get("top_n") for m in entry["measurements"] if m.get("key") == key), None) or 20
        )
        hit = None
        for row in value or []:
            name = ((row.get("dimensions") or [{}])[0].get("name") or "").rstrip("/") or "/"
            if name == path:
                hit = (row.get("metrics") or [None])[0]
                break
        out[key] = {"value": hit} if hit is not None else {"outside_top_n": top_n}
    ok, visits, reason = _metric(entry, "visits")
    out["domain_visits"] = visits if ok else {"not_measured": reason}
    ok, engines, reason = _metric(entry, SEARCH_ENGINE_KEY)
    out["domain_search_visits"] = _search_visits(engines) if ok else {"not_measured": reason}
    return out


def _baseline(snaps: list[Path], domain: str, url: str, published_at: str | None) -> dict:
    """Исходные показатели — из последнего снимка, окно которого кончилось ДО
    публикации (снимок дня D покрывает дни по D-1). Снимка до публикации нет —
    исходных нет, и это говорится, а не подменяется снимком «после»."""
    moment = parse_iso(published_at)
    if moment is None:
        return {"not_measured": "время публикации неизвестно"}
    day = moment.astimezone(MSK).date()
    before = [f for f in snaps if dt.date.fromisoformat(f.name[10:20]) <= day]
    if not before:
        return {"not_measured": f"снимка аналитики на {day} или раньше нет"}
    return page_metrics(before[-1], domain, url)


#: Проверки эффекта: через 7 и 14 дней после публикации.
HORIZONS = (7, 14)
#: Меньше этого числа входов на страницу в обоих окнах — данных мало, вывод не делается.
MIN_VOLUME = 10
#: Расхождение страницы с доменом, после которого изменение называется.
CLEAR_SHIFT = 0.3


def _page_value(metrics: dict) -> tuple[float | None, str]:
    cell = (metrics or {}).get("landing_pages") or {}
    if "value" in cell:
        return float(cell["value"]), ""
    if "outside_top_n" in cell:
        return None, f"страница вне первых {cell['outside_top_n']} входных"
    return None, cell.get("not_measured") or (metrics or {}).get("not_measured") or "не измерено"


def judge(baseline: dict, after: dict, control: tuple[dict, dict] | None = None) -> dict:
    """Вердикт по двум сопоставимым 7-дневным окнам с поправкой на домен.

    Поправка на спрос и прочие изменения сайта — грубая, но честная: изменение
    страницы сравнивается с изменением всего домена за те же окна. Вердикт —
    наблюдение; причину правки он не доказывает.
    """
    before_v, why_b = _page_value(baseline)
    after_v, why_a = _page_value(after)
    if before_v is None or after_v is None:
        return {"verdict": "NOT_MEASURABLE", "reason": why_b or why_a}
    if max(before_v, after_v) < MIN_VOLUME:
        return {
            "verdict": "INSUFFICIENT_VOLUME",
            "before": before_v,
            "after": after_v,
            "reason": f"входов меньше {MIN_VOLUME} в обоих окнах — проверить позже",
        }
    dom_b, dom_a = baseline.get("domain_visits"), after.get("domain_visits")
    page_change = (after_v - before_v) / before_v if before_v else None
    dom_change = (
        ((dom_a - dom_b) / dom_b)
        if isinstance(dom_a, int | float) and isinstance(dom_b, int | float) and dom_b
        else None
    )
    out = {
        "before": before_v,
        "after": after_v,
        "page_change": page_change,
        "domain_change": dom_change,
    }
    if page_change is None or dom_change is None:
        out.update(verdict="NOT_MEASURABLE", reason="нет исходного значения страницы или домена")
        return out
    excess = page_change - dom_change
    out["excess_over_domain"] = round(excess, 3)
    if control is not None:
        cb, _ = _page_value(control[0])
        ca, _ = _page_value(control[1])
        if cb and ca is not None:
            out["control_change"] = (ca - cb) / cb
            # Сдвиг засчитывается, только если он есть и относительно домена, и
            # относительно контроля: иначе это спрос на тайтл, а не правка.
            excess = min(excess, page_change - out["control_change"], key=abs)
            out["excess_over_control"] = round(page_change - out["control_change"], 3)
        else:
            out["control_note"] = "контроль не измерен — вывод только относительно домена"
    out["verdict"] = (
        "REGRESSION_SUSPECTED"
        if excess <= -CLEAR_SHIFT
        else "GAIN_OBSERVED"
        if excess >= CLEAR_SHIFT
        else "NO_CLEAR_CHANGE"
    )
    return out


def evaluate_changes(
    changes: dict, snapshots_dir: Path, controls: dict[str, str] | None = None
) -> list[dict]:
    """Проверки через 7 и 14 дней по окнам, которые не задевают день публикации.

    Исходное окно кончается не позже дня до публикации (снимок дня D покрывает
    D-7…D-1). Окно «+h» — снимок дня публикации + h + 1, то есть дни
    публикация + h - 6 … публикация + h. Нет такого снимка — проверка ждёт.
    """
    files = {f.name[10:20]: f for f in snapshots_dir.glob("analytics-????-??-??.json")}
    out = []
    for url, change in sorted(changes.items()):
        published = parse_iso(change.get("published_at"))
        if not published or not (change.get("baseline") or {}).get("snapshot"):
            continue
        day = published.astimezone(MSK).date()
        for h in HORIZONS:
            if change.get(f"evaluation_{h}"):
                continue
            target = day + dt.timedelta(days=h + 1)
            ready = sorted(d for d in files if dt.date.fromisoformat(d) >= target)
            if not ready:
                continue
            after = page_metrics(files[ready[0]], change["domain"], url)
            control = None
            control_url = (controls or {}).get(url)
            if control_url:
                host = urllib.parse.urlsplit(control_url).hostname or ""
                control = (
                    page_metrics(files[change["baseline"]["snapshot"][10:20]], host, control_url)
                    if change["baseline"]["snapshot"][10:20] in files
                    else {},
                    page_metrics(files[ready[0]], host, control_url),
                )
            out.append(
                {
                    "url": url,
                    "horizon": h,
                    "baseline": change["baseline"],
                    "after": after,
                    **judge(change["baseline"], after, control),
                    "control_url": control_url,
                    "note": (
                        "наблюдение по сопоставимым окнам с "
                        "поправкой на домен; причину не доказывает"
                    ),
                }
            )
    return out


# ---------------------------------------------------------------- отчёт


def optimization_candidates(visited: dict, *, limit: int = 15) -> dict:
    """Посещаемые страницы с находками аудита, самые посещаемые первыми.

    Находки уровня info (длинный title, нет описания) идут после warning:
    их правка возможна, но основание слабее.
    """
    rows = []
    for v in visited.get("checked") or []:
        audit = v.get("audit") or {}
        found = [f for f in audit.get("findings") or [] if f["severity"] != "info"]
        info = [f for f in audit.get("findings") or [] if f["severity"] == "info"]
        if found or info:
            rows.append(
                {
                    "url": v["url"],
                    "weight": v.get("weight") or 0,
                    "findings": found + info,
                    "strong": bool(found),
                }
            )
    rows.sort(key=lambda r: (not r["strong"], -r["weight"]))
    return {
        "pages": rows[:limit],
        "total": len(rows),
        "duplicate_titles": visited.get("duplicate_titles") or [],
    }


def changes_section(
    ledger_path: Path, state: dict, today: dt.date, extra: Path | None = None
) -> dict:
    """Пять разделов: написано, оптимизировано, опубликовано и проверено,
    эффект пока не установлен, результат измерен."""
    ledger = list(_read_json(ledger_path, {}).get("changes") or [])
    runs = (
        ledger_path.parent.parent / "var" / "editor-runs" / "ledger.jsonl"
        if extra is None
        else extra
    )
    if runs.is_file():
        for line in runs.read_text(encoding="utf-8").splitlines():
            try:
                row = json.loads(line)
            except ValueError:
                continue
            if row.get("url") and row.get("kind") in ("written", "optimized"):
                ledger.append({"element": "description", "published_at": "", **row})
    measured_state = state.get("changes") or {}
    publications = state.get("publications") or {}
    out: dict[str, list] = {
        "written": [],
        "optimized": [],
        "verified": [],
        "effect_pending": [],
        "measured": [],
    }
    for c in ledger:
        row = {
            "id": c["id"],
            "url": c["url"],
            "element": c["element"],
            "published_at": c["published_at"],
            "decision": c.get("decision", "pending"),
        }
        out["written" if c["kind"] == "written" else "optimized"].append(row)
        pub = publications.get(c["url"]) or {}
        if pub.get("verdict") == "VISIBLE":
            out["verified"].append({**row, "checked_at": pub.get("checked_at")})
        st = measured_state.get(c["url"]) or {}
        evals = {h: st.get(f"evaluation_{h}") for h in HORIZONS if st.get(f"evaluation_{h}")}
        done = {
            h: e
            for h, e in evals.items()
            if e.get("verdict") in ("GAIN_OBSERVED", "NO_CLEAR_CHANGE", "REGRESSION_SUSPECTED")
        }
        if done:
            out["measured"].append({**row, "evaluations": done})
        else:
            published = parse_iso(c["published_at"])
            due = (
                [str(published.astimezone(MSK).date() + dt.timedelta(days=h + 1)) for h in HORIZONS]
                if published
                else []
            )
            reason = (
                "; ".join(
                    f"+{h}: {e.get('verdict')} ({e.get('reason', '')})" for h, e in evals.items()
                )
                or f"данных ещё нет: снимки для проверки +7/+14 — {', '.join(due)}"
            )
            out["effect_pending"].append(
                {**row, "reason": reason, "baseline": (st.get("baseline") or {}).get("snapshot")}
            )
    out["without_ledger"] = sorted(set(measured_state) - {c["url"] for c in ledger})
    return out


def module_section(defects_path: Path) -> dict:
    """«SEO-модуль: найдено → исправлено → проверено → осталось»."""
    data = _read_json(defects_path, {})
    items = data.get("defects") or []
    states = {"proposed": 0, "implemented": 0, "installed": 0, "verified": 0}
    for item in items:
        states[item.get("state", "proposed")] = states.get(item.get("state", "proposed"), 0) + 1
    remaining = [i for i in items if i.get("state") != "verified"]
    remaining.sort(key=lambda i: (i.get("priority", "P9"), i.get("id", "")))
    return {
        "found": len(items),
        "states": states,
        "fixed": states["implemented"] + states["installed"] + states["verified"],
        "verified": states["verified"],
        "remaining": [
            {
                "id": i.get("id"),
                "priority": i.get("priority"),
                "state": i.get("state"),
                "title": i.get("title"),
                "zone": i.get("zone"),
            }
            for i in remaining
        ],
    }


def _fmt_metric(row: dict) -> str:
    if "not_measured" in row:
        return f"не измерено ({row['not_measured']})"
    now, before, delta = row.get("now"), row.get("before"), row.get("delta")
    if now is None or before is None:
        return "не измерено (значение не разобрано)"
    return f"{now:g} (было {before:g}, {delta:+g})"


#: Единый файл последнего суточного отчёта — перезаписывается каждым прогоном.
LATEST_MD = "var/seo-regular/reports/LATEST.md"


def editor_day(state_dir: Path, since: dt.datetime) -> dict:
    """Работа фонового редактора за сутки: публикации с источниками, ошибки.

    Источники берутся из журнала обращений source_fetch.py в окне запуска —
    то, что действительно прочитано, а не то, что заявлено в ответе модели.
    """
    runs, sources = [], []
    try:
        for line in (state_dir / "runs.jsonl").read_text(encoding="utf-8").splitlines():
            r = json.loads(line)
            if (parse_iso(r.get("finished_at")) or since) >= since:
                runs.append(r)
    except (OSError, ValueError):
        pass
    try:
        sources = [
            json.loads(x)
            for x in (state_dir / "sources.jsonl").read_text(encoding="utf-8").splitlines()
            if x
        ]
    except (OSError, ValueError):
        sources = []
    published, problems = [], []
    for r in runs:
        try:
            v = json.loads((state_dir / f"{r['run_id']}.verify.json").read_text(encoding="utf-8"))
        except (OSError, ValueError):
            v = {"publications": []}
        # Источник засчитывается публикации, только если прочитан в ЕЁ окне:
        # от предыдущей публикации этого запуска (или его начала) до неё.
        # Окно всего запуска приписывало одной странице источники другой.
        pubs = sorted(v.get("publications") or [], key=lambda x: x.get("at", ""))
        window_start = r["started_at"]
        for pub in pubs:
            read = sorted(
                {
                    src.get("url")
                    for src in sources
                    if window_start <= src.get("at", "") <= pub.get("at", r["finished_at"])
                    and src.get("status") == 200
                }
            )
            published.append(
                {
                    "url": pub["url"],
                    "at": pub.get("at"),
                    "run_id": r["run_id"],
                    "trigger": r.get("trigger"),
                    "sources": read or ["только каталог сети (внешних обращений нет)"],
                }
            )
            window_start = pub.get("at", window_start)
        # Вердикт — по файлу проверки, если он перепроверен позже запуска: проверка
        # 2026-10-09 не видела доставку очередью (Lords/Zona) и записала полные
        # запуски неполными; пересчёт штатной командой исправляет файл проверки.
        if v.get("complete") is True:
            r["verdict"] = "COMPLETE"
        if r.get("verdict") != "COMPLETE":
            note = (r.get("self_report") or {}).get("note") or ""
            problems.append(
                {"run_id": r["run_id"], "verdict": r.get("verdict"), "note": note[:300]}
            )
    verdicts: dict[str, int] = {}
    for r in runs:
        verdicts[r.get("verdict", "?")] = verdicts.get(r.get("verdict", "?"), 0) + 1
    return {"runs": len(runs), "verdicts": verdicts, "published": published, "problems": problems}


def published_since(since: dt.datetime, roots: dict | None = None) -> list[dict]:
    """Что фактически опубликовано на сайтах за период — по истории хранилищ."""
    out = []
    for _family, (root, form) in (roots if roots is not None else OVERLAY_ROOTS).items():
        if not root.is_dir():
            continue
        for site_dir in sorted(root.iterdir()):
            history = site_dir / "history.jsonl"
            if not history.is_file():
                continue
            for line in history.read_text(encoding="utf-8").splitlines():
                try:
                    rec = json.loads(line)
                except ValueError:
                    continue
                at = parse_iso(rec.get("at"))
                if rec.get("op") == "publish" and at and at >= since:
                    url = f"https://{site_dir.name}" + form.format(slug=rec["slug"])
                    out.append({"url": url, "at": rec["at"], "author": rec.get("author")})
    # Одна страница — одна строка: последняя публикация за период.
    last: dict[str, dict] = {}
    for row in sorted(out, key=lambda r: r["at"]):
        last[row["url"]] = row
    return sorted(last.values(), key=lambda r: r["at"])


def publication_metrics(
    since: dt.datetime,
    verdicts: dict[str, dict],
    roots: dict | None = None,
) -> dict[str, dict]:
    """Итоги публикаций за период по доменам — четыре разных числа, не одно.

    * new_texts — страницы, получившие текст ВПЕРВЫЕ (раньше периода публикаций
      этого слага на домене не было), с текстом, которого нет больше нигде в сети;
    * urls — разные адреса, где за период был publish;
    * edits — повторные publish: правка уже опубликованного или второй за период;
    * visible — адреса, где ТЕКУЩИЙ текст подтверждён на странице (VISIBLE с тем же
      отпечатком); not_visible — проверено и не видно; unchecked — ещё не проверялось.
      Переклассификация ошибки исправлением не считается: только вердикт страницы.
    """
    events: list[dict] = []
    digests_all: dict[str, set[str]] = {}
    for _family, (root, form) in (roots if roots is not None else OVERLAY_ROOTS).items():
        if not root.is_dir():
            continue
        for site_dir in sorted(root.iterdir()):
            history = site_dir / "history.jsonl"
            if not history.is_file():
                continue
            for line in history.read_text(encoding="utf-8").splitlines():
                try:
                    rec = json.loads(line)
                except ValueError:
                    continue
                if rec.get("op") != "publish" or not rec.get("slug"):
                    continue
                url = f"https://{site_dir.name}" + form.format(slug=rec["slug"])
                digest = str(rec.get("body_digest") or "")[:16]
                if digest:
                    digests_all.setdefault(digest, set()).add(url)
                events.append(
                    {
                        "domain": site_dir.name,
                        "url": url,
                        "at": parse_iso(rec.get("at")),
                        "digest": digest,
                    }
                )
    out: dict[str, dict] = {}
    seen_before = {(e["domain"], e["url"]) for e in events if e["at"] and e["at"] < since}
    window = sorted((e for e in events if e["at"] and e["at"] >= since), key=lambda e: e["at"])
    last_digest: dict[str, str] = {}
    for e in window:
        row = out.setdefault(
            e["domain"],
            {
                "new_texts": [],
                "urls": [],
                "edits": 0,
                "visible": [],
                "not_visible": [],
                "unchecked": [],
            },
        )
        first_here = (e["domain"], e["url"]) not in seen_before and e["url"] not in row["urls"]
        if first_here:
            row["urls"].append(e["url"])
            if len(digests_all.get(e["digest"], set())) <= 1:
                row["new_texts"].append(e["url"])
        else:
            if e["url"] not in row["urls"]:
                row["urls"].append(e["url"])
            row["edits"] += 1
        last_digest[e["url"]] = e["digest"]
    for row in out.values():
        for url in row["urls"]:
            v = verdicts.get(url) or {}
            if not last_digest.get(url) or v.get("digest") != last_digest[url]:
                row["unchecked"].append(url)
            elif v.get("verdict") == "VISIBLE":
                row["visible"].append(url)
            else:
                row["not_visible"].append(url)
    return out


#: Через сколько видимый и неизменный текст перепроверяется на странице. Меньше
#: интервала проверок (6 ч): каждая проверка сети перепроверяет все видимые
#: тексты, и утренняя (05:25) видит итог ночной доставки каталога (03:30).
RECHECK_VISIBLE_AFTER = dt.timedelta(hours=5)

AUDIENCE_TARGET = 1000
_ROBOT_YES = {"yes", "1", "true", "роботы", "robots"}
_ROBOT_NO = {"no", "0", "false", "люди", "people", "humans"}


def _robot_flag(dim: dict) -> bool | None:
    for raw in (dim.get("id"), dim.get("name")):
        val = str(raw).strip().lower() if raw is not None else ""
        if val in _ROBOT_YES:
            return True
        if val in _ROBOT_NO:
            return False
    return None


def audience_goal(snapshot: Path | None) -> dict:
    """Пользователи в день против цели 1000 — по последнему снимку аналитики.

    Есть `daily_users` (дата × признак робота) — считаются только люди: последний
    полный день и среднее по дням окна. Нет — строгие границы среднего:
    не меньше users₇/7 и не больше visits₇/7 (роботы при этом не исключены).
    Значение признака робота, которое не распознано, не угадывается.
    """
    if snapshot is None:
        return {}
    data = _read_json(snapshot, {})
    out: dict[str, dict] = {"_snapshot": {"name": snapshot.name, "period": data.get("period")}}
    for entry in data.get("domains") or []:
        domain = entry.get("domain")
        m = {x.get("key"): x for x in entry.get("measurements") or []}
        daily = m.get("daily_users") or {}
        if daily.get("measured") and isinstance(daily.get("value"), list):
            humans: dict[str, float] = {}
            unknown = set()
            for row in daily["value"]:
                dims = row.get("dimensions") or [{}, {}]
                day = str((dims[0] or {}).get("name") or "")
                flag = _robot_flag(dims[1] if len(dims) > 1 else {})
                if flag is None:
                    unknown.add(str((dims[1] if len(dims) > 1 else {}).get("name")))
                    continue
                if not flag:
                    humans[day] = humans.get(day, 0.0) + float((row.get("metrics") or [0])[0])
            if unknown and not humans:
                out[domain] = {"not_measured": f"признак робота не распознан: {sorted(unknown)}"}
                continue
            if humans:
                last_day = max(humans)
                last = humans[last_day]
                avg = sum(humans.values()) / len(humans)
                out[domain] = {
                    "kind": "daily",
                    "last_day": last_day,
                    "last": last,
                    "avg": avg,
                    "days": len(humans),
                    "gap": max(0.0, AUDIENCE_TARGET - last),
                }
                continue
        users, visits = m.get("visitors") or {}, m.get("visits") or {}
        if users.get("measured") and visits.get("measured"):
            lo, hi = float(users["value"]) / 7, float(visits["value"]) / 7
            out[domain] = {
                "kind": "bounds",
                "low": lo,
                "high": hi,
                "gap_low": max(0.0, AUDIENCE_TARGET - hi),
                "gap_high": max(0.0, AUDIENCE_TARGET - lo),
            }
        else:
            out[domain] = {"not_measured": users.get("reason") or "нет данных"}
    return out


def owner_needs(defects_path: Path) -> list[str]:
    """Что требуется от владельца: открытые пункты зоны владельца."""
    items = _read_json(defects_path, {}).get("defects") or []
    return [
        f"{i['id']}: {i['title']}"
        for i in items
        if i.get("zone") == "owner" and i.get("state") not in ("verified",)
    ]


def delivery_status(saved_as: str) -> dict:
    """Доставки владельцу нет: канал Telegram отменён владельцем 2026-10-08.

    Сохранённый файл доставкой не считается — отчёт лежит для чтения по
    запросу, и строка отчёта говорит именно это.
    """
    return {
        "state": "не выполняется — канал доставки отменён владельцем",
        "detail": f"отчёт сохранён для чтения по запросу: {saved_as} (последний — {LATEST_MD})",
    }


def notable_changes(wow: dict, *, share: float = 0.3, minimum: float = 20) -> list[dict]:
    out = []
    for domain, row in (wow.get("domains") or {}).items():
        for metric in ("visits", "search_visits"):
            cell = row.get(metric) or {}
            now, before = cell.get("now"), cell.get("before")
            if now is None or before is None or not before:
                continue
            change = (now - before) / before
            if abs(change) >= share and abs(now - before) >= minimum:
                main = (row.get("sources") or [None])[0] if metric == "visits" else None
                out.append(
                    {
                        "domain": domain,
                        "metric": metric,
                        "now": now,
                        "before": before,
                        "share": change,
                        "main_source": main,
                    }
                )
    return sorted(out, key=lambda n: n["share"])


def _plain(value: Any) -> str:
    if isinstance(value, dict):
        return f"не измерено ({value.get('not_measured')})"
    return "—" if value is None else f"{value:g}"


def _page_cell(metrics: dict, key: str) -> str:
    cell = (metrics or {}).get(key) or {}
    if "value" in cell:
        return f"{cell['value']:g}"
    if "outside_top_n" in cell:
        return f"вне первых {cell['outside_top_n']}"
    return f"не измерено ({cell.get('not_measured', metrics.get('not_measured'))})"


def render_daily(report: dict) -> str:
    lines: list[str] = []
    add = lines.append
    add(f"# SEO-сеть: отчёт владельцу — {report['date_msk']}")
    add("")
    add("## Кратко")
    pubs = report.get("published_24h") or []
    # Источники — только у той же публикации (URL и время совпадают); правки из
    # сессии редактора описаны в журнале изменений config/seo-changes.json.
    src = {
        (p["url"], p.get("at")): p["sources"]
        for p in (report.get("editor") or {}).get("published") or []
    }
    pm = report.get("publication_metrics") or {}

    def total(key: str) -> int:
        return sum(len(r[key]) if isinstance(r[key], list) else r[key] for r in pm.values())

    add(
        f"**Публикации за сутки: новых уникальных текстов {total('new_texts')}, "
        f"адресов {total('urls')}, повторных правок {total('edits')}; видимость "
        f"подтверждена {total('visible')}, не видно {total('not_visible')}, "
        f"не проверено {total('unchecked')}**"
    )
    for pub in pubs:
        key = (pub["url"], pub["at"])
        if key in src:
            where = "; источники: " + ", ".join(src[key])
        elif str(pub.get("author", "")).startswith("editor/claude-indexing"):
            where = "; источники и основание — config/seo-changes.json"
        else:
            where = ""
        add(f"- {pub['url']} ({pub['at']}, {pub['author']}{where})")
    ch = report.get("changes") or {}
    fixes = [
        r
        for r in (ch.get("optimized") or [])
        if (parse_iso(r.get("published_at")) or dt.datetime.min.replace(tzinfo=UTC))
        >= parse_iso(report["generated_at"]) - dt.timedelta(days=1)
    ]
    resolved = (report.get("issues") or {}).get("resolved") or []
    add(f"**Исправлено на сайтах: {len(fixes)} правок текста, устранено проблем: {len(resolved)}**")
    for r in fixes[:15]:
        add(f"- {r['url']} ({r['element']})")
    for it in resolved[:10]:
        add(f"- устранено: `{it['domain']}` {it['code']}")
    issues = report.get("issues") or {}
    open_now = (issues.get("new") or []) + (issues.get("persisting") or [])
    probs = (report.get("editor") or {}).get("problems") or []
    add(
        f"**Ошибки и нерешённые вопросы: проблем сайтов {len(open_now)}, "
        f"циклов редактора без публикации {len(probs)}**"
    )
    for it in open_now[:10]:
        add(f"- `{it['domain']}` {it['code']} [{it.get('severity', '—')}]")
    wow = report.get("week_over_week") or {}
    if wow.get("status") == "MEASURED":
        cp = (wow.get("current_period") or {}).get("resolved") or {}
        bp = (wow.get("base_period") or {}).get("resolved") or {}
        tv = sum(
            (r["visits"].get("now") or 0) for r in wow["domains"].values() if "now" in r["visits"]
        )
        bv = sum(
            (r["visits"].get("before") or 0)
            for r in wow["domains"].values()
            if "now" in r["visits"]
        )
        add(
            f"**Трафик сети: визиты {bv:g} → {tv:g} "
            f"({bp.get('from')}…{bp.get('to')} → {cp.get('from')}…{cp.get('to')})**; "
            "по доменам и источникам — ниже"
        )
    else:
        add(f"**Трафик: не измерено** — {wow.get('reason')}")
    left = (report.get("editor") or {}).get("candidates_left", 0)
    add(
        f"**Следующие действия:** редактор продолжает круглосуточно (кандидатов в списке {left}); "
        "проверка сети каждые 6 часов; оценка правок +7/+14 дней по журналу изменений."
    )
    needs = report.get("owner_needs") or []
    add(f"**Требуется от владельца: {len(needs) or 'ничего'}**")
    for n in needs:
        add(f"- {n}")
    add("")
    add(f"- Запуск: `{report['run_id']}`, сформирован {report['generated_at']}")
    check = report.get("check") or {}
    add(
        f"- Проверка доступности: `{check.get('run_id', 'нет')}` от {check.get('finished_at', '—')}"
        f" (повторно не выполнялась: {'да' if report.get('check_reused') else 'нет'})"
    )
    fresh = report.get("analytics") or {}
    snap_day = str(fresh.get("snapshot") or "")[10:20] or "нет"
    add(
        f"- **Учтён снимок аналитики от {snap_day}** (`{fresh.get('snapshot', 'нет')}`, собран "
        f"{fresh.get('collected_at', '—')}, возраст "
        f"{fresh.get('age_hours', '—')} ч — {fresh.get('status', 'нет')}). "
        "Данные, поступившие позже формирования отчёта, в нём не учтены."
    )
    if snap_day != report["date_msk"]:
        add(
            f"- Снимка за {report['date_msk']} на момент отчёта "
            f"нет: все показатели ниже — по снимку от {snap_day}."
        )
    delivery = report.get("delivery") or {}
    add(
        f"- Доставка владельцу: **{delivery.get('state', 'не выполнена')}** "
        f"— {delivery.get('detail', '')}"
    )
    obs = [
        d for d, v in (fresh.get("domains") or {}).items() if v["observation"] == "NEW_OBSERVATION"
    ]
    same = [
        d
        for d, v in (fresh.get("domains") or {}).items()
        if v["observation"] == "SAME_SNAPSHOT_REREAD"
    ]
    add(
        f"- Новых наблюдений аналитики: {len(obs)}; повторное чтение того же снимка "
        f"(не наблюдение): {len(same)}"
    )
    add("")

    add("## Проблемы сайтов")
    issues = report.get("issues") or {}
    for title, key in (("Новые", "new"), ("Сохраняются", "persisting"), ("Устранены", "resolved")):
        group = issues.get(key) or []
        add(f"**{title}: {len(group)}**")
        for it in group[:30]:
            add(
                f"- `{it['domain']}` {it['code']} "
                f"[{it.get('severity', '—')}] — {it.get('detail', '')}"
            )
    add("")

    add("## Неделя к неделе (непересекающиеся окна)")
    wow = report.get("week_over_week") or {}
    if wow.get("status") != "MEASURED":
        add(f"не измерено: {wow.get('reason')}")
    else:
        cp = (wow.get("current_period") or {}).get("resolved") or {}
        bp = (wow.get("base_period") or {}).get("resolved") or {}
        add(
            f"Окна: {bp.get('from')}…{bp.get('to')} → {cp.get('from')}…{cp.get('to')} "
            "(даты вычислены из времени сбора)"
        )
        add("")
        add("| домен | визиты | из поиска |")
        add("| --- | --- | --- |")
        for domain, row in wow["domains"].items():
            add(
                f"| {domain} | {_fmt_metric(row['visits'])} | {_fmt_metric(row['search_visits'])} |"
            )
        notable = notable_changes(wow)
        if notable:
            add("")
            add(
                "**Заметные изменения** (не меньше 30% и 20 "
                "визитов; причина этим отчётом не установлена):"
            )
            for n in notable:
                src = n.get("main_source")
                tail = (
                    (
                        f"; больше всего изменился источник «{src['source']}» "
                        f"{src['before']:g} → {src['now']:g}"
                    )
                    if src
                    else ""
                )
                add(
                    f"- `{n['domain']}` {n['metric']}: {n['before']:g} → {n['now']:g} "
                    f"({n['share']:+.0%}){tail}"
                )
    add("")

    add("## Публикации: фактический результат на сайте")
    pubs = report.get("publications") or {}
    add(
        f"Проверено сейчас: {len(pubs.get('checked') or [])}; без изменений с прошлой проверки "
        f"(не перепроверялись): {pubs.get('unchanged', 0)}"
    )
    for p in (pubs.get("checked") or [])[:30]:
        add(f"- {p['verdict']} {p['status']} {p['url']}")
    add("")

    aud = dict(report.get("audience") or {})
    meta = aud.pop("_snapshot", None)
    if aud:
        add(f"## Аудитория: цель {AUDIENCE_TARGET} пользователей в день")
        add(
            f"Снимок `{meta['name']}`, окно {meta['period']}. База зафиксирована "
            "в docs/seo-operator/AUDIENCE_GOAL_20261012.md."
        )
        add("| домен | последний полный день (люди) | среднее в день | до цели |")
        add("| --- | --- | --- | --- |")
        for domain, a in sorted(aud.items()):
            if "not_measured" in a:
                add(f"| {domain} | не измерено: {a['not_measured']} | | |")
            elif a["kind"] == "daily":
                add(
                    f"| {domain} | {a['last']:.0f} ({a['last_day']}) | {a['avg']:.0f} "
                    f"за {a['days']} дн. | {a['gap']:.0f} |"
                )
            else:
                add(
                    f"| {domain} | по дням не собрано | {a['low']:.0f}–{a['high']:.0f} "
                    f"(границы, роботы не исключены) | {a['gap_low']:.0f}–{a['gap_high']:.0f} |"
                )
        add("")

    if pm:
        add("## Публикации за сутки по доменам")
        add(
            "| домен | новых уникальных текстов | адресов | повторных правок | "
            "видимость подтверждена | не видно | не проверено |"
        )
        add("| --- | --- | --- | --- | --- | --- | --- |")
        for domain, r in sorted(pm.items()):
            add(
                f"| {domain} | {len(r['new_texts'])} | {len(r['urls'])} | {r['edits']} | "
                f"{len(r['visible'])} | {len(r['not_visible'])} | {len(r['unchecked'])} |"
            )
        for _domain, r in sorted(pm.items()):
            for url in r["not_visible"]:
                add(f"- не видно на странице: {url}")
        add("Успехом считается только «видимость подтверждена» для текущего текста.")
        add("")

    if report.get("coverage"):
        from seo_operator import coverage

        add("## Покрытие редактора по доменам")
        lines.extend(coverage.render(report["coverage"]))
        add("")

    add("## Остановившиеся обновления (sitemap)")
    stalls = report.get("stalled") or []
    add("не обнаружено" if not stalls else "")
    for s in stalls:
        add(f"- `{s['domain']}` — {s['detail']}")
    unmeasured = report.get("sitemap_not_measured") or []
    if unmeasured:
        add(f"sitemap не измерен: {', '.join(f'{d} ({r})' for d, r in unmeasured)}")
    add("")

    add("## Редакционная очередь: дубли и пересечение ролей")
    hyg = report.get("queue") or {}
    add(f"- живых дублей одной страницы: {len(hyg.get('live_duplicates') or [])}")
    for g in (hyg.get("live_duplicates") or [])[:10]:
        add(
            f"  - {g['page']}: " + ", ".join(f"{t['content_id']} {t['status']}" for t in g["tasks"])
        )
    add(f"- заданий на относительный адрес: {len(hyg.get('relative_urls') or [])}")
    for t in report.get("task_targets") or []:
        if t["status"] != 200:
            add(f"  - {t['content_id']} {t['url']} → {t['status']} (задание {t['task_status']})")
    add(
        f"- адресов, которые брали несколько владельцев за сутки: "
        f"{hyg.get('urls_claimed_by_several_owners', 0)} из {hyg.get('urls_claimed', 0)}"
    )
    add(
        "- заданий, взятых SEO-владельцами (должен брать "
        f"редактор): {len(hyg.get('seo_side_claims') or [])}"
    )
    add("")
    ed = hyg.get("editor") or {}
    if ed:
        add("## Процесс редактора (за сутки)")
        add(
            f"- выдач заданий: {ed['claims']}, результатов: {ed['results']}, "
            f"выдач без результата (аренда истекла или снята): {ed['claims_without_result']}"
        )
        add(f"- исходы по семействам: {ed['outcomes']}")
        add(f"- написанные тексты по решению ворот: {ed['text_gate']}")
        for t in ed["looping"]:
            add(
                f"- задание {t['task_id']} ({t['site']}) выдано "
                f"{t['claims']} раз, результатов {t['results']} — "
                "повторная выдача без нового условия ничего не даст"
            )
        dead = ed["dead_end_tasks"]
        add(f"- живых заданий на описание у семейств без доставки (выполнить нельзя): {len(dead)}")
        for t in dead[:10]:
            add(f"  - {t['content_id']} {t['site']} ({t['family']}, {t['status']})")
        add("")

    weekly = report.get("weekly")
    if weekly:
        add(f"## Неделя `{weekly['run_id']}`: приоритеты")
        for p in weekly.get("priorities") or []:
            add(f"- {p['domain']}: {p['reason']}")
        evaluations = weekly.get("evaluations") or []
        add(f"Оценка изменений (окна не перекрываются; причину не доказывает): {len(evaluations)}")
        for ev in evaluations[:20]:
            add(
                f"- +{ev.get('horizon')} дн. {ev['url']}: {ev.get('verdict')}; вход "
                f"{_page_cell(ev['baseline'], 'landing_pages')} "
                f"→ {_page_cell(ev['after'], 'landing_pages')}; "
                f"визиты домена {_plain(ev['baseline'].get('domain_visits'))} "
                f"→ {_plain(ev['after'].get('domain_visits'))}"
                + (f" ({ev.get('reason')})" if ev.get("reason") else "")
            )
        add("")

    ed = report.get("editor") or {}
    if ed:
        add("## Фоновый редактор за сутки")
        add(
            f"Запусков: {ed.get('runs', 0)}, по итогам: {ed.get('verdicts') or 'нет'}; "
            f"кандидатов в списке: {ed.get('candidates_left', 0)}"
        )
        for pub in ed.get("published") or []:
            add(
                f"- {pub['url']} — источники: {', '.join(pub['sources'])} "
                f"({pub['run_id']}, {pub['trigger']})"
            )
        for prob in ed.get("problems") or []:
            add(f"- без публикации {prob['run_id']}: {prob['verdict']} — {prob['note']}")
        add("")

    cand = report.get("candidates") or {}
    if cand.get("pages"):
        add(f"## Кандидаты на оптимизацию (посещаемые страницы с находками: {cand['total']})")
        for r in cand["pages"]:
            add(
                f"- {r['url']} (входы+просмотры {r['weight']:g}): "
                + "; ".join(f"{f['code']} — {f['detail']}" for f in r["findings"])
            )
        for d in cand.get("duplicate_titles") or []:
            add(f"- одинаковый title «{d['title']}» у {len(d['urls'])} адресов {d['domain']}")
        add(
            "Правка — только при конкретном основании; шаблонные находки (meta разделов и серий) "
            "чинятся в шаблоне семейства, а не по одной странице."
        )
        add("")

    ch = report.get("changes") or {}
    if ch:
        add("## Изменения страниц")
        titles = (
            ("written", "Написано"),
            ("optimized", "Оптимизировано"),
            ("verified", "Опубликовано и проверено на сайте"),
            ("effect_pending", "Эффект пока не установлен"),
            ("measured", "Результат измерен"),
        )
        for key, title in titles:
            rows = ch.get(key) or []
            add(f"**{title}: {len(rows)}**")
            for r in rows[:20]:
                extra = ""
                if key == "effect_pending":
                    extra = f" — {r['reason']}; исходный снимок {r.get('baseline') or 'нет'}"
                elif key == "measured":
                    extra = " — " + "; ".join(
                        f"+{h} дн.: {e['verdict']}, входы "
                        f"{e.get('before'):g} → {e.get('after'):g}, "
                        f"страница {e.get('page_change'):+.0%} "
                        f"при домене {e.get('domain_change'):+.0%}"
                        for h, e in r["evaluations"].items()
                    )
                elif key == "verified":
                    extra = f" — проверено {r.get('checked_at')}"
                add(
                    f"- {r['id']} {r['url']} ({r['element']}, "
                    f"опубликовано {r['published_at']}){extra}"
                )
        if ch.get("without_ledger"):
            add(
                f"Публикаций без записи в журнале изменений (нет проблемы и гипотезы): "
                f"{len(ch['without_ledger'])}"
            )
        add(
            "Эффект — наблюдение по сопоставимым окнам с "
            "поправкой на домен; причину правки он не доказывает."
        )
        add("")

    mod = report.get("module") or {}
    add("## SEO-модуль: найдено → исправлено → проверено → осталось")
    add(
        f"найдено {mod.get('found', 0)} → исправлено {mod.get('fixed', 0)} → "
        f"проверено {mod.get('verified', 0)} → осталось {len(mod.get('remaining') or [])}"
    )
    for r in (mod.get("remaining") or [])[:12]:
        add(f"- {r['id']} [{r['priority']}, {r['state']}, {r['zone']}] {r['title']}")
    add("")
    add(
        "Реестр: `config/seo-module-defects.json`, "
        "описание — `docs/seo-operator/MODULE_DEFECTS.md`."
    )
    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------- прогон


@dataclass
class Context:
    root: Path
    mode: str
    run_id: str
    now: dt.datetime
    budget: Budget
    journal: Journal
    http: Http
    state: dict
    sources: dict[str, Path]

    def step_path(self, step: str) -> Path:
        return self.root / "runs" / self.run_id / f"{step}.json"

    def result(self, step: str) -> Any:
        return _read_json(self.step_path(step), None)


def step_discover(ctx: Context) -> Any:
    domains = discover_domains(ctx.sources)
    ctx.journal.write("domains", count=len(domains))
    return domains


def step_availability(ctx: Context) -> Any:
    out = []
    reachable = ctx.state.get("reachable") or {}
    for item in ctx.result("discover") or []:
        res = check_domain(ctx.http, item, was_reachable=item["domain"] in reachable)
        ctx.journal.write(
            "domain_checked",
            domain=item["domain"],
            home=res["home_status"],
            observed_indexing=res["observed_indexing"],
            issues=[i["code"] for i in res["issues"]],
        )
        out.append(res)
    return out


def step_analytics(ctx: Context) -> Any:
    # Новизна считается отдельно для каждого режима: проверка в 05:40 первой
    # прочтёт свежий снимок, и суточный отчёт иначе назвал бы его «повторным».
    seen = ctx.state.setdefault(f"analytics_seen_{ctx.mode}", {})
    res = analytics_freshness(ctx.sources["analytics_snapshots"], seen, ctx.now)
    ctx.journal.write(
        "analytics_freshness",
        status=res["status"],
        snapshot=res.get("snapshot"),
        new=sum(1 for v in res["domains"].values() if v["observation"] == "NEW_OBSERVATION"),
        reread=sum(
            1 for v in res["domains"].values() if v["observation"] == "SAME_SNAPSHOT_REREAD"
        ),
    )
    return res


def step_publications(ctx: Context, *, limit: int = 150) -> Any:
    verified = ctx.state.setdefault("publications", {})
    changes = ctx.state.get("changes") or {}
    checked, unchanged, untracked = [], 0, []
    for item in published_items():
        prior = verified.get(item["url"]) or {}
        last_check = parse_iso(prior.get("checked_at"))
        # Видимый текст перепроверяется раз в сутки, даже если не менялся: после
        # обновления данных витрины (доставка каталога ночью) правка обязана
        # остаться, и без перепроверки её пропажа не была бы замечена.
        recent = last_check is not None and ctx.now - last_check < RECHECK_VISIBLE_AFTER
        fresh = (
            prior.get("verdict") == "VISIBLE" and prior.get("digest") == item["digest"] and recent
        )
        if fresh:
            unchanged += 1
            known = changes.get(item["url"]) or {}
            if known.get("digest") != item["digest"] or known.get("published_at") != item.get(
                "published_at"
            ):
                untracked.append(
                    {**prior, "url": item["url"], "published_at": item.get("published_at")}
                )
            continue
        if len(checked) >= limit:
            break
        res = verify_publication(ctx.http, item)
        checked.append(res)
        ctx.journal.write(
            "publication_verified",
            url=res["url"],
            status=res["status"],
            verdict=res["verdict"],
            digest=res["digest"],
        )
    return {"checked": checked, "unchanged": unchanged, "untracked": untracked}


def step_sitemaps(ctx: Context) -> Any:
    today = f"{ctx.now.astimezone(MSK):%Y-%m-%d}"
    checks = {c["domain"]: c for c in ((ctx.result("check") or {}).get("availability") or [])}
    out: dict[str, dict] = {}
    for item in ctx.result("discover") or []:
        domain = item["domain"]
        sitemaps = (checks.get(domain) or {}).get("robots_sitemaps") or []
        snap = sitemap_snapshot(ctx.http, domain, sitemaps)
        out[domain] = snap
        ctx.journal.write(
            "sitemap",
            domain=domain,
            **{k: v for k, v in snap.items() if k != "reason"},
            reason=snap.get("reason"),
        )
    return {"date": today, "domains": out}


def visited_paths(snapshot: Path, *, per_domain: int = 5) -> dict[str, list[str]]:
    """Самые посещаемые адреса домена по снимку (входы + просмотры)."""
    out: dict[str, list[str]] = {}
    for entry in _read_json(snapshot, {}).get("domains") or []:
        weight: dict[str, float] = {}
        for key in ("landing_pages", "popular_pages"):
            ok, value, _ = _metric(entry, key)
            for name, metric in (_rows(value) if ok else {}).items():
                if name.startswith("/"):
                    weight[name] = weight.get(name, 0.0) + metric
        out[entry["domain"]] = [p for p, _ in sorted(weight.items(), key=lambda kv: -kv[1])][
            :per_domain
        ]
        _WEIGHTS[entry["domain"]] = weight
    return out


#: Вес адреса (входы + просмотры) из последнего разобранного снимка.
_WEIGHTS: dict[str, dict[str, float]] = {}


def step_visited(ctx: Context) -> Any:
    """Посещаемый адрес, отвечающий не 200, — посетители и робот видят ошибку.

    animedia.icu/title/pozhiratel-zvezd/season-1/episode-244/: 404 при трёх
    просмотрах в снимке 2026-10-08.
    """
    snaps = sorted(ctx.sources["analytics_snapshots"].glob("analytics-????-??-??.json"))
    if not snaps:
        return {"snapshot": None, "checked": []}
    live = {
        c["domain"]
        for c in ((ctx.result("check") or {}).get("availability") or [])
        if c.get("home_status") == 200
    }
    checked = []
    for domain, paths in visited_paths(snaps[-1]).items():
        if domain not in live:
            continue
        for path in paths:
            resp = ctx.http.get(f"https://{domain}{path}")
            row = {
                "domain": domain,
                "url": f"https://{domain}{path}",
                "status": resp.status,
                "weight": _WEIGHTS.get(domain, {}).get(path),
            }
            if resp.status == 200:
                # Страница уже скачана — аудит без второго запроса.
                row["audit"] = page_audit.audit(resp.body.decode("utf-8", "replace"), row["url"])
            checked.append(row)
            if resp.status not in (200, 301, 308):
                ctx.journal.write(
                    "visited_url_error",
                    domain=domain,
                    url=f"https://{domain}{path}",
                    status=resp.status,
                    error=resp.error,
                )
    audits = [c["audit"] for c in checked if c.get("audit")]
    return {
        "snapshot": snaps[-1].name,
        "checked": checked,
        "duplicate_titles": page_audit.duplicate_titles(audits),
    }


def _details_for_editor(path: Path, wanted: set[str] | None = None) -> dict:
    """Подробности снимка. Крупный снимок — по записи и только нужные пробелы.

    Из крупного снимка сохраняются записи без описания, которые редактор может
    взять: посещаемые (`wanted`) или с проверенным сопоставлением Shikimori.
    Остальные ~14 тыс. пробелов на сайт держать в памяти незачем: при пяти
    сайтах Lords/Zona пик доходил до 308 МБ при MemoryMax=512M.
    """
    try:
        size = path.stat().st_size
    except OSError:
        return {}
    if size <= STREAM_DETAILS_BYTES:
        return _read_json(path, {}).get("details") or {}
    import heapq

    from factory.qwen import editorial

    keep: dict = {}
    films: list[tuple] = []  # куча лучших пробелов-фильмов: (оценка, год, slug, запись)

    def light(rec: dict) -> dict:
        out = {k: rec.get(k) for k in _EDITOR_FIELDS}
        out["ratings_by_source"] = {
            "shikimori": (rec.get("ratings_by_source") or {}).get("shikimori") or {}
        }
        return out

    def take(slug: str, rec: dict) -> bool:
        if str(rec.get("description") or "").strip():
            return False
        shiki = (rec.get("ratings_by_source") or {}).get("shikimori") or {}
        if (wanted is not None and slug in wanted) or (
            shiki.get("match_state") == "external_id_exact+title_verified"
        ):
            keep[slug] = light(rec)
        elif (rec.get("external_ids") or {}).get("imdb") and rec.get("playable", True):
            ключ = (float(rec.get("imdb_rating") or 0), int(rec.get("year") or 0), slug)
            if len(films) < FILM_GAPS_KEPT:
                heapq.heappush(films, (*ключ, light(rec)))
            elif ключ > films[0][:3]:
                heapq.heapreplace(films, (*ключ, light(rec)))
        return False

    try:
        editorial._обойти_снимок(path, take)
    except (OSError, ValueError):
        return {}
    for *_, slug, rec in films:
        keep.setdefault(slug, rec)
    return keep


def _details_path(facts_dir: Path, sid: str) -> Path:
    """Снимок подробностей: общий каталог, иначе каталог данных ячейки (AnimeGo)."""
    общий = facts_dir / f"{sid}-details.json"
    # Каталог данных ячейки — только для рабочего каталога фабрики: каталог,
    # переданный явно (тесты, разбор чужого снимка), не подменяется данными хоста.
    if общий.is_file() or facts_dir != SOURCES["facts_snapshots"]:
        return общий
    try:
        from factory.cell import privileged

        свой = privileged.Площадка.из_реестра(sid).data / f"{sid}-details.json"
    except Exception:  # noqa: BLE001 — ячейки нет в реестре
        return общий
    return свой if свой.is_file() else общий


def _film_candidate(domain: str, slug: str, mine: dict, weight: float, reason: str) -> dict:
    """Кандидат-фильм/сериал: путь источника D200 (Википедия по IMDb → Wikidata → сайт)."""
    ids = mine.get("external_ids") or {}
    return {
        "site": domain,
        "slug": slug,
        "url": f"https://{domain}/title/{slug}/",
        "weight": weight,
        "reason": reason,
        "has_synopsis": False,
        "headline": mine.get("name"),
        "source_kind": "film",
        "film_args": [
            ids.get("imdb"),
            mine.get("name") or "",
            mine.get("original_name") or "",
            str(mine.get("year") or ""),
            "tv" if mine.get("type") == "tv" else "movie",
        ],
        "note": "фильм/сериал: source_fetch.py film <film_args> → wikidata <QID> → page <P856>",
    }


def editor_candidates(
    snapshot: Path,
    facts_dir: Path,
    published: set[tuple[str, str]],
    *,
    limit: int = 20,
    sites: dict[str, str] | None = None,
    needs_source: list[dict] | None = None,
) -> list[dict]:
    """Что редактору брать, когда очередь пуста: по трафику, с причиной.

    * GAP — описания нет вовсе (заглушка на странице);
    * DUPLICATE — синопсис есть и дословно совпадает на icu и space; меняется
      только на space, icu — контроль пилота (MOD-25).
    Визиты на серии засчитываются тайтлу: интерес к тайтлу — это они.
    `sites` — домены и их снимки; по умолчанию EDITOR_SITES.
    """
    sites = EDITOR_SITES if sites is None else sites
    weights: dict[tuple[str, str], float] = {}
    for entry in _read_json(snapshot, {}).get("domains") or []:
        domain = entry.get("domain")
        if domain not in sites:
            continue
        for key in ("landing_pages", "popular_pages"):
            ok, value, _ = _metric(entry, key)
            for path, metric in (_rows(value) if ok else {}).items():
                m = re.match(r"^/title/([^/]+)/", path)
                if m:
                    weights[(domain, m.group(1))] = weights.get((domain, m.group(1)), 0.0) + metric
    details = {
        d: _details_for_editor(
            _details_path(facts_dir, sid), {slug for dom, slug in weights if dom == d}
        )
        for d, sid in sites.items()
    }
    out = []
    # Одно своё описание произведения на сеть. Второй домен с тем же тайтлом
    # получал бы пересказ уже написанного текста по тому же источнику —
    # синонимайз, который владелец запретил 2026-10-09 (за ночь 08→09.10 таких
    # пар icu/space было 9). Другому домену — другая тема или другой формат.
    taken = {slug for _, slug in published}
    for (domain, slug), weight in sorted(weights.items(), key=lambda kv: -kv[1]):
        if (domain, slug) in published or slug in taken:
            continue
        mine = (details.get(domain) or {}).get(slug)
        if not mine:
            continue
        desc = (mine.get("description") or "").strip()
        other = (details.get("animedia.icu") or {}).get(slug) or {}
        if not desc:
            reason = "GAP"
        elif domain == "animedia.space" and desc == (other.get("description") or "").strip():
            reason = "DUPLICATE"
        else:
            continue
        shiki = (mine.get("ratings_by_source") or {}).get("shikimori") or {}
        source_id = shiki.get("external_id") or (mine.get("external_ids") or {}).get("mal")
        imdb = (mine.get("external_ids") or {}).get("imdb")
        if reason == "GAP" and not source_id and imdb:
            taken.add(slug)
            out.append(_film_candidate(domain, slug, mine, weight, "GAP"))
            continue
        if reason == "GAP" and not source_id:
            # Ни синопсиса, ни ID одобренного источника: редактору писать не из
            # чего (запуск закончился бы SOURCES_MISSING). Карточка не исключается,
            # а уходит в учёт «нужен источник» с данными для проверки идентичности
            # (владелец 2026-10-09: Shikimori ID не обязателен для фильмов и сериалов).
            if needs_source is not None:
                ids = mine.get("external_ids") or {}
                needs_source.append(
                    {
                        "site": domain,
                        "slug": slug,
                        "url": f"https://{domain}/title/{slug}/",
                        "weight": weight,
                        "headline": mine.get("name"),
                        "type": mine.get("type"),
                        "year": mine.get("year"),
                        "countries": mine.get("countries"),
                        "identity": {
                            k: ids[k] for k in ("imdb", "kinopoisk", "tmdb", "mdl") if ids.get(k)
                        },
                        "source_plan": SOURCE_PLAN.get(mine.get("type"), SOURCE_PLAN[None]),
                    }
                )
            continue
        taken.add(slug)
        out.append(
            {
                "site": domain,
                "slug": slug,
                "url": f"https://{domain}/title/{slug}/",
                "weight": weight,
                "reason": reason,
                "has_synopsis": bool(desc),
                "headline": mine.get("name"),
                # ID для source_fetch.py: сначала проверенное сопоставление Shikimori,
                # затем MAL ID каталога (у Shikimori те же номера) — идентичность
                # сверяется по названию в ответе.
                "shikimori_id": shiki.get("external_id")
                or (mine.get("external_ids") or {}).get("mal"),
                "shikimori_match": shiki.get("match_state"),
            }
        )
    out = out[:limit]
    # Запас: когда посещаемые страницы закрыты, редактор не простаивает.
    # Берутся заглушки Animedia с ПРОВЕРЕННЫМ сопоставлением Shikimori (идентичность
    # уже подтверждена каталогом), по оценке Shikimori и свежести. Трафика у них
    # в снимке нет — это помечено, а не скрыто.
    if len(out) < limit:
        seen = {(c["site"], c["slug"]) for c in out} | set(published)
        pool = []
        for domain, items in details.items():
            for slug, mine in items.items():
                if (
                    (domain, slug) in seen
                    or slug in taken
                    or (mine.get("description") or "").strip()
                ):
                    continue
                shiki = (mine.get("ratings_by_source") or {}).get("shikimori") or {}
                if not mine.get("playable", True):
                    continue
                if shiki.get("match_state") == "external_id_exact+title_verified":
                    оценка = shiki.get("value") or 0
                elif (mine.get("external_ids") or {}).get("imdb") and not shiki:
                    оценка = float(mine.get("imdb_rating") or 0)
                else:
                    continue
                pool.append((-оценка, -(mine.get("year") or 0), domain, slug, mine, shiki))
        per_domain: dict[str, int] = {}
        for c in out:
            per_domain[c["site"]] = per_domain.get(c["site"], 0) + 1
        by_slug: dict[str, list[tuple]] = {}
        for entry in sorted(pool):
            by_slug.setdefault(entry[3], []).append(entry)
        # Потолок на домен: без него фильмы с рейтингом каталога вытесняли аниме
        # Animedia из запаса целиком (оценки шкал несравнимы). Два прохода: сначала
        # всем поровну по нижней границе, затем добор до верхней.
        доменов = max(1, len({e[2] for e in pool}))
        for потолок in (max(1, limit // доменов), -(-limit // доменов)):
            for slug, entries in by_slug.items():
                if len(out) >= limit:
                    break
                if slug in taken:
                    continue
                entries = [e for e in entries if per_domain.get(e[2], 0) < потолок]
                if not entries:
                    continue
                # Тайтл, свободный на нескольких доменах, — тому, у кого кандидатов меньше.
                _, _, domain, slug, mine, shiki = min(
                    entries, key=lambda e: per_domain.get(e[2], 0)
                )
                per_domain[domain] = per_domain.get(domain, 0) + 1
                taken.add(slug)
                if not shiki:
                    out.append(_film_candidate(domain, slug, mine, 0.0, "GAP_BACKFILL"))
                    continue
                out.append(
                    {
                        "site": domain,
                        "slug": slug,
                        "url": f"https://{domain}/title/{slug}/",
                        "weight": 0.0,
                        "reason": "GAP_BACKFILL",
                        "has_synopsis": False,
                        "headline": mine.get("name"),
                        "shikimori_id": shiki.get("external_id"),
                        "shikimori_match": shiki.get("match_state"),
                        "note": "трафика в снимке нет; приоритет — оценка Shikimori и год",
                    }
                )
    return out


def step_candidates(ctx: Context) -> Any:
    snaps = sorted(ctx.sources["analytics_snapshots"].glob("analytics-????-??-??.json"))
    if not snaps:
        return {"snapshot": None, "candidates": []}
    published = {(i["domain"], i["slug"]) for i in published_items()}
    needs: list[dict] = []
    found = editor_candidates(
        snaps[-1], ctx.sources["facts_snapshots"], published, needs_source=needs
    )
    out = {
        "snapshot": snaps[-1].name,
        "generated_at": iso(utcnow()),
        "candidates": found,
        "needs_source": needs,
    }
    _write_json(ctx.root / "editor-candidates.json", out)
    ctx.journal.write("editor_candidates", count=len(found))
    return out


def step_queue(ctx: Context) -> Any:
    hygiene = queue_hygiene(
        ctx.sources["queue_registry"],
        ctx.sources["queue_events"],
        since=ctx.now - dt.timedelta(days=1),
    )
    cells = {
        c.get("domain"): c.get("site_id") or ""
        for c in _read_json(ctx.sources["cells"], {}).get("cells") or []
    }
    hygiene["editor"] = editor_process(
        ctx.sources["queue_events"],
        ctx.sources["queue_registry"],
        cells,
        since=ctx.now - dt.timedelta(days=1),
    )
    targets = verify_task_targets(ctx.http, hygiene)
    for t in targets:
        if t["status"] != 200:
            ctx.journal.write("task_target_missing", **t)
    return {"hygiene": hygiene, "targets": targets}


def _latest_check(ctx: Context, *, max_age_h: float = 7.0) -> list[dict] | None:
    last = ctx.state.get("last_check") or {}
    finished = parse_iso(last.get("finished_at"))
    if not finished or (ctx.now - finished).total_seconds() > max_age_h * 3600:
        return None
    return _read_json(ctx.root / "runs" / last["run_id"] / "availability.json", None)


def step_reuse_check(ctx: Context) -> Any:
    """Суточный прогон не повторяет проверку моложе семи часов."""
    reused = _latest_check(ctx)
    if reused is not None:
        ctx.journal.write("check_reused", run_id=ctx.state["last_check"]["run_id"])
        return {
            "reused": True,
            "run_id": ctx.state["last_check"]["run_id"],
            "finished_at": ctx.state["last_check"]["finished_at"],
            "availability": reused,
        }
    res = step_availability(ctx)
    return {
        "reused": False,
        "run_id": ctx.run_id,
        "finished_at": iso(utcnow()),
        "availability": res,
    }


def _issue_set(availability: list[dict], extra: list[dict] = ()) -> dict[str, dict]:
    issues = {}
    for res in availability or []:
        for it in res.get("issues") or []:
            issues[f"{res['domain']}|{it['code']}"] = {"domain": res["domain"], **it}
    for it in extra:
        issues[f"{it['domain']}|{it['code']}"] = it
    return issues


def _publication_issues(publications: dict | None) -> list[dict]:
    """Публикация, которой нет на сайте, — проблема сайта, а не строка отчёта."""
    out = []
    for res in (publications or {}).get("checked") or []:
        if res.get("verdict") == "VISIBLE":
            continue
        parts = urllib.parse.urlsplit(res["url"])
        out.append(
            {
                "domain": parts.hostname or "",
                "severity": "warning",
                "code": f"PUBLICATION_{res['verdict']}:{parts.path}",
                "detail": f"{res['url']} — ответ {res.get('status') or res.get('error')}",
            }
        )
    return out


def _diff(previous: dict[str, dict], current: dict[str, dict]) -> dict:
    return {
        "new": [current[k] for k in sorted(current) if k not in previous],
        "persisting": [current[k] for k in sorted(current) if k in previous],
        "resolved": [previous[k] for k in sorted(previous) if k not in current],
    }


def step_diff(ctx: Context) -> Any:
    """Сравнение с прошлым набором проблем. Уведомляет только о НОВОМ."""
    availability = ctx.result("availability") or []
    current = _issue_set(availability, _publication_issues(ctx.result("publications")))
    previous = ctx.state.get("open_issues_check") or {}
    diff = _diff(previous, current)
    for it in diff["new"]:
        ctx.journal.write("issue_new", **it)
    for it in diff["resolved"]:
        ctx.journal.write("issue_resolved", **it)
    return diff


def step_coverage(ctx: Context) -> Any:
    """Где редактор работает, а где сайт только наблюдается (seo_operator/coverage.py)."""
    from seo_operator import coverage

    reuse = ctx.result("check") or {}
    # Список сайтов — реестр фабрики; в тестах — файл из sources.
    sites_file = ctx.sources.get("coverage_sites")
    rows = coverage.build(
        _read_json(sites_file, []) if sites_file else coverage.load_sites(),
        availability=reuse.get("availability") or [],
        published=published_items(),
        verdicts=ctx.state.get("publications") or {},
        queue_items=_read_json(ctx.sources["queue_registry"], {}).get("items") or [],
        candidates=(ctx.result("candidates") or {}).get("candidates") or [],
        analytics_props=_read_json(ctx.sources["analytics_registry"], {}).get("properties") or [],
        blockers=coverage.load_blockers(
            ctx.sources.get("coverage_blockers") or SOURCES["coverage_blockers"]
        ),
        cells={
            c.get("domain"): c.get("status") or ""
            for c in _read_json(ctx.sources["cells"], {}).get("cells") or []
        },
        now=ctx.now,
    )
    _write_json(ctx.root / "coverage.json", {"generated_at": iso(utcnow()), "rows": rows})
    ctx.journal.write("editor_coverage", **coverage.summary(rows))
    return rows


def step_daily_report(ctx: Context) -> Any:
    reuse = ctx.result("check") or {}
    sitemaps = ctx.result("sitemaps") or {"domains": {}}
    history = ctx.state.setdefault("sitemaps", {})
    stalled, not_measured = [], []
    for domain, snap in (sitemaps.get("domains") or {}).items():
        days = history.setdefault(domain, {})
        days[sitemaps["date"]] = snap
        for old in sorted(days)[:-21]:
            days.pop(old)
        if snap.get("status") != "MEASURED":
            not_measured.append((domain, snap.get("reason")))
            continue
        found = stalled_updates(days, sitemaps["date"])
        if found:
            stalled.append({"domain": domain, **found})
        for finding in sitemap_findings(snap, ctx.now):
            stalled.append({"domain": domain, **finding})
    visited_errors = [
        {
            "domain": v["domain"],
            "severity": "warning",
            "code": f"VISITED_URL_{v['status'] or 'ERROR'}:{urllib.parse.urlsplit(v['url']).path}",
            "detail": (
                f"{v['url']} — посещаемый адрес (снимок "
                f"{(ctx.result('visited') or {}).get('snapshot')}) отвечает {v['status']}"
            ),
        }
        for v in (ctx.result("visited") or {}).get("checked") or []
        if v["status"] not in (200, 301, 308)
    ]
    current = _issue_set(
        reuse.get("availability") or [],
        stalled + visited_errors + _publication_issues(ctx.result("publications")),
    )
    previous = ctx.state.get("open_issues_daily") or {}
    issues = _diff(previous, current)
    queue = ctx.result("queue") or {}
    weekly = None
    last_weekly = ctx.state.get("last_weekly") or {}
    if last_weekly and last_weekly.get("reported_in") is None:
        weekly = _read_json(ctx.root / "runs" / last_weekly["run_id"] / "priorities.json", None)
        if weekly is not None:
            evaluations = _read_json(
                ctx.root / "runs" / last_weekly["run_id"] / "evaluate.json", []
            )
            weekly = {"run_id": last_weekly["run_id"], **weekly, "evaluations": evaluations}
    report = {
        "run_id": ctx.run_id,
        "date_msk": f"{ctx.now.astimezone(MSK):%Y-%m-%d}",
        "generated_at": iso(utcnow()),
        "check": {"run_id": reuse.get("run_id"), "finished_at": reuse.get("finished_at")},
        "check_reused": reuse.get("reused"),
        "analytics": ctx.result("analytics"),
        "issues": issues,
        "week_over_week": week_over_week(
            ctx.sources["analytics_snapshots"], ctx.now.astimezone(MSK).date()
        ),
        "publications": ctx.result("publications"),
        "coverage": ctx.result("coverage"),
        "audience": audience_goal(
            (
                sorted(ctx.sources["analytics_snapshots"].glob("analytics-????-??-??.json"))
                or [None]
            )[-1]
        ),
        "publication_metrics": publication_metrics(
            ctx.now - dt.timedelta(days=1), ctx.state.get("publications") or {}
        ),
        "stalled": stalled,
        "sitemap_not_measured": not_measured,
        "queue": queue.get("hygiene"),
        "task_targets": queue.get("targets"),
        "weekly": weekly,
        "candidates": optimization_candidates(ctx.result("visited") or {}),
        "module": module_section(ctx.sources["defects"]),
        "changes": changes_section(
            ctx.sources["changes_ledger"],
            ctx.state,
            ctx.now.astimezone(MSK).date(),
            ctx.sources.get("changes_ledger_runs"),
        ),
        # Файл сохранён — это НЕ доставка. Канала доставки владельцу в проекте
        # нет (docs/SEO_REGULAR_RUN.md §4); пока он не выбран, отчёт честно
        # говорит, что не доставлен.
        "delivery": delivery_status(
            f"var/seo-regular/reports/daily/{ctx.now.astimezone(MSK):%Y-%m-%d}.md"
        ),
    }
    report["editor"] = editor_day(REPO_ROOT / "var" / "editor-runs", ctx.now - dt.timedelta(days=1))
    report["published_24h"] = published_since(ctx.now - dt.timedelta(days=1))
    report["owner_needs"] = owner_needs(ctx.sources["defects"])
    try:
        cands = _read_json(ctx.root / "editor-candidates.json", {}).get("candidates") or []
    except AttributeError:
        cands = []
    report["editor"]["candidates_left"] = len(cands)
    out_dir = ctx.root / "reports" / "daily"
    _write_json(out_dir / f"{report['date_msk']}.json", report)
    text = render_daily(report)
    (out_dir / f"{report['date_msk']}.md").write_text(text, encoding="utf-8")
    # Единый «последний отчёт»: тот же текст, перезаписывается атомарно.
    latest = ctx.root / "reports" / "LATEST.md"
    tmp = latest.with_name("LATEST.md.tmp")
    tmp.write_text(text, encoding="utf-8")
    tmp.replace(latest)
    ctx.state["open_issues_daily"] = current
    if weekly is not None:
        ctx.state["last_weekly"]["reported_in"] = ctx.run_id
    ctx.journal.write(
        "owner_report_written",
        path=str(out_dir / f"{report['date_msk']}.md"),
        new_issues=len(issues["new"]),
        resolved=len(issues["resolved"]),
    )
    return {"path": str(out_dir / f"{report['date_msk']}.md")}


def step_evaluate(ctx: Context) -> Any:
    controls = {
        c["url"]: c["control_url"]
        for c in _read_json(ctx.sources["changes_ledger"], {}).get("changes") or []
        if c.get("control_url")
    }
    found = evaluate_changes(
        ctx.state.get("changes") or {}, ctx.sources["analytics_snapshots"], controls
    )
    ctx.journal.write("changes_evaluated", count=len(found))
    return found


def step_weekly_priorities(ctx: Context) -> Any:
    """Пересмотр приоритетов: сначала критическое, затем видимость в поиске."""
    wow = week_over_week(ctx.sources["analytics_snapshots"], ctx.now.astimezone(MSK).date())
    open_issues = ctx.state.get("open_issues_daily") or ctx.state.get("open_issues_check") or {}
    by_domain: dict[str, list[dict]] = {}
    for it in open_issues.values():
        by_domain.setdefault(it["domain"], []).append(it)
    # Падение учитывается, только если оно заметно (notable_changes): «-1 переход»
    # при единицах трафика — шум, и ставить его выше предупреждений нельзя.
    drops: dict[str, list[dict]] = {}
    for n in notable_changes(wow):
        if n["share"] < 0:
            drops.setdefault(n["domain"], []).append(n)
    names = {"visits": "визиты", "search_visits": "переходы из поиска"}
    priorities = []
    for domain in sorted({*by_domain, *(wow.get("domains") or {})}):
        crit = [i for i in by_domain.get(domain, []) if i.get("severity") == "critical"]
        warn = [i for i in by_domain.get(domain, []) if i.get("severity") == "warning"]
        if crit:
            priorities.append((0, domain, "критично: " + ", ".join(i["code"] for i in crit)))
        elif domain in drops:
            priorities.append(
                (
                    1,
                    domain,
                    "; ".join(
                        f"{names[n['metric']]} {n['before']:g} → "
                        f"{n['now']:g} ({n['share']:+.0%}) за неделю"
                        + (
                            f", главный вклад — «{n['main_source']['source']}» "
                            f"{n['main_source']['before']:g} → {n['main_source']['now']:g}"
                            if n.get("main_source")
                            else ""
                        )
                        for n in drops[domain]
                    )
                    + " — причину установить",
                )
            )
        elif warn:
            priorities.append((2, domain, "предупреждения: " + ", ".join(i["code"] for i in warn)))
    # Подозрение на регрессию после правки — разобрать и при подтверждении
    # откатить адресно (rollback в журнале изменений), не трогая остальное.
    for ev in ctx.result("evaluate") or []:
        if ev.get("verdict") == "REGRESSION_SUSPECTED":
            priorities.append(
                (
                    0,
                    ev["url"],
                    f"после правки +{ev['horizon']} дн.: входы {ev['before']:g} → "
                    f"{ev['after']:g} при домене {ev['domain_change']:+.0%} — разобрать, при "
                    "подтверждении откатить адресно",
                )
            )
    priorities.sort()
    result = {
        "week_over_week": wow,
        "priorities": [{"domain": d, "reason": r, "rank": p} for p, d, r in priorities],
    }
    ctx.state["last_weekly"] = {"run_id": ctx.run_id, "reported_in": None}
    ctx.journal.write("weekly_priorities", count=len(priorities))
    return result


def step_hourly(ctx: Context) -> Any:
    """Короткая сводка за час. Ни одного сетевого запроса — только журналы."""
    since = ctx.now - dt.timedelta(hours=1)
    pubs = []
    for _family, (root, form) in OVERLAY_ROOTS.items():
        if not root.is_dir():
            continue
        for site_dir in root.iterdir():
            history = site_dir / "history.jsonl"
            if not history.is_file():
                continue
            for line in history.read_text(encoding="utf-8").splitlines()[-200:]:
                try:
                    r = json.loads(line)
                except ValueError:
                    continue
                at = parse_iso(r.get("at"))
                if r.get("op") in ("publish", "unpublish") and at and at >= since:
                    pubs.append(
                        f"{r['op']} https://{site_dir.name}{form.format(slug=r['slug'])} "
                        f"({r.get('author')})"
                    )
    claims = results = 0
    outcomes: dict[str, int] = {}
    events = ctx.sources["queue_events"]
    if events.is_file():
        for line in events.read_text(encoding="utf-8").splitlines()[-3000:]:
            try:
                e = json.loads(line)
            except ValueError:
                continue
            at = parse_iso(e.get("at"))
            if not at or at < since:
                continue
            if e.get("event") == "task_claimed":
                claims += 1
            elif e.get("event") == "task_result":
                results += 1
                outcomes[e.get("outcome")] = outcomes.get(e.get("outcome"), 0) + 1
    runs = []
    log = REPO_ROOT / "var" / "editor-runs" / "runs.jsonl"
    if log.is_file():
        for line in log.read_text(encoding="utf-8").splitlines():
            try:
                r = json.loads(line)
            except ValueError:
                continue
            at = parse_iso(r.get("finished_at"))
            if at and at >= since:
                runs.append(f"{r['run_id']} {r.get('trigger')} → {r.get('verdict')}")
    open_issues = [
        i
        for i in (ctx.state.get("open_issues_check") or {}).values()
        if i.get("severity") == "critical"
    ]
    out_path_hint = f"var/seo-regular/hourly/{ctx.now.astimezone(UTC):%Y-%m-%dT%H}.md"
    lines = [
        f"# Сводка за час до {iso(ctx.now)}",
        "",
        f"- публикаций: {len(pubs)}",
        *[f"  - {x}" for x in pubs[:10]],
        f"- очередь: выдач {claims}, результатов {results} {outcomes or ''}",
        f"- запуски фонового редактора: {len(runs)}",
        *[f"  - {x}" for x in runs],
        f"- открытых критических проблем сайтов (последняя проверка): {len(open_issues)}",
        "- доставка владельцу: не выполняется (канал отменён владельцем); "
        f"сводка только в журнале {out_path_hint}",
    ]
    out = ctx.root / "hourly" / f"{ctx.now.astimezone(UTC):%Y-%m-%dT%H}.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return {
        "path": str(out),
        "publications": len(pubs),
        "claims": claims,
        "results": results,
        "editor_runs": len(runs),
    }


PLANS: dict[str, list[tuple[str, Callable[[Context], Any]]]] = {
    "check": [
        ("discover", step_discover),
        ("availability", step_availability),
        ("analytics", step_analytics),
        ("publications", step_publications),
        ("diff", step_diff),
    ],
    "daily": [
        ("discover", step_discover),
        ("check", step_reuse_check),
        ("analytics", step_analytics),
        ("publications", step_publications),
        ("sitemaps", step_sitemaps),
        ("visited", step_visited),
        ("candidates", step_candidates),
        ("queue", step_queue),
        ("coverage", step_coverage),
        ("report", step_daily_report),
    ],
    "hourly": [("summary", step_hourly)],
    "weekly": [
        ("discover", step_discover),
        ("evaluate", step_evaluate),
        ("priorities", step_weekly_priorities),
    ],
}

LIMITS = {
    # предел времени цикла, предел запросов
    # 250 запросов: каждая проверка перепроверяет все видимые тексты (60 на 09.10).
    # Время не поднимается: юнит обрывает запуск на 540 с (TimeoutStartSec).
    "check": (420, 250),
    "daily": (840, 400),
    "weekly": (300, 20),
    "hourly": (60, 0),
}


def _commit_state(ctx: Context, step: str, result: Any) -> None:
    """Состояние, которое шаг вправе зафиксировать, — только после его успеха."""
    if step == "analytics" and isinstance(result, dict):
        ctx.state.setdefault(f"analytics_seen_{ctx.mode}", {}).update(
            result.get("seen_update") or {}
        )
    if step == "publications" and isinstance(result, dict):
        store = ctx.state.setdefault("publications", {})
        changes = ctx.state.setdefault("changes", {})
        snaps = sorted(ctx.sources["analytics_snapshots"].glob("analytics-????-??-??.json"))
        for res in result.get("checked") or []:
            store[res["url"]] = {
                "verdict": res["verdict"],
                "digest": res["digest"],
                "checked_at": res["checked_at"],
                "status": res["status"],
            }
        for res in (result.get("checked") or []) + (result.get("untracked") or []):
            known = changes.get(res["url"]) or {}
            stale = known.get("digest") != res["digest"] or known.get("published_at") != res.get(
                "published_at"
            )
            if res.get("verdict") == "VISIBLE" and stale:
                domain = urllib.parse.urlsplit(res["url"]).hostname or ""
                changes[res["url"]] = {
                    "domain": domain,
                    "digest": res["digest"],
                    "published_at": res.get("published_at"),
                    "first_visible_at": res.get("checked_at"),
                    # Время проверки исходной точкой не служит: текст мог висеть
                    # неделями, и «исходный» снимок оказался бы снимком «после».
                    "baseline": _baseline(snaps, domain, res["url"], res.get("published_at")),
                }
    if step == "evaluate" and isinstance(result, list):
        changes = ctx.state.setdefault("changes", {})
        for ev in result:
            if ev["url"] in changes:
                changes[ev["url"]][f"evaluation_{ev['horizon']}"] = {
                    k: ev.get(k)
                    for k in (
                        "verdict",
                        "before",
                        "after",
                        "page_change",
                        "domain_change",
                        "excess_over_domain",
                        "control_change",
                        "excess_over_control",
                        "reason",
                    )
                } | {"snapshot": ev["after"].get("snapshot")}
    if step in ("availability", "check") and isinstance(result, list | dict):
        rows = result if isinstance(result, list) else (result.get("availability") or [])
        for row in rows:
            if row.get("home_status") == 200:
                ctx.state.setdefault("reachable", {})[row["domain"]] = row.get("checked_at")
    if step == "diff" and ctx.mode == "check":
        ctx.state["open_issues_check"] = _issue_set(
            ctx.result("availability") or [], _publication_issues(ctx.result("publications"))
        )
    if step == "check" and isinstance(result, dict) and not result.get("reused"):
        _write_json(ctx.step_path("availability"), result.get("availability"))


def run(
    mode: str,
    *,
    root: Path | None = None,
    now: dt.datetime | None = None,
    sources: dict[str, Path] | None = None,
    http: Http | None = None,
    trigger: str = "manual",
    step_attempts: int = 2,
) -> dict:
    """Один запуск режима. Возвращает итог с кодом выхода."""
    if mode not in PLANS:
        raise ValueError(f"неизвестный режим {mode!r}")
    root = Path(root or os.environ.get("SEO_REGULAR_ROOT") or REPO_ROOT / "var" / "seo-regular")
    root.mkdir(parents=True, exist_ok=True)
    now = now or utcnow()
    run_id = slot_id(mode, now)
    journal = Journal(root, run_id)
    seconds, requests = LIMITS[mode]
    budget = Budget(
        float(os.environ.get("SEO_REGULAR_MAX_SECONDS", seconds)),
        int(os.environ.get("SEO_REGULAR_MAX_REQUESTS", requests)),
    )
    lock = FileLock(root / "run.lock", stale_after=seconds * 3)
    try:
        lock.acquire(f"{mode}:{trigger}")
    except LockBusy as exc:
        journal.write("lock_busy", mode=mode, trigger=trigger, detail=str(exc))
        return {
            "run_id": run_id,
            "state": "LOCK_BUSY",
            "exit_code": EXIT_TEMPFAIL,
            "detail": str(exc),
        }
    try:
        return _run_locked(
            mode,
            root,
            run_id,
            now,
            journal,
            budget,
            sources or SOURCES,
            http,
            trigger,
            step_attempts,
        )
    finally:
        lock.release()


def _run_locked(mode, root, run_id, now, journal, budget, sources, http, trigger, step_attempts):
    state_path = root / "state.json"
    state = _read_json(state_path, {})
    checkpoint = Checkpoint(root / "checkpoints.json")
    ctx = Context(
        root=root,
        mode=mode,
        run_id=run_id,
        now=now,
        budget=budget,
        journal=journal,
        http=http or Http(budget, journal),
        state=state,
        sources=sources,
    )
    if http is not None:
        http.budget, http.journal = budget, journal
    done = checkpoint.completed(run_id)
    journal.write(
        "run_started",
        mode=mode,
        trigger=trigger,
        resumed_steps=done,
        budget_seconds=budget.seconds,
        budget_requests=budget.requests,
    )
    run_record = {
        "run_id": run_id,
        "mode": mode,
        "trigger": trigger,
        "started_at": iso(utcnow()),
        "resumed_from": done,
        "steps": {},
    }
    final, exit_code, error = "DONE", 0, ""
    for step, func in PLANS[mode]:
        if step in done:
            run_record["steps"][step] = "resumed_skip"
            continue
        for attempt in range(1, step_attempts + 1):
            try:
                budget.check_time()
                result = func(ctx)
            except BudgetExceeded as exc:
                final, exit_code, error = "PARTIAL", EXIT_TEMPFAIL, str(exc)
                journal.write("budget_exceeded", step=step, detail=str(exc))
                break
            except Exception as exc:  # noqa: BLE001 - любой сбой шага журналируется и повторяется
                error = f"{type(exc).__name__}: {exc}"
                journal.write("step_failed", step=step, attempt=attempt, error=error)
                if attempt < step_attempts:
                    time.sleep(min(5.0, max(0.0, budget.remaining() / 10)))
                    continue
                final, exit_code = "FAILED", 1
                break
            _write_json(ctx.step_path(step), result)
            _commit_state(ctx, step, result)
            _write_json(state_path, state)
            checkpoint.mark(run_id, step)
            run_record["steps"][step] = "done"
            journal.write("step_done", step=step, attempt=attempt)
            error = ""
            break
        if final != "DONE":
            run_record["steps"][step] = final.lower()
            break
    if final == "DONE" and all(v == "resumed_skip" for v in run_record["steps"].values()):
        # Слот уже отработан: повторный вызов ничего не делает и не выдаёт
        # себя за новую проверку.
        journal.write("run_finished", state="ALREADY_DONE", exit_code=0)
        # Пропуск виден в истории: иначе срабатывание таймера, не сделавшее
        # работы, неотличимо от несработавшего таймера.
        history = state.setdefault("runs", [])
        history.append(
            {
                "run_id": run_id,
                "mode": mode,
                "trigger": trigger,
                "started_at": run_record["started_at"],
                "finished_at": iso(utcnow()),
                "state": "ALREADY_DONE",
            }
        )
        del history[:-200]
        _write_json(state_path, state)
        return {**run_record, "state": "ALREADY_DONE", "exit_code": 0, "error": ""}
    run_record.update(
        {
            "finished_at": iso(utcnow()),
            "state": final,
            "error": error,
            "requests_used": budget.used_requests,
        }
    )
    if final == "DONE":
        _prune_checkpoints(
            checkpoint, keep=[r["run_id"] for r in state.get("runs", [])[-60:]] + [run_id]
        )
    if final == "DONE" and mode == "check":
        state["last_check"] = {"run_id": run_id, "finished_at": run_record["finished_at"]}
        new_critical = [
            i
            for i in (ctx.result("diff") or {}).get("new") or []
            if i.get("severity") == "critical"
        ]
        run_record["new_critical"] = new_critical
        if new_critical:
            exit_code = EXIT_NEW_CRITICAL
    _write_json(state_path, state)
    _write_json(root / "runs" / run_id / "run.json", run_record)
    history = state.setdefault("runs", [])
    history.append(
        {
            k: run_record[k]
            for k in ("run_id", "mode", "trigger", "started_at", "finished_at", "state")
        }
    )
    del history[:-200]
    _write_json(state_path, state)
    journal.write(
        "run_finished",
        state=final,
        exit_code=exit_code,
        error=error,
        requests_used=budget.used_requests,
    )
    return {**run_record, "exit_code": exit_code}


def _prune_checkpoints(checkpoint: Checkpoint, keep: list[str]) -> None:
    data = _read_json(checkpoint.path, {})
    stale = [run_id for run_id in data if run_id not in keep]
    for run_id in stale:
        checkpoint.clear(run_id)


SYSTEMD_DIR = Path("/etc/systemd/system")
TIMER_STAMPS = Path("/var/lib/systemd/timers")


def status(
    root: Path | None = None, *, systemd_dir: Path = SYSTEMD_DIR, stamps: Path = TIMER_STAMPS
) -> dict:
    """Подтверждение расписания ЧТЕНИЕМ, без root и без systemctl.

    Три независимых свидетельства на каждый режим: файл таймера с его
    OnCalendar, ссылка включения в timers.target.wants, отметка последнего
    срабатывания. И отдельно — завершённые запуски из собственного журнала с
    триггером: запуск по расписанию и ручной не смешиваются.
    """
    root = Path(root or os.environ.get("SEO_REGULAR_ROOT") or REPO_ROOT / "var" / "seo-regular")
    state = _read_json(root / "state.json", {})
    out: dict[str, Any] = {"root": str(root), "modes": {}}
    for mode in MODES:
        timer = systemd_dir / f"seo-regular-{mode}.timer"
        text = timer.read_text(encoding="utf-8") if timer.is_file() else ""
        stamp = stamps / f"stamp-seo-regular-{mode}.timer"
        runs = [r for r in state.get("runs") or [] if r.get("mode") == mode]
        scheduled = [
            r for r in runs if r.get("trigger") == "systemd-timer" and r.get("state") == "DONE"
        ]
        manual = [r for r in runs if r.get("trigger") != "systemd-timer"]
        out["modes"][mode] = {
            "timer_installed": timer.is_file(),
            "on_calendar": re.findall(r"(?m)^OnCalendar=(.+)$", text),
            "enabled": (systemd_dir / "timers.target.wants" / timer.name).exists(),
            "last_fired": iso(dt.datetime.fromtimestamp(stamp.stat().st_mtime, tz=UTC))
            if stamp.exists()
            else None,
            "last_scheduled_run": scheduled[-1] if scheduled else None,
            "scheduled_runs_done": len(scheduled),
            "last_manual_run": manual[-1] if manual else None,
        }
    out["confirmed"] = all(
        m["timer_installed"] and m["enabled"] for m in out["modes"].values()
    ) and any(m["scheduled_runs_done"] for m in out["modes"].values())
    return out


def main(argv: list[str] | None = None) -> int:
    if argv is None:
        argv = sys.argv[1:]
    if argv[:1] == ["status"]:
        print(json.dumps(status(), ensure_ascii=False, indent=2))
        return 0
    parser = argparse.ArgumentParser(
        prog="seo-operator regular",
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("mode", choices=MODES)
    parser.add_argument(
        "--trigger",
        default=os.environ.get("SEO_REGULAR_TRIGGER", "manual"),
        help="кто запустил: systemd-timer или manual (пишется в журнал)",
    )
    parser.add_argument("--root", help="каталог состояния (по умолчанию var/seo-regular)")
    args = parser.parse_args(argv)
    result = run(args.mode, root=Path(args.root) if args.root else None, trigger=args.trigger)
    print(
        json.dumps(
            {
                k: result.get(k)
                for k in (
                    "run_id",
                    "state",
                    "exit_code",
                    "error",
                    "steps",
                    "requests_used",
                    "detail",
                )
            },
            ensure_ascii=False,
        )
    )
    return int(result["exit_code"])


if __name__ == "__main__":
    sys.exit(main())
