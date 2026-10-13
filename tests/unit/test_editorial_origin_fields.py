"""Происхождение записи наложения в отчёте состояния: два поля, одно понятие.

Повод — T043 и замер 13.10 на живой сети: 294 записи наложений, 291 несут
`provenance` {author, prepared_by, …}, 3 несут `source_manifest`
{source_type, source_id, facts} и поля `author` НЕ содержат по устройству
(`stage2-ongoing-019fc72d`, `batch10-15-24-y-okrug-tokio`, `repair-009-1-rev1`
на yummyani.site). Без обоих полей — ни одной.

Прежний разбор читал только `provenance.author`, и эти три записи отдавались
без автора. От такого отчёта один шаг до неверного вывода «авторство потеряно
у трёх записей» — тогда как тело и его отпечаток у них целы.

Поэтому проверяется не «считает правильно», а четыре вида подмены:

* названное иначе происхождение за отсутствие автора — у записи с
  `source_manifest` должен появиться `origin`, а не молчаливый `None`;
* иной путь за полноценное авторство — обратная ошибка: `author` у такой
  записи обязан остаться пустым, иначе отчёт назовёт автора, которого нет;
* настоящий пробел за иной путь — запись без обоих полей обязана отличаться от
  записи с `source_manifest`;
* пустой словарь за названное поле — `{}` это не происхождение.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

КОРЕНЬ = Path(__file__).resolve().parents[2]


def _модуль():
    if str(КОРЕНЬ) not in sys.path:
        sys.path.insert(0, str(КОРЕНЬ))
    спец = importlib.util.spec_from_file_location(
        "factory.qwen.editorial_origin",
        КОРЕНЬ / "factory" / "qwen" / "editorial.py")
    м = importlib.util.module_from_spec(спец)
    sys.modules["factory.qwen.editorial_origin"] = м
    спец.loader.exec_module(м)
    return м


@pytest.fixture(scope="module")
def ред():
    return _модуль()


ПРОВ = {
    "provenance": {"author": "Редактор", "prepared_by": "seo",
                   "facts_source": "kp", "written_at": "2026-10-13T00:00:00Z"},
}
МАН = {
    "source_manifest": {"source_type": "authorized_editorial_batch",
                        "source_id": "batch10:210", "facts": {}},
}


def test_provenance_даёт_автора_и_путь(ред):
    итог = ред._происхождение(ПРОВ)
    assert итог["author"] == "Редактор"
    assert итог["origin"] == "provenance"
    assert итог["origin_ref"] is None


def test_prepared_by_берётся_когда_автора_нет(ред):
    итог = ред._происхождение({"provenance": {"prepared_by": "seo"}})
    assert итог["author"] == "seo"
    assert итог["origin"] == "provenance"


def test_source_manifest_называет_путь_а_не_молчит(ред):
    """Главная проверка: иной путь виден, и это не пустой ответ."""
    итог = ред._происхождение(МАН)
    assert итог["origin"] == "source_manifest", "иной путь не назван"
    assert итог["origin_ref"] == "authorized_editorial_batch/batch10:210"


def test_source_manifest_автора_не_выдумывает(ред):
    """Обратная ошибка: автора в этом поле нет по устройству."""
    assert ред._происхождение(МАН)["author"] is None


def test_настоящий_пробел_отличается_от_иного_пути(ред):
    пробел = ред._происхождение({"slug": "x", "body": "текст"})
    иной = ред._происхождение(МАН)
    assert пробел["origin"] is None
    assert иной["origin"] == "source_manifest"
    assert пробел != иной, "пробел и иной путь дают одинаковый ответ"


def test_пустой_словарь_происхождением_не_считается(ред):
    итог = ред._происхождение({"provenance": {}, "source_manifest": {}})
    assert итог["origin"] is None
    assert итог["author"] is None


def test_не_словарь_в_поле_происхождением_не_считается(ред):
    итог = ред._происхождение({"provenance": "Редактор"})
    assert итог["origin"] is None, "строка в поле зачтена за происхождение"


def test_оба_поля_разом_главным_остаётся_provenance(ред):
    итог = ред._происхождение({**ПРОВ, **МАН})
    assert итог["origin"] == "provenance"
    assert итог["author"] == "Редактор"


def test_набор_полей_ответа_постоянен(ред):
    """Отчёт состояния не должен терять ключи в зависимости от записи."""
    ожидаемо = {"author", "origin", "origin_ref"}
    for запись in (ПРОВ, МАН, {}, {"provenance": {}}):
        assert set(ред._происхождение(запись)) == ожидаемо


def test_поля_происхождения_объявлены_в_порядке_разбора(ред):
    assert ред.ПОЛЯ_ПРОИСХОЖДЕНИЯ == ("provenance", "source_manifest")


def test_проверка_накладки_происхождения_НЕ_требует(ред):
    """Намеренно: эта проверка повторяет схему ПРИЛОЖЕНИЯ, где такого поля нет.

    13.10 требование происхождения было сюда добавлено и снято: оно отвергало
    бы файл, который приложение приняло бы, и сообщение вызывающего
    «приложение витрины отвергло бы этот файл» стало бы неверным.
    """
    тело = "Текст описания достаточной длины для проверки отпечатка."
    запись = {
        "title_id": "01927e18-0e9e-7319-91b5-b8dd8be5a6a9",
        "slug": "009-1",
        "canonical_path": "/anime/009-1",
        "content_id": "editorial-009-1-abc",
        "content_type": "TITLE_DESCRIPTION",
        "body": тело,
        "content_digest": ред.отпечаток(тело),
        "published_at": "2026-10-09T13:00:00Z",
        "methodology_version": "SEO_CONTENT_METHODOLOGY_V1",
    }
    данные = {"schema_version": 1, "site": "yummyani.site",
              "generated_at": "2026-10-09T13:00:00Z", "generation_id": "g1",
              "items": [запись]}
    беды = ред.проверить_накладку_приложения(данные, "yummyani.site")
    assert беды == [], f"проверка схемы приложения пожаловалась: {беды}"
    assert not any("происхождение" in б for б in беды)
