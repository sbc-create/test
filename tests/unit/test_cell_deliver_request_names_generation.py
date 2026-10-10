"""Заявка на доставку данных называется ПОКОЛЕНИЕМ, а не коммитом кода.

Что ловится. Идентификатор заявки строится из операции и коммита:
`zona-02-data-bf63a60c60bd`. Для выпуска кода это верно — коммит и есть
содержание работы. Для доставки данных это неверно: выпуск не меняется месяцами,
а снимок каталога меняется каждую ночь. Вторая доставка на тот же выпуск
получала имя первой, очередь отвечала `already-finished` — «уже выполнено», — и
новое поколение не доезжало до витрины НИКОГДА, причём обе стороны считали, что
всё в порядке.

Как это выглядело вживую (10 октября 2026). Ночной прогон не смог записать
каталог zona-02: каталога данных ячейки не было в `ReadWritePaths` юнита, и
доставка отказала с `Errno 30`. Прогон, который это исправил бы, погиб в
публикации от нехватки памяти. Единственным оставшимся способом довезти уже
собранное и проверенное поколение была документированная доставка через
очередь — и она отвечала «уже выполнено», ссылаясь на доставку прежнего
поколения двухдневной давности.

Поэтому здесь сторожится ровно два свойства:

* поколение берётся ИЗ СНИМКА производителя, а не из рук человека;
* прочитать его нечем — заявка отказывает, а не подставляет коммит: подстановка
  и есть та неисправность.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

КОРЕНЬ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(КОРЕНЬ))

from factory.cell import content, queue  # noqa: E402

КОММИТ = "bf63a60c60bdcb297404c971ee870603f05ee8b9"
DIGEST = "sha256:" + "6" * 64


def снимок(путь: Path, *, revision: str, записей: int = 400) -> None:
    """Файл того же порядка полей и масштаба, что у производителя.

    Масштаб важен: `revision` лежит ЗА записями, то есть в хвосте файла, и
    чтение одной головы его не находит.
    """
    путь.write_text(json.dumps({
        "builtAt": "2026-10-10T03:17:07Z",
        "count": записей,
        "items": [{"slug": f"z-{i}", "title": "Тайтл " * 12} for i in range(записей)],
        "revision": revision,
        "schema": "nova-catalog/2.0.0",
        "site": "zona-02",
    }, ensure_ascii=False), encoding="utf-8")
    assert путь.stat().st_size > 32768, "снимок должен быть больше окна чтения"


def test_ревизия_источника_читается_из_хвоста(tmp_path):
    снимок(tmp_path / "zona-02-catalog.json", revision="37a6679e5de4bd5a")
    assert content.ревизия_источника("zona-02", общий=tmp_path) == "37a6679e5de4bd5a"


def test_нет_снимка_нет_ревизии(tmp_path):
    """Пустая строка — это «нечем измерить», и вызывающая сторона обязана отказать."""
    assert content.ревизия_источника("zona-02", общий=tmp_path) == ""


def test_разные_поколения_дают_разные_заявки():
    """Главное свойство: новое поколение — новая работа, а не повтор прежней."""
    первая = queue.собрать("zona-02", КОММИТ, DIGEST, operation="deliver",
                           snapshot="4e501fc6280c1ddb")
    вторая = queue.собрать("zona-02", КОММИТ, DIGEST, operation="deliver",
                           snapshot="37a6679e5de4bd5a")
    assert первая.request_id != вторая.request_id, (
        "две доставки разных поколений на один выпуск получили одно имя: "
        "очередь ответит already-finished и новое поколение не доедет")
    assert вторая.request_id == "zona-02-data-37a6679e5de4"


def test_то_же_поколение_остаётся_той_же_заявкой():
    """Повтор доставки того же снимка — именно повтор, и очередь вправе его узнать."""
    а = queue.собрать("zona-02", КОММИТ, DIGEST, operation="deliver",
                      snapshot="37a6679e5de4bd5a")
    б = queue.собрать("zona-02", КОММИТ, DIGEST, operation="deliver",
                      snapshot="37a6679e5de4bd5a")
    assert а.request_id == б.request_id


def test_без_поколения_заявка_называется_коммитом_и_это_та_самая_ошибка():
    """Фиксируется прежнее поведение, чтобы было видно, от чего защита.

    Без `snapshot` имя заявки зависит только от коммита, то есть от выпуска
    кода. Этот тест не требует изменить `собрать` — он показывает, почему
    подстановка коммита на уровне подачи запрещена.
    """
    а = queue.собрать("zona-02", КОММИТ, DIGEST, operation="deliver")
    assert а.request_id == "zona-02-data-bf63a60c60bd"


def test_подача_отказывает_без_ревизии_вместо_подстановки_коммита(tmp_path, monkeypatch, capsys):
    """Подача читает поколение сама и отказывает, если прочитать нечем."""
    from factory.cell import cli as cell_cli

    monkeypatch.setattr(content, "ОБЩИЙ", tmp_path)

    class Аргументы:
        site = "zona-02"
        commit = КОММИТ
        expect_digest = DIGEST
        cell_operation = "deliver"
        ci_run = ""
        repo = ""
        reason = "проверка"
        mode = ""

    подано: list = []
    monkeypatch.setattr(queue, "подать", lambda з: подано.append(з))
    # Проверки рабочей копии и доступа исполнителя к этому свойству не
    # относятся: они стоят до подачи и в стенде недоступны.
    for имя in ("проверить_рабочую_копию", "проверить_комплектность_данных",
                "проверить_маршрут", "проверить_сборщик", "проверить_лаунчер",
                "проверить_доступ_исполнителя"):
        monkeypatch.setattr(queue, имя, lambda *а, **к: None)

    код = cell_cli.cmd_submit(Аргументы())
    assert код == 2, "без ревизии снимка подача обязана отказать"
    assert not подано, "заявка не должна была уйти в очередь"
    вывод = capsys.readouterr()
    assert "BLOCKED_INPUT" in вывод.err
    assert "ревизию снимка" in вывод.err


def test_подача_берёт_поколение_из_снимка(tmp_path, monkeypatch):
    """С снимком на месте заявка называется поколением, а не коммитом."""
    from factory.cell import cli as cell_cli

    снимок(tmp_path / "zona-02-catalog.json", revision="37a6679e5de4bd5a")
    monkeypatch.setattr(content, "ОБЩИЙ", tmp_path)

    class Аргументы:
        site = "zona-02"
        commit = КОММИТ
        expect_digest = DIGEST
        cell_operation = "deliver"
        ci_run = ""
        repo = ""
        reason = "проверка"
        mode = ""

    подано: list = []
    monkeypatch.setattr(queue, "подать",
                        lambda з: (подано.append(з), {"status": "accepted"})[1])
    for имя in ("проверить_рабочую_копию", "проверить_комплектность_данных",
                "проверить_маршрут", "проверить_сборщик", "проверить_лаунчер",
                "проверить_доступ_исполнителя"):
        monkeypatch.setattr(queue, имя, lambda *а, **к: None)

    assert cell_cli.cmd_submit(Аргументы()) == 0
    assert подано and подано[0].request_id == "zona-02-data-37a6679e5de4"


@pytest.mark.parametrize("операция", ["activate", "update", "rollback"])
def test_выпуск_кода_по_прежнему_называется_коммитом(операция, monkeypatch):
    """Исправление не трогает выпуск кода: там содержание работы — коммит."""
    заявка = queue.собрать("zona-02", КОММИТ, DIGEST, operation=операция)
    assert КОММИТ[:12] in заявка.request_id
