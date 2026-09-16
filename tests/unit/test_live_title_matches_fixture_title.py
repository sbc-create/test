"""Живая карточка не отстаёт от фикстурной по набору полей.

`LiveTitle` повторяет набор полей `fx.Title` вручную — так написано в его же
докстроке, и причина названа: рендерер обращается именно к этим полям, а живая
карточка добавляет то, чего у фикстуры быть не может, — подтверждённые оценки
и настоящий постер.

Повторяет вручную, а сверять было нечем. Поле, добавленное в фикстуру и
забытое здесь, ломает не тесты — тесты на фикстуре как раз проходят, — а живые
страницы, и обнаружится это на витрине.

Отсюда правило проверки: живая карточка обязана иметь **всё**, что есть у
фикстурной. Обратное неверно и не проверяется: своих полей у неё четырнадцать,
и это не долг, а разница между настоящими данными и синтетическими.
"""

from __future__ import annotations

import dataclasses
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from factory.lords import fixtures as fx  # noqa: E402
from factory.lords import live_catalog as lc  # noqa: E402


def _fields(cls) -> set[str]:
    return {f.name for f in dataclasses.fields(cls)}


def _properties(cls) -> set[str]:
    return {n for n in dir(cls) if isinstance(getattr(cls, n, None), property)}


def _обращения(source: str) -> set[str]:
    """Что рендерер читает у карточки.

    Скобка после имени исключается намеренно: в рендерере есть локальные
    строки с тем же именем `title`, и `title.endswith(...)` — вызов метода
    строки, а не поле карточки. Первая редакция проверки объявила `endswith`
    отсутствующим полем обеих моделей.
    """
    return {name for name, следом in re.findall(r"\btitle\.([a-z_]+)\b(\s*\()?", source)
            if not следом}


class TestНаборПолейНеРасходится:
    def test_живая_карточка_имеет_все_поля_фикстурной(self):
        нет = sorted(_fields(fx.Title) - _fields(lc.LiveTitle))
        assert нет == [], (
            f"поля есть у фикстуры и нет у живой карточки: {нет}. "
            "Рендерер обращается к ним на обеих, и живые страницы сломаются "
            "там, где тесты на фикстуре останутся зелёными")

    def test_свойства_тоже_не_расходятся(self):
        """Свойство читается рендерером так же, как поле."""
        нет = sorted(_properties(fx.Title) - _properties(lc.LiveTitle))
        assert нет == [], f"свойства есть у фикстуры и нет у живой карточки: {нет}"

    def test_у_живой_карточки_есть_своё(self):
        """Проверка симметричной не является и не должна быть.

        Подтверждённые оценки, внешние идентификаторы и настоящий постер у
        синтетического каталога взяться неоткуда.
        """
        своё = _fields(lc.LiveTitle) - _fields(fx.Title)
        assert "kinopoisk_id" in своё and "poster_url" in своё


class TestРендерерЧитаетОдноИТоЖе:
    def test_поля_из_разметки_есть_у_обеих(self):
        """Что рендерер берёт у карточки, то обязано быть у обеих.

        Список не выписан руками, а собран из самого рендерера: выписанный
        руками расходится с кодом ровно так же, как расходились эти два класса.
        """
        source = (ROOT / "factory" / "lords" / "render.py").read_text(encoding="utf-8")
        обращения = _обращения(source)
        известные = (_fields(fx.Title) | _properties(fx.Title)
                     | _fields(lc.LiveTitle) | _properties(lc.LiveTitle))
        неизвестные = sorted(обращения - известные)
        assert неизвестные == [], (
            f"рендерер читает у карточки то, чего нет ни у одной модели: {неизвестные}")

    def test_каждое_обращение_есть_у_живой_карточки(self):
        source = (ROOT / "factory" / "lords" / "render.py").read_text(encoding="utf-8")
        обращения = _обращения(source)
        живые = _fields(lc.LiveTitle) | _properties(lc.LiveTitle)
        нет = sorted(обращения - живые)
        assert нет == [], (
            f"рендерер читает {нет} — на живой витрине этого поля нет")
