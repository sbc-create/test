"""Пустой индексируемый раздел: находка; пустой и закрытый — нет.

Два свойства этого обхода держат его смысл, и каждое проверяется отдельно:

* разделы **не придумываются** — берутся те, на которые ссылается сама витрина.
  Придуманный адрес проверял бы обработку неизвестного значения, а не пустой
  раздел;
* форма адреса карточки берётся с НЕПУСТОЙ страницы каталога. Без этого ноль
  карточек в разделе означал бы не пустоту, а слепой признак — ошибка, уже
  сделанная дважды за ночь.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

ПУТЬ = (Path(__file__).resolve().parents[2] / "automation" / "local"
        / "empty-sections-probe.py")


def _модуль():
    спец = importlib.util.spec_from_file_location("empty_sections_probe", ПУТЬ)
    м = importlib.util.module_from_spec(спец)
    спец.loader.exec_module(м)
    return м


МОД = _модуль()


def test_разделы_берутся_из_ссылок_витрины_в_обеих_формах():
    тело = ('<a href="/genre/drama/">д</a>'
            '<a href="/catalog/?genre=horror">у</a>'
            '<a href="/year/2026/">2026</a>'
            '<a href="/catalog/?country=usa">США</a>')
    найдено = МОД.разделы(тело)
    assert "/genre/drama/" in найдено
    assert "/catalog/?genre=horror" in найдено
    assert "/year/2026/" in найдено
    assert "/catalog/?country=usa" in найдено


def test_адреса_карточек_разделами_не_считаются():
    """Иначе обход ушёл бы по карточкам и мерил бы не то."""
    найдено = МОД.разделы('<a href="/title/alpha">A</a>'
                          '<a href="/anime/beta">B</a>')
    assert найдено == [], найдено


def test_повтор_ссылки_не_удваивает_раздел():
    тело = '<a href="/genre/drama/">д</a><nav><a href="/genre/drama/">д</a></nav>'
    assert МОД.разделы(тело) == ["/genre/drama/"]


def test_форма_карточки_нераспознана_это_отказ_а_не_ноль():
    assert МОД.карточек('<a href="/film/x">x</a>') is None
    assert МОД.карточек('<a href="/title/x">x</a>') == (1, "/title/")
    assert МОД.карточек('<a href="/anime/x">x</a>') == (1, "/anime/")


def test_закрытая_страница_распознаётся_заголовком_и_meta():
    assert МОД.закрыта("", {"x-robots-tag": "noindex"})
    assert МОД.закрыта('<meta name="robots" content="NoIndex, follow">', {})
    assert not МОД.закрыта('<meta name="robots" content="index, follow">', {})


def test_заведомо_отсутствующие_значения_названы_и_их_три():
    """Год вне кинопроизводства и две строки, которых в таксономии быть не может.

    Эта часть обхода проверяет обратное свойство: отсутствующее значение НЕ
    должно отдавать индексируемую страницу. Без неё обход доказывал бы только
    то, что существующие разделы непусты.
    """
    assert len(МОД.ЗАВЕДОМО_НЕТ) == 3
    assert any("1066" in а for а in МОД.ЗАВЕДОМО_НЕТ)
    assert all(а.startswith("/") for а in МОД.ЗАВЕДОМО_НЕТ)


def test_зарезервированные_имена_в_обход_не_попадают():
    """RFC 6761: `.test` и `.localhost` — не витрины сети."""
    assert all(not д.endswith((".test", ".localhost")) for д in МОД.домены())


def test_предел_числа_разделов_есть_и_он_настраиваемый():
    текст = ПУТЬ.read_text(encoding="utf-8")
    assert "--limit" in текст
    assert "сколько разделов проверять" in текст
