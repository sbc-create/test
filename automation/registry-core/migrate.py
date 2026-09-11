"""Перенос профилей в авторитетное хранилище Registry. Обратим: файлы целы."""
import json, pathlib, sys
sys.path.insert(0, "/srv/site-factory/registry-core")
import registry_store as rs

ПРОФИЛИ = pathlib.Path("/srv/site-factory/repo/config/site-profiles")
БД = "/srv/site-factory/registry-core/registry.sqlite3"
СЕМЬЯ = {"lords-01": "lords", "lords-02": "lords", "lords-03": "lords",
         "yummyani-biz": "yummy", "yummyani-org": "yummy", "yummyani-site": "yummy",
         "zona-01": "zona", "animedia-01": "animedia", "animedia-02": "animedia"}
# demo-books: домен в зоне .invalid (RFC 2606) — в DNS существовать не может.
# Это образец, а не витрина, поэтому среда non-production и состояние DRAFT.
НЕ_PRODUCTION = {"demo-books": ("non-production", "DRAFT",
                                "RFC2606 .invalid; образец, не витрина")}

соед = rs.открыть(БД)
перенесено = []
for f in sorted(ПРОФИЛИ.glob("*.json")):
    d = json.loads(f.read_text(encoding="utf-8"))
    sid = d["site_id"]
    домен = (d.get("domains") or [None])[0]
    dep = d.get("deployment") or {}
    среда, состояние, _ = НЕ_PRODUCTION.get(sid, ("production", "ACTIVE", ""))
    поля = {
        "canonical_domain": домен,
        "family": d.get("family") or СЕМЬЯ.get(sid) or "unknown",
        "environment": среда, "lifecycle_state": состояние,
        "owner_ref": "ARCHITECT_CORE",
        "template_id": dep.get("template_family"),
        "template_version": dep.get("template_version"),
        "build_id": dep.get("build_id"),
        "release_id": dep.get("release_id"),
        "desired_state": "ACTIVE" if состояние == "ACTIVE" else состояние,
        "observed_state": None,          # наблюдаемое ставит не реестр
        # Только несекретные ссылки. Значение credential сюда не попадает
        # никогда — переносится имя ссылки, по которому его найдёт тот,
        # у кого есть права.
        "integration_refs": {k: v for k, v in
                             (d.get("content_providers") or {}).items()
                             if isinstance(v, str)} if isinstance(
                                 d.get("content_providers"), dict) else {},
        "monitoring_profile_ref": None, "backup_policy_ref": None,
        "content_profile_ref": None,
        "seo_profile_ref": f"seo:{sid}" if d.get("seo_profile") else None,
    }
    р = rs.применить(соед, команда="register", site_id=sid, поля=поля,
                     actor="service:architect", aliases=[])
    if состояние == "ACTIVE":
        rs.применить(соед, команда="activate", site_id=sid, поля={},
                     actor="service:architect", causation_id=р["correlation_id"])
    перенесено.append((sid, домен, среда, состояние))

print("перенесено записей:", len(перенесено))
for sid, домен, среда, сост in перенесено:
    print("   %-14s %-22s %-14s %s" % (sid, домен, среда, сост))
сн = rs.снимок(соед)
print("\nsnapshot: production ACTIVE = %d, registry_version = %d"
      % (сн["count"], сн["registry_version"]))
print("checksum:", сн["checksum"][:16], " etag:", сн["etag"])
ев = rs.события(соед, after=0, limit=500)
типы = {}
for e in ев["items"]:
    типы[e["event_type"]] = типы.get(e["event_type"], 0) + 1
print("событий в outbox:", len(ев["items"]), типы)
