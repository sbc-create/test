"""REQ-EDITOR-LIVE-PROOF: опубликованное проверяется на живой странице отдельно.

Прогон редактора ставит себе отметку `public_page_verified`. Проверяющий и
проверяемый — одно лицо, поэтому нужна независимая сверка: взять адреса из
прогонов, достать НАШУ запись из хранилища витрины и найти её текст у читателя.

Два вида материала различаются по журналу витрины, и это главное, в чём
инструмент уже один раз ошибся:

* описание произведения лежит списком в накладке и видно в HTML;
* комментарий лежит СЛОВАРЁМ по slug и рисуется на стороне клиента — по HTML
  его проверить нельзя, нужен браузер (измерено 09.10).

Первая редакция ждала список в обоих хранилищах и выдала 24 ложных «не
измерено»; вторая искала комментарий в HTML и выдала 24 ложных «отказа». Оба
случая закреплены тестами.
"""
from __future__ import annotations

import datetime as dt
import importlib.util
import json
import pathlib
import types

import pytest

КОРЕНЬ = pathlib.Path(__file__).resolve().parents[2]
_путь = КОРЕНЬ / "automation/local/published-text-live-check.py"
_спец = importlib.util.spec_from_file_location("published_text_live_check", _путь)
ИНСТР = importlib.util.module_from_spec(_спец)
_спец.loader.exec_module(ИНСТР)

ТЕЛО = "Небольшое уточнение к завязке: пингвина-андроида собирает отец."


def _прогон(каталог: pathlib.Path, метка: str, адреса: list[str]) -> None:
    (каталог / f"{метка}.run.json").write_text(json.dumps(
        {"run_id": метка, "self_report": {"urls": адреса}}), encoding="utf-8")


def test_адреса_берутся_за_окно_и_без_повторов(tmp_path):
    сейчас = dt.datetime(2026, 10, 19, 12, 0, tzinfo=dt.timezone.utc)
    _прогон(tmp_path, "20261019T110000Z", ["https://a.test/anime/x"])
    _прогон(tmp_path, "20261019T113000Z", ["https://a.test/anime/x",
                                           "https://a.test/anime/y"])
    _прогон(tmp_path, "20261018T110000Z", ["https://a.test/anime/старый"])
    (tmp_path / "мусор.run.json").write_text("{}", encoding="utf-8")
    итог = ИНСТР.адреса_прогонов(6, сейчас=сейчас, каталог=tmp_path)
    assert итог == ["https://a.test/anime/x", "https://a.test/anime/y"]


@pytest.mark.parametrize("адрес,ожидание", [
    ("https://a.test/anime/perepoloh-minori", "perepoloh-minori"),
    ("https://a.test/title/nekromant/", "nekromant"),
    ("https://a.test/title/nekromant/season-1/episode-2/", "nekromant"),
    ("https://a.test/catalog", ""),
])
def test_slug_из_адреса(адрес, ожидание):
    assert ИНСТР.slug_из_адреса(адрес) == ожидание


def _склад(tmp_path, monkeypatch, *, журнал: list[dict],
           накладка=None, комментарии=None):
    каталог = tmp_path / "overlays" / "a.test"
    каталог.mkdir(parents=True)
    if накладка is not None:
        (каталог / "title-overlays.json").write_text(
            json.dumps({"items": накладка}), encoding="utf-8")
    if комментарии is not None:
        (каталог / "comment-drafts.json").write_text(
            json.dumps({"site": "a.test", "items": комментарии}), encoding="utf-8")
    (каталог / "history.jsonl").write_text(
        "\n".join(json.dumps(з, ensure_ascii=False) for з in журнал) + "\n",
        encoding="utf-8")
    сайт = types.SimpleNamespace(domain="a.test", adapter="animedia", site_id="c-01")
    monkeypatch.setattr(ИНСТР.registry, "собрать", lambda **кв: [сайт])
    monkeypatch.setattr(ИНСТР.registry, "корень_хранилища",
                        lambda a: str(tmp_path / "overlays"))
    monkeypatch.setattr(ИНСТР.registry, "путь_доставки",
                        lambda s: str(каталог / "title-overlays.json"))
    return каталог


def test_комментарии_читаются_из_словаря(tmp_path, monkeypatch):
    """Та самая ошибка: `items` комментариев — словарь по slug, не список."""
    _склад(tmp_path, monkeypatch,
           журнал=[{"slug": "x", "op": "publish-comment"}],
           накладка=[],
           комментарии={"x": {"slug": "x", "body": ТЕЛО}})
    склад = ИНСТР.склад_витрины("a.test")
    assert склад["комментарии"]["x"] == [ТЕЛО]
    assert склад["журнал"]["x"] == "publish-comment"


def test_описания_читаются_из_списка(tmp_path, monkeypatch):
    _склад(tmp_path, monkeypatch,
           журнал=[{"slug": "x", "op": "publish"}],
           накладка=[{"slug": "x", "body": ТЕЛО}],
           комментарии={})
    склад = ИНСТР.склад_витрины("a.test")
    assert склад["описания"]["x"] == ТЕЛО


