"""Слой аналитики фабрики: Яндекс.Метрика и Яндекс.Вебмастер.

Публичная поверхность узкая и намеренно такая: провайдер, реестр публичных
идентификаторов, описание событий и разметка страницы. Всё, что связано со
значением OAuth-токена, живёт в :mod:`factory.analytics.credentials` и наружу
не отдаётся.
"""
from __future__ import annotations

from factory.analytics import client_codegen, events, registry, snippet
from factory.analytics.credentials import inspect_token_file, load_token, token_path
from factory.analytics.yandex import (
    BLOCKED_DEPLOYMENT,
    PLANNED,
    CounterState,
    CredentialsReport,
    WebmasterState,
    YandexAnalyticsProvider,
    host_url,
    normalize_domain,
    webvisor_enabled,
)

__all__ = [
    "BLOCKED_DEPLOYMENT",
    "PLANNED",
    "CounterState",
    "CredentialsReport",
    "WebmasterState",
    "YandexAnalyticsProvider",
    "client_codegen",
    "events",
    "host_url",
    "inspect_token_file",
    "load_token",
    "normalize_domain",
    "registry",
    "snippet",
    "token_path",
    "webvisor_enabled",
]
