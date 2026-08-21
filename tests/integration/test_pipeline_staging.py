"""REQ-QA-LEVELS: полный проход конвейера на одноразовой цели."""
import json

import pytest

from factory import pipeline
from factory.paths import PATHS


@pytest.mark.slow
def test_full_staging_run_reaches_done():
    outcome = pipeline.run_job("pilot-local", skip_browser=True)
    assert outcome.status == "DONE", f"блокеры: {outcome.blockers}"
    data = json.loads(outcome.result_path.read_text(encoding="utf-8"))

    assert data["status"] == "DONE"
    assert data["build_id"] and data["release_id"]
    assert data["backup"]["restore_verified"] is True

    ids = {check["id"] for check in data["checks"]}
    assert {"seo-lint", "seo-crawl", "security-smoke", "acceptance-routes"} <= ids
    browser_dependent = {"seo-render", "performance-budget"}
    for check in data["checks"]:
        # Проверки, зависящие от браузера: с флагом skip_browser они честно
        # отмечаются как невыполненные (severity major), а не «пройденные».
        if check["id"] in browser_dependent:
            assert check["passed"] is False and check["severity"] == "major", \
                "пропущенная проверка не может выглядеть пройденной"
            continue
        assert check["passed"], f"{check['id']} не пройдена"
        artifact = PATHS.root / check["artifact"]
        assert artifact.exists(), f"проверка {check['id']} заявлена без артефакта"

    assert data["seo_summary"]["pages_total"] > 0
    assert data["seo_summary"]["orphan_pages"] == 0
    assert data["seo_summary"]["soft_404"] == 0
    assert data["seo_summary"]["duplicate_titles"] == 0
    assert any("приёмка неполная" in note for note in data["notes"]), \
        "неполная приёмка обязана быть названа в отчёте"


@pytest.mark.slow
def test_second_run_is_idempotent_and_keeps_state():
    first = pipeline.run_job("pilot-local", skip_browser=True)
    second = pipeline.run_job("pilot-local", skip_browser=True)
    assert first.status == second.status == "DONE"
    a = json.loads(first.result_path.read_text(encoding="utf-8"))
    b = json.loads(second.result_path.read_text(encoding="utf-8"))
    assert a["build_id"] == b["build_id"], "повторный прогон не создаёт новый релиз"


@pytest.mark.slow
def test_broken_package_blocks_before_any_mutation(temp_site):
    site = temp_site(lambda p: p.__setitem__("canonical_url", "https://wrong.example.test/"))
    outcome = pipeline.run_job(site, skip_browser=True)
    assert outcome.status == "BLOCKED_SEO"
    data = json.loads(outcome.result_path.read_text(encoding="utf-8"))
    assert data["mutations"] == []
    assert data["blockers"], "блокер обязан называть поле и требуемый вход"
    assert data["blockers"][0]["required_input"]
