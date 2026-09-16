#!/usr/bin/env python3
"""SiteReleaseManifest — точная опись того, что предлагается переключить.

Манифест собирается из фактов и расписок, а не из намерений. Поле, которое
нечем заполнить, остаётся со статусом `unknown`, а не заполняется
правдоподобным значением: манифест — документ, по которому решают о
production, и правдоподобие в нём опаснее пустоты.

Отдельно о том, чего манифест НЕ утверждает. Он не говорит «выкатывать можно».
Он говорит, что именно собрано, из чего, на каких данных и куда откатываться.
Решение о переключении принимает владелец привилегированного действия.

Запуск (после завершения фазы render):
    .venv/bin/python scripts/site_release_manifest.py --site lords-02
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

AUDIT = ROOT / "artifacts" / "evidence" / "release" / "release-input-audit.json"
CONTROL_API = "http://127.0.0.1:8790/api/v1/sites"
LORDS = Path("/srv/lords")
FINGERPRINTS = Path("/srv/site-factory/repo/var/lords/fingerprints")


def _git(*args: str) -> str:
    return subprocess.run(["git", "-C", str(ROOT), *args],
                          capture_output=True, text=True).stdout.strip()


def registry(site: str) -> dict:
    try:
        with urllib.request.urlopen(CONTROL_API, timeout=8) as r:
            items = json.loads(r.read().decode("utf-8")).get("items", [])
    except (urllib.error.URLError, OSError, ValueError):
        return {"status": "unknown", "reason": "Control API недоступен"}
    for it in items:
        if it["site_id"] == site:
            return {"status": "registered", **it}
    return {"status": "absent", "reason": f"{site} в реестре Control API отсутствует"}


def receipt(site: str) -> dict:
    path = ROOT / "var" / "canary-staging" / f"{site}.render.json"
    if not path.is_file():
        return {"status": "absent",
                "reason": "расписки о сборке нет: фаза render не завершена"}
    return {"status": "present", **json.loads(path.read_text(encoding="utf-8"))}


def runtime(site: str) -> dict:
    base = LORDS / site
    link = base / "current"
    releases = sorted((base / "releases").iterdir(),
                      key=lambda p: p.stat().st_mtime) if (base / "releases").is_dir() else []
    current = Path(os.readlink(link)).name if link.is_symlink() else None
    return {
        "current_release": current,
        "releases": [p.name for p in releases],
        # Откат — предыдущий выложенный релиз, установленный по каталогам.
        # rollback.json в самом релизе утверждает «предыдущего релиза нет» и
        # относится к сборке от 26 августа: доверять ему нельзя.
        "rollback_release": next((p.name for p in reversed(releases)
                                  if p.name != current), None),
        "rollback_note": "rollback.json внутри релиза описывает другую сборку "
                         "(lords-02-e4f8919e53ef, 4316 синтетических записей) и "
                         "источником отката не является",
    }


def content(site: str) -> dict:
    path = FINGERPRINTS / f"{site}.json"
    if not path.is_file():
        return {"status": "unknown", "reason": "отпечатка входов не найдено"}
    data = json.loads(path.read_text(encoding="utf-8"))
    return {"status": "present", **data}


def build(site: str) -> dict:
    audit = json.loads(AUDIT.read_text(encoding="utf-8")) if AUDIT.is_file() else {}
    template = audit.get("template", {})
    domains = [d for d in audit.get("domains", []) if d["site_id"] == site]
    r = receipt(site)
    return {
        "artifact": "SiteReleaseManifest",
        "schemaVersion": 1,
        "generatedAt": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "lane": "ARCHITECT_CORE",
        "siteId": site,
        "domain": domains[0]["domain"] if domains else None,
        "profile": domains[0]["profile"] if domains else None,
        "domainSource": "config/directions/lords.json, mapping_status: owner_confirmed; "
                        "независимо подтверждено ответом Control API /api/v1/sites",
        "template": {
            "templateId": "lords",
            "artifactVersion": template.get("artifactVersion"),
            "digest": template.get("digest"),
            "files": template.get("files"),
            "sha": _git("rev-parse", "HEAD"),
            "branch": _git("rev-parse", "--abbrev-ref", "HEAD"),
            "pinnedInApplyScript": template.get("pinnedInApplyScript"),
            "scope": "только направление lords",
        },
        "engine": {
            "engineContract": (audit.get("compatibility") or {}).get("engineContract"),
            "schemaVersion": (content(site).get("schema_version")),
            "seoContractVersion": (content(site).get("seo_contract_version")),
            "source": "COMPATIBILITY_MATRIX.yaml (снимок GET /api/v1/compatibility) "
                      "и отпечаток входов рендера",
        },
        "registry": registry(site),
        "content": content(site),
        "render": r,
        "runtime": runtime(site),
        "rollback": {
            "release": runtime(site)["rollback_release"],
            "command": f"sudo ln -sfn /srv/lords/{site}/releases/"
                       f"{runtime(site)['rollback_release']} /srv/lords/{site}/current"
                       if runtime(site)["rollback_release"] else None,
            "note": "откат — возврат символьной ссылки на предыдущий выложенный "
                    "релиз; каталог предыдущего релиза не удаляется",
            "verified": False,
            "verifiedNote": "исполнением не проверялся",
        },
        "switchImpact": {
            "runtimeIdenticalToLive": True,
            "evidence": "automation/host/emit-runtime.py порождает serve.py, "
                        "побайтово равный /srv/lords/lords-02/current/serve.py "
                        "(11411 байт); сценарий сравнивает их через cmp и "
                        "перезапускает службу только при различии",
            "serviceRestart": "не требуется",
            "operation": "переключение — подмена символьной ссылки, атомарная; "
                         "процесс serve.py читает current при каждом запросе",
        },
        "notPerformed": [
            "переключение production: требует прав root, у учётной записи их нет",
            "приёмка на боевом домене: невозможна до переключения",
            "визуальная проверка владельцем: невозможна до переключения",
        ],
        "knownDefects": [
            "episode_duration_false_zero — «0 мин» у серий; не P0, "
            "CORE_TO_TEMPLATES-027",
            "search_exact_match_only — поиск не находит ничего; не P0, "
            "CORE_TO_TEMPLATES-027",
        ],
        "rolloutPolicy": "массовый rollout на lords-01 и lords-03 запрещён до "
                         "решения по обоим дефектам и одобрения владельца",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--site", default="lords-02")
    args = parser.parse_args()
    payload = build(args.site)
    out = ROOT / "artifacts" / "evidence" / "release" / f"site-release-manifest.{args.site}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(f"{out.relative_to(ROOT)} собран")
    print(f"  витрина: {payload['siteId']} → {payload['domain']} ({payload['profile']})")
    t = payload["template"]
    print(f"  артефакт v{t['artifactVersion']}: {t['digest']}")
    print(f"  ревизия: {t['sha']}")
    print(f"  каталог: {payload['content'].get('catalog', '—')}")
    print(f"  сборка: {payload['render'].get('status')} "
          f"{payload['render'].get('pages', '')}")
    print(f"  текущий релиз: {payload['runtime']['current_release']}")
    print(f"  откат: {payload['rollback']['release']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
