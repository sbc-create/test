"""Запрет служебных путей в ответе приложения: слой для витрин на общем ядре.

Измерено 2026-10-05 на открытом lordserial33.biz и на давно открытом
lordfilm47.space: `/healthz` отдавал ДВА заголовка — `index, follow` от
приложения и `noindex, nofollow` от nginx. Запрет держался только на слое
nginx, а ответ противоречил сам себе. У монолитов это делает
`мета_роботов_пути` внутри рантайма; у витрин на ОБЩЕМ ядре такой функции нет,
а править ядро в репозитории сайта запрещено его же правилами.

Проверяется ПОВЕДЕНИЕ обёртки, а не наличие файла.
"""
from __future__ import annotations

import importlib.util
import pathlib

import pytest

КОРЕНЬ = pathlib.Path(__file__).resolve().parents[2]
ШАБЛОН = КОРЕНЬ / "automation" / "host" / "lords_service_robots.py"


def _слой():
    """Свежий экземпляр модуля: он держит состояние подключения в себе."""
    спец = importlib.util.spec_from_file_location("lords_service_robots_проба",
                                                  ШАБЛОН)
    модуль = importlib.util.module_from_spec(спец)
    спец.loader.exec_module(модуль)
    return модуль


class Ядро:
    """Заглушка ядра: класс обработчика с записью отданных заголовков."""

    def __init__(self):
        отданное: list = []

        class Обработчик:
            path = "/"

            def send_header(self, имя, значение):
                отданное.append((имя, значение))

        self.Обработчик = Обработчик
        self.отданное = отданное


def test_служебный_путь_закрывается_приложением():
    слой = _слой()
    ядро = Ядро()
    assert слой.подключить(ядро) is True
    о = ядро.Обработчик()
    for путь in ("/healthz", "/api/titles", "/poster/x.jpg", "/__debug",
                 "/healthz?verbose=1"):
        о.path = путь
        о.send_header("X-Robots-Tag", "index, follow")
    assert ядро.отданное == [("X-Robots-Tag", "noindex, nofollow")] * 5, (
        ядро.отданное)


def test_обычная_страница_не_меняется():
    """Обёртка, а не подмена: без служебного пути ответ прежний байт в байт."""
    слой = _слой()
    ядро = Ядро()
    слой.подключить(ядро)
    о = ядро.Обработчик()
    о.path = "/title/что-нибудь/"
    о.send_header("X-Robots-Tag", "index, follow")
    о.send_header("Content-Type", "text/html")
    assert ядро.отданное == [("X-Robots-Tag", "index, follow"),
                             ("Content-Type", "text/html")]


def test_чужие_заголовки_служебного_пути_не_трогаются():
    слой = _слой()
    ядро = Ядро()
    слой.подключить(ядро)
    о = ядро.Обработчик()
    о.path = "/healthz"
    о.send_header("Content-Type", "application/json")
    assert ядро.отданное == [("Content-Type", "application/json")]


def test_повторное_подключение_не_оборачивает_дважды():
    слой = _слой()
    ядро = Ядро()
    assert слой.подключить(ядро) is True
    assert слой.подключить(ядро) is True
    о = ядро.Обработчик()
    о.path = "/healthz"
    о.send_header("X-Robots-Tag", "index, follow")
    assert ядро.отданное == [("X-Robots-Tag", "noindex, nofollow")]


def test_без_обработчика_отказ_называется():
    слой = _слой()

    class Пустое:
        pass

    assert слой.подключить(Пустое()) is False
    assert "Обработчик" in слой.состояние()["reason"]


def test_перечень_путей_один_с_robots_и_картой_запретов():
    """Своя копия перечня разошлась бы с robots.txt и картой nginx молча."""
    слой = _слой()
    # Без модуля режима слой всё равно закрывает служебные пути: отсутствие
    # перечня — не повод открыть их.
    assert слой.ПО_УМОЛЧАНИЮ == ("/poster/", "/api/", "/healthz", "/__")
    текст = ШАБЛОН.read_text(encoding="utf-8")
    assert "indexing_mode.СЛУЖЕБНЫЕ_ЗАПРЕТЫ" in текст, (
        "перечень обязан браться из того же места, из которого собираются "
        "robots.txt и карта запретов nginx")


def test_копия_в_репозитории_сайта_совпадает_с_шаблоном():
    """Копия общего модуля, разошедшаяся с шаблоном, — дефект учёта."""
    копия = (КОРЕНЬ / "var" / "site-repos" / "lordserial33-biz" / "src"
             / "lords_service_robots.py")
    if not копия.is_file():
        pytest.skip("рабочей копии lordserial33-biz здесь нет")
    assert копия.read_bytes() == ШАБЛОН.read_bytes()
