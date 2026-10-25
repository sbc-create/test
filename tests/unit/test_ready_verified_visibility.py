"""Проверенные тексты очереди: видно ли их посетителю.

Повод и собственная ошибка в одном. В реестре 847 записей `READY_VERIFIED` с
пустым `published_at`, и соблазн был объявить это складом недоставленной
работы. Первая редакция инструмента спрашивала `editorial.факты`, а тот для
семейств со снимком (animedia, animego, lords, zona) читает снимок поставщика,
где описаний не бывает вовсе: ответ вышел «animedia.space — 12 из 12 не
видно». Чтение той же выборки со СТРАНИЦЫ дало обратное: видно 11 из 12.

Отсюда закреплено: истина — живая страница (разметка schema.org), а не поле
учёта и не снимок. И третий исход обязателен: страница, которая не ответила, —
«НЕ ПРОВЕРЕНО», это ни доставка, ни потеря.
"""
from __future__ import annotations

import importlib.util
import json
import pathlib

import pytest

КОРЕНЬ = pathlib.Path(__file__).resolve().parents[2]
_путь = КОРЕНЬ / "automation/local/ready-verified-visibility.py"
_спец = importlib.util.spec_from_file_location("ready_verified_visibility", _путь)
ВИД = importlib.util.module_from_spec(_спец)
_спец.loader.exec_module(ВИД)


@pytest.mark.parametrize("готово,живое,ожидание", [
    (473, 473, "ВИДНО"),
    (473, 460, "ВИДНО"),             # типографика витрины — тот же материал
    (662, 0, "НЕ ВИДНО"),            # страница без описания: вот это недоставка
    (662, 120, "РАСХОЖДЕНИЕ"),       # на странице другой, более короткий текст
    (195, 486, "РАСХОЖДЕНИЕ"),       # страница БОГАЧЕ: устарела запись очереди
    (662, None, "НЕ ПРОВЕРЕНО"),
])
def test_исход_по_длинам(готово, живое, ожидание) -> None:
    assert ВИД.видно(готово, живое) == ожидание


def test_допуск_назван_числом_и_применяется_симметрично() -> None:
    д = ВИД.ДОПУСК_ЗНАКОВ
    assert ВИД.видно(500, 500 + д) == "ВИДНО"
    assert ВИД.видно(500, 500 - д) == "ВИДНО"
    assert ВИД.видно(500, 500 + д + 1) == "РАСХОЖДЕНИЕ"


def test_готовые_берутся_по_статусу_и_несут_адрес(tmp_path) -> None:
    реестр = tmp_path / "registry.json"
    реестр.write_text(json.dumps({"items": [
        {"content_id": "a", "status": "READY_VERIFIED", "target_site": "animedia.space",
         "title_id": "x", "canonical_url": "https://animedia.space/title/x",
         "body": " текст ", "published_at": ""},
        {"content_id": "b", "status": "BLOCKED_INSUFFICIENT_FACTS",
         "target_site": "animedia.space", "title_id": "y", "body": "т"},
    ]}, ensure_ascii=False), encoding="utf-8")
    г = ВИД.готовые(реестр)
    assert [з["content_id"] for з in г] == ["a"]
    assert г[0]["знаков"] == 5 and г[0]["site"] == "animedia.space"


def test_сайт_берётся_из_адреса_если_поля_нет(tmp_path) -> None:
    реестр = tmp_path / "registry.json"
    реестр.write_text(json.dumps({"items": [
        {"content_id": "a", "status": "READY_VERIFIED", "title_id": "x",
         "canonical_url": "https://yummyani.site/anime/x", "body": "т"}]}), encoding="utf-8")
    assert ВИД.готовые(реестр)[0]["site"] == "yummyani.site"


def test_нечитаемый_реестр_не_придумывает_записей(tmp_path) -> None:
    assert ВИД.готовые(tmp_path / "нет.json") == []


