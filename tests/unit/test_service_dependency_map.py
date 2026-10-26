"""Измеритель зависимостей служб: честность разбора, а не красота вывода.

MOD-198 требует перед переносом установить фактические зависимости каждой
службы. Опасность здесь одна и конкретная: разбор, который чего-то не умеет,
печатает «файлов кода: 1» вместо отказа — и перенос по такому набору даёт
службу, которая запускается и молча делает не то. Поэтому проверяются ровно
те четыре вида точек входа, которые встретились в системе, и каждая была
сначала разобрана неверно.
"""
from __future__ import annotations

import importlib.util
import json
import pathlib

import pytest

КОРЕНЬ = pathlib.Path(__file__).resolve().parents[2]
_сп = importlib.util.spec_from_file_location(
    "service_dependency_map", КОРЕНЬ / "automation" / "local" / "service-dependency-map.py")
инс = importlib.util.module_from_spec(_сп)
_сп.loader.exec_module(инс)


def test_многострочный_execstart_склеивается():
    """systemd разрешает перенос обратным слешем, и реальные юниты им пользуются.

    Первая редакция читала только первую строку и теряла `-m пакет.модуль`,
    то есть саму точку входа.
    """
    текст = ("[Service]\n"
             "ExecStart=/path/.venv/bin/python \\\n"
             "  -m seo_engine.content_operator.report_server \\\n"
             "  --port 8231\n")
    значение = инс._поле(текст, "ExecStart")
    assert "-m seo_engine.content_operator.report_server" in значение
    assert "--port 8231" in значение


def test_интерпретатор_не_считается_точкой_входа(tmp_path):
    """Иначе точкой входа оказывается .venv/bin/python, и это бесполезно."""
    (tmp_path / ".venv" / "bin").mkdir(parents=True)
    (tmp_path / ".venv" / "bin" / "python").write_text("", encoding="utf-8")
    (tmp_path / "automation").mkdir()
    сценарий = tmp_path / "automation" / "дело.sh"
    сценарий.write_text("#!/bin/bash\n", encoding="utf-8")
    юнит = {"ExecStart": f"{tmp_path}/.venv/bin/python {tmp_path}/automation/дело.sh"}
    вход, как = инс.точка_входа(юнит, tmp_path)
    assert вход is not None and вход.name == "дело.sh", как


def test_инлайн_c_разбирается(tmp_path):
    """community-ratings-monitor запускается через python -c с импортом."""
    (tmp_path / "factory" / "community").mkdir(parents=True)
    цель = tmp_path / "factory" / "community" / "monitor_once.py"
    цель.write_text("def main():\n    return 0\n", encoding="utf-8")
    юнит = {"ExecStart": "/usr/bin/python3 -c 'from factory.community.monitor_once import main; "
                         "raise SystemExit(main())'"}
    вход, как = инс.точка_входа(юнит, tmp_path)
    assert вход == цель and "-c" in как


def test_обёртка_вне_дерева_с_pythonpath_раскрывается(tmp_path):
    """Худший вид привязки: юнит дерева не называет, оно спрятано в PYTHONPATH."""
    дерево = tmp_path / "wt-дерево"
    (дерево / "factory" / "community").mkdir(parents=True)
    цель = дерево / "factory" / "community" / "http_gateway.py"
    цель.write_text("def main():\n    return 0\n", encoding="utf-8")
    обёртка = tmp_path / "обёртка"
    обёртка.write_text(
        f"#!/bin/bash\nexport PYTHONPATH={дерево}\n"
        "exec /usr/bin/python3 -c 'from factory.community.http_gateway import main; "
        "raise SystemExit(main())'\n", encoding="utf-8")
    вход, как = инс.точка_входа({"ExecStart": str(обёртка)}, дерево)
    assert вход == цель, как
    assert "PYTHONPATH" in как


def test_сценарий_оболочки_тянет_то_что_зовёт(tmp_path):
    """«Файлов кода: 1» у обёртки — это недоразбор, а не факт."""
    (tmp_path / "automation" / "host").mkdir(parents=True)
    (tmp_path / "seo_operator").mkdir()
    модуль = tmp_path / "seo_operator" / "cli.py"
    модуль.write_text("import json\n", encoding="utf-8")
    сценарий = tmp_path / "automation" / "host" / "дело.sh"
    сценарий.write_text("#!/bin/bash\npython3 -m seo_operator.cli regular\n", encoding="utf-8")
    файлы = инс.зависимости_оболочки(сценарий, tmp_path)
    assert модуль in файлы and сценарий in файлы


def test_нулевые_байты_не_ломают_разбор(tmp_path):
    """В грязном дереве бывает частично записанный файл; это ValueError."""
    (tmp_path / "pkg").mkdir()
    плохой = tmp_path / "pkg" / "битый.py"
    плохой.write_bytes(b"import json\x00\n")
    assert инс.импорты(плохой, tmp_path) == {плохой}


def test_карта_покрывает_все_работающие_службы():
    """Замер по системе: ни одной службы без разобранной точки входа.

    Числа измеренные (26.10): 18 работающих служб из пяти рабочих копий, и
    зависимость от незакоммиченного — ровно у двух.
    """
    запись = КОРЕНЬ / "artifacts" / "evidence" / "service-dependency-map-20261026.json"
    д = json.loads(запись.read_text(encoding="utf-8"))
    assert д["служб"] == 18
    без_входа = [з["служба"] for з in д["службы"] if not з["точка_входа"]]
    assert not без_входа, f"без точки входа: {без_входа}"
    # 26.10 около 10:34Z линия аудита закоммитила три файла (ff8d678), и
    # зависимость от незакоммиченного исчезла у обеих своих служб. Проверка
    # следит за СВОЙСТВОМ, а не за прежним числом: как только какая-то служба
    # снова начнёт зависеть от незакоммиченного, она назовёт её по имени —
    # это и есть сигнал, что переносить её рано.
    грязные = {з["служба"]: з["нужны_незакоммиченные"] for з in д["службы"]
               if з["нужны_незакоммиченные"]}
    assert not грязные, (
        "служба снова зависит от незакоммиченного — перенос такой службы "
        f"откатил бы её поведение на неизвестную величину: {грязные}")
    # Агентные службы: правила каталога запуска — часть выпуска, и их нельзя
    # потерять при переносе.
    агентные = {з["служба"] for з in д["службы"]
                if (з.get("неимпортные") or {}).get("агентная")}
    assert агентные == {"editor-run.service", "seo-tech-run.service"}, агентные
    for з in д["службы"]:
        ни = з.get("неимпортные") or {}
        if ни.get("агентная"):
            assert "CLAUDE.md" in (ни.get("правила_агента") or []), з["служба"]
