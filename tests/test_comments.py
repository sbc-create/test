"""Комментарии: только настоящие. Модерация, вопросы, редакционные ответы."""
import pytest

from seo_operator.comments import moderation as mod
from seo_operator.comments import reply as rp
from seo_operator.guardrails import AuthorizationBlocked, GuardrailViolation


def _c(text, cid="c1", links=None):
    return mod.Comment(id=cid, site_id="demo-fixture", page_url="/title/x",
                       author_type="user", text=text, created_at="2026-08-22T10:00:00Z",
                       links=links or [])


# --- запрет генерации ---------------------------------------------------------

@pytest.mark.parametrize("payload", [
    {"author_type": "user", "generated_by": "operator"},
    {"kind": "rating", "generated_by": "operator"},
    {"kind": "vote", "generated_by": "operator"},
    {"kind": "review", "generated_by": "operator"},
])
def test_synthetic_engagement_is_forbidden(payload):
    with pytest.raises(GuardrailViolation):
        mod.forbid_synthetic(payload)


# --- модерация ----------------------------------------------------------------

@pytest.mark.parametrize("text,expected", [
    ("Отличный сезон, особенно финал!", "publish"),
    ("промокод SALE50 скидки 90%", "hold"),
    ("казино ставки заработок без вложений http://spam.invalid", "reject"),
    ("аааааааааааа", "hold"),
])
def test_moderation_actions(text, expected):
    assert mod.classify(_c(text)).action == expected


def test_user_links_get_ugc_nofollow():
    verdict = mod.classify(_c("смотри тут http://example.invalid", links=["http://example.invalid"]))
    assert verdict.link_treatment == 'rel="ugc nofollow"'


def test_link_sanitizer_rewrites_rel():
    html = '<a href="http://x.invalid">x</a> <a href="/y" rel="follow">y</a>'
    out = mod.sanitize_links(html)
    assert out.count('rel="ugc nofollow"') == 2
    assert 'rel="follow"' not in out


def test_moderation_is_appealable():
    assert mod.classify(_c("казино ставки")).appealable is True


def test_duplicate_comments_are_detected():
    pairs = mod.detect_duplicates([_c("одинаковый текст", "a"), _c("одинаковый текст!", "b")])
    assert pairs == [("a", "b")]


# --- вопросы ------------------------------------------------------------------

def test_questions_are_extracted_from_real_comments():
    qs = mod.extract_questions([_c("Когда выйдет вторая серия?", "a"),
                                _c("Классный сериал", "b")])
    assert len(qs) == 1


def test_only_recurring_questions_reach_faq():
    comments = [_c("Когда выйдет вторая серия сезона?", f"c{i}") for i in range(4)]
    comments.append(_c("Есть ли русская озвучка?", "c9"))
    recurring = mod.recurring_questions(mod.extract_questions(comments), min_count=3)
    assert len(recurring) == 1
    assert recurring[0]["count"] == 4
    assert "FAQ" in recurring[0]["proposed_action"]


def test_single_question_does_not_become_faq():
    recurring = mod.recurring_questions(mod.extract_questions([_c("Когда выйдет?", "a")]), min_count=3)
    assert recurring == []


# --- качество и накрутка ------------------------------------------------------

def test_quality_score_orders_existing_comments():
    good = mod.quality_score(_c("Финал объясняет мотивацию капитана через сцену на мостике: "
                                "он повторяет реплику из первой серии, замыкая арку персонажа."))
    poor = mod.quality_score(_c("+"))
    assert good > poor


def test_rating_burst_is_flagged():
    ratings = [{"date": "2026-08-20", "value": 5} for _ in range(60)]
    ratings += [{"date": f"2026-08-{d}", "value": 4} for d in range(10, 19)]
    alerts = mod.detect_rating_manipulation(ratings)
    assert any("Всплеск" in a for a in alerts)


def test_uniform_ratings_flagged():
    alerts = mod.detect_rating_manipulation([{"date": f"2026-08-{d:02d}", "value": 10}
                                             for d in range(1, 26)])
    assert any("одно значение" in a for a in alerts)


def test_natural_ratings_not_flagged():
    ratings = [{"date": f"2026-08-{d:02d}", "value": v}
               for d in range(1, 21) for v in (3, 4, 5)]
    assert mod.detect_rating_manipulation(ratings) == []


# --- редакционные ответы ------------------------------------------------------

MANIFEST_ON = {"disclosed_editorial_reply_enabled": True}


def test_reply_blocked_when_feature_disabled():
    r = rp.build_reply("c1", "demo-fixture", "Ответ", sources=["src"])
    with pytest.raises(AuthorizationBlocked):
        rp.check_reply(r, {}, answers_real_comment=True, states_facts=True)


def test_reply_author_must_be_disclosed():
    with pytest.raises(GuardrailViolation):
        rp.build_reply("c1", "demo-fixture", "Ответ", sources=[], author_label="Маша")


def test_reply_cannot_fake_personal_viewing():
    r = rp.build_reply("c1", "demo-fixture", "Я смотрел этот сезон, мне понравился финал", [])
    check = rp.check_reply(r, MANIFEST_ON, answers_real_comment=True, states_facts=False)
    assert not check.ok and any("личный опыт" in v for v in check.violations)


def test_reply_cannot_promise_unbacked_action():
    r = rp.build_reply("c1", "demo-fixture", "Мы добавим озвучку на следующей неделе", [])
    check = rp.check_reply(r, MANIFEST_ON, answers_real_comment=True, states_facts=False)
    assert not check.ok


def test_reply_cannot_carry_hidden_ad():
    r = rp.build_reply("c1", "demo-fixture", "Подпишись на наш канал, промокод внутри", [])
    check = rp.check_reply(r, MANIFEST_ON, answers_real_comment=True, states_facts=False)
    assert not check.ok


def test_factual_reply_requires_source():
    r = rp.build_reply("c1", "demo-fixture", "Сезон состоит из 12 серий.", sources=[])
    check = rp.check_reply(r, MANIFEST_ON, answers_real_comment=True, states_facts=True)
    assert not check.ok


def test_valid_disclosed_reply_passes():
    r = rp.build_reply("c1", "demo-fixture", "Сезон состоит из 12 серий.",
                       sources=["cdnvideohub://stellar-drift/s2"])
    check = rp.check_reply(r, MANIFEST_ON, answers_real_comment=True, states_facts=True)
    assert check.ok
    assert r.entity_type == "editorial_reply"
    assert r.author_label in rp.ALLOWED_AUTHORS


def test_reply_must_answer_a_real_comment():
    r = rp.build_reply("c1", "demo-fixture", "Просто текст", sources=["s"])
    check = rp.check_reply(r, MANIFEST_ON, answers_real_comment=False, states_facts=False)
    assert not check.ok
