"""Инструмент читает паспорт ячеек своего репозитория и называет копию.

Повод — MOD-164. Восемь инструментов держали в коде абсолютный путь в рабочую
копию соседней линии (`/home/claude/wt-portable-site-cell-01/config/`), где
восьми живых витрин партии K2 нет. Следствие измерено 24.10: их проверки молча
исключали `lordfilm.group`, `lordfilm.msk.ru`, `lordfilm.spb.ru`,
`lordserial.group`, `lordserial.msk.ru`, `lordserial.net.ru`,
`lordserial.spb.ru` и `lordserial.su` — 21 домен вместо 29, и в отчёте это
никак не выглядело неполнотой.

Здесь закрепляются два свойства, и второе важнее первого:

* путь берётся от СВОЕГО репозитория (и переопределяется `SITE_CELLS_PATH`),
  а не из чужой рабочей копии;
* прочитанная копия и число ячеек НАЗЫВАЮТСЯ в выводе. Пока копий несколько и
  они расходятся, молчание о копии — это вердикт без знаменателя: неполный
  охват неотличим от полного.

Чего эта проверка НЕ решает: какую копию читает исполнитель при выпуске. Это
вопрос владельца (шаг 1 в MOD-164), и подменять его выбором за него нельзя.
"""
from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path

КОРЕНЬ = Path(__file__).resolve().parents[2]
ПРОБЫ = КОРЕНЬ / "automation" / "local"
ЧУЖАЯ = "wt-portable-site-cell-01/config/site-cells.json"
ВИТРИНЫ_K2 = ("lordfilm.group", "lordfilm.msk.ru", "lordfilm.spb.ru",
              "lordserial.group", "lordserial.msk.ru", "lordserial.net.ru",
              "lordserial.spb.ru", "lordserial.su")
#: Читатели паспорта: у каждого названа функция, отдающая домены.
ЧИТАТЕЛИ = {
    "card-links-audit.py": "домены",
    "empty-sections-probe.py": "домены",
    "tls-expiry-probe.py": "из_паспорта",
    "cross-site-leak-probe.py": None,
    "schema-vs-visible.py": None,
    "pager-bounds-probe.py": None,
    "sitemap-completeness.py": None,
    "cell-name-map.py": None,
}


def _модуль(имя: str):
    п = ПРОБЫ / имя
    спец = importlib.util.spec_from_file_location(имя.replace("-", "_")[:-3], п)
    м = importlib.util.module_from_spec(спец)
    спец.loader.exec_module(м)
    return м


def test_ни_один_инструмент_не_читает_паспорт_из_чужой_копии():
    беды = [п.name for п in sorted(ПРОБЫ.glob("*.py"))
            if ЧУЖАЯ in п.read_text(encoding="utf-8")]
    assert not беды, ("паспорт ячеек читается из чужой рабочей копии, где нет"
                      f" восьми живых витрин K2: {беды}")


def test_путь_берётся_от_своего_репозитория():
    for имя in ЧИТАТЕЛИ:
        исходник = (ПРОБЫ / имя).read_text(encoding="utf-8")
        assert 'parents[2] / "config"' in исходник, имя
        assert "SITE_CELLS_PATH" in исходник, имя


def test_каждый_читатель_называет_прочитанную_копию():
    for имя in ЧИТАТЕЛИ:
        исходник = (ПРОБЫ / имя).read_text(encoding="utf-8")
        assert "паспорт ячеек:" in исходник, (
            f"{имя}: копия не называется в выводе — неполный охват будет"
            " неотличим от полного")


def test_переопределение_пути_действует(tmp_path, monkeypatch):
    урезанный = tmp_path / "site-cells.json"
    урезанный.write_text(json.dumps(
        {"cells": [{"site_id": "x-01", "domain": "example.test"},
                   {"site_id": "y-01", "domain": "yummyani.site"}]}),
        encoding="utf-8")
    monkeypatch.setenv("SITE_CELLS_PATH", str(урезанный))
    м = _модуль("card-links-audit.py")
    assert str(м.ПАСПОРТ) == str(урезанный)
    assert м.домены() == ["yummyani.site"], "домен .test обязан отсеиваться"


def test_копия_без_витрин_k2_видна_по_числу_ячеек(tmp_path, monkeypatch, capsys):
    """Отрицательный контроль: неполная копия обязана быть ЗАМЕТНА.

    Если копия названа и число ячеек напечатано, подмена копии перестаёт быть
    тихой — именно это свойство отсутствовало у восьми инструментов.
    """
    неполная = tmp_path / "site-cells.json"
    неполная.write_text(json.dumps(
        {"cells": [{"site_id": "y-01", "domain": "yummyani.site"}]}),
        encoding="utf-8")
    monkeypatch.setenv("SITE_CELLS_PATH", str(неполная))
    м = _модуль("empty-sections-probe.py")
    домены = м.домены()
    напечатано = capsys.readouterr().out
    assert not set(домены) & set(ВИТРИНЫ_K2)
    assert str(неполная) in напечатано and "ячеек 1" in напечатано


def test_в_своей_копии_витрины_k2_на_месте(monkeypatch):
    """Прямая граница: со штатной копией охват включает все восемь."""
    monkeypatch.delenv("SITE_CELLS_PATH", raising=False)
    м = _модуль("card-links-audit.py")
    домены = set(м.домены())
    пропущены = [в for в in ВИТРИНЫ_K2 if в not in домены]
    assert not пропущены, f"витрины K2 вне охвата: {пропущены}"
