"""Очереди и квоты для 100+ сайтов (ТЗ §4) и Secret Hub (ТЗ §12)."""
import pytest

from seo_operator import queueing as q
from seo_operator import secrets as sec
from seo_operator.guardrails import AuthorizationBlocked
from seo_operator.statuses import Status


# ============================ Квоты и backoff ============================

def test_quota_is_split_across_all_sites():
    plan = q.allocate_quota("gsc", 1000, [f"s{i}" for i in range(100)])
    assert all(plan.budget_for(f"s{i}") >= 1 for i in range(100))
    assert sum(plan.per_site.values()) <= 1000 - plan.reserve


def test_reserve_is_kept_for_incidents():
    plan = q.allocate_quota("gsc", 1000, ["a", "b"], reserve_share=0.1)
    assert plan.reserve == 100
    assert sum(plan.per_site.values()) <= 900


def test_priority_weights_shift_quota_without_starving_anyone():
    plan = q.allocate_quota("gsc", 1000, ["big", "small"],
                            priority_weights={"big": 9.0, "small": 1.0})
    assert plan.budget_for("big") > plan.budget_for("small")
    assert plan.budget_for("small") >= 1, "Низкоприоритетный сайт не должен выпадать совсем"


def test_insufficient_quota_is_reported_not_hidden():
    plan = q.allocate_quota("gsc", 10, [f"s{i}" for i in range(100)], min_per_site=1)
    assert "не хватает" in plan.note
    assert sum(plan.per_site.values()) <= 10


def test_empty_portfolio_is_handled():
    plan = q.allocate_quota("gsc", 100, [])
    assert plan.per_site == {} and plan.reserve == 100


@pytest.mark.parametrize("code,kind", [
    (429, q.FailureKind.RATE_LIMIT), (500, q.FailureKind.SERVER_ERROR),
    (503, q.FailureKind.SERVER_ERROR), (401, q.FailureKind.AUTH),
    (403, q.FailureKind.FORBIDDEN), (404, q.FailureKind.NOT_FOUND),
    (408, q.FailureKind.TRANSIENT_NETWORK),
])
def test_http_codes_map_to_failure_kinds(code, kind):
    assert q.classify_http(code) is kind


@pytest.mark.parametrize("kind", [q.FailureKind.AUTH, q.FailureKind.FORBIDDEN,
                                  q.FailureKind.SCHEMA, q.FailureKind.RIGHTS,
                                  q.FailureKind.NOT_FOUND])
def test_non_retriable_failures_return_no_delay(kind):
    """Токен и права не чинятся повтором — возвращается None, а не 0."""
    assert q.backoff_seconds(1, kind, "job") is None


def test_retriable_backoff_grows():
    a = q.backoff_seconds(1, q.FailureKind.SERVER_ERROR, "job")
    b = q.backoff_seconds(4, q.FailureKind.SERVER_ERROR, "job")
    assert a is not None and b is not None and b > a


def test_backoff_is_capped():
    assert q.backoff_seconds(50, q.FailureKind.SERVER_ERROR, "job") <= 900 * 1.25


def test_backoff_jitter_is_deterministic_but_differs_per_job():
    same = q.backoff_seconds(3, q.FailureKind.SERVER_ERROR, "job-a")
    again = q.backoff_seconds(3, q.FailureKind.SERVER_ERROR, "job-a")
    other = q.backoff_seconds(3, q.FailureKind.SERVER_ERROR, "job-b")
    assert same == again, "Повторный прогон должен быть воспроизводим"
    assert same != other, "Разные джобы не должны бить в API синхронно"


def test_rate_limit_respects_retry_after():
    assert q.backoff_seconds(1, q.FailureKind.RATE_LIMIT, "job", retry_after=42) == 42.0


# ============================ Батч по портфелю ============================

def test_one_failing_site_does_not_stop_the_portfolio():
    sites = [f"s{i}" for i in range(20)]
    plan = q.allocate_quota("metrika", 1000, sites)

    def worker(site: str):
        if site == "s7":
            return False, q.FailureKind.SERVER_ERROR, "500"
        return True, None, ""

    result = q.run_batch(sites, plan, worker)
    assert len(result.succeeded) == 19
    assert result.coverage == 0.95


def test_exception_in_worker_is_contained_to_one_site():
    sites = ["a", "b", "c"]
    plan = q.allocate_quota("metrika", 100, sites)

    def worker(site: str):
        if site == "b":
            raise ValueError("неожиданный ответ API")
        return True, None, ""

    result = q.run_batch(sites, plan, worker)
    assert result.succeeded == ["a", "c"]
    assert len(result.retrying) == 1


