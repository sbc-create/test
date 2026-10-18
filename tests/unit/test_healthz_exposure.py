"""Публичный /healthz: что он рассказывает об устройстве машины.

Повод. Путь `/healthz` сознательно публичен — он нужен наблюдению, и решения
D150, D166, D187 закрывают его от ИНДЕКСАЦИИ, а не от доступа. Но «закрыт от
индексации» и «ограничен по содержимому» — разные вещи, и второе не
измерялось. Замер 12.10: девять витрин из семнадцати отдают наружу `pid`,
`process_start_time`, `runtime_path` и `runtime_sha256`, а остальные восемь —
ровно `{"ok": true}`. То есть минимальная форма монитору достаточна, и это
доказано восьмью живыми доменами, а не рассуждением.

Два свойства инструмента закрепляются здесь, потому что без них отчёт сам
станет проблемой:

* он печатает ИМЕНА полей, а не значения: отчёт о раскрытии не должен
  раскрывать путь и хеш;
* он не выносит вердикт «уязвимость»: публичность пути решена, а состав ответа
  может быть сознательным. Вопрос, на который он отвечает, — сколько витрин
  показывают устройство машины.

Сеть не используется: `ответ` подменяется.
"""
from __future__ import annotations

import importlib.util
import io
import json
from contextlib import redirect_stdout
from pathlib import Path

import pytest

КОРЕНЬ = Path(__file__).resolve().parents[2]
ИСТОЧНИК = КОРЕНЬ / "automation" / "local" / "healthz-exposure.py"

ПОДРОБНЫЙ = json.dumps({
    "ok": True, "pid": 290479,
    "process_start_time": "2026-10-11T22:47:17Z",
    "runtime_path": "/srv/animedia-icu/releases/dccb53b08d0d/src/x.py",
    "runtime_sha256": "3cfc181cb84426812ec95463fc79bd1a01",
    "build_id": "dccb53b08d0d-animedia-01"})
МИНИМАЛЬНЫЙ = '{"ok":true}'


def _модуль():
    спец = importlib.util.spec_from_file_location("healthz_exposure", ИСТОЧНИК)
    м = importlib.util.module_from_spec(спец)
    спец.loader.exec_module(м)
    return м


@pytest.fixture(scope="module")
def м():
    return _модуль()


def _подменить(м, monkeypatch, ответы):
    # Третий параметр — служебный путь: инструмент умеет не только /healthz
    # (ключ `--path` повторяется), и подделка обязана принимать его тоже.
    def поддельный(домен, таймаут, путь="/healthz"):
        assert домен in ответы, f"тест не описал домен {домен}"
        return ответы[домен]
    monkeypatch.setattr(м, "ответ", поддельный)


def test_поля_про_устройство_названы(м):
    имена, разобрался, разбор = м.поля(ПОДРОБНЫЙ)
    assert разобрался is True
    # Решает ФУНКЦИЯ, а не постоянная. Прежняя редакция проверки читала
    # закрытый перечень имён `ОПИСЫВАЮТ_УСТРОЙСТВО` напрямую — то есть
    # внутренность инструмента, — и сломалась, когда признак стал видовым.
    # Заодно это и была причина пятикратной недооценки: перечень из десяти
    # имён находил четыре поля из двадцати двух.
    # Признак судит по имени И ПО ЗНАЧЕНИЮ: имя выбирает тот, кто поле
    # добавил, и перечень видов имени терял поле с путём внутри, названное
    # иначе. Измерено 2026-10-18 на animeg0.site: по имени 10 полей, по
    # смыслу 15; расхождение закрылось признаком по значению.
    устройство = [и for и in имена if м.раскрывает(и, разбор.get(и))]
    assert set(устройство) == {"pid", "process_start_time", "runtime_path",
                               "runtime_sha256", "build_id"}, устройство
    # `ok` раскрытием не считается: это ответ о живости, ради которого путь и
    # существует.
    assert "ok" not in устройство


def test_минимальный_ответ_устройства_не_раскрывает(м):
    имена, разобрался, разбор = м.поля(МИНИМАЛЬНЫЙ)
    assert разобрался is True
    assert имена == ["ok"]
    assert [и for и in имена if и in м.ОПИСЫВАЮТ_УСТРОЙСТВО] == []


