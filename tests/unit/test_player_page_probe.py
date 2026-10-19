"""REQ-PLAYER-PROBE: начало показа определяется по запросам к видеопотоку.

Повод (19.10): на вопрос «работает ли сайт» дашборд отвечать не может, а код
ответа 200 не говорит о плеере: плеер витрин — сторонний кадр, страница
рисуется на клиенте. Подтверждением считается не наличие разметки, а то, что
плеер начал забирать видео.

Здесь закрепляется распознавание запросов и честные исходы инструмента. Сам
браузерный проход в модульных тестах не запускается: сеть и браузер — не их
дело (правило `.claude/rules/tests.md`: тесты не выходят в сеть).
"""
from __future__ import annotations

import importlib.util
import pathlib

import pytest

КОРЕНЬ = pathlib.Path(__file__).resolve().parents[2]
_путь = КОРЕНЬ / "automation/local/player-page-probe.py"
_спец = importlib.util.spec_from_file_location("player_page_probe", _путь)
ИНСТР = importlib.util.module_from_spec(_спец)
_спец.loader.exec_module(ИНСТР)


@pytest.mark.parametrize("адрес", [
    "https://cdn.example/hls/master.m3u8",
    "https://cdn.example/dash/manifest.mpd",
    "https://cdn.example/video/file.mp4",
    "https://cdn.example/segment/12",
    "https://cdn.example/chunk-0001.ts",
    "https://cdn.example/hls/x",
])
def test_запросы_потока_узнаются(адрес):
    assert ИНСТР.ПОТОК.search(адрес)


@pytest.mark.parametrize("адрес", [
    "https://yummyani.site/anime/x",
    "https://yummyani.site/_next/static/chunks/main.js",
    "https://mc.yandex.ru/watch/111881037",
    # Служебный API поставщика — это метаданные, а не видео. Считать его
    # потоком значило бы объявлять показ начавшимся на любой странице.
    "https://public-api.cdnvideohub.com/api/v1/x",
])
def test_обычные_запросы_потоком_не_считаются(адрес):
    assert not ИНСТР.ПОТОК.search(адрес)


@pytest.mark.parametrize("адрес", [
    "https://poster.cdnvideohub.com/019f7fa3.webp",
    "https://yummyani.site/poster/abc.webp",
    "https://cdn.example/preview.jpg",
    "https://cdn.example/sprite.png",
])
def test_постеры_и_картинки_потоком_не_считаются(адрес):
    """Ошибка первой редакции: постеры на poster.cdnvideohub.com попадали в
    шаблон по слову «videohub», и проверка срабатывала даже на главной, где
    плеера нет. Проверка, которая не может провалиться, ничего не стоит."""
    поток = bool(ИНСТР.ПОТОК.search(адрес)) and not bool(ИНСТР.НЕ_ПОТОК.search(адрес))
    assert поток is False


@pytest.mark.parametrize("адрес", [
    "https://pagead2.googlesyndication.com/x",
    "https://ads.adfox.ru/banner",
    "https://www.doubleclick.net/x",
])
def test_рекламные_запросы_узнаются(адрес):
    assert ИНСТР.РЕКЛАМА.search(адрес)


def test_реклама_и_поток_не_путаются():
    """Отказ рекламного запроса не должен выглядеть поломкой плеера."""
    адрес = "https://pagead2.googlesyndication.com/pagead/x.mp4"
    assert ИНСТР.РЕКЛАМА.search(адрес)
    # Такой адрес распознаётся и как поток, поэтому порядок проверки в коде
    # важен: рекламные отказы считаются отдельно от неудачных запросов.
    assert ИНСТР.ПОТОК.search(адрес)


def test_оба_устройства_описаны():
    assert set(ИНСТР.УСТРОЙСТВА) == {"телефон", "компьютер"}
    тел = ИНСТР.УСТРОЙСТВА["телефон"]
    пк = ИНСТР.УСТРОЙСТВА["компьютер"]
    assert тел["is_mobile"] is True and пк["is_mobile"] is False
    assert тел["viewport"]["width"] < пк["viewport"]["width"]
    assert "iPhone" in тел["user_agent"] and "Windows" in пк["user_agent"]
    # Своя подпись не притворяется человеком сверх необходимого: UA нужен,
    # чтобы витрина отдала мобильную разметку, и это единственная причина.
    assert "HeadlessChrome" not in тел["user_agent"]


def test_без_адресов_код_2(capsys):
    assert ИНСТР.main([]) == 2
    assert "НЕ ИЗМЕРЕНО" in capsys.readouterr().out


def test_нет_браузера_код_2(monkeypatch, capsys, tmp_path):
    """Отсутствие браузера — «не измерено», а не «плеер не работает»."""
    monkeypatch.setattr(ИНСТР, "ХРОМ_ШАБЛОН", str(tmp_path / "нет*/chrome"))
    код = ИНСТР.main(["--url", "https://example.test/x"])
    assert код == 2
    assert "НЕ ИЗМЕРЕНО" in capsys.readouterr().out
