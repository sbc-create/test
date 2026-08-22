"""Read-only измерение референсного интерфейса.

Сеть открывается только для источников из `inventory/reference-sources.yaml` и
только на время измерения: allowlist берётся из inventory, а не из желания агента.
Наружу сохраняются собственные измерения и скриншоты; тексты, изображения,
каталог и чужие идентификаторы не сохраняются — это прямое требование задания.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path
from urllib.parse import urlparse

import yaml

from factory import audit
from factory.redaction import redact
from factory.errors import BlockedAccess, BlockedInput
from factory.paths import PATHS

SOURCES = PATHS.root / "inventory" / "reference-sources.yaml"
SCRIPT = PATHS.root / "tests" / "tools" / "measure_reference.js"


def sources() -> list[dict]:
    if not SOURCES.exists():
        return []
    data = yaml.safe_load(SOURCES.read_text(encoding="utf-8")) or {}
    return list(data.get("sources") or [])


def source(ref: str) -> dict:
    for entry in sources():
        if entry.get("ref") == ref:
            return entry
    raise BlockedInput(
        f"Референс «{ref}» отсутствует в inventory/reference-sources.yaml.",
        field="reference_ref",
        required_input="Запись источника, разрешённая владельцем проекта",
        blocks_stage="RECEIVED")


def measure(ref: str) -> dict:
    """Запускает браузерное измерение и возвращает сводку прогона."""
    entry = source(ref)
    if not entry.get("read_only", False):
        raise BlockedAccess(f"Источник «{ref}» не помечен read_only.", field="reference_ref",
                            blocks_stage="RECEIVED")

    url = entry["url"]
    host = urlparse(url).netloc
    out_dir = PATHS.root / "artifacts" / "reference"
    out_dir.mkdir(parents=True, exist_ok=True)

    chromium = Path(os.environ.get("FACTORY_CHROMIUM",
                                   "/opt/pw-browsers/chromium-1194/chrome-linux/chrome"))
    if not chromium.exists():
        summary = {"ref": ref, "url": url, "status": "unavailable_tool",
                   "reason": f"Chromium не найден по пути {chromium}",
                   "measured_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
        (out_dir / f"{ref}-run.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2),
                                                 encoding="utf-8")
        return summary

    env = dict(os.environ)
    # Allowlist на время измерения — ровно один хост из inventory.
    env["FACTORY_NETWORK_ALLOWLIST"] = host
    viewports = ",".join(str(v) for v in entry.get("viewports", [390, 768, 1024, 1440, 1920]))

    started = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    process = subprocess.run(
        ["node", str(SCRIPT), url, str(out_dir), viewports],
        cwd=PATHS.root, env=env, capture_output=True, text=True, timeout=600, check=False)

    measurements_path = out_dir / "measurements.json"
    measurements = {}
    if measurements_path.exists():
        measurements = json.loads(measurements_path.read_text(encoding="utf-8"))
        # Итоговый файл именуется по источнику: в артефактах не должно быть
        # безымянного measurements.json неизвестного происхождения.
        target = out_dir / f"{ref}-measurements.json"
        target.write_text(json.dumps(measurements, ensure_ascii=False, indent=2), encoding="utf-8")
        measurements_path.unlink()

    measured = list((measurements.get("viewports") or {}).keys())
    summary = {
        "ref": ref,
        "url": url,
        "started_at": started,
        "finished_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "exit_code": process.returncode,
        "status": "measured" if measured else "unavailable_blocked",
        "viewports_measured": measured,
        "errors": measurements.get("errors", []),
        # Вывод внешней команды проходит редакцию, как и любой другой.
        "stderr": redact(process.stderr.strip()[-800:]),
        "artifact": f"artifacts/reference/{ref}-measurements.json" if measured else None,
    }
    (out_dir / f"{ref}-run.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2),
                                             encoding="utf-8")
    audit.record(job_id=f"reference-{ref}", site_id=ref, environment="staging",
                 action="reference.measure", target=host, exit_code=process.returncode,
                 mutation=False, extra={"viewports": measured, "status": summary["status"]})
    return summary
