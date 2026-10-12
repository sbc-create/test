"""Якорь расписания таймера: поломка, замечание и разница между ними.

Повод оплачен дважды и обе аварии задокументированы в самих юнитах:

* 2026-09-04 07:11 — убитый прогон `lords-content-refresh` остановил
  расписание, каталог не обновлялся сутки, а таймер числился `active`.
  `OnUnitActiveSec` считает от последней АКТИВАЦИИ службы, и мёртвая служба
  больше не активируется: следующий срок становится `infinity`;
* связка `OnBootSec` + `OnUnitActiveSec` без календаря дала `NEXT: n/a` —
  поданная заявка пролежала необработанной при `enabled` и `active`.

Разница между этими двумя случаями принципиальна, и тесты её закрепляют.
Первый — ПОЛОМКА: она наступает у любого работающего таймера, как только
прогон убьют. Второй — ЗАМЕЧАНИЕ: он требует, чтобы момент загрузки уже прошёл
И служба ни разу не активировалась, то есть проверять его надо при включении
таймера, а не у того, который годами наполняет каталоги. Смешать их значило бы
объявить сломанными пять исправно работающих обработчиков обновлений, и
проверка перестала бы читаться.
"""
from __future__ import annotations

import importlib.util
import io
import json
from contextlib import redirect_stdout
from pathlib import Path

import pytest

КОРЕНЬ = Path(__file__).resolve().parents[2]
ИСТОЧНИК = КОРЕНЬ / "automation" / "local" / "timer-anchors.py"


def _модуль():
    спец = importlib.util.spec_from_file_location("timer_anchors", ИСТОЧНИК)
    м = importlib.util.module_from_spec(спец)
    спец.loader.exec_module(м)
    return м


@pytest.fixture(scope="module")
def м():
    return _модуль()


def таймер(каталог: Path, имя: str, тело: str) -> None:
    (каталог / имя).write_text(f"[Unit]\nDescription=x\n[Timer]\n{тело}",
                               encoding="utf-8")


def test_без_якоря_по_завершению_это_поломка(м, tmp_path):
    таймер(tmp_path, "а.timer", "OnBootSec=3min\nOnUnitActiveSec=10min\n")
    буфер = io.StringIO()
    with redirect_stdout(буфер):
        код = м.главное(["--units", str(tmp_path)])
    вывод = буфер.getvalue()
    assert код == 1
    assert "БЕЗ ЯКОРЯ ПО ЗАВЕРШЕНИЮ: 1" in вывод
    assert "ПОЛОМКА" in вывод


def test_якорь_по_завершению_снимает_поломку(м, tmp_path):
    таймер(tmp_path, "б.timer",
           "OnBootSec=3min\nOnUnitActiveSec=10min\nOnUnitInactiveSec=10min\n")
    буфер = io.StringIO()
    with redirect_stdout(буфер):
        код = м.главное(["--units", str(tmp_path)])
    assert код == 0
    assert "главную ловушку" in буфер.getvalue()


def test_календарь_снимает_поломку(м, tmp_path):
    """OnCalendar считает от стенных часов: убитый прогон расписание не рвёт."""
    таймер(tmp_path, "в.timer", "OnCalendar=*:0/5\nPersistent=true\n")
    буфер = io.StringIO()
    with redirect_stdout(буфер):
        assert м.главное(["--units", str(tmp_path)]) == 0


def test_замечание_не_делает_код_ненулевым(м, tmp_path):
    """Иначе проверка падает на том, что проверять надо в другой момент (D205)."""
    таймер(tmp_path, "г.timer", "OnCalendar=*:0/5\n")   # без Persistent
    буфер = io.StringIO()
    with redirect_stdout(буфер):
        код = м.главное(["--units", str(tmp_path)])
    вывод = буфер.getvalue()
    assert код == 0, "замечание — не поломка"
    assert "ЗАМЕЧАНИЯ (не поломки)" in вывод
    assert "Persistent" in вывод


def test_связка_загрузки_и_активации_это_замечание_а_не_поломка(м, tmp_path):
    """Риск ВКЛЮЧЕНИЯ: для уже работающего таймера срок считается и находится.

    Поломкой здесь остаётся только отсутствие якоря по завершению, поэтому у
    такого таймера ровно одна беда и одно замечание, а не две беды.
    """
    таймер(tmp_path, "д.timer", "OnBootSec=3min\nOnUnitActiveSec=10min\n")
    знач = м.директивы(м.строки_юнита("д.timer", tmp_path))
    разбор = м.разобрать("д.timer", знач)
    assert len(разбор["беды"]) == 1
    assert "OnUnitInactiveSec" in разбор["беды"][0]
    assert len(разбор["замечания"]) == 1
    assert "NEXT: n/a" in разбор["замечания"][0]
    assert "не поломка" in разбор["замечания"][0]


