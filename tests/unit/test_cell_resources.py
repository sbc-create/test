"""Пределы витрин: инструмент обязан различать «не задан» и «не измерено».

Проверяется поведение, а не имена: инструмент читает подставные файлы юнитов и
подставные cgroup, и каждый тест говорит, какой вывод при каком состоянии мира
допустим. Самое дорогое здесь — три различения, каждое из которых уже стоило
ошибки в отчёте раньше:

* отсутствующий предел — факт о юните, нечитаемый юнит — факт о сессии;
* `Имя=` пустой строкой у systemd СБРАСЫВАЕТ предел, и инструмент не вправе
  назвать такой предел исполняемым;
* предел в файле без применения ядром защитой не является.
"""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

КОРЕНЬ = Path(__file__).resolve().parents[2]
ИСТОЧНИК = КОРЕНЬ / "automation" / "local" / "cell-resources.py"


def _модуль():
    спец = importlib.util.spec_from_file_location("cell_resources", ИСТОЧНИК)
    м = importlib.util.module_from_spec(спец)
    спец.loader.exec_module(м)
    return м


@pytest.fixture(scope="module")
def м():
    return _модуль()


def _юнит(каталог: Path, имя: str, текст: str) -> None:
    (каталог / имя).write_text(текст, encoding="utf-8")


def test_предел_прочитан_из_файла_юнита(м, tmp_path, monkeypatch):
    monkeypatch.setattr(м, "ЮНИТЫ", tmp_path)
    _юнит(tmp_path, "а.service", "[Service]\nMemoryMax=512M\nTasksMax=32\n")
    знач = м.директивы(м.строки_юнита("а.service"), м.ПРЕДЕЛЫ)
    assert знач["MemoryMax"] == "512M"
    assert знач["TasksMax"] == "32"
    assert знач["CPUQuota"] == м.НЕ_ЗАДАН


def test_отсутствующий_юнит_это_не_измерено_а_не_не_задан(м, tmp_path,
                                                          monkeypatch):
    """Разница не косметическая: «не задан» разрешает тревогу, «не измерено» нет."""
    monkeypatch.setattr(м, "ЮНИТЫ", tmp_path)
    assert м.строки_юнита("нет-такого.service") is None
    знач = м.директивы(None, м.ПРЕДЕЛЫ)
    assert set(знач.values()) == {м.НЕ_ИЗМЕРЕНО}


def test_dropin_перекрывает_основной_файл(м, tmp_path, monkeypatch):
    monkeypatch.setattr(м, "ЮНИТЫ", tmp_path)
    _юнит(tmp_path, "б.service", "[Service]\nMemoryMax=256M\n")
    (tmp_path / "б.service.d").mkdir()
    _юнит(tmp_path / "б.service.d", "10-выше.conf",
          "[Service]\nMemoryMax=1G\n")
    знач = м.директивы(м.строки_юнита("б.service"), м.ПРЕДЕЛЫ)
    assert знач["MemoryMax"] == "1G"


def test_пустое_присваивание_снимает_предел(м, tmp_path, monkeypatch):
    """`MemoryMax=` у systemd сбрасывает значение.

    Если бы инструмент этого не повторял, drop-in, СНИМАЮЩИЙ предел, читался
    бы как предел на месте — ровно та ошибка, которой отчёт говорит «защита
    есть» там, где её нет.
    """
    monkeypatch.setattr(м, "ЮНИТЫ", tmp_path)
    _юнит(tmp_path, "в.service", "[Service]\nMemoryMax=256M\n")
    (tmp_path / "в.service.d").mkdir()
    _юнит(tmp_path / "в.service.d", "20-снять.conf", "[Service]\nMemoryMax=\n")
    знач = м.директивы(м.строки_юнита("в.service"), м.ПРЕДЕЛЫ)
    assert знач["MemoryMax"] == м.НЕ_ЗАДАН


def test_нечитаемый_dropin_не_выдаётся_за_отсутствие_предела(м, tmp_path,
                                                            monkeypatch):
    """Нечитаемый drop-in мог снимать предел: вывод обязан быть «не измерено»."""
    monkeypatch.setattr(м, "ЮНИТЫ", tmp_path)
    _юнит(tmp_path, "г.service", "[Service]\nMemoryMax=256M\n")
    строки = м.строки_юнита("г.service")
    строки.append(f"{м.МЕТКА_НЕЧИТАЕМОГО} 99-чужой.conf")
    знач = м.директивы(строки, м.ПРЕДЕЛЫ)
    # Названный предел остаётся названным, а НЕ названные становятся
    # «не измерено»: про них нечитаемый кусок как раз и мог говорить.
    assert знач["MemoryMax"] == "256M"
    assert знач["TasksMax"] == м.НЕ_ИЗМЕРЕНО


def test_комментарий_не_считается_пределом(м, tmp_path, monkeypatch):
    monkeypatch.setattr(м, "ЮНИТЫ", tmp_path)
    _юнит(tmp_path, "д.service",
          "[Service]\n# MemoryMax=4G — обсуждалось, не включено\n"
          "; TasksMax=16\n")
    знач = м.директивы(м.строки_юнита("д.service"), м.ПРЕДЕЛЫ)
    assert знач["MemoryMax"] == м.НЕ_ЗАДАН
    assert знач["TasksMax"] == м.НЕ_ЗАДАН


