"""Снимок маршрутов для витрин Lords — тем же кодом и в тот же каталог.

Отдельный файл только потому, что источник адреса другой: у Lords адрес
выводится из названия функцией движка, у yummyani объявляется таблицей
витрины. Всё остальное — тот же builder, тот же решатель вида, та же версия
контракта. Ради этого и затевалось объединение.
"""
import datetime as dt, hashlib, json, pathlib, subprocess, sys

КОРЕНЬ = "/home/claude/wt-core-ident-35"
sys.path.insert(0, КОРЕНЬ)
from factory.lords.live_catalog import slugify
from factory.site_engine import route_snapshot as rs

КЭШ = pathlib.Path("/srv/site-factory/repo/var/lords/lords/catalog-cache")
ВЫХОД = pathlib.Path("/home/claude/ident-35-artifacts/snapshots")
ВЫХОД.mkdir(parents=True, exist_ok=True)
SHA = subprocess.run(["git", "rev-parse", "HEAD"], cwd=КОРЕНЬ,
                     capture_output=True, text=True).stdout.strip()

#: Узлы витрин Lords. Как и у yummyani, идентификатор витрины узлом не
#: является, и в canonicalUrl обязан стоять узел.
УЗЛЫ = {"lords-01": "lordfilm47.space",
        "lords-02": "lordserial33.biz",
        "lords-03": "1lordserials1.online"}


def адрес(name, external_id):
    return f"/title/{slugify(name) or external_id.lower()}/"


словарь = rs.load_tag_vocabulary(КОРЕНЬ)
наблюдение = dt.datetime.now(dt.timezone.utc)
манифест = json.loads((ВЫХОД / "MANIFEST.json").read_text(encoding="utf-8"))

for витрина, узел in УЗЛЫ.items():
    сырьё = json.loads((КЭШ / f"{витрина}.json").read_text(encoding="utf-8"))
    записи, метка = сырьё["items"], сырьё["mark"]
    источник = hashlib.blake2b(
        json.dumps(записи, ensure_ascii=False, sort_keys=True,
                   separators=(",", ":")).encode(), digest_size=16).hexdigest()
    снимок = rs.build(записи, site_id=витрина, route_of=адрес,
                      observed_at=наблюдение, producer_sha=SHA,
                      source_digest=источник, generation_reason="full-rebuild",
                      content_kind_of=rs.catalog_kind, tag_vocabulary=словарь,
                      source_observed_at=метка, canonical_host=узел)
    д = снимок.as_dict()
    путь = ВЫХОД / f"route-snapshot-{витрина}.json"
    путь.write_text(json.dumps(д, ensure_ascii=False), encoding="utf-8")

    виды, состояния = {}, {}
    for з in д["records"]:
        виды[з["contentKind"]] = виды.get(з["contentKind"], 0) + 1
        состояния[з["contentKindState"]] = состояния.get(з["contentKindState"], 0) + 1
    манифест["snapshots"][витрина] = {
        "file": путь.name, "canonicalHost": узел,
        "routeProvenance": "catalog+slugify",
        "recordCount": д["recordCount"], "collisionCount": д["collisionCount"],
        "rejectedCount": len(д.get("rejected") or []),
        "completeness": д["completeness"],
        "byContentKind": виды, "byContentKindState": состояния,
        "digest": д["digest"], "envelopeDigest": д["envelopeDigest"],
        "sourceDigest": источник, "sourceObservedAt": метка,
        "sha256": hashlib.sha256(путь.read_bytes()).hexdigest()}
    print(f"{витрина}: записей {д['recordCount']}, столкновений "
          f"{д['collisionCount']}, отклонено {len(д.get('rejected') or [])}, "
          f"виды {виды}, состояния {состояния}")

(ВЫХОД / "MANIFEST.json").write_text(
    json.dumps(манифест, ensure_ascii=False, indent=1), encoding="utf-8")
print("витрин в манифесте:", len(манифест["snapshots"]))
