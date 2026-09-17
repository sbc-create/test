"""Адаптеры: подключение существующих реализаций без изменения их поведения.

Тесты работают на фикстурах формата, снятого с настоящих файлов. Отдельно
проверяется, что адаптеры остаются пригодны и когда живых данных нет.
"""
import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from factory.site_engine import renderers
from factory.site_engine.adapters.lords import LordsCatalogAdapter
from factory.site_engine.adapters.lords_renderer import LordsRendererAdapter
from factory.site_engine.adapters.yummy import YummyWatcherAdapter
from factory.site_engine.adapters.yummy_renderer import YummyRendererAdapter
from factory.site_engine.ingestion import IngestionService, diff_titles
from factory.site_engine.profiles import load_profile
from factory.site_engine.providers import ProviderContractBroken, ProviderUnavailable
from factory.site_engine.store import InMemoryStore

ROOT = Path(__file__).resolve().parents[2]
MOMENT = datetime(2026, 8, 30, 12, 0, tzinfo=timezone.utc)

#: Форма записи снята с настоящего кэша Lords (53 116 записей).
ЗАПИСЬ_LORDS = {
    "external_id": "01a052c9-7090-7640-9c32-737878eaca65",
    "name": "Приятель",
    "year": 2026,
    "is_series": False,
    "imdb_rating": 6.6,
    "kinopoisk_rating": None,
    "external_ids": {"imdb": "37281055", "kinopoisk": "8549783"},
    "playback": {"aggregator": "kp", "title_id": "8549783"},
    "poster_url": "https://poster.example/1.webp",
    "created_at": "2026-08-30T13:08:48Z",
    "updated_at": "2026-08-30T13:08:52Z",
}

#: Форма записи снята с настоящего снимка наблюдателя (6 774 записи).
ЗАПИСЬ_YUMMY = {
    "id": "01a03ceb-8309-7452-a66b-bde66e5c6c1f",
    "name": "Проект Кирамэки",
    "originalName": "Kirameki",
    "posterUrl": "https://poster.example/2.webp",
    "kinopoiskScore": None,
    "imdbScore": None,
    "typeLabel": "series",
    "year": 2026,
    "seasonsCount": 1,
    "plannedEpisodes": 5,
    "availableEpisodes": 5,
    "maxSeason": 1,
    "maxEpisode": 5,
    "videoAvailable": True,
    "providerUpdatedAt": "2026-08-23T19:32:31Z",
    "observedAt": "2026-08-30T12:00:00Z",
}


@pytest.fixture
def кэш_lords(tmp_path: Path) -> Path:
    путь = tmp_path / "lords-01.json"
    путь.write_text(json.dumps({"fetched_at_ms": 0, "source": "live",
                                "items": [ЗАПИСЬ_LORDS]}, ensure_ascii=False),
                    encoding="utf-8")
    return путь


@pytest.fixture
def снимок_yummy(tmp_path: Path) -> Path:
    путь = tmp_path / "watcher.json"
    путь.write_text(json.dumps({"version": 2, "titles": {ЗАПИСЬ_YUMMY["id"]: ЗАПИСЬ_YUMMY}},
                               ensure_ascii=False), encoding="utf-8")
    return путь


class TestАдаптерLords:
    def test_идентификатор_берётся_из_поля_кэша(self, кэш_lords):
        """Кэш называет его `external_id`, а не `id`."""
        тайтл = next(iter(LordsCatalogAdapter(cache_path=кэш_lords).walk_titles()))
        assert тайтл.provider_id == ЗАПИСЬ_LORDS["external_id"]
        assert тайтл.canonical_id.endswith(ЗАПИСЬ_LORDS["external_id"])

    def test_кинопоиск_читается_под_своим_именем(self, кэш_lords):
        """У двух представлений источника поле называется по-разному."""
        тайтл = next(iter(LordsCatalogAdapter(cache_path=кэш_lords).walk_titles()))
        assert тайтл.external_ids.kp == "8549783"

    def test_нулевая_оценка_не_придумывается(self, кэш_lords):
        тайтл = next(iter(LordsCatalogAdapter(cache_path=кэш_lords).walk_titles()))
        assert [r.source for r in тайтл.ratings] == ["imdb"]
        assert тайтл.best_rating().value == 6.6

    def test_время_поставщика_переносится_из_списка(self, кэш_lords):
        """`updated_at` есть у списка каталога — в карточке его нет."""
        тайтл = next(iter(LordsCatalogAdapter(cache_path=кэш_lords).walk_titles()))
        assert тайтл.provider_timestamp is not None
        assert тайтл.provider_timestamp.tzinfo is not None

    def test_отсутствие_кэша_это_отказ_источника(self, tmp_path):
        """Витрина при этом остаётся на прежнем релизе — это last-known-good."""
        адаптер = LordsCatalogAdapter(cache_path=tmp_path / "нет.json")
        with pytest.raises(ProviderUnavailable):
            list(адаптер.walk_titles())
        assert адаптер.total_titles() is None

    def test_кэш_без_списка_записей_это_сломанный_контракт(self, tmp_path):
        путь = tmp_path / "плохой.json"
        путь.write_text('{"fetched_at_ms": 0}', encoding="utf-8")
        with pytest.raises(ProviderContractBroken):
            list(LordsCatalogAdapter(cache_path=путь).walk_titles())


