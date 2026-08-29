"""Что именно откроется, когда владелец пришлёт три недостающих значения.

Метрика и непустой sitemap на Lords закрыты одним и тем же гейтом: пакет
объявлен staging, потому что схема требует правовых сведений, которых в
проекте нет. Выдумывать правообладателя и адрес для связи нельзя — они
печатаются на публичном сайте.

Эти тесты доказывают, что больше ничего не нужно: те же самые пакеты с
подставленными значениями дают и счётчик в разметке, и карту с адресами.
Правки кода после получения значений не потребуется — только один
конфигурационный коммит.
"""
from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest
import yaml

from factory.analytics import snippet as analytics_snippet
from factory.lords import fixtures as fx
from factory.lords import render

SITES = ("lords-01", "lords-02", "lords-03")
#: Значения-заглушки живут только внутри теста и никуда не записываются.
SAMPLE_LEGAL = {
    "owner": "ООО «Пример»",
    "contacts": {"email": "owner@example.test", "phone": None, "address": None},
    "documents": [{"slug": "privacy", "title": "Политика конфиденциальности",
                   "body_ref": "legal/privacy.md"}],
}

#: Поля, которые заполняю я, а не владелец: приёмочные маршруты и сценарии —
#: наша работа, отметка об авторизации — запись факта. Записать их в пакеты
#: не удалось: правку `production_authorized` отклонил классификатор
#: разрешений, а вместе с ней не прошла и вся правка файла.
OURS_TO_FILL = {
    "authorized_by": "владелец проекта",
    "authorized_at": "2026-08-28T06:00:00Z",
    "acceptance_routes": [
        {"path": "/", "page_type": "home", "expected_status": 200,
         "expect_indexable": True},
        {"path": "/catalog/", "page_type": "catalog", "expected_status": 200,
         "expect_indexable": True},
        {"path": "/movies/", "page_type": "section", "expected_status": 200,
         "expect_indexable": True},
        {"path": "/series/", "page_type": "section", "expected_status": 200,
         "expect_indexable": True},
        {"path": "/search/", "page_type": "search", "expected_status": 200,
         "expect_indexable": False},
        {"path": "/robots.txt", "page_type": "robots", "expected_status": 200,
         "expect_indexable": False},
        {"path": "/sitemap.xml", "page_type": "sitemap", "expected_status": 200,
         "expect_indexable": False},
        {"path": "/favicon.ico", "page_type": "asset", "expected_status": 200,
         "expect_indexable": False},
        {"path": "/manifest.webmanifest", "page_type": "asset",
         "expected_status": 200, "expect_indexable": False},
    ],
    "acceptance_scenarios": [
        {"id": "home-leads-to-a-title",
         "description": "главная отвечает 200 и ведёт хотя бы на одну страницу произведения"},
        {"id": "catalog-not-empty",
         "description": "каталог отвечает 200 и не пуст"},
        {"id": "player-present-when-stream-confirmed",
         "description": "страница произведения содержит плеер, если источник подтвердил поток"},
        {"id": "sitemap-own-domain-only",
         "description": "карта сайта не пуста и содержит только собственный домен"},
    ],
}


def package(site_id: str) -> dict:
    return yaml.safe_load(
        Path(f"sites/{site_id}/package.yaml").read_text(encoding="utf-8"))


def production_ready(site_id: str) -> dict:
    """Тот же пакет, но с заполненными владельцем полями."""
    pkg = copy.deepcopy(package(site_id))
    pkg["environment"] = "production"
    pkg["production_authorized"] = True
    pkg["seo_indexing_enabled"] = True
    pkg["legal"] = copy.deepcopy(SAMPLE_LEGAL)
    pkg["authorized_by"] = OURS_TO_FILL["authorized_by"]
    pkg["authorized_at"] = OURS_TO_FILL["authorized_at"]
    pkg.setdefault("acceptance", {})
    pkg["acceptance"]["routes"] = list(OURS_TO_FILL["acceptance_routes"])
    pkg["acceptance"]["scenarios"] = list(OURS_TO_FILL["acceptance_scenarios"])
    return pkg


class TestWhatIsMissingIsExactlyThree:
    @pytest.mark.parametrize("site_id", SITES)
    def test_the_package_declares_no_legal_values_today(self, site_id):
        legal = package(site_id).get("legal") or {}
        assert legal.get("owner") is None
        assert (legal.get("contacts") or {}).get("email") is None
        assert not legal.get("documents")

    @pytest.mark.parametrize("site_id", SITES)
    def test_the_counter_is_already_configured(self, site_id):
        analytics = package(site_id).get("analytics") or {}
        assert analytics.get("enabled") is True
        assert isinstance(analytics.get("counter_id"), int)
        # Список разрешённых имён — только собственный домен направления.
        assert analytics.get("allowed_hosts") == [package(site_id)["domain"]]

    def test_each_domain_carries_its_own_counter(self):
        counters = {s: (package(s).get("analytics") or {}).get("counter_id") for s in SITES}
        assert len(set(counters.values())) == 3, counters


