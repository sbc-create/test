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


# --- сетевой обход ----------------------------------------------------------

def test_сетевой_итог_считает_домéны_и_визиты():
    """Вопрос «сколько таких по сети» мерой не задавался: был только --domain.

    Повод — MOD-143 (23.10): зарабатывающий адрес отдаёт 404 и не объявлен в
    карте. Сетевой ответ руками собирается семнадцатью запусками, а
    оборванный на середине перечень выглядит полным.
    """
    итоги = [
        {"домен": "a.test", "проверено": 8, "вне_карт": 2,
         "визиты_вне": 35, "визиты_всего": 220, "адреса_вне": ["/x", "/y"]},
        {"домен": "b.test", "проверено": 8, "вне_карт": 0,
         "визиты_вне": 0, "визиты_всего": 100, "адреса_вне": []},
    ]
    с = ИНСТР.сетевой_итог(итоги)
    assert "домéнов измерено 2" in с
    assert "с адресами вне карт 1" in с
    assert "адресов вне карт 2" in с
    assert "35 из 320" in с and "11 %" in с


def test_неизмеренный_домен_назван_а_не_посчитан_исправным():
    """«Карта не отдалась» и «всё в карте» — разные ответы."""
    итоги = [
        {"домен": "a.test", "проверено": 1, "вне_карт": 0,
         "визиты_вне": 0, "визиты_всего": 10, "адреса_вне": []},
        {"домен": "b.test", "не_измерено": "карта не отдалась"},
    ]
    с = ИНСТР.сетевой_итог(итоги)
    assert "домéнов измерено 1" in с
    assert "НЕ ИЗМЕРЕНО 1: b.test" in с


def test_сетевой_итог_без_визитов_не_делит_на_ноль():
    итоги = [{"домен": "a.test", "проверено": 0, "вне_карт": 0,
              "визиты_вне": 0, "визиты_всего": 0, "адреса_вне": []}]
    assert "0 %" in ИНСТР.сетевой_итог(итоги)


def test_без_домена_и_без_all_мера_отказывается():
    """Молча брать «все» нельзя: это другой вопрос и другая цена."""
    with pytest.raises(SystemExit):
        ИНСТР.main([])


def test_адрес_печатается_целиком_а_не_обрезанным(monkeypatch, tmp_path, capsys):
    """Обрезка делала пять разных адресов серий неразличимыми.

    23.10 я приняла обрезанный адрес серии за страницу произведения и чуть не
    записала «главная зарабатывающая страница вне карты». Это тот же класс
    молчаливой обрезки, что в паспорте домена и в печати цикла.
    """
    длинный = ("/anime/neveroyatnoe-priklyuchenie-dzhodzho-gonka-stalnoy-shar"
               "/season/7/episode/4")
    выгрузка = _выгрузка(tmp_path, [(10, длинный)])
    monkeypatch.setattr(ИНСТР, "карты", lambda д: (
        {"_индекс": {"карт": 1, "lastmod": []},
         "titles.xml": {"адресов": 1, "текст": "<loc>https://a.test/anime/x</loc>"}},
        ""))
    код = ИНСТР.main(["--domain", "a.test", "--file", str(выгрузка)])
    вывод = capsys.readouterr().out
    assert код == 1
    assert длинный in вывод, "адрес обрезан — разные серии станут неразличимы"


@pytest.mark.parametrize("путь,вид", [
    ("/title/x/season-1/episode-3/", "серия"),
    ("/anime/x/season/7/episode/4", "серия"),
    ("/title/x/", "произведение"),
    ("/anime/x", "произведение"),
    ("/search/", "прочее"),
    ("/catalog/", "прочее"),
])
def test_вид_адреса_различает_серию_и_произведение(путь, вид):
    """«Серия вне карты» и «произведение вне карты» — разные утверждения."""
    assert ИНСТР.вид_адреса(путь) == вид


def test_сетевой_итог_печатает_разбивку_и_оговорку():
    """Голое «54 % визитов вне карты» вводит в заблуждение.

    Измерено 23.10: из 7 156 визитов вне карт 6 586 — пять адресов СЕРИЙ
    одной работы на yummyani.site, то есть известный заблокированный
    недостаток, а у Animedia и AnimeGo карта вообще состоит из страниц
    произведений.
    """
    итоги = [{"домен": "a.test", "проверено": 3, "вне_карт": 2,
              "визиты_вне": 100, "визиты_всего": 200,
              "адреса_вне": ["/title/x/season-1/episode-3/", "/title/y/"]}]
    с = ИНСТР.сетевой_итог(итоги)
    assert "из них произведение 1, серия 1" in с
    assert "ДОЛЮ ЧИТАТЬ ТОЛЬКО С РАЗБИВКОЙ" in с
    assert "T087" in с and "MOD-103/106" in с


def test_без_адресов_вне_карт_разбивка_не_печатается():
    итоги = [{"домен": "a.test", "проверено": 3, "вне_карт": 0,
              "визиты_вне": 0, "визиты_всего": 200, "адреса_вне": []}]
    assert "из них" not in ИНСТР.сетевой_итог(итоги)
