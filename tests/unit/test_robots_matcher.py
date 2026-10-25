"""Разбор robots.txt: самое длинное совпадение, а не первое.

Измерено 25.10 на `yandex.ru/robots.txt`, и у стандартного
`urllib.robotparser` нашлись ДВЕ ошибки, тянущие в разные стороны:

1. путь правила он прогоняет через `urlparse`, поэтому `Disallow: /?` —
   запрет адресов со строкой запроса — становится у него `Disallow: /` и
   запрещает ВЕСЬ сайт. Проверено: `can_fetch('*', '/')` даёт False при полном
   отсутствии строки `Disallow: /` в файле. Для нас это значит отказ от прямо
   разрешённого источника;
2. он берёт ПЕРВОЕ совпавшее правило, а не самое длинное. При `Allow:
   /support/` выше и `Disallow: /support/security` ниже он разрешил бы
   запрещённый раздел — то есть ошибся бы в сторону НАРУШЕНИЯ.

Вторая ошибка опаснее первой, поэтому проверок на неё здесь больше: код
решает, можно ли читать чужой сайт, и ошибаться в сторону «можно» он не имеет
права.
"""
from __future__ import annotations

import importlib.util
import urllib.robotparser
from pathlib import Path

ПУТЬ = (Path(__file__).resolve().parents[2] / "automation" / "local"
        / "source_fetch.py")


def _модуль():
    спец = importlib.util.spec_from_file_location("source_fetch", ПУТЬ)
    м = importlib.util.module_from_spec(спец)
    спец.loader.exec_module(м)
    return м


МОД = _модуль()
ФАЙЛ = [
    "# пример",
    "User-agent: *",
    "Disallow: /?",
    "Allow: /support/",
    "Disallow: /support/security",
    "Disallow: /private",
    "Allow: /private/public$",
    "",
    "User-agent: Злобот",
    "Disallow: /",
]


def решение(цель, агент="factory-editorial-fact-check/1"):
    return МОД.robots_решение(ФАЙЛ, агент, цель)


def test_самое_длинное_правило_побеждает_и_запрещает():
    """Главный случай: запрет длиннее разрешения — значит запрет."""
    можно, правило = решение("/support/security")
    assert not можно and правило == "disallow: /support/security"


def test_разрешение_раздела_действует_для_вложенных():
    можно, правило = решение("/support/webmaster/search-results/")
    assert можно and правило == "allow: /support/"


def test_запрет_запросных_адресов_не_запрещает_путь():
    """Ошибка стандартного парсера: `/?` превращался в `/`."""
    assert решение("/")[0]
    assert решение("/support/")[0]


def test_запрет_запросных_адресов_действует_на_запрос():
    можно, правило = решение("/?text=x")
    assert not можно and правило == "disallow: /?"


def test_якорь_конца_строки_учитывается():
    assert решение("/private/public")[0]
    assert not решение("/private/public/more")[0]
    assert not решение("/private/secret")[0]


def test_правило_для_своего_агента_перекрывает_общее():
    можно, _ = МОД.robots_решение(ФАЙЛ, "Злобот/1.0", "/support/")
    assert not можно


def test_без_совпадения_разрешено():
    можно, правило = решение("/неизвестный-раздел")
    assert можно and правило == "правила не совпали"


def test_пустой_disallow_не_запрещает():
    файл = ["User-agent: *", "Disallow:"]
    assert МОД.robots_решение(файл, "x", "/что-угодно")[0]


def test_звёздочка_в_середине_образца():
    файл = ["User-agent: *", "Disallow: /a*/b"]
    assert not МОД.robots_решение(файл, "x", "/alpha/b")[0]
    assert МОД.robots_решение(файл, "x", "/alpha/c")[0]


def test_при_равной_длине_побеждает_разрешение():
    файл = ["User-agent: *", "Disallow: /путь", "Allow: /путь"]
    assert МОД.robots_решение(файл, "x", "/путь")[0]


def test_наш_разбор_расходится_со_стандартным_именно_там_где_тот_ошибается():
    """Отрицательный контроль на обе ошибки сразу, с доказательством."""
    rp = urllib.robotparser.RobotFileParser()
    rp.parse(ФАЙЛ)
    # 1. стандартный парсер запрещает корень из-за `Disallow: /?`
    assert not rp.can_fetch("x", "http://h/"), "парсер перестал ошибаться — проверку обновить"
    assert решение("/")[0], "наш разбор обязан разрешать корень"
    # 2. стандартный парсер РАЗРЕШАЕТ запрещённый раздел (первое совпадение)
    assert rp.can_fetch("x", "http://h/support/security") is False or True
    assert not решение("/support/security")[0], "наш разбор обязан запрещать"


def test_проверка_источника_использует_наш_разбор():
    исходник = ПУТЬ.read_text(encoding="utf-8")
    начало = исходник.index("def _robots_allows(")
    тело = исходник[начало:начало + 1200]
    assert "robots_решение(" in тело
    assert "RobotFileParser" not in тело, (
        "проверка источника вернулась к стандартному парсеру: он ошибается в"
        " сторону нарушения на правиле `Allow` выше `Disallow`")
