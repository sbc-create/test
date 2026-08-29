"""Футер обязан быть полезен читателю и различаться между сайтами.

Одинаковый подвал на шести витринах не сообщает ничего: он не помогает ни
человеку, ни поисковой системе. Поэтому у каждого сайта своё описание, а общими
остаются только те сведения, которые действительно общие, — контакт и источник
каталога.
"""
from __future__ import annotations

import datetime as dt
import re

import pytest
import yaml

from factory.lords import fixtures as fx
from factory.lords import render
from factory.paths import PATHS

SITES = ("lords-01", "lords-02", "lords-03")
CONTACT = "sbc.claude@yandex.ru"


def package(site_id: str) -> dict:
    return yaml.safe_load(PATHS.site_package(site_id).read_text(encoding="utf-8"))


def footer_of(site_id: str) -> str:
    site = render.render_site(package(site_id), catalog=fx.build_catalog())
    body = site.pages["/"].body
    match = re.search(r"<footer.*?</footer>", body, re.S)
    assert match, "подвала нет вовсе"
    return match.group(0)


@pytest.mark.parametrize("site_id", SITES)
def test_the_footer_carries_a_working_contact(site_id):
    footer = footer_of(site_id)
    assert CONTACT in footer, "контактного адреса нет"
    assert f"mailto:{CONTACT}" in footer, "адрес не кликабелен"


@pytest.mark.parametrize("site_id", SITES)
def test_the_footer_names_the_current_year(site_id):
    assert str(dt.date.today().year) in footer_of(site_id)


@pytest.mark.parametrize("site_id", SITES)
def test_the_footer_describes_this_particular_site(site_id):
    footer = footer_of(site_id)
    text = re.sub(r"<[^>]+>", " ", footer)
    # Описание, а не одна строка про источник данных.
    assert len(text.split()) >= 30, "подвал слишком беден, чтобы быть полезным"


def test_the_three_footers_are_not_identical():
    texts = []
    for site_id in SITES:
        text = re.sub(r"<[^>]+>", " ", footer_of(site_id))
        text = re.sub(r"\s+", " ", text).strip()
        texts.append(text)
    assert len(set(texts)) == 3, "три сайта получили один и тот же подвал"


@pytest.mark.parametrize("site_id", SITES)
def test_no_internal_vocabulary_leaks_into_the_footer(site_id):
    footer = footer_of(site_id).lower()
    for word in ("стенд", "фабрик", "синтетическ", "тестовый каталог",
                 "lords-0", "lords new", "профиль сборки"):
        assert word not in footer, f"внутреннее слово «{word}» в подвале публичного сайта"


@pytest.mark.parametrize("site_id", SITES)
def test_the_footer_does_not_invent_legal_details(site_id):
    """Правообладатель и документы неизвестны и выдуманы быть не могут."""
    footer = footer_of(site_id).lower()
    for word in ("ооо ", "инн ", "огрн ", "правообладатель:", "лицензия №"):
        assert word not in footer, f"выдуманные реквизиты: {word}"


@pytest.mark.parametrize("site_id", SITES)
def test_every_footer_link_points_somewhere_real(site_id):
    site = render.render_site(package(site_id), catalog=fx.build_catalog())
    footer = footer_of(site_id)
    hrefs = re.findall(r'href="([^"]+)"', footer)
    internal = [h for h in hrefs if h.startswith("/")]
    assert internal, "в подвале нет внутренних ссылок"
    known = set(site.pages)
    for href in internal:
        path = href.split("?", 1)[0]
        assert path in known or f"{path.rstrip('/')}/" in known or path.rstrip("/") in known, \
            f"ссылка подвала ведёт в никуда: {href}"
