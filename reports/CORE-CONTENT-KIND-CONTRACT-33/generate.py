"""Сборка снимков на новом контракте — в изолированный каталог артефактов."""
import datetime as dt, hashlib, json, pathlib, subprocess, sys
sys.path.insert(0, "/home/claude/wt-core-kind-33")
from factory.lords.live_catalog import slugify
from factory.site_engine import route_snapshot as rs

КЭШ = pathlib.Path("/home/claude/wt-core-kind-33/var/lords/lords/catalog-cache")
ВЫХОД = pathlib.Path("/home/claude/core-kind-33-artifacts")
ВЫХОД.mkdir(parents=True, exist_ok=True)
SHA = subprocess.run(["git", "rev-parse", "HEAD"], cwd="/home/claude/wt-core-kind-33",
                     capture_output=True, text=True).stdout.strip()


def адрес(name, external_id):
    return f"/title/{slugify(name) or external_id.lower()}/"


манифест = {"contract": rs.SNAPSHOT_SCHEMA, "producerSha": SHA,
            "producerBranch": "claude/core-content-kind-contract-33",
            "kindTaxonomy": rs.KIND_TAXONOMY, "snapshots": {}}
for сайт in ("lords-01", "lords-02", "lords-03"):
    сырьё = json.loads((КЭШ / f"{сайт}.json").read_text())
    записи, метка = сырьё["items"], сырьё["mark"]
    отпечаток = hashlib.blake2b(
        json.dumps(записи, ensure_ascii=False, sort_keys=True,
                   separators=(",", ":")).encode(), digest_size=16).hexdigest()
    снимок = rs.build(записи, site_id=сайт, route_of=адрес,
                      observed_at=dt.datetime.now(dt.timezone.utc),
                      producer_sha=SHA, source_digest=отпечаток,
                      generation_reason="full-rebuild",
                      content_kind_of=rs.catalog_kind,
                      tag_vocabulary=rs.load_tag_vocabulary('/home/claude/wt-core-kind-33'),
                      source_observed_at=метка)
    д = снимок.as_dict()
    путь = ВЫХОД / f"route-snapshot-{сайт}.json"
    путь.write_text(json.dumps(д, ensure_ascii=False), encoding="utf-8")
    манифест["snapshots"][сайт] = {
        "file": путь.name, "recordCount": д["recordCount"],
        "collisionCount": д["collisionCount"], "completeness": д["completeness"],
        "digest": д["digest"], "envelopeDigest": д["envelopeDigest"],
        "sourceDigest": отпечаток, "sourceObservedAt": метка,
        "sha256": hashlib.sha256(путь.read_bytes()).hexdigest(),
    }
    виды = {}
    for з in д["records"]:
        виды[з["contentKind"]] = виды.get(з["contentKind"], 0) + 1
    анимация = sum(1 for з in д["records"] if з["isAnimation"] is True)
    формы = sum(1 for з in д["records"] if з["contentForm"])
    print(f"{сайт}: записей {д['recordCount']}, столкновений {д['collisionCount']}, "
          f"виды {виды}, анимация {анимация}, форма {формы}")

(ВЫХОД / "MANIFEST.json").write_text(
    json.dumps(манифест, ensure_ascii=False, indent=1), encoding="utf-8")
print("производитель:", SHA)
