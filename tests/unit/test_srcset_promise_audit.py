"""Проверки инструмента замера обещаний srcset (MOD-214, MOD-217).

Инструмент меряет цель, а не разметку, поэтому тесты закрепляют именно
различение исходов: «обещать нечего», «обещано больше настоящего» и
«не измерено». Подмена последнего тихим нулём — та самая ошибка, из-за
которой замер вообще понадобился.
"""
from __future__ import annotations

import importlib.util
import pathlib

import pytest

КОРЕНЬ = pathlib.Path(__file__).resolve().parents[2]
ПУТЬ = КОРЕНЬ / "automation" / "local" / "srcset-promise-audit.py"


def _модуль():
    спец = importlib.util.spec_from_file_location("srcset_promise_audit", ПУТЬ)
    assert спец and спец.loader
    м = importlib.util.module_from_spec(спец)
    спец.loader.exec_module(м)
    return м


@pytest.fixture(scope="module")
def ин():
    return _модуль()


def test_инструмент_на_месте():
    assert ПУТЬ.is_file()


@pytest.mark.parametrize(
    "значение, ожидание",
    [
        ("/p/a.webp?w=240 240w, /p/a.webp 480w", [("/p/a.webp?w=240", 240),
                                                  ("/p/a.webp", 480)]),
        ("  /p/a.webp?w=240   240w ,/p/a.webp 480w ", [("/p/a.webp?w=240", 240),
                                                       ("/p/a.webp", 480)]),
        ("/p/a.webp 2x", []),                       # плотность, а не ширина
        ("/p/a.webp", []),                          # без описателя
        ("/p/a.webp xw", []),                       # ширина не число
    ],
)
def test_разбор_srcset(ин, значение, ожидание):
    assert ин._разобрать_srcset(значение) == ожидание


@pytest.mark.parametrize(
    "адрес, ожидание",
    [
        ("/poster/a.webp?w=240", "/poster/a.webp"),
        ("/poster/a.webp", "/poster/a.webp"),
        ("/poster/a.webp?w=240&v=7", "/poster/a.webp?v=7"),
        ("https://d/poster/a.webp?w=1200", "https://d/poster/a.webp"),
    ],
)
def test_основа_без_ширины(ин, адрес, ожидание):
    assert ин._без_ширины(адрес) == ожидание


def _подменить(ин, разметка, ширина, причина=""):
    ин._получить = lambda url, начало=False: разметка.encode("utf-8")
    ин._ширина_файла = lambda url: (ширина, причина)


def test_без_srcset_не_дефект(ин, monkeypatch):
    """Витрина без srcset ничего не обещает — это отдельный исход."""
    monkeypatch.setattr(ин, "_получить",
                        lambda url, начало=False: b'<img src="/poster/a.webp">')
    итог = ин.проверить("x.test", "/", 12)
    assert итог["обложек с srcset"] == 0
    assert итог["обложек без srcset"] == 1
    assert итог["ложных обещаний"] == 0
    assert "обещать нечего" in итог["исход"]


def test_обещано_больше_настоящего_дефект(ин, monkeypatch):
    monkeypatch.setattr(ин, "_получить", lambda url, начало=False:
                        b'<img srcset="/poster/a.webp?w=240 240w, /poster/a.webp 480w">')
    monkeypatch.setattr(ин, "_ширина_файла", lambda url: (424, ""))
    итог = ин.проверить("x.test", "/", 12)
    assert итог["описателей"] == 2
    assert итог["ложных обещаний"] == 1          # 480 > 424, а 240 — нет
    assert итог["случаи"][0]["обещано"] == 480
    assert итог["случаи"][0]["настоящая"] == 424
    assert итог["исход"].startswith("ДЕФЕКТ")


def test_обещано_ровно_настоящее_не_дефект(ин, monkeypatch):
    """Граница: обещание РАВНО настоящему — исполнимо, это не дефект."""
    monkeypatch.setattr(ин, "_получить", lambda url, начало=False:
                        b'<img srcset="/poster/a.webp 480w">')
    monkeypatch.setattr(ин, "_ширина_файла", lambda url: (480, ""))
    итог = ин.проверить("x.test", "/", 12)
    assert итог["ложных обещаний"] == 0
    assert "цель достигнута" in итог["исход"]


def test_непрочитанный_файл_не_становится_нулём(ин, monkeypatch):
    """Неизмеренное идёт как неизмеренное с причиной, а не как «дефектов нет»."""
    monkeypatch.setattr(ин, "_получить", lambda url, начало=False:
                        b'<img srcset="/poster/a.webp 480w">')
    monkeypatch.setattr(ин, "_ширина_файла", lambda url: (None, "HTTP 404"))
    итог = ин.проверить("x.test", "/", 12)
    assert итог["не измерено"] == 1
    assert итог["ложных обещаний"] == 0
    assert итог["исход"].startswith("НЕ ИЗМЕРЕНО")
    assert итог["случаи"][0]["причина"] == "HTTP 404"


def test_недоступная_страница_не_даёт_зелёного(ин, monkeypatch):
    def падать(url, начало=False):
        raise OSError("сеть недоступна")
    monkeypatch.setattr(ин, "_получить", падать)
    итог = ин.проверить("x.test", "/", 12)
    assert "страница не получена" in итог["исход"]
    assert итог["описателей"] == 0


def test_один_файл_меряется_однажды(ин, monkeypatch):
    """Повторное чтение той же обложки на странице не делается."""
    monkeypatch.setattr(ин, "_получить", lambda url, начало=False:
                        b'<img srcset="/poster/a.webp 480w">'
                        b'<img srcset="/poster/a.webp 480w">')
    счёт = {"n": 0}

    def мерить(url):
        счёт["n"] += 1
        return 480, ""
    monkeypatch.setattr(ин, "_ширина_файла", мерить)
    ин.проверить("x.test", "/", 12)
    assert счёт["n"] == 1
