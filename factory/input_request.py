"""Единый пакет запроса недостающих входных данных.

Правило §13: не спрашивать по одному вопросу в процессе работы. Отсутствующее
собирается автоматически из состояния фабрики и выдаётся одним списком.
"""
from __future__ import annotations

import json
from pathlib import Path

from factory import blueprint, inventory, validation
from factory.paths import PATHS


def _item(field: str, why: str, fmt: str, example: str, where: str, blocks: str) -> dict:
    return {"field": field, "why": why, "format": fmt, "example_without_secret": example,
            "where_to_put": where, "blocks_stage": blocks}


def collect() -> list[dict]:
    items: list[dict] = []

    if not inventory.all_licenses():
        items.append(_item(
            "dle_license", "Одна лицензия DLE покрывает один домен второго уровня и его поддомены; без записи production-установка невозможна.",
            "YAML-запись в inventory/dle-licenses.yaml", "ref: lic-001, covered_domain: example.tld, version: '20.0', license_key_secret_ref: env:FACTORY_DLE_LICENSE_LIC001",
            "inventory/dle-licenses.yaml (сам ключ — только через secret_ref)", "PRODUCTION_DEPLOY → BLOCKED_LICENSE"))
    if not inventory.load("dle-distributions.yaml").get("distributions"):
        items.append(_item(
            "dle_distribution", "Установка DLE выполняется только из официального лицензионного архива с зафиксированной контрольной суммой.",
            "файл + запись с sha256", "DLE_20.0.zip, sha256: <64 hex>",
            "blueprints/dle20/dist/ (в git не попадает) + inventory/dle-distributions.yaml", "BUILDING/STAGING_DEPLOY → BLOCKED_INPUT"))
    status = blueprint.check("dle20")
    if not status.ready:
        items.append(_item(
            "dle_paths_profile", "Изменяемые/неизменяемые/общие пути DLE, точки входа установщика и требования PHP/БД нельзя угадывать (§3.8).",
            "YAML по образцу blueprints/dle20/profiles/paths.template.yaml",
            "writable_paths: [ ... ], installer_entrypoints: [ ... ], runtime.php.min_version: '8.x'",
            "blueprints/dle20/profiles/paths.yaml", "STAGING_DEPLOY → BLOCKED_INPUT"))
    if not inventory.load("ssh-hosts.yaml").get("hosts"):
        items.append(_item(
            "ssh_host", "Без цели по SSH фабрика не может выкатить сайт на реальный staging/production.",
            "YAML-запись", "ref: stage-1, hostname: staging.example.tld, deploy_user: dle-deploy, known_hosts_entry_ref: inventory/known_hosts.d/stage-1",
            "inventory/ssh-hosts.yaml; приватный ключ — только через ssh_key_secret_ref", "STAGING_DEPLOY → BLOCKED_ACCESS"))
    if not inventory.load("dns-zones.yaml").get("zones"):
        items.append(_item(
            "dns_zone", "DNS cutover выполняется отдельным журналируемым шагом и требует scoped-токена зоны.",
            "YAML-запись", "ref: example-tld, zone: example.tld, api_token_secret_ref: env:FACTORY_DNS_TOKEN_EXAMPLE_TLD, scope: zone_records_only",
            "inventory/dns-zones.yaml", "PRODUCTION_DEPLOY → BLOCKED_ACCESS"))

    items.append(_item(
        "vk_catalog", "Каждый пакет обязан ссылаться на разрешённый каталог/выгрузку VK и rights manifest: публичная доступность ролика правом не является.",
        "файл выгрузки + версия + sha256 + rights manifest",
        "catalog_ref: content/vk-catalog-2026-08.json, catalog_sha256: <64 hex>, rights_manifest_ref: content/rights.yaml",
        "sites/<site_id>/content/", "BUILDING → BLOCKED_RIGHTS"))
    items.append(_item(
        "vk_player_contract", "Схема встраивания белого плеера не выдумывается: без contract доступен только mock и только для staging.",
        "официальный/внутренний документ + ref", "contract_ref: content/vk-player-contract.yaml, embed_template: <из contract>",
        "sites/<site_id>/content/", "BUILDING → BLOCKED_RIGHTS"))
    items.append(_item(
        "vk_ads_contract", "Рекламный слой подключается только по согласованному contract VK/Adman/AdTech с placement/product ID и перечнем разрешённых событий.",
        "документ + placement IDs + policy refs + secret_ref",
        "provider: vk_adman_adtech, placements: [{placement_id: ..., page_types: [...], reserved_size: {height: 250}}]",
        "sites/<site_id>/content/ + secret_ref на токен", "BUILDING → BLOCKED_RIGHTS"))
    items.append(_item(
        "brand_and_legal", "Бренд, логотипы, палитра, юридическое лицо, контакты и тексты правовых документов берутся только из переданных данных.",
        "файлы + поля пакета", "brand.logo_ref: brand/logo.svg, legal.owner: ООО «...», legal.contacts.email: info@example.tld",
        "sites/<site_id>/brand/, sites/<site_id>/legal/", "BUILDING → BLOCKED_INPUT"))
    items.append(_item(
        "acceptance_baseline", "Визуальное сравнение требует утверждённого baseline: сохранение скриншота сравнением не является.",
        "PNG-файлы + пороги", "acceptance.reference_screenshots: [qa/baseline/home-390.png]",
        "sites/<site_id>/qa/baseline/", "STAGING_QA → QA_FAILED"))
    items.append(_item(
        "webmaster_access", "Подтверждение в Google Search Console и Яндекс Вебмастере нужно для наблюдения за индексацией после запуска.",
        "verification ID (уникальный на каждый сайт)", "seo.webmaster_verification_refs.google_search_console: google-site-verification=...",
        "sites/<site_id>/package.yaml", "MONITORING"))
    items.append(_item(
        "official_docs_egress", "Официальные источники (dle-news.com, developers.google.com, yandex.ru, web.dev, playwright.dev, w3.org) закрыты egress-политикой сессии — сверка SEO/DLE-правил с первоисточником невозможна.",
        "разрешение хостов в egress allowlist ИЛИ переданные официальные экспорты страниц",
        "allowlist: dle-news.com, developers.google.com, yandex.ru, web.dev",
        "настройки окружения сессии или knowledge/imported/", "DISCOVERY (knowledge freeze помечен unverified)"))

    for package_path in sorted(PATHS.sites.glob("*/package.yaml")):
        site_id = package_path.parent.name
        result = validation.validate(site_id)
        for blocker in result.blockers:
            items.append(_item(f"{site_id}: {blocker.field}", blocker.reason, "см. schemas/site-package.schema.json",
                               "-", f"sites/{site_id}/", f"{blocker.blocks_stage} → {blocker.status}"))
    return items


