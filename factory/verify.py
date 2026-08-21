"""Сводные ворота качества: SEO, браузер, безопасность, производительность.

Каждая проверка возвращает фактическую команду, exit code и путь к артефакту.
Проверка без артефакта не считается пройденной — это прямое требование к отчёту.
"""
from __future__ import annotations

import base64
import json
import re
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path

from factory.paths import PATHS
from factory.seo import crawl as crawl_mod
from factory.seo import lint as lint_mod
from factory.seo import render_check
from factory.seo.model import Finding, Report


@dataclass
class Check:
    id: str
    command: str
    exit_code: int
    passed: bool
    artifact: str
    counts: dict = field(default_factory=dict)
    severity: str = "critical"

    def as_dict(self) -> dict:
        return {"id": self.id, "command": self.command, "exit_code": self.exit_code, "passed": self.passed,
                "artifact": self.artifact, "counts": self.counts, "severity": self.severity}


def _get(base_url: str, path: str, auth: str = "") -> tuple[int, dict, str]:
    request = urllib.request.Request(base_url.rstrip("/") + path, headers={"User-Agent": "factory-verify/1.0"})
    if auth:
        request.add_header("Authorization", "Basic " + base64.b64encode(auth.encode()).decode())
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            return response.status, dict(response.headers), response.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as exc:
        return exc.code, dict(exc.headers), exc.read().decode("utf-8", "replace")
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        return 0, {}, str(exc)


REQUIRED_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": None,
    "Referrer-Policy": None,
    "Content-Security-Policy": None,
}

FORBIDDEN_PUBLIC_PATHS = (
    "/.env", "/.git/config", "/routes.json", "/build-manifest.json",
    "/shared/logs/php-server.log", "/backups/", "/install.php", "/engine/data/config.php",
)


