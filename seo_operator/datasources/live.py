"""Конкретные адаптеры источников, названных в задании.

Источники Яндекса — рабочие: транспорт, повторы и редакция живут в
:mod:`factory.analytics`, а здесь остаётся контракт источника. Остальные
адаптеры по-прежнему объявлены, но не реализованы: доступов к ним не выдано, и
``probe()`` честно называет причину вместо того, чтобы вернуть пустой результат,
который отчёт нарисует как «0 кликов».

Отдельное правило для Яндекса: токен берётся **только** из файла, путь к
которому задан ``YANDEX_OAUTH_TOKEN_FILE``. Значения токена в окружении быть не
должно — источник это проверяет и отказывается работать, если оно там есть.
"""

from __future__ import annotations

import socket
from urllib.parse import urlsplit

from seo_operator.datasources.base import (
    Availability,
    CredentialedSource,
    SourceStatus,
    UnavailableSourceError,
)


def _reachable(url: str, timeout: float = 5.0) -> tuple[bool, str]:
    """Best-effort TCP reachability check against the endpoint host."""
    host = urlsplit(url).hostname or url
    port = 443
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True, f"{host}:{port} доступен"
    except OSError as exc:
        return False, f"{host}:{port} недоступен ({exc.__class__.__name__})"


class NetworkGatedSource(CredentialedSource):
    """Credentialed source that also verifies the endpoint is reachable."""

    def probe(self) -> Availability:
        base = super().probe()
        if not base.usable:
            return base
        if self.endpoint:
            ok, detail = _reachable(self.endpoint)
            if not ok:
                return Availability(SourceStatus.NETWORK_BLOCKED, detail)
        return base


class GoogleSearchConsole(NetworkGatedSource):
    name = "google_search_console"
    kind = "search_analytics"
    endpoint = "https://searchconsole.googleapis.com"
    required_env = ("GSC_SERVICE_ACCOUNT_JSON", "GSC_PROPERTY_MAP")
    metrics = ("impressions", "clicks", "ctr", "position")


class YandexSource(NetworkGatedSource):
    """Общее поведение источников Яндекса: файл секрета вместо переменной.

    ``required_env`` содержит имя переменной с **путём**, а не со значением:
    сам токен в окружение не попадает никогда. Если значение всё-таки положили
    в переменную, источник отказывается работать — молча предпочесть файл
    значило бы оставить утечку незамеченной.
    """

    required_env = ()

    def probe(self) -> Availability:
        from factory.analytics.credentials import forbidden_env_present, inspect_token_file

        leaked = forbidden_env_present()
        if leaked:
            return Availability(
                SourceStatus.ERROR,
                f"значение токена передано переменной окружения ({', '.join(leaked)}); "
                "разрешён только путь к файлу через YANDEX_OAUTH_TOKEN_FILE",
            )
        status = inspect_token_file()
        if not status.exists:
            return Availability(
                SourceStatus.MISSING_CREDENTIALS, f"нет файла секрета {status.path}"
            )
        if not status.readable:
            return Availability(
                SourceStatus.MISSING_CREDENTIALS,
                f"файл секрета {status.path} недоступен этой учётной записи: "
                "источник работает из systemd-unit с LoadCredential",
            )
        if status.problems:
            return Availability(SourceStatus.ERROR, "; ".join(status.problems))
        if self.endpoint:
            ok, detail = _reachable(self.endpoint)
            if not ok:
                return Availability(SourceStatus.NETWORK_BLOCKED, detail)
        return Availability(SourceStatus.AVAILABLE, "файл секрета на месте, endpoint отвечает")


class YandexWebmaster(YandexSource):
    name = "yandex_webmaster"
    kind = "search_analytics"
    endpoint = "https://api.webmaster.yandex.net"
    metrics = ("impressions", "clicks", "ctr", "position", "indexing")

    def _fetch(self, site_id: str, **kwargs):
        """Read-only ресурс Вебмастера. Записей не делает ни при каких аргументах."""
        from factory.analytics.yandex import YandexAnalyticsProvider

        host_id = kwargs.get("host_id")
        resource = kwargs.get("resource", "summary")
        if not host_id:
            raise UnavailableSourceError(
                f"{self.name}: host_id не передан — сайт ещё не зарегистрирован в Вебмастере"
            )
        provider = YandexAnalyticsProvider(dry_run=True)
        return provider.get_webmaster_report(host_id, resource, kwargs.get("params"))


class YandexMetrika(YandexSource):
    name = "yandex_metrika"
    kind = "analytics"
    endpoint = "https://api-metrika.yandex.net"
    metrics = ("sessions", "depth", "returning", "watch_starts")

    def _fetch(self, site_id: str, **kwargs):
        """Табличный отчёт Метрики. Только чтение."""
        from factory.analytics.yandex import YandexAnalyticsProvider

        counter_id = kwargs.get("counter_id")
        if not counter_id:
            raise UnavailableSourceError(
                f"{self.name}: counter_id не передан — счётчик для сайта {site_id} не создан"
            )
        provider = YandexAnalyticsProvider(dry_run=True)
        return provider.get_metrica_report(
            int(counter_id),
            date1=kwargs.get("date1", "7daysAgo"),
            date2=kwargs.get("date2", "yesterday"),
            metrics=kwargs.get("metrics")
            or list(provider.contract["metrika"]["reporting"]["metrics_used"].values()),
            dimensions=kwargs.get("dimensions"),
        )


class CmsSource(CredentialedSource):
    name = "cms"
    kind = "content"
    required_env = ("CMS_BASE_URL", "CMS_API_TOKEN")


class ServerLogs(CredentialedSource):
    name = "server_logs"
    kind = "crawl"
    required_env = ("SERVER_LOG_PATH",)


class Monitoring(CredentialedSource):
    name = "monitoring"
    kind = "availability"
    required_env = ("MONITORING_API_URL", "MONITORING_API_TOKEN")


class SitemapSource(CredentialedSource):
    """Public sitemap. Needs no credentials, only a site base URL."""

    name = "sitemap"
    kind = "crawl"
    required_env = ()

    def __init__(self, base_url: str | None = None) -> None:
        self.base_url = base_url

    def probe(self) -> Availability:
        if not self.base_url:
            return Availability(SourceStatus.NOT_CONFIGURED, "не задан base_url сайта")
        ok, detail = _reachable(self.base_url)
        if not ok:
            return Availability(SourceStatus.NETWORK_BLOCKED, detail)
        return Availability(SourceStatus.AVAILABLE, detail)


class RobotsSource(SitemapSource):
    name = "robots"


ALL_SOURCES = (
    GoogleSearchConsole,
    YandexWebmaster,
    YandexMetrika,
    CmsSource,
    ServerLogs,
    Monitoring,
)


def probe_all() -> dict[str, Availability]:
    """Probe every configured source. Used by the inventory and daily report."""
    return {cls.name: cls().probe() for cls in ALL_SOURCES}
