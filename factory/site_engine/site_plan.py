"""Сухой прогон заявки: что будет создано, чем занято и как отменить.

План строится из ответов мастера и не выполняет ничего. Это не оговорка в
описании, а проверяемое свойство: `mutations` в плане равен нулю по построению,
и проверка сравнивает содержимое каталога до и после вызова.

План детерминирован. Отметки времени в него не попадают — время создания
заявки берётся из самой заявки, идентификатор задания выводится из её номера.
Иначе «сравните и подтвердите» подтверждает не то, что выполнится.

Требования берутся из общей проверки пакета (`factory.validation`), а не из
второго списка, написанного для мастера: два списка правил расходятся, и
расхождение обнаруживается ровно тогда, когда на него полагаются.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from factory import validation
from factory.site_engine.site_request import Заявка

#: Что мастер не спрашивает, но пакет требует. Значения одинаковы для всех
#: заявок и меняются вместе со схемой, а не по одной витрине.
УМОЛЧАНИЯ: dict[str, Any] = {
    "schema_version": 1,
    "language": "ru",
    "blueprint": "payload-next-multisite",
    "runtime": {"kind": "node", "version": "20"},
    "backup_policy": {"enabled": True, "keep_days": 14},
    "monitoring_policy": {"enabled": True, "checks": ["http", "catalog-freshness"]},
    "retention_policy": {"logs_days": 30, "artifacts_days": 14},
    "rollback_policy": {"keep_releases": 5, "strategy": "symlink-switch"},
    "acceptance": {"manual_review": True, "canary_required": True},
    "network_allowlist": ["127.0.0.1"],
}

#: Разделы, которыми владеет каждый SEO-профиль. Дублировать таблицу проверки
#: здесь нельзя — она берётся оттуда же, откуда её читает блокер.
РАЗДЕЛЫ = validation.PROFILE_OWNED_LISTINGS

#: Контракты, которым обязана соответствовать новая витрина. Перечисляются
#: поимённо: «соответствует контрактам» без списка — не утверждение.
КОНТРАКТЫ = (
    "schemas/site-package.schema.json",
    "operator-identity/1.0.0",
    "PLAYER_CONTRACT: идентификатор воспроизведения только из разрешённых",
    "NOINDEX до подтверждения владельцем",
)


def собрать_пакет(заявка: Заявка) -> dict[str, Any]:
    """Пакет витрины из ответов мастера.

    Разрешение на production и индексацию сюда не попадает ни при каких
    ответах: и то и другое — решение владельца, а не поле формы.
    """
    о = заявка.answers
    домен = (о.get("domain") or {}).get("domain", "")
    профиль = о.get("profile") or {}
    оформление = о.get("branding") or {}
    seo = о.get("seo") or {}
    содержимое = о.get("content") or {}
    правовое = о.get("legal") or {}
    аналитика = о.get("analytics") or {}
    хост = f"www.{домен}" if seo.get("canonicalHostForm") == "www" else домен
    слэш = "/" if seo.get("trailingSlash", True) else ""

    пакет: dict[str, Any] = dict(УМОЛЧАНИЯ)
    пакет.update(
        {
            "job_id": f"{заявка.site_id}-{заявка.request_id[:8]}",
            "site_id": заявка.site_id,
            "requested_action": "create",
            "domain": домен,
            "aliases": list((о.get("domain") or {}).get("aliases") or []),
            "canonical_url": f"https://{хост}{слэш}" if домен else "",
            "environment": профиль.get("environment", "staging"),
            # Разрешение владельца не выдаётся мастером. Ни один ответ в форме
            # не переводит это поле в True.
            "production_authorized": False,
            "seo_indexing_enabled": False,
            "target_ref": профиль.get("targetRef", ""),
            "theme_ref": о.get("template", {}).get("themeRef", ""),
            "brand": {
                "name": оформление.get("brandName", ""),
                "legal_name": оформление.get("legalName", ""),
                "colors": {"primary": оформление.get("primaryColor", "")},
            },
            "tenant": {
                "seo_profile": профиль.get("seoProfile", ""),
                "owned_listings": list(РАЗДЕЛЫ.get(профиль.get("seoProfile", ""), [])),
                "theme": о.get("template", {}).get("themeRef", ""),
            },
            "content_source": {
                "adapter": содержимое.get("contentSource", ""),
                "types": list(содержимое.get("contentTypes") or []),
            },
            "content_types": list(содержимое.get("contentTypes") or []),
            "metadata": {
                "canonical_policy": {
                    "scheme": "https",
                    "host_form": seo.get("canonicalHostForm", "non_www"),
                    "trailing_slash": bool(seo.get("trailingSlash", True)),
                    "case": "lower",
                }
            },
            "seo": {"indexing": "noindex", "sitemap": False},
            "navigation": {"primary": []},
            "legal": {
                "entity": правовое.get("legalEntity", ""),
                "contact_email": правовое.get("contactEmail", ""),
                "rights_confirmed": bool(правовое.get("rightsConfirmed")),
            },
            "analytics": {
                # Только ссылки. Значения ключей в пакет не попадают.
                "provider_ref": аналитика.get("analyticsRef", ""),
            },
            "advertising": {"provider_ref": аналитика.get("adsRef", "")},
            "requested_by": заявка.created_by or "self-service",
            "created_at": заявка.created_at,
        }
    )
    return пакет


def _ресурсы(пакет: dict[str, Any]) -> list[str]:
    site_id = пакет["site_id"]
    площадка = пакет.get("target_ref") or "неизвестна"
    return [
        f"config/site-profiles/{site_id}.json",
        f"sites/{site_id}/package.yaml",
        f"var/targets/{площадка}/{site_id}/releases/<новый>",
        f"var/targets/{площадка}/{site_id}/current",
        f"var/state/site-requests/{site_id}",
        f"домен {пакет.get('domain') or '—'}",
    ]


def _шаги(пакет: dict[str, Any]) -> list[dict[str, Any]]:
    site_id = пакет["site_id"]
    return [
        {"id": "validate_package", "detail": "проверка пакета по схеме и правилам",
         "mutation": False},
        {"id": "reserve_domain", "detail": f"занять домен {пакет.get('domain') or '—'}",
         "mutation": True, "dryRun": True},
        {"id": "create_profile", "detail": f"config/site-profiles/{site_id}.json",
         "mutation": True, "dryRun": True},
        {"id": "write_package", "detail": f"sites/{site_id}/package.yaml",
         "mutation": True, "dryRun": True},
        {"id": "build_release", "detail": "сборка выпуска на площадке",
         "mutation": True, "dryRun": True},
        {"id": "canary", "detail": "изолированная канарейка под NOINDEX",
         "mutation": True, "dryRun": True},
        {"id": "verify", "detail": "проверки доступности, каталога и разметки",
         "mutation": False},
    ]


def _откат(пакет: dict[str, Any]) -> dict[str, Any]:
    site_id = пакет["site_id"]
    площадка = пакет.get("target_ref") or "неизвестна"
    return {
        "steps": [
            {"id": "drop_canary", "detail": "снять канарейку, не трогая боевые витрины"},
            {"id": "remove_release", "detail": f"удалить var/targets/{площадка}/{site_id}"},
            {"id": "remove_package", "detail": f"удалить sites/{site_id}/package.yaml"},
            {"id": "remove_profile", "detail": f"удалить config/site-profiles/{site_id}.json"},
            {"id": "release_domain", "detail": f"освободить домен {пакет.get('domain') or '—'}"},
        ],
        "note": (
            "Откат не трогает существующие витрины: у новой витрины свои каталог, "
            "замок и площадка."
        ),
    }


def план(заявка: Заявка, root: Path, env: dict[str, str] | None = None) -> dict[str, Any]:
    """Полный сухой прогон. Ничего не выполняет и ничего не пишет."""
    пакет = собрать_пакет(заявка)
    не_заполнено = [
        {
            "step": ш["id"],
            "title": ш["title"],
            "required_input": ", ".join(ш["required"]) or ш["hint"],
        }
        for ш in заявка.as_dict()["steps"]
        if not ш["done"]
    ]

    итог = validation.validate_package(пакет, заявка.site_id)
    блокеры = [б.as_dict() for б in итог.blockers]
    требования = не_заполнено + [
        {
            "step": б["field"],
            "title": б["reason"],
            "required_input": б["required_input"],
            "status": б["status"],
        }
        for б in блокеры
    ]

    тело: dict[str, Any] = {
        "requestId": заявка.request_id,
        "siteId": заявка.site_id,
        "ready": not не_заполнено and itog_ok(итог),
        "package": пакет,
        "steps": _шаги(пакет),
        "resources": _ресурсы(пакет),
        "locks": [f"site:{заявка.site_id}:{пакет.get('environment', 'staging')}"],
        "contracts": list(КОНТРАКТЫ),
        "blockers": блокеры,
        "warnings": list(итог.warnings),
        "requirements": требования,
        "rollback": _откат(пакет),
        "mutations": 0,
    }
    # Отпечаток считается по тому, что будет сделано, а не по всему ответу:
    # предупреждения и порядок требований на исполнение не влияют, а меняются
    # чаще. Отпечаток, реагирующий на них, обесценивает сравнение.
    основа = {
        "package": пакет,
        "steps": тело["steps"],
        "resources": тело["resources"],
        "locks": тело["locks"],
        "contracts": тело["contracts"],
        "rollback": тело["rollback"],
    }
    тело["planHash"] = "sha256:" + hashlib.sha256(
        json.dumps(основа, ensure_ascii=False, sort_keys=True).encode("utf-8")
    ).hexdigest()
    return тело


def itog_ok(итог) -> bool:
    """Готовность к исполнению. Отдельной функцией — чтобы условие читалось."""
    return bool(итог.ok)
