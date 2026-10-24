"""Опись редакционных материалов и сравнение с живой страницей.

Два повода, оба измеренные 24.10.

1. `content_hash` в записи реестра НЕ является хешем текста: у 148 записей
   animedia.space с разными телами он одинаков, на весь реестр 28 значений при
   833 телах. Счёт уникальных текстов по этому полю дал бы «1 текст на домен»
   вместо 148 — и вывод «все описания домена это копии одного».

2. Сравнение с живой страницей объявило РАСХОЖДЕНИЕ на странице, которая
   отдала HTTP 503 «overloaded, retry later»: загрузчик без ключа -f
   возвращает 0 и на 503, а тело ошибки инструмент принял за текст страницы.
   Отрицательный вывод при невозможности измерить хуже отсутствия вывода.

Сеть здесь не нужна: загрузчик подменяется.
"""
from __future__ import annotations

import importlib.util
import json
import pathlib

КОРЕНЬ = pathlib.Path(__file__).resolve().parents[2]


def _модуль(имя: str, файл: str):
    п = КОРЕНЬ / "automation" / "local" / файл
    с = importlib.util.spec_from_file_location(имя, п)
    м = importlib.util.module_from_spec(с)
    assert с.loader is not None
    с.loader.exec_module(м)
    return м


ОПИСЬ = _модуль("editorial_inventory", "editorial-inventory.py")
СРАВНЕНИЕ = _модуль("editorial_live_compare", "editorial-live-compare.py")


def _реестр(tmp_path: pathlib.Path, записи: list[dict]) -> pathlib.Path:
    ф = tmp_path / "registry.json"
    ф.write_text(json.dumps({"version": 1, "count": len(записи),
                             "items": записи}, ensure_ascii=False),
                 encoding="utf-8")
    return ф


def _запись(**kw) -> dict:
    о = {"content_id": "c1", "target_site": "d.site", "title_id": "t",
         "headline": "З", "status": "READY_VERIFIED", "body": "текст",
         "canonical_url": "https://d.site/title/t", "content_hash": "одинаковый",
         "provenance": {}, "author": "", "published_at": "", "updated_at": "",
         "draft_created_at": "", "authorship_data_gap": False,
         "reject_reason": "", "content_type": "TITLE_DESCRIPTION"}
    о.update(kw)
    return о


# --- опись ------------------------------------------------------------------

def test_уникальность_считается_по_тексту_а_не_по_content_hash():
    """Главный повод: одинаковый content_hash при разных телах."""
    а = ОПИСЬ.отпечаток("первый текст")
    б = ОПИСЬ.отпечаток("второй текст")
    assert а != б, "разные тексты обязаны давать разные отпечатки"


def test_пробелы_не_считаются_различием_текста():
    assert ОПИСЬ.отпечаток("а  б\n в") == ОПИСЬ.отпечаток("а б в")


def test_пустое_тело_текстом_не_считается():
    assert ОПИСЬ.с_текстом([_запись(body="   ")]) == []
    assert ОПИСЬ.с_текстом([_запись(body="  есть  ")]) != []


def test_свод_различает_копии_и_разные_тексты(capsys, tmp_path):
    """Два тела одинаковы, третье своё: это 2 уникальных на 3 записи."""
    зп = [_запись(content_id="a", body="один и тот же"),
          _запись(content_id="b", body="один  и  тот  же"),
          _запись(content_id="c", body="другой")]
    ОПИСЬ.свод(зп)
    из = capsys.readouterr().out
    assert "уникальных текстов 2" in из, из
    assert "повторов текста: 1" in из, из


def test_отсутствующий_автор_не_выдумывается():
    """Пустое поле — пробел в данных, а не «Qwen»."""
    assert ОПИСЬ.авторство(_запись(author="")) == "не записано"
    assert "пробел" in ОПИСЬ.авторство(_запись(author="",
                                               authorship_data_gap=True))
    assert ОПИСЬ.авторство(_запись(author="Редакция")) == "Редакция"


def test_недоступное_хранилище_не_выдаётся_за_отсутствие_текста(monkeypatch,
                                                               tmp_path):
    """«Нет доступа» и «нет текста» — разные ответы."""
    monkeypatch.setitem(ОПИСЬ.ХРАНИЛИЩА, "пробное", tmp_path / "нет-такого")
    состояния = dict((и, с) for и, _, с in ОПИСЬ.доступность())
    assert состояния["пробное"] == "ОТСУТСТВУЕТ"


