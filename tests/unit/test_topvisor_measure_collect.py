"""Измерения Топвизора и платный съём в пределах лимита.

Проверяется поведение, а не строки: «не найден» не становится позицией,
архивный и выведенный проекты не читаются, ошибка одного проекта не
останавливает остальные, без лимита владельца платный метод не уходит в сеть,
повтор одной конфигурации за сутки не допускается.
"""
from __future__ import annotations

import datetime as dt
import json

import pytest

from factory.errors import BlockedAccess, BlockedInput, FactoryError
from factory.topvisor import collect, measure
from factory.topvisor.client import TopvisorClient
from factory.topvisor.credentials import TopvisorCredentials

СЕГОДНЯ = dt.date(2026, 10, 26)


def проект(ид, домен, on=0, регионы=True):
    п = {"id": ид, "url": f"https://{домен}/", "site": домен, "on": on}
    if регионы:
        п["searchers"] = [{"key": 0, "regions": [{"index": 7, "key": 225, "name": "Россия",
                                                  "device": 0, "depth": 1}]},
                          {"key": 1, "regions": [{"index": 9, "key": 2643, "name": "Россия",
                                                  "device": 0, "depth": 1}]}]
    return п


class Клиент:
    def __init__(self, проекты, история=None, ошибка_у=None):
        self.проекты = проекты
        self.история = история or {}
        self.ошибка_у = ошибка_у
        self.вызовы = []

    def projects_with_regions(self):
        return self.проекты

    def keywords(self, ид):
        self.вызовы.append(("keywords", ид))
        if ид == self.ошибка_у:
            raise FactoryError("Topvisor вернул ошибку")
        return [{"name": "а"}, {"name": "б"}]

    def history(self, ид, индексы, d1, d2):
        self.вызовы.append(("history", ид, tuple(индексы)))
        return self.история.get((ид, индексы[0]), {})

    def checker_price(self, ids, индексы=None):
        self.вызовы.append(("price", tuple(ids)))
        return 0.18


@pytest.fixture(autouse=True)
def _без_исключений(monkeypatch, tmp_path):
    from factory.cell import withdrawn
    monkeypatch.setattr(withdrawn, "ИСКЛЮЧЕНЫ", {"выведен.test": "тест"})
    monkeypatch.setenv("SITE_CELLS_REGISTRY", str(tmp_path / "нет.json"))
    monkeypatch.setattr(measure, "ЯДРО", tmp_path / "нет-ядра.json")


def test_полосы_и_не_найден():
    assert measure.полоса(1) == "1-3"
    assert measure.полоса(10) == "4-10"
    assert measure.полоса(30) == "11-30"
    assert measure.полоса(50) == "31-50"
    assert measure.полоса(51) == "51+"
    assert measure.полоса(None) == "not_found_within_depth"


def test_история_разбирается_без_выдумывания():
    ответ = {"existsDates": ["2026-10-20", "2026-10-25"], "keywords": [
        {"id": 1, "name": "а", "positionsData": {
            "2026-10-25:5:7": {"position": "4", "relevant_url": "https://x.test/a"},
            "2026-10-20:5:7": {"position": "9"}}},
        {"id": 2, "name": "б", "positionsData": {"2026-10-25:5:7": {"position": "--"}}},
        {"id": 3, "name": "в", "positionsData": {}},
    ]}
    р = measure.разобрать_историю(ответ, {"index": 7})
    по = {к["query"]: к for к in р["keywords"]}
    assert р["last_check"] == "2026-10-25" and р["previous_check"] == "2026-10-20"
    assert по["а"]["position"] == 4 and по["а"]["previous_position"] == 9
    assert по["а"]["band"] == "4-10" and по["а"]["relevant_url"] == "https://x.test/a"
    # '--' — не найден в пределах глубины, не позиция и не «нет в индексе».
    assert по["б"]["position"] is None and по["б"]["found"] is False
    assert по["б"]["band"] == "not_found_within_depth" and по["б"]["measured"] is True
    # Пустая ячейка — не измерено, а не «не найден».
    assert по["в"]["measured"] is False and по["в"]["band"] is None


def test_состояния_и_изоляция_ошибок():
    история = {(2, 7): {"existsDates": ["2026-10-25"], "keywords": [
        {"id": 1, "name": "а", "positionsData": {"2026-10-25:2:7": {"position": "2"}}}]}}
    клиент = Клиент([
        проект(1, "архив.test", on=-1),
        проект(2, "данные.test"),
        проект(3, "сбой.test"),
        проект(4, "пусто.test", регионы=False),
        проект(5, "выведен.test"),
        проект(6, "новый.test"),
    ], история=история, ошибка_у=3)
    итог = measure.измерить(клиент, сегодня=СЕГОДНЯ)
    состояние = {с["domain"]: с["state"] for с in итог["sites"]}
    assert состояние == {"архив.test": "ARCHIVED", "данные.test": "HAS_DATA",
                         "сбой.test": "READ_ERROR", "пусто.test": "NO_REGIONS",
                         "выведен.test": "WITHDRAWN", "новый.test": "NEVER_CHECKED"}
    читали = {в[1] for в in клиент.вызовы}
    assert 1 not in читали, "архивный проект не читается"
    assert 5 not in читали, "выведенный домен не читается регулярно"
    данные = next(с for с in итог["sites"] if с["domain"] == "данные.test")
    assert данные["last_check"] == "2026-10-25"
    assert данные["checks"][0]["bands"] == {"1-3": 1}
    assert данные["price_one_check_rub"] == 0.18


