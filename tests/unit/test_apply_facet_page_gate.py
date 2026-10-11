"""apply-facet-page-gate.py: путевые фасеты получают _page_gate; повтор без изменений; отказ без якоря."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
спец = importlib.util.spec_from_file_location(
    "apply_facet_page_gate", ROOT / "automation" / "host" / "apply-facet-page-gate.py"
)
инструмент = importlib.util.module_from_spec(спец)
спец.loader.exec_module(инструмент)

ОБРАЗЕЦ = """class Обработчик:
    def _page_gate(self, в, путь, разд, зпр, path_kind):
        return self.ответ

    def маршрут(self, в, путь, зпр, год, код):
        if год:
            зпр = dict(зпр)
            зпр["year"] = [год.group("year")]
            return self._отдать(в.список("/catalog", зпр).encode("utf-8"))
        if код:
            зпр = dict(зпр)
            зпр["country"] = [код]
            return self._отдать(в.список("/catalog", зпр).encode("utf-8"))
"""


def test_both_facet_routes_get_the_gate_and_rerun_is_a_no_op():
    новый, n = инструмент.привести(ОБРАЗЕЦ)
    assert n == 2 and новый.count("if self._page_gate(в, путь, \"/catalog\", зпр, None):") == 2
    assert инструмент.привести(новый) == (новый, 0)


def test_rewritten_route_stops_when_the_gate_answered():
    новый, _ = инструмент.привести(ОБРАЗЕЦ)
    пространство: dict = {}
    exec(новый, пространство)  # noqa: S102 — проверка вставляемого кода
    обр = пространство["Обработчик"]()
    отдано = []
    обр._отдать = отдано.append

    class Год:
        def group(self, _):
            return "2024"

    class Вид:
        def список(self, разд, зпр):
            return "страница"

    обр.ответ = True  # шлюз уже ответил 400/404/308
    assert обр.маршрут(Вид(), "/year/2024/", {"page": ["abc"]}, Год(), None) is None and not отдано
    обр.ответ = None
    обр.маршрут(Вид(), "/year/2024/", {}, Год(), None)
    assert отдано == ["страница".encode("utf-8")]


def test_file_without_gate_is_refused():
    with pytest.raises(ValueError):
        инструмент.привести(ОБРАЗЕЦ.replace("_page_gate(self", "_другое(self"))
