"""Состояния плеера: пустая область — не состояние.

## Что наблюдалось

На странице произведения `<video-player>` присутствовал, атрибуты и скрипт
поставщика — тоже, но сам элемент имел размер `0×0`, содержимого у него не
было, обёртка занимала около 1170×658, а запасной текст «Источник видео сейчас
недоступен» оставался `hidden`. Зритель видел большую пустую область без
единого слова о том, что произошло.

Проверено по коду: строка `data-player-fallback` не упоминается больше нигде.
Показать запасной текст было **некому** — он скрыт навсегда.

Наличие тега плеера приёмкой не является.

## Что требуется

Явные состояния и переход между ними: загрузка, готово, недоступно, ошибка.
В недоступном и ошибочном состоянии запасной текст обязан стать видимым.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from factory.lords import render as render_mod  # noqa: E402
from factory.lords import theme as theme_mod  # noqa: E402
from factory.lords import plan as plan_mod  # noqa: E402


class TestСценарийУправляетСостояниямиПлеера:
    def test_запасной_текст_кто_то_показывает(self):
        assert "player-fallback" in render_mod.APP_JS, (
            "запасной текст скрыт навсегда: показать его некому, и зритель "
            "видит пустую область без объяснения")

    def test_отказ_загрузки_скрипта_поставщика_замечен(self):
        js = render_mod.APP_JS
        assert "error" in js and "data-player-script" in js, (
            "падение скрипта поставщика не отслеживается")

    def test_состояние_объявлено_на_обёртке(self):
        """Состояние читается из разметки, а не угадывается по виду."""
        assert "data-player-state" in render_mod.APP_JS

    def test_нет_бесконечных_повторов(self):
        """Бесконечные попытки жгут батарею и не чинят недоступный источник."""
        js = render_mod.APP_JS
        assert "setInterval" not in js.split("player")[1][:1500], (
            "в сценарии плеера бесконечный интервал")


class TestОформлениеСостоянийСуществует:
    def _sheet(self) -> str:
        return theme_mod.stylesheet(plan_mod.load_profiles()["lords-general"])

    def test_кадр_резервирует_место(self):
        """Кадр обязан занимать место до подключения: иначе включение плеера
        сдвинет всю раскладку."""
        sheet = self._sheet()
        assert ".player__frame" in sheet
        assert "aspect-ratio" in sheet

    def test_у_недоступного_состояния_есть_правило(self):
        sheet = self._sheet()
        assert 'data-player-state="unavailable"' in sheet or ".player__fallback" in sheet, (
            "нет правила оформления для недоступного состояния")

    def test_запасной_текст_читается_когда_показан(self):
        sheet = self._sheet()
        assert ".player__fallback" in sheet, "у запасного текста нет оформления"
