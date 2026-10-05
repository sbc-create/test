"""Запрет служебных путей живёт В ВИТРИНЕ, а не только в слое nginx.

Что измерено
------------

2026-10-05, сразу после открытия an1mego.site и animeg0.site штатной
операцией:

    GET https://an1mego.site/healthz
      X-Robots-Tag: index, follow          <- витрина
      X-Robots-Tag: noindex, nofollow      <- слой nginx

То же на `/api/` и `/poster/`, и то же у УЖЕ ОТКРЫТОГО соседа `an1meg0.site`:
дефект семейный. Пока домен был закрыт, противоречия не было — витрина
отдавала `noindex, nofollow` на всех путях, и открытие его обнажило.

Фактически путь закрыт: обходчик разрешает такую пару по более строгому
значению, и эти пути вдобавок стоят в `Disallow` у `robots.txt`. Но
противоречивая пара на производственном ответе — дефект, а не особенность, и
держать запрет служебных путей в одном слое из двух нельзя: слой nginx
принадлежит ХОСТУ, а эти пути — ВИТРИНЕ.
"""
from __future__ import annotations

import pathlib
import re

import pytest

from factory.cell.nginx_indexing import СЛУЖЕБНЫЕ

КОРЕНЬ = pathlib.Path(__file__).resolve().parents[2]
РЕПОЗИТОРИИ = ("an1mego-site", "animeg0-site", "an1meg0-site")
ТОЧКА = "src/animego-frontend.py"


def _точка(имя: str) -> pathlib.Path:
    п = КОРЕНЬ / "var" / "site-repos" / имя / ТОЧКА
    if not п.is_file():
        pytest.skip(f"рабочей копии {имя} здесь нет")
    return п


@pytest.mark.parametrize("имя", РЕПОЗИТОРИИ)
def test_заголовок_зависит_от_пути(имя):
    текст = _точка(имя).read_text(encoding="utf-8")
    assert "def мета_роботов_пути(" in текст, (
        "витрина не различает служебные пути: запрет на них останется только "
        "в слое nginx, который принадлежит хосту, а не витрине")
    отдачи = re.findall(r'send_header\("X-Robots-Tag", ([^)]+\)?)\)', текст)
    # Ровно две отдачи: общая по пути и ЗАШИТАЯ в ветви постера (D180).
    assert 'мета_роботов_пути(self.path or "/")' in "".join(отдачи), отдачи
    assert 'мета_роботов()' not in [о.strip() for о in отдачи], (
        "осталась отдача заголовка без учёта пути")
    assert '"noindex, nofollow"' in [о.strip() for о in отдачи], (
        "зашитый запрет ветви постера пропал: он обязан быть при любом режиме")


@pytest.mark.parametrize("имя", РЕПОЗИТОРИИ)
def test_перечень_служебных_путей_совпадает_со_слоем_nginx(имя):
    """Три места об одном. Расхождение значит «закрыт не везде»."""
    текст = _точка(имя).read_text(encoding="utf-8")
    м = re.search(r"СЛУЖЕБНЫЕ_ПУТИ = \(([^)]*)\)", текст)
    assert м, "витрина не объявляет перечень служебных путей"
    объявлено = tuple(re.findall(r'"([^"]+)"', м.group(1)))
    assert объявлено == tuple(СЛУЖЕБНЫЕ), (
        f"{имя}: витрина объявляет {объявлено}, а слой nginx {tuple(СЛУЖЕБНЫЕ)}")


@pytest.mark.parametrize("имя", РЕПОЗИТОРИИ)
def test_поведение_функции(имя):
    """Проверка поведением, а не присутствием текста.

    Берутся ровно два определения из точки входа и исполняются с подставной
    `мета_роботов`: импортировать витрину целиком здесь нельзя — ей нужны
    окружение, снимок каталога и конфигурация площадки.
    """
    текст = _точка(имя).read_text(encoding="utf-8")
    начало = текст.index("СЛУЖЕБНЫЕ_ПУТИ = (")
    конец = текст.index("def _тело_robots() -> str:")
    область: dict = {"мета_роботов": lambda: "index, follow", "any": any}
    exec(compile(текст[начало:конец], "<витрина>", "exec"), область)  # noqa: S102
    мета = область["мета_роботов_пути"]

    for путь in ("/healthz", "/api/", "/poster/a.webp", "/__debug",
                 "/.well-known/acme-challenge/x", "/healthz?x=1"):
        assert мета(путь) == "noindex, nofollow", путь
    for путь in ("/", "/catalog/", "/title/nekaya-kartochka/", "",
                 "/search/?q=a"):
        assert мета(путь) == "index, follow", путь