def test_опись_несёт_путь_и_ключ_записи(tmp_path):
    """По описи материал должны открыть, а не только посчитать."""
    ф = tmp_path / "опись.tsv"
    ОПИСЬ.опись([_запись(content_id="ключ-1")], ф)
    строки = ф.read_text(encoding="utf-8").splitlines()
    assert "хранилище и ключ записи" in строки[0]
    assert "content_id=ключ-1" in строки[1]
    assert "https://d.site/title/t" in строки[1]


def test_нет_реестра_это_не_измерено_а_не_ноль(capsys, tmp_path):
    код = ОПИСЬ.главное(["--summary", "--registry", str(tmp_path / "нет.json")])
    assert код == 2
    assert "НЕ ИЗМЕРЕНО" in capsys.readouterr().out


def test_окно_суток_отделяет_созданное_от_накопленного(capsys, tmp_path):
    import datetime
    сейчас = datetime.datetime.now(datetime.timezone.utc)
    свежо = (сейчас - datetime.timedelta(hours=2)).strftime("%Y-%m-%dT%H:%M:%SZ")
    давно = "2026-09-01T00:00:00Z"
    зп = [_запись(content_id="новая", draft_created_at=свежо),
          _запись(content_id="старая", draft_created_at=давно)]
    ОПИСЬ.окно(зп, 24)
    из = capsys.readouterr().out
    assert "черновик создан : 1" in из, из
    assert "записей 2" in из, из


# --- сравнение с живой страницей -------------------------------------------

def test_не_двести_это_не_измерено_а_не_расхождение(monkeypatch):
    """Ровно та ошибка: 503 принимался за текст страницы.

    Тело ответа 503 не содержит сохранённого текста, поэтому прежняя редакция
    печатала РАСХОДИТСЯ — отрицательный вывод там, где измерения не было.
    """
    class Ответ:
        returncode = 0
        stdout = "503 Service Unavailable: overloaded, retry later@@КОД:503"
        stderr = ""

    monkeypatch.setattr(СРАВНЕНИЕ.subprocess, "run",
                        lambda *a, **k: Ответ())
    итог = СРАВНЕНИЕ.сравнить_запись(_запись(body="достаточно длинное"
                                             " предложение для сравнения фраз."),
                                     5)
    assert итог["исход"] == "НЕ ИЗМЕРЕНО", итог
    assert "503" in итог["почему"], итог


def test_двести_с_текстом_даёт_совпадение(monkeypatch):
    """Положительный контроль подмены: инструмент обязан уметь совпасть."""
    тело = "Достаточно длинное предложение для сравнения фраз между собой."

    class Ответ:
        returncode = 0
        stdout = f"<html><body><p>{тело}</p></body></html>@@КОД:200"
        stderr = ""

    monkeypatch.setattr(СРАВНЕНИЕ.subprocess, "run", lambda *a, **k: Ответ())
    итог = СРАВНЕНИЕ.сравнить_запись(_запись(body=тело), 5)
    assert итог["исход"] == "СОВПАЛ", итог
    assert итог["доля"] == 1.0


def test_двести_без_текста_даёт_расхождение(monkeypatch):
    class Ответ:
        returncode = 0
        stdout = "<html><body><p>совсем другое содержимое страницы</p></body></html>@@КОД:200"
        stderr = ""

    monkeypatch.setattr(СРАВНЕНИЕ.subprocess, "run", lambda *a, **k: Ответ())
    итог = СРАВНЕНИЕ.сравнить_запись(
        _запись(body="Достаточно длинное предложение для сравнения фраз."), 5)
    assert итог["исход"] == "РАСХОДИТСЯ", итог


def test_живой_статус_без_тела_это_нечего_сравнить(monkeypatch):
    """58 записей «на сайте», тело есть у 15: по остальным вывода нет."""
    monkeypatch.setattr(СРАВНЕНИЕ.subprocess, "run",
                        lambda *a, **k: (_ for _ in ()).throw(
                            AssertionError("сеть не должна вызываться")))
    итог = СРАВНЕНИЕ.сравнить_запись(_запись(body="", status="ALREADY_LIVE"), 5)
    assert итог["исход"] == "НЕЧЕГО СРАВНИТЬ"


def test_описание_из_meta_тоже_считается_страницей():
    """Описание произведения часто живёт в meta description."""
    стр, опис = СРАВНЕНИЕ.текст_страницы(
        '<html><head><meta name="description" content="Текст описания тут">'
        '</head><body>прочее</body></html>')
    assert "текст описания тут" in опис
    assert "прочее" in стр


def test_разметка_и_скрипты_в_текст_страницы_не_попадают():
    стр, _ = СРАВНЕНИЕ.текст_страницы(
        "<html><script>var x='мусор скрипта';</script><body>видимое</body></html>")
    assert "видимое" in стр
    assert "мусор" not in стр
