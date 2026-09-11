#!/usr/bin/env python3
"""Каталог возможностей с ЖИВОЙ проверкой и манифест bundle с суммами.

AVAILABLE не объявляется по намерению. Каждая такая возможность здесь
проверяется запросом, и если адрес не ответил — статус становится BLOCKED,
а не остаётся AVAILABLE. Ложное AVAILABLE дороже отсутствующего: потребитель
построит на нём работу и обнаружит обман в проде.
"""
from __future__ import annotations
import datetime as dt, hashlib, json, pathlib, urllib.error, urllib.request

ВЕРСИЯ = "1.0.0"
КОРЕНЬ = pathlib.Path("/srv/site-factory/control-plane-contracts") / ВЕРСИЯ
БАЗА = "http://127.0.0.1:8790"
СЕЙЧАС = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def жив(путь: str) -> tuple[bool, int]:
    try:
        with urllib.request.urlopen(БАЗА + путь, timeout=10) as о:
            return о.status == 200, о.status
    except urllib.error.HTTPError as e:
        return False, e.code
    except Exception:
        return False, 0


ПРОВЕРЯЕМЫЕ = [
 ("registry.sites.read", "architect", "/api/v1/sites",
  ["site.registered.v1","site.updated.v1","site.activated.v1","site.retired.v1"]),
 ("registry.snapshot.read", "architect", "/api/v1/registry/snapshot", []),
 ("registry.version.read", "architect", "/api/v1/registry/version", []),
 ("registry.events.replay", "architect", "/api/v1/events",
  ["site.registered.v1","site.updated.v1","site.activated.v1","site.retired.v1"]),
 ("contracts.discovery", "architect", "/api/v1/contracts/manifest", []),
 ("capabilities.directory", "architect", "/api/v1/capabilities", []),
 ("control-plane.version", "architect", "/api/v1/control-plane/version", []),
]

ПЛАНИРУЕМЫЕ = [
 ("registry.commands.write", "architect", ["site.registered.v1"],
  ["registry:write"], ["contracts.discovery"],
  "командный API существует, но выносится наружу после IAM (FLEET-CORE-003)"),
 ("actions.ledger", "architect", ["action.recorded.v1"], ["actions:read"],
  [], "FLEET-CORE-002"),
 ("workflows.engine", "architect", ["workflow.started.v1"], ["workflow:read"],
  [], "FLEET-CORE-004"),
 ("changesets.controller", "architect", ["changeset.approved.v1"],
  ["changeset:read"], [], "владелец не реализован"),
 ("evidence.store", "architect", [], ["evidence:read"], [], "FLEET-CORE-002"),
 ("integrations.provisioner", "architect",
  ["integration.provision.completed.v1"], ["integration:write"], [],
  "создание счётчиков Метрики и проектов Topvisor; владелец не реализован"),
 ("templates.releases", "templates", ["template.release.published.v1"],
  ["templates:read"], [], "владелец не реализован"),
 ("content.catalog", "content", ["content.refresh.completed.v1"],
  ["content:read"], [], "владелец не реализован"),
 ("seo.audits", "seo", ["seo.audit.completed.v1"], ["seo:read"], [],
  "владелец не реализован"),
 ("monitoring.observations", "monitoring", ["monitor.alert.opened.v1"],
  ["monitoring:read"], [], "владелец не реализован"),
 ("backup.runs", "backup", ["backup.completed.v1"], ["backup:read"], [],
  "владелец не реализован"),
 ("qwen.planner", "qwen", [], ["qwen:propose"], ["contracts.discovery"],
  "MODEL-actor; только предложения, production apply выключен"),
]


