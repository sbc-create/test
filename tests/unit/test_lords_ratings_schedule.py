"""Оценки и расписание Lords говорят читателю правду.

Две правки в одном месте, потому что обе про одно: страница не должна обещать
того, чего у неё нет, и не должна показывать техническую кухню.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest
import yaml

from factory.lords import fixtures as fx
from factory.lords import render
from factory.paths import PATHS

SITES = ("lords-01", "lords-02", "lords-03")


def package(site_id: str) -> dict:
    return yaml.safe_load(PATHS.site_package(site_id).read_text(encoding="utf-8"))


def page_body(site_id: str, path: str) -> str:
    site = render.render_site(package(site_id), catalog=fx.build_catalog())
    page = site.pages.get(path)
    assert page is not None, f"нет страницы {path}"
    return page.body


class TestRatingFormat:
    def test_rating_uses_a_comma(self):
        """По-русски дробная часть отделяется запятой."""
        assert render._format_rating(7.282) == "7,3"
        assert render._format_rating(9.0) == "9,0"

    def test_zero_is_not_a_rating(self):
        assert render._format_rating(0) is None
        assert render._format_rating(None) is None

    def test_value_outside_the_scale_is_refused(self):
        # 1135533 — это идентификатор Кинопоиска, а не балл.
        assert render._format_rating(1135533) is None
        assert render._format_rating(-1) is None

    def test_no_place_formats_a_rating_by_hand(self):
        """Форматирование живёт в одном помощнике.

        Отрисовать оценку на фикстуре нельзя — в фикстурном каталоге оценок нет
        вовсе. Зато можно запретить то, из-за чего дефект и возник: карточка,
        карусель и страница произведения форматировали число каждая сама, и
        точка осталась там, куда правка не дошла.
        """
        source = Path(render.__file__).read_text(encoding="utf-8")
        # Ручным считается формат без замены точки на запятую. Внутри самого
        # помощника `:.1f` законен — он там и превращается в запятую.
        offenders = [
            line.strip()
            for line in source.splitlines()
            if ":.1f}" in line and 'replace(".", ",")' not in line
        ]
        assert offenders == [], f"оценка форматируется вручную: {offenders}"
        assert "_format_rating" in source


class TestScheduleHonesty:
    @pytest.mark.parametrize("site_id", SITES)
    def test_no_stand_vocabulary_in_the_calendar_text(self, site_id):
        """Каталог давно настоящий, а календарь говорил о стенде и синтетике.

        Проверяется именно текст календаря. Баннер фикстурного каталога выше по
        странице появляется только при сборке из фикстуры и на живом сайте его
        нет — предъявлять его этому тесту значило бы искать дефект там, где
        поведение верное.
        """
        body = page_body(site_id, "/schedule/")
        match = re.search(r"<section class=\"section\"><h2>Сезоны.*?</section>", body, re.S)
        assert match, "секции календаря нет"
        calendar = re.sub(r"<[^>]+>", " ", match.group(0)).lower()
        for word in ("стенд", "синтетическ", "выдуман", "условный"):
            assert word not in calendar, f"внутреннее слово «{word}» в тексте календаря"

    @pytest.mark.parametrize("site_id", SITES)
    def test_page_does_not_promise_dates_it_has_not(self, site_id):
        """Источник не сообщает ни дат премьер, ни дат выхода серий.

        Вступление обещало «ближайшие серии по дням» и «прошедшие дни уходят в
        новинки», а на странице не было ни одной даты: список шёл по алфавиту.
        """
        body = page_body(site_id, "/schedule/")
        text = re.sub(r"<[^>]+>", " ", body).lower()
        for promise in ("по дням", "ближайшие серии", "прошедшие дни", "дата выхода"):
            assert promise not in text, f"обещание «{promise}» без данных"

    @pytest.mark.parametrize("site_id", SITES)
    def test_the_page_explains_what_it_actually_shows(self, site_id):
        body = page_body(site_id, "/schedule/")
        text = re.sub(r"<[^>]+>", " ", body)
        assert len(text.split()) >= 25, "страница слишком пуста, чтобы быть полезной"
