"""Сборщик патча полки постеров: он обязан отказываться, а не подгонять.

Повод, и ошибка моя. Патч был собран против `/srv/zonafilm-space/app/...`
(35 269 Б), а витрина обслуживает `current` → `releases/69f79d8502a9`
(41 602 Б). Ошибку нашла линия zona-01: `app` — старое дерево, между файлами
лежит T284, и репетиция на `app` к сайту не относилась. Поэтому путь берётся
через `current`, а деревья `app`, `app.prev` и `candidate` объявлены ловушками.

Отрицательные контроли, названные заранее:

* **неоднозначный якорь — отказ**, а не правка «по похожему месту». Подгонка по
  похожим местам уже дважды выпускала мёртвую правку;
* **правка, которая уже есть в установленном файле, — отказ**: иначе патч
  наложился бы вторым слоем;
* **не обслуживаемое дерево — отказ** с названием работающего пути.
"""
from __future__ import annotations

import importlib.util
import pathlib

import pytest

КОРЕНЬ = pathlib.Path(__file__).resolve().parents[2]
_с = importlib.util.spec_from_file_location(
    "prepare_shelf_posters_patch",
    КОРЕНЬ / "automation/local/prepare-shelf-posters-patch.py")
ИНСТР = importlib.util.module_from_spec(_с)
_с.loader.exec_module(ИНСТР)

ОБРАЗЕЦ = '''"""Проба."""


def спецификации(семейство):
    return []


def разрешить(ключ, снимок, семейство, *, предел=None, страница=1,
              на_странице=60):
    набор = []
    всего = len(набор)
    if предел is not None:
        кусок = набор[:предел]
        номер = 1
    else:
        номер = max(1, страница)
        кусок = набор[(номер - 1) * на_странице: номер * на_странице]
    return кусок, всего, номер
'''


def test_правка_вписывается_в_установленный_текст():
    стало = ИНСТР.переписать(ОБРАЗЕЦ)
    assert "def превью_с_постерами(" in стало
    assert 'по_оценке = (спец.sort_spec or {}).get("field") == "rating"' in стало
    assert "кусок = набор[:предел]\n        номер = 1" not in стало


def test_неоднозначный_якорь_это_отказ():
    with pytest.raises(SystemExit) as ош:
        ИНСТР.переписать(ОБРАЗЕЦ + "\n\n" + ОБРАЗЕЦ)
    assert "вместо одного" in str(ош.value)


def test_отсутствие_якоря_это_отказ():
    with pytest.raises(SystemExit):
        ИНСТР.переписать('"""Пустой файл."""\n')


def test_уже_исправленный_файл_это_отказ():
    стало = ИНСТР.переписать(ОБРАЗЕЦ)
    with pytest.raises(SystemExit) as ош:
        ИНСТР.переписать(стало)
    assert "УЖЕ есть" in str(ош.value)


def test_необслуживаемое_дерево_отвергается(capsys, tmp_path):
    ловушка = tmp_path / "srv" / "zonafilm-space" / "app" / "src"
    ловушка.mkdir(parents=True)
    файл = ловушка / "collection_contract.py"
    файл.write_text(ОБРАЗЕЦ, encoding="utf-8")
    код = ИНСТР.главное(["--source", str(файл)])
    assert код == 2
    вывод = capsys.readouterr().out
    assert "не обслуживаемое витриной дерево" in вывод
    assert "current" in вывод


def test_работающий_путь_назван_через_current():
    assert str(ИНСТР.УСТАНОВЛЕНО) == \
        "/srv/zonafilm-space/current/src/collection_contract.py"
    assert "/app/" in ИНСТР.ЛОВУШКИ
    текст = " ".join(
        pathlib.Path(ИНСТР.__file__).read_text(encoding="utf-8").split())
    assert "41 602" in текст and "35 269" in текст, \
        "основание выбора пути должно быть названо числами"
