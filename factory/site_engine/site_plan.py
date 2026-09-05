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

#: Пресет пакета: всё, что одинаково для новых витрин профиля. Лежит в
#: конфигурации, а не в коде, и взят из рабочего пакета — пакет из придуманных
#: значений проходит схему и падает на первой же настоящей проверке.
ПРЕСЕТЫ = "config/site-request-presets"
ПРОФИЛЬ_ПО_УМОЛЧАНИЮ = "video-showcase"

#: Разделы, которыми владеет каждый SEO-профиль. Таблица берётся оттуда же,
#: откуда её читает блокер: две копии разошлись бы на первом же изменении.
РАЗДЕЛЫ = validation.PROFILE_OWNED_LISTINGS

#: Контракты, которым обязана соответствовать новая витрина. Перечисляются
#: поимённо: «соответствует контрактам» без списка — не утверждение.
#: Поля, указывающие на файлы витрины: логотип, значок, тексты, каталог, тема.
#: Их отсутствие не мешает канарейке и мешает публикации.
ПОЛЯ_АКТИВОВ = (
    "logo_ref",
    "favicon_ref",
    "body_ref",
    "catalog_ref",
    "content_package_ref",
    "contract_ref",
    "theme_ref",
)

КОНТРАКТЫ = (
    "schemas/site-package.schema.json",
    "operator-identity/1.0.0",
    "PLAYER_CONTRACT: идентификатор воспроизведения только из разрешённых",
    "NOINDEX до подтверждения владельцем",
)


def пресет(root: Path, профиль: str = ПРОФИЛЬ_ПО_УМОЛЧАНИЮ) -> dict[str, Any]:
    """Основа пакета. Отсутствие пресета — не повод собрать «что-нибудь»."""
    import yaml

    путь = Path(root) / ПРЕСЕТЫ / f"{профиль}.yaml"
    if not путь.is_file():
        return {}
    try:
        данные = yaml.safe_load(путь.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError):
        return {}
    return данные if isinstance(данные, dict) else {}


def _слить(основа: dict[str, Any], поверх: dict[str, Any]) -> dict[str, Any]:
    """Наложение по разделам, а не заменой целиком.

    Мастер задаёт название бренда, но не его цвета и не ссылки на логотип;
    замена раздела целиком стёрла бы остальное и собрала пакет, не проходящий
    собственную проверку.
    """
    итог = dict(основа)
    for ключ, значение in поверх.items():
        если_словарь = isinstance(значение, dict) and isinstance(итог.get(ключ), dict)
        итог[ключ] = _слить(итог[ключ], значение) if если_словарь else значение
    return итог


def собрать_пакет(заявка: Заявка, root: Path | None = None) -> dict[str, Any]:
    """Пакет витрины: пресет профиля плюс ответы мастера.

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
    хост = f"www.{домен}" if seo.get("canonicalHostForm") == "www" else домен
    слэш = "/" if seo.get("trailingSlash", True) else ""

    основа = пресет(root if root is not None else Path("."))
    поверх: dict[str, Any] = {
        "job_id": f"{заявка.site_id}-{заявка.request_id[:8]}",
        "site_id": заявка.site_id,
        "requested_action": "create",
        "domain": домен,
        "aliases": list((о.get("domain") or {}).get("aliases") or []),
        "canonical_url": f"https://{хост}{слэш}" if домен else "",
        "environment": профиль.get("environment", "staging"),
        # Разрешение владельца не выдаётся мастером ни при каком ответе.
        "production_authorized": False,
        "seo_indexing_enabled": False,
        "target_ref": профиль.get("targetRef", ""),
        "theme_ref": о.get("template", {}).get("themeRef", ""),
        "brand": {
            "name": оформление.get("brandName", ""),
            "legal_name": оформление.get("legalName", ""),
            "colors": {"primary": оформление.get("primaryColor", "")},
        },
        # Типы содержимого в пакете — набор флагов с закрытым списком имён.
        # Список приходит из схемы, а не из кода: имена типов там доменные, и
        # универсальному модулю их называть нечем и незачем.
        "content_types": {т: True for т in (содержимое.get("contentTypes") or [])},
        "metadata": {
            "canonical_policy": {
                "scheme": "https",
                "host_form": seo.get("canonicalHostForm", "non_www"),
                "trailing_slash": bool(seo.get("trailingSlash", True)),
                "case": "lower",
            }
        },
        "legal": {
            "owner": правовое.get("legalEntity", ""),
            "contacts": {"email": правовое.get("contactEmail", "")},
        },
        "requested_by": заявка.created_by or "self-service",
        "created_at": заявка.created_at,
    }
    if профиль.get("seoProfile"):
        поверх["tenant"] = {
            # Идентификатор тенанта выводится из имени витрины: отдельное поле
            # в мастере означало бы два имени одного и того же и рано или
            # поздно два разных ответа на вопрос «чья это витрина».
            "slug": _слаг(заявка.site_id),
            "seo_profile": профиль["seoProfile"],
            "owned_listings": list(РАЗДЕЛЫ.get(профиль["seoProfile"], [])),
            "theme": о.get("template", {}).get("themeRef", ""),
            # Канарейка не индексируется. Значение выставляется здесь, а не
            # оставляется на пресет: пресет когда-нибудь скопируют с боевой
            # витрины вместе с включённой индексацией.
            "indexing_enabled": False,
            "allow_guest_comments": False,
        }
    if содержимое.get("contentSource"):
        поверх["content_source"] = {
            "kind": содержимое["contentSource"],
            "rights_confirmed": bool(правовое.get("rightsConfirmed")),
        }
    # Ссылка на счётчик аналитики в пакет не попадает: схема пакета его не
    # принимает, и это правильно — токены и ссылки на них живут в инвентаре, а
    # не в манифесте витрины. Ссылка остаётся в заявке и попадает в требования
    # плана как отдельный шаг для владельца.
    поверх["analytics"] = {"provider": "none", "enabled": False}
    return _слить(основа, поверх)


def _слаг(site_id: str) -> str:
    """Идентификатор тенанта: строчные буквы, цифры и подчёркивание."""
    чистый = "".join(c if c.isalnum() else "_" for c in site_id.lower())
    чистый = чистый.lstrip("0123456789_") or "site"
    return чистый[:31]


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
    пакет = собрать_пакет(заявка, root)
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
    # Недостающие файлы отделены от остального намеренно. Канарейка нужна,
    # чтобы посмотреть на устройство витрины до того, как нарисован логотип и
    # написаны юридические тексты; она не индексируется и никому не показана.
    # Смешать их с настоящими препятствиями значило бы либо не дать завести
    # канарейку вовсе, либо тихо считать отсутствующий логотип мелочью и на
    # публикации. Поэтому два разных ответа: «готов к канарейке» и «готов».
    активы = [б for б in блокеры if str(б.get("field", "")).endswith(ПОЛЯ_АКТИВОВ)]
    мешают = [б for б in блокеры if б not in активы]
    ссылки = []
    аналитика = (заявка.answers.get("analytics") or {})
    for имя, подпись in (("analyticsRef", "счётчик аналитики"), ("adsRef", "рекламный аккаунт")):
        if аналитика.get(имя):
            ссылки.append(
                {
                    "step": имя,
                    "title": f"{подпись}: ссылка записана, подключение — отдельным решением",
                    "required_input": str(аналитика[имя]),
                    "status": "OWNER_ACTION",
                }
            )
    требования = не_заполнено + ссылки + [
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
        "ready": not не_заполнено and not блокеры,
        "canaryReady": not не_заполнено and not мешают,
        "missingAssets": активы,
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
