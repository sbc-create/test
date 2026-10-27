"""Внешняя проба к витрине называет себя: иначе мы меряем собственный предел.

ПОВОД — опыт 27.10, парные пробы на одних путях в одном окне:

    UA по умолчанию (curl/8.x):   200 200 503 503 503 503
    UA «factory-ua-probe»:        200 200 200 200 200 200

Разница только в User-Agent. В рантайме витрины стоит защита от роботов
(T326/T327/T329): класс `other_bot` получает 4 одновременных слота и не больше
30 принятых запросов за скользящие 60 с, сверх — сразу 503 с
`Retry-After: 120`. В `other_bot` попадает всё, где в UA есть `curl`, `python`,
`wget`, `bot`, `crawler` или `spider`. UA, начинающийся с `factory-`,
классифицируется как `factory` и под предел не попадает.

Из-за этого целый день сессии читали 503 как свойство витрины: отказ
приходил от приложения, с нужным `Retry-After`, перемежался от запроса к
запросу (скользящее окно) и совпадал с прогоном обновлятеля просто потому, что
тот занимает почти восемь минут из десяти. Бюджет ОБЩИЙ на класс, поэтому
непомеченные пробы разных сессий тратили его друг у друга.

ЧТО ПРОВЕРЯЕТСЯ. Инструмент, который делает ВНЕШНИЙ запрос к витрине (через
nginx, то есть не на 127.0.0.1), обязан называть себя `factory-…`. Проверка
судит только по тексту инструмента: это дешево и ловит именно ту ошибку, из-за
которой нельзя доверять замеру.

ЧЕГО ПРОВЕРКА НЕ ТРЕБУЕТ. Запросы к `127.0.0.1`/`localhost` идут мимо nginx, и
предел роботов к ним не применяется (`_через_прокси`), — их метка не нужна.
Инструменты на браузере отправляют настоящий UA Chrome и попадают в класс
`browser`: предел их не касается, но у них своя обязанность — глушить счётчик,
и за ней следит `test_home_acceptance_tool.py`.
"""
from __future__ import annotations

import pathlib
import re

import pytest

КОРЕНЬ = pathlib.Path(__file__).resolve().parents[2]
КАТАЛОГ = КОРЕНЬ / "automation" / "local"
#: Признаки внешнего запроса в тексте инструмента.
ЗАПРОС = ("curl", "urlopen", "requests.get", "requests.post")
#: Запрос мимо nginx: предел роботов к нему не применяется.
МЕСТНОЕ = ("127.0.0.1", "localhost", "0.0.0.0")
#: Браузерные инструменты отправляют UA Chrome и попадают в класс `browser`.
БРАУЗЕР = ("sync_playwright", "chromium", "playwright")
#: Сторонние адреса — не наши витрины, и наша метка там ничего не значит.
ЧУЖИЕ = ("api-metrika.yandex", "api.github.com", "plapi.cdnvideohub.com",
         "webmaster.yandex", "oauth.yandex", "cdnvideohub.com",
         "mc.yandex", "yandex.ru", "github.com")


def инструменты():
    return sorted(КАТАЛОГ.glob("*.py")) if КАТАЛОГ.is_dir() else []


def _внешние_адреса(текст: str) -> list:
    адреса = re.findall(r"https?://[^\s\"'`),]+", текст)
    итог = []
    for а in адреса:
        if any(м in а for м in МЕСТНОЕ) or any(ч in а for ч in ЧУЖИЕ):
            continue
        итог.append(а)
    return итог


def кандидаты():
    """Инструменты, делающие внешний запрос НЕ браузером."""
    итог = []
    for путь in инструменты():
        текст = путь.read_text(encoding="utf-8", errors="replace")
        if not any(п in текст for п in ЗАПРОС):
            continue
        if any(б in текст for б in БРАУЗЕР):
            continue
        if not _внешние_адреса(текст):
            continue
        итог.append(путь)
    return итог


def test_кандидаты_нашлись():
    """Пустой список означал бы, что проверка ничего не проверяет."""
    найдено = кандидаты()
    assert len(найдено) >= 10, [п.name for п in найдено]


@pytest.mark.parametrize("путь", кандидаты(), ids=lambda п: п.name)
def test_проба_называет_себя(путь):
    текст = путь.read_text(encoding="utf-8", errors="replace")
    assert "factory-" in текст, (
        f"{путь.name} делает внешний запрос к витрине, не называя себя: "
        "класс other_bot получает 503 с Retry-After 120 после 30 запросов за "
        "минуту, и замер покажет предел вместо состояния витрины")


def test_метка_стоит_в_начале_значения_UA():
    """Классификация смотрит на НАЧАЛО строки: `ua.startswith("factory-")`.

    «probe factory-x» классом `factory` не станет, а слово `curl` внутри
    такого UA увело бы его в `other_bot` — то есть под предел. Поэтому
    судится ЗНАЧЕНИЕ переменной агента, а не любое вхождение подстроки:
    `x-site-factory-build-id` — имя заголовка, а не имя пробы.
    """
    import ast

    имена = {"АГЕНТ", "UA", "USER_AGENT", "ИМЯ_ПРОБЫ", "АГЕНТ_ПРОБЫ"}
    проверено, плохие = [], []
    for путь in кандидаты():
        текст = путь.read_text(encoding="utf-8", errors="replace")
        try:
            дерево = ast.parse(текст)
        except SyntaxError:  # pragma: no cover — такой файл поймает компиляция
            continue
        for узел in дерево.body:
            if not isinstance(узел, ast.Assign):
                continue
            цели = {ц.id for ц in узел.targets if isinstance(ц, ast.Name)}
            if not (цели & имена):
                continue
            if not (isinstance(узел.value, ast.Constant)
                    and isinstance(узел.value.value, str)):
                continue
            значение = узел.value.value
            проверено.append((путь.name, значение))
            if not значение.startswith("factory-"):
                плохие.append((путь.name, значение))
    assert проверено, "ни один инструмент не объявляет имя пробы постоянной"
    assert not плохие, плохие
