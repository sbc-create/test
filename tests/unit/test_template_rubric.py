"""Проверки самой рубрики: критерий обязан уметь падать.

Рубрика стала основанием для утверждения «страница набирает 10 из 10», и это
делает её саму предметом проверки. Критерий, который не падает ни на чём, даёт
не оценку, а согласие: он всегда возвращает PASS и создаёт видимость контроля.

Два таких случая уже случились и стоят здесь тестами:

* критерий оценок искал атрибут `data-rating`, которого рендерер не выдаёт
  вовсе, — и потому не отличал оценку без источника от отсутствия оценок;
* критерий плеера засчитывал одну лишь фразу «недоступно» и не замечал утечки
  служебного кода в разметку.

Поэтому у каждого критерия здесь по паре: документ, на котором он проходит, и
документ, на котором он обязан упасть.
"""

from __future__ import annotations

import pytest

from factory.templates import rubric
from factory.templates.rubric import (
    FAIL,
    NOT_APPLICABLE,
    PASS,
    Expectation,
    score_page,
)

#: Минимальный документ, проходящий всё, что не относится к предмету теста.
BASE = """<!doctype html><html lang="ru"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Заголовок</title>
<meta name="description" content="{description}">
<meta name="robots" content="{robots}">
<meta name="lords-canonical-state" content="self">
<meta name="lords-data-source" content="fixture/test">
<script type="application/ld+json">{{}}</script>
<link rel="stylesheet" href="/assets/site.css"></head>
<body><a class="visually-hidden" href="#content">К содержимому</a>
<header class="site-header"><button class="nav-toggle" aria-expanded="false"
aria-controls="site-nav">Меню</button><nav id="site-nav" aria-label="Навигация">
<ul><li><a href="/">Главная</a></li></ul></nav></header>
<main id="content"><h1>Заголовок страницы</h1>{body}</main>
<footer class="site-footer"><p>подвал</p></footer></body></html>"""

DESCRIPTION = "Описание раздела длиной более сорока символов для критерия документа."


def document(body: str = "", *, robots: str = "noindex, nofollow",
            description: str = DESCRIPTION) -> str:
    return BASE.format(body=body, robots=robots, description=description)


CARD = ('<article class="card" data-slug="s"><a class="card__poster" href="/t/">'
        '<img src="/p.svg" alt="" loading="lazy" width="400" height="600"></a>'
        '<div class="card__body"><a class="card__title" href="/t/">Название</a>'
        '</div></article>')


def check(html: str, criterion: str, expectation: Expectation):
    page = score_page(html, expectation)
    found = next(c for c in page.checks if c.criterion == criterion)
    return found


PLAIN = Expectation("plain", "index.html", cards=False)


class TestValidity:
    def test_unique_identifiers_pass(self):
        assert check(document('<div id="a"></div>'), "validity", PLAIN).status == PASS

    def test_repeated_identifier_fails(self):
        html = document('<div id="grid"></div><div id="grid"></div>')
        found = check(html, "validity", PLAIN)
        assert found.status == FAIL and "grid" in found.detail


class TestDocument:
    def test_two_h1_fail(self):
        found = check(document("<h1>Второй</h1>"), "document", PLAIN)
        assert found.status == FAIL and "h1" in found.detail

    def test_indexable_page_without_description_fails(self):
        html = document(robots="index, follow", description="")
        found = check(html, "document", PLAIN)
        assert found.status == FAIL and "description" in found.detail

    def test_navigation_page_without_description_passes(self):
        """У раздела с `noindex` собственного текста нет намеренно."""
        html = document(robots="noindex, nofollow", description="")
        assert check(html, "document", PLAIN).status == PASS


class TestAccessibility:
    def test_control_without_a_name_fails(self):
        html = document('<select id="f-genre"><option>а</option></select>')
        found = check(html, "accessibility", PLAIN)
        assert found.status == FAIL and "подписи" in found.detail

    def test_control_with_aria_label_passes(self):
        html = document('<select id="f" aria-label="Жанр"><option>а</option></select>')
        assert check(html, "accessibility", PLAIN).status == PASS


class TestRatings:
    def test_rating_without_a_source_fails(self):
        """Ровно тот случай, который прежняя версия критерия пропускала."""
        html = document('<span class="card__rating-value">8.1</span>')
        found = check(html, "ratings", PLAIN)
        assert found.status == FAIL and "источник" in found.detail

    def test_rating_with_a_source_passes(self):
        html = document('<span class="card__rating-source">IMDb</span>'
                        '<span class="card__rating-value">8.1</span>')
        assert check(html, "ratings", PLAIN).status == PASS

    def test_absence_of_ratings_is_not_a_defect(self):
        assert check(document(), "ratings", PLAIN).status == PASS


class TestPlayerShell:
    PLAYER = Expectation("title", "t.html", player=True, cards=False)

    def test_reserved_frame_with_explanation_passes(self):
        html = document('<div class="player__frame"><p>временно недоступно</p></div>')
        assert check(html, "player_shell", self.PLAYER).status == PASS

    def test_leaked_service_code_fails(self):
        """Утечка кода — дефект, а не признак диагностируемости (D128)."""
        html = document('<div class="player__frame" '
                        'data-player-status="BLOCKED_INPUT_CDNVIDEOHUB_CREDENTIALS">'
                        "<p>временно недоступно</p></div>")
        found = check(html, "player_shell", self.PLAYER)
        assert found.status == FAIL and "утёк" in found.detail

    def test_page_without_a_player_is_not_penalised(self):
        assert check(document(), "player_shell", PLAIN).status == NOT_APPLICABLE


class TestUpdates:
    def test_listing_page_counts_its_own_cards(self):
        expectation = Expectation("new", "new.html", updates=True, updates_via="listing")
        assert check(document(CARD), "updates", expectation).status == PASS

    def test_empty_listing_fails(self):
        expectation = Expectation("new", "new.html", updates=True, updates_via="listing")
        assert check(document(), "updates", expectation).status == FAIL

    def test_home_requires_a_shelf_block(self):
        expectation = Expectation("home", "index.html", updates=True)
        assert check(document(CARD), "updates", expectation).status == FAIL
        shelf = f'<section data-block="latest_grid">{CARD}</section>'
        assert check(document(shelf), "updates", expectation).status == PASS


class TestScoreArithmetic:
    def test_not_applicable_does_not_inflate_the_score(self):
        """Снятый критерий не даёт балла и не входит в знаменатель."""
        page = score_page(document(), PLAIN)
        applicable = [c for c in page.checks if c.status != NOT_APPLICABLE]
        assert len(page.applicable) == len(applicable)
        assert page.score == round(10.0 * page.passed / len(applicable), 1)

    def test_unmeasured_is_not_counted_as_success(self):
        page = score_page(document(), PLAIN)
        page.checks.append(rubric.Check("выдуманный", rubric.UNMEASURED, "не запускалась"))
        assert page.score < 10.0, "непроверенный критерий не может давать балл"

    def test_page_of_only_not_applicable_checks_does_not_apply(self):
        page = score_page(document(), PLAIN)
        page.checks = [rubric.Check(c.criterion, NOT_APPLICABLE, "нет") for c in page.checks]
        assert not page.applies
