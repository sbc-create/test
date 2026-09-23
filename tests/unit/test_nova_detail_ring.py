"""Круговой обход добора подробностей: полнота без опоры на признаки.

Почему круг вообще понадобился. Отбор «продолжающихся» брал тех, у кого
доступно меньше заявленного. Но поставщик поднимает `available_episodes_count`
и `episodes_count` ВМЕСТЕ, поэтому выросший сезон в устаревшем снимке выглядит
завершённым — 9 из 9 — и в набор не попадает вообще. Тайтл может стоять на
девяти сериях при двадцати трёх у источника, и ни один отбор по данным этого
не увидит: увидит только тот, кто спросит.

`updated_since` тут тоже не помогает: `updated_at` при выходе серии не меняется.
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

КОРЕНЬ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(КОРЕНЬ))

_спец = importlib.util.spec_from_file_location(
    "nova_detail_backfill", КОРЕНЬ / "automation" / "host" / "nova-detail-backfill.py")
nb = importlib.util.module_from_spec(_спец)
_спец.loader.exec_module(nb)


@pytest.fixture(autouse=True)
def _позиции_в_песочнице(tmp_path, monkeypatch):
    """Ни один тест не должен доставать до боевых файлов позиции.

    Один забытый monkeypatch записал `after: "b"` в рабочее состояние —
    суточный прогон начал бы круг с середины алфавита. Изоляция обязана быть
    свойством набора, а не внимательностью автора теста.
    """
    monkeypatch.setattr(nb, "ПОЗИЦИЯ", tmp_path / "ring-position.json")
    monkeypatch.setattr(nb, "ПОЗИЦИЯ_СВЕЖИХ", tmp_path / "hot-position.json")


def test_боевые_пути_позиции_не_трогаются():
    """Страховка от того, что фикстуру однажды снимут."""
    assert nb.ПОЗИЦИЯ.name == "ring-position.json", (
        "фикстура изоляции не сработала — тест писал бы в боевое состояние")


def _кэш(tmp_path: Path, записи: dict[str, list[dict]]) -> Path:
    кэш = tmp_path / "detail-cache"
    кэш.mkdir()
    for ид, сезоны in записи.items():
        (кэш / f"{ид}.json").write_text(
            json.dumps({"detail": {"seasons": сезоны}}), encoding="utf-8")
    return кэш


def test_завершённый_на_вид_сезон_не_попадает_в_срочные(tmp_path):
    """Тот самый случай, ради которого понадобился круг."""
    кэш = _кэш(tmp_path, {"a": [{"season_number": 1, "available_episodes_count": 9,
                                 "episodes_count": 9}]})
    assert nb._продолжающиеся(["a"], кэш) == []
    # ...но в круге он есть, и потому будет спрошен.
    assert nb._сериалы(["a"], кэш) == ["a"]


def test_кино_в_круг_не_берётся(tmp_path):
    """У полнометражного нечему вырасти, а бюджет оно тратит наравне."""
    кэш = _кэш(tmp_path, {"film": [], "serial": [{"season_number": 1,
                                                  "available_episodes_count": 1,
                                                  "episodes_count": 2}]})
    assert nb._сериалы(["film", "serial"], кэш) == ["serial"]


def test_круг_проворачивается_и_замыкается(tmp_path):
    сезон = [{"season_number": 1, "available_episodes_count": 5, "episodes_count": 5}]
    кэш = _кэш(tmp_path, {и: сезон for и in ("a", "b", "c", "d")})

    первый = nb._круг(["d", "b", "a", "c"], кэш, кроме=set(), сколько=2)
    assert первый == ["a", "b"], "порядок обязан быть устойчивым, а не как в каталоге"
    nb._записать_позицию(первый[-1], len(первый))

    второй = nb._круг(["d", "b", "a", "c"], кэш, кроме=set(), сколько=2)
    assert второй == ["c", "d"]
    nb._записать_позицию(второй[-1], len(второй))

    # Круг замкнулся: следующий отрезок начинается сначала, а не встаёт.
    assert nb._круг(["d", "b", "a", "c"], кэш, кроме=set(), сколько=2) == ["a", "b"]


def test_исчезнувшая_позиция_не_останавливает_круг(tmp_path):
    """Позиция хранится идентификатором, и он может пропасть из каталога."""
    сезон = [{"season_number": 1, "available_episodes_count": 5, "episodes_count": 5}]
    кэш = _кэш(tmp_path, {и: сезон for и in ("a", "c", "d")})
    nb._записать_позицию("b", 1)          # «b» больше нет в каталоге
    assert nb._круг(["a", "c", "d"], кэш, кроме=set(), сколько=1) == ["c"]


def test_срочные_в_круг_не_попадают(tmp_path):
    """Второй запрос в том же прогоне им не нужен — бюджет уходит на круг."""
    сезон = [{"season_number": 1, "available_episodes_count": 5, "episodes_count": 5}]
    кэш = _кэш(tmp_path, {и: сезон for и in ("a", "b", "c")})
    assert nb._круг(["a", "b", "c"], кэш, кроме={"a"}, сколько=2) == ["b", "c"]


def test_понижение_от_прямого_ответа_принимается(tmp_path):
    """Отзыв прав и снятие потока — настоящие события, а не сбой выдачи.

    Безусловный откат любого понижения не пропустил бы настоящий отзыв никогда,
    и витрина показывала бы ссылку на серию, где нечего смотреть. Разделять
    надо по ИСТОЧНИКУ: здесь источник всегда прямой ответ поставщика.
    """
    кэш = _кэш(tmp_path, {"a": [{"season_number": 1, "available_episodes_count": 218,
                                 "episodes_count": 218}]})
    прежние = {"a": nb._состав_сезонов("a", кэш)}
    (кэш / "a.json").write_text(json.dumps(
        {"detail": {"seasons": [{"season_number": 1, "available_episodes_count": 50,
                                 "episodes_count": 218}]}}), encoding="utf-8")
    итог = nb._снижения(прежние, кэш)
    assert nb._состав_сезонов("a", кэш)[1][0] == 50, "прямой ответ не откатывается"
    assert итог["count"] == 1 and итог["seasons"][0]["from"] == 218
    assert итог["seasons"][0]["to"] == 50, "снижение обязано попасть в отчёт"


def test_рост_числа_серий_снижением_не_считается(tmp_path):
    кэш = _кэш(tmp_path, {"a": [{"season_number": 1, "available_episodes_count": 9,
                                 "episodes_count": 9}]})
    прежние = {"a": nb._состав_сезонов("a", кэш)}
    (кэш / "a.json").write_text(json.dumps(
        {"detail": {"seasons": [{"season_number": 1, "available_episodes_count": 23,
                                 "episodes_count": 23}]}}), encoding="utf-8")
    assert nb._снижения(прежние, кэш)["count"] == 0
    assert nb._состав_сезонов("a", кэш)[1][0] == 23


def test_круг_выключается_только_нулём(tmp_path):
    """Ноль выключает; отрицательное значит «весь круг за прогон»."""
    сезон = [{"season_number": 1, "available_episodes_count": 1, "episodes_count": 2}]
    кэш = _кэш(tmp_path, {и: сезон for и in ("a", "b", "c")})
    assert nb._круг(["a", "b", "c"], кэш, кроме=set(), сколько=0) == []
    assert nb._круг(["a", "b", "c"], кэш, кроме=set(), сколько=-1) == ["a", "b", "c"]


def test_весь_круг_не_дублирует_записи(tmp_path):
    """Замыкание не должно добавлять те же идентификаторы второй раз."""
    сезон = [{"season_number": 1, "available_episodes_count": 1, "episodes_count": 2}]
    кэш = _кэш(tmp_path, {и: сезон for и in ("a", "b", "c")})
    nb._записать_позицию("b", 1)
    отрезок = nb._круг(["a", "b", "c"], кэш, кроме=set(), сколько=-1)
    assert sorted(отрезок) == ["a", "b", "c"]
    assert len(отрезок) == len(set(отрезок))


def test_свежие_отбираются_по_году_из_списка():
    """Год приходит со списком и не стоит ни одного запроса к источнику."""
    записи = [
        {"external_id": "s-new", "is_series": True, "year": 2026},
        {"external_id": "s-old", "is_series": True, "year": 2015},
        {"external_id": "film", "is_series": False, "year": 2026},
        {"is_series": True, "year": 2026},                    # без идентификатора
    ]
    assert nb._свежие_сериалы(записи, 2025) == ["s-new"]


def test_два_круга_идут_по_своим_позициям(tmp_path):
    """Общая позиция на два круга означала бы, что один тянет другой назад."""
    свежие = ["h1", "h2", "h3"]
    все = ["a1", "a2", "a3"]
    первый_свежий = nb._круг(свежие, кроме=set(), сколько=1,
                             позиция=nb.ПОЗИЦИЯ_СВЕЖИХ)
    nb._записать_позицию(первый_свежий[-1], 1, nb.ПОЗИЦИЯ_СВЕЖИХ)
    assert первый_свежий == ["h1"]
    # Полный круг не сдвинулся от чужой позиции.
    assert nb._круг(все, кроме=set(), сколько=1, позиция=nb.ПОЗИЦИЯ) == ["a1"]
    # И свежий продолжает со своей.
    assert nb._круг(свежие, кроме=set(), сколько=1,
                    позиция=nb.ПОЗИЦИЯ_СВЕЖИХ) == ["h2"]
