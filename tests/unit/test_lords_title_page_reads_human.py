"""Страница произведения говорит с посетителем на его языке.

Четыре вещи на ней были написаны для машины, а не для человека: раздел
назывался «Структура», дата выводилась как «2024-11-21», в озвучках печатался
служебный словарь источника, а внизу стояло поле «Происхождение данных»,
которое посетителю ничего не сообщает.
"""
from __future__ import annotations

import pytest

from factory.lords import fixtures as fx
from factory.lords.live_catalog import voice_names
from factory.lords.render import _human_date, render_site


class TestVoicesAreNamesNotCodes:
    def test_a_studio_name_wins_and_loses_its_decorations(self):
        assert voice_names([
            {"voice_type": "multivoice", "voice_type_label": "Многоголосый",
             "studio_code": "muzoboz", "studio_name": "@MUZOBOZ@"}
        ]) == ("MUZOBOZ",)

    def test_without_a_studio_the_kind_is_named(self):
        assert voice_names([
            {"voice_type": "subtitles", "voice_type_label": "Субтитры", "studio_name": None}
        ]) == ("Субтитры",)

    def test_a_bare_code_is_not_shown(self):
        # «multivoice» ничего не сообщает тому, кто пришёл смотреть.
        assert voice_names(["multivoice"]) == ()
        assert voice_names(["subtitles", "Студия Х"]) == ("Студия Х",)

    def test_the_raw_dictionary_never_reaches_the_page(self):
        rendered = " ".join(voice_names([
            {"voice_type": "multivoice", "studio_code": "muzoboz", "studio_name": "Студия"}
        ]))
        for leak in ("voice_type", "studio_code", "created_at", "{", "}"):
            assert leak not in rendered

    def test_repeats_collapse_and_order_holds(self):
        assert voice_names([
            {"studio_name": "Б"}, {"studio_name": "А"}, {"studio_name": "Б"}
        ]) == ("Б", "А")

    @pytest.mark.parametrize("junk", [None, [], [{}], [""], [None]])
    def test_nothing_useful_yields_nothing(self, junk):
        assert voice_names(junk) == ()


class TestDateReadsLikeADate:
    @pytest.mark.parametrize(("raw", "shown"), [
        ("2024-11-21", "21.11.2024"),
        ("2026-08-28T09:31:46Z", "28.08.2026"),
        ("2026-01-05", "05.01.2026"),
    ])
    def test_iso_becomes_dotted(self, raw, shown):
        assert _human_date(raw) == shown

    def test_a_year_alone_stays_a_year(self):
        # Придумывать день и месяц нельзя: источник их не сообщил.
        assert _human_date("2019") == "2019"

    @pytest.mark.parametrize("empty", ["", None, "   "])
    def test_absent_date_shows_nothing(self, empty):
        assert _human_date(empty) == ""


class TestThePageNamesItsSectionsPlainly:
    @pytest.fixture
    def page(self):
        from pathlib import Path

        import yaml

        package = yaml.safe_load(
            Path("sites/lords-01/package.yaml").read_text(encoding="utf-8"))
        site = render_site(package, catalog=fx.build_catalog())
        path = next(p for p in site.pages if p.startswith("/title/"))
        return site.pages[path].body

    def test_the_section_is_called_about_the_film(self, page):
        assert "О фильме" in page
        assert "Структура" not in page

    def test_the_data_origin_row_is_gone(self, page):
        # Служебное поле не сообщает посетителю ничего о фильме.
        assert "Происхождение данных" not in page

    def test_no_iso_date_is_printed(self, page):
        import re

        assert not re.search(r">\d{4}-\d{2}-\d{2}<", page)