def test_таймер_без_источника_времени_это_поломка(м, tmp_path):
    таймер(tmp_path, "е.timer", "AccuracySec=1min\n")
    разбор = м.разобрать("е.timer",
                         м.директивы(м.строки_юнита("е.timer", tmp_path)))
    assert any("источника времени нет" in б for б in разбор["беды"])


def test_dropin_перекрывает_основной_файл(м, tmp_path):
    таймер(tmp_path, "ж.timer", "OnBootSec=3min\nOnUnitActiveSec=10min\n")
    (tmp_path / "ж.timer.d").mkdir()
    (tmp_path / "ж.timer.d" / "10-якорь.conf").write_text(
        "[Timer]\nOnUnitInactiveSec=10min\n", encoding="utf-8")
    разбор = м.разобрать("ж.timer",
                         м.директивы(м.строки_юнита("ж.timer", tmp_path)))
    assert разбор["беды"] == []


def test_пустое_присваивание_снимает_якорь(м, tmp_path):
    """`OnUnitInactiveSec=` у systemd сбрасывает значение — и поломка возвращается."""
    таймер(tmp_path, "з.timer",
           "OnBootSec=3min\nOnUnitActiveSec=10min\nOnUnitInactiveSec=10min\n")
    (tmp_path / "з.timer.d").mkdir()
    (tmp_path / "з.timer.d" / "20-снять.conf").write_text(
        "[Timer]\nOnUnitInactiveSec=\n", encoding="utf-8")
    разбор = м.разобрать("з.timer",
                         м.директивы(м.строки_юнита("з.timer", tmp_path)))
    assert len(разбор["беды"]) == 1


def test_комментарий_якорем_не_считается(м, tmp_path):
    таймер(tmp_path, "и.timer",
           "OnBootSec=3min\nOnUnitActiveSec=10min\n"
           "# OnUnitInactiveSec=10min — обсуждалось, не включено\n")
    разбор = м.разобрать("и.timer",
                         м.директивы(м.строки_юнита("и.timer", tmp_path)))
    assert len(разбор["беды"]) == 1


def test_нечитаемый_юнит_это_не_измерено(м, tmp_path):
    """Факт о сессии, не о таймере: тревогу по нему поднимать нельзя."""
    assert м.строки_юнита("нет-такого.timer", tmp_path) is None
    знач = м.директивы(None)
    assert set(знач.values()) == {м.НЕ_ИЗМЕРЕНО}
    разбор = м.разобрать("нет-такого.timer", знач)
    # Вердикта нет вовсе: ни бед, ни замечаний, и состояние названо отдельно.
    # Без этого «не измерено» давало беду «источника времени нет» — факт о
    # сессии, выданный за факт о таймере. Поймано этим тестом.
    assert разбор["беды"] == []
    assert разбор["замечания"] == []
    assert разбор["не_измерено"] is True


def test_нечитаемый_dropin_не_выдаётся_за_отсутствие_якоря(м, tmp_path):
    таймер(tmp_path, "к.timer", "OnBootSec=3min\nOnUnitActiveSec=10min\n")
    строки = м.строки_юнита("к.timer", tmp_path)
    строки.append(f"{м.МЕТКА_НЕЧИТАЕМОГО} 99-чужой.conf")
    знач = м.директивы(строки)
    assert знач["OnUnitInactiveSec"] == м.НЕ_ИЗМЕРЕНО
    # «Не измерено» задано не считается, поэтому беда остаётся — и это верно:
    # нечитаемый кусок мог якорь и не ставить. Но слово о пределе знания
    # сохранено в самих директивах.
    assert м.задано(знач["OnUnitInactiveSec"]) is False


def test_пустой_каталог_это_отказ(м, tmp_path):
    assert м.главное(["--units", str(tmp_path)]) == 2


def test_можно_спросить_один_таймер(м, tmp_path):
    таймер(tmp_path, "л.timer", "OnCalendar=*:0/5\nPersistent=true\n")
    таймер(tmp_path, "м.timer", "OnBootSec=1min\nOnUnitActiveSec=5min\n")
    буфер = io.StringIO()
    with redirect_stdout(буфер):
        код = м.главное(["--units", str(tmp_path), "--timer", "л"])
    assert код == 0, "спрошен исправный таймер — сломанный в счёт не идёт"
    assert "прочитано: 1" in буфер.getvalue()


def test_json_вывод_разбирается(м, tmp_path):
    таймер(tmp_path, "н.timer", "OnBootSec=3min\nOnUnitActiveSec=10min\n")
    буфер = io.StringIO()
    with redirect_stdout(буфер):
        код = м.главное(["--units", str(tmp_path), "--json"])
    assert код == 1
    данные = json.loads(буфер.getvalue())
    assert данные[0]["юнит"] == "н.timer"
    assert данные[0]["беды"] and данные[0]["замечания"]
