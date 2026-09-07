"""Сериал без данных о сезонах не выдаётся за полнометражную запись.

## Что наблюдалось на боевой витрине

На странице записи типа «Сериал» стоял текст:

    «У полнометражной записи сезонов нет: страница ведёт к одному просмотру,
    а не к списку серий.»

Страница одновременно называла запись сериалом и утверждала, что она
полнометражная. Зритель получает противоречие и не узнаёт, где серии.

## Почему так вышло

Заглушка выбиралась по признаку `episodic`, а он равен `bool(seasons)`. Сезоны
приходят только через обогащение, а оно покрывает 12 010 записей из 53 249 —
22,6 %. Сериалов при этом помечено 20 314, то есть примерно у 86 % сериальных
страниц сезонов нет просто потому, что до них не дошло обогащение.

Измерено отдельно: среди обогащённых сериалов сезоны есть у **100 %** (923 из
923). Данные не теряются — их ещё не запросили.

## Что требуется

Три состояния вместо двух:

* фильм — сезонов нет и не будет, так и написано;
* сериал с сезонами — список;
* **сериал без данных** — честное «данные о сериях пока не получены», а не
  утверждение, что запись полнометражная.

Глубина обогащения принадлежит Core. Шаблон обязан не лгать о том, чего не
получил.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from factory.lords import fixtures as fx  # noqa: E402
from factory.lords import render as render_mod  # noqa: E402


def _title(content_type: str, seasons=()) -> fx.Title:
    return fx.Title(slug="t", name="Запись", original_name="",
                    content_type=content_type, year=2024, country_slug="ssha",
                    country="США", genre_slugs=(), genres=(), studio="",
                    runtime_min=None, age_rating="", summary="", seasons=seasons)


def _text(html: str) -> str:
    return re.sub(r"<[^>]+>", " ", html).lower()


class TestТриСостоянияВместоДвух:
    def test_фильм_говорит_что_сезонов_не_будет(self):
        text = _text(render_mod._seasons_block(_title(fx.MOVIES)))
        assert "полнометражн" in text

    def test_сериал_без_сезонов_не_называется_полнометражным(self):
        text = _text(render_mod._seasons_block(_title(fx.SERIES)))
        assert "полнометражн" not in text, (
            "страница называет сериал полнометражной записью — она противоречит "
            "собственному типу и не объясняет, где серии")

    def test_сериал_без_сезонов_объясняет_состояние(self):
        text = _text(render_mod._seasons_block(_title(fx.SERIES)))
        assert any(w in text for w in ("пока", "ещё", "не получен", "нет данных")), (
            f"состояние не объяснено: {text[:120]}")

    def test_сериал_с_сезонами_показывает_список(self):
        season = fx.Season(number=1, episodes=(
            fx.Episode(number=1, name="Серия 1", runtime_min=24),))
        html = render_mod._seasons_block(_title(fx.SERIES, seasons=(season,)))
        assert "Серия 1" in html
        assert "полнометражн" not in _text(html)

    def test_аниме_и_дорама_ведут_себя_как_сериал(self):
        """Многосерийными бывают не только «Сериалы»: у аниме и дорам тот же
        разговор о сезонах, и списывать их в полнометражные так же неверно."""
        for kind in (fx.ANIME, fx.DORAMA):
            text = _text(render_mod._seasons_block(_title(kind)))
            assert "полнометражн" not in text, f"{kind} назван полнометражным"
