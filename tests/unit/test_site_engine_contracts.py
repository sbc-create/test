"""Нормализованная модель: что она обязана удерживать.

Каждая проверка соответствует уже случившейся ошибке, а не воображаемой.
"""
from datetime import datetime, timezone

import pytest

from factory.site_engine.contracts import (
    ContentEvent,
    ContractError,
    CoverageReport,
    EpisodeCounts,
    EventType,
    ExternalIds,
    IngestionRun,
    PlaybackAvailability,
    Rating,
    Season,
    Title,
)

MOMENT = datetime(2026, 8, 30, 12, 0, tzinfo=timezone.utc)


def make_title(**kw) -> Title:
    base = {"canonical_id": "p:1", "provider": "p", "provider_id": "1",
            "name": "Тайтл", "observed_at": MOMENT}
    base.update(kw)
    return Title(**base)


class TestВремя:
    def test_наивное_время_не_принимается(self):
        """Наивная метка молча трактуется как локальная, а хосты живут в разных зонах."""
        with pytest.raises(ContractError, match="без часового пояса"):
            make_title(observed_at=datetime(2026, 8, 30, 12, 0))

    def test_время_поставщика_может_отсутствовать(self):
        """Карточка поставщика `updated_at` не содержит — и это законно."""
        assert make_title().provider_timestamp is None

    def test_время_приводится_к_utc(self):
        from datetime import timedelta

        moscow = datetime(2026, 8, 30, 15, 0, tzinfo=timezone(timedelta(hours=3)))
        assert make_title(observed_at=moscow).observed_at == MOMENT


class TestОценки:
    def test_вне_шкалы_отклоняется(self):
        """Оценка 85 — не «высокая оценка», а неверно понятый источник."""
        with pytest.raises(ContractError, match="вне шкалы"):
            Rating(source="kinopoisk", value=85.0)

    def test_порядок_источников_задан_владельцем(self):
        title = make_title(ratings=(Rating("imdb", 7.0), Rating("kinopoisk", 8.5)))
        assert title.best_rating().source == "kinopoisk"

    def test_без_оценок_возвращается_ничего(self):
        assert make_title().best_rating() is None


class TestСерии:
    def test_неизвестное_число_серий_это_не_ноль(self):
        """«Серий нет» и «неизвестно, сколько» — разные утверждения."""
        assert make_title().available_episodes is None
        assert make_title(episode_counts=EpisodeCounts(available=0)).available_episodes == 0

    def test_счётчики_суммируются_по_сезонам(self):
        title = make_title(seasons=(
            Season(number=1, available_episodes_count=12),
            Season(number=2, available_episodes_count=5),
        ))
        assert title.available_episodes == 17

    def test_сезон_с_отрицательным_счётчиком_отклоняется(self):
        with pytest.raises(ContractError):
            Season(number=1, available_episodes_count=-1)


class TestРедакторскиеПравки:
    def test_поля_поставщика_править_нельзя(self):
        """Правка сезонов означала бы, что витрина сообщает о содержимом небывшее."""
        with pytest.raises(ContractError, match="принадлежат поставщику"):
            make_title().with_overrides({"seasons": ()})

    def test_разрешённое_поле_меняется_копией(self):
        title = make_title()
        changed = title.with_overrides({"name": "Другое"})
        assert changed.name == "Другое"
        assert title.name == "Тайтл", "исходная запись обязана остаться нетронутой"


class TestСобытия:
    def test_без_ключа_идемпотентности_событие_не_создать(self):
        with pytest.raises(ContractError, match="idempotency_key"):
            ContentEvent(event_id="e", event_type=EventType.EPISODE_ADDED, provider="p",
                         provider_id="1", canonical_title_id="p:1", observed_at=MOMENT,
                         idempotency_key="")

    def test_каждое_событие_сбрасывает_теги(self):
        """Событие, не сбрасывающее ни одного тега, до страницы не доедет."""
        мимо = {EventType.SOURCE_ANOMALY}
        for kind in EventType:
            event = ContentEvent(event_id="e", event_type=kind, provider="p", provider_id="1",
                                 canonical_title_id="p:1", observed_at=MOMENT,
                                 idempotency_key="k")
            if kind in мимо:
                continue
            assert event.cache_tags(), f"{kind.value} не сбрасывает ничего"

    def test_выход_серии_обновляет_полку_новых_серий(self):
        event = ContentEvent(event_id="e", event_type=EventType.EPISODE_ADDED, provider="p",
                             provider_id="1", canonical_title_id="p:1", observed_at=MOMENT,
                             idempotency_key="k")
        assert "shelf:new-episodes" in event.cache_tags()


class TestПолнота:
    def test_молчание_источника_это_не_полнота(self):
        """`None` — «источник не сказал сколько», а не «всё на месте»."""
        report = CoverageReport(site_id="s", source_total=None, local_total=100,
                                observed_at=MOMENT)
        assert report.complete is None
        assert report.missing is None

    def test_недобор_виден(self):
        report = CoverageReport(site_id="s", source_total=53116, local_total=4800,
                                observed_at=MOMENT)
        assert report.complete is False
        assert report.missing == 48316

    def test_обрыв_каталога_не_успех(self):
        """Прогон, оборвавший каталог, обязан называться оборванным."""
        run = IngestionRun(run_id="r", site_id="s", started_at=MOMENT, finished_at=MOMENT,
                           truncated=True)
        assert run.status == "truncated"

    def test_прогон_без_отказов_успешен(self):
        run = IngestionRun(run_id="r", site_id="s", started_at=MOMENT, finished_at=MOMENT)
        assert run.status == "succeeded"


class TestВнешниеИдентификаторы:
    def test_пустые_не_попадают_в_вывод(self):
        assert ExternalIds(kp="1", imdb=None).as_dict() == {"kp": "1"}


class TestДоступность:
    def test_время_проверки_обязано_быть_с_зоной(self):
        with pytest.raises(ContractError):
            PlaybackAvailability(available=True, checked_at=datetime(2026, 1, 1))

    def test_доступность_без_времени_допустима(self):
        assert PlaybackAvailability(available=True).checked_at is None
