"""Одна страница — один ключ задания, как бы её ни записали.

Очередь ищет существующее задание по адресу, и одна и та же страница,
записанная двумя способами, давала ДВА живых задания. Измерено 2026-10-09 на
живом реестре: восемь групп дублей, среди них
`yummyani.org/anime/ledyanaya-stena-2` — одно задание с относительным
`/anime/ledyanaya-stena-2`, другое с абсолютным
`https://yummyani.org/anime/ledyanaya-stena-2`. Это одна страница, два задания
и два исполнителя, не знающих друг о друге.

Форма адреса берётся из реестра, а не перечисляется в мосте: второй перечень
разошёлся бы с первым, и ключ поиска стал бы зависеть от того, кто его считал.
"""

from __future__ import annotations

import pytest

from factory.qwen import queue_bridge as qb


@pytest.mark.parametrize("адрес", [
    "/anime/ledyanaya-stena-2",
    "https://yummyani.org/anime/ledyanaya-stena-2",
    "https://yummyani.org/anime/ledyanaya-stena-2/",
])
def test_обе_записи_одной_страницы_дают_один_ключ(адрес):
    н, _ = qb.нормализовать_адрес("yummyani.org", адрес)
    assert н == "https://yummyani.org/anime/ledyanaya-stena-2"


def test_форма_семейства_доводится_до_проверенной():
    """У Lords карточка живёт по /title/<слаг>/ — адрес без слеша отвечает 308.

    Измерено на `request-01b4575857beada5`:
    `https://lordfilm47.space/title/specnaz-novobrancy` → 308 на форму со
    слешем. Задание, записанное адресом-редиректом, проверяется не на той
    странице, на которой публикуется.
    """
    н, заметка = qb.нормализовать_адрес(
        "lordfilm47.space", "https://lordfilm47.space/title/specnaz-novobrancy")
    assert н == "https://lordfilm47.space/title/specnaz-novobrancy/"
    assert "форме семейства" in заметка


def test_страница_серии_к_карточке_не_приводится():
    """Адрес серии — не карточка. Приведение подменило бы задание."""
    н, заметка = qb.нормализовать_адрес(
        "lordfilm47.space", "/title/specnaz-novobrancy/season-1/episode-1")
    assert н == ("https://lordfilm47.space/title/specnaz-novobrancy/"
                 "season-1/episode-1")
    assert "абсолютный" in заметка


def test_чужой_хост_не_переписывается_на_свой():
    """Опечатка в домене не превращается молча в свой адрес.

    Иначе задание, заведённое по чужому домену, тихо стало бы заданием по
    своему — и проверялось бы не на той странице, которую просили.
    """
    н, заметка = qb.нормализовать_адрес(
        "yummyani.org", "https://yummyani.site/anime/009-1")
    assert н == "https://yummyani.site/anime/009-1"
    assert "не равен домену" in заметка


def test_неизвестная_форма_семейства_не_угадывается(monkeypatch):
    from factory.qwen import registry

    monkeypatch.setitem(registry.ФОРМА_АДРЕСА, "animedia", None)
    н, заметка = qb.нормализовать_адрес("animedia.icu", "/title/пример/")
    assert н == "https://animedia.icu/title/пример/"
    assert "не проверена" in заметка


def test_пустой_адрес_остаётся_пустым():
    н, заметка = qb.нормализовать_адрес("yummyani.org", "   ")
    assert н == ""
    assert заметка == "адрес пуст"


def test_отказ_реестра_адрес_не_чинит(monkeypatch):
    import factory.qwen.editorial as ред

    monkeypatch.setattr(ред, "_сайт",
                        lambda *а, **к: (_ for _ in ()).throw(RuntimeError("нет")))
    н, заметка = qb.нормализовать_адрес("незнакомая.test", "/anime/x")
    assert н == "/anime/x"
    assert "оставлен как передан" in заметка


def test_поиск_и_регистрация_нормализуют_одинаково(monkeypatch):
    """Разойдясь, они снова завели бы дубль: поиск не нашёл, регистрация создала."""
    видел = []
    monkeypatch.setattr(qb, "_вызвать",
                        lambda з, **к: видел.append(з) or {"found": False})
    monkeypatch.setattr(qb, "доставка_описаний", lambda site: (True, ""))
    qb.найти(site="yummyani.org", canonical_url="/anime/x")
    qb.завести(site="yummyani.org", canonical_url="/anime/x", headline="X")
    assert видел[0]["canonical_url"] == видел[1]["canonical_url"]
    assert видел[0]["canonical_url"] == "https://yummyani.org/anime/x"
