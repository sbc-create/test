"""Новости доступны штатным CLI, и он не путает их с карточкой аниме.

Почему этот тест существует
---------------------------

Измерено 2026-10-05. Механизм публикации новостей yummyani.org был собран и
проверен, но существовал ТОЛЬКО как инструменты MCP-моста. Редактор, у которого
в сессии инструментов не оказалось, перешёл на доступную ему командную строку,
нашёл там команды с теми же глаголами — `prepare` и `publish` — и выполнил их.
Эти команды пишут накладку описания КАРТОЧКИ (`/anime/<slug>`), а не новость
(`/posts/<slug>`): запись `100kano-radio-57` попала в `title-overlays.json`,
адрес `/anime/100kano-radio-57` ответил 404, потому что карточки с таким
названием в каталоге нет и быть не может.

Корень ошибки — не в инструкции и не в отсутствии фактов у записи, а в
структуре интерфейса: один материал имел два пути доступа, другой — один.
Одинаковые глаголы при разном материале довершили дело.

Поэтому тест закрепляет две вещи:

1. четыре операции новостей есть в штатном CLI;
2. они идут в модуль новостей, а операции карточек — в модуль накладок, и
   подмены между ними нет.

Второе проверяется вызовом, а не чтением текста: присутствие имени в списке
`choices` доказывает только то, что аргумент примут.
"""
from __future__ import annotations

import json

import pytest

from factory.qwen import __main__ as cli
from factory.qwen import editorial, posts

ОПЕРАЦИИ_НОВОСТЕЙ = ("posts-status", "posts-prepare", "posts-publish",
                     "posts-unpublish")


def _варианты() -> list[str]:
    """Список операций — из самого разборщика, а не из копии в тесте."""
    import argparse

    захвачено: list[str] = []
    настоящий = argparse.ArgumentParser.add_argument

    def перехват(сам, *позиционные, **именованные):
        if позиционные and позиционные[0] == "операция":
            захвачено.extend(именованные.get("choices") or [])
        return настоящий(сам, *позиционные, **именованные)

    import unittest.mock as мок
    with мок.patch.object(argparse.ArgumentParser, "add_argument", перехват):
        with pytest.raises(SystemExit):
            cli.главная(["--help"])
    return захвачено


def test_операции_новостей_есть_в_штатном_cli():
    варианты = _варианты()
    отсутствуют = [о for о in ОПЕРАЦИИ_НОВОСТЕЙ if о not in варианты]
    assert not отсутствуют, (
        f"новости недоступны штатным CLI: {отсутствуют}. Редактор без "
        "инструментов MCP снова возьмёт `prepare`/`publish` и запишет "
        "новость в накладку карточки")


@pytest.mark.parametrize("операция,функция", [
    ("posts-status", "состояние"),
    ("posts-publish", "опубликовать"),
    ("posts-unpublish", "снять"),
])
def test_новостные_операции_идут_в_модуль_новостей(операция, функция,
                                                   monkeypatch, capsys):
    """Вызов доходит до модуля новостей, а не до накладок карточек."""
    вызовы: list[tuple] = []

    def подмена(site, slug=None, **именованные):
        вызовы.append((site, slug))
        return {"site": site, "slug": slug or "", "status": "unpublished",
                "problems": [], "published": [], "drafted_in_delivery": [],
                "factory_drafts": [], "delivery_present": True}

    monkeypatch.setattr(posts, функция, подмена)
    # Накладки карточек не должны быть задеты ни одним из этих вызовов.
    for имя in ("подготовить", "публиковать", "снять"):
        def запрет(*_а, имя=имя, **_и):
            raise AssertionError(f"новость ушла в накладку карточки: {имя}")
        monkeypatch.setattr(editorial, имя, запрет)

    аргументы = ["--site", "yummyani.org"]
    if операция != "posts-status":
        аргументы += ["--slug", "proverka"]
    cli.главная([операция, *аргументы])
    assert вызовы and вызовы[0][0] == "yummyani.org"
    ответ = json.loads(capsys.readouterr().out)
    assert ответ["site"] == "yummyani.org"


def test_новость_не_публикуется_без_слага(capsys):
    """Пропущенный слаг — названный отказ, а не запись без адреса."""
    with pytest.raises(SystemExit) as выход:
        cli.главная(["posts-publish", "--site", "yummyani.org"])
    assert выход.value.code == 2
    assert "--slug" in capsys.readouterr().out


def test_тело_новости_не_передаётся_аргументом():
    """Текст едет файлом: иначе он попадает в исполняемую строку и журналы."""
    варианты = _варианты()
    assert "posts-prepare" in варианты
    текст = (cli.__file__ and open(cli.__file__, encoding="utf-8").read())
    assert "--post-file" in текст
    assert "--title" not in текст, (
        "заголовок и текст новости аргументами командной строки не передаются")
