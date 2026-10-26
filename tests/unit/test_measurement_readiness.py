"""Готовность измерений: три состояния на три системы, и ни одной подмены.

Проверка появилась вместе с инструментом, потому что именно здесь подмены
дешевле всего: «проект создан» выдать за «данные есть», отсутствие домена в
сборе показать нулём, недоступный каталог артефактов — отсутствием данных, а
подтверждённые Яндексом права — работающим сбором. Каждая из этих подмен уже
случалась в сети хотя бы раз.
"""
from __future__ import annotations

import importlib.util
import json
import pathlib

import pytest

КОРЕНЬ = pathlib.Path(__file__).resolve().parents[2]
_сп = importlib.util.spec_from_file_location(
    "measurement_readiness", КОРЕНЬ / "automation" / "local" / "measurement-readiness.py")
инс = importlib.util.module_from_spec(_сп)
_сп.loader.exec_module(инс)


def _сбор(домен: str, измерения: list[dict]) -> dict:
    return {"collected_at": "2026-10-26T05:00:00Z",
            "domains": [{"domain": домен, "measurements": измерения}]}


def test_разбирает_рабочую_форму_артефакта():
    """Форма прочитана у рабочего артефакта: measurements — СПИСОК записей."""
    сбор = _сбор("x.test", [
        {"key": "visitors", "measured": True, "value": 21.0},
        {"key": "pages_in_search", "measured": False, "reason": "нет доступа"},
    ])
    состояние, причина = инс.измерено_по_домену(сбор, "x.test")
    assert состояние == "ДАННЫЕ ЕСТЬ"
    assert "visitors=21.0" in причина and "измерено 1 из 2" in причина


def test_измерено_много_но_без_опорного_показателя_не_данные():
    """«18 из 23» ничего не значит, если среди них нет посетителей и визитов."""
    сбор = _сбор("x.test", [
        {"key": "pages_in_search", "measured": True, "value": 5},
        {"key": "visitors", "measured": False, "reason": "счётчик не отдал"},
    ])
    состояние, причина = инс.измерено_по_домену(сбор, "x.test")
    assert состояние == инс.НЕТ_ДАННЫХ
    assert "ни одного опорного" in причина and "счётчик не отдал" in причина


def test_домена_нет_в_сборе_это_пробел_а_не_ноль():
    сбор = _сбор("другой.test", [{"key": "visitors", "measured": True, "value": 1}])
    состояние, причина = инс.измерено_по_домену(сбор, "x.test")
    assert состояние == инс.НЕТ_ДАННЫХ
    assert "домена нет в сборе" in причина and "не ноль" in причина


def test_недоступный_каталог_артефактов_называет_причину(tmp_path):
    сбор, пояснение = инс.последний_сбор(tmp_path / "нет-такого")
    assert сбор is None
    assert "недоступен" in пояснение


def test_пустой_каталог_отличается_от_недоступного(tmp_path):
    сбор, пояснение = инс.последний_сбор(tmp_path)
    assert сбор is None and "нет артефактов" in пояснение


def test_права_яндекса_и_наш_сбор_различаются(monkeypatch, tmp_path):
    """VERIFIED — ответ Яндекса; enabled — наше решение. Путать нельзя."""
    запись = {"domain": "x.test", "counter_id": 1, "counter_state": "created",
              "webvisor": False,
              "webmaster": {"enabled": False, "host_id": "https:x.test:443",
                            "verification_status": "VERIFIED"}}
    monkeypatch.setattr(инс, "запись_аналитики", lambda d: запись)
    monkeypatch.setattr(инс, "расписание", lambda ю: ("РАСПИСАНИЕ", ю))
    итог = инс.по_домену({"domain": "x.test", "site_id": "x-01", "status": "live"},
                         _сбор("x.test", [{"key": "visits", "measured": True, "value": 3}]),
                         "проба")
    вм = итог["системы"]["вебмастер"]
    assert вм["настроено"] == "НАСТРОЕНО"
    assert "ВЫКЛЮЧЕН" in вм["почему"], "выключенный сбор обязан быть назван"
    assert вм["данные"] == инс.НЕТ_ДАННЫХ


def test_отсутствующий_таймер_называется_а_не_молчит():
    состояние, причина = инс.расписание("такого-таймера-нет.timer")
    assert состояние == инс.НЕТ_ДАННЫХ and "нет" in причина


def test_состав_домéнов_берётся_из_паспортов_и_без_выведенных():
    имена = [я["domain"] for я in инс.домены()]
    assert "lordserial33.biz" in имена
    for выведен in ("animedia.space", "lordfilm47.space",
                    "lordserials22.site", "lordserials22.space"):
        assert выведен not in имена, f"{выведен} выведен владельцем и не проверяется"
    assert not [д for д in имена if д.endswith((".test", ".invalid", ".localhost"))]


def test_готовность_требует_всех_трёх_систем(monkeypatch):
    monkeypatch.setattr(инс, "запись_аналитики", lambda d: None)
    monkeypatch.setattr(инс, "расписание", lambda ю: ("РАСПИСАНИЕ", ю))
    итог = инс.по_домену({"domain": "x.test", "site_id": "x-01", "status": "live"},
                         _сбор("x.test", [{"key": "visitors", "measured": True, "value": 9}]),
                         "проба")
    assert итог["готовность"] == "НЕ ГОТОВО"
