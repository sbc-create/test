"""Состав очереди редактора живёт в паспорте, а не в коде.

До 25.10.2026 он жил двумя литералами — `editor_run.EDITOR_DOMAINS` и
`regular.EDITOR_SITES`. Последствие измеримо: домен попадал в публикацию
правкой кода, паспорт при этом мог говорить обратное, а снятие признака в
паспорте не прекращало ничего. Задание владельца на пятёрку новых витрин
требует обратного прямо: добавлять домены «через единый реестр, без второго
перечня в коде».

Проверяется не наличие функций, а свойства состава:
  * признак положительный и составной — флага без даты и доказательства не
    хватает (иначе «показ подтверждён» держится на слове);
  * запись в паспорте управляет публикацией в обе стороны;
  * кандидаты строятся только по витринам со снимком каталога;
  * недоступный реестр оставляет состав пустым, а не разрешает всё.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from factory.cell import registry


def _ячейка(site_id: str, домен: str, editorial: dict | None = None) -> dict:
    запись = {
        "site_id": site_id, "domain": домен, "aliases": [], "status": "live",
        "repo": {"kind": "local", "path": f"var/site-repos/{site_id}"},
        "template": {"template_id": "lords-serials", "family": "lords"},
        "pins": {}, "deploy_target": {"ref": "k2-zomro-01"},
        "publisher": {}, "data": {},
    }
    if editorial is not None:
        запись["editorial"] = editorial
    return запись


@pytest.fixture()
def реестр(tmp_path: Path) -> Path:
    путь = tmp_path / "site-cells.json"
    путь.write_text(json.dumps({"schema_version": "1.0", "cells": [
        _ячейка("a-01", "a.test", {"overlay_confirmed": True, "confirmed_at": "2026-10-09",
                                   "proof": "a.test/title/x/ — текст виден",
                                   "candidates_from_snapshot": True}),
        _ячейка("b-01", "b.test", {"overlay_confirmed": True, "confirmed_at": "2026-10-10",
                                   "proof": "b.test/anime/y/ — текст виден",
                                   "candidates_from_snapshot": False}),
        _ячейка("c-01", "c.test", {"overlay_confirmed": False}),
        _ячейка("d-01", "d.test", None),
        # Флаг есть, доказательства нет: это слово, а не подтверждение.
        _ячейка("e-01", "e.test", {"overlay_confirmed": True}),
        _ячейка("f-01", "f.test", {"overlay_confirmed": True, "confirmed_at": "2026-10-10",
                                   "proof": "   "}),
    ]}, ensure_ascii=False), encoding="utf-8")
    return путь


def test_публикуют_только_витрины_с_подтверждённым_показом(реестр):
    assert registry.домены_публикации(path=реестр) == {"a.test", "b.test"}


def test_флага_без_даты_и_доказательства_не_хватает(реестр):
    """Иначе текст публикуется и никуда не попадает — мёртвые данные."""
    состав = registry.домены_публикации(path=реестр)
    assert "e.test" not in состав, "флаг без даты и доказательства допущен"
    assert "f.test" not in состав, "пробелы вместо доказательства допущены"


def test_отсутствие_блока_не_разрешает_публикацию(реестр):
    assert "d.test" not in registry.домены_публикации(path=реестр)
    assert "c.test" not in registry.домены_публикации(path=реестр)


def test_кандидаты_только_по_витринам_со_снимком(реестр):
    """Yummy публикует заданиями: снимка каталога у семейства нет вовсе."""
    assert registry.сайты_кандидатов(path=реестр) == {"a.test": "a-01"}


def test_снятие_признака_прекращает_публикацию(реестр):
    assert "a.test" in registry.домены_публикации(path=реестр)
    registry.update("a-01", {"editorial": {"overlay_confirmed": False}}, path=реестр)
    assert "a.test" not in registry.домены_публикации(path=реестр)
    assert registry.сайты_кандидатов(path=реестр) == {}


def test_недоступный_реестр_оставляет_состав_пустым(tmp_path, monkeypatch):
    """Fail-closed: редактор остановится с причиной, а не опубликует на всех."""
    from seo_operator import editor_run, regular

    monkeypatch.setattr(registry, "домены_публикации",
                        lambda **_: (_ for _ in ()).throw(OSError("реестр недоступен")))
    monkeypatch.setattr(registry, "сайты_кандидатов",
                        lambda **_: (_ for _ in ()).throw(OSError("реестр недоступен")))
    assert editor_run._домены_публикации_из_реестра() == ()
    assert regular._сайты_кандидатов_из_реестра() == {}


def test_состав_совпал_с_прежними_литералами():
    """Перенос не менял состав: 17 доменов публикации и 12 со снимком.

    Числа — измеренные на боевом реестре 25.10, а не желаемые: перенос обязан
    быть тождественным, иначе он сам по себе менял бы, где публикуется текст.
    """
    assert len(registry.домены_публикации()) == 17
    assert len(registry.сайты_кандидатов()) == 12