def test_auth_failure_quarantines_immediately_with_right_status():
    plan = q.allocate_quota("metrika", 100, ["a"])
    result = q.run_batch(["a"], plan, lambda s: (False, q.FailureKind.AUTH, "401"))
    assert result.quarantined[0].status is Status.BLOCKED_SECRET
    assert result.quarantined[0].attempts == 1
    assert "повтор не имеет смысла" in result.quarantined[0].detail


def test_forbidden_maps_to_blocked_access():
    plan = q.allocate_quota("metrika", 100, ["a"])
    result = q.run_batch(["a"], plan, lambda s: (False, q.FailureKind.FORBIDDEN, "403"))
    assert result.quarantined[0].status is Status.BLOCKED_ACCESS


def test_sites_without_quota_are_reported_not_silently_dropped():
    sites = [f"s{i}" for i in range(100)]
    plan = q.allocate_quota("metrika", 10, sites, min_per_site=1)
    result = q.run_batch(sites, plan, lambda s: (True, None, ""))
    assert result.skipped_no_quota, "Пропущенные по квоте сайты обязаны быть видимы"
    assert result.total == 100


def test_coverage_reflects_reality():
    sites = [f"s{i}" for i in range(10)]
    plan = q.allocate_quota("metrika", 1000, sites)
    result = q.run_batch(sites, plan,
                         lambda s: (s != "s0", q.FailureKind.AUTH if s == "s0" else None, "401"))
    assert result.coverage == 0.9
    assert result.summary()["quarantined"] == 1


# ============================ Secret Hub ============================

def test_default_hub_refuses_instead_of_reading_env():
    hub = sec.build_hub()
    handle = hub.probe("secret://metrika/s1")
    assert not handle.available
    with pytest.raises(AuthorizationBlocked):
        hub.authorized_session("secret://metrika/s1")


def test_handle_never_contains_a_value():
    hub = sec.InMemorySecretHub({"secret://metrika/s1": "read_only"})
    handle = hub.probe("secret://metrika/s1")
    assert handle.available and handle.scope == "read_only"
    assert not hasattr(handle, "value")
    assert "read_only" in repr(handle) and "secret://metrika/s1" in repr(handle)


def test_session_repr_does_not_leak():
    hub = sec.InMemorySecretHub({"secret://metrika/s1": "read_only"})
    session = hub.authorized_session("secret://metrika/s1")
    assert "secret://metrika/s1" in repr(session)
    assert "AQAA" not in repr(session)


def test_missing_secret_blocks_with_status():
    hub = sec.InMemorySecretHub()
    with pytest.raises(AuthorizationBlocked) as exc:
        hub.authorized_session("secret://metrika/s1")
    assert exc.value.request["status"] == Status.BLOCKED_SECRET.value


@pytest.mark.parametrize("ref", ["metrika/s1", "secret://", "secret://METRIKA/s1",
                                 "secret://metrika", "http://metrika/s1"])
def test_malformed_secret_refs_rejected(ref):
    with pytest.raises(ValueError):
        sec.SecretHandle(ref=ref, available=False, scope="none", checked_at="now")


def test_ref_builders_match_pattern():
    assert sec.SECRET_REF_PATTERN.match(sec.metrika_ref("demo-fixture"))
    assert sec.SECRET_REF_PATTERN.match(sec.webmaster_ref("demo-fixture"))


# Образцы собираются из частей: литерал, похожий на настоящий секрет, не должен
# лежать в репозитории — иначе `seo secrets check` справедливо ругается на тесты.
_PEM_HEADER = "-----BEGIN " + "RSA PRIVATE KEY" + "-----"


@pytest.mark.parametrize("payload", [
    "token=" + "AQAA" + "b" * 30,
    "y0_" + "c" * 30,
    "gh" + "p_" + "d" * 30,
    _PEM_HEADER,
    "AKIA" + "A" * 16,
])
def test_leak_guard_stops_publication(payload):
    with pytest.raises(sec.SecretLeak):
        sec.assert_no_secret(f"отчёт содержит {payload}", "daily_report")


def test_leak_guard_passes_clean_text():
    sec.assert_no_secret("organic_daily_unique = 12345 [metrika, 28д]", "daily_report")


def test_leak_guard_message_does_not_echo_the_secret():
    payload = "y0_" + "e" * 30
    with pytest.raises(sec.SecretLeak) as exc:
        sec.assert_no_secret(payload, "report")
    assert payload not in str(exc.value)


def test_environment_scan_returns_names_not_values():
    env = {"YANDEX_OAUTH_TOKEN": "y0_" + "f" * 30, "PATH": "/usr/bin",
           "INNOCENT": "hello", "SOME_VAR": "AKIA" + "B" * 16}
    found = sec.scan_environment_for_secrets(env)
    assert "YANDEX_OAUTH_TOKEN" in found
    assert "SOME_VAR" in found, "Секрет опознаётся и по значению, не только по имени"
    assert "PATH" not in found and "INNOCENT" not in found
    assert all("y0_" not in name for name in found)
