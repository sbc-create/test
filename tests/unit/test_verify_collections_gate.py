"""Приёмка подборок — ворота ВЫПУСКА, а не команда в документации.

Поручение владельца 26.10: «проверь, что приёмка подборок действительно
вызывается штатным выпуском. Наличие команды в AGENTS.md само по себе этого не
подтверждает». Измерено 26.10 до этой правки: ни `factory verify`, ни
`checks/run.sh` проекта о подборках не знали — требование жило только текстом.
"""
from __future__ import annotations

import json
import pathlib

import pytest

from factory import verify as verify_mod

КОРЕНЬ = pathlib.Path(__file__).resolve().parents[2]


def _файл_подборок(куда: pathlib.Path, *, целых: bool = True) -> pathlib.Path:
    подборка = {
        "key": "trillery-na-vecher",
        "title": "Триллеры на вечер",
        "viewer_request": "посмотреть напряжённое кино на один вечер",
        "intro": "Три фильма с закрытой историей: каждый заканчивается в тот же "
                 "вечер, продолжения искать не нужно.",
        "section": "/movies/",
        "indexing": {"open": False,
                     "reason": "витрина закрыта от индексации целиком, "
                               "подборка не исключение"},
        "items": [{"order": н, "id": f"catalog-{н:04d}", "slug": f"proba-{н}",
                   "url": f"https://proba.invalid/title/proba-{н}/",
                   "name": f"Проба {н}", "year": 2024,
                   "reason": "закрытая история на один вечер",
                   "checked": "2026-10-26"} for н in (1, 2, 3)],
    }
    if not целых:
        подборка["indexing"] = {"open": False}
    путь = куда / verify_mod.ФАЙЛ_ПОДБОРОК
    путь.write_text(json.dumps({
        "schema": "proba.invalid.collections/1", "site": "proba.invalid",
        "site_id": "proba-01", "prepared_at": "2026-10-26T00:00:00Z",
        "status": "PREPARED_NOT_RELEASED", "key": "proba-01-20261026",
        "direction_rule": "подборки по направлению витрины и разделу-владельцу",
        "collections": [подборка],
    }, ensure_ascii=False), encoding="utf-8")
    return путь


def test_без_файла_ворота_не_придумывают_код_выхода(tmp_path):
    """«Не применимо» — это НЕЗАПУЩЕННАЯ команда, а не синтетический ноль."""
    сборка = tmp_path / "build"
    сборка.mkdir()
    отчёты = tmp_path / "out"
    отчёты.mkdir()
    ворота = verify_mod._ворота_подборок("нет-такого-сайта", сборка, отчёты)
    assert ворота.id == "collections"
    assert ворота.exit_code is None, "ноль здесь означал бы «проверено»"
    assert ворота.passed is True
    assert ворота.counts["status"] == "skipped"
    assert "не объявляет подборок" in (отчёты / "collections.txt").read_text(
        encoding="utf-8")


def test_негодный_файл_валит_ворота(tmp_path):
    """Решение об индексации без причины — не решение, и выпуск не проходит."""
    сборка = tmp_path / "build"
    сборка.mkdir()
    отчёты = tmp_path / "out"
    отчёты.mkdir()
    _файл_подборок(сборка, целых=False)
    ворота = verify_mod._ворота_подборок("proba-01", сборка, отчёты)
    assert ворота.passed is False
    assert ворота.exit_code not in (None, 0)
    вывод = (отчёты / "collections.txt").read_text(encoding="utf-8")
    assert "схем" in вывод or "indexing" in вывод


def test_ворота_стоят_в_перечне_проверок_выпуска():
    """Ворота, которых нет в списке, выпуск не держат."""
    источник = pathlib.Path(verify_mod.__file__).read_text(encoding="utf-8")
    assert "_ворота_подборок(site_id, build_dir, out_dir)" in источник
    # И они идут ДО тяжёлых сетевых ворот: отказ по составу дешевле обхода.
    assert источник.index("_ворота_подборок(site_id") < источник.index(
        "crawl_report = crawl_mod.crawl")


def test_артефакт_ворот_лежит_рядом_с_остальными(tmp_path):
    сборка = tmp_path / "build"
    сборка.mkdir()
    отчёты = tmp_path / "out"
    отчёты.mkdir()
    ворота = verify_mod._ворота_подборок("proba-01", сборка, отчёты)
    assert ворота.artifact.endswith("collections.txt")
