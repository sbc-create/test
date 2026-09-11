"""Шесть последовательных циклов сверки с evidence на каждый."""
import json, pathlib, sqlite3, sys, time
sys.path.insert(0, "/srv/site-factory/registry-core")
import registry_store as rs, registry_command as rc

БД = "/srv/site-factory/registry-core/registry.sqlite3"
ОТЧЁТЫ = pathlib.Path("/srv/site-factory/registry-core/evidence")
ОТЧЁТЫ.mkdir(parents=True, exist_ok=True)

ОЖИДАЕМЫЕ = {"lordfilm47.space", "lordserial33.biz", "1lordserials1.online",
             "yummyani.biz", "yummyani.org", "yummyani.site",
             "zonafilm.space", "animedia.icu", "animedia.space"}

def манифесты() -> dict:
    итог = {}
    for sid in ("zona-01", "animedia-01", "animedia-02", "lords-02", "lords-03"):
        p = pathlib.Path(f"/srv/lords/.frontend/template-manifest-{sid}.json")
        if p.exists():
            d = json.loads(p.read_text(encoding="utf-8"))
            итог[sid] = {"build_id": d.get("build_id")}
    return итог

соед = sqlite3.connect(БД, timeout=30, isolation_level=None)
соед.row_factory = sqlite3.Row
м = манифесты()
print("манифестов для сверки:", len(м))
итоги = []
for n in range(1, 7):
    р = rc.сверка(соед, ожидаемые_домены=ОЖИДАЕМЫЕ, манифесты=м)
    путь = ОТЧЁТЫ / f"reconcile-{n}-{р['run_id'][:8]}.json"
    путь.write_text(json.dumps(р, ensure_ascii=False, indent=1), encoding="utf-8")
    итоги.append(р)
    print("  цикл %d  run_id %s  %s  версия %d  находок %d  backlog %d  %.3f с"
          % (n, р["run_id"][:8], р["verdict"], р["input_registry_version"],
             len(р["findings"]), р["metrics"]["outbox_backlog"],
             р["duration_seconds"]))
    for f in р["findings"][:3]:
        print("      ", json.dumps(f, ensure_ascii=False))
    time.sleep(1)
вердикты = [и["verdict"] for и in итоги]
print("\nвердикты:", вердикты)
print("все SUCCESS:", all(v == "SUCCESS" for v in вердикты))
