"""Вывод домена из активной работы: решение владельца, которое ИСПОЛНЯЕТСЯ.

Распоряжение владельца 2026-10-25: вывести из активной работы animedia.space,
lordfilm47.space, lordserials22.site и lordserials22.space (lordserials22.info
в список НЕ входит), прекратить расходы на них и сделать так, чтобы
«автоматическое обнаружение не возвращало эти домены в работу».

Почему отдельно от `promotion`. Исключение из продвижения намеренно НЕ снимает
обходы и проверки доступности — так и записано в
`seo_operator/regular.py::discover_domains`: «убрать домен здесь значило бы
заодно снять с него поддержку». Вывод из работы — обратное решение: расходы
прекращаются целиком. Одно поле на два решения означало бы либо потерю
поддержки у исключённых, либо продолжение расходов на выведенных.

Главная проверка здесь — не предикат, а ИСПОЛНЕНИЕ: запись без читающего
обработчика обещает остановку, которой никто не делает. Цена такой записи
измерена в этот же день: блок вывода записался операцией и ПРОПАЛ при
сохранении (его не было в сериализаторе), причём печать операции отвечала
«выведен True». Отчёт утверждал бы остановку, а следующий общий прогон вернул
бы четыре домена в работу.
"""
from __future__ import annotations

import json
import pathlib
import sys

import pytest

КОРЕНЬ = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(КОРЕНЬ))

from factory.cell import registry  # noqa: E402

ОБРАЗЕЦ = {
    "site_id": "proba-01", "domain": "proba.example", "aliases": ["www.proba.example"],
    "status": "live", "repo": {"path": "var/site-repos/proba"},
    "template": {"template_id": "lords-anime"},
    "deploy_target": {"ref": "claude-control-01", "server": None},
}


@pytest.fixture()
def реестр(tmp_path):
    п = tmp_path / "site-cells.json"
    п.write_text(json.dumps({"schema_version": 1, "cells": [dict(ОБРАЗЕЦ)]},
                            ensure_ascii=False), encoding="utf-8")
    return п


# --- предикаты ---------------------------------------------------------------

def test_без_блока_домен_в_работе(реестр) -> None:
    """Появление поля не меняет поведения действующих сайтов."""
    ячейка = registry.resolve("proba.example", реестр)
    assert registry.выведен_из_работы(ячейка) is False
    assert registry.выведенные_домены(реестр) == frozenset()


def test_область_вне_scopes_не_считается_выведенной(реестр) -> None:
    """Вывод, записанный наполовину, не должен читаться как полный."""
    registry.объявить_вывод("proba.example", withdrawn=True, reason="решение владельца",
                            authority="владелец", scopes=("analytics_collection",),
                            path=реестр)
    ячейка = registry.resolve("proba.example", реестр)
    assert registry.выведен_из_работы(ячейка, "analytics_collection") is True
    assert registry.выведен_из_работы(ячейка, "availability_crawl") is False
    assert registry.выведен_из_работы(ячейка) is True


def test_псевдонимы_попадают_в_перечень(реестр) -> None:
    registry.объявить_вывод("proba.example", withdrawn=True, reason="решение владельца",
                            authority="владелец", path=реестр)
    assert registry.выведенные_домены(реестр) == {"proba.example", "www.proba.example"}


# --- операция ----------------------------------------------------------------

def test_вывод_без_причины_и_основания_отклоняется(реестр) -> None:
    with pytest.raises(registry.RegistryError, match="BLOCKED_INPUT"):
        registry.объявить_вывод("proba.example", withdrawn=True, reason="",
                                authority="владелец", path=реестр)
    with pytest.raises(registry.RegistryError, match="BLOCKED_INPUT"):
        registry.объявить_вывод("proba.example", withdrawn=True, reason="есть",
                                authority="", path=реестр)


def test_придуманная_область_отклоняется(реестр) -> None:
    """Имя без обработчика обещало бы остановку, которой никто не исполняет."""
    with pytest.raises(registry.RegistryError, match="неизвестные области"):
        registry.объявить_вывод("proba.example", withdrawn=True, reason="решение",
                                authority="владелец", scopes=("всё_сразу",), path=реестр)


def test_дата_вывода_записывается(реестр) -> None:
    registry.объявить_вывод("proba.example", withdrawn=True, reason="решение владельца",
                            authority="владелец", at="2026-10-25", path=реестр)
    ячейка = registry.resolve("proba.example", реестр)
    assert ячейка.withdrawal["at"] == "2026-10-25"


def test_блок_вывода_ВЫЖИВАЕТ_сохранение(реестр) -> None:
    """Та самая ошибка 25.10: операция отвечала «выведен», а в файле ничего.

    Сериализатор перечисляет поля вручную, и нового он не знал. Проверка
    читает ФАЙЛ, а не объект: иначе она прошла бы и на сломанном коде.
    """
    registry.объявить_вывод("proba.example", withdrawn=True, reason="решение владельца",
                            authority="владелец", at="2026-10-25",
                            replacement_domain="zamena.example", path=реестр)
    сырое = json.loads(реестр.read_text(encoding="utf-8"))
    блок = сырое["cells"][0].get("withdrawal") or {}
    assert блок.get("withdrawn") is True, "блок вывода не сохранён в файле"
    assert блок.get("replacement_domain") == "zamena.example"


def test_замена_не_придумывается(реестр) -> None:
    registry.объявить_вывод("proba.example", withdrawn=True, reason="решение владельца",
                            authority="владелец", path=реестр)
    assert registry.замена_домена(реестр) == {}
    registry.объявить_вывод("proba.example", withdrawn=True, reason="решение владельца",
                            authority="владелец", replacement_domain="zamena.example",
                            path=реестр)
    assert registry.замена_домена(реестр) == {"proba.example": "zamena.example",
                                              "www.proba.example": "zamena.example"}


