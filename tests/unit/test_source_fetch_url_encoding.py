"""Адрес источника с нелатинским названием обязан быть запрашиваемым.

Измерено 25.10: `source_fetch.py page https://ru.wikipedia.org/wiki/Правила_…`
падал с `UnicodeEncodeError: 'ascii' codec can't encode characters` внутри
http.client — то есть ЛЮБОЙ записанный источник с русским названием в адресе
этим путём прочитать было нельзя. Отказ при этом выглядел поломкой
инструмента, а не свойством адреса, и поэтому мог годами не исправляться:
редактор записывал такой источник при подготовке (путь `film` строит адрес
сам и кодирует его), а перечитать его при рецензии было нечем.

Проверка держит два края: нелатинский путь кодируется, а уже закодированный
адрес не кодируется ВТОРОЙ раз (иначе «%D0» стало бы «%25D0» и источник
подменился бы на несуществующий).
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

ПУТЬ = (Path(__file__).resolve().parents[2] / "automation" / "local"
        / "source_fetch.py")


def _модуль():
    спец = importlib.util.spec_from_file_location("source_fetch", ПУТЬ)
    м = importlib.util.module_from_spec(спец)
    спец.loader.exec_module(м)
    return м


МОД = _модуль()


def test_кириллический_путь_кодируется():
    из = МОД.безопасный_адрес(
        "https://ru.wikipedia.org/wiki/Правила_совместной_жизни")
    assert из.startswith("https://ru.wikipedia.org/wiki/%D0%9F")
    из.encode("ascii")  # запрос обязан кодироваться в ASCII


def test_уже_закодированный_адрес_не_кодируется_повторно():
    было = "https://ru.wikipedia.org/wiki/%D0%9F%D1%80%D0%B0%D0%B2%D0%B8%D0%BB%D0%B0"
    assert МОД.безопасный_адрес(было) == было


def test_латинский_адрес_не_меняется():
    было = "https://en.wikipedia.org/wiki/So_Cold_the_River"
    assert МОД.безопасный_адрес(было) == было


def test_схема_и_хост_сохраняются():
    из = МОД.безопасный_адрес("https://shikimori.io/animes/61967")
    assert из == "https://shikimori.io/animes/61967"


def test_запрос_и_якорь_не_ломаются():
    из = МОД.безопасный_адрес(
        "https://example.org/путь?ключ=значение&b=2#раздел")
    из.encode("ascii")
    assert "?" in из and "&b=2" in из and "#" in из


def test_запрос_использует_безопасный_адрес():
    """Исправление обязано стоять на входе ЛЮБОГО запроса, а не в одном пути."""
    исходник = ПУТЬ.read_text(encoding="utf-8")
    начало = исходник.index("def _get(")
    тело = исходник[начало:начало + 700]
    assert "безопасный_адрес(url)" in тело, (
        "запрос идёт мимо кодирования: тогда один путь исправлен, а остальные"
        " падают на том же адресе")


#: Разметка Википедии бывает двух видов, и оба настоящие: классическая, где
#: абзац это `<p>`, и Parsoid, где у абзаца есть атрибуты (`<p id="mwAw">`).
КЛАССИКА = (
    '<div class="mw-content-ltr mw-parser-output" lang="en">'
    '<p class="mw-empty-elt"></p>'
    '<p><b>So Cold the River</b> is a 2022 horror film written and directed by'
    ' Paul Shoulberg. It is based on the novel by Michael Koryta.</p></div>')
PARSOID = (
    '<div class="mw-content-ltr mw-parser-output" lang="en" id="mwAQ">'
    '<section data-mw-section-id="0" id="mwAg">'
    '<p id="mwAw"><b>Chang\'an</b> is a 2023 Chinese animated film. It follows'
    ' the friendship of poets Li Bai and Gao Shi amid the rebellion led by'
    ' An Lushan.</p></section></div>')


def test_ввод_читается_в_классической_разметке():
    из = МОД._ввод(КЛАССИКА)
    assert "So Cold the River" in из and "Koryta" in из


def test_ввод_читается_в_разметке_parsoid():
    """Главный случай: прежний образец требовал буквального «<p>».

    Измерено 25.10 на статье про «Тридцать тысяч ли до Чанъаня»: `lead`
    приходил пустым при живом вводном абзаце, и редактор закрывал задание как
    «завязки нет» — хотя источник прямо называл и «rebellion led by An
    Lushan», и «Li Bai».
    """
    из = МОД._ввод(PARSOID)
    assert "Li Bai" in из and "An Lushan" in из


def test_пустой_первый_абзац_пропускается():
    из = МОД._ввод('<div class="mw-content-ltr mw-parser-output">'
                   '<p class="mw-empty-elt">\n</p><p id="x">' + "я" * 100
                   + '</p></div>')
    assert из.startswith("я" * 20)


def test_короткая_служебная_вставка_не_считается_вводом():
    """Hatnote вроде «см. также» короче порога и вводом не является."""
    из = МОД._ввод('<div class="mw-content-ltr mw-parser-output">'
                   '<p><i>См. также другую статью.</i></p>'
                   '<p id="y">' + "ф" * 120 + '</p></div>')
    assert из.startswith("ф")


def test_раздел_без_служебной_ссылки_правки():
    страница = ('<h2 id="Plot">Plot</h2><p>[ edit ] Эрика снимает фильм о'
                ' миллиардере.</p><h2 id="Cast">Cast</h2>')
    из = МОД._section(страница, ("Plot",))
    assert из.startswith("Эрика"), из


def test_раздела_нет_это_пустая_строка():
    assert МОД._section('<h2 id="Cast">Cast</h2><p>актёры</p>', ("Plot",)) == ""
