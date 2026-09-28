"""Контрактные тесты Site Engine API v1.

Проверяется форма ответа, а не совпадение с реализацией: тест, повторяющий
реализацию, не поймает её ошибку.
"""
from datetime import datetime, timezone
from pathlib import Path

import pytest

from factory.site_engine.api import create_api
from factory.site_engine.api.app import MAX_LIMIT, SiteEngineApi, api_enabled
from factory.site_engine.contracts import EpisodeCounts, PlaybackAvailability, Rating, Title
from factory.site_engine.store import InMemoryStore, WriteToken

ROOT = Path(__file__).resolve().parents[2]
ВКЛЮЧЁН = {"SITE_ENGINE_API_ENABLED": "1", "SITE_ENGINE_ENVIRONMENT": "test"}
MOMENT = datetime(2026, 8, 30, 12, 0, tzinfo=timezone.utc)


def наполнить(store: InMemoryStore, сколько: int = 5) -> None:
    token = WriteToken(run_id="test", site_id=store.site_id)
    store.declare_source_total(token, сколько * 2)
    store.put(
        token,
        [
            Title(
                canonical_id=f"p:{i}",
                provider="p",
                provider_id=str(i),
                name=f"Тайтл {i}",
                observed_at=MOMENT,
                year=2020 + i,
                kind="series" if i % 2 else "movie",
                ratings=(Rating("kinopoisk", 7.0 + i / 10, observed_at=MOMENT),),
                episode_counts=EpisodeCounts(available=i),
                playback=PlaybackAvailability(available=bool(i % 2), checked_at=MOMENT),
            )
            for i in range(сколько)
        ],
    )


@pytest.fixture
def api() -> SiteEngineApi:
    def loader(profile):
        store = InMemoryStore(profile.site_id)
        наполнить(store)
        return store, "тестовый"

    return create_api(["yummyani-site", "lords-01", "demo-books"], root=ROOT,
                      loader=loader, env=ВКЛЮЧЁН)


class TestВыключенПоУмолчанию:
    def test_без_флага_маршрутов_нет(self):
        api = create_api(["lords-01"], root=ROOT,
                         loader=lambda p: (InMemoryStore(p.site_id), "нет"), env={})
        ответ = api.handle("/api/v1/health")
        assert ответ.status == 404, "выключенный API не должен отвечать содержательно"

    def test_в_production_не_включается_даже_с_флагом(self):
        """Маршрут, которого нет в production, невозможно там открыть."""
        assert not api_enabled({"SITE_ENGINE_API_ENABLED": "1",
                                "SITE_ENGINE_ENVIRONMENT": "production"})

    @pytest.mark.parametrize("значение", ["", "0", "false", "нет", "maybe"])
    def test_невнятный_флаг_считается_выключенным(self, значение):
        assert not api_enabled({"SITE_ENGINE_API_ENABLED": значение,
                                "SITE_ENGINE_ENVIRONMENT": "test"})


class TestФормаОтветов:
    def test_health(self, api):
        ответ = api.handle("/api/v1/health")
        assert ответ.status == 200
        assert ответ.body["version"] == "v1"
        assert ответ.body["sites"] == 3

    def test_список_сайтов(self, api):
        тело = api.handle("/api/v1/sites").body
        assert тело["total"] == len(тело["items"]) == 3
        assert {i["site_id"] for i in тело["items"]} == {"yummyani-site", "lords-01", "demo-books"}

    def test_сайт(self, api):
        тело = api.handle("/api/v1/sites/lords-01").body
        assert тело["site_id"] == "lords-01"
        assert тело["normalized_content"] == "content-ingestion"

    def test_новый_тип_сайта_берёт_контент_из_общего_api(self, api):
        тело = api.handle("/api/v1/sites/demo-books").body
        assert тело["normalized_content"] == "site-engine-api"

    def test_конфигурация_не_отдаёт_ссылок_на_секреты(self, api):
        тело = api.handle("/api/v1/sites/lords-01/config").body
        сериализованное = str(тело)
        assert "credentials_ref" not in сериализованное
        assert "token" not in сериализованное.lower()

    def test_покрытие_различает_недобор(self, api):
        тело = api.handle("/api/v1/sites/lords-01/coverage").body
        assert тело["local_total"] == 5
        assert тело["source_total"] == 10
        assert тело["missing"] == 5
        assert тело["complete"] is False


class TestСтраницы:
    def test_страница_сообщает_общее_число(self, api):
        тело = api.handle("/api/v1/sites/lords-01/titles", {"limit": 2}).body
        assert len(тело["items"]) == 2
        assert тело["total"] == 5
        assert тело["has_more"] is True

    def test_последняя_страница_не_обещает_продолжения(self, api):
        тело = api.handle("/api/v1/sites/lords-01/titles", {"offset": 4, "limit": 2}).body
        assert тело["has_more"] is False

    def test_слишком_большой_limit_это_ошибка_а_не_молчаливое_усечение(self, api):
        """Молча отдать меньше запрошенного — как раз то, чем каталог себя обманывал."""
        ответ = api.handle("/api/v1/sites/lords-01/titles", {"limit": MAX_LIMIT + 1})
        assert ответ.status == 400
        assert ответ.body["error"]["code"] == "limit_too_large"

    @pytest.mark.parametrize("параметры", [{"offset": -1}, {"limit": 0}, {"limit": "много"}])
    def test_негодные_параметры_дают_400(self, api, параметры):
        assert api.handle("/api/v1/sites/lords-01/titles", параметры).status == 400


