"""Русский язык, стиль и редакционные заметки.

Отдельно зафиксирована граница: полная морфология и орфография здесь НЕ
проверяются, потому что ни `pymorphy`, ни LanguageTool в окружении нет, а
обязательной зависимости от публичной службы у контура быть не должно —
неопубликованный текст туда не отправляется. Проверка честно сообщает об
этом, и тест на это тоже есть: «ноль ошибок» не должно читаться как
«проверено всё».
"""
from __future__ import annotations

import pytest

from factory.seo_content import editorial as ED
from factory.seo_content.language import (LanguageValidator,
                                          languagetool_available,
                                          форма_числительного)
from factory.seo_content.testing import пакет_тайтла

ЧИСТЫЙ = ("«Тихая гавань» — сериал 2019 года производства России. В центре "
          "истории — смотритель маяка Вера Ильина. В каталоге — 3 сезона "
          "и 24 серии; завершён.")


def проверить(текст: str):
    return LanguageValidator(canonical_title="Тихая гавань",
                             allowed_titles=["Тихая гавань"]).validate(текст)


class TestЗапрещённыеШтампы:
    @pytest.mark.parametrize("фраза", [
        "Захватывающий сюжет держит до конца.",
        "Этот сериал никого не оставит равнодушным.",
        "Погрузитесь в удивительный мир героев.",
        "Любителям жанра обязательно понравится.",
        "Смотреть онлайн бесплатно в хорошем качестве.",
    ])
    def test_штамп_ловится(self, фраза):
        о = проверить(ЧИСТЫЙ + " " + фраза)
        assert о.cliches, [i.code for i in о.issues]
        assert all(i.severity == "CRITICAL" for i in о.cliches)

    def test_чистый_текст_без_штампов(self):
        assert проверить(ЧИСТЫЙ).cliches == []


class TestКритическиеОшибки:
    def test_смешение_кириллицы_и_латиницы(self):
        о = проверить(ЧИСТЫЙ.replace("Вера", "Вeра"))  # латинская e
        assert [i for i in о.issues if i.code == "SCRIPT_MIXING"]

    def test_переспам(self):
        текст = ("Сериал сериала сериалу сериалом о сериале. " * 6
                 + "Сериал про сериал и сериалы сериальные.")
        о = проверить(текст)
        assert [i for i in о.issues if i.code == "KEYWORD_STUFFING"]

    def test_обрыв_текста(self):
        о = проверить("«Тихая гавань» — сериал 2019 года производства и")
        assert [i for i in о.issues if i.code == "TRUNCATED_SENTENCE"]

    def test_машинная_конструкция(self):
        о = проверить("Вот описание: как языковая модель, я составил текст.")
        assert [i for i in о.issues if i.code == "MACHINE_CONSTRUCTION"]


class TestГрамматикаКоторуюМыДействительноПроверяем:
    @pytest.mark.parametrize("n,ожидание", [
        (1, "1 сезон"), (2, "2 сезона"), (4, "4 сезона"), (5, "5 сезонов"),
        (11, "11 сезонов"), (12, "12 сезонов"), (14, "14 сезонов"),
        (21, "21 сезон"), (22, "22 сезона"), (25, "25 сезонов"),
        (101, "101 сезон"), (111, "111 сезонов"),
    ])
    def test_счётная_форма(self, n, ожидание):
        from factory.seo_content.writer import счётная
        assert счётная(n, "сезон") == ожидание

    def test_несогласованное_числительное_ловится(self):
        о = проверить("В каталоге — 2 сезонов и 21 серий.")
        коды = [i.detail for i in о.issues if i.code == "NUMERAL_AGREEMENT"]
        assert len(коды) == 2

    def test_год_не_считается_счётной_формой(self):
        """«2019 года» — это год, а не две тысячи девятнадцать лет."""
        о = проверить("Сериал 2019 года и 2021 года.")
        assert [i for i in о.issues if i.code == "NUMERAL_AGREEMENT"] == []

    def test_склонение_названия_в_кавычках(self):
        о = проверить("События «Тихой гавани» разворачиваются на острове.")
        assert [i for i in о.issues if i.code == "TITLE_DECLINED"]

    def test_повтор_слова_подряд(self):
        о = проверить("Сериал рассказывает о о смотрителе маяка.")
        assert [i for i in о.issues if i.code == "DOUBLED_WORD"]

    def test_незакрытая_кавычка(self):
        о = проверить("«Тихая гавань — сериал 2019 года.")
        assert [i for i in о.issues if i.code == "UNBALANCED_QUOTES"]


