"""Сводный SEO-отчёт задания."""
from __future__ import annotations

import json
from pathlib import Path

from factory.paths import PATHS
from factory.seo.model import Report


def combine(site_id: str, reports: list[Report], out_dir: Path | None = None) -> dict:
    out_dir = out_dir or PATHS.artifact_dir("seo", site_id)
    out_dir.mkdir(parents=True, exist_ok=True)
    expected = {"seo-lint", "seo-crawl", "seo-render"}
    present = {r.name for r in reports}
    summary = {
        "site_id": site_id,
        # Частичный набор не выдаётся за полный: одна команда seo-lint не доказывает
        # весь SEO-контур.
        "partial": not expected <= present,
        "missing_reports": sorted(expected - present),
        "passed": all(r.passed for r in reports) and expected <= present,
        "reports": [r.as_dict() for r in reports],
        "totals": {
            "critical": sum(len(r.critical) for r in reports),
            "major": sum(len([f for f in r.findings if f.severity == "major"]) for r in reports),
            "minor": sum(len([f for f in r.findings if f.severity == "minor"]) for r in reports),
        },
    }
    (out_dir / "seo-report.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    lines = [f"# SEO-отчёт — {site_id}", "",
             f"Итог: {'PASSED' if summary['passed'] else ('PARTIAL' if summary['partial'] else 'FAILED')}",
             ("Отчёт частичный, не выполнялись: " + ", ".join(summary["missing_reports"])) if summary["partial"] else "",
             f"Критических: {summary['totals']['critical']}, серьёзных: {summary['totals']['major']}, малых: {summary['totals']['minor']}", ""]
    for report in reports:
        lines.append(f"## {report.name} — {'passed' if report.passed else 'FAILED'}")
        lines.append("")
        lines.append(f"Счётчики: `{json.dumps(report.counts, ensure_ascii=False)}`")
        lines.append("")
        if report.findings:
            lines.append("| severity | check | url | сообщение |")
            lines.append("|---|---|---|---|")
            for finding in report.findings[:200]:
                message = finding.message.replace("|", "\\|")[:200]
                lines.append(f"| {finding.severity} | {finding.check} | `{finding.url}` | {message} |")
        else:
            lines.append("Находок нет.")
        lines.append("")
    (out_dir / "seo-report.md").write_text("\n".join(lines), encoding="utf-8")
    return summary
