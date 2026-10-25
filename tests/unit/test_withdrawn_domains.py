"""Исключённые сайты не получают работы SEO и редакции.

Решение владельца 25.10.2026: animedia.space, lordfilm47.space,
lordserials22.site, lordserials22.space исключены из активного продвижения,
написания текстов и регулярных проверок до замены доменов; история и
материалы сохраняются; lordserials22.info работает дальше; lords3rial.site
(переезд lordfilm47.space, линия Архитектора) включается после
подтверждённого запуска. Каждый потребитель, раздающий работу, обязан
спрашивать factory.cell.withdrawn — иначе домен вернётся через свой
статический перечень или через автоматическое обнаружение.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from factory.cell import withdrawn

ИСКЛЮЧЁННЫЕ = {"animedia.space", "lordfilm47.space", "lordserials22.site", "lordserials22.space",
               "lordserial101.site", "lordfilm077.site"}


def _реестр(путь: Path, ячейки: list[dict]) -> Path:
    путь.write_text(json.dumps({"schema_version": "1.0", "cells": ячейки}), encoding="utf-8")
    return путь


@pytest.fixture()
def реестр(tmp_path, monkeypatch):
    """Реестр, где все ячейки live: исключение не зависит от статуса ячейки."""
    п = _реестр(tmp_path / "site-cells.json", [
        {"site_id": "animedia-02", "domain": "animedia.space", "status": "live"},
        {"site_id": "lords-01", "domain": "lordfilm47.space", "status": "live"},
        {"site_id": "animedia-01", "domain": "animedia.icu", "status": "live"},
        {"site_id": "lords-05", "domain": "lordserials22.info", "status": "live"},
    ])
    monkeypatch.setenv("SITE_CELLS_REGISTRY", str(п))
    return п


def test_перечень_решения_владельца():
    assert set(withdrawn.ИСКЛЮЧЕНЫ) == ИСКЛЮЧЁННЫЕ
    assert not withdrawn.выведен("lordserials22.info")
    assert withdrawn.выведен("WWW.LordFilm47.space")


def test_исключение_по_домену_а_не_по_site_id(tmp_path, monkeypatch):
    # Ячейка lords-01 переезжает на lords3rial.site: новый домен не исключён.
    п = _реестр(tmp_path / "c.json", [{"site_id": "lords-01", "domain": "lords3rial.site",
                                        "status": "live"}])
    monkeypatch.setenv("SITE_CELLS_REGISTRY", str(п))
    assert not withdrawn.выведен("lords3rial.site")
    assert not withdrawn.выведен("lords-01")
    assert withdrawn.выведен("lordfilm47.space")


def test_статус_retired_тоже_исключает(tmp_path, monkeypatch):
    п = _реестр(tmp_path / "c.json", [{"site_id": "x-01", "domain": "example-site.org",
                                        "aliases": ["www.example-site.org"], "status": "retired"}])
    monkeypatch.setenv("SITE_CELLS_REGISTRY", str(п))
    assert withdrawn.выведен("example-site.org") and withdrawn.выведен("x-01")


def test_нечитаемый_реестр_оставляет_перечень(tmp_path, monkeypatch):
    monkeypatch.setenv("SITE_CELLS_REGISTRY", str(tmp_path / "нет.json"))
    assert ИСКЛЮЧЁННЫЕ <= withdrawn.выведенные()


def test_обнаружение_доменов_пропускает_исключённые(реестр, tmp_path):
    from seo_operator import regular

    аналитика = tmp_path / "analytics.json"
    аналитика.write_text(json.dumps({"properties": [
        {"domain": "animedia.space", "counter_id": 113288760},
        {"domain": "lordserials22.site", "counter_id": 113109084},
        {"domain": "animedia.icu", "counter_id": 1},
    ]}), encoding="utf-8")
    sources = dict(regular.SOURCES, cells=реестр, analytics_registry=аналитика,
                   indexing_states=tmp_path)
    домены = {d["domain"] for d in regular.discover_domains(sources)}
    assert not домены & ИСКЛЮЧЁННЫЕ
    assert {"animedia.icu", "lordserials22.info"} <= домены


def test_техочередь_не_выдаёт_задачи_исключённых(реестр):
    from seo_operator import tech_run

    assert set(tech_run.ИСКЛЮЧЕНЫ_ВЛАДЕЛЬЦЕМ) == set(withdrawn.ИСКЛЮЧЕНЫ)
    assert tech_run.вне_продвижения({"site": "animedia.space"}) == "animedia.space"
    assert tech_run.вне_продвижения({"site": "lordfilm47.space, lordserial33.biz"}) == "lordfilm47.space"
    assert tech_run.вне_продвижения({"site": "lordserials22.info"}) is None


def test_topvisor_не_создаёт_и_не_наполняет_проекты_исключённых(реестр):
    from factory.topvisor import cli, manifest, plan

    действующий = cli._действующий_манифест()
    assert not {s.domain for s in действующий} & ИСКЛЮЧЁННЫЕ
    assert any(s.domain == "lordserials22.info" for s in действующий)
    # План на пустом аккаунте не предлагает создать проекты исключённых.
    действия = plan.build([], manifest=действующий).actions
    assert not {a.domain for a in действия} & ИСКЛЮЧЁННЫЕ
    # Записи манифеста сохранены для переноса.
    assert any(s.domain == "lordfilm47.space" for s in manifest.MANIFEST)


def test_редактор_не_получает_исключённые_домены(реестр):
    from seo_operator import editor_run

    разрешено = set(editor_run.allowed_domains())
    assert not разрешено & ИСКЛЮЧЁННЫЕ
    assert "animedia.icu" in разрешено
    assert ИСКЛЮЧЁННЫЕ <= editor_run.закрытые()
    # Пауза опытов сохраняется.
    assert "lordserials22.info" in editor_run.закрытые()


def test_кандидаты_не_строятся_для_исключённых(реестр, tmp_path, monkeypatch):
    from seo_operator import regular

    снимок = tmp_path / "snap.json"
    снимок.write_text(json.dumps({"domains": [{"domain": "animedia.space"},
                                              {"domain": "animedia.icu"}]}), encoding="utf-8")
    # Трафик: по одной странице тайтла на каждом домене; подробности — пробел
    # в описании (GAP) с идентификатором источника.
    monkeypatch.setattr(regular, "_metric", lambda entry, key: (True, {"/title/t-%s/" % entry["domain"]: 5.0}, None))
    monkeypatch.setattr(regular, "_rows", lambda value: value)
    monkeypatch.setattr(regular, "_details_for_editor", lambda path, slugs: {
        sl: {"description": "", "name": sl, "ratings_by_source": {"shikimori": {"external_id": "1"}}}
        for sl in slugs})
    кандидаты = regular.editor_candidates(снимок, tmp_path, set())
    домены = {json.dumps(к, ensure_ascii=False) for к in кандидаты}
    assert any("animedia.icu" in д for д in домены)
    assert not any("animedia.space" in д for д in домены)


def test_мост_очереди_не_выдаёт_и_не_заводит(реестр):
    from factory.qwen import queue_bridge

    assert "исключена" in queue_bridge._выведен("animedia.space")
    assert queue_bridge._выведен("animedia.icu") == ""
    with pytest.raises(queue_bridge.ОчередьОтклонила):
        queue_bridge.завести(site="lordfilm47.space", canonical_url="https://lordfilm47.space/title/x/",
                             headline="x")


def test_запись_текстов_отказывает_а_чтение_нет(реестр, monkeypatch):
    from factory.qwen import editorial

    with pytest.raises(editorial.ОперацияОтклонена, match="исключён"):
        editorial._сайт("animedia.space", опрашивать_сеть=True)
    # Чтение не отказывает по исключению: дальше идёт обычный разбор реестра.
    monkeypatch.setattr(editorial, "_реестр", lambda **_: [])
    with pytest.raises(editorial.ОперацияОтклонена) as отказ:
        editorial._сайт("animedia.space")
    assert "исключён" not in str(отказ.value)


def _паспорт_с_выводом(tmp_path, monkeypatch, *, scopes):
    """Ячейка в форме паспорта Архитектора (2b32d06): блок withdrawal с заменой домена."""
    п = _реестр(tmp_path / "c.json", [
        {"site_id": "lords-01", "domain": "old-site.example", "aliases": ["www.old-site.example"],
         "status": "live",
         "withdrawal": {"withdrawn": True, "at": "2026-10-25", "scopes": scopes,
                        "replacement_domain": "new-site.example",
                        "authority": "владелец, распоряжение 2026-10-25"}},
        {"site_id": "z-01", "domain": "keep.example", "status": "live"},
    ])
    monkeypatch.setenv("SITE_CELLS_REGISTRY", str(п))
    return п


def test_блок_withdrawal_паспорта_исключает_домен_но_не_site_id(tmp_path, monkeypatch):
    _паспорт_с_выводом(tmp_path, monkeypatch, scopes=["text_generation", "alerts"])
    assert withdrawn.выведен("old-site.example") and withdrawn.выведен("www.old-site.example")
    assert not withdrawn.выведен("lords-01")          # ячейка переезжает, а не уходит
    assert not withdrawn.выведен("new-site.example")  # замена после запуска — в работу
    assert not withdrawn.выведен("keep.example")


def test_область_вне_scopes_не_выведена(tmp_path, monkeypatch):
    п = _паспорт_с_выводом(tmp_path, monkeypatch, scopes=["text_generation"])
    assert "old-site.example" in withdrawn.выведенные(п, область="text_generation")
    assert "old-site.example" not in withdrawn.выведенные(п, область="position_checks")


def test_техочередь_видит_блок_withdrawal(tmp_path, monkeypatch):
    from seo_operator import tech_run

    _паспорт_с_выводом(tmp_path, monkeypatch, scopes=["new_tasks"])
    assert tech_run.вне_продвижения({"site": "old-site.example"}) == "old-site.example"
    assert tech_run.вне_продвижения({"site": "keep.example"}) is None


def test_план_топвизора_не_создаёт_проекты_замороженным(реестр):
    """Моделирование 25.10: без исключения план создал бы проекты lordserial101.site
    и lordfilm077.site — замороженным доменам, которых владелец запретил возвращать."""
    from factory.topvisor import cli, plan

    действия = plan.build([], manifest=cli._действующий_манифест()).actions
    assert not {a.domain for a in действия} & {"lordserial101.site", "lordfilm077.site"}
    assert "animedia.icu" in {a.domain for a in действия}
