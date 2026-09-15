"""Реестр портфеля и сетевой allowlist не расходятся молча.

Пустой портфель при девяти работающих доменах — это не «нет сайтов», а
неучтённый портфель: ежедневный SEO-цикл выбирает работу из портфеля, и пока
тот пуст, цикл честно отчитывается «сайтов нет», хотя сайты отвечают HTTP 200.
Ровно так контур и простоял с 2026-08-22.

Вторая половина той же ошибки — домен в портфеле, которого нет в allowlist.
Тогда оператор обязан читать сайт и не имеет права этого делать, и отказ
всплывает не здесь, а в ночном прогоне.

Тест держит оба конца: каждый рабочий сайт портфеля имеет запись в allowlist с
методом GET, и ни один синтетический тенант в рабочий реестр не попадает.
"""

from __future__ import annotations

import json
from pathlib import Path
from urllib.parse import urlsplit

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
PORTFOLIO = REPO_ROOT / "config" / "portfolio.json"
FIXTURE_PORTFOLIO = REPO_ROOT / "config" / "portfolio.fixture.json"
ALLOWLIST = REPO_ROOT / "inventory" / "network-allowlist.yaml"


def _portfolio() -> dict:
    return json.loads(PORTFOLIO.read_text(encoding="utf-8"))


def _allowed_hosts() -> dict[str, list[str]]:
    data = yaml.safe_load(ALLOWLIST.read_text(encoding="utf-8"))
    return {entry["host"]: list(entry.get("methods", [])) for entry in data.get("hosts", [])}


def _domains(portfolio: dict) -> list[str]:
    out = []
    for site in portfolio["sites"]:
        host = urlsplit(site["base_url"]).hostname
        assert host, f"{site['site_id']}: base_url без хоста"
        out.append(host)
    return out


def test_real_portfolio_is_not_empty() -> None:
    portfolio = _portfolio()
    real = [s for s in portfolio["sites"] if not s.get("synthetic", False)]
    assert real, (
        "рабочий портфель пуст. Пустой реестр заставляет ежедневный цикл "
        "отчитываться «сайтов нет» при работающих доменах."
    )


def test_every_portfolio_domain_is_readable_by_the_operator() -> None:
    allowed = _allowed_hosts()
    missing = []
    for site in _portfolio()["sites"]:
        if site.get("synthetic", False):
            continue
        host = urlsplit(site["base_url"]).hostname
        if host not in allowed:
            missing.append(f"{site['site_id']}: {host} отсутствует в network-allowlist")
        elif "GET" not in allowed[host]:
            missing.append(f"{site['site_id']}: {host} есть в allowlist, но без метода GET")
    assert not missing, "оператор обязан читать эти сайты, но не имеет права:\n" + "\n".join(
        missing
    )


def test_portfolio_domains_are_unique() -> None:
    domains = _domains(_portfolio())
    duplicates = sorted({d for d in domains if domains.count(d) > 1})
    assert not duplicates, f"один домен объявлен несколькими сайтами: {duplicates}"


def test_synthetic_tenant_never_leaks_into_the_real_registry() -> None:
    portfolio = _portfolio()
    leaked = [s["site_id"] for s in portfolio["sites"] if s.get("synthetic", False)]
    assert not leaked, (
        f"синтетические тенанты в рабочем реестре: {leaked}. "
        "Их место — config/portfolio.fixture.json."
    )

    fixture = json.loads(FIXTURE_PORTFOLIO.read_text(encoding="utf-8"))
    real_ids = {s["site_id"] for s in portfolio["sites"]}
    fixture_ids = {s["site_id"] for s in fixture["sites"]}
    assert not (real_ids & fixture_ids), (
        f"один и тот же site_id в обоих реестрах: {sorted(real_ids & fixture_ids)}"
    )


def test_no_third_party_host_is_listed_as_our_site() -> None:
    """amd.online — чужой сайт, а не наша витрина.

    Он назван в задании как ориентир, и соблазн завести его как свой домен
    существует ровно до первой попытки что-нибудь на нём поменять.
    """
    assert "amd.online" not in _domains(_portfolio()), (
        "amd.online принадлежит стороннему владельцу (AniMedia.Online) и не может "
        "числиться сайтом портфеля"
    )


@pytest.mark.parametrize(
    "host",
    [
        "lordfilm47.space",
        "lordserial33.biz",
        "1lordserials1.online",
        "zonafilm.space",
        "animedia.icu",
        "animedia.space",
        "yummyani.site",
        "yummyani.org",
        "yummyani.biz",
    ],
)
def test_known_live_host_is_in_the_portfolio(host: str) -> None:
    assert host in _domains(_portfolio()), (
        f"{host} отвечает на запросы и имеет профиль, но в портфеле его нет"
    )
