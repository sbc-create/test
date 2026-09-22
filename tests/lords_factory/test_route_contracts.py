"""Контракты маршрутов и токенов: то, что обязано быть верным до браузера.

Каждая проверка здесь предъявляется парой: на настоящих пакетах она молчит, на
заведомо испорченном входе — срабатывает. Проверка, которая не умеет падать,
ничего не доказывает; этот урок фабрика уже оплатила однажды.
"""

from __future__ import annotations

import importlib.util
import json
import pathlib

import pytest

КОРЕНЬ = pathlib.Path(__file__).resolve().parents[2]
ЯДРО = КОРЕНЬ / "factory" / "templates" / "lords" / "shared"
ПАКЕТЫ = КОРЕНЬ / "factory" / "templates" / "lords"


def _загрузить(имя: str, файл: pathlib.Path):
    spec = importlib.util.spec_from_file_location(имя, файл)
    модуль = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(модуль)
    return модуль


routes = _загрузить("lords_routes", ЯДРО / "routes.py")
contrast = _загрузить("lords_contrast", ЯДРО / "contrast.py")
render = _загрузить("lords_render", ЯДРО / "render.py")


def пакеты() -> list[pathlib.Path]:
    return sorted(п for п in ПАКЕТЫ.iterdir() if п.is_dir() and п.name[:1] == "T"
                  and п.name[1:4].isdigit())


# --- состав маршрутов --------------------------------------------------------

ОБЯЗАТЕЛЬНЫЕ_МАРШРУТЫ = {
    "catalog", "new", "search", "search_empty", "genre", "year", "country",
    "collection", "title_movie", "title_series", "season", "episode",
    "episode_player", "notfound",
}


@pytest.mark.parametrize("пакет", пакеты(), ids=lambda п: п.name[:4])
def test_package_declares_every_route(пакет):
    манифест = json.loads((пакет / "template.json").read_text(encoding="utf-8"))
    объявлено = set(манифест.get("routes") or {})
    отсутствуют = ОБЯЗАТЕЛЬНЫЕ_МАРШРУТЫ - объявлено
    assert not отсутствуют, f"{пакет.name}: не объявлены маршруты {sorted(отсутствуют)}"


@pytest.mark.parametrize("пакет", пакеты(), ids=lambda п: п.name[:4])
def test_route_blocks_are_known_to_the_core(пакет):
    манифест = json.loads((пакет / "template.json").read_text(encoding="utf-8"))
    for имя, блоки in (манифест.get("routes") or {}).items():
        for блок in блоки:
            assert блок["тип"] in render.БЛОКИ, \
                f"{пакет.name}/{имя}: ядро не знает блок {блок['тип']!r}"


@pytest.mark.parametrize("пакет", пакеты(), ids=lambda п: п.name[:4])
def test_route_grids_have_no_orphan_tail(пакет):
    манифест = json.loads((пакет / "template.json").read_text(encoding="utf-8"))
    лестницы = routes.лестницы_из_css((пакет / "layout.css").read_text(encoding="utf-8"))
    беды = routes.проверить(манифест.get("routes") or {}, лестницы)
    assert not беды, f"{пакет.name}: {беды[:2]}"


@pytest.mark.parametrize("пакет", пакеты(), ids=lambda п: п.name[:4])
def test_row_cards_never_sit_in_narrow_columns(пакет):
    """Строка-карточка в узкой колонке обрезает обязательную дату.

    Дефект уже наблюдался на живой витрине и стоил отдельного разбора: на
    320 px колонка сжималась до величины, в которую дата не помещается.
    """
    манифест = json.loads((пакет / "template.json").read_text(encoding="utf-8"))
    лестницы = routes.лестницы_из_css((пакет / "layout.css").read_text(encoding="utf-8"))
    лестницы.update(routes.ЗАПАСНЫЕ_ЛЕСТНИЦЫ)
    беды = []
    for имя, блоки in (манифест.get("routes") or {}).items():
        for блок in блоки:
            if блок.get("грамматика") != "compact" or not блок.get("класс"):
                continue
            for точка, колонок in лестницы.get(блок["класс"], []):
                ширина = routes.ширина_колонки(точка, колонок)
                if ширина < routes.МИН_КОЛОНКА_COMPACT:
                    беды.append(f'{имя}/{блок["класс"]}: {ширина:.0f}px на '
                                f'{точка or 320}px')
    assert not беды, f"{пакет.name}: строка-карточка в узкой колонке — {беды[:3]}"


@pytest.mark.parametrize("пакет", пакеты(), ids=lambda п: п.name[:4])
def test_one_filter_panel_per_route(пакет):
    """На одной странице не может быть двух панелей отбора.

    Две панели — это два независимых состояния, правящих одним перечнем:
    выдача меняется от одной, а живая область сообщает число от другой.
    Проверка действием поймала это на шестнадцати страницах; здесь оно
    ловится до отрисовки.
    """
    манифест = json.loads((пакет / "template.json").read_text(encoding="utf-8"))
    for имя, блоки in (манифест.get("routes") or {}).items():
        панелей = sum(1 for б in блоки if б["тип"] == "filters")
        assert панелей <= 1, f"{пакет.name}/{имя}: панелей отбора {панелей}"


