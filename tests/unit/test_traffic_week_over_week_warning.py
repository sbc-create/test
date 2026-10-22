"""Числа «неделя к неделе» нельзя взять молча: предупреждение обязательно.

Эту меру читает не только человек: `network-table.py` берёт её вывод из
`var/seo/traffic-wow.json` и строит по нему столбцы сводной таблицы сети.
Раз измерено (MOD-131), что ранняя неделя там занижена и рост завышен на
17–80 %, предупреждение должно лежать и в файле, а не только в печати —
иначе оно не дойдёт до того, кто возьмёт число.
"""
from __future__ import annotations

import importlib.util
import pathlib

КОРЕНЬ = pathlib.Path(__file__).resolve().parents[2]
ПУТЬ = КОРЕНЬ / "automation" / "local" / "traffic-week-over-week.py"

спец = importlib.util.spec_from_file_location("traffic_week_over_week", ПУТЬ)
модуль = importlib.util.module_from_spec(спец)
assert спец.loader is not None
спец.loader.exec_module(модуль)


def test_предупреждение_называет_запись_и_обе_даты():
    т = модуль.предупреждение_о_досчёте("2026-10-19", "2026-10-12")
    assert "MOD-131" in т
    assert "2026-10-19" in т and "2026-10-12" in т


def test_предупреждение_называет_чем_мерить_вместо_этого():
    т = модуль.предупреждение_о_досчёте("2026-10-19", "2026-10-12")
    assert "network-search-two-weeks.py" in т
    assert "metrika-day-settled.py" in т


def test_предупреждение_говорит_в_какую_сторону_ошибка():
    # «Числа неточны» ничего не даёт: важно, что рост именно ЗАВЫШЕН.
    т = модуль.предупреждение_о_досчёте("2026-10-19", "2026-10-12")
    assert "ЗАВЫШЕН" in т


def test_предупреждение_попадает_в_json(tmp_path, monkeypatch):
    выход = tmp_path / "traffic-wow.json"
    код = модуль.главная(["--now", "2026-10-19", "--prev", "2026-10-12",
                          "--out", str(выход)])
    assert код == 0
    import json
    d = json.loads(выход.read_text(encoding="utf-8"))
    assert "MOD-131" in d["предупреждение"]
    assert d["снимок_раньше"] == "2026-10-12"
