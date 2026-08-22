"""Concrete adapters for the sources named in the operating brief.

None of these can be exercised end-to-end in the current environment: no
credentials are provisioned, and the Yandex endpoints are additionally blocked
by the network policy. They are written so that supplying credentials is the
only remaining step, and so that ``probe()`` reports the true reason today.
"""

from __future__ import annotations

import socket
from urllib.parse import urlsplit

from seo_operator.datasources.base import (
    Availability,
    CredentialedSource,
    SourceStatus,
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


class YandexWebmaster(NetworkGatedSource):
    name = "yandex_webmaster"
    kind = "search_analytics"
    endpoint = "https://api.webmaster.yandex.net"
    required_env = ("YANDEX_WEBMASTER_TOKEN", "YANDEX_WEBMASTER_USER_ID")
    metrics = ("impressions", "clicks", "ctr", "position", "indexing")


class YandexMetrika(NetworkGatedSource):
    name = "yandex_metrika"
    kind = "analytics"
    endpoint = "https://api-metrika.yandex.net"
    required_env = ("YANDEX_METRIKA_TOKEN", "YANDEX_METRIKA_COUNTER_MAP")
    metrics = ("sessions", "depth", "returning", "watch_starts")


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
