"""Счётчики не получают технических просмотров — это проверяется, а не обещается.

Требование владельца 23.10: «Технические просмотры не должны отправлять
события в Метрику». Браузерная проверка исполняет JavaScript страницы, а
значит и счётчик, поэтому запрет нужен на уровне перехвата запросов. Измерено
23.10: ни один из браузерных инструментов счётчики не блокировал.

Проверяется ПОВЕДЕНИЕ перехватчика на поддельных маршруте и запросе, а не
наличие слова в коде: структурная проверка прошла бы и на модуле, который
список объявил и не применил.
"""
from __future__ import annotations

import importlib.util
import pathlib

КОРЕНЬ = pathlib.Path(__file__).resolve().parents[2]
_путь = КОРЕНЬ / "automation" / "local" / "counter_guard.py"
_спец = importlib.util.spec_from_file_location("counter_guard", _путь)
СТРАЖ = importlib.util.module_from_spec(_спец)
_спец.loader.exec_module(СТРАЖ)

БРАУЗЕРНЫЕ = ("player-page-probe.py", "playback-check.py",
              "mobile-render-probe.py")


class ПоддельныйМаршрут:
    def __init__(self):
        self.оборван = False
        self.продолжен = False

    def abort(self):
        self.оборван = True

    def continue_(self):
        self.продолжен = True


class ПоддельныйЗапрос:
    def __init__(self, url):
        self.url = url


class ПоддельныйКонтекст:
    def __init__(self):
        self.обработчик = None
        self.шаблон = None

    def route(self, шаблон, обработчик):
        self.шаблон = шаблон
        self.обработчик = обработчик


def test_счётчик_узнаётся_по_хосту():
    for адрес in ("https://mc.yandex.ru/watch/1",
                  "http://MC.YANDEX.RU/watch/2",
                  "https://www.googletagmanager.com/gtag/js",
                  "https://top-fwz1.mail.ru/counter"):
        assert СТРАЖ.это_счётчик(адрес), адрес


def test_наши_адреса_не_считаются_счётчиком():
    """Контроль: без него страж обрывал бы и то, что проверяется."""
    for адрес in ("https://animedia.icu/poster/01a1.webp",
                  "https://poster.cdnvideohub.com/01a1.webp",
                  "https://lordfilm.group/title/x/",
                  "https://animedia.icu/catalog/"):
        assert not СТРАЖ.это_счётчик(адрес), адрес


def test_запрос_к_счётчику_обрывается_и_записывается():
    контекст = ПоддельныйКонтекст()
    перехвачено = СТРАЖ.запретить_счётчики(контекст)
    assert контекст.обработчик is not None, "перехват не поставлен"
    маршрут = ПоддельныйМаршрут()
    контекст.обработчик(маршрут, ПоддельныйЗапрос(
        "https://mc.yandex.ru/watch/113288667"))
    assert маршрут.оборван is True
    assert маршрут.продолжен is False
    assert перехвачено == ["https://mc.yandex.ru/watch/113288667"]


def test_обычный_запрос_пропускается():
    контекст = ПоддельныйКонтекст()
    перехвачено = СТРАЖ.запретить_счётчики(контекст)
    маршрут = ПоддельныйМаршрут()
    контекст.обработчик(маршрут, ПоддельныйЗапрос(
        "https://animedia.icu/catalog/"))
    assert маршрут.продолжен is True
    assert маршрут.оборван is False
    assert перехвачено == []


def test_браузерные_инструменты_ставят_запрет():
    """Модуль без применения бесполезен: каждый браузерный инструмент обязан
    поставить перехват. Проверяется вызов, а не упоминание в комментарии."""
    for имя in БРАУЗЕРНЫЕ:
        т = (КОРЕНЬ / "automation" / "local" / имя).read_text(encoding="utf-8")
        assert "_запрет_счётчиков(" in т, f"{имя}: запрет не вызывается"
        вызовы = [с for с in т.splitlines()
                  if "_запрет_счётчиков(" in с and not с.strip().startswith("def")]
        assert вызовы, f"{имя}: есть определение, но нет вызова"
