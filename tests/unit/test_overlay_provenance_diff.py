"""REQ-EDITORIAL-PROVENANCE-DIFF: подмена авторства соседей видна по данным.

Дефект: публикация одного текста переклеймляла авторство всей накладки (правка
85bf620 от 12.10 22:57Z; служба моста запущена 12.10 17:42Z и правку не
читала). Инструмент `automation/local/overlay-provenance-diff.py` отвечает на
вопрос по живым данным, а не по дате процесса.

Отрицательные контроли здесь обязательны: проверка, которая не может сказать
«подмен нет», ничего не стоит. Поэтому на каждый случай «нашли» есть случай
«не нашли» и случай «не измерено».
"""
from __future__ import annotations

import importlib.util
import json
import pathlib

import pytest

КОРЕНЬ = pathlib.Path(__file__).resolve().parents[2]
_путь = КОРЕНЬ / "automation/local/overlay-provenance-diff.py"
_спец = importlib.util.spec_from_file_location("overlay_provenance_diff", _путь)
ИНСТР = importlib.util.module_from_spec(_спец)
_спец.loader.exec_module(ИНСТР)


def _записать(п: pathlib.Path, данные) -> pathlib.Path:
    п.parent.mkdir(parents=True, exist_ok=True)
    п.write_text(json.dumps(данные, ensure_ascii=False), encoding="utf-8")
    return п


def _накладка(записи: list[dict]) -> dict:
    return {"schema_version": 1, "site": "x.test",
            "generated_at": "2026-10-19T00:00:00Z", "items": записи}


def _запись(slug: str, тело: str, автор: str) -> dict:
    return {"slug": slug, "title_id": f"id-{slug}", "body": тело,
            "provenance": {"author": автор, "prepared_by": автор,
                           "written_at": "2026-10-09T00:00:00Z"}}


# --- накладка items+provenance -----------------------------------------------

def test_переклеймлённый_сосед_найден(tmp_path):
    прежний = _записать(tmp_path / "title-overlays.last-good.json",
                        _накладка([_запись("старый", "текст", "run-09")]))
    живой = _записать(tmp_path / "title-overlays.json",
                      _накладка([_запись("старый", "текст", "run-12")]))
    итог = ИНСТР.сверить_items(живой, прежний)
    assert итог["измерено"] is True
    assert [п["ключ"] for п in итог["подмены"]] == ["старый"]
    assert итог["подмены"][0]["было"] == "run-09"
    assert итог["подмены"][0]["стало"] == "run-12"


def test_новая_запись_соседей_не_трогает(tmp_path):
    """Отрицательный контроль: штатная публикация даёт ноль подмен."""
    прежний = _записать(tmp_path / "title-overlays.last-good.json",
                        _накладка([_запись("старый", "текст", "run-09")]))
    живой = _записать(tmp_path / "title-overlays.json",
                      _накладка([_запись("старый", "текст", "run-09"),
                                 _запись("новый", "текст-2", "run-12")]))
    итог = ИНСТР.сверить_items(живой, прежний)
    assert итог["подмены"] == []
    assert итог["новых"] == ["новый"]


def test_переписанный_текст_подменой_не_считается(tmp_path):
    """Сменился текст — сменился и автор: это работа, а не подмена."""
    прежний = _записать(tmp_path / "title-overlays.last-good.json",
                        _накладка([_запись("старый", "текст", "run-09")]))
    живой = _записать(tmp_path / "title-overlays.json",
                      _накладка([_запись("старый", "ДРУГОЙ текст", "run-12")]))
    assert ИНСТР.сверить_items(живой, прежний)["подмены"] == []


def test_без_прошлой_копии_не_измерено(tmp_path):
    живой = _записать(tmp_path / "title-overlays.json",
                      _накладка([_запись("старый", "текст", "run-09")]))
    итог = ИНСТР.сверить_items(живой, tmp_path / "title-overlays.last-good.json")
    assert итог["измерено"] is False
    assert "сравнивать не с чем" in итог["почему"]


def test_чужая_структура_не_измерено(tmp_path):
    живой = _записать(tmp_path / "title-overlays.json", {"items": "не список"})
    прежний = _записать(tmp_path / "title-overlays.last-good.json",
                        _накладка([_запись("с", "т", "run-09")]))
    итог = ИНСТР.сверить_items(живой, прежний)
    assert итог["измерено"] is False and "items" in итог["почему"]


# --- доставленный файл overrides+actor (Lords/Zona) --------------------------

