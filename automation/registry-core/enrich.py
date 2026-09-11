"""Заполнение deployment-полей исходных шести записей фактическими данными."""
import json, os, pathlib, sqlite3, sys
sys.path.insert(0, "/srv/site-factory/registry-core")
import registry_store as rs, registry_command as rc

os.environ.setdefault(rc.ТОКЕН_REF, "local-architect-token")
соед = sqlite3.connect("/srv/site-factory/registry-core/registry.sqlite3",
                       timeout=30, isolation_level=None)
соед.row_factory = sqlite3.Row
ЗАГ = {"authorization": f"Bearer {os.environ[rc.ТОКЕН_REF]}",
       "x-service-name": "service:architect"}
ФРОНТ = pathlib.Path("/srv/lords/.frontend")

def манифест(sid):
    for имя in (f"template-manifest-{sid}.json",):
        p = ФРОНТ / имя
        if p.exists():
            return json.loads(p.read_text(encoding="utf-8"))
    return None

def релиз(путь):
    p = pathlib.Path(путь)
    return p.resolve().name if p.exists() else None

# Витрины Yummy обслуживаются nova из общей проекции; их релиз — build проекции.
ИСТОЧНИК = {
    "lords-01": ("lords-01", "/srv/lords/lords-01/current"),
    "lords-02": ("lords-02", "/srv/lords/lords-02/current"),
    "lords-03": ("lords-03", "/srv/lords/lords-03/current"),
    "yummyani-site": ("yummy-site", None),
    "yummyani-org": ("yummy-org", None),
    "yummyani-biz": ("yummy-biz", None),
}
обновлено, пропущено = [], []
for sid, (ключ, путь_релиза) in ИСТОЧНИК.items():
    м = манифест(ключ)
    if not м:
        пропущено.append((sid, f"манифест template-manifest-{ключ}.json отсутствует"))
        continue
    поля = {"template_id": м.get("template_family"),
            "template_version": м.get("design_version"),
            "build_id": м.get("build_id")}
    рел = релиз(путь_релиза) if путь_релиза else None
    if рел:
        поля["release_id"] = рел
    р = rc.выполнить(соед, команда="update", site_id=sid, поля=поля,
                     заголовки=dict(ЗАГ, **{"idempotency-key": f"enrich-{sid}-1"}))
    обновлено.append((sid, поля.get("build_id"), поля.get("release_id")))

print("обновлено:", len(обновлено))
for sid, b, r in обновлено:
    print("   %-14s build=%s release=%s" % (sid, b, r))
if пропущено:
    print("не обновлено (доказательства нет, поле оставлено пустым):")
    for sid, почему in пропущено:
        print("   %-14s %s" % (sid, почему))