class TestАдаптерYummy:
    def test_счётчики_серий_переносятся_как_счётчики(self, снимок_yummy):
        """Списка серий в снимке нет: достраивать сезоны значит выдумывать."""
        тайтл = next(iter(YummyWatcherAdapter(snapshot_path=снимок_yummy).walk_titles()))
        assert тайтл.seasons == ()
        assert тайтл.episode_counts.available == 5
        assert тайтл.available_episodes == 5

    def test_доступность_читается_из_своего_поля(self, снимок_yummy):
        тайтл = next(iter(YummyWatcherAdapter(snapshot_path=снимок_yummy).walk_titles()))
        assert тайтл.playback.available is True

    def test_время_наблюдения_берётся_из_снимка(self, снимок_yummy):
        тайтл = next(iter(YummyWatcherAdapter(snapshot_path=снимок_yummy).walk_titles()))
        assert тайтл.observed_at == MOMENT

    def test_версия_снимка_меняется_вместе_с_файлом(self, снимок_yummy):
        адаптер = YummyWatcherAdapter(snapshot_path=снимок_yummy)
        было = адаптер.snapshot_version()
        снимок_yummy.write_text(снимок_yummy.read_text(encoding="utf-8") + " ", encoding="utf-8")
        assert адаптер.snapshot_version() != было

    def test_без_снимка_версия_названа_прямо(self, tmp_path):
        адаптер = YummyWatcherAdapter(snapshot_path=tmp_path / "нет.json")
        assert адаптер.snapshot_version() == "отсутствует"


class TestРендереры:
    @pytest.fixture(autouse=True)
    def чистый_реестр(self):
        renderers.clear_registry()
        renderers.register(LordsRendererAdapter())
        renderers.register(YummyRendererAdapter())
        yield
        renderers.clear_registry()

    @pytest.mark.parametrize(
        "site_id,ожидание",
        [("lords-01", "lords-static"), ("lords-03", "lords-static"),
         ("yummyani-site", "yummy-hybrid"), ("yummyani-biz", "yummy-hybrid")],
    )
    def test_рендерер_выбирается_по_профилю_а_не_по_имени(self, site_id, ожидание):
        assert renderers.for_profile(load_profile(site_id, ROOT)).name == ожидание

    def test_рендерер_не_владеет_данными_и_не_создаёт_событий(self):
        for имя in renderers.registered():
            описание = renderers.get(имя).describe()
            assert описание["owns_data"] is False
            assert описание["emits_events"] is False

    def test_повторная_регистрация_отклоняется(self):
        with pytest.raises(Exception, match="уже зарегистрирован"):
            renderers.register(LordsRendererAdapter())


class TestДельтаСерий:
    def _тайтл(self, доступно):
        from factory.site_engine.contracts import Season, Title

        return Title(canonical_id="p:1", provider="p", provider_id="1", name="Т",
                     observed_at=MOMENT,
                     seasons=(Season(number=1, available_episodes_count=доступно),))

    def test_рост_счётчика_даёт_событие(self):
        события = diff_titles(self._тайтл(4), self._тайтл(5))
        assert [e.event_type.value for e in события] == ["EPISODE_ADDED"]
        assert события[0].payload["available_episodes"] == 5

    def test_без_прибавки_события_нет(self):
        """Отрицательный контроль: серии не выходило — события быть не должно."""
        assert diff_titles(self._тайтл(5), self._тайтл(5)) == []

    def test_убыль_серий_событием_о_выходе_не_считается(self):
        assert diff_titles(self._тайтл(5), self._тайтл(4)) == []

    def test_ключ_идемпотентности_устойчив(self):
        """Повторный цикл с тем же изменением обязан дать тот же ключ."""
        первый = diff_titles(self._тайтл(4), self._тайтл(5))[0]
        второй = diff_titles(self._тайтл(4), self._тайтл(5))[0]
        assert первый.idempotency_key == второй.idempotency_key

    def test_новая_запись_это_создание_а_не_выход_серии(self):
        события = diff_titles(None, self._тайтл(5))
        assert [e.event_type.value for e in события] == ["TITLE_CREATED"]


class TestПрогонОбхода:
    def test_обход_наполняет_хранилище_и_считает_покрытие(self, снимок_yummy):
        адаптер = YummyWatcherAdapter(snapshot_path=снимок_yummy)
        хранилище = InMemoryStore("yummyani-site")
        прогон = IngestionService(site_id="yummyani-site", adapter=адаптер,
                                  store=хранилище).run()
        assert прогон.titles_seen == 1
        assert прогон.status == "succeeded"
        assert прогон.coverage.complete is True

    def test_недобор_виден_как_обрыв(self, снимок_yummy):
        """Успешно завершившийся обход половины каталога — неудача, похожая на удачу."""
        адаптер = YummyWatcherAdapter(snapshot_path=снимок_yummy)
        адаптер.total_titles = lambda: 100
        прогон = IngestionService(site_id="s", adapter=адаптер,
                                  store=InMemoryStore("s")).run()
        assert прогон.status == "truncated"
        assert прогон.coverage.missing == 99

    def test_повторный_обход_не_дублирует_события(self, снимок_yummy):
        адаптер = YummyWatcherAdapter(snapshot_path=снимок_yummy)
        хранилище = InMemoryStore("s")
        сервис = IngestionService(site_id="s", adapter=адаптер, store=хранилище)
        сервис.run()
        было = len(сервис.events)
        сервис.run()
        assert len(сервис.events) == было, "тот же факт остаётся одним событием"
