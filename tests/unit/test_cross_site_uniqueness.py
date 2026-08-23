"""REQ-CSU: ворота cross_site_uniqueness.

Проверяется и то, что дубль ловится, и то, что три честно разных сайта проходят:
ворота, которые блокируют всё подряд, отключат при первом же релизе.
"""
from __future__ import annotations

import pytest

from factory.seo import uniqueness


def page(site, path, **kwargs):
    defaults = {
        "page_type": "title",
        "indexable": True,
        "title": f"{site} {path}",
        "description": f"Описание {site} {path}",
        "h1": f"{site} {path}",
        "own_text": f"Собственный текст сайта {site} про страницу {path}. " * 12,
        "canonical": f"https://{site}{path}",
    }
    defaults.update(kwargs)
    return uniqueness.PageObservation(site_id=site, path=path, **defaults)


def rules(report):
    return sorted({finding.rule for finding in report.critical})


def test_three_distinct_sites_pass():
    pages = [page("a", "/catalog/x/"), page("b", "/schedule/"), page("c", "/collections/y/")]
    report = uniqueness.check(pages)
    assert report.passed, [f.message for f in report.critical]
    assert report.counts["sites"] == 3


def test_identical_title_between_sites_is_blocked():
    pages = [page("a", "/x/", title="Один и тот же заголовок"),
             page("b", "/y/", title="Один и тот же заголовок")]
    report = uniqueness.check(pages)
    assert "CSU-1" in rules(report)
    assert not report.passed


def test_identical_description_between_sites_is_blocked():
    pages = [page("a", "/x/", description="Одно и то же описание страницы"),
             page("b", "/y/", description="Одно и то же описание страницы")]
    assert "CSU-2" in rules(uniqueness.check(pages))


def test_identical_h1_between_sites_is_blocked():
    pages = [page("a", "/x/", h1="Одинаковый заголовок первого уровня"),
             page("b", "/y/", h1="Одинаковый заголовок первого уровня")]
    assert "CSU-3" in rules(uniqueness.check(pages))


ORIGINAL_TEXT = (
    "Сериал выходит еженедельно, и к концу первого сезона сюжет успевает "
    "смениться дважды: сначала это спокойная история о переезде, потом "
    "напряжённый конфликт вокруг наследства. Второй сезон снят другой командой, "
    "поэтому темп заметно быстрее, а музыкальное сопровождение стало сдержаннее. "
    "Смотреть лучше подряд: отдельные серии теряют половину смысла без предыдущих."
)


def test_near_duplicate_text_is_blocked_even_after_light_editing():
    original = ORIGINAL_TEXT
    lightly_edited = original.replace("спокойная", "неторопливая").replace("сдержаннее", "скромнее")
    pages = [page("a", "/x/", own_text=original, title="A", description="A", h1="A"),
             page("b", "/y/", own_text=lightly_edited, title="B", description="B", h1="B")]
    report = uniqueness.check(pages)
    assert "CSU-4" in rules(report), "синонимайзер не должен считаться уникальностью"


def test_different_text_on_same_facts_passes():
    pages = [
        page("a", "/x/", title="A", description="A", h1="A",
             own_text="Каталожная карточка: состав сезонов, порядок серий, статус выхода и даты. " * 5),
        page("b", "/y/", title="B", description="B", h1="B",
             own_text="Редакционный разбор: чем цепляет, кому подойдёт, с какого момента смотреть. " * 5),
    ]
    report = uniqueness.check(pages)
    assert report.passed, [f.message for f in report.critical]


def test_indexable_page_without_own_text_is_blocked():
    pages = [page("a", "/x/", own_text="Коротко."), page("b", "/y/")]
    assert "CSU-5" in rules(uniqueness.check(pages))


def test_identical_indexable_surface_is_blocked():
    pages = [page("a", "/x/", title="A1", description="A1", h1="A1"),
             page("b", "/x/", title="B1", description="B1", h1="B1")]
    assert "CSU-6" in rules(uniqueness.check(pages))


def test_cross_domain_canonical_is_blocked():
    pages = [page("a", "/x/", canonical="https://b/x/"), page("b", "/y/")]
    assert "CSU-7" in rules(uniqueness.check(pages))


def test_noindex_pages_do_not_trigger_duplicates():
    # Неиндексируемые страницы могут совпадать: в выдачу они не попадают.
    pages = [page("a", "/x/", indexable=False, title="Одинаково", own_text="одно и то же " * 40),
             page("b", "/y/", indexable=False, title="Одинаково", own_text="одно и то же " * 40)]
    report = uniqueness.check(pages)
    assert report.passed, [f.message for f in report.critical]


def test_empty_input_is_not_a_pass():
    report = uniqueness.check([])
    assert not report.passed
    assert report.counts["status"] == "skipped"


def test_single_site_is_not_a_pass():
    report = uniqueness.check([page("a", "/x/")])
    assert not report.passed, "сравнивать не с чем — это не «уникально»"


def test_similarity_bounds():
    text = "одинаковый текст для проверки границ метрики сравнения абзацев"
    other = "совершенно другой набор слов без единого пересечения вовсе"
    assert uniqueness.similarity(text, text) == pytest.approx(1.0)
    assert uniqueness.similarity(text, other) == pytest.approx(0.0)


def test_containment_catches_text_with_appended_paragraph():
    # «Тот же текст плюс абзац сверху» — тоже дубль: Jaccard такую пару пропускает.
    extended = ORIGINAL_TEXT + " Дополнительный абзац, написанный ради формальной уникальности."
    assert uniqueness.similarity(ORIGINAL_TEXT, extended) >= uniqueness.NEAR_DUPLICATE_THRESHOLD
    assert uniqueness.jaccard(ORIGINAL_TEXT, extended) < 1.0
