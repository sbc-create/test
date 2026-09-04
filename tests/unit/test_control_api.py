"""REQ-CONTROL: записывающая часть Control API v1 безопасна по умолчанию.

Проверяется не «работает ли запись», а каждая ступень конвейера по отдельности:
выключенность, аутентификация, право, лимит, валидация, идемпотентность,
сверка версии, аудит. Ступень, которую никто не проверяет, однажды окажется
пропущенной, и узнают об этом по последствиям.
"""
import json

import pytest

from factory import audit, queue
from factory.paths import PATHS
from factory.site_engine.api import ratelimit
from factory.site_engine.api.control import ControlApi

ADMIN = "admin-token"
READER = "reader-token"
ENV = {
    "SITE_ENGINE_CONTROL_WRITES": "1",
    "SITE_ENGINE_CONTROL_TOKENS": (
        f"{ADMIN}=read,jobs:write,config:write,cache:write,audit:read"
        f"|{READER}=read"
    ),
}
AUTH = {"Authorization": f"Bearer {ADMIN}"}
SITE = "test-site-a"


@pytest.fixture
def sandbox(tmp_path, monkeypatch):
    """Полная изоляция: очередь, блокировки и аудит уходят во временный корень.

    Без этого тест правил бы настоящие профили сайтов — то есть проверял бы
    безопасность способом, который сам небезопасен.
    """
    monkeypatch.setattr(PATHS, "root", tmp_path)
    profiles = tmp_path / "config" / "site-profiles"
    profiles.mkdir(parents=True)
    (profiles / f"{SITE}.json").write_text(
        json.dumps(
            {
                "site_id": SITE,
                "site_type": "anime",
                "domains": ["example.test"],
                "canonical_host": "example.test",
                "keep_releases": 5,
                "indexing_enabled": True,
                "cache_policy": {"homepage_ttl": 60},
                "feature_flags": {"beta_player": False},
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    for sub in ("queue/inbox", "queue/processing", "queue/done", "queue/failed",
                "queue/quarantine", "var/locks", "var/audit", "var/state"):
        (tmp_path / sub).mkdir(parents=True, exist_ok=True)
    return tmp_path


def api(sandbox, env=None):
    return ControlApi(root=sandbox, env=env if env is not None else ENV)


def profile_of(sandbox):
    return json.loads((sandbox / "config" / "site-profiles" / f"{SITE}.json").read_text(encoding="utf-8"))


# ---- ступень 1: включённость ------------------------------------------------

def test_writes_are_disabled_by_default(sandbox):
    """Без явного включения записывающий маршрут не существует."""
    a = api(sandbox, env={"SITE_ENGINE_CONTROL_TOKENS": ENV["SITE_ENGINE_CONTROL_TOKENS"]})
    r = a.handle("POST", f"/api/v1/sites/{SITE}/jobs", body={"action": "reindex"}, headers=AUTH)
    assert r.status == 404, "выключенная запись должна быть неотличима от отсутствующего маршрута"


def test_disabled_writes_do_not_leak_existence(sandbox):
    """Ответ не должен подсказывать, что здесь есть что включать."""
    a = api(sandbox, env={"SITE_ENGINE_CONTROL_TOKENS": ENV["SITE_ENGINE_CONTROL_TOKENS"]})
    r = a.handle("PATCH", f"/api/v1/sites/{SITE}/settings", body={"changes": {"keep_releases": 4}}, headers=AUTH)
    assert r.status == 404
    assert "disabled" not in json.dumps(r.body).lower()


def test_reads_stay_available_when_writes_disabled(sandbox):
    """Выключатель записи не должен глушить чтение."""
    a = api(sandbox, env={"SITE_ENGINE_CONTROL_TOKENS": ENV["SITE_ENGINE_CONTROL_TOKENS"]})
    r = a.handle("GET", "/api/v1/jobs/nonexistent-job", headers=AUTH)
    assert r.status == 404
    assert r.body["error"]["code"] == "job_not_found", "чтение должно отвечать по существу"


# ---- ступень 2-3: аутентификация и права ------------------------------------

def test_missing_token_is_rejected(sandbox):
    r = api(sandbox).handle("POST", f"/api/v1/sites/{SITE}/jobs", body={"action": "reindex"})
    assert r.status == 401


def test_unknown_token_is_rejected(sandbox):
    r = api(sandbox).handle("POST", f"/api/v1/sites/{SITE}/jobs", body={"action": "reindex"},
                            headers={"Authorization": "Bearer nope"})
    assert r.status == 401


def test_scope_is_enforced_per_operation(sandbox):
    """Право на чтение не даёт права на запись."""
    r = api(sandbox).handle("POST", f"/api/v1/sites/{SITE}/jobs", body={"action": "reindex"},
                            headers={"Authorization": f"Bearer {READER}"})
    assert r.status == 403
    assert r.body["error"]["required_scope"] == "jobs:write"


def test_job_scope_does_not_grant_config_scope(sandbox):
    """Отдельные области должны быть действительно отдельными."""
    env = dict(ENV, SITE_ENGINE_CONTROL_TOKENS="partial=read,jobs:write")
    r = api(sandbox, env=env).handle("PATCH", f"/api/v1/sites/{SITE}/settings",
                                     body={"changes": {"keep_releases": 4}},
                                     headers={"Authorization": "Bearer partial"})
    assert r.status == 403
    assert r.body["error"]["required_scope"] == "config:write"


# ---- ступень 4: лимит частоты -----------------------------------------------

def test_rate_limit_stops_runaway_automation(sandbox):
    """Предел общий для процессов и иерархический: срабатывает самый узкий."""
    a = api(sandbox)
    statuses = [a.handle("GET", "/api/v1/jobs/x", headers=AUTH).status for _ in range(80)]
    assert 429 in statuses, "сорвавшийся цикл должен упереться в предел"
    первый = statuses.index(429)
    самый_узкий = min(п.capacity for п in ratelimit.DEFAULT_LIMITS.values())
    assert первый >= самый_узкий - 1, f"предел сработал слишком рано: на {первый}"


def test_rate_limit_names_which_limit_was_hit(sandbox):
    """Без имени ключа оператор не поймёт, что именно упёрлось."""
    a = api(sandbox)
    ответ = None
    for _ in range(80):
        r = a.handle("GET", "/api/v1/jobs/x", headers=AUTH)
        if r.status == 429:
            ответ = r
            break
    assert ответ is not None
    assert ответ.body["error"]["limit_key"]
    assert ответ.body["error"]["retry_after_seconds"] >= 1


def test_noisy_site_does_not_block_its_neighbour(sandbox):
    """Ключи раздельные по витрине: иначе один сайт упирает в предел все."""
    другой = sandbox / "config" / "site-profiles" / "quiet-site.json"
    другой.write_text((sandbox / "config" / "site-profiles" / f"{SITE}.json").read_text(
        encoding="utf-8").replace(SITE, "quiet-site"), encoding="utf-8")
    a = api(sandbox)
    # Столько, чтобы исчерпать ведро витрины и операции, но не ведро
    # действующего лица: иначе проверялось бы не разделение по витринам.
    шумных = ratelimit.DEFAULT_LIMITS["site"].capacity + 2
    assert шумных < ratelimit.DEFAULT_LIMITS["actor"].capacity
    последний = None
    for _ in range(шумных):
        последний = a.handle("POST", f"/api/v1/sites/{SITE}/jobs",
                             body={"action": "reindex", "dryRun": True}, headers=AUTH)
    assert последний.status == 429, "шумная витрина должна была упереться сама"
    сосед = a.handle("POST", "/api/v1/sites/quiet-site/jobs",
                     body={"action": "reindex", "dryRun": True}, headers=AUTH)
    assert сосед.status != 429, "шумная витрина упёрла в предел соседнюю"


# ---- ступень 5: валидация ---------------------------------------------------

def test_unknown_site_is_404(sandbox):
    r = api(sandbox).handle("POST", "/api/v1/sites/no-such-site/jobs",
                            body={"action": "reindex"}, headers=AUTH)
    assert r.status == 404


def test_malformed_site_id_is_rejected_before_lookup(sandbox):
    r = api(sandbox).handle("POST", "/api/v1/sites/..%2Fetc/jobs",
                            body={"action": "reindex"}, headers=AUTH)
    assert r.status == 400
    assert r.body["error"]["code"] == "invalid_site_id"


def test_job_action_is_a_closed_list(sandbox):
    """Свободное поле action означало бы выполнение произвольного действия."""
    r = api(sandbox).handle("POST", f"/api/v1/sites/{SITE}/jobs",
                            body={"action": "rm -rf /"}, headers=AUTH)
    assert r.status == 400
    assert r.body["error"]["code"] == "invalid_action"


def test_dangerous_settings_are_refused_with_a_reason(sandbox):
    """Отказ по замыслу, а не пробел: причина должна быть в ответе."""
    r = api(sandbox).handle("PATCH", f"/api/v1/sites/{SITE}/settings",
                            body={"changes": {"indexing_enabled": False}}, headers=AUTH)
    assert r.status == 422
    problems = " ".join(r.body["error"]["problems"])
    assert "indexing_enabled" in problems and "отклонено намеренно" in problems
    assert profile_of(sandbox)["indexing_enabled"] is True, "профиль не должен измениться"


def test_canonical_host_change_is_refused(sandbox):
    r = api(sandbox).handle("PATCH", f"/api/v1/sites/{SITE}/settings",
                            body={"changes": {"canonical_host": "evil.test"}}, headers=AUTH)
    assert r.status == 422
    assert profile_of(sandbox)["canonical_host"] == "example.test"


def test_range_is_checked_not_only_type(sandbox):
    """keep_releases=0 — корректное число, после которого откатываться некуда."""
    r = api(sandbox).handle("PATCH", f"/api/v1/sites/{SITE}/settings",
                            body={"changes": {"keep_releases": 0}}, headers=AUTH)
    assert r.status == 422
    assert profile_of(sandbox)["keep_releases"] == 5


def test_bool_is_not_accepted_as_int(sandbox):
    """В Python True == 1; без явной проверки это прошло бы как число."""
    r = api(sandbox).handle("PATCH", f"/api/v1/sites/{SITE}/settings",
                            body={"changes": {"keep_releases": True}}, headers=AUTH)
    assert r.status == 422


def test_all_problems_are_reported_at_once(sandbox):
    """Отказ по одному полю за запрос превращает правку в переписку."""
    r = api(sandbox).handle("PATCH", f"/api/v1/sites/{SITE}/settings",
                            body={"changes": {"keep_releases": 0, "domains": ["x"],
                                              "unknown_key": 1}}, headers=AUTH)
    assert r.status == 422
    assert len(r.body["error"]["problems"]) == 3


# ---- ступень 6: dry-run -----------------------------------------------------

def test_dry_run_reports_diff_without_changing_anything(sandbox):
    before = profile_of(sandbox)
    r = api(sandbox).handle("PATCH", f"/api/v1/sites/{SITE}/settings",
                            body={"changes": {"keep_releases": 9}, "dryRun": True}, headers=AUTH)
    assert r.status == 200 and r.body["dryRun"] is True
    assert r.body["diff"]["keep_releases"] == {"before": 5, "after": 9}
    assert profile_of(sandbox) == before, "dry-run не должен ничего менять"


def test_dry_run_job_does_not_enqueue(sandbox):
    r = api(sandbox).handle("POST", f"/api/v1/sites/{SITE}/jobs",
                            body={"action": "reindex", "dryRun": True}, headers=AUTH)
    assert r.status == 200 and r.body["dryRun"] is True
    assert queue.counts()["inbox"] == 0


# ---- ступень 7: идемпотентность ---------------------------------------------

def test_same_key_replays_instead_of_repeating(sandbox):
    a = api(sandbox)
    body = {"action": "reindex"}
    h = {**AUTH, "Idempotency-Key": "key-1"}
    first = a.handle("POST", f"/api/v1/sites/{SITE}/jobs", body=body, headers=h)
    second = a.handle("POST", f"/api/v1/sites/{SITE}/jobs", body=body, headers=h)
    assert first.status == 202
    assert second.body.get("idempotentReplay") is True
    assert queue.counts()["inbox"] == 1, "повтор не должен ставить второе задание"


def test_same_key_with_different_body_is_a_conflict(sandbox):
    """Молча выполнить другой запрос под использованным ключом — выполнить дважды."""
    a = api(sandbox)
    h = {**AUTH, "Idempotency-Key": "key-2"}
    a.handle("POST", f"/api/v1/sites/{SITE}/jobs", body={"action": "reindex"}, headers=h)
    r = a.handle("POST", f"/api/v1/sites/{SITE}/jobs", body={"action": "enrich"}, headers=h)
    assert r.status == 409
    assert r.body["error"]["code"] == "idempotency_key_reused"


# ---- ступень 8: сверка версии -----------------------------------------------

def test_stale_version_is_rejected(sandbox):
    """Конкурентная правка не должна теряться молча."""
    r = api(sandbox).handle("PATCH", f"/api/v1/sites/{SITE}/settings",
                            body={"changes": {"keep_releases": 7},
                                  "expectedVersion": "sha256:obsolete"}, headers=AUTH)
    assert r.status == 409
    assert r.body["error"]["code"] == "version_conflict"
    assert profile_of(sandbox)["keep_releases"] == 5


def test_current_version_is_accepted_and_changes_after_write(sandbox):
    a = api(sandbox)
    peek = a.handle("PATCH", f"/api/v1/sites/{SITE}/settings",
                    body={"changes": {"keep_releases": 7}, "dryRun": True}, headers=AUTH)
    version = peek.body["currentVersion"]
    r = a.handle("PATCH", f"/api/v1/sites/{SITE}/settings",
                 body={"changes": {"keep_releases": 7}, "expectedVersion": version}, headers=AUTH)
    assert r.status == 200 and r.body["applied"] is True
    assert profile_of(sandbox)["keep_releases"] == 7
    assert r.body["version"] != version, "версия обязана измениться после записи"


def test_nested_settings_merge_rather_than_replace(sandbox):
    """Замена словаря целиком тихо стёрла бы соседние ключи."""
    r = api(sandbox).handle("PATCH", f"/api/v1/sites/{SITE}/settings",
                            body={"changes": {"cache_policy": {"title_ttl": 120}}}, headers=AUTH)
    assert r.status == 200
    policy = profile_of(sandbox)["cache_policy"]
    assert policy == {"homepage_ttl": 60, "title_ttl": 120}


def test_no_op_change_is_reported_as_such(sandbox):
    r = api(sandbox).handle("PATCH", f"/api/v1/sites/{SITE}/settings",
                            body={"changes": {"keep_releases": 5}}, headers=AUTH)
    assert r.status == 200 and r.body["noop"] is True and r.body["applied"] is False


# ---- инвалидация кэша -------------------------------------------------------

def test_targeted_invalidation_requires_keys(sandbox):
    """Пустой список при точечной области — «сбрось всё» под видом точечного."""
    r = api(sandbox).handle("POST", f"/api/v1/sites/{SITE}/cache/invalidate",
                            body={"scope": "title", "keys": []}, headers=AUTH)
    assert r.status == 400
    assert r.body["error"]["code"] == "keys_required"


def test_invalidation_is_queued_not_executed_directly(sandbox):
    """Управляющий слой не ходит в хранилище витрины сам."""
    r = api(sandbox).handle("POST", f"/api/v1/sites/{SITE}/cache/invalidate",
                            body={"scope": "title", "keys": ["t-1"]}, headers=AUTH)
    assert r.status == 202
    assert queue.counts()["inbox"] == 1
    assert r.body["job"]["action"] == "invalidate"


# ---- задания ----------------------------------------------------------------

def test_job_status_reflects_queue_stage(sandbox):
    a = api(sandbox)
    started = a.handle("POST", f"/api/v1/sites/{SITE}/jobs",
                       body={"action": "reindex"}, headers=AUTH)
    job_id = started.body["job"]["job_id"]
    r = a.handle("GET", f"/api/v1/jobs/{job_id}", headers=AUTH)
    assert r.status == 200
    assert r.body["stage"] == "inbox" and r.body["terminal"] is False


# ---- аудит и прослеживаемость -----------------------------------------------

def test_mutation_is_recorded_with_diff(sandbox):
    before = len(audit.read_all())
    api(sandbox).handle("PATCH", f"/api/v1/sites/{SITE}/settings",
                        body={"changes": {"keep_releases": 8}}, headers=AUTH)
    entries = audit.read_all()
    assert len(entries) == before + 1
    entry = entries[-1]
    assert entry["mutation"] is True
    assert entry["extra"]["diff"]["keep_releases"] == {"before": 5, "after": 8}


def test_refusal_is_recorded_too(sandbox):
    """Журнал только удачных операций не отвечает на вопрос «кто пытался»."""
    before = len(audit.read_all())
    api(sandbox).handle("PATCH", f"/api/v1/sites/{SITE}/settings",
                        body={"changes": {"indexing_enabled": False}}, headers=AUTH)
    entries = audit.read_all()
    assert len(entries) == before + 1
    assert entries[-1]["action"] == "control.denied.invalid_settings"
    assert entries[-1]["mutation"] is False


def test_raw_token_never_reaches_the_audit_log(sandbox):
    api(sandbox).handle("PATCH", f"/api/v1/sites/{SITE}/settings",
                        body={"changes": {"keep_releases": 6}}, headers=AUTH)
    assert ADMIN not in json.dumps(audit.read_all(), ensure_ascii=False)


def test_correlation_id_is_returned_even_on_failure(sandbox):
    """Без идентификатора вызывающий не найдёт свой запрос в журнале."""
    ok = api(sandbox).handle("POST", f"/api/v1/sites/{SITE}/jobs",
                             body={"action": "reindex"}, headers=AUTH)
    bad = api(sandbox).handle("POST", f"/api/v1/sites/{SITE}/jobs",
                              body={"action": "bogus"}, headers=AUTH)
    assert ok.body["correlationId"].startswith("cid-")
    assert bad.body["correlationId"].startswith("cid-")


def test_supplied_correlation_id_is_preserved(sandbox):
    r = api(sandbox).handle("POST", f"/api/v1/sites/{SITE}/jobs", body={"action": "reindex"},
                            headers={**AUTH, "X-Correlation-Id": "trace-42"})
    assert r.body["correlationId"] == "trace-42"


def test_audit_trail_is_readable_and_filterable(sandbox):
    a = api(sandbox)
    a.handle("PATCH", f"/api/v1/sites/{SITE}/settings",
             body={"changes": {"keep_releases": 6}}, headers=AUTH)
    r = a.handle("GET", "/api/v1/audit", body={"limit": 10, "siteId": SITE}, headers=AUTH)
    assert r.status == 200
    assert all(e["site_id"] == SITE for e in r.body["entries"])
