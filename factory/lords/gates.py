"""Ворота, которые нельзя открыть отсутствующими входными данными.

Каждая функция здесь закрывает одну операцию и объясняет, почему именно она
невозможна. Смысл в том, чтобы отказ наступал в одном месте и по одному
правилу, а не выводился заново на каждом вызове: правило, размазанное по коду,
рано или поздно где-нибудь не сработает.

Проверки опираются только на поля, которые есть в любом manifest — `domain`,
`canonical_url`, `target_ref`, `seo_indexing_enabled`. Новых полей они не
требуют. Это сознательно: иначе пакет в старом формате, где новых полей просто
нет, проходил бы мимо ворот — и обход выглядел бы не как обход, а как
совместимость.
"""

from __future__ import annotations

from factory.errors import BlockedAccess, BlockedAnalyticsAccess, BlockedInput, BlockedSeo

#: Операции, каждая со своим отказом. Список закрыт: расширять его — отдельное
#: решение, а не побочный эффект новой фичи.
OPERATIONS = (
    "indexing",
    "production_sitemap",
    "production_deploy",
    "tls_certificate",
    "analytics_account",
    "webmaster_account",
)


def _domain(package: dict) -> str:
    return str(package.get("domain") or "").strip()


def _canonical(package: dict) -> str:
    return str(package.get("canonical_url") or "").strip()


def _target(package: dict) -> str:
    return str(package.get("target_ref") or "").strip()


def check_indexing(package: dict) -> None:
    """Индексацию нельзя включить без домена.

    Индексация без домена бессмысленна и опасна одновременно: поисковику нечего
    сообщить, кроме адреса стенда, а попавший в выдачу стенд убирается оттуда
    неделями.
    """
    if not package.get("seo_indexing_enabled"):
        return
    if not _domain(package):
        raise BlockedSeo(
            "индексацию нельзя включить: домен не передан",
            field="seo_indexing_enabled",
            required_input="domain в manifest",
            blocks_stage="VALIDATING",
        )
    if not _canonical(package):
        raise BlockedSeo(
            "индексацию нельзя включить: canonical_url не передан",
            field="seo_indexing_enabled",
            required_input="canonical_url в manifest",
            blocks_stage="VALIDATING",
        )


def check_production_sitemap(package: dict) -> None:
    """Production-sitemap без домена собрать невозможно.

    Адрес в sitemap абсолютен по спецификации: без хоста запись либо невалидна,
    либо указывает на чужой сайт. Пустая карта — допустимый ответ, выдуманный
    хост — нет.
    """
    if str(package.get("environment")) != "production":
        return
    if not _domain(package):
        raise BlockedInput(
            "production-sitemap не собирается: домен не передан, "
            "а абсолютный адрес без домена невозможен",
            field="metadata.sitemap",
            required_input="domain в manifest",
            blocks_stage="BUILDING",
        )


def check_production_deploy(package: dict) -> None:
    """Production-выкат без цели невозможен — выкатывать некуда."""
    if not _target(package):
        raise BlockedAccess(
            "production-выкат невозможен: цель выката не передана",
            field="target_ref",
            required_input="target_ref и запись в inventory/targets.yaml",
            blocks_stage="PRODUCTION_DEPLOY",
        )
    if not package.get("production_authorized"):
        raise BlockedAccess(
            "production-выкат невозможен: production_authorized не подтверждён",
            field="production_authorized",
            required_input="production_authorized: true",
            blocks_stage="AUTHORIZATION_CHECK",
        )


def check_tls_certificate(package: dict) -> None:
    """Сертификат выпускается на имя. Имени нет — выпускать не на что."""
    if not _domain(package):
        raise BlockedInput(
            "TLS-сертификат не выпускается: домен не передан, "
            "а сертификат выдаётся на доменное имя",
            field="domain",
            required_input="domain в manifest",
            blocks_stage="STAGING_DEPLOY",
        )


def check_analytics_account(package: dict) -> None:
    """Счётчик Метрики заводится на сайт. Сайта без домена не бывает."""
    if not _domain(package):
        raise BlockedAnalyticsAccess(
            "счётчик Метрики не создаётся: домен не передан",
            field="analytics",
            required_input="domain в manifest",
            blocks_stage="VALIDATING",
        )


def check_webmaster_account(package: dict) -> None:
    """Хост в Вебмастере — это домен. Без домена регистрировать нечего."""
    if not _domain(package):
        raise BlockedAnalyticsAccess(
            "хост в Вебмастере не создаётся: домен не передан",
            field="webmaster",
            required_input="domain в manifest",
            blocks_stage="VALIDATING",
        )


CHECKS = {
    "indexing": check_indexing,
    "production_sitemap": check_production_sitemap,
    "production_deploy": check_production_deploy,
    "tls_certificate": check_tls_certificate,
    "analytics_account": check_analytics_account,
    "webmaster_account": check_webmaster_account,
}


def blocked_operations(package: dict) -> dict:
    """Какие операции пакет сейчас не может выполнить и почему.

    Отчёт строится обходом тех же функций, что стоят на пути операции. Второго
    списка причин не существует: он неминуемо разошёлся бы с первым, и отчёт
    начал бы обещать то, чего ворота не пропустят.
    """
    out = {}
    for name in OPERATIONS:
        try:
            CHECKS[name](package)
        except Exception as exc:  # Blocked* — единственное, что здесь возникает
            out[name] = {"status": getattr(exc, "status", "BLOCKED_INPUT"),
                         "reason": str(exc),
                         "required_input": getattr(exc, "required_input", "")}
    return out


def ready_for_deployment(package: dict) -> tuple[bool, list]:
    """Может ли пакет дойти до READY.

    Три отсутствующих значения — домен, canonical и цель — закрывают дорогу
    целиком. Проверка смотрит на сами значения, а не на объявленный статус
    готовности: статус пишет тот же manifest, и доверять ему — значит спрашивать
    у пакета разрешение на самого себя.
    """
    missing = []
    if not _domain(package):
        missing.append("domain")
    if not _canonical(package):
        missing.append("canonical_url")
    if not _target(package):
        missing.append("target_ref")
    return (not missing), missing
