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


# --- Topvisor: состояние измеряется, а не утверждается в коде ----------------

def _состояние_topvisor(tmp_path, *, строки, сводка=None, тревога=None, здоровье=None):
    к = tmp_path / "topvisor-inventory"
    к.mkdir()
    (к / "mapping-matrix.json").write_text(json.dumps(
        {"generated_at": "2026-10-26T04:26:03Z",
         "mapping_summary": сводка if сводка is not None else {"MAPPED_EXACT_COUNT": 1},
         "rows": строки}, ensure_ascii=False), encoding="utf-8")
    (к / "health.json").write_text(json.dumps(
        здоровье or {"source": "LIVE_READ_ONLY", "read_only_call_count": 52,
                     "last_success_at": "2026-10-26T04:26:03Z",
                     "SYNC_COST_STATE": "VERIFIED_NON_BILLABLE",
                     "SYNC_RUN_COST_RUB": 0, "timer_deployed": True,
                     "consecutive_successes": 47, "freshness_hours": 36,
                     "stale": False}, ensure_ascii=False), encoding="utf-8")
    if тревога is not None:
        (к / "alert.json").write_text(json.dumps(тревога, ensure_ascii=False),
                                      encoding="utf-8")
    return к


def test_расхождение_сводки_и_строк_объясняется_до_выбора_числа(tmp_path):
    """Две меры одного предмета: сводка говорит 2, строк MATCHED_EXACT одна.

    Так и измерено 26.10: разницу даёт ZERO_QUERIES — проект есть, запросов
    нет. Для готовности это разные состояния, поэтому берётся строка домена,
    а расхождение называется, а не разрешается молча (класс 47).
    """
    строки = [{"canonical_domain": "а.ru", "mapping_state": "MATCHED_EXACT"},
              {"canonical_domain": "б.ru", "mapping_state": "ZERO_QUERIES"}]
    снимок = инс._topvisor_снимок(_состояние_topvisor(
        tmp_path, строки=строки, сводка={"MAPPED_EXACT_COUNT": 2}))
    assert снимок["расхождение"] and "ZERO_QUERIES" in снимок["расхождение"]
    assert "берётся строка домена" in снимок["расхождение"]


def test_совпадение_сводки_и_строк_расхождением_не_объявляется(tmp_path):
    строки = [{"canonical_domain": "а.ru", "mapping_state": "MATCHED_EXACT"}]
    снимок = инс._topvisor_снимок(_состояние_topvisor(
        tmp_path, строки=строки, сводка={"MAPPED_EXACT_COUNT": 1}))
    assert снимок["расхождение"] is None


def test_активная_тревога_инвентаря_попадает_в_причину(tmp_path):
    снимок = инс._topvisor_снимок(_состояние_topvisor(
        tmp_path, строки=[{"canonical_domain": "а.ru", "mapping_state": "MATCHED_EXACT"}],
        тревога={"active": True, "reasons": ["INVENTORY_DRIFT"]}))
    assert снимок["тревога"]["reasons"] == ["INVENTORY_DRIFT"]


def test_погашенная_тревога_не_считается_активной(tmp_path):
    снимок = инс._topvisor_снимок(_состояние_topvisor(
        tmp_path, строки=[{"canonical_domain": "а.ru", "mapping_state": "MATCHED_EXACT"}],
        тревога={"active": False, "reasons": ["INVENTORY_DRIFT"]}))
    assert снимок["тревога"] is None


def test_отсутствующий_каталог_состояния_называет_причину(tmp_path):
    снимок = инс._topvisor_снимок(tmp_path / "нет-такого")
    assert снимок["здоровье"] is None
    assert "нет" in снимок["почему_нет"]


# --- Окно поставщика для съёма позиций в Яндексе -----------------------------

def test_расписание_внутри_окна_поставщика():
    """Прочитано 26.10 в справке Topvisor: запуск только 20:00–05:59 МСК.

    Наш подготовленный съём стоит на 18:10 UTC = 21:10 МСК — внутри окна.
    Проверка нужна затем, что таймер на дневной час не отказывает громко: он
    просто не соберёт позиций, а готовность будет выглядеть настроенной.
    """
    исход, почему = инс.окно_съёма_позиций("[Timer]\nOnCalendar=*-*-* 18:10:00 UTC\n")
    assert исход == "ДА" and "внутри окна" in почему


def test_дневное_расписание_съёма_это_нет():
    исход, почему = инс.окно_съёма_позиций("[Timer]\nOnCalendar=*-*-* 09:00:00 UTC\n")
    assert исход == "НЕТ" and "ВНЕ окна" in почему


def test_часть_запусков_вне_окна_называется_частично():
    """Два запуска в сутки: один в окне, другой нет — это не «да» и не «нет»."""
    исход, _ = инс.окно_съёма_позиций(
        "[Timer]\nOnCalendar=*-*-* 18:10:00 UTC\nOnCalendar=*-*-* 09:00:00 UTC\n")
    assert исход == "ЧАСТИЧНО"


def test_без_oncalendar_окно_не_измеряется():
    исход, почему = инс.окно_съёма_позиций("[Timer]\nOnUnitActiveSec=15min\n")
    assert исход == инс.НЕТ_ДАННЫХ and "нечем" in почему


def test_окно_не_применяется_к_чтению_готовых_данных():
    """topvisor-measure читает собранное; применить к нему окно — ложный запрет.

    Проверяется НЕ поведение функции, а то, что оговорка записана в коде:
    иначе следующий читатель применит окно ко всем юнитам Topvisor подряд.
    """
    источник = (КОРЕНЬ / "automation" / "local" / "measurement-readiness.py").read_text(
        encoding="utf-8")
    assert "ПРИМЕНЯЕТСЯ ТОЛЬКО К СЪЁМУ ПОЗИЦИЙ" in источник
    assert "читает уже" in источник and "дефектом не является" in источник


def test_область_окна_названа_в_коде():
    """Окно — про режим Search API, и расписание не доказывает съём.

    Замечание владельца 26.10: прежняя оговорка говорила «только к съёму
    позиций», но не называла РЕЖИМ и создавала впечатление, что верное
    расписание означает получение позиций. Проверяется, что обе границы
    записаны там, где их прочтёт следующий читатель кода.
    """
    источник = (КОРЕНЬ / "automation" / "local" / "measurement-readiness.py").read_text(
        encoding="utf-8")
    assert "ЧЕРЕЗ ЯНДЕКС SEARCH API" in источник
    assert "Яндекс SERP" in источник
    assert "НЕ доказывает получение позиций" in источник
