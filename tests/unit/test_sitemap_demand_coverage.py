"""REQ-SITEMAP-DEMAND: карта проверяется по спросу, а не по размеру.

Повод (19.10): карта серий yummyani.site отдаёт 1 663 адреса и `lastmod` индекса
2026-08-21, и пять страниц серий ДжоДжо — 66 % поисковых входов витрины — в ней
отсутствуют. Инструмент берёт страницы входа из выгрузки кабинета и ищет их в
картах: 95 % измеренных визитов приходят на страницы, которых нет ни в одной
карте. На yummyani7.site с теми же проверками — 0 %.

Закрепляется: сравнение путей с учётом слеша и экранирования; главная из
проверки исключается (она в карте всегда); «карта не отдалась» и «нет страниц
входа» — «не измерено», а не «покрытие полное».
"""
from __future__ import annotations

import importlib.util
import json
import pathlib

import pytest

КОРЕНЬ = pathlib.Path(__file__).resolve().parents[2]
_путь = КОРЕНЬ / "automation/local/sitemap-demand-coverage.py"
_спец = importlib.util.spec_from_file_location("sitemap_demand_coverage", _путь)
ИНСТР = importlib.util.module_from_spec(_спец)
_спец.loader.exec_module(ИНСТР)

КАРТЫ = {
    "_индекс": {"карт": 2, "lastmod": ["2026-10-18"]},
    "titles.xml": {"адресов": 2, "текст":
                   "<loc>https://a.test/anime/x</loc><loc>https://a.test/anime/y/</loc>"},
    "episodes.xml": {"адресов": 1, "текст":
                     "<loc>https://a.test/anime/x/season/1/episode/2</loc>"},
}


@pytest.mark.parametrize("путь,ожидание", [
    ("/anime/x", ["titles.xml"]),
    ("/anime/y", ["titles.xml"]),            # в карте со слешем
    ("/anime/y/", ["titles.xml"]),
    ("/anime/x/season/1/episode/2", ["episodes.xml"]),
    ("/anime/нет-такого", []),
])
def test_поиск_пути_в_картах(путь, ожидание):
    assert ИНСТР.в_карте(путь, КАРТЫ) == ожидание


def test_экранированный_путь_находится():
    карты = {"titles.xml": {"текст": "<loc>https://a.test/anime/%D1%85</loc>"}}
    assert ИНСТР.в_карте("/anime/х", карты) == ["titles.xml"]


def _выгрузка(tmp_path, строки, измерено=True):
    п = tmp_path / "cabinet.json"
    п.write_text(json.dumps({"domains": [{"domain": "a.test", "measurements": [
        {"key": "search_landing_pages", "measured": измерено,
         "state": "" if измерено else "ИСТОЧНИК_НЕДОСТУПЕН",
         "value": [{"dimensions": [{"id": "organic"}, {"name": путь}],
                    "metrics": [визиты]} for визиты, путь in строки]}]}]}),
        encoding="utf-8")
    return п


def test_страницы_спроса_по_визитам(tmp_path):
    п = _выгрузка(tmp_path, [(10, "/anime/a"), (99, "/anime/b"), (5, "/anime/c")])
    строки, беда = ИНСТР.страницы_спроса(п, "a.test", 2)
    assert беда == ""
    assert строки == [(99.0, "/anime/b"), (10.0, "/anime/a")]


def test_главная_в_проверку_не_идёт(tmp_path):
    """Главная есть в карте всегда, и спроса на проверку не создаёт."""
    п = _выгрузка(tmp_path, [(500, "/"), (10, "/anime/a")])
    строки, _ = ИНСТР.страницы_спроса(п, "a.test", 5)
    assert [путь for _, путь in строки] == ["/anime/a"]


def test_непоисковый_источник_не_идёт(tmp_path):
    п = tmp_path / "cabinet.json"
    п.write_text(json.dumps({"domains": [{"domain": "a.test", "measurements": [
        {"key": "search_landing_pages", "measured": True, "value": [
            {"dimensions": [{"id": "direct"}, {"name": "/anime/a"}], "metrics": [99]},
            {"dimensions": [{"id": "organic"}, {"name": "/anime/b"}], "metrics": [5]}]}]}]}),
        encoding="utf-8")
    строки, _ = ИНСТР.страницы_спроса(п, "a.test", 5)
    assert [путь for _, путь in строки] == ["/anime/b"]


def test_показатель_не_измерен_даёт_причину(tmp_path):
    п = _выгрузка(tmp_path, [(10, "/anime/a")], измерено=False)
    строки, беда = ИНСТР.страницы_спроса(п, "a.test", 5)
    assert строки == [] and "ИСТОЧНИК_НЕДОСТУПЕН" in беда


def test_чужой_домен_даёт_причину(tmp_path):
    п = _выгрузка(tmp_path, [(10, "/anime/a")])
    строки, беда = ИНСТР.страницы_спроса(п, "нет.test", 5)
    assert строки == [] and "нет" in беда


def test_карта_не_отдалась_не_измерено(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(ИНСТР, "_достать", lambda адрес, предел=60: ("", "код ответа 503"))
    п = _выгрузка(tmp_path, [(10, "/anime/a")])
    код = ИНСТР.main(["--domain", "a.test", "--file", str(п)])
    assert код == 2 and "НЕ ИЗМЕРЕНО" in capsys.readouterr().out


def test_полное_покрытие_код_0(monkeypatch, tmp_path, capsys):
    индекс = "<loc>https://a.test/sitemap/titles.xml</loc><lastmod>2026-10-18</lastmod>"
    карта = "<loc>https://a.test/anime/a</loc>"

    def достать(адрес, предел=60):
        return (индекс if адрес.endswith("/sitemap.xml") else карта), ""

    monkeypatch.setattr(ИНСТР, "_достать", достать)
    п = _выгрузка(tmp_path, [(10, "/anime/a")])
    assert ИНСТР.main(["--domain", "a.test", "--file", str(п)]) == 0
    assert "вне карт 0" in capsys.readouterr().out


def test_страница_вне_карты_код_1(monkeypatch, tmp_path, capsys):
    индекс = "<loc>https://a.test/sitemap/titles.xml</loc><lastmod>2026-08-21</lastmod>"

    def достать(адрес, предел=60):
        return (индекс if адрес.endswith("/sitemap.xml")
                else "<loc>https://a.test/anime/другое</loc>"), ""

    monkeypatch.setattr(ИНСТР, "_достать", достать)
    п = _выгрузка(tmp_path, [(2843, "/anime/a/season/7/episode/4")])
    assert ИНСТР.main(["--domain", "a.test", "--file", str(п)]) == 1
    вывод = capsys.readouterr().out
    assert "НЕТ НИ В ОДНОЙ КАРТЕ" in вывод and "2843" in вывод
