"""Длительность серии: неизвестное не выдаётся за ноль.

Дефект наблюдался на боевой витрине lords-02 и воспроизведён обращением к ней:
на двадцати осмотренных страницах тайтлов единственное встречающееся значение
длительности серии — ноль.

    <li class="episode"><span>Серия 1</span><span>0 мин</span></li>

Причина в Core: провайдер поэпизодного хронометража не отдаёт вовсе, а
`factory/lords/live_catalog.py` создавал серии как
``fx.Episode(number=i, name=..., runtime_min=0)`` — то есть **выдумывал ноль**.

Ноль минут — не длительность, а её отсутствие, и разница видна зрителю:
«0 мин» сообщает, что серия пустая, тогда как на самом деле длительность
просто не передана. Страница тайтла это решение уже содержала —
`render.py` скрывает нулевую длительность с прямым комментарием, — а список
серий строкой выше печатал её безусловно. Одно решение, применённое в одном
месте и не применённое в соседнем.
"""
from __future__ import annotations

import pytest

from factory.lords import fixtures as fx
from factory.lords import render as render_mod


class TestМодельРазличаетНольИНеизвестно:
    def test_серия_без_длительности_хранит_none(self):
        episode = fx.Episode(number=1, name="Серия 1")
        assert episode.runtime_min is None, (
            "серия без переданной длительности получила число: неизвестное "
            "стало нулём ещё в модели")

    def test_сезон_без_известных_длительностей_даёт_none(self):
        season = fx.Season(number=1, episodes=(
            fx.Episode(number=1, name="Серия 1"),
            fx.Episode(number=2, name="Серия 2"),
        ))
        assert season.runtime_min is None, (
            "сумма неизвестных величин объявлена нулём")

    def test_сезон_суммирует_только_известное(self):
        season = fx.Season(number=1, episodes=(
            fx.Episode(number=1, name="Серия 1", runtime_min=24),
            fx.Episode(number=2, name="Серия 2"),
        ))
        assert season.runtime_min == 24, (
            "известная длительность потерялась из-за соседней неизвестной")


class TestРазметкаНеПечатаетЛожныйНоль:
    @staticmethod
    def _список(episodes) -> str:
        season = fx.Season(number=1, episodes=tuple(episodes))
        return render_mod._episode_items(season)

    def test_неизвестная_длительность_не_печатается(self):
        html = self._список([fx.Episode(number=1, name="Серия 1")])
        assert "мин" not in html, (
            f"отсутствие длительности напечатано как значение: {html}")
        assert "Серия 1" in html, "сама серия исчезла вместе с длительностью"

    def test_известная_длительность_печатается(self):
        html = self._список([fx.Episode(number=1, name="Серия 1", runtime_min=24)])
        assert "24 мин" in html

    def test_ноль_остаётся_отсутствием(self):
        # Ноль, пришедший из источника, тоже не длительность: серии в ноль
        # минут не бывает. Различать «источник прислал 0» и «источник промолчал»
        # здесь незачем — зрителю в обоих случаях показывать нечего.
        html = self._список([fx.Episode(number=1, name="Серия 1", runtime_min=0)])
        assert "мин" not in html

    def test_смешанный_список_показывает_только_известное(self):
        html = self._список([
            fx.Episode(number=1, name="Серия 1", runtime_min=24),
            fx.Episode(number=2, name="Серия 2"),
        ])
        assert html.count("мин") == 1, f"лишнее упоминание длительности: {html}"
        assert "24 мин" in html


class TestЖивойКаталогНеВыдумываетНоль:
    def test_серии_из_живого_ответа_без_длительности(self):
        from factory.lords.live_catalog import seasons_from_detail

        seasons = seasons_from_detail([{"number": 1, "episodes_count": 3}])
        assert seasons, "сезоны не разобраны"
        episodes = seasons[0].episodes
        assert len(episodes) == 3
        assert all(e.runtime_min is None for e in episodes), (
            "живой каталог выдумал длительность серий, которой источник не давал: "
            f"{[e.runtime_min for e in episodes]}")

    def test_страница_серий_живого_ответа_не_содержит_нуля(self):
        # Сквозная проверка: от разбора ответа источника до разметки.
        from factory.lords.live_catalog import seasons_from_detail

        seasons = seasons_from_detail([{"number": 1, "episodes_count": 4}])
        html = render_mod._episode_items(seasons[0])
        assert "0 мин" not in html, f"ложный ноль дошёл до разметки: {html[:160]}"
        assert html.count("<li class=\"episode\">") == 4
