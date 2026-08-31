"""Карта зависимостей: смысл в том, чего она НЕ трогает.

Соблазн добавить ресурс «на всякий случай» велик, и каждое такое добавление
возвращает к полной пересборке маленькими шагами. Поэтому большая часть проверок
ниже — отрицательные.
"""
from datetime import datetime, timezone

import pytest

from factory.site_engine.contracts import ContentEvent, EventType
from factory.site_engine.dependencies import Plan, SiteContext, dry_run, plan_for

MOMENT = datetime(2026, 8, 31, 12, 0, tzinfo=timezone.utc)


def событие(kind: EventType, **payload) -> ContentEvent:
    return ContentEvent(
        event_id="e1", event_type=kind, provider="p", provider_id="1",
        canonical_title_id="p:1", observed_at=MOMENT, idempotency_key="k",
        payload=payload,
    )


def сайт(**kw) -> SiteContext:
    база = {
        "site_id": "lords-01",
        "title_path": "film",
        "listing_paths": ("/catalog/page/3/", "/catalog/page/1/"),
        "seasons": (1, 2),
    }
    база.update(kw)
    return SiteContext(**база)


def пути(план: Plan) -> set[str]:
    return {r.path for r in план.resources if r.kind == "page"}


class TestОдноСобытиеНеПерестраиваетСайт:
    def test_выход_серии_задевает_единицы_страниц(self):
        """Шестьдесят одна тысяча страниц против четырёх — в этом весь смысл."""
        план = plan_for(событие(EventType.EPISODE_ADDED, season=1, available_episodes=9),
                        [сайт()])
        assert план.page_count <= 5, план.as_dict()
        assert "/title/film/" in пути(план)
        assert "/title/film/season-1/" in пути(план)

    def test_обновление_оценки_не_трогает_главную(self):
        """Оценка меняет карточку, но не состав полок."""
        план = plan_for(событие(EventType.RATING_UPDATED, value=8.5), [сайт()])
        assert "/" not in пути(план)

    def test_обновление_расписания_не_трогает_карточку(self):
        план = plan_for(событие(EventType.SCHEDULE_UPDATED), [сайт(has_schedule=True)])
        assert пути(план) == {"/schedule/"}

    def test_новый_тайтл_не_трогает_страницы_сезонов(self):
        план = plan_for(событие(EventType.TITLE_CREATED), [сайт()])
        assert not any("season-" in p for p in пути(план))


class TestРесурсНеПопадаетЗря:
    def test_расписание_не_обновляется_там_где_выключено(self):
        план = plan_for(событие(EventType.SCHEDULE_UPDATED), [сайт(has_schedule=False)])
        assert план.resources == ()

    def test_анонсы_не_обновляются_там_где_выключены(self):
        план = plan_for(событие(EventType.ANNOUNCEMENT_UPDATED),
                        [сайт(has_announcements=False)])
        assert план.resources == ()

    def test_полка_новых_серий_не_трогается_там_где_её_нет(self):
        план = plan_for(событие(EventType.EPISODE_ADDED, season=1),
                        [сайт(has_news_shelf=False)])
        assert "/" not in пути(план)

    def test_страница_несуществующего_сезона_не_попадает_в_план(self):
        """Сезон 7 у сайта, знающего только первый и второй."""
        план = plan_for(событие(EventType.EPISODE_ADDED, season=7), [сайт()])
        assert not any("season-7" in p for p in пути(план))

    def test_карта_сайта_обновляется_только_при_новом_адресе(self):
        серия = plan_for(событие(EventType.EPISODE_ADDED, season=1), [сайт()])
        тайтл = plan_for(событие(EventType.TITLE_CREATED), [сайт()])
        assert not any(r.kind == "sitemap" for r in серия.resources)
        assert any(r.kind == "sitemap" for r in тайтл.resources)


class TestНесколькоСайтов:
    def test_план_охватывает_все_переданные_сайты(self):
        план = plan_for(событие(EventType.EPISODE_ADDED, season=1),
                        [сайт(site_id="lords-01"), сайт(site_id="lords-02")])
        assert план.site_ids == ("lords-01", "lords-02")

    def test_одинаковые_ресурсы_не_дублируются(self):
        план = plan_for(событие(EventType.EPISODE_ADDED, season=1),
                        [сайт(site_id="a"), сайт(site_id="b")])
        ключи = [(r.kind, r.path) for r in план.resources]
        assert len(ключи) == len(set(ключи))


class TestПричины:
    def test_у_каждого_ресурса_есть_причина(self):
        """Причина — не украшение: по ней видно, если ресурс попал зря."""
        план = plan_for(событие(EventType.EPISODE_ADDED, season=1), [сайт()])
        assert all(r.reason.strip() for r in план.resources)

    def test_seo_документ_идёт_за_карточкой(self):
        план = plan_for(событие(EventType.TITLE_UPDATED), [сайт()])
        assert any(r.kind == "seo" for r in план.resources)

    def test_seo_документ_не_идёт_без_карточки(self):
        план = plan_for(событие(EventType.SCHEDULE_UPDATED), [сайт(has_schedule=True)])
        assert not any(r.kind == "seo" for r in план.resources)


class TestТегиКэша:
    def test_теги_берутся_из_контракта_события(self):
        план = plan_for(событие(EventType.EPISODE_ADDED, season=1), [сайт()])
        assert "shelf:new-episodes" in план.cache_tags
        assert "title" in план.cache_tags

    def test_озвучка_не_сбрасывает_полку_новых_серий(self):
        план = plan_for(событие(EventType.VOICEOVER_ADDED), [сайт()])
        assert план.cache_tags == ("title",)


class TestСухойПрогон:
    def test_сухой_прогон_помечен_и_ничего_не_меняет(self):
        отчёт = dry_run(событие(EventType.EPISODE_ADDED, season=1), [сайт()])
        assert отчёт["dry_run"] is True
        assert отчёт["pages"] >= 1
        assert all("reason" in r for r in отчёт["resources"])

    def test_сухой_прогон_называет_сайты_и_теги(self):
        отчёт = dry_run(событие(EventType.EPISODE_ADDED, season=1),
                        [сайт(site_id="a"), сайт(site_id="b")])
        assert отчёт["sites"] == ["a", "b"]
        assert отчёт["cache_tags"]


class TestВсеРодыСобытий:
    @pytest.mark.parametrize("kind", list(EventType))
    def test_ни_одно_событие_не_роняет_планировщик(self, kind):
        план = plan_for(событие(kind, season=1), [сайт(has_schedule=True,
                                                       has_announcements=True)])
        assert isinstance(план.page_count, int)

    @pytest.mark.parametrize("kind", list(EventType))
    def test_ни_одно_событие_не_перестраивает_всё(self, kind):
        """Верхняя граница — десяток страниц, а не десятки тысяч."""
        план = plan_for(событие(kind, season=1), [сайт(has_schedule=True,
                                                       has_announcements=True)])
        assert план.page_count <= 10, f"{kind.value} задевает {план.page_count} страниц"
