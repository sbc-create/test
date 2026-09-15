"""Проверка правил тревоги ежедневного отчёта.

Правило, которое ни разу не срабатывало, неотличимо от правила, которое не
работает. Поэтому каждое проверяется на снимке, где поломка присутствует, и
на снимке, где её нет.
"""
from __future__ import annotations

import importlib.util
import pathlib

import pytest

ОТЧЁТ = pathlib.Path(__file__).resolve().parents[2] / "automation/host/seo-daily-report.py"
spec = importlib.util.spec_from_file_location("_seo_daily", ОТЧЁТ)
М = importlib.util.module_from_spec(spec)
spec.loader.exec_module(М)

ЗДОРОВЫЙ = {
    "domain": "lordfilm47.space", "site_id": "lords-01", "http": 200,
    "metrika_counter_id": 112010269, "metrika_tag_present": True,
    "metrika_tag_occurrences": 1, "metrika_init_calls": 1,
    "metrika_foreign_counters": [], "topvisor_project_id": 32531504,
    "x_robots_tag": "noindex, nofollow", "meta_robots": "noindex, nofollow",
    "robots_txt_http": 200, "robots_txt_disallow_all": True,
    "sitemap_http": 200, "sitemap_url_count": 120,
    "canonical_present": True, "canonical_absolute": True,
    "json_ld_blocks": 1, "soft_404": False,
    "renderer_build_id": "b1", "renderer_template_revision": "r1",
}

ПОЛОМКИ = {
    "METRIKA_TAG_MISSING": {"metrika_tag_present": False},
    "METRIKA_WRONG_COUNTER": {"metrika_foreign_counters": [112010274]},
    "METRIKA_DUPLICATE_INIT": {"metrika_init_calls": 2},
    "HTTP_NOT_OK": {"http": 502},
    "INDEXING_UNEXPECTEDLY_OPEN": {"x_robots_tag": "all", "meta_robots": "index, follow"},
    "ROBOTS_TXT_LOST": {"robots_txt_http": 404},
    "SITEMAP_EMPTY": {"sitemap_url_count": 0},
    "CANONICAL_MISSING": {"canonical_present": False},
    "SOFT_404": {"soft_404": True},
}


def test_на_здоровом_снимке_тревог_нет():
    assert М.тревоги(ЗДОРОВЫЙ, None) == []


@pytest.mark.parametrize("правило", sorted(ПОЛОМКИ))
def test_правило_срабатывает(правило):
    снимок = dict(ЗДОРОВЫЙ) | ПОЛОМКИ[правило]
    коды = [t["rule"] for t in М.тревоги(снимок, None)]
    assert правило in коды, f"{правило} не сработало: {коды}"


def test_смена_рендерера_замечается():
    вчера = dict(ЗДОРОВЫЙ)
    сегодня = dict(ЗДОРОВЫЙ) | {"renderer_build_id": "b2"}
    коды = [t["rule"] for t in М.тревоги(сегодня, вчера)]
    assert "RENDERER_CHANGED" in коды


def test_смена_рендерера_с_пропажей_тега_названа_отдельно():
    """Смена сборки сама по себе не беда. Смена вместе с пропажей тега — беда."""
    вчера = dict(ЗДОРОВЫЙ)
    сегодня = dict(ЗДОРОВЫЙ) | {"renderer_build_id": "b2", "metrika_tag_present": False}
    т = М.тревоги(сегодня, вчера)
    коды = [x["rule"] for x in т]
    assert "RENDERER_CHANGED" in коды and "METRIKA_TAG_MISSING" in коды
    смена = next(x for x in т if x["rule"] == "RENDERER_CHANGED")
    assert "ТЕГ ПРОПАЛ" in смена["detail"]


def test_исчезновение_проекта_topvisor_замечается():
    вчера = dict(ЗДОРОВЫЙ)
    сегодня = dict(ЗДОРОВЫЙ) | {"topvisor_project_id": None}
    assert "TOPVISOR_PROJECT_CHANGED" in [t["rule"] for t in М.тревоги(сегодня, вчера)]


def test_отчёт_не_запускает_платное():
    источник = ОТЧЁТ.read_text(encoding="utf-8")
    for платное in ("positions_2/checker/go", "audit_2/audit"):
        assert платное not in источник, f"отчёт умеет запускать платное: {платное}"
