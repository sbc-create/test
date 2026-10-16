"""Закрыт ли обход целиком — проверяется строкой, а не подстрокой.

Нашла линия витрины lordfilm47.space 2026-10-16 у своего сторожа:
`"Disallow: /" not in robots` совпадает с `Disallow: /poster/`, и условие
«режим индексации не изменился» молча проходило И при закрытой витрине, И при
открытой — то есть сторож не заметил бы ни открытия, ни закрытия. Тот же
текст нашёлся в четырёх местах этого репозитория, где на нём принимается
решение.

Каждая проверка здесь падает на прежней подстроке — это и есть её смысл.
"""
from __future__ import annotations

import sys
from pathlib import Path

КОРЕНЬ = Path(__file__).resolve().parents[2]
if str(КОРЕНЬ) not in sys.path:
    sys.path.insert(0, str(КОРЕНЬ))

from factory.seo.robots_scope import (  # noqa: E402
    закрывает_весь_обход,
    запрещённые_пути,
)

ОТКРЫТЫЙ = """# витрина открыта
User-agent: *
Disallow: /poster/
Disallow: /api/
Disallow: /healthz
Allow: /
Sitemap: https://example/sitemap.xml
"""

ЗАКРЫТЫЙ = """User-agent: *
Disallow: /
"""


def test_частичные_запреты_не_считаются_полным():
    # Прежняя подстрочная проверка здесь возвращала True и объявляла открытую
    # витрину закрытой.
    assert "Disallow: /" in ОТКРЫТЫЙ          # подстрока есть
    assert закрывает_весь_обход(ОТКРЫТЫЙ) is False  # запрета всего — нет


def test_полный_запрет_виден():
    assert закрывает_весь_обход(ЗАКРЫТЫЙ) is True


def test_пустой_disallow_разрешение_а_не_запрет():
    assert закрывает_весь_обход("User-agent: *\nDisallow:") is False
    assert закрывает_весь_обход("User-agent: *\nDisallow:   ") is False


def test_комментарии_и_регистр_не_мешают():
    assert закрывает_весь_обход("user-agent: *\n  DISALLOW: /   # всё") is True
    assert закрывает_весь_обход("# Disallow: /\nUser-agent: *\nAllow: /") is False


def test_блок_агента_не_распространяется_на_других():
    текст = "User-agent: Yandex\nDisallow: /\n\nUser-agent: *\nDisallow: /tmp/"
    assert закрывает_весь_обход(текст, "Yandex") is True
    assert закрывает_весь_обход(текст, "Googlebot") is False
    assert закрывает_весь_обход(текст) is False


def test_несколько_агентов_в_одном_блоке():
    текст = "User-agent: Yandex\nUser-agent: Googlebot\nDisallow: /"
    assert закрывает_весь_обход(текст, "Googlebot") is True
    assert закрывает_весь_обход(текст, "Bingbot") is False


def test_пустой_и_битый_файл_не_закрывают():
    """Ни один из этих файлов не закрывает обход, включая последний.

    `Disallow: /` без блока `User-agent` — директива без группы: вопрос «кому
    запрещено» остаётся без ответа, и роботы такие правила игнорируют.
    Направление ошибки здесь выбрано намеренно: предикат отвечает «не
    закрыт», то есть проверка staging на закрытость ПАДЁТ, а не объявит
    закрытым то, что закрытым не является. Ложное «закрыто» дороже ложного
    «открыто»: первое выпускает индексируемый staging в поиск.
    """
    for текст in ("", "   ", "совсем не robots", "Disallow: /"):
        assert закрывает_весь_обход(текст) is False, текст


def test_перечень_запрещённых_путей_для_отчёта():
    assert запрещённые_пути(ОТКРЫТЫЙ) == ["/poster/", "/api/", "/healthz"]
    assert запрещённые_пути(ЗАКРЫТЫЙ) == ["/"]
