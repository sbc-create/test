"""Кнопки ленты отключаются на краях, а не изображают работу.

Замер на живой витрине: при `scrollLeft=0` кнопка «назад» была включена на
390, 768 и 1440 — и при этом лежала поверх первой карточки. Пользователь
видит кнопку, попадает по ней пальцем и не получает ничего. Правило
`.zrl__btn[disabled]` в таблице стилей было описано и не включалось ни разу.

Поведение проверяется в браузере (`scripts/reconciliation/probe_rail.py`), а
здесь удерживается то, что можно удержать без браузера: скрипт обязан
синхронизировать состояние, а отключённая кнопка — уходить с карточки, а не
гаснуть до трети и продолжать ловить палец.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

КОРЕНЬ = Path(__file__).resolve().parents[2]
ИСХОДНИК = КОРЕНЬ / "automation" / "host" / "lords-frontend.py"


@pytest.fixture(scope="module")
def модуль():
    имя = "lf_rail_buttons"
    спец = importlib.util.spec_from_file_location(имя, ИСХОДНИК)
    assert спец and спец.loader
    m = importlib.util.module_from_spec(спец)
    sys.modules[имя] = m
    спец.loader.exec_module(m)
    return m


def test_скрипт_синхронизирует_состояние_кнопок(модуль):
    s = модуль.СКРИПТ_ЛЕНТ
    assert "disabled" in s, "скрипт не трогает состояние кнопок"
    assert "aria-disabled" in s, "состояние не объявлено для скрин-ридера"
    assert "scrollWidth-v.clientWidth" in s.replace(" ", ""), "конец ленты не вычисляется"
    # Пересчёт обязан происходить не только по клику: лента прокручивается
    # пальцем и колесом, и после этого состояние тоже меняется.
    assert "'scroll'" in s, "прокрутка пальцем не пересчитывает кнопки"
    assert "resize" in s, "смена ширины не пересчитывает кнопки"


def test_отключённая_кнопка_не_нажимается(модуль):
    s = модуль.СКРИПТ_ЛЕНТ
    assert "b.disabled" in s, "скрипт готов прокручивать по отключённой кнопке"


def test_отключённая_кнопка_освобождает_карточку(модуль):
    """Гашения до трети мало: полупрозрачная кнопка всё ещё закрывает постер."""
    for стиль in (модуль.ЗОНА_СТИЛЬ, ):
        текст = стиль if isinstance(стиль, str) else стиль()
        assert ".zrl__btn[disabled]" in текст
        кусок = текст.split(".zrl__btn[disabled]", 1)[1].split("}", 1)[0]
        assert "visibility:hidden" in кусок, f"кнопка остаётся на карточке: {кусок}"
        assert "pointer-events:none" in кусок, f"кнопка продолжает ловить палец: {кусок}"
