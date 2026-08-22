"""Pipeline tests: dry-run writes nothing, canary is bounded, rollback is real."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from seo_operator.audit import AuditLog, ChangeStatus
from seo_operator.experiments import (
    CanaryScopeError,
    Experiment,
    Observation,
    Phase,
    Verdict,
)
from seo_operator.pipeline import Mode, Operator, ProductionSafetyError
from seo_operator.registry import load_portfolio
from seo_operator.technical_seo import Page

FIXTURE = Path("config/portfolio.fixture.json")
TODAY = date(2026, 8, 22)


def pages():
    return [
        Page(
            url="https://anime.example-fixture.test/t/1",
            title="Очень длинное название карточки, которое точно не влезет в выдачу поиска",
            description="Описание.",
            h1=["Заголовок"],
            canonical="https://anime.example-fixture.test/t/1",
            status_code=200,
            indexable=True,
            internal_links_in=3,
            in_sitemap=True,
            lastmod="2026-08-20",
            raw_html_text_length=4000,
            rendered_text_length=4100,
            open_graph={
                "og:title": "t",
                "og:description": "d",
                "og:image": "i",
                "og:type": "video",
            },
        ),
        Page(
            url="https://anime.example-fixture.test/t/2",
            title="Короткий title",
            description="Описание.",
            h1=["Заголовок"],
            canonical="https://anime.example-fixture.test/other",
            status_code=200,
            indexable=True,
            internal_links_in=2,
            in_sitemap=True,
            lastmod="2026-08-20",
            raw_html_text_length=4000,
            rendered_text_length=4100,
            open_graph={
                "og:title": "t",
                "og:description": "d",
                "og:image": "i",
                "og:type": "video",
            },
        ),
    ]


def operator(tmp_path, allow_synthetic=True):
    return Operator(
        portfolio=load_portfolio(FIXTURE),
        audit_log=AuditLog(tmp_path / "audit.jsonl"),
        allow_synthetic=allow_synthetic,
    )


class TestDryRun:
    def test_dry_run_writes_nothing_to_audit(self, tmp_path):
        op = operator(tmp_path)
        result = op.run(Mode.DRY_RUN, pages_by_site={"fixture-anime": pages()}, today=TODAY)
        assert result.proposed_changes
        assert result.applied_changes == []
        assert op.audit.records() == []

    def test_dry_run_proposes_fixes_for_mechanical_findings(self, tmp_path):
        result = operator(tmp_path).run(
            Mode.DRY_RUN, pages_by_site={"fixture-anime": pages()}, today=TODAY
        )
        kinds = {c.kind.value for c in result.proposed_changes}
        assert "title" in kinds and "canonical" in kinds

    def test_proposed_changes_are_reversible(self, tmp_path):
        result = operator(tmp_path).run(
            Mode.DRY_RUN, pages_by_site={"fixture-anime": pages()}, today=TODAY
        )
        for change in result.proposed_changes:
            payload = change.rollback_payload
            assert payload["restore_value"] == change.before

    def test_dry_run_refuses_to_write(self, tmp_path):
        op = operator(tmp_path)
        with pytest.raises(ProductionSafetyError, match="dry-run"):
            op._assert_writable("fixture-anime", Mode.DRY_RUN)

    def test_empty_crawl_yields_no_findings_and_says_so(self, tmp_path):
        result = operator(tmp_path).run(Mode.DRY_RUN, pages_by_site={}, today=TODAY)
        assert result.findings == []
        assert any("нет данных обхода" in n for n in result.notes)


class TestBlockers:
    def test_empty_real_portfolio_is_reported_as_a_blocker(self, tmp_path):
        op = Operator(
            portfolio=load_portfolio(Path("config/portfolio.json")),
            audit_log=AuditLog(tmp_path / "a.jsonl"),
        )
        result = op.run(Mode.INVENTORY, today=TODAY)
        assert any("портфель пуст" in b for b in result.blockers)

    def test_unavailable_sources_are_listed(self, tmp_path):
        result = operator(tmp_path).run(Mode.INVENTORY, today=TODAY)
        assert any("google_search_console" in b for b in result.blockers)

    def test_quality_gate_fails_without_search_sources(self, tmp_path):
        result = operator(tmp_path).run(Mode.INVENTORY, today=TODAY)
        assert result.quality.result.value == "fail"
        assert not result.quality.can_publish_metrics


class TestCanary:
    def make_experiment(self, **kw):
        defaults = {
            "hypothesis": "Сокращение title повысит CTR",
            "site_id": "fixture-anime",
            "primary_metric": "ctr",
            "scope_pages": 2,
            "site_total_pages": 100,
        }
        defaults.update(kw)
        return Experiment(**defaults)

    def test_canary_applies_and_audits(self, tmp_path):
        op = operator(tmp_path)
        result = op.run(Mode.DRY_RUN, pages_by_site={"fixture-anime": pages()}, today=TODAY)
        exp = self.make_experiment()
        applied = op.apply_canary(exp, result.proposed_changes)
        assert applied and all(c.status is ChangeStatus.APPLIED for c in applied)
        records = op.audit.records()
        assert len(records) == len(applied)
        assert all(r["rollback_payload"]["restore_value"] is not None for r in records)

    def test_canary_rejects_oversized_scope(self, tmp_path):
        op = operator(tmp_path)
        exp = self.make_experiment(scope_pages=50, site_total_pages=100)
        with pytest.raises(CanaryScopeError):
            op.apply_canary(exp, [])

    def test_canary_rejects_portfolio_wide_rollout(self, tmp_path):
        op = operator(tmp_path)
        with pytest.raises(CanaryScopeError, match="сайтов"):
            op.apply_canary(self.make_experiment(), [], sites_touched=15)

    def test_synthetic_site_write_blocked_without_opt_in(self, tmp_path):
        op = operator(tmp_path, allow_synthetic=False)
        with pytest.raises(ProductionSafetyError, match="синтетический"):
            op.apply_canary(self.make_experiment(), [])


class TestObserveAndRollback:
    def setup_canary(self, tmp_path):
        op = operator(tmp_path)
        result = op.run(Mode.DRY_RUN, pages_by_site={"fixture-anime": pages()}, today=TODAY)
        exp = Experiment(
            hypothesis="h",
            site_id="fixture-anime",
            primary_metric="ctr",
            scope_pages=2,
            site_total_pages=100,
        )
        op.apply_canary(exp, result.proposed_changes)
        return op, exp

    def test_regression_triggers_rollback_records(self, tmp_path):
        op, exp = self.setup_canary(tmp_path)
        verdict, reason, rolled = op.observe_and_decide(
            exp, Observation(days_elapsed=15, impressions=5000, primary_metric_delta=-0.10)
        )
        assert verdict is Verdict.ROLLBACK
        assert exp.phase is Phase.ROLLED_BACK
        assert len(rolled) == len(exp.changes)
        assert all(r["action"] == "rollback" for r in rolled)
        assert all(c.status is ChangeStatus.ROLLED_BACK for c in exp.changes)

    def test_rollback_restores_original_values(self, tmp_path):
        op, exp = self.setup_canary(tmp_path)
        originals = {c.entity_id: c.before for c in exp.changes}
        _, _, rolled = op.observe_and_decide(
            exp, Observation(days_elapsed=15, impressions=5000, primary_metric_delta=-0.10)
        )
        for record in rolled:
            assert record["restore_value"] == originals[record["entity_id"]]

    def test_improvement_is_kept_without_rollback(self, tmp_path):
        op, exp = self.setup_canary(tmp_path)
        verdict, _, rolled = op.observe_and_decide(
            exp, Observation(days_elapsed=15, impressions=5000, primary_metric_delta=0.11)
        )
        assert verdict is Verdict.KEEP
        assert exp.phase is Phase.KEPT
        assert rolled == []

    def test_immature_data_keeps_observing(self, tmp_path):
        op, exp = self.setup_canary(tmp_path)
        verdict, _, rolled = op.observe_and_decide(
            exp, Observation(days_elapsed=2, impressions=100, primary_metric_delta=0.03)
        )
        assert verdict is Verdict.CONTINUE
        assert exp.phase is Phase.OBSERVING
        assert rolled == []

    def test_audit_log_survives_restart(self, tmp_path):
        op, exp = self.setup_canary(tmp_path)
        op.observe_and_decide(
            exp, Observation(days_elapsed=15, impressions=5000, primary_metric_delta=-0.10)
        )
        reopened = AuditLog(tmp_path / "audit.jsonl")
        actions = [r.get("action") for r in reopened.records()]
        assert "rollback" in actions


class TestReportRendering:
    """The report must show what actually changed, not two identical stumps."""

    def test_prefix_change_shows_the_removed_tail(self):
        from seo_operator.reporting import render_delta

        out = render_delta("Длинный заголовок, который обрезали", "Длинный заголовок")
        assert "убрано" in out
        assert "который обрезали" in out

    def test_differing_values_never_render_identically(self):
        from seo_operator.reporting import render_delta

        a = "https://anime.example-fixture.test/title/other"
        b = "https://anime.example-fixture.test/title/2"
        out = render_delta(a, b)
        left, _, right = out.partition("→")
        assert left.strip() != right.strip()

    def test_lengths_are_reported(self):
        from seo_operator.reporting import render_delta

        assert "(8→13 симв.)" in render_delta("короткий", "совсем другой")

    def test_report_contains_no_zero_for_unmeasured_metric(self, tmp_path):
        """The regression the quality gate exists to prevent."""
        from seo_operator.reporting import daily_report

        result = operator(tmp_path).run(
            Mode.DRY_RUN, pages_by_site={"fixture-anime": pages()}, today=TODAY
        )
        text = daily_report(result, TODAY)
        assert "не измерено" in text
        assert "| Показы | 0 |" not in text

    def test_report_lists_blockers_as_one_block(self, tmp_path):
        from seo_operator.reporting import daily_report

        result = operator(tmp_path).run(Mode.INVENTORY, today=TODAY)
        text = daily_report(result, TODAY)
        assert "## Блокеры" in text
        assert "google_search_console" in text