@pytest.mark.parametrize("пакет", пакеты(), ids=lambda п: п.name[:4])
def test_catalog_has_filters_and_listing(пакет):
    """Каталог обязан нести отбор и перечень: это контракт, а не украшение."""
    манифест = json.loads((пакет / "template.json").read_text(encoding="utf-8"))
    типы = [б["тип"] for б in манифест["routes"]["catalog"]]
    assert "filters" in типы, f"{пакет.name}: на каталоге нет панели отбора"
    assert "listing" in типы, f"{пакет.name}: на каталоге нет перечня"
    assert типы.index("filters") < типы.index("listing"), \
        f"{пакет.name}: отбор стоит после перечня"


def test_catalog_openings_are_unique_across_the_pool():
    """Два каталога не могут открываться одинаковой геометрией."""
    подписи = {}
    for пакет in пакеты():
        манифест = json.loads((пакет / "template.json").read_text(encoding="utf-8"))
        подпись = routes.подпись_открытия(манифест["routes"]["catalog"])
        assert подпись not in подписи, \
            f"{пакет.name} открывается так же, как {подписи[подпись]}: {подпись}"
        подписи[подпись] = пакет.name


def test_opening_signature_ignores_data_source():
    """Разный источник данных при той же геометрии — не различие.

    Первая версия подписи учитывала источник, и генератор считал непохожими
    страницы, которые отпечаток первого экрана нашёл совпадающими.
    """
    a = [{"тип": "taxonomy", "источник": "genres", "максимум": 12}]
    b = [{"тип": "taxonomy", "источник": "countries", "максимум": 12}]
    assert routes.подпись_открытия(a) == routes.подпись_открытия(b)
    в = [{"тип": "taxonomy", "источник": "genres", "максимум": 8}]
    assert routes.подпись_открытия(a) != routes.подпись_открытия(в)


def test_orphan_gate_catches_a_broken_route():
    """Гейт одинокого хвоста обязан падать на заведомо испорченном маршруте."""
    испорченный = {"catalog": [
        {"тип": "grid", "заголовок": "Порча", "класс": "g--x", "максимум": 13,
         "грамматика": "poster"}]}
    беды = routes.проверить(испорченный, {"g--x": [[0, 2], [1200, 4]]})
    assert беды, "13 карточек в четыре колонки оставляют одну — не поймано"


def test_page_size_avoids_orphan_on_last_page():
    """Последняя страница пагинации тоже не должна оставлять одну карточку."""
    фикстура = {"items": [{"slug": str(i)} for i in range(135)]}
    блоки = [{"тип": "listing", "на_странице": 24, "колонки": [2, 3, 5]}]
    размер = render._страница_маршрута(блоки, фикстура)
    остаток = 135 % размер or размер
    for колонок in (3, 5):
        assert размер % колонок != 1 and остаток % колонок != 1, \
            f"размер {размер}, остаток {остаток} оставляют одинокий хвост"


def test_trimming_keeps_block_above_its_minimum():
    записи = [{"slug": str(i)} for i in range(7)]
    оставлено = render.без_хвоста(записи, [3], минимум=6)
    assert len(оставлено) == 6, "семь карточек в три колонки обрезаются до шести"
    оставлено = render.без_хвоста(записи, [3], минимум=7)
    assert len(оставлено) == 7, "ниже объявленного минимума резать нельзя"


# --- контраст токенов --------------------------------------------------------

def test_declared_token_pairs_meet_aa():
    отчёт = contrast.проверить(ПАКЕТЫ, ЯДРО)
    assert отчёт["PASS"], отчёт["violations"][:4]


def test_contrast_gate_catches_a_bad_pair(tmp_path):
    """На заведомо нечитаемой паре гейт обязан сработать."""
    пакет = tmp_path / "T099-bad"
    пакет.mkdir()
    (пакет / "tokens.css").write_text(
        ":root{--ink:#777777; --bg:#808080; --card:#808080; --dim:#7a7a7a;\n"
        "--brand:#808080; --brand-ink:#8a8a8a; --brand-text:#7f7f7f; --soft:#808080;}",
        encoding="utf-8")
    беды = contrast.проверить_пакет(пакет, {})
    assert беды, "серое на сером не поймано"
    assert all(б["ratio"] < б["need"] for б in беды)


def test_contrast_threshold_is_not_softened():
    """Порог — величина стандарта, а не настройка под результат."""
    assert contrast.ПОРОГ_ОБЫЧНЫЙ == 4.5
    assert contrast.ПОРОГ_КРУПНЫЙ == 3.0
