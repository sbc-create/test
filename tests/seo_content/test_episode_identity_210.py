"""Пять чисел серии и регрессия на двухстах десяти сериях.

Разобранный случай:

    https://yummyani.site/anime/raskolotaya-bitvoy-sineva-nebes-5/season/5/episode/100

У тайтла заявлено 210 серий, интерфейс обрывался на сотой. Здесь проверяется
не то, что число в адресе «правильное», а то, что оно вообще не является
доказательством номера серии, и что контур отказывается писать текст, пока
номер не разрешён снаружи.
"""
from __future__ import annotations

import pytest

from factory.seo_content import identity as ID
from factory.seo_content.draft import GateStatus
from factory.seo_content.pipeline import ContentPipeline, SiteContext
from factory.seo_content.testing import пакет_серии

ГРАНИЦЫ = (1, 2, 99, 100, 101, 209, 210)

БОЕВОЙ_АДРЕС = ("https://yummyani.site/anime/raskolotaya-bitvoy-sineva-nebes-5"
                "/season/5/episode/100")


def маршрут(**переопределения) -> ID.Route:
    основа = dict(url="/anime/raskolotaya-bitvoy-sineva-nebes-5/season/5/"
                      "episode/100",
                  resolved_entity_id="ep-0100", url_number=100,
                  numbering_scheme="display", season_url_number=5,
                  canonical="/anime/raskolotaya-bitvoy-sineva-nebes-5/season/5/"
                            "episode/100",
                  breadcrumbs=("Главная", "Аниме", "Расколотая битвой синева "
                               "небес", "Сезон 5", "Серия 100"))
    основа.update(переопределения)
    return ID.Route(**основа)


class TestЧислоВАдресеНеДоказательство:
    def test_адрес_разбирается_но_ничего_не_утверждает(self):
        assert ID.url_number(БОЕВОЙ_АДРЕС) == 100
        assert ID.url_number(БОЕВОЙ_АДРЕС, "season") == 5

    def test_нумерация_адреса_обязана_быть_объявлена(self):
        """Без объявления схемы «100» — просто ключ маршрута."""
        отчёт = ID.resolve_episode_identity(
            пакет_серии(), маршрут(numbering_scheme=None))
        assert отчёт.code == ID.IdentityCode.URL_NUMBERING_SCHEME_UNDECLARED
        assert not отчёт.ok

    def test_адрес_расходится_с_объявленной_нумерацией(self):
        """Каталог сдвинут на шесть спешлов: в адресе 100, показывается 106."""
        отчёт = ID.resolve_episode_identity(
            пакет_серии(отображаемый=106), маршрут())
        assert отчёт.code == ID.IdentityCode.URL_NUMBER_MISMATCH

    def test_адрес_ведёт_к_другой_сущности(self):
        отчёт = ID.resolve_episode_identity(
            пакет_серии(), маршрут(resolved_entity_id="ep-0101"))
        assert отчёт.code == ID.IdentityCode.URL_RESOLVES_TO_OTHER_EPISODE

    def test_совпадение_чисел_личности_не_доказывает(self):
        """Все пять чисел равны 100, но маршрут отдаёт другую серию.
        Совпадение чисел не должно перевешивать факт маршрута."""
        p = пакет_серии(номер_в_сезоне=100, отображаемый=100, абсолютный=100,
                        номер_источника=100)
        отчёт = ID.resolve_episode_identity(
            p, маршрут(resolved_entity_id="ep-другая"))
        assert отчёт.code == ID.IdentityCode.URL_RESOLVES_TO_OTHER_EPISODE


class TestПятьЧиселРазведены:
    def test_все_пять_попадают_в_отчёт(self):
        отчёт = ID.resolve_episode_identity(пакет_серии(), маршрут())
        assert отчёт.numbers == {"in_season": 100, "absolute": 196,
                                 "source": 100, "display": 100, "url": 100}

    def test_абсолютный_не_подменяет_отображаемый(self):
        отчёт = ID.resolve_episode_identity(пакет_серии(), маршрут())
        assert отчёт.display_number == 100 != отчёт.numbers["absolute"]

    def test_без_отображаемого_и_внутрисезонного_показать_нечем(self):
        import dataclasses
        p = пакет_серии()
        факты = [ф for ф in p.facts if ф.field_path not in
                 ("/episode_display_number", "/episode_in_season_number")]
        отчёт = ID.resolve_episode_identity(
            dataclasses.replace(p, facts=tuple(факты)),
            маршрут(numbering_scheme="source"))
        assert отчёт.code == ID.IdentityCode.NUMBERS_UNRESOLVED


