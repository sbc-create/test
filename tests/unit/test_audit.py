"""REQ-AUDIT: журнал мутаций полон и без секретов."""
import json

from factory import audit


def test_record_contains_required_fields(monkeypatch, tmp_path):
    monkeypatch.setenv("FACTORY_ACTOR", "tester")
    entry = audit.record(job_id="j1", site_id="s1", environment="staging", action="deploy",
                         target="stage-1", exit_code=0, output="ok", mutation=True)
    for field in ("ts", "job_id", "site_id", "environment", "action", "target", "actor",
                  "factory_commit", "mutation", "exit_code", "output"):
        assert field in entry, f"в журнале нет поля {field}"
    assert entry["actor"] == "tester"
    assert entry["mutation"] is True


def test_output_is_redacted(monkeypatch):
    monkeypatch.setenv("FACTORY_DEPLOY_TOKEN", "supersecretvalue123")
    entry = audit.record(job_id="j2", site_id="s1", environment="staging", action="deploy",
                         target="stage-1", exit_code=0,
                         output="using token supersecretvalue123 and password=hunter2secret")
    assert "supersecretvalue123" not in entry["output"]
    assert "hunter2secret" not in entry["output"]


def test_extra_payload_is_redacted():
    entry = audit.record(job_id="j3", site_id="s1", environment="staging", action="deploy",
                         target="stage-1", extra={"db_password": "x" * 20, "checks": ["seo-lint"]})
    assert entry["extra"]["db_password"] != "x" * 20
    assert entry["extra"]["checks"] == ["seo-lint"]


def test_log_is_append_only_jsonl():
    before = len(audit.read_all())
    audit.record(job_id="j4", site_id="s1", environment="staging", action="verify", target="-")
    entries = audit.read_all()
    assert len(entries) == before + 1
    raw = audit.audit_file().read_text(encoding="utf-8").strip().splitlines()
    for line in raw[-3:]:
        json.loads(line)


def test_commit_is_recorded():
    assert audit.factory_commit() != ""