def test_журнал_позиций_без_повторов(tmp_path):
    история = {(2, 7): {"existsDates": ["2026-10-25"], "keywords": [
        {"id": 1, "name": "а", "positionsData": {"2026-10-25:2:7": {"position": "12"}}}]}}
    итог = measure.измерить(Клиент([проект(2, "данные.test")], история=история), сегодня=СЕГОДНЯ)
    measure.записать(итог, tmp_path)
    measure.записать(итог, tmp_path)
    строки = (tmp_path / "positions.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(строки) == 1
    assert json.loads(строки[0])["band"] == "11-30"


# -- платный съём --------------------------------------------------------------

РЕГ_Я = [{"index": 7, "searcher_key": 0}]
РЕГ_G = [{"index": 9, "searcher_key": 1}]
ВЕЧЕР = dt.datetime(2026, 10, 26, 18, 0, tzinfo=dt.timezone.utc)   # 21:00 МСК
ДЕНЬ = dt.datetime(2026, 10, 26, 9, 0, tzinfo=dt.timezone.utc)     # 12:00 МСК


def test_без_лимита_съём_не_запускается(tmp_path):
    with pytest.raises(BlockedInput):
        collect.лимит(tmp_path / "нет.json")
    (tmp_path / "ноль.json").write_text('{"monthly_limit_rub": 0}', encoding="utf-8")
    with pytest.raises(BlockedInput):
        collect.лимит(tmp_path / "ноль.json")


def test_окно_яндекса_и_повтор_за_сутки():
    д, причина = collect.допуск_съёма(project_id=1, regions=РЕГ_Я, цена=5.0, сейчас=ДЕНЬ,
                                      лимит_руб=1000, журнал=[])
    assert д is None and "окна" in причина
    д, _ = collect.допуск_съёма(project_id=1, regions=РЕГ_G, цена=5.0, сейчас=ДЕНЬ,
                                лимит_руб=1000, журнал=[])
    assert д is not None, "Google окном Яндекса не ограничен"
    журнал = [{"at": "2026-10-26T17:00:00Z", "project_id": 1, "regions_indexes": [7], "price_rub": 5}]
    д, причина = collect.допуск_съёма(project_id=1, regions=РЕГ_Я, цена=5.0, сейчас=ВЕЧЕР,
                                      лимит_руб=1000, журнал=журнал)
    assert д is None and "уже снималась" in причина


def test_лимит_и_дневная_доля():
    # 26.10: осталось 6 дней; лимит 60, потрачено 30 → доля (60-30)/6 = 5 в день.
    журнал = [{"at": "2026-10-01T18:00:00Z", "project_id": 9, "regions_indexes": [1], "price_rub": 30}]
    д, причина = collect.допуск_съёма(project_id=1, regions=РЕГ_Я, цена=6.0, сейчас=ВЕЧЕР,
                                      лимит_руб=60, журнал=журнал)
    assert д is None and "дневная доля" in причина
    д, _ = collect.допуск_съёма(project_id=1, regions=РЕГ_Я, цена=5.0, сейчас=ВЕЧЕР,
                                лимит_руб=60, журнал=журнал)
    assert д is not None and д.сумма == 5.0
    д, причина = collect.допуск_съёма(project_id=1, regions=РЕГ_Я, цена=None, сейчас=ВЕЧЕР,
                                      лимит_руб=60, журнал=[])
    assert д is None and "цену" in причина


def test_платный_метод_только_по_своему_допуску():
    журнал = []

    def opener(request, timeout):  # noqa: ARG001
        журнал.append(request.full_url)
        return 200, b'{"result": {"projectsIds": [1]}}'

    клиент = TopvisorClient(credentials=TopvisorCredentials("1", "не-настоящий"), dry_run=False,
                            opener=opener, sleep=lambda _: None)
    допуск = collect.Допуск(1, (7,), 5.0)
    with pytest.raises(BlockedAccess):
        клиент.call("edit/positions_2/checker/go", допуск.payload())
    with pytest.raises(BlockedAccess):
        клиент.call_paid("edit/positions_2/checker/go", допуск.payload(), object())
    чужой = collect.Допуск(2, (7,), 5.0)
    with pytest.raises(BlockedAccess):
        клиент.call_paid("edit/positions_2/checker/go", допуск.payload(), чужой)
    assert журнал == [], "без своего допуска платный метод не уходит в сеть"
    клиент.call_paid("edit/positions_2/checker/go", допуск.payload(), допуск)
    assert len(журнал) == 1 and журнал[0].endswith("edit/positions_2/checker/go")


def test_очередь_яндекс_раньше_google_и_по_визитам():
    измерение = {"sites": [
        {"domain": "малый.test", "state": "NEVER_CHECKED", "keywords_total": 3,
         "regions": [{"index": 1, "searcher_key": 0, "enabled": True, "searcher_enabled": True},
                     {"index": 2, "searcher_key": 1, "enabled": True, "searcher_enabled": True}]},
        {"domain": "большой.test", "state": "HAS_DATA", "keywords_total": 3,
         "regions": [{"index": 3, "searcher_key": 0, "enabled": True, "searcher_enabled": True}]},
        {"domain": "архив.test", "state": "ARCHIVED", "keywords_total": 3, "regions": []},
    ]}
    порядок = [(с["domain"], р[0]["searcher_key"])
               for с, р in collect.очередь(измерение, {"большой.test": 100, "малый.test": 1})]
    assert порядок == [("большой.test", 0), ("малый.test", 0), ("малый.test", 1)]
