"""Mutation- и adversarial-проверки сверки утверждений с фактами.

Мутация вносится в ГОТОВЫЙ ТЕКСТ, а не в факты. Так проверяется то, что
действительно нужно: заметит ли контур ложь в том, что увидит человек. Если
бы мы правили факты, тест доказывал бы лишь согласованность двух копий одних
и тех же данных.

Каждая подмена обязана быть обнаружена. Тест, который «иногда» ловит подмену,
здесь не годится: он означал бы, что часть лжи проходит.
"""
from __future__ import annotations

import pytest

from factory.seo_content.claims import extract_and_verify
from factory.seo_content.draft import ClaimVerdict
from factory.seo_content.testing import пакет_серии, пакет_тайтла

ЧИСТЫЙ = ("«Тихая гавань» (Quiet Harbour) — сериал 2019 года производства "
          "России. В центре истории — смотритель маяка Вера Ильина. "
          "Заявленные жанры — драма и детектив. В каталоге — 3 сезона и "
          "24 серии; завершён.")

#: (имя подмены, что пишем в тексте вместо правды, тип утверждения)
ПОДМЕНЫ = [
    ("год", ЧИСТЫЙ.replace("2019", "2014"), "year"),
    ("название", ЧИСТЫЙ.replace("«Тихая гавань»", "«Шумная бухта»"), "title"),
    ("оригинальное название",
     ЧИСТЫЙ.replace("(Quiet Harbour)", "«Loud Bay»"), "title"),
    ("тип произведения", ЧИСТЫЙ.replace("сериал", "документальный фильм"),
     "work_type"),
    ("страна", ЧИСТЫЙ.replace("России", "Японии"), "country"),
    ("жанр", ЧИСТЫЙ.replace("драма и детектив", "комедия и мюзикл"), "genre"),
    ("число сезонов", ЧИСТЫЙ.replace("3 сезона", "7 сезонов"), "season_count"),
    ("число серий", ЧИСТЫЙ.replace("24 серии", "48 серий"), "episode_count"),
    ("статус выхода", ЧИСТЫЙ.replace("завершён", "выходит"), "release_status"),
]


class TestПодменаВТекстеОбнаруживается:
    @pytest.mark.parametrize("имя,текст,тип",
                             ПОДМЕНЫ, ids=[п[0] for п in ПОДМЕНЫ])
    def test_подмена_даёт_опровержение(self, имя, текст, тип):
        отчёт = extract_and_verify(пакет_тайтла(), {"body_description": текст})
        опровергнутые = [c for c in отчёт.contradicted if c.claim_type == тип]
        assert опровергнутые, (
            f"подмена «{имя}» не обнаружена; вердикты: "
            f"{[(c.claim_type, c.verdict.value) for c in отчёт.claims]}")
        assert опровергнутые[0].fact_id, "опровержение без ссылки на факт"

    def test_чистый_текст_не_опровергается(self):
        отчёт = extract_and_verify(пакет_тайтла(), {"body_description": ЧИСТЫЙ})
        assert отчёт.contradicted == []
        assert отчёт.unsupported_material == []

    def test_каждое_подтверждение_несёт_факт(self):
        отчёт = extract_and_verify(пакет_тайтла(), {"body_description": ЧИСТЫЙ})
        подтверждённые = отчёт.by_verdict(ClaimVerdict.SUPPORTED)
        assert подтверждённые
        assert all(c.fact_id for c in подтверждённые)


class TestВыдуманныеИменаИСобытия:
    def test_чужое_имя_не_подтверждается(self):
        текст = ЧИСТЫЙ.replace("Вера Ильина", "Аркадий Незнамов")
        отчёт = extract_and_verify(пакет_тайтла(), {"body_description": текст})
        чужие = [c for c in отчёт.claims if c.claim_type == "person"
                 and c.verdict is ClaimVerdict.UNSUPPORTED]
        assert чужие, [c.text for c in отчёт.claims if c.claim_type == "person"]

    def test_подтверждённое_имя_проходит(self):
        отчёт = extract_and_verify(пакет_тайтла(), {"body_description": ЧИСТЫЙ})
        свои = [c for c in отчёт.claims if c.claim_type == "person"]
        assert свои and all(c.verdict is ClaimVerdict.SUPPORTED for c in свои)

    def test_добавленная_награда_остаётся_недоказанной(self):
        текст = ЧИСТЫЙ + " Сериал получил премию «Золотой маяк» 2021 года."
        отчёт = extract_and_verify(пакет_тайтла(), {"body_description": текст})
        assert отчёт.contradicted or отчёт.unsupported_material, (
            "выдуманная награда прошла обе проверки")


