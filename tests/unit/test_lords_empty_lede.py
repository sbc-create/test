"""Пустой абзац не выводится вместо отсутствующего вступления.

Вступительный текст на витрине необязателен: у части разделов его нет и не
должно быть. Но отсутствие текста — это отсутствие абзаца, а не абзац без
текста. Пустой `<p class="lede"></p>` занимает место осмысленного вступления,
поэтому ни человек, ни проверка не увидят, что раздел остался без описания.

В рендерере это уже сделано правильно в двух местах (страница списка и общий
раздел): абзац появляется только при непустом `intro`. Проверяются оставшиеся.
"""
from __future__ import annotations

import re

import yaml

from factory.lords import fixtures as fx
from factory.lords import render
from factory.paths import PATHS

SITES = ("lords-01", "lords-02", "lords-03")
EMPTY_LEDE = re.compile(r'<p class="lede">\s*</p>')


def package(site_id: str) -> dict:
    return yaml.safe_load(PATHS.site_package(site_id).read_text(encoding="utf-8"))


EMPTY_SECTION = re.compile(r'<section class="section"><h2>[^<]*</h2>\s*</section>')


def test_no_page_leaves_a_heading_without_its_content():
    """Заголовок без текста хуже пустого абзаца.

    Убрать пустой абзац и оставить `<h2>О карточке</h2>` над пустотой — значит
    заменить одну ложь другой: раздел объявлен, содержимого нет. Секция либо
    имеет текст, либо не выводится целиком.
    """
    offenders = []
    for site_id in SITES:
        site = render.render_site(package(site_id), catalog=fx.build_catalog())
        for path, page in site.pages.items():
            if EMPTY_SECTION.search(page.body):
                offenders.append(f"{site_id}{path}")
    assert not offenders, f"заголовок без содержимого на страницах: {offenders[:5]} (всего {len(offenders)})"


def test_no_page_of_any_site_emits_an_empty_lede():
    offenders = []
    for site_id in SITES:
        site = render.render_site(package(site_id), catalog=fx.build_catalog())
        for path, page in site.pages.items():
            if EMPTY_LEDE.search(page.body):
                offenders.append(f"{site_id}{path}")
    assert not offenders, f"пустой вступительный абзац на страницах: {offenders}"
