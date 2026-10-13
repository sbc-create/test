"""Назначение `publisher_id`: три места или ни одного, и номер не печатается.

D177 называет три места — значение у производителя, объявление в пакете
витрины, учёт в реестре — и требует их согласия: «правка одного места без
остальных возвращается следующей выкладкой». Это измеренный 2026-10-05 случай
zonafilm.cc, где все три места говорили номер СОСЕДНЕЙ витрины.

Здесь закрепляется поведение инструмента, который меняет три места вместе:

* форма номера и отзыв поставщиком проверяются ДО любой записи;
* один номер на несколько домен возможен (в сети так уже есть), но только
  явным решением: без `--allow-shared` — отказ с именем домена-владельца;
* после записи согласие ПРОВЕРЯЕТСЯ чтением, а не предполагается;
* повторный запуск ничего не меняет и говорит об этом;
* номер не попадает ни в отчёт, ни в текст отказа.
"""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

from factory.cell import registry

КОРЕНЬ = Path(__file__).resolve().parents[2]
НОМЕР = "10999"          # для стенда, не для сети
ЧУЖОЙ = "10998"


def _модуль():
    путь = КОРЕНЬ / "automation" / "local" / "assign-publisher-id.py"
    spec = importlib.util.spec_from_file_location("assign_publisher_id", путь)
    м = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(м)
    return м


def _стенд(tmp_path, *, с_путём_репо=True, сосед_с_номером=None):
    репо = tmp_path / "repo" / "lords-10"
    (репо / "config").mkdir(parents=True)
    (репо / "config" / "site.json").write_text(json.dumps(
        {"site_id": "lords-10", "domain": "lordfilm.group",
         "publisher_id_expected": None,
         "publisher_id_ref": "secret://cdnvideohub/lords/publisher-id"},
        ensure_ascii=False), encoding="utf-8")

    def запись(site_id, domain, repo_path, publisher):
        return {"site_id": site_id, "domain": domain, "aliases": [],
                "status": "planned",
                "repo": ({"kind": "local", "path": str(repo_path)} if repo_path
                         else {"kind": "local"}),
                "template": {"template_id": "lords-films"}, "pins": {},
                "deploy_target": {}, "publisher": publisher, "data": {},
                "deployed": {}, "content_revision": None, "last_update": None,
                "backup": {}, "resources": {},
                "runtime": {"port": 9125, "unit": "nova-lordfilm-group.service",
                            "data_dir": "/srv/lordfilm-group/data"},
                "release": {}}

    ячейки = [запись("lords-10", "lordfilm.group",
                     репо if с_путём_репо else None, {})]
    if сосед_с_номером:
        ячейки.append(запись("lords-13", "lordserial.su", None,
                             {"publisher_id": сосед_с_номером}))
    реестр = tmp_path / "site-cells.json"
    реестр.write_text(json.dumps({"schema_version": registry.SCHEMA_VERSION,
                                  "cells": ячейки}, ensure_ascii=False),
                      encoding="utf-8")
    производитель = tmp_path / "frontend"
    производитель.mkdir()
    return реестр, репо, производитель


@pytest.mark.parametrize("плохой", ["", "  ", "abc", "0123", "102 38", "10a38"])
def test_негодная_форма_отвергается_до_записи(tmp_path, плохой):
    м = _модуль()
    реестр, _, производитель = _стенд(tmp_path)
    with pytest.raises(м.Отказ):
        м.назначить("lords-10", плохой, apply=True, path=реестр,
                    производитель=производитель)
    assert not list(производитель.iterdir()), "файл значения создан при негодной форме"


def test_отозванный_номер_отвергается(tmp_path):
    м = _модуль()
    реестр, _, производитель = _стенд(tmp_path)
    отозванный = sorted(registry.RETIRED_PUBLISHER_IDS)[0]
    with pytest.raises(м.Отказ, match="отозван"):
        м.назначить("lords-10", отозванный, apply=True, path=реестр,
                    производитель=производитель)


def test_номер_не_печатается_ни_в_отчёте_ни_в_отказе(tmp_path):
    """Номер публичен по D138, но в терминале и журналах ему делать нечего."""
    м = _модуль()
    реестр, _, производитель = _стенд(tmp_path, сосед_с_номером=НОМЕР)
    with pytest.raises(м.Отказ) as ош:
        м.назначить("lords-10", НОМЕР, apply=True, path=реестр,
                    производитель=производитель)
    assert НОМЕР not in str(ош.value)
    отчёт = м.назначить("lords-10", НОМЕР, apply=True, allow_shared=True,
                        path=реестр, производитель=производитель)
    assert НОМЕР not in json.dumps(отчёт, ensure_ascii=False)


def test_совместное_использование_только_явным_решением(tmp_path):
    м = _модуль()
    реестр, _, производитель = _стенд(tmp_path, сосед_с_номером=НОМЕР)
    with pytest.raises(м.Отказ, match="allow-shared"):
        м.назначить("lords-10", НОМЕР, apply=True, path=реестр,
                    производитель=производитель)
    отчёт = м.назначить("lords-10", НОМЕР, apply=True, allow_shared=True,
                        path=реестр, производитель=производитель)
    assert отчёт["shared_with"] == ["lordserial.su"]
    assert отчёт["итог"] == "три места согласованы"


def test_сухой_прогон_не_меняет_ничего(tmp_path):
    м = _модуль()
    реестр, репо, производитель = _стенд(tmp_path)
    до = (реестр.read_text(encoding="utf-8"),
          (репо / "config" / "site.json").read_text(encoding="utf-8"))
    отчёт = м.назначить("lords-10", НОМЕР, apply=False, path=реестр,
                        производитель=производитель)
    assert отчёт["применено"] is False
    assert not list(производитель.iterdir())
    assert до == (реестр.read_text(encoding="utf-8"),
                  (репо / "config" / "site.json").read_text(encoding="utf-8"))


def test_три_места_согласованы_и_повтор_ничего_не_меняет(tmp_path):
    м = _модуль()
    реестр, репо, производитель = _стенд(tmp_path)
    отчёт = м.назначить("lords-10", НОМЕР, apply=True, path=реестр,
                        производитель=производитель)
    assert отчёт["совпадает_после"] == {"значение": True, "объявление": True,
                                        "учёт": True}
    файл = производитель / "player-lords-10.json"
    assert файл.is_file() and oct(файл.stat().st_mode)[-3:] == "600"
    assert json.loads((репо / "config" / "site.json").read_text(
        encoding="utf-8"))["publisher_id_expected"] == НОМЕР
    assert (registry.resolve("lords-10", реестр).publisher or {})["publisher_id"] == НОМЕР

    снова = м.назначить("lords-10", НОМЕР, apply=True, path=реестр,
                        производитель=производитель)
    assert снова["итог"] == "менять нечего: три места уже согласны"


def test_без_пути_репозитория_отказ(tmp_path):
    """Объявлять publisher_id_expected некуда — значит назначение не выполнено."""
    м = _модуль()
    реестр, _, производитель = _стенд(tmp_path, с_путём_репо=False)
    with pytest.raises(м.Отказ, match="путь репозитория"):
        м.назначить("lords-10", НОМЕР, apply=True, path=реестр,
                    производитель=производитель)
    assert not list(производитель.iterdir())


def test_неизвестная_ячейка_отказ(tmp_path):
    м = _модуль()
    реестр, _, производитель = _стенд(tmp_path)
    with pytest.raises(м.Отказ):
        м.назначить("lords-99", НОМЕР, apply=True, path=реестр,
                    производитель=производитель)
