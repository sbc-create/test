"""У каждой ячейки с собственным репозиторием есть чем собрать выпуск.

Повод. Из семнадцати ячеек `tools/build_release.py` не было ровно у `animego-04`
— и узналось это трассировкой `ExecutorRefused` в середине подачи заявки, после
зелёного CI, заведённой площадки, nginx и сертификата. Проверка стоит один
вызов `is_file()` и не требует ни прав, ни сети: место ей до подачи, а не в
обработчике исключений.

Второе свойство, которое здесь же закрепляется: проверка обязана стоять в ОБОИХ
путях подачи. Проверки, обходимой соседней командой, у нас уже было достаточно —
`cell trigger` шёл мимо всего, что стояло только в `cell submit`, и заявки
подавались именно им.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from factory.cell import queue as q

КОРЕНЬ = Path(__file__).resolve().parents[2]


def ячейки_с_репозиторием() -> list[tuple[str, Path]]:
    реестр = json.loads((КОРЕНЬ / "config" / "site-cells.json").read_text(encoding="utf-8"))
    итог = []
    for ячейка in реестр["cells"]:
        путь = (ячейка.get("repo") or {}).get("path")
        if not путь:
            continue
        рабочая = КОРЕНЬ / путь
        if (рабочая / ".git").exists():
            итог.append((ячейка["site_id"], рабочая))
    return итог


ЯЧЕЙКИ = ячейки_с_репозиторием()


def test_есть_что_проверять() -> None:
    assert len(ЯЧЕЙКИ) >= 10, f"ячеек с рабочей копией найдено {len(ЯЧЕЙКИ)}"


@pytest.mark.parametrize("site_id,репозиторий", ЯЧЕЙКИ, ids=[с for с, _ in ЯЧЕЙКИ])
def test_у_ячейки_есть_сборщик(site_id: str, репозиторий: Path) -> None:
    сборщик = репозиторий / q.СБОРЩИК_ПАКЕТА
    assert сборщик.is_file(), (
        f"{site_id}: нет {q.СБОРЩИК_ПАКЕТА} — выпуск этой ячейки невозможен, "
        "и узнается это только при подаче заявки")


@pytest.mark.parametrize("site_id,репозиторий", ЯЧЕЙКИ, ids=[с for с, _ in ЯЧЕЙКИ])
def test_предполётная_проверка_пропускает_готовую_ячейку(site_id: str, репозиторий: Path) -> None:
    q.проверить_сборщик(site_id)


def test_проверка_отказывает_без_сборщика(tmp_path: Path, monkeypatch) -> None:
    from factory.cell import registry as реестр_ячеек

    (tmp_path / "репо" / ".git").mkdir(parents=True)

    class Ячейка:
        site_id = "проба"
        domain = "проба.test"
        repo = {"path": "репо"}

    monkeypatch.setattr(q, "КОРЕНЬ_ПРОЕКТА", tmp_path)
    monkeypatch.setattr(реестр_ячеек, "resolve", lambda _: Ячейка())
    with pytest.raises(q.RequestRejected) as отказ:
        q.проверить_сборщик("проба")
    assert q.СБОРЩИК_ПАКЕТА in str(отказ.value)

    (tmp_path / "репо" / "tools").mkdir()
    (tmp_path / "репо" / q.СБОРЩИК_ПАКЕТА).write_text("# пусто\n", encoding="utf-8")
    q.проверить_сборщик("проба")


def test_проверка_стоит_в_обоих_путях_подачи() -> None:
    for файл in ("factory/cell/cli.py", "factory/cell/trigger.py"):
        текст = (КОРЕНЬ / файл).read_text(encoding="utf-8")
        assert "проверить_сборщик" in текст, f"{файл} не вызывает проверить_сборщик"


def test_имя_сборщика_одно_и_то_же_у_очереди_и_у_исполнителя() -> None:
    """Два написания одного имени разойдутся, и проверка начнёт мерить не то."""
    from factory.cell import admin_exec

    assert str(admin_exec.СБОРЩИК) == q.СБОРЩИК_ПАКЕТА
    # И берётся оно у него же, а не повторено строкой: иначе два
    # написания разойдутся молча.
    исходник = (КОРЕНЬ / "factory" / "cell" / "queue.py").read_text(encoding="utf-8")
    assert 'СБОРЩИК_ПАКЕТА = str(_admin_exec.СБОРЩИК)' in исходник
