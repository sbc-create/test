"""Первое нажатие зрителя доводит до воспроизведения, а не теряется (T338).

Измерено 27.10 на живых витринах линии Zona. Без нажатия состояние плеера
остаётся `resolving` и медиа не появляется даже через двадцать секунд — значит
разрешение источника запускает ИМЕННО нажатие. После него состояние доходит до
`ready`, но воспроизведение не начинается: нужно второе нажатие, и от первого до
`currentTime >= 1` проходит 7–10 секунд. Независимая приёмка линии SEO: 12
прогонов из 12, телефон и компьютер — во всех воспроизведение только со
второго нажатия.

Жест у нас УЖЕ есть, мы его теряем. Поэтому желание запоминается и применяется
к медиа, как только оно появилось; этапы плеера при этом не меняются.
"""
from __future__ import annotations

import pathlib
import re
import subprocess
import sys
import tempfile

КОРЕНЬ = pathlib.Path(__file__).resolve().parents[2]
РАНТАЙМ = КОРЕНЬ / "automation" / "host" / "lords-frontend.py"


def _скрипт() -> str:
    т = РАНТАЙМ.read_text(encoding="utf-8")
    н = т.index('СКРИПТ_ПЛЕЕРА_КЛИЕНТ = """') + len('СКРИПТ_ПЛЕЕРА_КЛИЕНТ = """')
    return т[н:т.index('"""', н)]


def test_жест_записывается_на_рамке_плеера():
    """Слушатель на рамке, а не на документе: щелчок по описанию — не желание."""
    с = _скрипт()
    assert "f.addEventListener('click', function(){ хотел_играть=true; }, true)" in с
    assert "touchstart" in с
    # Документ целиком слушателем не покрывается.
    assert "document.addEventListener('click'" not in с


def test_желание_применяется_один_раз_и_только_к_нетронутому_медиа():
    """Иначе мы боролись бы с тем, кто поставил на паузу сам."""
    с = _скрипт()
    условие = re.search(
        r"if\(v && хотел_играть && пуск_сделан!==my && v\.paused && "
        r"\(v\.currentTime\|\|0\)<0\.25\)\{", с)
    assert условие, "условие применения желания не найдено или ослаблено"
    assert "пуск_сделан=my;" in с, "нет отметки «пуск уже сделан»"


def test_есть_запас_на_отказ_автозапуска():
    """`play()` может быть отклонён политикой — тогда кнопка самого провайдера."""
    с = _скрипт()
    assert "обещание.catch" in с
    assert "function нажать_кнопку(node)" in с
    assert 'aria-label="Смотреть"' in с
    # Запас ничего не обещает, если кнопки нет.
    assert "return false;" in с.split("function нажать_кнопку(node)")[1][:900]


def test_этапы_плеера_сохранены():
    """Обязательные этапы не исчезли: resolving → ready/active → ok."""
    с = _скрипт()
    for этап in ("state('resolving')", "state('active')", "state('ok')"):
        assert этап in с, этап
    # Честные состояния отказа тоже на месте.
    assert "state('provider'" in с and "state('slow'" in с


def test_скрипт_разбирается_как_javascript():
    """Беда синтаксиса здесь не видна ни одной проверкой Python."""
    with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False,
                                     encoding="utf-8") as ф:
        ф.write(_скрипт())
        путь = ф.name
    г = subprocess.run(["node", "--check", путь], capture_output=True, text=True)
    assert г.returncode == 0, г.stderr[:400]


def test_цель_player_start_не_сдвинулась():
    """Цель означает «площадка ЗАПРОСИЛА показ», и правка её не переносит."""
    с = _скрипт()
    assert "window.__sfGoalOnce('player_start')" in с
    # Она по-прежнему в bind, а не в обработчике нажатия: иначе одна цель
    # значила бы на разных витринах разное.
    до_жеста = с.split("f.addEventListener('click'")[0]
    assert "window.__sfGoalOnce('player_start')" in до_жеста
