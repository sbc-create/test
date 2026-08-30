"""Главная витрины отдаёт `Organization` рядом с `WebSite`, как требует матрица.

`knowledge/SEO_INDEXABILITY_MATRIX.yaml` для типа `home` объявляет
`structured_data: [WebSite, Organization]`. На LIVE все три витрины Lords
отдавали только `WebSite`: слова `Organization` в разметке не было вовсе
(проверено 2026-08-30). У Yummy оба типа присутствуют.

Важно, чего этот тест НЕ требует. Юридического имени, логотипа, контактов и
документов у витрин нет: в пакете `brand.legal_name`, `brand.logo_ref`,
`legal.owner` и контакты равны `null`, `legal.documents` пуст. Выдумывать их
нельзя, поэтому `Organization` несёт ровно два поля — имя и адрес, — и оба
уже присутствуют на странице: имя вычисляет `_brand_name` (объявленное имя,
иначе домен, никогда технический идентификатор), адрес — сам домен.

Тест закрепляет и это ограничение: появление в разметке юридических полей,
которых нет в пакете, должно валить проверку так же, как их отсутствие.
"""

from __future__ import annotations

import json
import re

import yaml

from factory.lords import fixtures as fx
from factory.lords import render
from factory.paths import PATHS

SITES = ("lords-01", "lords-02", "lords-03")
LD = re.compile(r'<script type="application/ld\+json">(.*?)</script>', re.S)

FORBIDDEN_WHEN_UNKNOWN = ("legalName", "logo", "email", "telephone", "address", "founder")


def package(site_id: str) -> dict:
    return yaml.safe_load(PATHS.site_package(site_id).read_text(encoding="utf-8"))


def _home_nodes(site_id: str) -> list[dict]:
    site = render.render_site(package(site_id), catalog=fx.build_catalog())
    body = site.pages["/"].body
    nodes: list[dict] = []
    for raw in LD.findall(body):
        data = json.loads(raw)
        for node in (data if isinstance(data, list) else [data]):
            if isinstance(node, dict):
                nodes.append(node)
    return nodes


def test_home_declares_both_website_and_organization():
    for site_id in SITES:
        types = {n.get("@type") for n in _home_nodes(site_id)}
        assert "WebSite" in types, f"{site_id}: нет WebSite, типы: {sorted(types)}"
        assert "Organization" in types, f"{site_id}: нет Organization, типы: {sorted(types)}"


def test_organization_carries_only_facts_the_package_has():
    for site_id in SITES:
        org = next(n for n in _home_nodes(site_id) if n.get("@type") == "Organization")
        assert org.get("name"), f"{site_id}: у Organization нет имени"
        assert org.get("url", "").startswith("https://"), f"{site_id}: у Organization нет адреса"
        pkg = package(site_id)
        assert org["name"] != pkg.get("site_id"), (
            f"{site_id}: в разметку попал технический идентификатор вместо имени"
        )
        for field in FORBIDDEN_WHEN_UNKNOWN:
            assert field not in org, (
                f"{site_id}: Organization несёт поле {field!r}, которого нет в пакете"
            )


def test_website_node_carries_its_url():
    """Без адреса узел `WebSite` не связывается с сайтом, который описывает."""
    for site_id in SITES:
        site = next(n for n in _home_nodes(site_id) if n.get("@type") == "WebSite")
        assert site.get("url", "").startswith("https://"), f"{site_id}: у WebSite нет url"
