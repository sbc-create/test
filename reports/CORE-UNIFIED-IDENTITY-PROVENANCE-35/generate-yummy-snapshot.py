"""Снимок маршрутов `core-route-snapshot` для витрин yummyani.

Адрес берётся из таблицы `PublicTitleRoute` самой витрины, вид произведения —
из кэша каталога тем же решателем, каким он берётся для Lords. Ни одного
живого запроса: обе стороны читаются из снятых ранее файлов.

Идентификатор, у которого есть маршрут, но нет записи каталога, из снимка НЕ
выбрасывается. Витрина такую страницу публикует, тождество у неё известно, и
молчание снимка потребитель прочёл бы как «страницы нет» — то есть как ложь.
Она входит в снимок с видом UNKNOWN/MISSING: адрес знаем, произведение знаем,
вид не знаем.
"""
import datetime as dt, hashlib, json, pathlib, subprocess, sys

КОРЕНЬ = "/home/claude/wt-core-ident-35"
sys.path.insert(0, КОРЕНЬ)
from factory.site_engine import route_snapshot as rs
from factory.site_engine.adapters.yummy_seo_binding import snapshot_route_of

МАРШРУТЫ = pathlib.Path("/srv/site-factory/repo/var/yummyani/routes")
КАТАЛОГ = pathlib.Path("/srv/site-factory/repo/var/lords/lords/"
                       "catalog-cache/lords-01.json")
ВЫХОД = pathlib.Path("/home/claude/ident-35-artifacts/snapshots")
ВЫХОД.mkdir(parents=True, exist_ok=True)

SHA = subprocess.run(["git", "rev-parse", "HEAD"], cwd=КОРЕНЬ,
                     capture_output=True, text=True).stdout.strip()

#: Узел витрины отдельно от её идентификатора: `yummyani-site` — имя витрины,
#: `yummyani.site` — узел. В `canonicalUrl` обязан стоять узел.
УЗЛЫ = {"yummyani-site": "yummyani.site",
        "yummyani-org": "yummyani.org",
        "yummyani-biz": "yummyani.biz"}

ПРОИСХОЖДЕНИЕ_АДРЕСА = "showcase-route-table:PublicTitleRoute"


def отпечаток(данные) -> str:
    return hashlib.blake2b(
        json.dumps(данные, ensure_ascii=False, sort_keys=True,
                   separators=(",", ":")).encode(), digest_size=16).hexdigest()


сырой_каталог = json.loads(КАТАЛОГ.read_text(encoding="utf-8"))
каталог = {str(з["external_id"]): з for з in сырой_каталог["items"]}
метка_каталога = сырой_каталог["mark"]
словарь = rs.load_tag_vocabulary(КОРЕНЬ)
наблюдение = dt.datetime.now(dt.timezone.utc)

манифест = {
    "contract": rs.SNAPSHOT_SCHEMA,
    "producerSha": SHA,
    "producerBranch": "claude/core-unified-identity-provenance-35",
    "kindTaxonomy": rs.KIND_TAXONOMY,
    "routeProvenance": ПРОИСХОЖДЕНИЕ_АДРЕСА,
    "catalogMark": метка_каталога,
    "catalogFile": str(КАТАЛОГ),
    "catalogEntries": len(каталог),
    "liveRequests": 0,
    "snapshots": {},
}

for витрина, узел in УЗЛЫ.items():
    выгрузка = json.loads((МАРШРУТЫ / f"{витрина}.json").read_text("utf-8"))
    все_маршруты = выгрузка["items"]
    снято = выгрузка["fetchedAt"]
    канонические = [м for м in все_маршруты if м.get("canonical")]
    псевдонимы = [м for м in все_маршруты if not м.get("canonical")]

    записи, без_каталога = [], []
    for м in канонические:
        идентификатор = str(м["providerTitleId"])
        запись = каталог.get(идентификатор)
        if запись is not None:
            записи.append(запись)
        else:
            # Только идентификатор из таблицы витрины. Ни одного поля,
            # которого мы не знаем: пустой вид честнее выдуманного.
            записи.append({"external_id": идентификатор})
            без_каталога.append(идентификатор)

    источник = отпечаток({"routes": канонические, "catalog": записи})
    снимок = rs.build(
        записи, site_id=витрина,
        route_of=snapshot_route_of(канонические),
        observed_at=наблюдение, producer_sha=SHA, source_digest=источник,
        generation_reason="full-rebuild", content_kind_of=rs.catalog_kind,
        tag_vocabulary=словарь, source_observed_at=снято,
        route_provenance=ПРОИСХОЖДЕНИЕ_АДРЕСА, canonical_host=узел)

    д = снимок.as_dict()
    путь = ВЫХОД / f"route-snapshot-{витрина}.json"
    путь.write_text(json.dumps(д, ensure_ascii=False), encoding="utf-8")

    виды: dict[str, int] = {}
    состояния: dict[str, int] = {}
    for з in д["records"]:
        виды[з["contentKind"]] = виды.get(з["contentKind"], 0) + 1
        состояния[з["contentKindState"]] = состояния.get(
            з["contentKindState"], 0) + 1

    манифест["snapshots"][витрина] = {
        "file": путь.name, "canonicalHost": узел,
        "routeRows": len(все_маршруты),
        "canonicalRoutes": len(канонические),
        "nonCanonicalAliases": [
            {"slug": м["slug"], "stableWorkId": м["providerTitleId"],
             "reason": "NON_CANONICAL_ALIAS: второй адрес того же "
                       "произведения; снимок объявляет канонический"}
            for м in псевдонимы],
        "routedWithoutCatalogEntry": {
            "count": len(без_каталога),
            "reason": "CATALOG_ENTRY_ABSENT: витрина публикует маршрут, а "
                      "записи в кэше каталога нет; вид не измерен, не ноль",
            "stableWorkIds": sorted(без_каталога)},
        "recordCount": д["recordCount"],
        "collisionCount": д["collisionCount"],
        "rejectedCount": len(д.get("rejected") or []),
        "completeness": д["completeness"],
        "byContentKind": виды, "byContentKindState": состояния,
        "isAnimationTrue": sum(1 for з in д["records"]
                               if з["isAnimation"] is True),
        "contentFormSet": sum(1 for з in д["records"] if з["contentForm"]),
        "digest": д["digest"], "envelopeDigest": д["envelopeDigest"],
        "sourceDigest": источник, "sourceObservedAt": снято,
        "sha256": hashlib.sha256(путь.read_bytes()).hexdigest(),
    }
    print(f"{витрина}: записей {д['recordCount']}, столкновений "
          f"{д['collisionCount']}, отклонено {len(д.get('rejected') or [])}, "
          f"виды {виды}, состояния {состояния}, без каталога "
          f"{len(без_каталога)}, псевдонимов {len(псевдонимы)}")

(ВЫХОД / "MANIFEST.json").write_text(
    json.dumps(манифест, ensure_ascii=False, indent=1), encoding="utf-8")
print("производитель:", SHA)