def test_возврат_в_работу_сохраняет_историю(реестр) -> None:
    """«Был выведен и возвращён» — факт, нужный для сопоставимости измерений."""
    registry.объявить_вывод("proba.example", withdrawn=True, reason="первое решение",
                            authority="владелец", at="2026-10-25", path=реестр)
    registry.объявить_вывод("proba.example", withdrawn=False, reason="возврат в работу",
                            authority="владелец", at="2026-11-01", path=реестр)
    блок = registry.resolve("proba.example", реестр).withdrawal
    assert блок["withdrawn"] is False
    assert any("первое решение" in str(з.get("reason")) for з in блок["history"])


# --- ИСПОЛНЕНИЕ обработчиками ------------------------------------------------

def test_обход_не_берёт_выведенный_домен(tmp_path, monkeypatch) -> None:
    from seo_operator import regular

    cells = tmp_path / "cells.json"
    cells.write_text(json.dumps({"cells": [
        {"site_id": "a-01", "domain": "ostayotsya.example"},
        {"site_id": "b-01", "domain": "vyveden.example", "aliases": ["www.vyveden.example"],
         "withdrawal": {"withdrawn": True, "at": "2026-10-25", "reason": "решение",
                        "authority": "владелец", "scopes": list(registry.ОБЛАСТИ_ВЫВОДА)}},
    ]}, ensure_ascii=False), encoding="utf-8")
    реестр_аналитики = tmp_path / "analytics.json"
    реестр_аналитики.write_text(json.dumps({"properties": [
        {"domain": "vyveden.example", "counter_id": 1},
        {"domain": "ostayotsya.example", "counter_id": 2}]}), encoding="utf-8")
    источники = {"cells": cells, "analytics_registry": реестр_аналитики,
                 "indexing_states": tmp_path / "states"}
    домены = [з["domain"] for з in regular.discover_domains(источники)]
    assert домены == ["ostayotsya.example"], "выведенный домен вернулся в обход"
    assert regular.withdrawn_domains(источники) == ["vyveden.example"]


def test_шлюз_редактора_не_выдаёт_заданий_выведенному(monkeypatch) -> None:
    from factory.cell import registry as cell_registry
    from seo_operator import editor_run, regular

    monkeypatch.setattr(cell_registry, "исключённые_домены", lambda *а, **к: frozenset())
    monkeypatch.setattr(cell_registry, "выведенные_домены",
                        lambda *а, **к: frozenset({"animedia.space"}))
    monkeypatch.setattr(editor_run, "EDITOR_DOMAINS", {"animedia.space", "animedia.icu"})
    monkeypatch.setattr(regular, "EDITOR_SITES", {"animedia.space": "animedia-02",
                                                  "animedia.icu": "animedia-01"})
    assert editor_run.allowed_domains() == ["animedia.icu"]


def test_сбор_аналитики_пропускает_и_называет_пропуск(monkeypatch) -> None:
    from seo_operator import analytics_collect as сбор

    monkeypatch.setattr(сбор, "_выведенные_домены", lambda: frozenset({"vyveden.example"}))
    monkeypatch.setattr(сбор.registry, "load", lambda: {"properties": [
        {"domain": "vyveden.example", "counter_id": 1},
        {"domain": "ostayotsya.example", "counter_id": 2}]})
    monkeypatch.setattr(сбор, "collect_domain",
                        lambda provider, entry, **к: сбор.DomainCollection(
                            domain=entry["domain"], counter_id=entry.get("counter_id"),
                            host_id=None))
    отчёт = сбор.collect(provider=object(), date1="2026-10-18", date2="2026-10-25")
    собраны = [з["domain"] for з in отчёт["domains"]]
    assert собраны == ["ostayotsya.example"]
    assert отчёт["withdrawn"]["domains"] == ["vyveden.example"]
    assert "выведены владельцем" in отчёт["withdrawn"]["note"]


def test_qwen_оставляет_выведенному_только_чтение() -> None:
    from factory.qwen import registry as qreg

    s = qreg.Сайт(site_id="lords-01", domain="lordfilm47.space")
    s.withdrawn = True
    операции = qreg.доступные_операции(s, мех="editorial-queue")
    меняющие = [о for о in операции if о not in qreg.ОПЕРАЦИИ_ЧТЕНИЯ]
    assert not меняющие, f"выведенному домену предложены меняющие операции: {меняющие}"


# --- фактическое состояние реестра сети --------------------------------------

def test_четыре_домена_распоряжения_выведены_и_с_датой() -> None:
    """Проверка не на образце, а на РАБОЧЕМ реестре: решение исполнено."""
    ожидаются = {"animedia.space", "lordfilm47.space",
                 "lordserials22.site", "lordserials22.space"}
    выведены = registry.выведенные_домены()
    assert ожидаются <= выведены, f"не выведены: {sorted(ожидаются - выведены)}"
    assert "lordserials22.info" not in выведены, (
        "lordserials22.info в список вывода не входит")
    for домен in sorted(ожидаются):
        блок = registry.resolve(домен).withdrawal
        assert блок.get("at", "").startswith("2026-10-25"), домен
        assert блок.get("authority"), домен
        assert len(блок.get("scopes") or ()) == len(registry.ОБЛАСТИ_ВЫВОДА), домен


def test_замена_lordfilm47_назначена_и_записана() -> None:
    assert registry.замена_домена().get("lordfilm47.space") == "lords3rial.site"