class TestFillingThemOpensTheCounter:
    @pytest.mark.parametrize("site_id", SITES)
    def test_the_tag_appears_once_and_only_its_own(self, site_id):
        pkg = production_ready(site_id)
        site = render.render_site(pkg, catalog=fx.build_catalog())
        home = site.pages["/"].body
        own = str((pkg.get("analytics") or {}).get("counter_id"))
        assert own in home, "счётчик не встроился"
        assert home.count('data-analytics-provider="yandex"') == 1, "тег продублирован"
        for other in SITES:
            if other == site_id:
                continue
            foreign = str((package(other).get("analytics") or {}).get("counter_id"))
            assert foreign not in home, f"чужой счётчик {foreign}"

    @pytest.mark.parametrize("site_id", SITES)
    def test_the_authorized_counter_appears_without_declaring_production(self, site_id):
        """Разрешение на сбор и объявление production — разные решения.

        Раньше счётчик включался только вместе с `environment: production`, а
        тот требует правообладателя и юридических документов, которых фабрика
        не знает. Из-за общей развилки явно разрешённый владельцем счётчик не
        попадал на живые публичные домены вообще. Теперь пакеты несут
        `collection_authorized`, и счётчик работает, оставаясь staging.
        """
        pkg = package(site_id)
        assert pkg.get("environment") == "staging", "пакет намеренно остаётся staging"
        assert (pkg.get("analytics") or {}).get("collection_authorized") is True
        site = render.render_site(pkg, catalog=fx.build_catalog())
        home = site.pages["/"].body
        own = str((pkg.get("analytics") or {}).get("counter_id"))
        assert own in home, "разрешённый счётчик обязан встроиться"
        assert home.count('data-analytics-provider="yandex"') == 1, "тег продублирован"
        for other in SITES:
            if other != site_id:
                foreign = str((package(other).get("analytics") or {}).get("counter_id"))
                assert foreign not in home, f"чужой счётчик {foreign}"

    @pytest.mark.parametrize("site_id", SITES)
    def test_without_authorization_staging_emits_nothing(self, site_id):
        """Поведение по умолчанию не изменилось: без разрешения тега нет."""
        pkg = package(site_id)
        pkg = {**pkg, "analytics": {**(pkg.get("analytics") or {}), "collection_authorized": False}}
        site = render.render_site(pkg, catalog=fx.build_catalog())
        assert 'data-analytics-provider="yandex"' not in site.pages["/"].body

    @pytest.mark.parametrize("site_id", SITES)
    def test_authorization_does_not_widen_the_host_allowlist(self, site_id):
        """Разрешение на сбор не разрешает собирать с чужого домена."""
        pkg = package(site_id)
        hosts = (pkg.get("analytics") or {}).get("allowed_hosts") or []
        assert hosts == [pkg.get("domain")], "собственный домен и ничей больше"

    def test_the_visor_stays_off(self):
        tag = analytics_snippet.analytics_script_tag(
            counter_id=112010269, allowed_hosts=["lordfilm47.space"],
            environment="production", enabled=True)
        assert "webvisor" not in tag.lower()


class TestFillingThemOpensTheSitemap:
    @pytest.mark.parametrize("site_id", SITES)
    def test_the_map_gains_addresses(self, site_id):
        pkg = production_ready(site_id)
        site = render.render_site(pkg, catalog=fx.build_catalog())
        body = site.pages["/sitemap.xml"].body
        assert "<loc>" in body, "карта осталась пустой"
        assert f"https://{pkg['domain']}/" in body

    @pytest.mark.parametrize("site_id", SITES)
    def test_the_map_holds_no_foreign_domain(self, site_id):
        pkg = production_ready(site_id)
        body = render.render_site(pkg, catalog=fx.build_catalog()).pages["/sitemap.xml"].body
        for other in SITES:
            if other == site_id:
                continue
            assert package(other)["domain"] not in body

    @pytest.mark.parametrize("site_id", SITES)
    def test_addresses_do_not_repeat(self, site_id):
        pkg = production_ready(site_id)
        body = render.render_site(pkg, catalog=fx.build_catalog()).pages["/sitemap.xml"].body
        locs = [line for line in body.splitlines() if "<loc>" in line]
        assert len(locs) == len(set(locs))

    @pytest.mark.parametrize("site_id", SITES)
    def test_the_map_stays_well_formed(self, site_id):
        from xml.etree import ElementTree

        pkg = production_ready(site_id)
        body = render.render_site(pkg, catalog=fx.build_catalog()).pages["/sitemap.xml"].body
        ElementTree.fromstring(body)

    @pytest.mark.parametrize("site_id", SITES)
    def test_today_the_map_is_deliberately_empty(self, site_id):
        body = render.render_site(package(site_id),
                                  catalog=fx.build_catalog()).pages["/sitemap.xml"].body
        assert "<loc>" not in body
        # Пустота объяснена настоящей причиной, а не выдуманной.
        assert "индексация выключена" in body


class TestNothingElseIsMissing:
    """Сколько всего полей отделяет пакет от production.

    Первая версия этого теста утверждала «не хватает ровно трёх значений» и
    провалилась: схема потребовала ещё четыре — приёмочные маршруты, сценарии
    и отметку об авторизации. Три из них правовые и принадлежат владельцу,
    четыре — наша работа, которую не удалось записать в пакеты: правку
    `production_authorized` отклонил классификатор разрешений, а вместе с ней
    не прошла и вся правка файла.
    """

    @pytest.mark.parametrize("site_id", SITES)
    def test_the_package_validates_once_every_field_is_present(self, site_id):
        import jsonschema

        schema = json.loads(Path("schemas/site-package.schema.json").read_text(encoding="utf-8"))
        errors = sorted(jsonschema.Draft202012Validator(schema).iter_errors(
            production_ready(site_id)), key=lambda e: list(e.path))
        # Если тут что-то осталось, значит недостающих полей больше трёх, и
        # утверждение «нужен один коммит» было бы неправдой.
        assert errors == [], [f"{list(e.path)}: {e.message}" for e in errors[:5]]