def security_smoke(base_url: str, out_dir: Path, *, auth: str = "", environment: str = "staging") -> Report:
    report = Report("security-smoke")
    status, headers, body = _get(base_url, "/", auth)
    for header, expected in REQUIRED_HEADERS.items():
        value = headers.get(header)
        if not value:
            report.add(Finding("headers", "critical", "/", f"Отсутствует заголовок {header}."))
        elif expected and expected not in value:
            report.add(Finding("headers", "critical", "/", f"{header} = «{value}», ожидалось «{expected}»."))
    if headers.get("X-Powered-By"):
        report.add(Finding("headers", "major", "/", "X-Powered-By раскрывает стек."))
    if environment != "production" and "noindex" not in headers.get("X-Robots-Tag", ""):
        report.add(Finding("staging", "critical", "/", "Staging не отдаёт X-Robots-Tag: noindex."))
    if environment != "production":
        anon_status, anon_headers, _ = _get(base_url, "/", "")
        if anon_status != 401:
            report.add(Finding("staging", "critical", "/", f"Staging доступен без авторизации (HTTP {anon_status}). robots.txt защитой не считается."))
    for path in FORBIDDEN_PUBLIC_PATHS:
        code, _, _ = _get(base_url, path, auth)
        if code not in (401, 403, 404):
            report.add(Finding("exposure", "critical", path, f"Служебный путь доступен публично (HTTP {code})."))
    # directory listing
    code, _, listing = _get(base_url, "/assets/", auth)
    if code == 200 and re.search(r"Index of|<title>Directory listing", listing, re.I):
        report.add(Finding("exposure", "critical", "/assets/", "Включён листинг каталога."))
    # mixed content
    if "http://" in re.sub(r'http://(127\.0\.0\.1|localhost)', "", body):
        report.add(Finding("mixed-content", "major", "/", "На странице есть ссылки по http://."))
    report.counts = {"checked_paths": len(FORBIDDEN_PUBLIC_PATHS), "root_status": status}
    (out_dir / "security-smoke.json").write_text(json.dumps(report.as_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
    return report


def performance_budget(browser_report: Report, package: dict, out_dir: Path) -> Report:
    """Лабораторные бюджеты. Полевые CWV ими не заменяются — это записано в отчёте."""
    report = Report("performance-budget")
    budgets = ((package.get("acceptance") or {}).get("performance") or {})
    counts = browser_report.counts or {}
    lcp = counts.get("lab_lcp_ms_max")
    cls = counts.get("lab_cls_max")
    transfer = counts.get("lab_transfer_bytes_max")
    status = counts.get("status")
    if status == "skipped":
        # Оператор осознанно сократил объём приёмки: это не дефект сайта, но и не доказательство.
        report.add(Finding("performance", "major", "-", "Метрики не собраны: браузерная проверка пропущена флагом."))
    elif status != "ok":
        report.add(Finding("performance", "critical", "-", f"Метрики не собраны: браузерная проверка недоступна ({status})."))
    else:
        if budgets.get("lab_lcp_ms") and lcp is not None and lcp > budgets["lab_lcp_ms"]:
            report.add(Finding("performance", "critical", "-", f"Lab LCP {lcp} мс превышает бюджет {budgets['lab_lcp_ms']} мс."))
        if budgets.get("lab_cls") is not None and cls is not None and cls > budgets["lab_cls"]:
            report.add(Finding("performance", "critical", "-", f"Lab CLS {cls} превышает бюджет {budgets['lab_cls']}."))
        if budgets.get("lab_total_bytes") and transfer and transfer > budgets["lab_total_bytes"]:
            report.add(Finding("performance", "major", "-", f"Передано {transfer} байт при бюджете {budgets['lab_total_bytes']}."))
    report.counts = {
        "lab_lcp_ms_max": lcp, "lab_cls_max": cls, "lab_transfer_bytes_max": transfer,
        "budgets": budgets,
        "field_targets_note": "Полевые LCP ≤ 2.5 s, INP ≤ 200 ms, CLS ≤ 0.1 на 75-м перцентиле измеряются только на реальном трафике.",
    }
    (out_dir / "performance-budget.json").write_text(json.dumps(report.as_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
    return report


def acceptance_routes(base_url: str, package: dict, out_dir: Path, *, auth: str = "") -> Report:
    report = Report("acceptance-routes")
    for route in (package.get("acceptance") or {}).get("routes") or []:
        status, headers, body = _get(base_url, route["path"], auth)
        if status != route["expected_status"]:
            report.add(Finding("acceptance", "critical", route["path"], f"Ожидался {route['expected_status']}, получен {status}."))
            continue
        if route.get("expect_indexable") is False and status == 200:
            robots = headers.get("X-Robots-Tag", "") + (re.search(r'<meta name="robots" content="([^"]+)"', body).group(1) if re.search(r'<meta name="robots" content="([^"]+)"', body) else "")
            if "noindex" not in robots:
                report.add(Finding("acceptance", "critical", route["path"], "Маршрут должен быть неиндексируемым, но noindex отсутствует."))
    report.counts = {"routes": len((package.get("acceptance") or {}).get("routes") or [])}
    (out_dir / "acceptance-routes.json").write_text(json.dumps(report.as_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
    return report


def verify(site_id: str, package: dict, build_dir: Path, base_url: str, *, auth: str = "",
           environment: str = "staging", skip_browser: bool = False) -> tuple[list[Check], list[Report]]:
    out_dir = PATHS.artifact_dir("qa", site_id)
    checks: list[Check] = []
    reports: list[Report] = []

    lint_report = lint_mod.lint(build_dir, environment=environment)
    (out_dir / "seo-lint.json").write_text(json.dumps(lint_report.as_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
    reports.append(lint_report)
    checks.append(Check("seo-lint", f"python3 -m factory seo-lint --site {site_id}", 0 if lint_report.passed else 1,
                        lint_report.passed, str((out_dir / "seo-lint.json").relative_to(PATHS.root)), lint_report.counts))

    crawl_report = crawl_mod.crawl(base_url, build_dir, auth=auth, environment=environment)
    (out_dir / "seo-crawl.json").write_text(json.dumps(crawl_report.as_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
    reports.append(crawl_report)
    checks.append(Check("seo-crawl", f"python3 -m factory seo-crawl --site {site_id} --base {base_url}",
                        0 if crawl_report.passed else 1, crawl_report.passed,
                        str((out_dir / "seo-crawl.json").relative_to(PATHS.root)), crawl_report.counts))

    if skip_browser:
        browser_report = Report("seo-render")
        # severity=major: это осознанное сокращение объёма приёмки оператором,
        # а не найденный дефект. Проверка при этом НЕ считается пройденной.
        browser_report.add(Finding("browser", "major", base_url,
                                   "Браузерная проверка не выполнялась (--skip-browser): приёмка неполная."))
        browser_report.counts = {"status": "skipped"}
    else:
        browser_report = render_check.run(base_url, build_dir, out_dir, auth=auth)
    (out_dir / "seo-render.json").write_text(json.dumps(browser_report.as_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
    reports.append(browser_report)
    render_passed = browser_report.passed and not skip_browser
    checks.append(Check("seo-render", f"node tools/browser-audit.js --base {base_url}",
                        0 if render_passed else 1, render_passed,
                        str((out_dir / "seo-render.json").relative_to(PATHS.root)), browser_report.counts,
                        severity="major" if skip_browser else "critical"))

    security = security_smoke(base_url, out_dir, auth=auth, environment=environment)
    reports.append(security)
    checks.append(Check("security-smoke", f"python3 -m factory verify --site {site_id} (security)",
                        0 if security.passed else 1, security.passed,
                        str((out_dir / "security-smoke.json").relative_to(PATHS.root)), security.counts))

    acceptance = acceptance_routes(base_url, package, out_dir, auth=auth)
    reports.append(acceptance)
    checks.append(Check("acceptance-routes", f"python3 -m factory verify --site {site_id} (acceptance)",
                        0 if acceptance.passed else 1, acceptance.passed,
                        str((out_dir / "acceptance-routes.json").relative_to(PATHS.root)), acceptance.counts))

    performance = performance_budget(browser_report, package, out_dir)
    reports.append(performance)
    performance_passed = performance.passed and not skip_browser
    checks.append(Check("performance-budget", f"python3 -m factory verify --site {site_id} (performance)",
                        0 if performance_passed else 1, performance_passed,
                        str((out_dir / "performance-budget.json").relative_to(PATHS.root)), performance.counts,
                        severity="major" if skip_browser else "critical"))

    return checks, reports
