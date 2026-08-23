"""Браузерная проверка: обёртка над tools/browser-audit.js.

Если Chromium недоступен, проверка честно возвращает статус `unavailable` и
попадает в отчёт как непройденная. Фабрика не помечает непроверенное как проверенное.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

from factory.paths import PATHS
from factory.seo.model import Finding, Report

CHROMIUM_CANDIDATES = (
    os.environ.get("FACTORY_CHROMIUM", ""),
    "/opt/pw-browsers/chromium-1194/chrome-linux/chrome",
    "/opt/pw-browsers/chromium/chrome-linux/chrome",
)


def chromium_path() -> str | None:
    for candidate in CHROMIUM_CANDIDATES:
        if candidate and Path(candidate).exists():
            return candidate
    return shutil.which("chromium") or shutil.which("google-chrome")


def available() -> tuple[bool, str]:
    if not (PATHS.root / "node_modules" / "playwright-core").exists():
        return False, "playwright-core не установлен (npm install)"
    if not (PATHS.root / "node_modules" / "axe-core").exists():
        return False, "axe-core не установлен (npm install)"
    path = chromium_path()
    if not path:
        return False, "исполняемый Chromium не найден"
    return True, path


def run(base_url: str, build_dir: Path, out_dir: Path, *, auth: str = "") -> Report:
    report = Report("seo-render")
    ok, detail = available()
    if not ok:
        report.add(Finding("browser", "critical", base_url, f"Браузерная проверка не выполнялась: {detail}."))
        report.counts = {"status": "unavailable"}
        return report
    out_dir.mkdir(parents=True, exist_ok=True)
    # Старый отчёт удаляется: иначе падение node до записи файла выдаёт прошлый
    # прогон за свежий вместе с устаревшими метриками и скриншотами.
    (out_dir / "browser-audit.json").unlink(missing_ok=True)
    cmd = [
        "node", str(PATHS.root / "tools" / "browser-audit.js"),
        "--base", base_url,
        "--routes", str(build_dir / "routes.json"),
        "--out", str(out_dir),
        "--executable", detail,
    ]
    # Учётные данные передаются окружением, а не argv: командная строка процесса
    # видна через `ps` и /proc/<pid>/cmdline любому пользователю хоста.
    child_env = dict(os.environ)
    if auth:
        child_env["FACTORY_STAGING_AUTH"] = auth
    else:
        child_env.pop("FACTORY_STAGING_AUTH", None)
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=1800, check=False,
                          env=child_env)
    audit_file = out_dir / "browser-audit.json"
    if not audit_file.exists():
        report.add(Finding("browser", "critical", base_url, f"Браузерная проверка завершилась без отчёта: {proc.stderr[:300]}"))
        report.counts = {"status": "failed", "exit_code": proc.returncode}
        return report
    if proc.returncode not in (0, 1):
        report.add(Finding("browser", "critical", base_url,
                           f"Браузерная проверка завершилась аварийно (exit {proc.returncode}): {proc.stderr[:200]}"))
        report.counts = {"status": "failed", "exit_code": proc.returncode}
        return report
    data = json.loads(audit_file.read_text(encoding="utf-8"))
    for finding in data.get("findings", []):
        report.add(Finding(finding["check"], finding["severity"], finding["url"],
                           f"[{finding.get('viewport')}] {finding['message']}"))
    for violation in data.get("a11y", []):
        targets = ", ".join(t["target"] for t in violation.get("targets", []))
        report.add(Finding("accessibility", "critical", violation["url"],
                           f"[{violation['viewport']}] {violation['id']} ({violation['impact']}): {violation['help']} → {targets}"))
    metrics = data.get("metrics", [])
    report.counts = {
        "status": "ok",
        "exit_code": proc.returncode,
        "viewports": data.get("viewports", []),
        "pages": len(data.get("sample", [])),
        "screenshots": len(data.get("screenshots", [])),
        "lab_lcp_ms_max": max((m["lcp_ms"] for m in metrics), default=None),
        "lab_cls_max": max((m["cls"] for m in metrics), default=None),
        "lab_transfer_bytes_max": max((m.get("transfer_bytes", 0) for m in metrics), default=None),
        "progressive_enhancement": data.get("enhance", {}),
        "note": "Лабораторные метрики. Полевые Core Web Vitals ими не подменяются.",
    }
    return report