def test_нет_журнала_витрины_не_измерено(tmp_path, monkeypatch):
    каталог = tmp_path / "overlays" / "a.test"
    каталог.mkdir(parents=True)
    сайт = types.SimpleNamespace(domain="a.test", adapter="animedia", site_id="c-01")
    monkeypatch.setattr(ИНСТР.registry, "собрать", lambda **кв: [сайт])
    monkeypatch.setattr(ИНСТР.registry, "корень_хранилища",
                        lambda a: str(tmp_path / "overlays"))
    monkeypatch.setattr(ИНСТР.registry, "путь_доставки",
                        lambda s: str(каталог / "title-overlays.json"))
    assert "журнал витрины не прочитан" in ИНСТР.склад_витрины("a.test")["почему"]


def test_описание_видно(tmp_path, monkeypatch):
    _склад(tmp_path, monkeypatch, журнал=[{"slug": "x", "op": "publish"}],
           накладка=[{"slug": "x", "body": ТЕЛО}], комментарии={})
    monkeypatch.setattr(ИНСТР, "страница",
                        lambda а: (f"<p>{ТЕЛО}</p>", ""))
    итог = ИНСТР.проверить(["https://a.test/anime/x"])[0]
    assert итог["итог"] == "видно" and итог["вид"] == "описание"


def test_описание_не_видно(tmp_path, monkeypatch):
    """Отрицательный контроль: отсутствие текста обязано давать отказ."""
    _склад(tmp_path, monkeypatch, журнал=[{"slug": "x", "op": "publish"}],
           накладка=[{"slug": "x", "body": ТЕЛО}], комментарии={})
    monkeypatch.setattr(ИНСТР, "страница", lambda а: ("<p>совсем другое</p>", ""))
    итог = ИНСТР.проверить(["https://a.test/anime/x"])[0]
    assert итог["итог"] == "отказ" and "описание" in итог["почему"]


def test_мнемоники_разворачиваются(tmp_path, monkeypatch):
    тело = 'Кавычки «ёлочки» и тире — вот так'
    _склад(tmp_path, monkeypatch, журнал=[{"slug": "x", "op": "publish"}],
           накладка=[{"slug": "x", "body": тело}], комментарии={})
    monkeypatch.setattr(ИНСТР, "страница",
                        lambda а: ("<p>Кавычки &laquo;ёлочки&raquo; и тире &mdash; вот так</p>", ""))
    assert ИНСТР.проверить(["https://a.test/anime/x"])[0]["итог"] == "видно"


def test_комментарий_без_браузера_не_измерен(tmp_path, monkeypatch):
    """Вторая ошибка инструмента: по HTML комментарий отказом считать нельзя."""
    _склад(tmp_path, monkeypatch, журнал=[{"slug": "x", "op": "publish-comment"}],
           накладка=[], комментарии={"x": {"slug": "x", "body": ТЕЛО}})
    def нельзя(а):
        raise AssertionError("страница не должна запрашиваться для комментария")
    monkeypatch.setattr(ИНСТР, "страница", нельзя)
    итог = ИНСТР.проверить(["https://a.test/anime/x"])[0]
    assert итог["итог"] == "не измерено"
    assert "на стороне клиента" in итог["почему"]


def test_комментарий_с_браузером_передаётся_инструменту(tmp_path, monkeypatch):
    _склад(tmp_path, monkeypatch, журнал=[{"slug": "x", "op": "publish-comment"}],
           накладка=[], комментарии={"x": {"slug": "x", "body": ТЕЛО}})
    вызовы = []

    def подделка(домен, slug, тела):
        вызовы.append((домен, slug, тела[0][:20]))
        return {"итог": "видно", "почему": ""}

    monkeypatch.setattr(ИНСТР, "_браузером", подделка)
    итог = ИНСТР.проверить(["https://a.test/anime/x"], браузер=True)[0]
    assert итог["итог"] == "видно"
    assert вызовы and вызовы[0][1] == "x"


def test_нет_записи_в_журнале_не_измерено(tmp_path, monkeypatch):
    _склад(tmp_path, monkeypatch, журнал=[{"slug": "другой", "op": "publish"}],
           накладка=[{"slug": "x", "body": ТЕЛО}], комментарии={})
    итог = ИНСТР.проверить(["https://a.test/anime/x"])[0]
    assert итог["итог"] == "не измерено"
    assert "нет записи" in итог["почему"]


def test_нет_адресов_код_2(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(ИНСТР, "ПРОГОНЫ", tmp_path)
    monkeypatch.setattr(ИНСТР, "адреса_прогонов", lambda *а, **кв: [])
    assert ИНСТР.main(["--hours", "3"]) == 2
    assert "НЕ ИЗМЕРЕНО" in capsys.readouterr().out