class TestГраничныеНомера:
    @pytest.mark.parametrize("номер", ГРАНИЦЫ)
    def test_граница_разрешается(self, номер):
        p = пакет_серии(номер_в_сезоне=номер, отображаемый=номер,
                        номер_источника=номер, абсолютный=номер)
        отчёт = ID.resolve_episode_identity(
            p, маршрут(url_number=номер,
                       url=f"/anime/x/season/5/episode/{номер}",
                       canonical=f"/anime/x/season/5/episode/{номер}"))
        assert отчёт.ok, отчёт.problems
        assert отчёт.display_number == номер

    @pytest.mark.parametrize("номер", (101, 209, 210))
    def test_обрыв_перечня_на_сотой_виден(self, номер):
        """Ровно заявленный дефект: страница есть, пути к ней нет."""
        p = пакет_серии(номер_в_сезоне=номер, отображаемый=номер,
                        номер_источника=номер, абсолютный=номер)
        отчёт = ID.resolve_episode_identity(
            p, маршрут(url_number=номер, listing_truncated_at=100,
                       url=f"/anime/x/season/5/episode/{номер}",
                       canonical=f"/anime/x/season/5/episode/{номер}"))
        assert отчёт.code == ID.IdentityCode.EPISODE_NOT_REACHABLE

    @pytest.mark.parametrize("номер", (1, 2, 99, 100))
    def test_до_обрыва_серии_достижимы(self, номер):
        p = пакет_серии(номер_в_сезоне=номер, отображаемый=номер,
                        номер_источника=номер, абсолютный=номер)
        отчёт = ID.resolve_episode_identity(
            p, маршрут(url_number=номер, listing_truncated_at=100,
                       url=f"/anime/x/season/5/episode/{номер}",
                       canonical=f"/anime/x/season/5/episode/{номер}"))
        assert отчёт.ok

    def test_серия_за_пределами_фактически_доступных(self):
        p = пакет_серии(номер_в_сезоне=210, отображаемый=210,
                        номер_источника=210, абсолютный=210, фактически=100)
        отчёт = ID.resolve_episode_identity(
            p, маршрут(url_number=210,
                       url="/anime/x/season/5/episode/210",
                       canonical="/anime/x/season/5/episode/210"))
        assert отчёт.code == ID.IdentityCode.EPISODE_BEYOND_ACTUAL


class TestУстаревшийНомерНеОстаётсяНигде:
    ПОВЕРХНОСТИ = ("meta_title", "meta_description", "h1", "body",
                   "breadcrumbs", "canonical", "og_title", "jsonld")

    @pytest.mark.parametrize("поверхность", ПОВЕРХНОСТИ)
    def test_сотая_серия_ловится_на_каждой_поверхности(self, поверхность):
        беды = ID.stale_number_scan({поверхность: "Смотреть 100 серия"},
                                    episode_number=106, season_number=5)
        assert беды and поверхность in беды[0]

    def test_совпадающий_номер_не_поднимает_тревоги(self):
        assert ID.stale_number_scan(
            {"meta_title": "106 серия", "h1": "Серия 106"},
            episode_number=106, season_number=None) == []

    def test_номер_сезона_проверяется_отдельно(self):
        беды = ID.stale_number_scan({"breadcrumbs": "Сезон 4 / Серия 106"},
                                    episode_number=106, season_number=5)
        assert беды and "номер сезона" in беды[0]


class TestГенерацияОстанавливаетсяДоТекста:
    def test_без_разрешённого_номера_текст_не_пишется(self, tmp_path):
        """Writer не выводит номер сам: вывести его можно было бы только
        догадкой, а догадка здесь и есть выдумывание."""
        конвейер = ContentPipeline()
        сайт = SiteContext("seo-test-0001", "https://seo-test-0001.invalid",
                           own_angle="разборы")
        р = конвейер.run_pack(пакет_серии(отображаемый=106), site=сайт,
                              route=маршрут())
        assert р.status is GateStatus.REJECTED
        assert any("EPISODE_IDENTITY_CONFLICT" in п
                   for п in р.draft.rejection_reasons)

    def test_разрешённая_личность_даёт_текст_с_тем_же_номером(self):
        конвейер = ContentPipeline()
        сайт = SiteContext("seo-test-0001", "https://seo-test-0001.invalid",
                           own_angle="разборы")
        р = конвейер.run_pack(пакет_серии(), site=сайт, route=маршрут())
        assert р.status is GateStatus.PASSED, р.draft.rejection_reasons
        for текст in р.draft.texts().values():
            assert "106" not in текст
        assert "100" in (р.draft.h1_recommendation or "")
