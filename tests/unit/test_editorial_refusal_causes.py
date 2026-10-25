"""Раскладка причин отказа: порядок признаков и честная доля неназванного.

Проверка стоит на ошибке, сделанной при написании самого инструмента 25.10.
Первый подсчёт отнёс 47 отказов к «русское название расходится», потому что
образец искал слово «russian». В тех деталях сказано «russian «…» СОВПАЛ», а
отказ был по пустому описанию; подлинных расхождений за те же 7 суток — 7.
Отсюда два закреплённых свойства:

* порядок признаков — часть правила: совпадение названия проверяется ПЕРЕД
  расхождением;
* причина, взятая из ИСХОДА, помечена отдельно и считается отдельно. При
  повторной выдаче очередь пишет в деталь только пометку круга, поэтому
  «главная причина» по исходам означала бы «самый частый исход» — то есть
  ничего нового, выданное за находку.
"""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

ПУТЬ = (Path(__file__).resolve().parents[2] / "automation" / "local"
        / "editorial-refusal-causes.py")


def _модуль():
    спец = importlib.util.spec_from_file_location("editorial_refusal_causes", ПУТЬ)
    м = importlib.util.module_from_spec(спец)
    спец.loader.exec_module(м)
    return м


МОД = _модуль()


def test_совпавшее_название_не_считается_расхождением():
    """Ровно та ошибка, из-за которой 47 отказов попали не в ту причину."""
    d = ("повтор без изменения условий: прежний отказ 2026-10-23T06:36:02Z,"
         " реестр источников не менялся; Shikimori 52610"
         " (russian «Асы и маленькая Линдан» совпадает) — description null")
    имя, откуда = МОД.причина(d, "SOURCES_MISSING")
    assert откуда == "деталь"
    assert имя == "у источника нет описания", имя


def test_подлинное_расхождение_названия_распознаётся():
    d = ("Shikimori 64375 russian «Хроники Чэнхуана» ≠ название страницы"
         " «Знамение бессмертного»; тождество не доказано")
    имя, откуда = МОД.причина(d, "IDENTITY_UNCLEAR")
    assert имя == "русское название расходится с названием страницы"
    assert откуда == "деталь"


def test_пустая_деталь_берёт_причину_из_исхода_и_это_помечено():
    d = ("повтор без изменения условий: прежний отказ 2026-10-21T10:02:48Z,"
         " реестр источников не менялся")
    имя, откуда = МОД.причина(d, "IDENTITY_UNCLEAR")
    assert откуда == "исход"
    assert имя.startswith("причина не названа в детали")
    assert "IDENTITY_UNCLEAR" in имя


def test_без_исхода_причина_остаётся_неразобранной():
    имя, откуда = МОД.причина("нечто непонятное", "")
    assert (имя, откуда) == ("причина не разобрана", "нет")


def test_страница_404_распознаётся_по_словам_журнала():
    for d in ("https://x/anime/y — HTTP 404 (проверено 2026-10-18).",
              "целевая страница отвечала HTTP 404 (35 раз подряд)",
              "https://x/anime/y снова отдала HTTP 404 (2026-10-19)"):
        имя, откуда = МОД.причина(d, "PAGE_ABSENT")
        assert имя == "страница витрины не отдалась", (d, имя)
        assert откуда == "деталь"


def test_пометка_круга_не_причина():
    assert МОД.по_кругу("повтор без изменения условий: прежний отказ …")
    assert МОД.по_кругу("реестр источников не менялся")
    assert not МОД.по_кругу("описания у источника нет")


def test_шаги_отбираются_по_окну_и_исходу():
    import datetime as dt
    сейчас = dt.datetime.now(dt.timezone.utc)
    записи = [{"site": "s", "work_id": "w", "history": [
        {"at": (сейчас - dt.timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M:%SZ"),
         "outcome": "SOURCES_MISSING", "detail": "description null"},
        {"at": (сейчас - dt.timedelta(days=9)).strftime("%Y-%m-%dT%H:%M:%SZ"),
         "outcome": "SOURCES_MISSING", "detail": "старое"},
        {"at": (сейчас - dt.timedelta(hours=2)).strftime("%Y-%m-%dT%H:%M:%SZ"),
         "outcome": "TEXT_WRITTEN", "detail": "текст"},
    ]}]
    с = сейчас - dt.timedelta(days=7)
    отобрано = МОД.шаги(записи, с, ("SOURCES_MISSING",))
    assert len(отобрано) == 1
    assert отобрано[0][1]["detail"] == "description null"


def test_нет_журнала_это_не_измерено(tmp_path, capsys):
    код = МОД.главное(["--leases", str(tmp_path / "нет.json")])
    assert код == 2
    assert "НЕ ИЗМЕРЕНО" in capsys.readouterr().err


def test_высокая_доля_неназванного_даёт_код_1_и_называет_причину(tmp_path, capsys):
    """Отрицательный контроль: раскладка по исходам не выдаётся за находку."""
    import datetime as dt
    сейчас = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    журнал = tmp_path / "leases.json"
    журнал.write_text(json.dumps({"leases": [
        {"site": "s", "work_id": f"w{i}", "history": [
            {"at": сейчас, "outcome": "SOURCES_MISSING",
             "detail": "повтор без изменения условий: реестр источников не менялся"}]}
        for i in range(9)
    ] + [
        {"site": "s", "work_id": "wx", "history": [
            {"at": сейчас, "outcome": "SOURCES_MISSING",
             "detail": "description null"}]}
    ]}), encoding="utf-8")
    код = МОД.главное(["--leases", str(журнал), "--days", "1"])
    вывод = capsys.readouterr().out
    assert код == 1
    assert "свойство ЖУРНАЛА" in вывод
    assert "среди названных причин главная" in вывод


def test_низкая_доля_неназванного_даёт_вывод_о_главной_причине(tmp_path, capsys):
    import datetime as dt
    сейчас = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    журнал = tmp_path / "leases.json"
    журнал.write_text(json.dumps({"leases": [
        {"site": "s", "work_id": f"w{i}", "history": [
            {"at": сейчас, "outcome": "SOURCES_MISSING",
             "detail": "description null"}]}
        for i in range(8)
    ]}), encoding="utf-8")
    код = МОД.главное(["--leases", str(журнал), "--days", "1"])
    вывод = capsys.readouterr().out
    assert код == 0
    assert "главная причина отказов — у источника нет описания" in вывод
