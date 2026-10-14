"""Закрепление publisher_id за витриной Yummy: источник один, расхождение — отказ.

Почему у этого семейства отдельный инструмент. У витрин Yummy своего плеера
нет: страницу отдаёт верхний поток Next.js, а ячейка только проксирует к нему,
поэтому `LORDS_PLAYER_CONFIG` в её окружении отсутствует НАМЕРЕННО. Как только
ячейка объявляет `publisher_id_expected`, её пусковая проверка отказывает
словами «LORDS_PLAYER_CONFIG не задан», и витрина не поднимается вовсе —
измерено 2026-10-14 на yummyani7.site. Номер живёт в контуре витрины
(`CDNVIDEOHUB_PUBLISHER_ID_PINNED`), и точка входа образа предпочитает его
общему файлу направления (решение D214).

Здесь закрепляется поведение инструмента:

* номер НЕ принимается аргументом — источник один, учёт реестра;
* расхождение учёта и контура — отказ, а не тихая правка в одну из сторон;
* отсутствие закрепления — отказ: без него витрина возьмёт общее значение
  направления, одно на все домены семейства;
* общий файл направления не читается и не меняется ни в одном исходе.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

КОРЕНЬ = Path(__file__).resolve().parents[2]
СЦЕНАРИЙ = КОРЕНЬ / "automation" / "local" / "yummy-publisher-id.py"

КОНТУР = """services:
  web:
    image: example:latest
    environment:
      NODE_ENV: production
{закрепление}      TITLE_OVERLAYS_PATH: /app/content/overlays/title-overlays.json
"""


def _модуль():
    спец = importlib.util.spec_from_file_location("yummy_publisher_id", СЦЕНАРИЙ)
    м = importlib.util.module_from_spec(спец)
    sys.modules[спец.name] = м
    спец.loader.exec_module(м)
    return м


def _витрина(tmp_path: Path, *, учёт: str | None, закреплено: str | None) -> Path:
    репо = tmp_path / "var" / "site-repos" / "yummyani7-site"
    (репо / "deploy").mkdir(parents=True, exist_ok=True)
    строка = f'      CDNVIDEOHUB_PUBLISHER_ID_PINNED: "{закреплено}"\n' if закреплено else ""
    (репо / "deploy" / "compose.yaml").write_text(
        КОНТУР.format(закрепление=строка), encoding="utf-8")
    (репо / "config").mkdir(exist_ok=True)
    (репо / "config" / "site.json").write_text(
        '{"environment": {"LORDS_LEGACY_UPSTREAM": "127.0.0.1:3104"}}', encoding="utf-8")
    return репо


@pytest.fixture()
def стенд(tmp_path: Path, monkeypatch):
    м = _модуль()
    monkeypatch.setattr(м, "КОРЕНЬ", tmp_path)
    # Метки контура берутся у работающего контейнера; в проверке докера нет.
    monkeypatch.setattr(м, "метки_контура",
                        lambda контейнер: {"проект": "yummyani7-site", "переменные": ""})
    return м


def _подставить_ячейку(м, monkeypatch, репо: Path, учёт: str | None):
    ячейка = SimpleNamespace(
        site_id="yummy-07", domain="yummyani7.site",
        publisher={"publisher_id": учёт} if учёт else {},
        repo={"path": str(репо)})
    monkeypatch.setattr(м.registry, "resolve", lambda site_id: ячейка)


def test_учёт_и_контур_согласны_сухой_прогон(стенд, tmp_path, monkeypatch):
    репо = _витрина(tmp_path, учёт="10376", закреплено="10376")
    _подставить_ячейку(стенд, monkeypatch, репо, "10376")
    отчёт = стенд.главное("yummy-07", apply=False)
    assert отчёт["учёт и закрепление согласны"] is True
    assert отчёт["итог"].startswith("сухой прогон")
    assert отчёт["общий файл не читается и не меняется"] is True


def test_расхождение_учёта_и_контура_отказ(стенд, tmp_path, monkeypatch):
    """Какое из двух значений верно — решает владелец, а не инструмент."""
    репо = _витрина(tmp_path, учёт="10376", закреплено="10371")
    _подставить_ячейку(стенд, monkeypatch, репо, "10376")
    отчёт = стенд.главное("yummy-07", apply=False)
    assert отчёт["итог"].startswith("ОТКАЗ")
    assert "расходятся" in отчёт["итог"]
    # Значения не печатаются: публичность номера не повод сыпать им в журнал.
    assert "10376" not in отчёт["итог"] and "10371" not in отчёт["итог"]


def test_без_закрепления_отказ(стенд, tmp_path, monkeypatch):
    """Без закрепления витрина возьмёт общее значение направления."""
    репо = _витрина(tmp_path, учёт="10376", закреплено=None)
    _подставить_ячейку(стенд, monkeypatch, репо, "10376")
    отчёт = стенд.главное("yummy-07", apply=False)
    assert отчёт["итог"].startswith("ОТКАЗ")
    assert "CDNVIDEOHUB_PUBLISHER_ID_PINNED" in отчёт["итог"]


def test_пустой_учёт_это_blocked_input(стенд, tmp_path, monkeypatch):
    """Пустое поле — не разрешение подставить значение направления."""
    репо = _витрина(tmp_path, учёт=None, закреплено="10376")
    _подставить_ячейку(стенд, monkeypatch, репо, None)
    with pytest.raises(стенд.Отказ, match="BLOCKED_INPUT"):
        стенд.главное("yummy-07", apply=False)


def test_номер_не_принимается_аргументом():
    """У инструмента нет ключа со значением: источник один — учёт реестра.

    Ключ `--publisher-id` здесь означал бы второй источник истины: запустивший
    мог бы задать витрине номер мимо учёта, и реестр с контуром разошлись бы
    молча. Поэтому отсутствие ключа — свойство, а не недоделка.
    """
    текст = СЦЕНАРИЙ.read_text(encoding="utf-8")
    assert "--publisher-id" not in текст
    assert 'add_argument("--site"' in текст


def test_верхний_порт_читается_из_пакета(стенд, tmp_path, monkeypatch):
    """Порт верхнего потока берётся из `config/site.json`, а не угадывается."""
    репо = _витрина(tmp_path, учёт="10376", закреплено="10376")
    assert стенд.верхний_порт(репо) == 3104
