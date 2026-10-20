"""Откуда пробел постеров: поставщик, ввоз или сопоставление.

Повод: линия SEO передала 14 карточек `lordserial33.biz` с заглушкой вместо
постера и потребовала первопричину с файлом, строкой или выводом. Версий ровно
три, и инструмент отвечает на все три числами.

Измерено 20.10 на lords-02: у поставщика без `poster_url` 841 запись из 67 685,
в доставленном каталоге без `poster` — тоже 841. Числа совпадают, значит ввоз не
теряет ничего; 836 из 841 имеют внешние идентификаторы, значит сопоставление на
месте. Остаётся ответ поставщика.

Отрицательные контроли, названные заранее:

* если в каталоге без постера БОЛЬШЕ, чем в ответе поставщика, проход обязан
  сказать «ВВОЗ ТЕРЯЕТ» — иначе он не умеет находить вторую версию вовсе;
* если меньше — это наследование от прежнего снимка, и это тоже называется;
* поле с ОДНИМ значением на всю совокупность объявляется не несущим вывода.
  Ровно так устроен `licensed`: `False` у всех 67 685 записей, и вывод по нему
  был бы выводом по признаку, который не умеет отвечать иначе;
* если ни одно поле не различает группы, механизм объявляется НЕ установленным,
  а не додумывается.
"""
from __future__ import annotations

import importlib.util
import json
import pathlib

КОРЕНЬ = pathlib.Path(__file__).resolve().parents[2]
_с = importlib.util.spec_from_file_location(
    "poster_source_gap", КОРЕНЬ / "automation/local/poster-source-gap.py")
ИНСТР = importlib.util.module_from_spec(_с)
_с.loader.exec_module(ИНСТР)


def _запись(н: int, *, постер: bool, год: bool = True,
            оценка: bool = True, внешние: bool = True) -> dict:
    return {
        "external_id": f"id-{н}",
        "name": f"Работа {н}",
        "poster_url": f"/p{н}.jpg" if постер else None,
        "year": 2020 if год else None,
        "kinopoisk_rating": 7.5 if оценка else None,
        "external_ids": {"kp": str(н)} if внешние else {},
        "licensed": False,
    }


def _доставлено(з: dict) -> dict:
    return {"slug": з["external_id"], "poster": з["poster_url"] or None}


# --- три версии ----------------------------------------------------------------

def test_числа_совпали_значит_ввоз_не_теряет():
    """Живой случай: 841 у поставщика и 841 в каталоге."""
    поставщик = ([_запись(н, постер=True) for н in range(90)]
                 + [_запись(100 + н, постер=False) for н in range(10)])
    итог = ИНСТР.разобрать(поставщик, [_доставлено(з) for з in поставщик])
    assert итог["поставщик_без_постера"] == 10
    assert итог["доставлено_без_постера"] == 10
    assert итог["теряет_ввоз"] == 0


def test_ввоз_теряющий_постеры_называется(capsys, tmp_path):
    """Отрицательный контроль: вторую версию проход обязан уметь находить."""
    поставщик = [_запись(н, постер=True) for н in range(10)]
    доставлено = [{"slug": з["external_id"], "poster": None}
                  for з in поставщик]
    итог = ИНСТР.разобрать(поставщик, доставлено)
    assert итог["теряет_ввоз"] == 10

    п = tmp_path / "p.json"
    д = tmp_path / "d.json"
    п.write_text(json.dumps({"items": поставщик}), encoding="utf-8")
    д.write_text(json.dumps({"items": доставлено}), encoding="utf-8")
    ИНСТР.главное(["--provider", str(п), "--delivered", str(д)])
    assert "ВВОЗ ТЕРЯЕТ 10" in capsys.readouterr().out


def test_наследование_тоже_называется(capsys, tmp_path):
    поставщик = [_запись(н, постер=False) for н in range(10)]
    доставлено = [{"slug": з["external_id"], "poster": "/был.jpg"}
                  for з in поставщик]
    п, д = tmp_path / "p.json", tmp_path / "d.json"
    п.write_text(json.dumps({"items": поставщик}), encoding="utf-8")
    д.write_text(json.dumps({"items": доставлено}), encoding="utf-8")
    ИНСТР.главное(["--provider", str(п), "--delivered", str(д)])
    assert "ввоз ДОБАВИЛ 10" in capsys.readouterr().out


