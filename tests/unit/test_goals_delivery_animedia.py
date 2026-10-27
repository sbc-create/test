"""Отправка целей Метрики на линии Animedia: событие уходит, а не только счётчик.

Замер линии ячейки 27.10: счётчик `113288667` на страницах инициализирован, а
`__sfGoal`/`reachGoal` в разметке нет вовсе — все девять целей за 20–26.10
равны нулю при 4417 визитах. Нуль там означал «событие не отправлялось», а не
поведение зрителя.

У этой линии свой скрипт плеера: ни `requested`, ни `nextOrFail`, ни трёх
ветвей готовности в нём нет, состояния ставит одна функция `state(k,…)`.
Поэтому точки отправки свои, и набор Zona на этом файле применять нельзя.
"""
from __future__ import annotations

import os
import pathlib
import re
import subprocess
import sys
import tempfile

import pytest

КОРЕНЬ = pathlib.Path(__file__).resolve().parents[2]
ИНСТРУМЕНТ = КОРЕНЬ / "automation" / "host" / "apply-goals-patch.py"
РАНТАЙМ = (КОРЕНЬ / "var" / "site-repos" / "animedia-icu" / "src"
           / "animedia-frontend.py")
#: Закрытый список. Две цели о рекомендательных блоках добавлены 27.10:
#: показов блоков не измеряла ни одна цель, и «блок показали, но из него не
#: переходят» было неотличимо от «блок никто не видел». Ключ блока в цель не
#: уходит — третьего аргумента у точки отправки нет по устройству.
ЦЕЛИ = ("title_view", "search", "filter_apply", "season_select",
        "episode_select", "player_start", "player_ready", "player_error",
        "block_view", "block_click")


def _текст() -> str:
    return РАНТАЙМ.read_text(encoding="utf-8")


def test_линия_приведена():
    и = subprocess.run([sys.executable, str(ИНСТРУМЕНТ), "--check", str(РАНТАЙМ)],
                       capture_output=True, text=True, timeout=180)
    assert и.returncode == 0, и.stdout + и.stderr


def test_список_целей_совпадает_с_каноном():
    м = re.search(r"ЦЕЛИ_МЕТРИКИ = \(\n(.*?)\n\)", _текст(), re.S)
    assert м, "закрытый список целей не найден"
    найденные = tuple(re.findall(r'"([a-z_]+)"', м.group(1)))
    assert найденные == ЦЕЛИ, найденные
    канон = (КОРЕНЬ / "automation" / "host" / "lords-frontend.py").read_text(
        encoding="utf-8")
    мк = re.search(r"ЦЕЛИ_МЕТРИКИ = \(\n(.*?)\n\)", канон, re.S)
    assert tuple(re.findall(r'"([a-z_]+)"', мк.group(1))) == найденные


def test_отправка_без_параметров():
    т = _текст()
    assert "window.ym(C,'reachGoal',n);" in т
    assert "reachGoal',n,{" not in т and 'reachGoal",n,{' not in т


def test_точки_плеера_этой_линии():
    """Каждая цель плеера стоит на СВОЕЙ точке, а не на выдуманной.

    `player_error` — в единственной ветви жёстких состояний (`hard`),
    `player_ready` — там, где оболочка поставщика смонтирована (`active`/`ok`),
    `player_start` — на первом продвижении медиа.
    """
    т = _текст()
    отказ = т[т.index("if(hard){ отказ=true;"):][:300]
    assert "__sfGoalOnce('player_error')" in отказ
    готов = т[т.index("if(k==='ok'||k==='resolving'||k==='active'){"):][:400]
    assert "if(k==='ok'||k==='active'){" in готов
    assert "__sfGoalOnce('player_ready')" in готов
    пуск = т[т.index("} else if(ct>0.05){"):][:400]
    assert "__sfGoalOnce('player_start')" in пуск


