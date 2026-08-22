"""Mutation-тесты защищённого ядра: попытки ослабить правила должны блокироваться."""
import pytest

from seo_operator import config
from seo_operator.guardrails import (AuthorizationBlocked, GuardrailViolation, MutationRequest,
                                     authorize_mutation, check_editorial_reply,
                                     check_no_fake_engagement, check_rights, check_search_spam,
                                     check_tenant_isolation, protected_fingerprint, verify_integrity)


def _req(**overrides):
    base = dict(
        site_id="demo-fixture", action="title_description_update", tier=1,
        experiment_id="EXP-1", before_snapshot={"title": "old"},
        rollback_payload={"executable": True, "kind": "cms_restore", "site_id": "demo-fixture"},
        payload={}, is_defect_fix=False)
    base.update(overrides)
    return MutationRequest(**base)


# --- GR-002: никакой имитации активности --------------------------------------

@pytest.mark.parametrize("payload", [
    {"action": "comment_create_as_user"},
    {"action": "rating_write"},
    {"action": "vote_write"},
    {"action": "review_create"},
    {"author_type": "user", "generated_by": "operator"},
    {"schema_type": "Review", "is_genuine_review": False},
    {"ratings": [5, 5, 5], "ratings_source": "generated"},
])
def test_fake_engagement_is_blocked(payload, isolated_state):
    with pytest.raises(GuardrailViolation) as exc:
        check_no_fake_engagement(payload)
    assert exc.value.rule_id == "GR-002"


def test_real_ratings_are_allowed(isolated_state):
    check_no_fake_engagement({"ratings": [5, 4], "ratings_source": "real_published"})


# --- GR-001: права ------------------------------------------------------------

def test_publish_without_rights_blocked(isolated_state):
    with pytest.raises(GuardrailViolation) as exc:
        check_rights({"publishes_content": True})
    assert exc.value.rule_id == "GR-001"


def test_publish_with_low_confidence_blocked(isolated_state):
    with pytest.raises(GuardrailViolation):
        check_rights({"publishes_content": True, "rights_ref": "rights://x",
                      "source_confidence": "medium"})


def test_publish_with_confirmed_rights_ok(isolated_state):
    check_rights({"publishes_content": True, "rights_ref": "rights://x",
                  "source_confidence": "high"})


# --- GR-005: изоляция tenant --------------------------------------------------

def test_cross_tenant_write_blocked(isolated_state):
    with pytest.raises(GuardrailViolation) as exc:
        check_tenant_isolation("demo-fixture", {"target_sites": ["demo-fixture", "other-site"]})
    assert exc.value.rule_id == "GR-005"


def test_cross_tenant_canonical_blocked(isolated_state):
    with pytest.raises(GuardrailViolation):
        check_tenant_isolation("demo-fixture", {"canonical_url": "https://other.example/x"})


# --- GR-009: поисковый спам ---------------------------------------------------

@pytest.mark.parametrize("payload", [
    {"generated_page_count": 500},
    {"technique": "keyword_stuffing"},
    {"technique": "doorway"},
    {"technique": "synonym_spinning"},
    {"technique": "hidden_text"},
])
def test_search_spam_blocked(payload, isolated_state):
    with pytest.raises(GuardrailViolation) as exc:
        check_search_spam(payload)
    assert exc.value.rule_id == "GR-009"


def test_keyword_density_blocked(isolated_state):
    stuffed = ("смотреть аниме онлайн " * 30)
    with pytest.raises(GuardrailViolation):
        check_search_spam({"text": stuffed})


def test_normal_text_passes(isolated_state):
    text = ("Второй сезон продолжает историю экипажа после событий финала первого сезона. "
            "Дата премьеры подтверждена студией; эпизоды выходят еженедельно по средам. "
            "На странице собраны список серий, информация об озвучке и порядок просмотра.")
    check_search_spam({"text": text})


# --- GR-006: rollback ---------------------------------------------------------

