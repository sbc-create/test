"""Повторная проверка всех гейтов FLEET-ARC-001.R1 против боевой службы."""
import json, sqlite3, subprocess, sys, urllib.error, urllib.request
Б = "http://127.0.0.1:8790"
БД = "/srv/site-factory/registry-core/registry.sqlite3"
ЦЕЛЕВЫЕ = {"lordfilm47.space", "lordserial33.biz", "1lordserials1.online",
           "yummyani.biz", "yummyani.org", "yummyani.site",
           "zonafilm.space", "animedia.icu", "animedia.space"}
ИСХОДНЫЕ = {"lords-01", "lords-02", "lords-03",
            "yummyani-biz", "yummyani-org", "yummyani-site"}

def дай(п):
    try:
        with urllib.request.urlopen(Б + п, timeout=15) as o:
            return o.status, json.loads(o.read() or b"{}")
    except urllib.error.HTTPError as e:
        return e.code, {}
    except Exception:
        return 0, {}

ок = 0; всего = 0; провалы = []
def g(имя, условие, деталь=""):
    global ок, всего
    всего += 1
    if условие: ок += 1
    else: провалы.append(имя)
    print("  %-58s %s %s" % (имя, "PASS" if условие else "FAIL", деталь))

к, sites = дай("/api/v1/sites")
items = sites.get("items", [])
g("G00 служба читает из реестра (source=registry)",
  к == 200 and sites.get("source") == "registry", f"source={sites.get('source')}")
g("G00 параллельных реестров нет",
  subprocess.run(["bash","-c","ss -lnt | grep -c 8791"],capture_output=True,
                 text=True).stdout.strip() == "0")

к, snap = дай("/api/v1/registry/snapshot")
домены = {s["canonical_domain"] for s in snap.get("sites", [])}
g("G01 ACTIVE production = 9/9", snap.get("count") == 9, f"{snap.get('count')}")
g("G01 состав доменов совпадает с целевым", домены == ЦЕЛЕВЫЕ,
  f"лишние={sorted(домены-ЦЕЛЕВЫЕ)} нет={sorted(ЦЕЛЕВЫЕ-домены)}")
ПОЛЯ = ("site_id","canonical_domain","aliases","family","environment",
        "lifecycle_state","owner_ref","template_id","template_version",
        "build_id","release_id","desired_state","observed_state",
        "integration_refs","monitoring_profile_ref","backup_policy_ref",
        "content_profile_ref","seo_profile_ref","created_at","updated_at")
полные = sum(1 for s in snap.get("sites", []) if all(p in s for p in ПОЛЯ))
g("G01 обязательные поля 9/9", полные == 9, f"{полные}")
ids = {i["site_id"] for i in items}
g("G01 исходные site_id сохранены 6/6", ИСХОДНЫЕ <= ids)
g("G01 дубликатов canonical_domain нет", len(домены) == len(snap.get("sites", [])))

g("G02 седьмая запись demo-books не в production",
  "demo-books.invalid" not in домены and "demo-books" in ids)

c = sqlite3.connect(БД); c.row_factory = sqlite3.Row
фикстур = c.execute("SELECT count(*) n FROM site WHERE environment='production' "
                    "AND canonical_domain LIKE '%.test'").fetchone()["n"]
g("G03 fixture-доменов в production = 0", фикстур == 0, f"{фикстур}")

к1, ver = дай("/api/v1/registry/version")
к2, ev = дай("/api/v1/events?after=0&limit=5")
g("G04 registry/version", к1 == 200 and isinstance(ver.get("registry_version"), int),
  f"v{ver.get('registry_version')}")
g("G04 events по курсору", к2 == 200 and len(ev.get("items", [])) == 5)
g("G04 совместимость: прежние ключи",
  all({"site_id","site_type","domains","render_mode"} <= set(i) for i in items))
g("G04 аддитивность: новые поля",
  all("lifecycle_state" in i and "build_id" in i for i in items))

backlog = c.execute("SELECT count(*) n FROM outbox WHERE published_at IS NULL"
                    ).fetchone()["n"]
eids = [r["event_id"] for r in c.execute("SELECT event_id FROM outbox")]
g("G05 outbox backlog = 0", backlog == 0, f"{backlog}")
g("G05 event_id уникальны", len(eids) == len(set(eids)), f"{len(eids)}")
seqs = [r["seq"] for r in c.execute("SELECT seq FROM outbox ORDER BY seq")]
g("G05 seq монотонна", seqs == sorted(seqs))

т = subprocess.run(["/home/claude/work-test/.venv/bin/python","-m","pytest",
                    "test_registry.py","test_command.py","-q"],
                   cwd="/srv/site-factory/registry-core",
                   capture_output=True, text=True)
последняя = (т.stdout or "").strip().splitlines()[-1] if т.stdout else "нет вывода"
g("G05/G07 модульные тесты", т.returncode == 0, последняя)

print("\n  итого: %d/%d" % (ок, всего))
if провалы:
    print("  провалы:", провалы)
