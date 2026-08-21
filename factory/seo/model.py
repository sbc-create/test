"""Общая модель находки SEO-проверок."""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Finding:
    check: str
    severity: str          # critical | major | minor
    url: str
    message: str
    rule: str = ""

    def as_dict(self) -> dict:
        return {"check": self.check, "severity": self.severity, "url": self.url, "message": self.message, "rule": self.rule}


@dataclass
class Report:
    name: str
    findings: list[Finding] = field(default_factory=list)
    counts: dict = field(default_factory=dict)

    def add(self, finding: Finding) -> None:
        self.findings.append(finding)

    @property
    def critical(self) -> list[Finding]:
        return [f for f in self.findings if f.severity == "critical"]

    @property
    def passed(self) -> bool:
        return not self.critical

    def as_dict(self) -> dict:
        return {
            "name": self.name,
            "passed": self.passed,
            "counts": self.counts,
            "totals": {
                "critical": len(self.critical),
                "major": len([f for f in self.findings if f.severity == "major"]),
                "minor": len([f for f in self.findings if f.severity == "minor"]),
            },
            "findings": [f.as_dict() for f in self.findings],
        }
