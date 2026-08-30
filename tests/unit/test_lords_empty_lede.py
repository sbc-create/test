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


def test_no_page_of_any_site_emits_an_empty_lede():
    offenders = []
    for site_id in SITES:
        site = render.render_site(package(site_id), catalog=fx.build_catalog())
        for path, page in site.pages.items():
            if EMPTY_LEDE.search(page.body):
                offenders.append(f"{site_id}{path}")
    assert not offenders, f"пустой вступительный абзац на страницах: {offenders}"
