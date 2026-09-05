"""REQ-DOD: отчёт не может утверждать непроведённую проверку."""
import json
from pathlib import Path

import pytest

from factory.paths import PATHS
from factory.report import build_result, validate_result, write_result


def _minimal(**overrides):
    payload = {
        "job_id": "j1",
        "site_id": "pilot-local",
        "environment": "staging",
        "status": "DONE",
        "started_at": "2026-08-21T00:00:00Z",
    }
    payload.update(overrides)
    return build_result(**payload)


def test_minimal_result_validates():
    assert validate_result(_minimal()) == []


def test_check_without_artifact_is_rejected():
    result = _minimal(checks=[{"id": "seo-lint", "command": "x", "exit_code": 0, "passed": True}])
    problems = validate_result(result)
    assert any("artifact" in p for p in problems)


def test_check_without_exit_code_is_rejected():
    result = _minimal(checks=[{"id": "x", "command": "y", "passed": True, "artifact": "a.json"}])
    assert any("exit_code" in p for p in problems_of(result))


def problems_of(result):
    return validate_result(result)


def test_unknown_status_is_rejected():
    assert validate_result(_minimal(status="ALMOST_DONE"))


def test_writing_invalid_result_raises():
    with pytest.raises(ValueError):
        write_result(_minimal(status="NOT_A_STATUS"))


def test_result_records_commit_and_freeze():
    result = _minimal()
    assert result["factory_commit"]
    assert result["knowledge_freeze_version"]


def test_secrets_never_reach_the_result(monkeypatch):
    monkeypatch.setenv("FACTORY_SECRET_TOKEN", "topsecretvalue0001")
    result = _minimal(notes=["deployed with token topsecretvalue0001"],
                      steps=[{"id": "s", "status": "ok", "started_at": "t", "finished_at": "t",
                              "detail": "password=hunter2secret"}])
    text = json.dumps(result, ensure_ascii=False)
    assert "topsecretvalue0001" not in text
    assert "hunter2secret" not in text


#: Настоящие результаты пилота, закреплённые как фикстуры.
#:
#: Прежде тест читал artifacts/jobs/pilot-local — runtime-состояние, которое
#: появляется только там, где задание реально прогонялось, и в git не хранится.
#: Тот же файл проходил в одном рабочем каталоге и падал в свежем: исход зависел
#: не от кода, а от того, что осталось на диске. Гейт, который так себя ведёт,
#: ничего не гарантирует.
#:
#: Фикстуры — это настоящие результаты боевых прогонов (BLOCKED_SEO и DONE),
#: проверенные на отсутствие секретов. Живые артефакты по-прежнему проверяются,
#: когда они есть, но их отсутствие больше не роняет набор.
FIXTURE_DIR = Path(__file__).resolve().parents[1] / "fixtures" / "job-results"


def _результаты_пилота():
    фикстуры = sorted(FIXTURE_DIR.glob("*.json"))
    job_dir = PATHS.artifacts / "jobs" / "pilot-local"
    живые = sorted(job_dir.glob("*.json")) if job_dir.exists() else []
    return фикстуры, живые


def test_real_pilot_results_are_schema_valid():
    фикстуры, живые = _результаты_пилота()
    assert фикстуры, (
        "фикстуры настоящих результатов пилота обязаны лежать в репозитории: "
        "без них проверка зависит от runtime-состояния рабочего каталога")
    for path in фикстуры + живые:
        assert validate_result(json.loads(path.read_text(encoding="utf-8"))) == [], path


def test_фикстуры_покрывают_и_успех_и_блокировку():
    """Одного исхода мало: схема обязана держать оба."""
    статусы = {json.loads(p.read_text(encoding="utf-8"))["status"]
               for p in sorted(FIXTURE_DIR.glob("*.json"))}
    assert len(статусы) >= 2, f"фикстуры покрывают только {статусы}"


def test_done_never_hides_a_failed_critical_check():
    """DONE допустим только когда ни одна критическая проверка не провалена, а
    любая невыполненная проверка честно названа в отчёте.

    Проверяются и фикстуры, и живые артефакты. Прежде тест обходил только
    живые, и на пустом каталоге проходил, ничего не проверив.
    """
    фикстуры, живые = _результаты_пилота()
    for path in фикстуры + живые:
        data = json.loads(path.read_text(encoding="utf-8"))
        if data["status"] != "DONE":
            continue
        failed_critical = [c["id"] for c in data["checks"]
                           if not c["passed"] and c.get("severity", "critical") == "critical"]
        assert not failed_critical, f"{path.name}: DONE при провале {failed_critical}"
        not_passed = [c["id"] for c in data["checks"] if not c["passed"]]
        if not_passed:
            notes = " ".join(data.get("notes", []))
            assert "приёмка неполная" in notes, \
                f"{path.name}: непройденные проверки {not_passed} не отражены в отчёте"


def test_checks_carry_severity():
    job_dir = PATHS.artifacts / "jobs" / "pilot-local"
    for path in sorted(job_dir.glob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        for check in data["checks"]:
            assert check.get("severity") in ("critical", "major", "minor")
