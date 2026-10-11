"""apply-empty-filter-404.py: нераспознанный и пустой фильтр Zona — 404 без canonical; повтор без изменений; отказ без якоря."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
спец = importlib.util.spec_from_file_location(
    "apply_empty_filter_404", ROOT / "automation" / "host" / "apply-empty-filter-404.py"
)
инструмент = importlib.util.module_from_spec(спец)
спец.loader.exec_module(инструмент)

ОБРАЗЕЦ = '''class Вид:
    имя = "Zona"

    def оболочка(self, тело, титул, адрес, **к):
        return (тело, к.get("код", 200), адрес)

    def список(self, разд, выбрано, кусок, есть_условия):
        if выбрано.get("_unknown"):
            тело = "неизвестно"
            return self.оболочка(тело, f"Некорректный фильтр — {self.имя}",
                                 разд + "/", код=400)
        if кусок:
            сетка = "плитки"
        elif есть_условия:
            сетка = ('<div class="zempty"><b>Ничего не подошло</b>'
                     "</div>")
        else:
            сетка = "пуст снимок"
        тело = сетка
        титул, хвост, адрес, актив = "Каталог", "", разд + "/", разд + "/"
        return self.оболочка(тело, f"{титул}{хвост} — {self.имя}", адрес,
                             актив=актив,
                             описание=f"{титул} на витрине {self.имя}{хвост}.",
                             сверху="")


class Обработчик:
    def _отдать(self, тело, код=200):
        self.отдано = (тело, код)

    def _переход(self, цель: str):
        return цель

    def маршрут(self, в, разд, выбрано, кусок, есть_условия):
        return self._отдать(в.список(разд, выбрано, кусок, есть_условия).encode("utf-8"))
'''


def _собрать():
    новый, n = инструмент.привести(ОБРАЗЕЦ)
    assert n == 1
    пространство: dict = {}
    exec(новый.replace('.encode("utf-8")', ""), пространство)  # noqa: S102 — вид-образец отдаёт кортеж
    return новый, пространство


def test_rerun_is_a_no_op_and_missing_anchor_is_refused():
    новый, _ = _собрать()
    assert инструмент.привести(новый) == (новый, 0)
    with pytest.raises(ValueError):
        инструмент.привести(ОБРАЗЕЦ.replace("Ничего не подошло", "Пусто"))
    with pytest.raises(ValueError):
        инструмент.привести(ОБРАЗЕЦ.replace('сверху="")', 'сверху="x")'))


@pytest.mark.parametrize("выбрано, кусок, условия, ждём", [
    ({"_unknown": "1"}, [], False, 404),       # нераспознанный фильтр
    ({"genre": "x"}, [], True, 404),            # фильтр без единой записи
    ({}, [], False, 200),                       # пуст снимок — не фильтр
    ({"genre": "x"}, ["з"], True, 200),         # обычная выдача
])
def test_view_code_reaches_shell_and_route(выбрано, кусок, условия, ждём):
    _, п = _собрать()
    в = п["Вид"]()
    тело, код_оболочки, _ = в.список("/catalog", выбрано, кусок, условия)
    assert код_оболочки == ждём  # оболочка не ставит canonical при коде ≠ 200
    обр = п["Обработчик"]()
    в2 = п["Вид"]()
    в2.список("/catalog", выбрано, кусок, условия)
    обр._отдать_вид(в2, "страница")
    assert обр.отдано[1] == ждём