def test_юнит_из_cgroup_не_путает_кандидата_с_витриной(м):
    """Подстрока спутала бы `-candidate` с действующей службой.

    Цена ошибки — расход чужого процесса, приписанный живой витрине.
    """
    живой = "0::/system.slice/nova-lordserials22-space.service\n"
    кандидат = "0::/system.slice/nova-lordserials22-space-candidate.service\n"
    assert м._юнит_из_cgroup(живой) == "nova-lordserials22-space.service"
    assert (м._юнит_из_cgroup(кандидат)
            == "nova-lordserials22-space-candidate.service")
    assert м._юнит_из_cgroup(живой) != м._юнит_из_cgroup(кандидат)


def test_юнит_из_cgroup_терпит_мусор(м):
    assert м._юнит_из_cgroup("") == ""
    assert м._юнит_из_cgroup("12:pids:/\n") == ""


def _запись(**поля):
    основа = {
        "процессов": 1,
        "юнит_прочитан": True,
        "пределы": {"MemoryMax": "не задан"},
        "cgroup": {"прочитан": True, "max": "max"},
    }
    основа.update(поля)
    return основа


def test_тревога_только_при_живом_процессе_и_прочитанном_юните(м):
    без = м.НЕ_ЗАДАН
    assert м.без_предела_памяти(_запись(пределы={"MemoryMax": без}))
    # Мёртвый процесс — не повод: предел незапущенной службы ничего не решает.
    assert not м.без_предела_памяти(
        _запись(процессов=0, пределы={"MemoryMax": без}))
    # Непрочитанный юнит — факт о сессии, тревогу поднимать нельзя.
    assert not м.без_предела_памяти(
        _запись(юнит_прочитан=False, пределы={"MemoryMax": м.НЕ_ИЗМЕРЕНО}))


def test_предел_исполняемый_ядром_снимает_тревогу_без_строки_в_юните(м):
    """Ядро применяет предел — хост защищён, даже если строки в файле нет.

    Обратное тоже важно и проверено ниже: строка без применения не защищает.
    """
    assert not м.без_предела_памяти(
        _запись(пределы={"MemoryMax": м.НЕ_ЗАДАН},
                cgroup={"прочитан": True, "max": "2147483648"}))


def test_объявленный_но_не_применённый_предел_назван_расхождением(м):
    assert м.объявлено_но_не_применено(
        _запись(пределы={"MemoryMax": "2G"},
                cgroup={"прочитан": True, "max": "max"}))
    # Применён — расхождения нет.
    assert not м.объявлено_но_не_применено(
        _запись(пределы={"MemoryMax": "2G"},
                cgroup={"прочитан": True, "max": "2147483648"}))
    # cgroup не прочитан — утверждать расхождение нельзя.
    assert not м.объявлено_но_не_применено(
        _запись(пределы={"MemoryMax": "2G"}, cgroup={"прочитан": False}))


def test_oom_kill_не_читается_без_возраста(м, tmp_path, monkeypatch):
    """Ноль OOM у витрины, поднятой минуту назад, ничего не доказывает.

    Инвариант инструмента: там, где печатается счётчик, печатается и возраст,
    и оговорка про обнуление присутствует в выводе. Проверяется поведение
    вывода, а не конкретная формулировка одной строки.
    """
    monkeypatch.setattr(м, "ЮНИТЫ", tmp_path)
    реестр = tmp_path / "site-cells.json"
    реестр.write_text(json.dumps({"cells": [{
        "site_id": "x-01", "domain": "x.example", "status": "deployed",
        "runtime": {"unit": "нет-такого.service"}, "resources": {}}]}),
        encoding="utf-8")
    import io
    import contextlib
    буфер = io.StringIO()
    with contextlib.redirect_stdout(буфер):
        код = м.главное(["--registry", str(реестр)])
    assert код == 0
    вывод = буфер.getvalue()
    assert "возраст" in вывод
    assert "обнуляется" in вывод


def test_пустой_реестр_это_отказ_а_не_зелёный_итог(м, tmp_path):
    реестр = tmp_path / "пусто.json"
    реестр.write_text(json.dumps({"cells": []}), encoding="utf-8")
    assert м.главное(["--registry", str(реестр)]) == 2


def test_нечитаемый_реестр_это_отказ(м, tmp_path):
    assert м.главное(["--registry", str(tmp_path / "нет.json")]) == 2


def test_json_вывод_содержит_оба_источника(м, tmp_path, monkeypatch):
    monkeypatch.setattr(м, "ЮНИТЫ", tmp_path)
    _юнит(tmp_path, "е.service", "[Service]\nMemoryMax=512M\n")
    реестр = tmp_path / "site-cells.json"
    реестр.write_text(json.dumps({"cells": [{
        "site_id": "y-01", "domain": "y.example",
        "runtime": {"unit": "е.service"}, "resources": {"memory_max": "512M"}}]}),
        encoding="utf-8")
    import io
    import contextlib
    буфер = io.StringIO()
    with contextlib.redirect_stdout(буфер):
        assert м.главное(["--registry", str(реестр), "--json"]) == 0
    данные = json.loads(буфер.getvalue())
    запись = данные["ячейки"][0]
    # Объявленное и исполняемое — РАЗНЫЕ поля: иначе одно подтверждало бы
    # другое, и расхождение стало бы невидимым.
    assert запись["объявлено"] == {"memory_max": "512M"}
    assert запись["пределы"]["MemoryMax"] == "512M"
    assert "cgroup" in запись


def test_возраст_процесса_отказывает_честно(м):
    assert м.возраст_процесса(2 ** 30) == -1.0
    свой = м.возраст_процесса(1)
    assert свой == -1.0 or свой >= 0.0


def test_cgroup_несуществующего_юнита_не_прочитан(м):
    итог = м.cgroup_юнита("нет-такого-юнита-12345.service")
    assert итог["прочитан"] is False
    assert итог["max"] == м.НЕ_ИЗМЕРЕНО