class TestОбещаниеПросмотра:
    ФРАЗЫ = ["смотреть онлайн", "доступен для просмотра", "можно посмотреть",
             "все серии доступны"]

    @pytest.mark.parametrize("фраза", ФРАЗЫ)
    def test_обещание_при_недоступном_источнике(self, фраза):
        from factory.seo_content.testing import заменить_факт
        p = заменить_факт(пакет_тайтла(), "/video_availability", "UNAVAILABLE")
        отчёт = extract_and_verify(p, {"body_description": f"{ЧИСТЫЙ} {фраза}."})
        assert отчёт.player_false, "ложное обещание просмотра не обнаружено"

    @pytest.mark.parametrize("фраза", ФРАЗЫ)
    def test_обещание_при_неизмеренной_доступности(self, фраза):
        from factory.seo_content.testing import заменить_факт
        p = заменить_факт(пакет_тайтла(), "/video_availability", "UNKNOWN")
        отчёт = extract_and_verify(p, {"body_description": f"{ЧИСТЫЙ} {фраза}."})
        assert отчёт.player_false, (
            "«не измеряли» не то же самое, что «доступно»")

    def test_обещание_при_доступном_источнике_проходит(self):
        отчёт = extract_and_verify(
            пакет_тайтла(), {"body_description": f"{ЧИСТЫЙ} Смотреть онлайн."})
        assert отчёт.player_false == []


СЕРИЯ_ЧИСТАЯ = ("Серия 100 5-го сезона «Расколотая битвой синева небес» — "
                "«Накладная». Смена на станции принимает груз, которого нет "
                "в накладной.")


class TestПодменаНомеровСерии:
    @pytest.mark.parametrize("подмена,тип", [
        ("Серия 106", "episode_number"),
        ("Серия 196", "episode_number"),
    ])
    def test_чужой_номер_серии_опровергается(self, подмена, тип):
        текст = СЕРИЯ_ЧИСТАЯ.replace("Серия 100", подмена)
        отчёт = extract_and_verify(пакет_серии(), {"body_description": текст})
        assert [c for c in отчёт.contradicted if c.claim_type == тип]

    def test_чужой_номер_сезона_опровергается(self):
        текст = СЕРИЯ_ЧИСТАЯ.replace("5-го сезона", "сезон 4")
        отчёт = extract_and_verify(пакет_серии(), {"body_description": текст})
        assert [c for c in отчёт.contradicted if c.claim_type == "season_number"]

    def test_абсолютный_номер_не_годится_как_отображаемый(self):
        """196 — настоящий абсолютный номер этой же серии. В тексте он
        всё равно ложь: зритель видит сотую."""
        текст = СЕРИЯ_ЧИСТАЯ.replace("Серия 100", "Серия 196")
        отчёт = extract_and_verify(пакет_серии(), {"body_description": текст})
        assert [c for c in отчёт.contradicted if c.claim_type == "episode_number"]


class TestГраницыРазбора:
    def test_текст_без_утверждений_помечается_стилем(self):
        отчёт = extract_and_verify(
            пакет_тайтла(),
            {"body_description": "Эта работа заслуживает отдельного разговора."})
        assert отчёт.by_verdict(ClaimVerdict.NON_FACTUAL_STYLE)
        assert not отчёт.contradicted

    def test_слово_из_факта_не_становится_чужим_утверждением(self):
        """«В военном городке» — не заявление жанра «военный»."""
        from factory.seo_content.testing import заменить_факт
        p = заменить_факт(пакет_тайтла(), "/setting", "в военном городке")
        отчёт = extract_and_verify(
            p, {"body_description": "«Тихая гавань» — сериал 2019 года. "
                                    "Действие происходит в военном городке."})
        военные = [c for c in отчёт.claims if c.claim_type == "genre"
                   and c.text == "военный"]
        assert военные and военные[0].verdict is ClaimVerdict.SUPPORTED
        assert военные[0].fact_id == p.fact_id_for("/setting")
