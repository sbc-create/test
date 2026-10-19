"""REQ-DEMAND-VS-TEXT: спрос и наличие нашего текста сводятся по slug.

Отбор кандидатов редактора идёт по каталогу, а не по спросу. Инструмент
`automation/local/demand-vs-text.py` сводит карту спроса Метрики (страницы
входа из поиска) с нашими опубликованными текстами и называет, где текста нет
при живом спросе.

Закрепляется главное, в чём легко ошибиться:

* пять страниц серий одного тайтла — ОДИН спрос, а не пять строк;
* `/`, `/catalog`, подборки — спрос, но не спрос на текст произведения;
* наш учёт лежит в разных местах у двух адаптеров, и путаница даёт ложное
  «текста нет» (эта ошибка в инструменте уже была и закреплена тестом).
"""
from __future__ import annotations

import importlib.util
import json
import pathlib
import types

import pytest

КОРЕНЬ = pathlib.Path(__file__).resolve().parents[2]
_путь = КОРЕНЬ / "automation/local/demand-vs-text.py"
_спец = importlib.util.spec_from_file_location("demand_vs_text", _путь)
ИНСТР = importlib.util.module_from_spec(_спец)
_спец.loader.exec_module(ИНСТР)


@pytest.mark.parametrize("путь,ожидание", [
    ("/anime/dzhodzho/season/7/episode/4", "dzhodzho"),
    ("/anime/dzhodzho/season/7", "dzhodzho"),
    ("/anime/dzhodzho", "dzhodzho"),
    ("/title/nekromant/season-1/episode-6/", "nekromant"),
    ("/title/nekromant/", "nekromant"),
    ("/", ""),
    ("/catalog/ongoing", ""),
    ("/collection/series_with_episodes/", ""),
    ("", ""),
])
def test_slug_из_пути(путь, ожидание):
    assert ИНСТР.slug_из_пути(путь) == ожидание


def _мера(строки, измерено=True, **прочее):
    м = {"key": "search_landing_pages", "measured": измерено, "value": строки}
    м.update(прочее)
    return {"domain": "x.test", "measurements": [м]}


def _строка(путь, визиты, источник="organic"):
    return {"dimensions": [{"id": источник, "name": "Search engine traffic"},
                           {"name": путь}],
            "metrics": [визиты, визиты]}


def test_серии_одного_тайтла_складываются():
    по_тайтлам, прочее, почему = ИНСТР.спрос(_мера([
        _строка("/anime/dzhodzho/season/7/episode/4", 2843),
        _строка("/anime/dzhodzho/season/7/episode/3", 1239),
        _строка("/anime/dzhodzho", 100),
    ]))
    assert почему == ""
    assert по_тайтлам == {"dzhodzho": 4182.0}
    assert прочее == {}


def test_непроизведения_отдельно():
    по_тайтлам, прочее, _ = ИНСТР.спрос(_мера([
        _строка("/", 3708), _строка("/catalog/ongoing", 143),
        _строка("/anime/x", 10),
    ]))
    assert по_тайтлам == {"x": 10.0}
    assert прочее == {"/": 3708.0, "/catalog/ongoing": 143.0}


def test_непоисковый_источник_в_спрос_не_идёт():
    """Прямые заходы — не поисковый спрос."""
    по_тайтлам, прочее, _ = ИНСТР.спрос(_мера([
        _строка("/anime/x", 999, источник="direct"),
        _строка("/anime/y", 5),
    ]))
    assert по_тайтлам == {"y": 5.0} and прочее == {}


def test_показатель_не_измерен_даёт_причину():
    по_тайтлам, прочее, почему = ИНСТР.спрос(
        _мера([], измерено=False, state="ИСТОЧНИК_НЕДОСТУПЕН"))
    assert не_пусто(почему) and по_тайтлам == {} and прочее == {}


def не_пусто(значение: str) -> bool:
    return bool(значение and значение.strip())


def test_нет_показателя_вовсе():
    _, _, почему = ИНСТР.спрос({"domain": "x.test", "measurements": []})
    assert "нет страниц входа" in почему


def _сайт(adapter: str, домен: str = "x.test"):
    return types.SimpleNamespace(domain=домен, adapter=adapter, site_id="c-01")


def test_тексты_приложения_читаются_из_накладки(tmp_path, monkeypatch):
    корень = tmp_path / "overlays"
    (корень / "x.test").mkdir(parents=True)
    (корень / "x.test" / "title-overlays.json").write_text(json.dumps(
        {"items": [{"slug": "a", "body": "т"}, {"slug": "b", "body": "т"}]}),
        encoding="utf-8")
    monkeypatch.setattr(ИНСТР.registry, "путь_доставки",
                        lambda s: str(корень / s.domain / "title-overlays.json"))
    monkeypatch.setattr(ИНСТР.registry, "корень_хранилища", lambda a: str(корень))
    тексты, беда = ИНСТР.наши_тексты(_сайт("animedia"))
    assert тексты == {"a", "b"} and беда == ""


def test_учёт_lords_ищется_в_корне_хранилища(tmp_path, monkeypatch):
    """Эта ошибка в инструменте была: учёт искался рядом с доставленным файлом.

    У lords доставленный файл лежит в каталоге данных ЯЧЕЙКИ (/srv/<cell>/data),
    а наш учёт — в корне хранилища адаптера. Поиск рядом с доставленным давал
    «нашего учёта нет» и ложное «текста нет» на всю витрину.
    """
    ячейка = tmp_path / "srv" / "cell" / "data"
    ячейка.mkdir(parents=True)
    (ячейка / "editorial-overrides.json").write_text('{"overrides":{}}',
                                                     encoding="utf-8")
    корень = tmp_path / "overlays"
    (корень / "x.test").mkdir(parents=True)
    (корень / "x.test" / "published.json").write_text(json.dumps(
        {"items": [{"slug": "c", "title_id": "id-c"}]}), encoding="utf-8")
    monkeypatch.setattr(ИНСТР.registry, "путь_доставки",
                        lambda s: str(ячейка / "editorial-overrides.json"))
    monkeypatch.setattr(ИНСТР.registry, "корень_хранилища", lambda a: str(корень))
    тексты, беда = ИНСТР.наши_тексты(_сайт("lords"))
    assert тексты == {"c"} and беда == ""


def test_нет_учёта_называется_причиной(tmp_path, monkeypatch):
    monkeypatch.setattr(ИНСТР.registry, "путь_доставки",
                        lambda s: str(tmp_path / "editorial-overrides.json"))
    monkeypatch.setattr(ИНСТР.registry, "корень_хранилища", lambda a: str(tmp_path))
    тексты, беда = ИНСТР.наши_тексты(_сайт("lords"))
    assert тексты == set() and "учёта нет" in беда


def test_нет_выгрузки_код_2(tmp_path, capsys):
    assert ИНСТР.main(["--file", str(tmp_path / "нет.json")]) == 2
    assert "НЕ ИЗМЕРЕНО" in capsys.readouterr().out


def test_живая_выгрузка_сводится(capsys):
    assert ИНСТР.main(["--top", "3"]) == 0
    вывод = capsys.readouterr().out
    assert "визитов из поиска на произведения без нашего текста" in вывод
