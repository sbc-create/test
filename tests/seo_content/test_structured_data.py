"""JSON-LD и техническое соответствие.

Главное утверждение набора: разметка не вправе обещать машине больше, чем
видит человек и чем подтверждено фактами. Отдельно закреплено, что
техническая исправность разметки не является доказательством показа rich
result — это разные утверждения, и путать их в отчёте нельзя.
"""
from __future__ import annotations

import json

import pytest

from factory.seo_content import structured_data as SD
from factory.seo_content.testing import (заменить_факт, пакет_сезона,
                                         пакет_серии, пакет_тайтла)

САЙТ = "https://seo-test-0001.invalid"


def разметка_тайтла(pack=None, **kw):
    pack = pack or пакет_тайтла()
    return pack, SD.build_jsonld(pack, site_url=САЙТ,
                                 canonical_path="/title/tihaya-gavan/", **kw)


class TestТипПоСущности:
    def test_сериал(self):
        _, узлы = разметка_тайтла()
        assert узлы[0]["@type"] == "TVSeries"

    def test_фильм(self):
        p = заменить_факт(пакет_тайтла(), "/work_type", "movie")
        _, узлы = разметка_тайтла(p)
        assert узлы[0]["@type"] == "Movie"

    def test_сезон(self):
        p = пакет_сезона(2)
        узлы = SD.build_jsonld(p, site_url=САЙТ,
                               canonical_path="/title/x/season/2/",
                               season_number=2, title_path="/title/x/")
        assert узлы[0]["@type"] == "TVSeason"
        assert узлы[0]["seasonNumber"] == 2
        assert узлы[0]["isPartOf"]["@id"].endswith("/title/x/")

    def test_серия(self):
        p = пакет_серии()
        узлы = SD.build_jsonld(p, site_url=САЙТ,
                               canonical_path="/t/x/season/5/episode/100",
                               display_number=100, title_path="/t/x/",
                               season_path="/t/x/season/5/")
        assert узлы[0]["@type"] == "TVEpisode"
        assert узлы[0]["episodeNumber"] == 100
        assert узлы[0]["partOfSeries"]["@id"].endswith("/t/x/")

    def test_чужой_тип_ловится(self):
        p, узлы = разметка_тайтла()
        узлы[0]["@type"] = "Movie"
        о = SD.validate(узлы, pack=p, canonical_html="/title/tihaya-gavan/",
                        canonical_sitemap="/title/tihaya-gavan/")
        assert [i for i in о.issues if i.code == "ENTITY_TYPE_MISMATCH"]


class TestVideoObject:
    def test_есть_при_доступном_и_разрешённом_источнике(self):
        _, узлы = разметка_тайтла(video_url=f"{САЙТ}/v", video_license_ok=True)
        assert any(у["@type"] == "VideoObject" for у in узлы)

    def test_нет_при_недоступном_источнике(self):
        p = заменить_факт(пакет_тайтла(), "/video_availability", "UNAVAILABLE")
        _, узлы = разметка_тайтла(p, video_url=f"{САЙТ}/v",
                                  video_license_ok=True)
        assert not any(у["@type"] == "VideoObject" for у in узлы)

    def test_нет_без_разрешения_на_источник(self):
        _, узлы = разметка_тайтла(video_url=f"{САЙТ}/v", video_license_ok=False)
        assert not any(у["@type"] == "VideoObject" for у in узлы)

    def test_подсунутый_videoobject_ловится(self):
        p = заменить_факт(пакет_тайтла(), "/video_availability", "UNKNOWN")
        _, узлы = разметка_тайтла(p)
        узлы.append({"@type": "VideoObject", "contentUrl": "x"})
        о = SD.validate(узлы, pack=p, canonical_html="/title/tihaya-gavan/",
                        canonical_sitemap="/title/tihaya-gavan/")
        коды = {i.code for i in о.issues}
        assert "VIDEOOBJECT_WITHOUT_SOURCE" in коды
        assert "VIDEOOBJECT_NOT_ON_PAGE" in коды