def test_свод_делит_по_витринам_и_не_смешивает_непроверенное() -> None:
    записи = [
        {"content_id": "1", "site": "animedia.space", "slug": "a", "url": "u", "знаков": 600,
         "published_at": ""},
        {"content_id": "2", "site": "animedia.space", "slug": "b", "url": "u", "знаков": 600,
         "published_at": ""},
        {"content_id": "3", "site": "yummyani.site", "slug": "c", "url": "u", "знаков": 400,
         "published_at": ""},
    ]
    ответы = {"a": 600, "b": 0, "c": None}
    с = ВИД.сверить(записи, читатель=lambda з: ответы[з["slug"]])
    assert с["итог"] == {"ВИДНО": 1, "НЕ ВИДНО": 1, "НЕ ПРОВЕРЕНО": 1}
    assert с["по_сайту"]["animedia.space"] == {"ВИДНО": 1, "НЕ ВИДНО": 1}
    assert с["по_сайту"]["yummyani.site"] == {"НЕ ПРОВЕРЕНО": 1}


def test_расхождение_не_считается_недоставкой() -> None:
    """Главное различение: пустая страница — работа, другой текст — решение.

    Разбор 25.10: среди одиннадцати случаев «текст не совпал» пустых страниц
    НЕ БЫЛО НИ ОДНОЙ, а у четырёх страница была богаче черновика (486 против
    195, 686 против 263). Объявить это недоставкой значило бы послать
    редактора переписывать то, что уже лучше.
    """
    записи = [
        {"content_id": "1", "site": "animedia.space", "slug": "пусто", "url": "u",
         "знаков": 600, "published_at": ""},
        {"content_id": "2", "site": "animedia.space", "slug": "богаче", "url": "u",
         "знаков": 195, "published_at": ""},
    ]
    ответы = {"пусто": 0, "богаче": 486}
    с = ВИД.сверить(записи, читатель=lambda з: ответы[з["slug"]])
    исходы = {з["slug"]: з["исход"] for з in с["строки"]}
    assert исходы == {"пусто": "НЕ ВИДНО", "богаче": "РАСХОЖДЕНИЕ"}


def test_истина_это_страница_а_не_снимок() -> None:
    """Закреплено текстом: инструмент читает страницу, а не снимок подробностей."""
    текст = _путь.read_text(encoding="utf-8")
    assert "_факты_со_страницы" in текст
    assert "editorial.факты(" not in текст.split("def _живое")[1], (
        "снимок поставщика снова стал источником истины — именно эта ошибка "
        "дала «12 из 12 не видно»")


# --- перенаправление 308 -----------------------------------------------------

def test_перенаправление_308_ведёт_к_конечному_адресу(monkeypatch) -> None:
    """У 173 записей в реестре вместо слага стоит UUID, и витрина отвечает 308.

    `urllib` в Python 3.10 этот код не следует (поддержка с 3.11), и первая
    сверка записала эти 173 материала в «НЕ ПРОВЕРЕНО»: честно, но бесполезно —
    материал доставлен, адрес просто другой.
    """
    import urllib.error
    import urllib.request

    def отвечает_308(запрос, timeout=0):
        raise urllib.error.HTTPError(
            запрос.full_url, 308, "Permanent Redirect",
            {"Location": "/anime/nastoyaschiy-slag"}, None)

    monkeypatch.setattr(urllib.request, "urlopen", отвечает_308)
    assert ВИД._после_перенаправления("https://yummyani.site/anime/0191511e") == (
        "https://yummyani.site/anime/nastoyaschiy-slag")


def test_без_перенаправления_адрес_не_меняется(monkeypatch) -> None:
    import urllib.request

    class Ответ:
        def read(self, _n=0):
            return b"<html"

    monkeypatch.setattr(urllib.request, "urlopen", lambda з, timeout=0: Ответ())
    адрес = "https://animedia.space/title/x"
    assert ВИД._после_перенаправления(адрес) == адрес


def test_сеть_не_ответила_адрес_остаётся_прежним(monkeypatch) -> None:
    import urllib.request

    def падает(з, timeout=0):
        raise OSError("сеть недоступна")

    monkeypatch.setattr(urllib.request, "urlopen", падает)
    адрес = "https://animedia.space/title/x"
    assert ВИД._после_перенаправления(адрес) == адрес
