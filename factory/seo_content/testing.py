"""Оснастка проверок контура качества SEO-контента.

Лежит в пакете, а не в каталоге тестов: репозиторий собирает тесты в режиме
importlib, и модуль оттуда не импортируется. При импорте ничего не делает.

Все пакеты фактов здесь синтетические. Названия вымышлены, витрины носят
идентификаторы `seo-test-*`, боевого каталога оснастка не касается.
"""
from __future__ import annotations

from .factpack import ConflictStatus, Fact, SEOFactPack

ВРЕМЯ = "2026-09-01T00:00:00Z"


def факт(fact_id: str, путь: str, значение, *, source_id="src-catalog",
         provider="internal_catalog", conflict="NONE",
         confidence=1.0) -> Fact:
    return Fact(fact_id=fact_id, source_id=source_id, provider=provider,
                retrieved_at=ВРЕМЯ, snapshot_hash="h-" + fact_id,
                field_path=путь, value=значение, confidence=confidence,
                conflict_status=ConflictStatus(conflict),
                source_license="internal")


def пакет_тайтла(**переопределения) -> SEOFactPack:
    факты = [
        факт("f-title", "/canonical_title_ru", "Тихая гавань"),
        факт("f-orig", "/original_title", "Quiet Harbour"),
        факт("f-type", "/work_type", "series"),
        факт("f-year", "/year", 2019),
        факт("f-country", "/countries", ["Россия"]),
        факт("f-genre", "/genres", ["драма", "детектив"]),
        факт("f-subject", "/premise_subject", "смотритель маяка Вера Ильина"),
        факт("f-setting", "/setting", "на острове с одним причалом"),
        факт("f-conflict", "/premise_conflict",
             "единственный катер снимают с рейса, и связь с берегом рвётся"),
        факт("f-chars", "/characters",
             [{"name": "Вера Ильина", "actor": "Мария Соколова"}]),
        факт("f-seasons", "/season_count", 3),
        факт("f-declared", "/declared_episode_count", 24),
        факт("f-actual", "/actual_episode_count", 24),
        факт("f-status", "/release_status", "completed"),
        факт("f-video", "/video_availability", "AVAILABLE"),
        факт("f-age", "/age_rating", "16+"),
        факт("f-studio", "/studio", "Студия «Северный контур»"),
        факт("f-spoiler", "/spoiler_level", "PREMISE"),
    ]
    основа = dict(site_id="seo-test-0001", entity_type="title",
                  entity_id="title-0001", title_id="title-0001",
                  season_id=None, episode_id=None, locale="ru",
                  facts=tuple(факты), event_type="title.created",
                  event_id="ev-0001")
    основа.update(переопределения)
    return SEOFactPack(**основа)


def пакет_сезона(номер: int = 2) -> SEOFactPack:
    факты = [ф for ф in пакет_тайтла().facts
             if ф.field_path not in ("/season_count",)]
    факты += [факт("f-snum", "/season_number", номер),
              факт("f-arc", "/season_arc",
                   "маяк передают другому ведомству, и прежние правила "
                   "перестают действовать"),
              факт("f-pos", "/season_position",
                   "продолжение первого сезона без перерыва в хронологии")]
    return SEOFactPack(
        site_id="seo-test-0001", entity_type="season",
        entity_id=f"title-0001-s{номер}", title_id="title-0001",
        season_id=f"title-0001-s{номер}", episode_id=None, locale="ru",
        facts=tuple(факты), event_type="season.created",
        event_id=f"ev-s{номер}")


def пакет_серии(*, номер_в_сезоне=100, отображаемый=100, абсолютный=196,
                номер_источника=100, сезон=5, заявлено=210,
                фактически=210) -> SEOFactPack:
    """Пакет серии с ПЯТЬЮ разными номерами.

    Значения по умолчанию воспроизводят разобранную регрессию: у тайтла
    заявлено 210 серий, адрес несёт число 100, абсолютный номер 196.
    """
    факты = [
        факт("f-title", "/canonical_title_ru",
             "Расколотая битвой синева небес"),
        факт("f-type", "/work_type", "anime"),
        факт("f-year", "/year", 2018),
        факт("f-genre", "/genres", ["фэнтези", "приключения"]),
        факт("f-snum", "/season_number", сезон),
        факт("f-ein", "/episode_in_season_number", номер_в_сезоне),
        факт("f-eabs", "/episode_absolute_number", абсолютный),
        факт("f-esrc", "/episode_source_number", номер_источника),
        факт("f-edisp", "/episode_display_number", отображаемый),
        факт("f-edecl", "/declared_episode_count", заявлено),
        факт("f-eact", "/actual_episode_count", фактически),
        факт("f-efocus", "/episode_focus",
             "смена на станции принимает груз, которого нет в накладной"),
        факт("f-etitle", "/episode_title", "Накладная"),
        факт("f-video", "/video_availability", "AVAILABLE"),
        факт("f-spoiler", "/spoiler_level", "PREMISE"),
    ]
    return SEOFactPack(
        site_id="seo-test-0001", entity_type="episode",
        entity_id="ep-0100", title_id="title-0500",
        season_id="title-0500-s5", episode_id="ep-0100", locale="ru",
        facts=tuple(факты), event_type="episode.created",
        event_id="ev-ep-0100")


def заменить_факт(pack: SEOFactPack, путь: str, значение) -> SEOFactPack:
    """Тот же пакет с одним подменённым значением. Для mutation-проверок."""
    import dataclasses
    факты = [ф for ф in pack.facts if ф.field_path != путь]
    старый = next((ф for ф in pack.facts if ф.field_path == путь), None)
    факты.append(факт(старый.fact_id if старый else "f-mut", путь, значение))
    return dataclasses.replace(pack, facts=tuple(факты))
