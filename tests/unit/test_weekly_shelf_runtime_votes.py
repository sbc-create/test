"""Витрина не показывает оценку по десятку голосов даже из старого снимка.

Порог стоит в сборщике недельного снимка, но снимок пересобирается раз в
неделю расписанием владельца. Без проверки ПРИ ЧТЕНИИ выложенный блок до
следующей пересборки продолжал бы показывать 8.5 по четырнадцати оценкам —
исправление осталось бы на бумаге.
"""
from __future__ import annotations

import ast
import pathlib

import pytest

КОРЕНЬ = pathlib.Path(__file__).resolve().parents[2]
РАНТАЙМЫ = (
    КОРЕНЬ / "var" / "site-repos" / "zonafilm-space" / "src" / "lords-frontend.py",
    КОРЕНЬ / "var" / "site-repos" / "zonafilm12-site" / "src" / "lords-frontend.py",
)


def _механизм(путь: pathlib.Path) -> dict:
    """Функции полки из рантайма — исполнением нужных кусков, без запуска витрины."""
    текст = путь.read_text(encoding="utf-8")
    дерево = ast.parse(текст)
    строки = текст.splitlines()
    куски = []
    for узел in дерево.body:
        имя = getattr(узел, "name", None)
        цели = [ц.id for ц in getattr(узел, "targets", [])
                if isinstance(ц, ast.Name)]
        if имя in ("_из_weekly_полки", "_оценок_у_записи") or \
                "ПОЛКА_МИН_ОЦЕНОК" in цели:
            куски.append("\n".join(строки[узел.lineno - 1:узел.end_lineno]))
    область = {"os": __import__("os"), "__name__": "полка"}
    exec(compile("\n\n".join(куски), str(путь), "exec"), область)  # noqa: S102
    assert "_из_weekly_полки" in область, путь
    return область


class Данные:
    def __init__(self, записи, подробности):
        self.items = записи
        self.подробности = type("П", (), {"записи": подробности})()


@pytest.fixture(params=РАНТАЙМЫ, ids=lambda п: п.parts[-3])
def м(request):
    return _механизм(request.param)


def _снимок(слаги):
    return {"shelves": {"pop-films": list(слаги)}, "reserves": {}}


def test_мало_оценок_не_показывается(м):
    записи = [{"slug": "malo", "kind": "Фильм"}, {"slug": "mnogo", "kind": "Фильм"}]
    подробности = {
        "malo": {"ratings_by_source": {"imdb": {"votes": 14}}},
        "mnogo": {"ratings_by_source": {"imdb": {"votes": 120_000}}},
    }
    итог = м["_из_weekly_полки"](Данные(записи, подробности),
                                 _снимок(["malo", "mnogo"]), "pop-films")
    assert [з["slug"] for з in итог] == ["mnogo"], итог


def test_без_числа_оценок_не_показывается(м):
    записи = [{"slug": "bez", "kind": "Фильм"}]
    подробности = {"bez": {"ratings_by_source": {}}}
    итог = м["_из_weekly_полки"](Данные(записи, подробности),
                                 _снимок(["bez"]), "pop-films")
    assert итог == [], итог


def test_без_подробностей_полка_не_обрезается(м):
    """Нет подробностей — проверить нечем, и витрина не делает вид, что
    проверила: полка остаётся как в снимке."""
    записи = [{"slug": "x", "kind": "Фильм"}]
    пустые = Данные(записи, {})
    итог = м["_из_weekly_полки"](пустые, _снимок(["x"]), "pop-films")
    assert [з["slug"] for з in итог] == ["x"], итог


def test_порог_общий_со_сборщиком(м):
    assert м["ПОЛКА_МИН_ОЦЕНОК"] >= 1000