def test_готовность_не_уходит_на_resolving():
    """`resolving` ставится ДО монтирования оболочки: цель там означала бы
    намерение, а не поднявшийся плеер."""
    т = _текст()
    готов = т[т.index("if(k==='ok'||k==='resolving'||k==='active'){"):][:400]
    # Условие цели перечисляет ровно два состояния и не включает resolving.
    строка = [с for с in готов.splitlines() if "__sfGoalOnce('player_ready')" in с]
    assert строка, готов
    условие = готов[:готов.index(строка[0])]
    assert "if(k==='ok'||k==='active'){" in условие
    assert "resolving" not in условие.split("if(k==='ok'||k==='active'){")[1]


def test_скрипт_плеера_остался_разбираемым():
    """Правка внесена в живой JS: `node --check` обязателен, иначе вместо
    события витрина получит страницу со сломанным скриптом."""
    т = _текст()
    начало = 'СКРИПТ_ПЛЕЕРА_КЛИЕНТ = """'
    i = т.index(начало) + len(начало)
    js = т[i:т.index('"""', i)]
    assert "__sfGoalOnce('player_start')" in js
    with tempfile.TemporaryDirectory() as кат:
        ф = pathlib.Path(кат) / "player.js"
        ф.write_text(js, encoding="utf-8")
        и = subprocess.run(["node", "--check", str(ф)], capture_output=True,
                           text=True, timeout=60)
    assert и.returncode == 0, и.stderr


def test_разметка_целей_разбирается_и_несёт_счётчик():
    т = _текст()
    k = т.index("ЦЕЛИ_МЕТРИКИ = (")
    область = {"__name__": "цели"}
    exec(compile(т[k:т.index("\ndef тег_метрики", k)], "цели", "exec"), область)
    разметка = область["цели_метрики"]("113288667")
    assert разметка.startswith("<script>") and разметка.endswith("</script>")
    assert "var C=113288667," in разметка
    assert "__sfGoalOnce('title_view')" in разметка
    with tempfile.TemporaryDirectory() as кат:
        ф = pathlib.Path(кат) / "goals.js"
        ф.write_text(разметка[len("<script>"):-len("</script>")], encoding="utf-8")
        и = subprocess.run(["node", "--check", str(ф)], capture_output=True,
                           text=True, timeout=60)
    assert и.returncode == 0, и.stderr


def test_канон_не_мерится_якорями_другой_линии():
    """На каноне инструмент обязан сказать «не этой линии», а не перечислять
    отсутствующие якоря Zona: у канона отправка целей своя, и список остатков
    по чужим якорям был бы ложным дефектом. Правка его точек по этим якорям
    сломала бы работающее."""
    канон = (КОРЕНЬ / "automation" / "host" / "lords-frontend.py")
    и = subprocess.run([sys.executable, str(ИНСТРУМЕНТ), "--check", str(канон)],
                       capture_output=True, text=True, timeout=180)
    assert и.returncode == 0, и.stdout + и.stderr
    assert "не этой линии" in и.stdout
    assert "остатки" not in и.stdout
    п = subprocess.run([sys.executable, str(ИНСТРУМЕНТ), str(канон)],
                       capture_output=True, text=True, timeout=180)
    assert "не этой линии" in п.stdout
    assert канон.read_text(encoding="utf-8").count("__sfGoal") > 0


def test_инструмент_отказывает_без_якоря():
    """Якорь не найден — отказ ДО записи, а не подгонка под похожее место."""
    with tempfile.TemporaryDirectory() as кат:
        ф = pathlib.Path(кат) / "animedia-frontend.py"
        ф.write_text(
            "СЧЁТЧИК_МЕТРИКИ = ''\n\n"
            "def тег_метрики() -> str:\n    return ''\n\n"
            "class В:\n    def _карточки_коллекций(self):\n        return []\n",
            encoding="utf-8")
        и = subprocess.run([sys.executable, str(ИНСТРУМЕНТ), str(ф)],
                           capture_output=True, text=True, timeout=120)
    assert и.returncode != 0
    assert "ОТКАЗ" in (и.stdout + и.stderr)
