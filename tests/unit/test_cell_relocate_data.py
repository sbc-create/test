"""Перенос каталога данных в реестре разрешён ТОЛЬКО по измерению юнита.

Эта операция закрывает незаметно пропускаемый шаг переезда витрины в свою
ячейку: включили новый юнит, а реестру не сказали. Тогда реестр описывает
намерение, производитель кладёт снимок по `data_dir`, витрина читает другой
каталог, и ошибки нет нигде — сайт просто перестаёт пополняться.

Измерено 2026-10-08 на zona-02 (zonafilm.cc): издатель положил 60 699 позиций
в `/srv/lords/.frontend/sites/zona-02/data`, а включённый юнит запускает
витрину с `--data-dir /srv/zonafilm-cc/data`, где лежал снимок от 2026-09-28 на
53 908 позиций. Разница — 6 791 произведение.

Поэтому тесты проверяют не «записалось», а ОТКАЗЫ: без включённого юнита, без
`--data-dir` в ExecStart и при расхождении измеренного пути с объявленным
операция обязана отказать. Иначе она станет вторым способом соврать о
размещении, только автоматическим.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from factory.cell import runtime as rt

ЮНИТ = "nova-пример.service"


def реестр(tmp_path: Path, *, data_dir: str, после: str | None,
           unit: str | None = ЮНИТ) -> Path:
    блок = {"unit": unit, "port": 9123, "account": "пример",
            "data_dir": data_dir, "reload": "mtime", "managed_by": "cell"}
    if после is not None:
        блок["data_dir_after_relocation"] = после
    путь = tmp_path / "site-cells.json"
    путь.write_text(json.dumps({
        "schema_version": "1.0",
        "cells": [{
            "site_id": "пример-02", "domain": "пример.test",
            "status": "staged",
            "repo": {"kind": "remote", "path": "var/site-repos/пример",
                     "remote": "https://example.invalid/пример"},
            "runtime": блок,
        }],
    }, ensure_ascii=False), encoding="utf-8")
    return путь


def юниты(tmp_path: Path, *, execstart: str,
          включён: bool = True) -> tuple[Path, Path]:
    корень = tmp_path / "systemd"
    включённые = корень / "multi-user.target.wants"
    включённые.mkdir(parents=True)
    (корень / ЮНИТ).write_text(
        "[Service]\n" + execstart + "\n", encoding="utf-8")
    if включён:
        (включённые / ЮНИТ).write_text("ссылка\n", encoding="utf-8")
    return корень, включённые


def вызвать(tmp_path: Path, *, data_dir: str, после: str | None,
            execstart: str, включён: bool = True, dry_run: bool = False,
            unit: str | None = ЮНИТ) -> dict:
    р = реестр(tmp_path, data_dir=data_dir, после=после, unit=unit)
    корень, включённые = юниты(tmp_path, execstart=execstart, включён=включён)
    return rt.завершить_переезд("пример-02", dry_run=dry_run, path=р,
                                корень_юнитов=корень,
                                корень_включённых=включённые)


def test_переезд_записывается_когда_юнит_подтверждает_путь(tmp_path):
    итог = вызвать(
        tmp_path, data_dir="/srv/старый/data", после="/srv/новый/data",
        execstart="ExecStart=/usr/bin/python3 run.py --port 9123 "
                  "--data-dir /srv/новый/data")
    assert итог["status"] == "relocated", итог
    assert итог["data_dir_in_unit"] == "/srv/новый/data"
    записано = json.loads((tmp_path / "site-cells.json").read_text(encoding="utf-8"))
    блок = записано["cells"][0]["runtime"]
    assert блок["data_dir"] == "/srv/новый/data"
    # История не теряется, а намерение больше не висит рядом с фактом.
    assert блок["data_dir_before_relocation"] == "/srv/старый/data"
    assert "data_dir_after_relocation" not in блок
    assert "ExecStart" in блок["data_dir_note"]


def test_невключённый_юнит_переезда_не_доказывает(tmp_path):
    итог = вызвать(
        tmp_path, data_dir="/srv/старый/data", после="/srv/новый/data",
        execstart="ExecStart=/usr/bin/python3 run.py --data-dir /srv/новый/data",
        включён=False)
    assert итог["status"] == "refused", итог
    assert "не включён" in итог["reason"]
    блок = json.loads((tmp_path / "site-cells.json")
                      .read_text(encoding="utf-8"))["cells"][0]["runtime"]
    assert блок["data_dir"] == "/srv/старый/data"


def test_расхождение_юнита_с_объявленным_путём_отвергается(tmp_path):
    """Самый опасный случай: объявили одно, витрина запущена с другим."""
    итог = вызвать(
        tmp_path, data_dir="/srv/старый/data", после="/srv/новый/data",
        execstart="ExecStart=/usr/bin/python3 run.py --data-dir /srv/третий/data")
    assert итог["status"] == "refused", итог
    assert "/srv/третий/data" in итог["reason"]
    assert "/srv/новый/data" in итог["reason"]
    assert "факт, а не намерение" in итог["reason"]
    блок = json.loads((tmp_path / "site-cells.json")
                      .read_text(encoding="utf-8"))["cells"][0]["runtime"]
    assert блок["data_dir"] == "/srv/старый/data"


def test_юнит_без_data_dir_не_называет_каталог(tmp_path):
    итог = вызвать(
        tmp_path, data_dir="/srv/старый/data", после="/srv/новый/data",
        execstart="ExecStart=/usr/bin/python3 run.py --port 9123")
    assert итог["status"] == "refused", итог
    assert "--data-dir" in итог["reason"]


def test_без_объявленного_переезда_делать_нечего(tmp_path):
    итог = вызвать(
        tmp_path, data_dir="/srv/старый/data", после=None,
        execstart="ExecStart=/usr/bin/python3 run.py --data-dir /srv/старый/data")
    assert итог["status"] == "nothing-to-do", итог


def test_повторный_вызов_ничего_не_меняет(tmp_path):
    итог = вызвать(
        tmp_path, data_dir="/srv/новый/data", после="/srv/новый/data",
        execstart="ExecStart=/usr/bin/python3 run.py --data-dir /srv/новый/data")
    assert итог["status"] == "nothing-to-do", итог


def test_сухой_прогон_в_реестр_не_пишет(tmp_path):
    р = реестр(tmp_path, data_dir="/srv/старый/data", после="/srv/новый/data")
    корень, включённые = юниты(
        tmp_path,
        execstart="ExecStart=/usr/bin/python3 run.py --data-dir /srv/новый/data")
    итог = rt.завершить_переезд("пример-02", dry_run=True, path=р,
                                корень_юнитов=корень,
                                корень_включённых=включённые)
    assert итог["status"] == "dry-run", итог
    блок = json.loads(р.read_text(encoding="utf-8"))["cells"][0]["runtime"]
    assert блок["data_dir"] == "/srv/старый/data"
    assert блок["data_dir_after_relocation"] == "/srv/новый/data"


@pytest.mark.parametrize("строка", [
    "ExecStart=/usr/bin/python3 run.py --data-dir /srv/новый/data",
    "ExecStart=/usr/bin/python3 run.py --data-dir=/srv/новый/data",
    "ExecStart=/usr/bin/python3 run.py --port 9123 --data-dir /srv/новый/data "
    "--verbose",
])
def test_обе_формы_аргумента_читаются(tmp_path, строка):
    корень, _ = юниты(tmp_path, execstart=строка)
    assert rt.каталог_данных_юнита(ЮНИТ, корень=корень) == "/srv/новый/data"