class TestЧегоМыНеПроверяем:
    def test_орфография_объявлена_непроверенной(self):
        о = проверить(ЧИСТЫЙ)
        доступен, _ = languagetool_available()
        if not доступен:
            assert о.evaluated["spelling"].startswith("NOT_EVALUATED")

    def test_морфология_объявлена_частичной(self):
        о = проверить(ЧИСТЫЙ)
        assert о.evaluated["full_morphology"].startswith("NOT_EVALUATED")

    def test_публичный_languagetool_не_используется(self, monkeypatch):
        monkeypatch.setenv("LANGUAGETOOL_URL", "https://api.languagetool.org")
        monkeypatch.delenv("LANGUAGETOOL_SELF_HOSTED", raising=False)
        доступен, причина = languagetool_available()
        assert not доступен and "публичный сервис" in причина


class TestРедакционныеЗаметки:
    def заметка(self, текст, *, note_id="n1", refs=("f-studio",),
                angle="production"):
        return ED.EditorialNote(
            note_id=note_id, site_id="seo-test-0001", entity_type="title",
            entity_id="title-0001", locale="ru", text=текст,
            fact_refs=tuple(refs), angle=angle,
            model_version="m", prompt_version="p")

    def test_поля_пользовательского_отзыва_отклоняются(self):
        for поле in ("rating", "author_name", "likes", "replies", "posted_at"):
            with pytest.raises(ED.FakeUgcAttempt):
                ED.reject_ugc_fields({"text": "x", поле: 1})

    @pytest.mark.parametrize("тип", ["Review", "AggregateRating", "Rating"])
    def test_разметка_отзыва_отклоняется(self, тип):
        with pytest.raises(ED.FakeUgcAttempt):
            ED.reject_review_markup(f'{{"@type": "{тип}"}}')

    def test_заметка_без_фактов_не_создаётся(self):
        with pytest.raises(ED.FakeUgcAttempt):
            self.заметка("Мысль без основания", refs=())

    def test_выдуманный_личный_опыт_отсеивается(self):
        n = self.заметка("Я смотрел это и мне понравилось.")
        отчёт = ED.validate_notes([n], pack=пакет_тайтла(), body=ЧИСТЫЙ)
        assert отчёт.notes == []
        assert "INVENTED_PERSONAL_EXPERIENCE" in отчёт.rejected[0]["reasons"]

    def test_повтор_основного_описания_отсеивается(self):
        n = self.заметка(ЧИСТЫЙ)
        отчёт = ED.validate_notes([n], pack=пакет_тайтла(), body=ЧИСТЫЙ)
        assert отчёт.notes == []
        assert "DUPLICATES_BODY" in отчёт.rejected[0]["reasons"]

    def test_повтор_между_страницами_отсеивается(self):
        n = self.заметка("Производством занималась «Северный контур».")
        отчёт = ED.validate_notes([n], pack=пакет_тайтла(), body=ЧИСТЫЙ,
                                  corpus_note_hashes=[n.text_sha256])
        assert "REPEATED_ACROSS_PAGES" in отчёт.rejected[0]["reasons"]

    def test_неизвестная_ссылка_на_факт_отсеивается(self):
        n = self.заметка("Мысль.", refs=("f-несуществующий",))
        отчёт = ED.validate_notes([n], pack=пакет_тайтла(), body=ЧИСТЫЙ)
        assert any(r.startswith("FACT_REF_UNKNOWN")
                   for r in отчёт.rejected[0]["reasons"])

    def test_спойлер_выше_разрешённого_отсеивается(self):
        n = self.заметка("В финале сезона погибает главный герой.")
        отчёт = ED.validate_notes([n], pack=пакет_тайтла(), body=ЧИСТЫЙ)
        assert "SPOILER_ABOVE_ALLOWED" in отчёт.rejected[0]["reasons"]

    def test_больше_трёх_заметок_не_принимается(self):
        заметки = [self.заметка(f"Мысль номер {i} о производстве.",
                                note_id=f"n{i}") for i in range(5)]
        отчёт = ED.validate_notes(заметки, pack=пакет_тайтла(), body=ЧИСТЫЙ)
        assert len(отчёт.notes) == ED.MAX_NOTES

    def test_пустой_массив_допустимый_исход(self):
        отчёт = ED.validate_notes([], pack=пакет_тайтла(), body=ЧИСТЫЙ)
        assert отчёт.notes == [] and отчёт.rejected == []

    def test_счётчики_подделок_всегда_нулевые(self):
        д = ED.validate_notes([], pack=пакет_тайтла(), body=None).to_dict()
        for ключ in ("auto_user_comments_created", "fake_personas",
                     "fake_timestamps", "fake_likes", "fake_replies",
                     "model_reviews", "model_ratings"):
            assert д[ключ] == 0

    def test_заметка_не_может_объявить_себя_отзывом(self):
        with pytest.raises(ED.FakeUgcAttempt):
            ED.EditorialNote(
                note_id="n", site_id="s", entity_type="title",
                entity_id="e", locale="ru", text="t", fact_refs=("f-studio",),
                angle="a", model_version="m", prompt_version="p",
                comment_mode="USER_COMMENT")