def собрать() -> dict:
    возможности, ложных = [], 0
    for cid, owner, адрес, события in ПРОВЕРЯЕМЫЕ:
        ок, код = жив(адрес)
        возможности.append({
            "capability_id": cid, "owner_service": owner, "version": ВЕРСИЯ,
            "status": "AVAILABLE" if ок else "BLOCKED",
            "read_endpoint": адрес, "command_endpoint": None,
            "event_types": события, "required_scopes": ["registry:read"],
            "dependencies": [], "last_verified_at": СЕЙЧАС if ок else None,
            "evidence_ref": f"live-probe:{адрес}:HTTP{код}",
            "verified_http_status": код})
        if not ок:
            ложных += 1
    for cid, owner, события, скоупы, зав, почему in ПЛАНИРУЕМЫЕ:
        возможности.append({
            "capability_id": cid, "owner_service": owner, "version": ВЕРСИЯ,
            "status": "PLANNED",
            # У PLANNED адреса нет намеренно: иначе потребитель пойдёт туда.
            "read_endpoint": None, "command_endpoint": None,
            "event_types": события, "required_scopes": скоупы,
            "dependencies": зав, "last_verified_at": None,
            "evidence_ref": None, "planned_reason": почему})
    return {"schema_version": "1.0.0", "bundle_version": ВЕРСИЯ,
            "generated_at": СЕЙЧАС, "count": len(возможности),
            "available": sum(1 for c in возможности if c["status"] == "AVAILABLE"),
            "planned": sum(1 for c in возможности if c["status"] == "PLANNED"),
            "blocked": ложных, "capabilities": возможности}


if __name__ == "__main__":
    кат = собрать()
    (КОРЕНЬ / "capability-catalog.json").write_text(
        json.dumps(кат, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print("возможностей: %d (AVAILABLE %d, PLANNED %d, BLOCKED %d)"
          % (кат["count"], кат["available"], кат["planned"], кат["blocked"]))
    for c in кат["capabilities"]:
        if c["status"] == "BLOCKED":
            print("   BLOCKED:", c["capability_id"], c["evidence_ref"])

    # --- манифест и контрольные суммы --------------------------------------
    суммы = {}
    for p in sorted(КОРЕНЬ.rglob("*")):
        if p.is_file() and p.name not in ("checksums.json", "manifest.json",
                                          "_partial-checksums.json"):
            суммы[str(p.relative_to(КОРЕНЬ))] = hashlib.sha256(
                p.read_bytes()).hexdigest()
    (КОРЕНЬ / "checksums.json").write_text(
        json.dumps({"algorithm": "sha256", "generated_at": СЕЙЧАС,
                    "files": суммы}, ensure_ascii=False, indent=1) + "\n",
        encoding="utf-8")
    манифест = {
        "bundle": "fleet-control-plane-contracts", "version": ВЕРСИЯ,
        "generated_at": СЕЙЧАС, "owner": "architect",
        "compatibility_policy": {
            "url_major": "/api/v1",
            "bundle_versioning": "SemVer",
            "event_suffix": ".v1",
            "additive_optional_ok_within_major": True,
            "removal_or_rename_requires_new_major": True,
            "consumers_must_tolerate_unknown_optional": True,
            "provider_must_not_drop_required": True,
            "supported_majors": ["v1"],
            "note": ("Аддитивное расширение допустимо внутри major. "
                     "Удаление, переименование или смена смысла поля — "
                     "ломающее изменение и требует нового major.")},
        "artifacts": sorted(суммы),
        "checksums": "checksums.json",
        "schemas_count": len(list((КОРЕНЬ / "schemas").glob("*.json"))),
        "capabilities": {"available": кат["available"],
                         "planned": кат["planned"], "blocked": кат["blocked"]},
        "depends_on": {"prompt": "FLEET-ARC-001.R1", "commit": "4d8cb5a",
                       "registry_version_at_build": None},
    }
    try:
        with urllib.request.urlopen(БАЗА + "/api/v1/registry/version",
                                    timeout=10) as о:
            манифест["depends_on"]["registry_version_at_build"] = json.loads(
                о.read())["registry_version"]
    except Exception:
        pass
    (КОРЕНЬ / "manifest.json").write_text(
        json.dumps(манифест, ensure_ascii=False, indent=1) + "\n",
        encoding="utf-8")
    print("артефактов в манифесте:", len(манифест["artifacts"]))
    print("registry_version на момент сборки:",
          манифест["depends_on"]["registry_version_at_build"])
