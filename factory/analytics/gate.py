"""Ворота аналитики в конвейере.

Отвечают на один вопрос: можно ли выкатывать сайт с включённой аналитикой прямо
сейчас. Ответ «не знаю» здесь не предусмотрен — либо ворота пройдены, либо
названа причина. Недоступный API даёт ``BLOCKED_ANALYTICS_ACCESS``: продолжать
с выдуманным counter ID нельзя, а называть это общим ``BLOCKED_ACCESS`` значит
отправить оператора чинить SSH вместо токена.
"""
from __future__ import annotations

import os

from factory.analytics import registry
from factory.analytics.yandex import YandexAnalyticsProvider, normalize_domain
from factory.errors import BlockedAnalyticsAccess, BlockedInput

#: Проверка живого API — сетевая операция. В тестах и на локальных стендах она
#: выключается явно, а не «случайно не сработала».
LIVE_CHECK_ENV = "FACTORY_ANALYTICS_LIVE_CHECK"


def live_check_enabled(environment: str) -> bool:
    raw = os.environ.get(LIVE_CHECK_ENV)
    if raw is not None:
        return raw.strip().lower() in {"1", "true", "yes"}
    # По умолчанию живая проверка нужна только там, где ошибка видна публике.
    return environment == "production"


def analytics_config(package: dict) -> dict:
    return package.get("analytics") or {}


def check(package: dict, environment: str, *, provider: YandexAnalyticsProvider | None = None) -> list[dict]:
    """Список блокеров. Пустой список означает «ворота пройдены»."""
    config = analytics_config(package)
    blockers: list[dict] = []

    if not config.get("enabled") or config.get("provider") in (None, "none"):
        return blockers

    domain = normalize_domain(str(package.get("domain") or ""))
    hosts = [normalize_domain(h) for h in (config.get("allowed_hosts") or [])]

    if config.get("webvisor"):
        blockers.append(BlockedInput(
            "Вебвизор включён в пакете, а заданием он должен быть выключен.",
            field="analytics.webvisor",
            required_input="analytics.webvisor: false",
            blocks_stage="VALIDATING").as_blocker())

    if environment == "production":
        if not hosts:
            blockers.append(BlockedInput(
                "Список analytics.allowed_hosts пуст: сбор невозможен ни с одного адреса.",
                field="analytics.allowed_hosts",
                required_input=f"Точный production-hostname, например [{domain}]",
                blocks_stage="PRODUCTION_DEPLOY").as_blocker())
        elif domain not in hosts:
            blockers.append(BlockedInput(
                f"Домен пакета {domain} отсутствует в analytics.allowed_hosts ({hosts}).",
                field="analytics.allowed_hosts",
                required_input=f"Добавить {domain} или исправить домен пакета",
                blocks_stage="PRODUCTION_DEPLOY").as_blocker())

        if not config.get("counter_id"):
            blockers.append(BlockedInput(
                "Счётчик Метрики для домена не создан: в пакете нет analytics.counter_id.",
                field="analytics.counter_id",
                required_input="python3 -m factory analytics apply --site <site_id> --confirm-writes",
                blocks_stage="PRODUCTION_DEPLOY").as_blocker())

    if not live_check_enabled(environment):
        return blockers

    # Живая проверка. Отдельный блок и отдельный статус: недоступный API — это
    # не отсутствующее поле пакета, и чинится он не редактированием manifest.
    provider = provider or YandexAnalyticsProvider(dry_run=True)
    try:
        report = provider.validate_credentials()
    except BlockedAnalyticsAccess as exc:
        blockers.append(exc.as_blocker())
        return blockers

    if not report.metrika_ok:
        blockers.append(BlockedAnalyticsAccess(
            f"API Метрики недоступен (HTTP {report.metrika_status}). "
            "Конвейер остановлен: продолжать с выдуманным counter ID запрещено.",
            field="analytics.provider",
            required_input="Действующий OAuth-токен с правами на Метрику",
            blocks_stage="PRODUCTION_DEPLOY").as_blocker())
    return blockers


def indexing_allowed(package: dict, environment: str) -> tuple[bool, str]:
    """Можно ли включать поисковую индексацию. Все условия обязаны выполниться разом.

    Возвращает `(можно, причина первого невыполненного условия)`. Одно «почти
    выполнено» — это «нельзя»: индексация неудачного сайта откатывается месяцами.
    """
    if not package.get("seo_indexing_enabled"):
        return False, "seo_indexing_enabled в пакете выключен"
    if not registry.indexing_enabled():
        return False, "глобальный SEO_INDEXING_ENABLED выключен в config/analytics.json"
    if environment != "production":
        return False, f"окружение {environment}, а не production"
    if not package.get("production_authorized"):
        return False, "в manifest нет production_authorized: true"
    if package.get("fixture"):
        return False, "пакет помечен fixture"

    webmaster = package.get("webmaster") or {}
    if not webmaster.get("enabled"):
        return False, "webmaster.enabled выключен"
    if webmaster.get("verification_status") != "VERIFIED":
        return False, (
            f"права в Вебмастере не подтверждены (статус {webmaster.get('verification_status')})"
        )
    return True, "все условия индексации выполнены"