def test_значения_путей_и_хешей_в_вывод_не_идут(м, monkeypatch):
    """Отчёт о раскрытии не должен сам становиться способом раскрытия."""
    _подменить(м, monkeypatch, {"x.example": ("200", ПОДРОБНЫЙ)})
    буфер = io.StringIO()
    with redirect_stdout(буфер):
        assert м.главное(["--domain", "x.example"]) == 0
    вывод = буфер.getvalue()
    assert "runtime_path" in вывод, "имя поля называется"
    assert "/srv/animedia-icu/releases" not in вывод, "значение пути — нет"
    assert "3cfc181cb844" not in вывод, "значение хеша — нет"
    assert "290479" not in вывод, "номер процесса — нет"


def test_json_вывод_тоже_без_значений(м, monkeypatch):
    _подменить(м, monkeypatch, {"x.example": ("200", ПОДРОБНЫЙ)})
    буфер = io.StringIO()
    with redirect_stdout(буфер):
        м.главное(["--domain", "x.example", "--json"])
    текст = буфер.getvalue()
    данные = json.loads(текст)
    assert данные[0]["про_устройство"]
    assert "/srv/" not in текст
    assert "3cfc181cb844" not in текст


def test_счёт_различает_подробные_и_минимальные(м, monkeypatch):
    _подменить(м, monkeypatch, {
        "много.example": ("200", ПОДРОБНЫЙ),
        "мало.example": ("200", МИНИМАЛЬНЫЙ),
    })
    буфер = io.StringIO()
    with redirect_stdout(буфер):
        м.главное(["--domain", "много.example", "--domain", "мало.example"])
    вывод = буфер.getvalue()
    assert "ответили 200: 2 из 2" in вывод
    assert "показывают устройство машины: 1" in вывод


def test_вердикт_не_выносится(м, monkeypatch):
    """Публичность пути решена решениями; инструмент её не оспаривает."""
    _подменить(м, monkeypatch, {"x.example": ("200", ПОДРОБНЫЙ)})
    буфер = io.StringIO()
    with redirect_stdout(буфер):
        код = м.главное(["--domain", "x.example"])
    вывод = буфер.getvalue()
    assert код == 0, "раскрытие состава — не отказ проверки"
    assert "Вердикта инструмент не выносит" in вывод
    assert "D150" in вывод and "D187" in вывод


def test_не_json_ответ_не_считается_раскрытием(м, monkeypatch):
    _подменить(м, monkeypatch, {"x.example": ("200", "OK")})
    имена, разобрался, разбор = м.поля("OK")
    assert (имена, разобрался) == ([], False)
    буфер = io.StringIO()
    with redirect_stdout(буфер):
        м.главное(["--domain", "x.example"])
    assert "показывают устройство машины: 0" in буфер.getvalue()


def test_json_массив_не_считается_набором_полей(м):
    """Список верхнего уровня полями не является — иначе счёт врёт."""
    assert м.поля('[{"runtime_path":"/srv/x"}]') == ([], False, {})


def test_домен_без_dns_не_путается_с_молчанием(м, monkeypatch):
    _подменить(м, monkeypatch, {"нет.example": ("dns", "")})
    буфер = io.StringIO()
    with redirect_stdout(буфер):
        м.главное(["--domain", "нет.example"])
    вывод = буфер.getvalue()
    assert "dns" in вывод
    assert "ответили 200: 0 из 1" in вывод


def test_испытательные_имена_не_опрашиваются(м, tmp_path):
    реестр = tmp_path / "site-cells.json"
    реестр.write_text(json.dumps({"cells": [
        {"site_id": "a", "domain": "site-a.localhost"},
        {"site_id": "b", "domain": "живой.example.com"}]}), encoding="utf-8")
    assert м.домены(реестр) == ["живой.example.com"]


def test_нечитаемый_реестр_это_отказ(м, tmp_path):
    assert м.главное(["--registry", str(tmp_path / "нет.json")]) == 2
