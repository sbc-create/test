"""Внутренняя ссылка витрины ведёт на страницу, которая в этой же сборке есть.

Повод — живой отказ: на `1lordserials1.online` главная ссылалась на
`/collections/`, а раздел отдавал 404. Причина не в вёрстке и не в маршрутах
nginx: ссылка «Все подборки» и сама страница подборок включаются **разными**
условиями. Ссылка выводится по `layout.show_collection_cards`, страница — по
`collections_on and "collections_index" in by_section`. Когда тип подборок
неактивен, ссылка переживает страницу.

Тест закрепляет инвариант целиком, а не один случай: любая внутренняя ссылка
любой страницы должна разрешаться в страницу этой же сборки либо в известный
источник редиректа.
"""

from __future__ import annotations

import re

import yaml

from factory.lords import fixtures as fx
from factory.lords import render
from factory.paths import PATHS

SITES = ("lords-01", "lords-02", "lords-03")
HREF = re.compile(r'href="(/[^"#?]*)"')


def package(site_id: str) -> dict:
    return yaml.safe_load(PATHS.site_package(site_id).read_text(encoding="utf-8"))


def _broken_links(site_id: str) -> list[tuple[str, str]]:
    site = render.render_site(package(site_id), catalog=fx.build_catalog())
    known = set(site.pages)
    known |= {r.get("source", "") for r in getattr(site, "redirects", []) or []}
    broken: list[tuple[str, str]] = []
    for path, page in site.pages.items():
        for href in HREF.findall(page.body):
            if href in known:
                continue
            # Статика не является страницей и в pages не лежит.
            if href.startswith(("/assets/", "/static/")) or "." in href.rsplit("/", 1)[-1]:
                continue
            broken.append((path, href))
    return broken


def test_every_internal_link_resolves_to_a_generated_page():
    report: dict[str, list[tuple[str, str]]] = {}
    for site_id in SITES:
        broken = _broken_links(site_id)
        if broken:
            report[site_id] = broken
    assert not report, (
        "внутренние ссылки ведут на страницы, которых нет в сборке: "
        + "; ".join(
            f"{site}: " + ", ".join(f"{src} → {dst}" for src, dst in sorted(set(links))[:6])
            for site, links in report.items()
        )
    )
