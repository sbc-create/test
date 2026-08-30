"""`robots.txt` называет настоящую причину закрытия, а не одну на все случаи.

На LIVE `lordfilm47.space/robots.txt` сообщает: «Стенд закрыт от индексации:
домен не передан, данные синтетические». При этом на той же странице
`canonical` равен `https://lordfilm47.space/`, а `lords-canonical-state` —
`self`. Домен передан. Половина публично заявленной причины ложна.

Причина ветвления: в генераторе один и тот же текст выдавался и когда домена
действительно нет, и когда домен есть, но индексация выключена в пакете. Для
читателя это разные состояния, и путать их вредно: неверная причина
отправляет искать отсутствующую настройку домена вместо флага индексации.

Данные при этом действительно синтетические (`lords-data-source: fixture/test`),
поэтому вторая половина сообщения остаётся — она проверяема.
"""

from __future__ import annotations

import yaml

from factory.lords import fixtures as fx
from factory.lords import render
from factory.paths import PATHS

SITES = ("lords-01", "lords-02", "lords-03")


def package(site_id: str) -> dict:
    return yaml.safe_load(PATHS.site_package(site_id).read_text(encoding="utf-8"))


def _robots(site_id: str) -> str:
    site = render.render_site(package(site_id), catalog=fx.build_catalog())
    return site.pages["/robots.txt"].body


def test_reason_does_not_claim_a_missing_domain_when_the_domain_is_present():
    for site_id in SITES:
        pkg = package(site_id)
        domain = str(pkg.get("domain") or "").strip()
        if not domain:
            continue
        body = _robots(site_id)
        assert "домен не передан" not in body, (
            f"{site_id}: домен {domain} передан, а robots.txt утверждает обратное:\n{body}"
        )


def test_closed_robots_still_disallows_everything():
    """Формулировка меняется, запрет — нет."""
    for site_id in SITES:
        body = _robots(site_id)
        assert "User-agent: *" in body
        assert "Disallow: /" in body


def test_reason_is_stated_at_all():
    """Молчаливый запрет хуже объяснённого: причина должна быть в файле."""
    for site_id in SITES:
        body = _robots(site_id)
        assert body.lstrip().startswith("#"), f"{site_id}: запрет без объяснения:\n{body}"