def test_mutation_without_rollback_blocked(isolated_state):
    with pytest.raises(GuardrailViolation) as exc:
        authorize_mutation(_req(rollback_payload=None))
    assert exc.value.rule_id == "GR-006"


def test_mutation_without_snapshot_blocked(isolated_state):
    with pytest.raises(GuardrailViolation) as exc:
        authorize_mutation(_req(before_snapshot=None))
    assert exc.value.rule_id == "GR-006"


def test_non_executable_rollback_blocked(isolated_state):
    with pytest.raises(GuardrailViolation):
        authorize_mutation(_req(rollback_payload={"executable": False}))


# --- GR-007: эксперимент ------------------------------------------------------

def test_change_without_experiment_blocked(isolated_state):
    with pytest.raises(GuardrailViolation) as exc:
        authorize_mutation(_req(experiment_id=None))
    assert exc.value.rule_id == "GR-007"


def test_defect_fix_allowed_without_experiment(isolated_state):
    authorize_mutation(_req(experiment_id=None, is_defect_fix=True))


# --- GR-004: авторизация ------------------------------------------------------

def test_unknown_site_blocked(isolated_state):
    with pytest.raises((AuthorizationBlocked, KeyError)):
        authorize_mutation(_req(site_id="no-such-site"))


def test_action_outside_manifest_blocked(isolated_state):
    with pytest.raises(AuthorizationBlocked) as exc:
        authorize_mutation(_req(action="canonical_change", tier=2))
    assert "не в allowed_actions" in str(exc.value) or "выше autonomy_tier" in str(exc.value)


def test_tier3_always_requires_owner(isolated_state):
    with pytest.raises(AuthorizationBlocked) as exc:
        authorize_mutation(_req(action="dns_change", tier=3))
    assert "Tier 3" in str(exc.value) or "не в allowed_actions" in str(exc.value)


def test_allowed_action_passes(isolated_state):
    manifest = authorize_mutation(_req())
    assert manifest["site_id"] == "demo-fixture"


def test_unknown_action_fails_closed(isolated_state):
    from seo_operator.guardrails import _action_tier
    with pytest.raises(GuardrailViolation):
        _action_tier("teleport_the_site")


# --- редакционный ответ -------------------------------------------------------

def test_editorial_reply_blocked_when_disabled(isolated_state):
    with pytest.raises(AuthorizationBlocked):
        check_editorial_reply({}, {"action": "editorial_reply", "author_label": "Редакция сайта"})


def test_editorial_reply_requires_disclosed_author(isolated_state):
    with pytest.raises(GuardrailViolation) as exc:
        check_editorial_reply({"disclosed_editorial_reply_enabled": True},
                              {"action": "editorial_reply", "author_label": "Аня"})
    assert exc.value.rule_id == "GR-002"


def test_editorial_reply_cannot_fake_viewing(isolated_state):
    with pytest.raises(GuardrailViolation):
        check_editorial_reply({"disclosed_editorial_reply_enabled": True},
                              {"action": "editorial_reply", "author_label": "Редакция сайта",
                               "claims_personal_viewing_experience": True})


# --- GR-012: целостность ядра -------------------------------------------------

def test_protected_fingerprint_detects_change(isolated_state, tmp_path):
    baseline = protected_fingerprint()
    assert baseline, "Fingerprint не должен быть пустым"
    tampered = dict(baseline)
    key = next(iter(tampered))
    tampered[key] = "0" * 64
    assert key in verify_integrity(tampered)


def test_no_drift_when_unchanged(isolated_state):
    baseline = protected_fingerprint()
    assert verify_integrity(baseline) == []


def test_protected_paths_cover_kernel(isolated_state):
    paths = config.guardrails()["protected_paths"]
    for required in (".claude/settings.json", ".claude/hooks/",
                     "seo/PROTECTED_GUARDRAILS.yaml", "inventory/authorization/"):
        assert required in paths
