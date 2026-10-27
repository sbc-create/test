"""Отправка целей Метрики на линии Zona: событие уходит, а не только счётчик.

Измерено 27.10 на живых адресах: счётчик на страницах ЕСТЬ (`112582938` у
zonafilm.space, `113109081` у zonafilm12.site), `mc.yandex` загружается — а ни
одного `reachGoal` в разметке нет. Значит нули в отчёте о целях означали
«событие не отправлялось», а не «зритель так себя ведёт»: считать их
поведением пользователей нельзя.
"""
from __future__ import annotations

import pathlib
import re
import subprocess
import sys
import tempfile

import pytest

КОРЕНЬ = pathlib.Path(__file__).resolve().parents[2]
ИНСТРУМЕНТ = КОРЕНЬ / "automation" / "host" / "apply-goals-patch.py"
ЛИНИЯ = [КОРЕНЬ / "var" / "site-repos" / имя / "src" / "lords-frontend.py"
         for имя in ("zonafilm-space", "zonafilm12-site")]
#: Тот же закрытый список, что в каноне. Расхождение означало бы, что одна цель
#: значит на разных витринах разное.
#: Закрытый список. Две цели о рекомендательных блоках добавлены 27.10:
#: показов блоков не измеряла ни одна цель, и «блок показали, но из него не
#: переходят» было неотличимо от «блок никто не видел». Ключ блока в цель не
#: уходит — третьего аргумента у точки отправки нет по устройству.
ЦЕЛИ = ("title_view", "search", "filter_apply", "season_select",
        "episode_select", "player_start", "player_ready", "player_error",
        "block_view", "block_click")


def test_линия_приведена():
    и = subprocess.run([sys.executable, str(ИНСТРУМЕНТ), "--check",
                        *[str(п) for п in ЛИНИЯ]],
                       capture_output=True, text=True, timeout=180)
    assert и.returncode == 0, и.stdout + и.stderr


@pytest.mark.parametrize("путь", ЛИНИЯ, ids=lambda п: п.parts[-3])
def test_список_целей_совпадает_с_каноном(путь):
    т = путь.read_text(encoding="utf-8")
    м = re.search(r"ЦЕЛИ_МЕТРИКИ = \(\n(.*?)\n\)", т, re.S)
    assert м, "закрытый список целей не найден"
    найденные = tuple(re.findall(r'"([a-z_]+)"', м.group(1)))
    assert найденные == ЦЕЛИ, найденные
    канон = (КОРЕНЬ / "automation" / "host" / "lords-frontend.py").read_text(
        encoding="utf-8")
    мк = re.search(r"ЦЕЛИ_МЕТРИКИ = \(\n(.*?)\n\)", канон, re.S)
    assert tuple(re.findall(r'"([a-z_]+)"', мк.group(1))) == найденные


@pytest.mark.parametrize("путь", ЛИНИЯ, ids=lambda п: п.parts[-3])
def test_отправка_без_параметров(путь):
    """Третьего аргумента у точки отправки не существует: вызов «с данными»
    написать нечем, и поисковая фраза в отчёт попасть не может."""
    т = путь.read_text(encoding="utf-8")
    assert "window.ym(C,'reachGoal',n);" in т
    assert "reachGoal',n,{" not in т and 'reachGoal",n,{' not in т
    # Поиск отправляет цель, но не фразу.
    assert "g('search')" in т
    assert "q=" not in т.split("g('search')")[1][:200]


@pytest.mark.parametrize("путь", ЛИНИЯ, ids=lambda п: п.parts[-3])
def test_отправка_подключена_одним_местом(путь):
    """Правка в четырёх оболочках разошлась бы: тег метрики один на все."""
    т = путь.read_text(encoding="utf-8")
    assert т.count("+ цели_метрики(н)") == 1
    assert "def цели_метрики(номер: str)" in т


@pytest.mark.parametrize("путь", ЛИНИЯ, ids=lambda п: п.parts[-3])
def test_цели_плеера_на_своих_точках(путь):
    т = путь.read_text(encoding="utf-8")
    assert "__sfGoalOnce('player_start')" in т
    assert "__sfGoalOnce('player_ready')" in т
    assert "__sfGoalOnce('player_error')" in т
    # Готовность у этой линии приходит тремя ветвями событий провайдера —
    # событие обязано уходить со всех, иначе часть путей останется без него.
    assert т.count("__sfGoalOnce('player_ready')") >= 3


@pytest.mark.parametrize("путь", ЛИНИЯ, ids=lambda п: п.parts[-3])
def test_скрипт_целей_разбирается_как_javascript(путь):
    """Проверяется ГОТОВАЯ разметка, а не попытка собрать её из исходника.

    Первая редакция проверки склеивала скрипт из строковых литералов файла и
    падала на своей же склейке — то есть измеряла себя, а не правку. Здесь
    исполняется сама функция: `цели_метрики` зависит только от закрытого
    списка целей, поэтому её можно поднять в отдельном пространстве имён без
    всего рантайма.
    """
    т = путь.read_text(encoding="utf-8")
    начало = т.index("ЦЕЛИ_МЕТРИКИ = (")
    конец = т.index("\n\ndef тег_метрики", начало)
    пространство: dict = {}
    exec(compile(т[начало:конец], str(путь), "exec"), пространство)  # noqa: S102
    разметка = пространство["цели_метрики"]("112582938")
    # Счётчик подставлен в переменную `C`, а вызов берёт её: так номер стоит в
    # разметке один раз, а не в каждом вызове.
    assert "var C=112582938," in разметка
    assert "window.ym(C,'reachGoal',n)" in разметка
    тела = re.findall(r"<script[^>]*>(.*?)</script>", разметка, re.S)
    assert тела, "скрипта в разметке нет"
    for тело in тела:
        with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False,
                                         encoding="utf-8") as ф:
            ф.write(тело)
            имя = ф.name
        г = subprocess.run(["node", "--check", имя], capture_output=True, text=True)
        assert г.returncode == 0, г.stderr[:300]
