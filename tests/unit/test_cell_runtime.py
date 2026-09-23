"""Размещение витрины — один ответ для всех, кто её трогает.

До этого блока производители содержимого знали про службы по собственным
спискам: таблица в `content-pipeline/refresh.py`, массив `SITES` в
`nova-daily-refresh.sh`. После переноса сайта в свою ячейку они продолжали
писать снимок по прежнему пути и звать прежний unit по имени — витрина не
ломалась, она переставала пополняться, и заметить это можно было только по дате
самой свежей карточки.

Проверяется поведение, а не наличие полей: решение «перезапускать или нет»
и «куда доставлять» вычисляется на подставных реестрах.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

КОРЕНЬ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(КОРЕНЬ))

from factory.cell import registry, runtime  # noqa: E402


def _реестр(tmp_path: Path, *ячейки: dict) -> Path:
    путь = tmp_path / "site-cells.json"
    путь.write_text(json.dumps({"schema_version": 1, "cells": list(ячейки)},
                               ensure_ascii=False), encoding="utf-8")
    return путь


ЯЧЕЙКА_ZONA = {
    "site_id": "zona-01", "domain": "zonafilm.space", "status": "deployed",
    "repo": {"kind": "remote", "path": "var/site-repos/zonafilm-space",
             "remote": "https://github.com/sbc-create/site-zonafilm-space"},
    "template": {"template_id": "zona-nova"}, "deploy_target": {},
    "runtime": {"unit": "nova-zonafilm-space.service",
                "previous_unit": "nova-zona-01.service", "port": 9120,
                "account": "zonafilm-space", "data_dir": "/srv/zonafilm-space/data",
                "reload": "mtime", "managed_by": "cell", "data_owner": "pipeline"},
}
ЯЧЕЙКА_МОНОЛИТ = {
    "site_id": "lords-01", "domain": "lordfilm47.space", "status": "staged",
    "repo": {"kind": "remote", "path": "var/site-repos/lordfilm47-space",
             "remote": "https://github.com/sbc-create/site-lordfilm47-space"},
    "template": {"template_id": "lords-general"}, "deploy_target": {},
    "runtime": {"unit": "lords-nova-01.service", "previous_unit": None, "port": 9110,
                "account": "lordfilm47-space", "data_dir": None,
                "reload": "unknown", "managed_by": "monolith", "data_owner": "pipeline"},
}
ЯЧЕЙКА_СВОЙ_ТАЙМЕР = {
    "site_id": "animedia-02", "domain": "animedia.space", "status": "deployed",
    "repo": {"kind": "remote", "path": "var/site-repos/animedia-space",
             "remote": "https://github.com/sbc-create/site-animedia-space"},
    "template": {"template_id": "animedia-nova"}, "deploy_target": {},
    "runtime": {"unit": "nova-animedia-space.service",
                "previous_unit": "nova-animedia-02.service", "port": 9122,
                "account": "animedia-space", "data_dir": "/srv/animedia-space/data",
                "reload": "unknown", "managed_by": "cell", "data_owner": "site_timer"},
}


def test_витрина_с_перечитыванием_не_требует_перезапуска(tmp_path):
    """Zona перечитывает снимок сама; перезапуск ей стоит минут, а не секунд."""
    путь = _реестр(tmp_path, ЯЧЕЙКА_ZONA)
    р = runtime.размещение("zona-01", path=путь)
    assert р.reload == "mtime"
    assert р.нужен_перезапуск is False
    assert р.data_dir == "/srv/zonafilm-space/data"


def test_неизвестный_режим_считается_перезапуском(tmp_path):
    """Осторожность по умолчанию: пропущенный перезапуск незаметен.

    Лишний перезапуск виден сразу и стоит минуты; пропущенный не виден вовсе и
    оставляет витрину на вчерашнем каталоге до следующего повода.
    """
    путь = _реестр(tmp_path, ЯЧЕЙКА_МОНОЛИТ)
    assert runtime.размещение("lords-01", path=путь).нужен_перезапуск is True


def test_прежний_unit_назван_отдельно(tmp_path):
    """Прежнюю службу надо знать, чтобы её НЕ звать, а не чтобы звать."""
    путь = _реестр(tmp_path, ЯЧЕЙКА_ZONA)
    р = runtime.размещение("zona-01", path=путь)
    assert р.previous_unit == "nova-zona-01.service"
    assert р.unit != р.previous_unit


def test_сайт_со_своим_переносом_отдаёт_владение(tmp_path):
    """Два писателя одного файла — гонка, а не запас."""
    путь = _реестр(tmp_path, ЯЧЕЙКА_СВОЙ_ТАЙМЕР)
    р = runtime.размещение("animedia-02", path=путь)
    assert р.managed_by == "cell"
    # Производитель обязан увидеть, что каталог данных не его.
    assert р.as_dict()["data_dir"] == "/srv/animedia-space/data"
    блок = json.loads(путь.read_text(encoding="utf-8"))["cells"][0]["runtime"]
    assert блок["data_owner"] == "site_timer"


def test_молчащий_реестр_останавливает_а_не_подсказывает(tmp_path):
    """Отсутствие записи — повод остановиться, а не выбрать прежний путь."""
    без_runtime = {**ЯЧЕЙКА_МОНОЛИТ}
    без_runtime.pop("runtime")
    путь = _реестр(tmp_path, без_runtime)
    with pytest.raises(runtime.RuntimeUnknown):
        runtime.размещение("lords-01", path=путь)


def test_чтение_файлом_совпадает_с_чтением_через_фабрику(tmp_path):
    """Производители читают реестр без импорта фабрики — ответ обязан совпасть.

    Иначе появятся две правды об одном сайте, и расходиться они начнут молча.
    """
    путь = _реестр(tmp_path, ЯЧЕЙКА_ZONA, ЯЧЕЙКА_МОНОЛИТ, ЯЧЕЙКА_СВОЙ_ТАЙМЕР)
    через_фабрику = runtime.для_производителя(путь)
    файлом = runtime.прочитать_реестр_файлом(путь)
    assert через_фабрику == файлом


def test_боевой_реестр_описывает_размещение_каждой_выделенной_ячейки():
    """Сайт с собственным репозиторием обязан знать, где он живёт."""
    выделенные = set(registry.extracted_sites())
    размещения = set(runtime.все_размещения())
    без_описания = sorted(выделенные - размещения)
    assert not без_описания, f"нет блока runtime: {без_описания}"


def test_ни_одна_ячейка_не_считает_прежний_unit_своим():
    """Иначе производитель позвал бы службу, закрытую от ручного запуска."""
    плохие = [s for s, р in runtime.все_размещения().items()
              if р.unit and р.unit == р.previous_unit]
    assert not плохие, плохие