class TestОтзывовИРейтинговНеБывает:
    @pytest.mark.parametrize("тип", ["Review", "AggregateRating", "Rating"])
    def test_разметка_отзыва_ловится(self, тип):
        p, узлы = разметка_тайтла()
        узлы.append({"@type": тип, "reviewBody": "текст модели"})
        о = SD.validate(узлы, pack=p, canonical_html="/title/tihaya-gavan/",
                        canonical_sitemap="/title/tihaya-gavan/")
        assert о.fake_review_markup >= 1

    def test_обычная_разметка_отзывов_не_содержит(self):
        p, узлы = разметка_тайтла(video_url=f"{САЙТ}/v", video_license_ok=True)
        о = SD.validate(узлы, pack=p, canonical_html="/title/tihaya-gavan/",
                        canonical_sitemap="/title/tihaya-gavan/",
                        video_present=True)
        assert о.fake_review_markup == 0


class TestCanonicalИВидимоеСовпадают:
    def test_расхождение_canonical_ловится(self):
        p, узлы = разметка_тайтла()
        о = SD.validate(узлы, pack=p, canonical_html="/title/tihaya-gavan/",
                        canonical_sitemap="/title/другой/")
        assert о.canonical_conflicts >= 1

    def test_внутренняя_ссылка_учитывается(self):
        p, узлы = разметка_тайтла()
        о = SD.validate(узлы, pack=p, canonical_html="/title/tihaya-gavan/",
                        canonical_sitemap="/title/tihaya-gavan/",
                        internal_links=["/title/tihaya-gavan"])
        assert о.canonical_conflicts >= 1

    def test_h1_и_name_должны_совпадать(self):
        p, узлы = разметка_тайтла()
        о = SD.validate(узлы, pack=p, canonical_html="/title/tihaya-gavan/",
                        canonical_sitemap="/title/tihaya-gavan/",
                        visible_h1="Совсем другое произведение")
        assert о.visible_mismatches >= 1

    def test_крошки_интерфейса_и_разметки_совпадают(self):
        p = пакет_тайтла()
        узлы = SD.build_jsonld(
            p, site_url=САЙТ, canonical_path="/title/tihaya-gavan/",
            breadcrumbs=(("Главная", "/"), ("Сериалы", "/series/"),
                         ("Тихая гавань", "/title/tihaya-gavan/")))
        о = SD.validate(узлы, pack=p, canonical_html="/title/tihaya-gavan/",
                        canonical_sitemap="/title/tihaya-gavan/",
                        visible_breadcrumbs=("Главная", "Фильмы",
                                             "Тихая гавань"))
        assert о.visible_mismatches >= 1


class TestНомераВРазметке:
    def test_чужой_номер_серии_ловится(self):
        p = пакет_серии()
        узлы = SD.build_jsonld(p, site_url=САЙТ,
                               canonical_path="/t/x/season/5/episode/100",
                               display_number=100, title_path="/t/x/",
                               season_path="/t/x/season/5/")
        узлы[0]["episodeNumber"] = 106
        о = SD.validate(узлы, pack=p, canonical_html="/t/x/season/5/episode/100",
                        canonical_sitemap="/t/x/season/5/episode/100",
                        display_number=100)
        assert [i for i in о.issues if i.code == "EPISODE_NUMBER_MISMATCH"]

    def test_сезон_без_связи_с_тайтлом_ловится(self):
        p = пакет_сезона(2)
        узлы = SD.build_jsonld(p, site_url=САЙТ,
                               canonical_path="/title/x/season/2/",
                               season_number=2)
        о = SD.validate(узлы, pack=p, canonical_html="/title/x/season/2/",
                        canonical_sitemap="/title/x/season/2/",
                        season_number=2)
        assert [i for i in о.issues if i.code == "MISSING_IS_PART_OF"]


class TestРазметкаНеДоказательствоПоказа:
    def test_статус_показа_не_объявляется(self):
        p, узлы = разметка_тайтла()
        о = SD.validate(узлы, pack=p, canonical_html="/title/tihaya-gavan/",
                        canonical_sitemap="/title/tihaya-gavan/")
        assert о.rich_result_status == "NOT_OBSERVED"
        assert "rich result" in о.rich_result_reason

    def test_разметка_разбирается_как_json(self):
        _, узлы = разметка_тайтла()
        json.loads(json.dumps(узлы, ensure_ascii=False))