def _учёт(записи: list[tuple[str, str]]) -> dict:
    return {"site": "x.test", "at": "2026-10-12T22:47:10Z",
            "items": [{"slug": s, "title_id": f"id-{s}", "body": "т",
                       "provenance": {"author": автор}} for s, автор in записи]}


def _доставлено(записи: list[tuple[str, str, str]]) -> dict:
    return {"schema_version": 1, "site_id": "zona-01",
            "overrides": {f"id-{s}": {"actor": актор, "fields": {"description": "т"},
                                      "reason": причина}
                          for s, актор, причина in записи}}


def test_подмена_актора_в_доставленном_файле(tmp_path):
    наш = _записать(tmp_path / "published.json",
                    _учёт([("первый", "run-09"), ("второй", "run-12")]))
    живой = _записать(tmp_path / "editorial-overrides.json", _доставлено([
        ("первый", "run-12", "SEO-описание тайтла второй"),
        ("второй", "run-12", "SEO-описание тайтла второй")]))
    итог = ИНСТР.сверить_overrides(живой, наш)
    assert итог["измерено"] is True
    assert [п["slug"] for п in итог["подмены"]] == ["первый"]
    assert [п["slug"] for п in итог["чужая_причина"]] == ["первый"]


def test_верный_актор_подменой_не_считается(tmp_path):
    """Отрицательный контроль: исправленный путь даёт ноль."""
    наш = _записать(tmp_path / "published.json",
                    _учёт([("первый", "run-09"), ("второй", "run-12")]))
    живой = _записать(tmp_path / "editorial-overrides.json", _доставлено([
        ("первый", "run-09", "SEO-описание тайтла первый"),
        ("второй", "run-12", "SEO-описание тайтла второй")]))
    итог = ИНСТР.сверить_overrides(живой, наш)
    assert итог["подмены"] == [] and итог["чужая_причина"] == []


def test_ручная_запись_не_объявляется_подменой(tmp_path):
    """Про автора чужой правки наш учёт ничего не знает — и молчит."""
    наш = _записать(tmp_path / "published.json", _учёт([("первый", "run-09")]))
    живой = _записать(tmp_path / "editorial-overrides.json", _доставлено([
        ("первый", "run-09", "SEO-описание тайтла первый"),
        ("ручной", "architect/restore", "восстановление решения D200")]))
    итог = ИНСТР.сверить_overrides(живой, наш)
    assert итог["подмены"] == []
    assert итог["не_наши"] == ["id-ручной"]


def test_без_нашего_учёта_не_измерено(tmp_path):
    живой = _записать(tmp_path / "editorial-overrides.json",
                      _доставлено([("первый", "run-12", "причина")]))
    итог = ИНСТР.сверить_overrides(живой, tmp_path / "published.json")
    assert итог["измерено"] is False and "учёта нет" in итог["почему"]


def test_пустой_overrides_не_измерено(tmp_path):
    """Пустой файл — это «сравнивать нечего», а не «подмен нет»."""
    наш = _записать(tmp_path / "published.json", _учёт([("первый", "run-09")]))
    живой = _записать(tmp_path / "editorial-overrides.json",
                      {"schema_version": 1, "overrides": {}})
    итог = ИНСТР.сверить_overrides(живой, наш)
    assert итог["измерено"] is False


def test_неопознанные_записи_не_измерено(tmp_path):
    """Живой файл про другие тайтлы: сверять нечего, и это не успех."""
    наш = _записать(tmp_path / "published.json", _учёт([("первый", "run-09")]))
    живой = _записать(tmp_path / "editorial-overrides.json",
                      _доставлено([("чужой", "run-12", "причина")]))
    итог = ИНСТР.сверить_overrides(живой, наш)
    assert итог["измерено"] is False and "не опознана" in итог["почему"]


# --- код возврата ------------------------------------------------------------

@pytest.mark.parametrize("домен", ["нет-такого.test"])
def test_ничего_не_измерено_даёт_код_2(домен, capsys):
    код = ИНСТР.main(["--domain", домен])
    assert код == 2
    assert "НЕ ИЗМЕРЕНО" in capsys.readouterr().out


def test_живая_сеть_измерима_хотя_бы_частично(capsys):
    """Инструмент не должен молча измерять ноль доменов на живом хосте."""
    код = ИНСТР.main([])
    вывод = capsys.readouterr().out
    assert код in (0, 1), вывод
    assert "домены: измерено" in вывод
