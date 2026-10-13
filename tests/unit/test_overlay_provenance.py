"""Происхождение записей наложений: два поля, одно понятие (T043).

Проверяется не «считает правильно», а четыре вида подмены:

* **названное происхождение за пробел** — запись с `source_manifest` не несёт
  поля `author` ПО УСТРОЙСТВУ, и проверка одного поля объявляет её пробелом.
  Измерено 13.10: так получаются ровно три ложных пробела на `yummyani.site`,
  у которых тело и его отпечаток целы;
* **иной путь за полноценное авторство** — обратная ошибка: запись с
  `source_manifest` нельзя зачесть как «автор назван», иначе отчёт состояния
  покажет автора там, где его нет;
* **нечитаемый файл за пустой** — отсутствие записей и отсутствие доступа
  должны быть разными исходами;
* **свой перечень корней за реестр** — корни хранилищ читаются из
  `factory/qwen/registry.py`; копия внутри инструмента разошлась бы с выпуском
  молча.
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

КОРЕНЬ = Path(__file__).resolve().parents[2]
ИСТОЧНИК = КОРЕНЬ / "automation" / "local" / "overlay-provenance.py"


def _модуль():
    спец = importlib.util.spec_from_file_location("overlay_provenance", ИСТОЧНИК)
    м = importlib.util.module_from_spec(спец)
    sys.modules["overlay_provenance"] = м
    спец.loader.exec_module(м)
    return м


@pytest.fixture(scope="module")
def модуль():
    return _модуль()


С_PROVENANCE = {
    "content_id": "a-1",
    "provenance": {"author": "Редактор", "prepared_by": "seo", "facts_source": "kp",
                   "written_at": "2026-10-13T00:00:00Z", "sources": ["x"]},
}
С_MANIFEST = {
    "content_id": "repair-009-1-rev1",
    "source_manifest": {"source_type": "authorized_editorial_batch",
                        "source_id": "batch10:210", "facts": {}},
}
БЕЗ_ОБОИХ = {"content_id": "b-1", "body": "текст"}


def _файл(tmp_path: Path, записи: list[dict], generation: str = "g1") -> Path:
    ф = tmp_path / "title-overlays.json"
    ф.write_text(json.dumps({"items": записи, "generation_id": generation},
                            ensure_ascii=False), encoding="utf-8")
    return ф


def test_provenance_даёт_происхождение_с_автором(модуль):
    код, чем = модуль.исход(С_PROVENANCE)
    assert код == модуль.ПРОИСХОЖДЕНИЕ
    assert "Редактор" in чем


def test_source_manifest_это_иной_путь_а_не_пробел(модуль):
    """Главная проверка: названное происхождение не выдаётся за пробел."""
    код, чем = модуль.исход(С_MANIFEST)
    assert код == модуль.ИНОЙ_ПУТЬ, "запись с source_manifest объявлена пробелом"
    assert код != модуль.ПРОБЕЛ
    assert "authorized_editorial_batch" in чем
    assert "batch10:210" in чем


def test_иной_путь_не_выдаётся_за_названного_автора(модуль):
    """Обратная ошибка: автора у source_manifest нет, и это должно быть сказано."""
    _, чем = модуль.исход(С_MANIFEST)
    assert "author" in чем and "нет по устройству" in чем


def test_без_обоих_полей_это_настоящий_пробел(модуль):
    код, чем = модуль.исход(БЕЗ_ОБОИХ)
    assert код == модуль.ПРОБЕЛ
    assert "ни provenance, ни source_manifest" in чем


def test_provenance_без_автора_не_становится_пробелом(модуль):
    """Поле есть, автор в нём не назван — это не отсутствие происхождения."""
    код, чем = модуль.исход({"content_id": "c", "provenance": {"facts_source": "kp"}})
    assert код == модуль.ПРОИСХОЖДЕНИЕ
    assert "автор в нём не назван" in чем


def test_оба_поля_разом_главным_считается_provenance(модуль):
    запись = {**С_PROVENANCE, **{"source_manifest": {"source_type": "t", "source_id": "i"}}}
    код, чем = модуль.исход(запись)
    assert код == модуль.ПРОИСХОЖДЕНИЕ
    assert "provenance.author" in чем


def test_пустой_словарь_поля_за_наличие_не_считается(модуль):
    код, _ = модуль.исход({"content_id": "d", "provenance": {}, "source_manifest": {}})
    assert код == модуль.ПРОБЕЛ, "пустое поле зачтено за названное происхождение"


def test_разбор_файла_считает_оба_пути(модуль, tmp_path):
    ф = _файл(tmp_path, [С_PROVENANCE, С_MANIFEST, С_PROVENANCE])
    разбор = модуль.разобрать_домен(ф)
    assert разбор["состояние"] == "прочитан"
    assert разбор["записей"] == 3
    assert разбор["исходы"][модуль.ПРОИСХОЖДЕНИЕ] == 2
    assert разбор["исходы"][модуль.ИНОЙ_ПУТЬ] == 1
    assert модуль.ПРОБЕЛ not in разбор["исходы"]
    assert разбор["generation_id"] == "g1"


def test_разбор_по_одному_полю_даёт_ЛОЖНЫЙ_пробел(модуль, tmp_path):
    """D203: на неисправленном поведении проверка обязана показать другое число."""
    ф = _файл(tmp_path, [С_PROVENANCE, С_MANIFEST])
    верный = модуль.разобрать_домен(ф, одно_поле=False)
    одно = модуль.разобрать_домен(ф, одно_поле=True)
    assert верный["исходы"].get(модуль.ПРОБЕЛ, 0) == 0
    assert одно["исходы"].get(модуль.ПРОБЕЛ, 0) == 1, \
        "разбор по одному полю не показал ложный пробел — демонстрация не работает"


def test_нечитаемый_файл_не_равен_пустому(модуль, tmp_path):
    ф = tmp_path / "title-overlays.json"
    ф.write_text("{не json", encoding="utf-8")
    разбор = модуль.разобрать_домен(ф)
    assert модуль.НЕ_ИЗМЕРЕНО in разбор["состояние"]
    assert разбор["исходы"] == {}


def test_отсутствующий_файл_называется_отдельно(модуль, tmp_path):
    разбор = модуль.разобрать_домен(tmp_path / "нет.json")
    assert разбор["состояние"] == "файла нет"
    assert разбор["записей"] == 0


def test_запись_без_имени_называет_себя_честно(модуль):
    assert "себя не называет" in модуль.ключ({"provenance": {"author": "x"}})


def test_имя_берётся_в_объявленном_порядке(модуль):
    assert модуль.ключ({"content_id": "c", "slug": "s"}) == "content_id=c"
    assert модуль.ключ({"slug": "s", "title_id": "t"}) == "slug=s"


def test_корни_читаются_из_реестра_фабрики(модуль):
    корни, откуда = модуль.корни_хранилищ()
    assert корни, "корни не прочитаны"
    assert "registry.py" in откуда
    assert set(корни) >= {"animedia", "animego", "yummy"}


def test_без_реестра_инструмент_отказывает_а_не_молчит(модуль, tmp_path, capsys):
    код = модуль.главная(["--root", str(tmp_path)])
    напечатано = capsys.readouterr().out
    assert код == 2
    assert "ОТКАЗ" in напечатано
    assert модуль.НЕ_ИЗМЕРЕНО in напечатано


def test_настоящий_пробел_меняет_код_возврата(модуль, tmp_path, monkeypatch, capsys):
    корень = tmp_path / "overlays" / "пример.site"
    корень.mkdir(parents=True)
    _файл(корень, [С_PROVENANCE, БЕЗ_ОБОИХ])
    monkeypatch.setattr(модуль, "корни_хранилищ",
                        lambda *а, **к: ({"пример": str(tmp_path / "overlays")}, "из подмены"))
    код = модуль.главная([])
    напечатано = capsys.readouterr().out
    assert код == 1, "настоящий пробел не изменил код возврата"
    assert модуль.ПРОБЕЛ in напечатано


def test_иной_путь_код_возврата_не_меняет(модуль, tmp_path, monkeypatch, capsys):
    """Названное иным путём происхождение — не повод для ненулевого кода."""
    корень = tmp_path / "overlays" / "пример.site"
    корень.mkdir(parents=True)
    _файл(корень, [С_PROVENANCE, С_MANIFEST])
    monkeypatch.setattr(модуль, "корни_хранилищ",
                        lambda *а, **к: ({"пример": str(tmp_path / "overlays")}, "из подмены"))
    код = модуль.главная([])
    напечатано = capsys.readouterr().out
    assert код == 0
    assert модуль.ИНОЙ_ПУТЬ in напечатано
    assert "нет по устройству поля" in напечатано


def test_json_вывод_разбирается(модуль, tmp_path, monkeypatch, capsys):
    корень = tmp_path / "overlays" / "пример.site"
    корень.mkdir(parents=True)
    _файл(корень, [С_PROVENANCE, С_MANIFEST])
    monkeypatch.setattr(модуль, "корни_хранилищ",
                        lambda *а, **к: ({"пример": str(tmp_path / "overlays")}, "из подмены"))
    модуль.главная(["--json"])
    d = json.loads(capsys.readouterr().out)
    assert d["сводка"]["записей"] == 2
    assert d["сводка"][модуль.ИНОЙ_ПУТЬ] == 1
    assert d["семейства"]["пример"]["домены"]["пример.site"]["записей"] == 2