def generate(docs_dir: Path | None = None) -> tuple[Path, Path, list[dict]]:
    """Собирает пакет недостающих данных.

    `docs_dir` существует ради тестов: без него проверка писала прямо в
    `docs/INPUT_REQUEST.md` — файл под контролем версий. Прогон тестов оставлял
    после себя изменённое рабочее дерево, а правило репозитория прямое: тесты не
    пишут за пределы `var/` и `artifacts/`.
    """
    items = collect()
    json_path = PATHS.artifact_dir("input-request") / "input-request.json"
    json_path.write_text(json.dumps({"items": items, "count": len(items)}, ensure_ascii=False, indent=2), encoding="utf-8")
    lines = [
        "# INPUT_REQUEST — недостающие входные данные",
        "",
        "Сформировано `python3 -m factory input-request`. Один пакет вместо череды вопросов (§13).",
        "**Секреты в этот файл не вписываются**: указывается только `secret_ref` и место, куда положить значение.",
        "",
        "| Поле | Зачем нужно | Формат | Пример без секрета | Куда положить | Что блокирует |",
        "|---|---|---|---|---|---|",
    ]
    for item in items:
        lines.append("| `{field}` | {why} | {format} | `{example_without_secret}` | {where_to_put} | {blocks_stage} |".format(
            **{k: str(v).replace("|", "\\|") for k, v in item.items()}))
    lines.append("")
    md_path = (Path(docs_dir) if docs_dir else PATHS.docs) / "INPUT_REQUEST.md"
    md_path.write_text("\n".join(lines), encoding="utf-8")
    return md_path, json_path, items
