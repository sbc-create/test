"""REQ-SEO-THIN-FACET: фасет с одной записью можно закрыть, но только по объявлению.

Измерено 2026-10-18: в общем каталоге Lords/Zona 163 страны и 99 жанров, а
произведений одна-две у 41 страны и 12 жанров; на zonafilm12.site из 165 стран
ровно одну запись показывают 32 (19 %), и все они отвечают `index, follow` с
self-canonical. Живая проверка Lords: `/country/andorra/` — одна карточка,
`/country/ssha/` — 48 карточек при 19 929 записях.

Такая страница отдаёт ту же карточку, с которой на неё ведёт ссылка. По F7.5
заморозки 2026-10-18 дубли конкурируют между собой, и робот может исключить
целевую страницу.

Три свойства закреплены здесь, потому что без любого из них правка была бы
вредной:

* **по умолчанию выключено.** Пакет запрещает индексируемые ПУСТЫЕ разделы
  (§3 п.4), а про «одну запись» правила нет — это наш вывод. Общий рантайм
  приезжает чужим линиям их обычным выпуском, и менять им состав индекса по
  нашему выводу без их решения нельзя;
* **раздел целиком не закрывается** даже при одной записи: `/catalog/` — это не
  отбор, а сам раздел;
* **порог ровно один**: две записи — уже сравнение, и своего порога
  «малоинформативности» мы не ставим, потому что документация его не даёт.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

ПУТЬ = (Path(__file__).resolve().parents[2] / "automation" / "host"
        / "lords-frontend.py")


def _рантайм(monkeypatch, флаг: str | None):
    """Свежий импорт рантайма с нужным значением переменной окружения."""
    if флаг is None:
        monkeypatch.delenv("LORDS_THIN_FACET_NOINDEX", raising=False)
    else:
        monkeypatch.setenv("LORDS_THIN_FACET_NOINDEX", флаг)
    имя = f"fe_thin_{флаг}"
    спец = importlib.util.spec_from_file_location(имя, ПУТЬ)
    м = importlib.util.module_from_spec(спец)
    sys.modules[имя] = м
    спец.loader.exec_module(м)
    return м


def test_по_умолчанию_ничего_не_закрывается(monkeypatch):
    м = _рантайм(monkeypatch, None)
    assert м.ТОНКИЙ_ФАСЕТ_NOINDEX is False
    assert м.тонкий_фасет("/country/andorra/", "/catalog/", 1) is False


def test_по_объявлению_фасет_с_одной_записью_закрывается(monkeypatch):
    м = _рантайм(monkeypatch, "1")
    assert м.ТОНКИЙ_ФАСЕТ_NOINDEX is True
    assert м.тонкий_фасет("/country/andorra/", "/catalog/", 1) is True
    assert м.тонкий_фасет("/genre/religiya/", "/catalog/", 0) is True


def test_две_записи_остаются_в_индексе(monkeypatch):
    """Порог ровно один: своего порога малоинформативности мы не ставим."""
    м = _рантайм(monkeypatch, "on")
    assert м.тонкий_фасет("/country/barbados/", "/catalog/", 2) is False
    assert м.тонкий_фасет("/country/ssha/", "/catalog/", 19929) is False


def test_раздел_целиком_не_закрывается(monkeypatch):
    """`/catalog/` — не отбор, а сам раздел; закрывать его нельзя."""
    м = _рантайм(monkeypatch, "1")
    assert м.тонкий_фасет("/catalog/", "/catalog/", 1) is False
    assert м.тонкий_фасет("", "/catalog/", 1) is False


@pytest.mark.parametrize("значение,ожидание",
                         [("1", True), ("true", True), ("ON", True),
                          ("0", False), ("off", False), ("", False),
                          ("нет", False)])
def test_перечень_истинных_значений_явный(monkeypatch, значение, ожидание):
    м = _рантайм(monkeypatch, значение)
    assert м.ТОНКИЙ_ФАСЕТ_NOINDEX is ожидание


def test_основание_и_масштаб_названы_рядом_с_флагом():
    тело = ПУТЬ.read_text(encoding="utf-8")
    где = тело.index("ТОНКИЙ_ФАСЕТ_NOINDEX")
    рядом = тело[max(0, где - 1500):где + 200]
    assert "163 стран" in рядом and "41 стран" in рядом
    assert "F7.5" in рядом
    assert "приезжает чужим линиям их обычным выпуском" in рядом


def test_применено_в_фасетной_ветке():
    тело = ПУТЬ.read_text(encoding="utf-8")
    assert "индексируема=not тонкий_фасет(" in тело
    assert "канон_пути, разд + \"/\", len(набор)" in тело