def test_сопоставление_считается_по_внешним_идентификаторам():
    поставщик = ([_запись(н, постер=False, внешние=True) for н in range(8)]
                 + [_запись(50 + н, постер=False, внешние=False)
                    for н in range(2)])
    итог = ИНСТР.разобрать(поставщик, [_доставлено(з) for з in поставщик])
    assert итог["без_постера_с_внешними_ид"] == 8


# --- механизм ------------------------------------------------------------------

def test_различающее_поле_находится():
    """Живой случай: year непусто у 62 % без постера против 96 % с ним."""
    поставщик = ([_запись(н, постер=True, год=True) for н in range(50)]
                 + [_запись(100 + н, постер=False, год=False)
                    for н in range(50)])
    итог = ИНСТР.разобрать(поставщик, [_доставлено(з) for з in поставщик])
    поля = [р["поле"] for р in итог["различающие_поля"]]
    assert "year" in поля, итог["различающие_поля"]


def test_слабое_различие_различающим_не_объявляется():
    """Порог назван числом: 20 пунктов — ещё не признак."""
    поставщик = ([_запись(н, постер=True, год=True) for н in range(50)]
                 + [_запись(100 + н, постер=False, год=(н < 40))
                    for н in range(50)])
    итог = ИНСТР.разобрать(поставщик, [_доставлено(з) for з in поставщик])
    assert "year" not in [р["поле"] for р in итог["различающие_поля"]]


def test_механизм_не_додумывается(capsys, tmp_path):
    """Отрицательный контроль: ни одно поле не различает — так и сказано."""
    поставщик = ([_запись(н, постер=True) for н in range(50)]
                 + [_запись(100 + н, постер=False) for н in range(50)])
    п, д = tmp_path / "p.json", tmp_path / "d.json"
    п.write_text(json.dumps({"items": поставщик}), encoding="utf-8")
    д.write_text(json.dumps({"items": [_доставлено(з) for з in поставщик]}),
                 encoding="utf-8")
    ИНСТР.главное(["--provider", str(п), "--delivered", str(д)])
    assert "механизм НЕ установлен" in capsys.readouterr().out


def test_поле_с_одним_значением_объявляется_непригодным(capsys, tmp_path):
    """Так устроен `licensed`: False у всех 67 685 записей каталога."""
    поставщик = ([_запись(н, постер=True) for н in range(20)]
                 + [_запись(100 + н, постер=False) for н in range(5)])
    п, д = tmp_path / "p.json", tmp_path / "d.json"
    п.write_text(json.dumps({"items": поставщик}), encoding="utf-8")
    д.write_text(json.dumps({"items": [_доставлено(з) for з in поставщик]}),
                 encoding="utf-8")
    ИНСТР.главное(["--provider", str(п), "--delivered", str(д)])
    вывод = capsys.readouterr().out
    assert "licensed" in вывод
    assert "не умеет отвечать иначе" in вывод


# --- пределы -------------------------------------------------------------------

def test_нет_файла_это_код_два(capsys, tmp_path):
    код = ИНСТР.главное(["--provider", str(tmp_path / "нет.json"),
                         "--delivered", str(tmp_path / "нет2.json")])
    assert код == 2
    assert "НЕ ИЗМЕРЕНО" in capsys.readouterr().out


def test_файл_без_записей_это_код_два(capsys, tmp_path):
    п, д = tmp_path / "p.json", tmp_path / "d.json"
    п.write_text(json.dumps({"items": []}), encoding="utf-8")
    д.write_text(json.dumps({"items": []}), encoding="utf-8")
    assert ИНСТР.главное(["--provider", str(п), "--delivered", str(д)]) == 2
    assert "нет списка записей" in capsys.readouterr().out


def test_порог_различия_объявлен_числом():
    assert ИНСТР.РАЗЛИЧАЕТ_ПУНКТОВ == 25
    текст = " ".join(
        pathlib.Path(ИНСТР.__file__).read_text(encoding="utf-8").split())
    assert "1.5 против 38.8" in текст, "основание порога должно быть названо"