class TestОшибки:
    def test_несуществующий_сайт(self, api):
        ответ = api.handle("/api/v1/sites/нет-такого")
        assert ответ.status == 404
        assert ответ.body["error"]["code"] == "site_not_found"

    def test_несуществующий_тайтл(self, api):
        ответ = api.handle("/api/v1/sites/lords-01/titles/нет-такого")
        assert ответ.status == 404
        assert ответ.body["error"]["code"] == "title_not_found"

    def test_несуществующий_маршрут(self, api):
        assert api.handle("/api/v1/чего-то-нет").status == 404

    def test_ошибки_всегда_одной_формы(self, api):
        for путь, параметры in [
            ("/api/v1/sites/нет", {}),
            ("/api/v1/sites/lords-01/titles/нет", {}),
            ("/api/v1/sites/lords-01/titles", {"limit": 9999}),
        ]:
            тело = api.handle(путь, параметры).body
            assert set(тело) == {"error"}
            assert {"code", "message"} <= set(тело["error"])


class TestСерииИОценки:
    def test_отсутствие_списка_серий_названо_прямо(self, api):
        """Пустой список читался бы как «серий нет». Это разные утверждения."""
        тело = api.handle("/api/v1/sites/lords-01/titles/p:3/episodes").body
        assert тело["episode_list_available"] is False
        assert тело["counts"]["available"] == 3

    def test_оценки_отдаются_с_происхождением(self, api):
        тело = api.handle("/api/v1/sites/lords-01/titles/p:1/ratings").body
        assert тело["items"][0]["provenance"] == "provider"
        assert тело["best"]["source"] == "kinopoisk"


class TestПолки:
    def test_полки_строятся_из_хранилища(self, api):
        тело = api.handle("/api/v1/sites/lords-01/shelves", {"limit": 3}).body
        полки = {s["id"] for s in тело["shelves"]}
        assert "watchable" in полки
        for полка in тело["shelves"]:
            assert полка["items"], "пустая полка не должна попадать в ответ"

    def test_на_полке_смотрибельного_только_смотрибельное(self, api):
        тело = api.handle("/api/v1/sites/lords-01/shelves").body
        полка = next(s for s in тело["shelves"] if s["id"] == "watchable")
        assert all(i["watchable"] for i in полка["items"])


class TestПолкиИзВсегоКаталога:
    """Полка, собранная из первой страницы, — неверный ответ, выглядящий верным."""

    @pytest.fixture
    def большой_каталог(self):
        from factory.site_engine.contracts import PlaybackAvailability, Rating, Title
        from factory.site_engine.store import WriteToken

        store = InMemoryStore("lords-01")
        token = WriteToken("r", "lords-01")
        # Лучшая оценка намеренно лежит далеко за первой сотней.
        store.put(
            token,
            [
                Title(
                    canonical_id=f"p:{i}",
                    provider="p",
                    provider_id=str(i),
                    name=f"Т{i}",
                    observed_at=MOMENT,
                    ratings=(Rating("kinopoisk", 9.9 if i == 250 else 5.0,
                                    observed_at=MOMENT),),
                    playback=PlaybackAvailability(available=True, checked_at=MOMENT),
                )
                for i in range(300)
            ],
        )
        return create_api(["lords-01"], root=ROOT, loader=lambda pr: (store, "тест"),
                          env=ВКЛЮЧЁН)

    def test_просмотрен_весь_каталог(self, большой_каталог):
        тело = большой_каталог.handle("/api/v1/sites/lords-01/shelves").body
        assert тело["considered"] == 300, "полка обязана назвать, из чего собрана"

    def test_лучшее_за_пределами_первой_страницы_найдено(self, большой_каталог):
        тело = большой_каталог.handle("/api/v1/sites/lords-01/shelves", {"limit": 1}).body
        полка = next(s for s in тело["shelves"] if s["id"] == "top-rated")
        assert полка["items"][0]["canonical_id"] == "p:250"


class TestСборкаAPI:
    def test_несуществующий_профиль_это_отказ_а_не_молчание(self):
        """Собрать API меньшего состава и не сказать об этом — худший исход."""
        from factory.site_engine.profiles import ProfileNotFound

        with pytest.raises(ProfileNotFound):
            create_api(["нет-такого-сайта"], root=ROOT,
                       loader=lambda p: (InMemoryStore(p.site_id), "тест"), env=ВКЛЮЧЁН)
