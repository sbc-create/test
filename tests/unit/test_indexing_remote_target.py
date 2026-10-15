"""Вердикт режима индексации не выдаёт чужую машину за факт о витрине.

Класс дефекта. Читатель режима, корень выпуска и слой nginx ищутся по
локальным путям. Для витрины с `deploy_target.ref` другого узла их отсутствие
— факт об ЭТОЙ машине. Измерено 2026-10-15 на партии K2: вердикт отвечал
`MECHANISM_UNSUPPORTED`, `release_gap: reader_missing` и «открытие невозможно
до НОВОГО выпуска» о восьми витринах, у которых `src/indexing_mode.py` в
выложенном релизе есть (8237 байт на k2-zomro-01).
"""
import json

import pytest

from factory.qwen import indexing, registry


class Витрина:
    def __init__(self, цель=""):
        self.site_id = "lords-10"
        self.domain = "lordfilm.group"
        self.account = "lordfilm-group"
        self.adapter = "lords-serve"
        self.deploy_target = цель
        self.published_release = ""


def test_чужой_узел_назван():
    assert indexing.чужой_узел(Витрина("k2-zomro-01")) == "k2-zomro-01"


def test_свой_узел_не_считается_чужим():
    assert indexing.чужой_узел(Витрина(registry.ЭТОТ_УЗЕЛ)) == ""
    assert indexing.чужой_узел(Витрина("")) == ""


def test_совет_называет_узел_и_путь():
    совет = indexing._проверить_на_узле(Витрина("k2-zomro-01"),
                                        "src/indexing_mode.py")
    assert "k2-zomro-01" in совет
    assert "/srv/lordfilm-group/current/src/indexing_mode.py" in совет


def test_реестр_отличает_неизмеримый_выпуск():
    """Пустой выпуск у витрины другого узла — «не измерено», а не «нет»."""
    сайты = {s.site_id: s for s in registry.собрать(опрашивать_сеть=False)}
    s = сайты.get("lords-10")
    if s is None:
        pytest.skip("витрины lords-10 нет в реестре этого окружения")
    assert s.deploy_target == "k2-zomro-01"
    assert s.release_measurable_here is False
    assert any("k2-zomro-01" in з for з in s.notes), s.notes


def test_вердикт_не_называет_пробел_выпуска(monkeypatch):
    """Статус — MECHANISM_UNPROVEN с доказательством, а не пробел выпуска."""
    monkeypatch.setattr(indexing, "_замерить",
                        lambda s, итог, док: (None, "CLOSED", [], {}))
    monkeypatch.setattr(indexing, "читатель_режима", lambda *а, **к: None)
    итог = indexing.готовность("lords-10", доказать=False)
    if итог["status"] in ("ENV_UNAVAILABLE", "DOMAIN_UNKNOWN"):
        pytest.skip(f"реестр этого окружения: {итог['status']}")
    assert итог["status"] == "MECHANISM_UNPROVEN", json.dumps(
        итог, ensure_ascii=False)[:600]
    assert "release_gap" not in итог
    assert итог["deploy_target"] == "k2-zomro-01"
    assert "k2-zomro-01" in итог["proof"]


def test_предпроверка_блокирует_по_верной_причине(monkeypatch):
    """BLOCKED остаётся, но причина — чужой узел, а не отсутствие читателя."""
    monkeypatch.setattr(indexing, "читатель_режима", lambda *а, **к: None)
    try:
        итог = indexing.проверить("lords-10", mode="closed")
    except indexing.Отказано as ош:
        pytest.skip(f"предпроверка недоступна в этом окружении: {ош}")
    блокеры = " ".join(итог["blockers"])
    assert итог["ok"] is False
    assert "k2-zomro-01" in блокеры, блокеры
    assert "до выпуска читателя" not in блокеры, блокеры
