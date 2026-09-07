"""Непроверенный поток — не подтверждённое отсутствие потока.

Два места продукта отвечали на один вопрос по-разному, и расхождение стоило
целого блока на всех витринах.

Рендерер плеера считает так: `playable is False` — источник подтвердил, что
играть нечего, плеер снимается; `None` — не проверяли, и запись плеер
сохраняет. Правило записано в самом поле: «неизвестность не должна снимать
плеер с записи, которая играет».

Ранжировщик полок считал иначе: он требовал подтверждённого потока и `None`
отвергал. На боевом каталоге поле `playable` не заполнено ни у одной записи —
проверка потока идёт отдельным процессом и до большинства записей не дошла. В
итоге полка «недавно добавленные» выходила пустой на **всех** живых витринах,
а верхняя карусель, объявленная в профилях, не отрисовывалась ни разу.

Заметить это чтением нельзя: оба места по отдельности выглядят правильно.
Видно только на живых данных — блок объявлен, а его нет.

Правило теперь одно и то же в обоих местах: исключает запись подтверждённое
отсутствие потока, а не отсутствие проверки.
"""

from __future__ import annotations

import pytest

from factory.lords import recommend as rec


class Запись:
    """Минимальная запись каталога в том виде, в каком её видит ранжировщик."""

    #: Жанры и годы намеренно разные: ранжировщик разбавляет полку и не ставит
    #: рядом однотипные записи. На двенадцати одинаковых записях полка выходит
    #: короче, и проверка падала бы не на том, что проверяет.
    ЖАНРЫ = (("драма",), ("комедия",), ("ужасы",), ("боевик",),
             ("детектив",), ("фантастика",))

    def __init__(self, playable=None, playback=None, slug="z-1", index=0):
        self.slug = slug
        self.name = f"Пример {index}"
        self.original_name = ""
        self.content_type = "movies"
        self.year = 2016 + index % 10
        self.country = ""
        self.genres = self.ЖАНРЫ[index % len(self.ЖАНРЫ)]
        self.seasons = ()
        # Постер обязателен для полки: карточка без обложки в карусели
        # выглядит дырой. У боевых записей он есть в 99,2 % случаев, и запись
        # без него была бы нетипичной, а не строгой.
        self.poster_url = f"https://poster.example.invalid/{slug}.webp"
        self.playable = playable
        self.playback = playback if playback is not None else {
            "aggregator": "kp", "title_id": "1",
        }
        self.created_at = f"2026-09-{6 - index % 5:02d}T12:00:00Z"
        self.updated_at = "2026-09-06T12:00:00Z"
        self.kinopoisk_rating = None
        self.imdb_rating = None

    @property
    def path(self) -> str:
        return f"/title/{self.slug}/"


class TestНеизвестностьНеСнимаетЗаписьСПолки:
    def test_непроверенный_поток_считается_пригодным(self):
        features = rec.features_from_title(Запись(playable=None))
        assert features.playback_state is True, (
            "непроверенная запись отвергается полкой, хотя плеер её показывает"
        )

    def test_подтверждённая_тишина_остаётся_отказом(self):
        features = rec.features_from_title(Запись(playable=False))
        assert features.playback_state is False, (
            "запись, у которой источник подтвердил отсутствие потока, попала на полку"
        )

    def test_подтверждённый_поток_остаётся_пригодным(self):
        assert rec.features_from_title(Запись(playable=True)).playback_state is True

    def test_запись_без_адресации_потока_не_выдаётся_за_играющую(self):
        """Нет ни агрегатора, ни идентификатора — играть нечем, и это факт."""
        features = rec.features_from_title(Запись(playable=None, playback={}))
        assert features.playback_state is None


class TestПолкаСобираетсяНаЖивыхДанных:
    @pytest.fixture()
    def записи(self):
        return [Запись(slug=f"z-{i}", index=i) for i in range(12)]

    def test_карусель_набирается(self, записи):
        shelf = rec.carousel_shelf(записи, domain=None)
        assert shelf is not None and len(shelf) >= 4, (
            f"полка из {0 if shelf is None else len(shelf)} записей: карусель не "
            "отрисуется, и объявленный профилем блок не появится"
        )

    def test_подтверждённо_молчащие_на_полку_не_идут(self):
        записи = [Запись(slug=f"z-{i}", index=i, playable=False) for i in range(12)]
        shelf = rec.carousel_shelf(записи, domain=None)
        assert shelf is None or len(shelf) == 0, (
            "на полку попали записи, у которых источник подтвердил отсутствие потока"
        )
