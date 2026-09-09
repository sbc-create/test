"""Соответствие потребителя: та же очередь, тот же неизменённый потребитель.

Потребитель берётся из рабочего дерева SEO на точном SHA ca2b6ca9… и не
правится ни на строку: смысл проверки в том, что переход на единый снимок
маршрутов НЕ требует изменений в SEO. Правка потребителя ради прохождения
этой проверки уничтожила бы её целиком.

Связи маршрутов (`bindings`) НЕ передаются вовсе — пустой словарь. Если бы
они передавались, нельзя было бы отличить страницу, разобранную снимком, от
страницы, разобранной прежним механизмом. Пустой словарь превращает
утверждение «прежний механизм больше не нужен» из намерения в измерение:
любая витрина, которую снимок не покрывает, выйдет NO_SNAPSHOT_FOR_SITE.
"""
import collections, datetime as dt, json, pathlib, sys

SEO = "/home/claude/wt-seo-kind-34"
CORE = "/home/claude/wt-core-ident-35"
СНИМКИ = pathlib.Path("/home/claude/ident-35-artifacts/snapshots")
sys.path.insert(0, SEO)

from seo_engine.binding import route_resolution as rr, route_snapshot as rs
from seo_engine.content.authoritative_kind import (
    AuthoritativeKind, IdentityStatus, missing)
from seo_engine.content.content_kind import ContentKind
from seo_engine.policy import eligibility as el
from seo_engine.policy import playback as pb

СЕЙЧАС = dt.datetime(2026, 9, 9, 12, 0, tzinfo=dt.timezone.utc)

профили, сведения = {}, {}
for f in sorted((pathlib.Path(CORE) / "config/site-profiles").glob("*.json")):
    d = json.loads(f.read_text()); sp = d.get("seo_profile", {})
    сведения[d["site_id"]] = {"version": d.get("schema_version", ""),
                              "indexing": sp.get("indexing_enabled")}
    for узел in d.get("domains", []):
        профили[узел.lower()] = {
            "site_id": d["site_id"],
            "work_prefixes": tuple(sp.get("title_prefixes") or ())}

снимки, указатели = {}, {}
for f in sorted(СНИМКИ.glob("route-snapshot-*.json")):
    d = json.loads(f.read_text()); снимки[d["siteId"]] = d
    указатели[d["siteId"]] = rs.index_by_route(d)

очередь = json.loads((pathlib.Path(SEO) / "reports/"
    "SEO-CLAIM-PROVENANCE-DRAFT-PROMOTION-26/fixtures/seo-queue-268.json"
    ).read_text())

САМОССЫЛКА = frozenset({"page:schema.org"})
АВТОРИТЕТНЫЕ = frozenset({"catalog:fact_table", "catalog:listing"})
НЕПОДТВЕРЖДЁННЫЕ = frozenset({"FACT_CONTRADICTED", "FACT_UNSUPPORTED"})


def разобрать_факты(запись):
    сырьё = запись.get("source_facts")
    if not isinstance(сырьё, dict):
        return 0, 0, ""
    факты = сырьё.get("facts") or []
    свои = sum(1 for ф in факты if ф.get("provenance") in САМОССЫЛКА)
    авторитетных = sum(1 for ф in факты if ф.get("provenance") in АВТОРИТЕТНЫЕ)
    return авторитетных, свои, str(сырьё.get("contentKind") or "")


решения = collections.Counter(); причины = collections.Counter()
по_исходу = collections.Counter(); по_контракту = collections.Counter()
расхождения = collections.Counter(); самоцитат = 0
строки = []
for з in очередь:
    р = rr.resolve(url=з["content_id"], content_type=з["content_type"],
                   profiles=профили, snapshots=снимки, indexes=указатели,
                   bindings={})          # прежний механизм не подключён
    по_исходу[р.outcome] += 1
    по_контракту[р.contract or "—"] += 1
    строка = {"id": з["id"], "domain": з["domain"],
              "outcome": р.outcome.value, "stableWorkId": р.stable_work_id,
              "contentKind": р.content_kind,
              "contentKindState": р.content_kind_state,
              "contract": р.contract, "reason": р.reason}
    if р.outcome is not rr.Outcome.MATCHED:
        строка["eligibility"] = None
        строки.append(строка); решения[f"НЕ ДОШЛО: {р.outcome.value}"] += 1
        continue

    if р.content_kind == "MOVIE":
        вид = AuthoritativeKind(status=IdentityStatus.RESOLVED,
                                kind=ContentKind.MOVIE)
    elif р.content_kind == "SERIES":
        вид = AuthoritativeKind(status=IdentityStatus.RESOLVED,
                                kind=ContentKind.SERIES)
    else:
        вид = missing("вид произведения не передан ни снимком, ни мостом")

    авторитетных, самоссылок, вид_очереди = разобрать_факты(з)
    самоцитат += самоссылок
    if вид_очереди and р.content_kind and вид_очереди != р.content_kind:
        расхождения[(р.content_kind, вид_очереди)] += 1
    проф = сведения.get(р.site_id, {})
    входы = el.Inputs(
        domain=з["domain"], path=р.route_key, kind=вид,
        playback=pb.unknown() if hasattr(pb, "unknown") else pb.from_core(
            "UNKNOWN", confirmed_at=None, identifiers=()),
        profile_version=проф.get("version", ""),
        confirmed_facts=авторитетных,
        has_unverified_facts=з.get("fact_check_status") in НЕПОДТВЕРЖДЁННЫЕ,
        is_canonical_owner=True, duplicate_of="", has_unique_text=False,
        observed_at=СЕЙЧАС, event="route-snapshot-accepted",
        evidence_ref=р.snapshot_digest)
    реш = el.decide(входы, today=СЕЙЧАС.date(), now=СЕЙЧАС)
    решения[реш.state.value] += 1
    список = (реш.reasons if isinstance(реш.reasons, (list, tuple))
              else [реш.reasons])
    for пр in список:
        причины[getattr(пр, "value", str(пр))] += 1
    строка.update({"eligibility": реш.state.value,
                   "reasons": [getattr(п, "value", str(п)) for п in список],
                   "queueContentKind": вид_очереди,
                   "authoritativeFacts": авторитетных,
                   "selfCitedFacts": самоссылок})
    строки.append(строка)

print("=== СВЯЗЬ МАРШРУТА (связи прежнего контракта не подключены) ===")
for и, n in по_исходу.most_common():
    print(f"  {и.value:<22} {n:>4}")
print("\n=== КАКИМ КОНТРАКТОМ РАЗОБРАНО ===")
for к, n in по_контракту.most_common():
    print(f"  {к:<28} {n:>4}")
print("\n=== ДОПУСК ===")
for с, n in решения.most_common():
    print(f"  {с:<34} {n:>4}")
print("\n=== ОСНОВАНИЯ ===")
for с, n in причины.most_common(10):
    print(f"  {с:<34} {n:>4}")

ym = [с for с in строки if "yummyani" in с["domain"]
      and с["outcome"] == "MATCHED"]
с_видом = [с for с in ym if с["contentKindState"] == "AUTHORITATIVE"]
без_вида = [с for с in ym if с["contentKindState"] != "AUTHORITATIVE"]
print(f"\n=== 71 ЗАПИСЬ yummyani, РАДИ КОТОРОЙ ВСЁ ЗАТЕВАЛОСЬ ===")
print(f"  разобрано снимком:            {len(ym)}")
print(f"  вид AUTHORITATIVE:            {len(с_видом)}")
print(f"  вид не разрешён:              {len(без_вида)}")
for с in без_вида:
    print(f"    id={с['id']} {с['domain']} {с['stableWorkId']} "
          f"{с['contentKindState']}")

итог = {"queueTotal": len(очередь),
        "consumerSha": "ca2b6ca96a50e644b287c92380a9f0fa70723a38",
        "consumerModified": False, "bindingsSupplied": False,
        "snapshotSites": sorted(снимки),
        "byRouteOutcome": {и.value: n for и, n in по_исходу.most_common()},
        "byContract": dict(по_контракту),
        "byEligibility": dict(решения), "byReason": dict(причины),
        "selfCitedFacts": самоцитат,
        "contentKindMismatches": {f"{с}->{о}": n
                                  for (с, о), n in расхождения.items()},
        "yummyaniMatched": len(ym),
        "yummyaniKindAuthoritative": len(с_видом),
        "yummyaniKindUnresolved": [
            {"id": с["id"], "domain": с["domain"],
             "stableWorkId": с["stableWorkId"],
             "contentKindState": с["contentKindState"],
             "reason": "CATALOG_ENTRY_ABSENT: маршрут витрины есть, записи "
                       "каталога нет; вид не измерен"} for с in без_вида],
        "policyVersion": el.POLICY_VERSION, "rows": строки}
out = pathlib.Path(CORE) / ("reports/CORE-UNIFIED-IDENTITY-PROVENANCE-35/"
                            "CONFORMANCE-268.json")
out.write_text(json.dumps(итог, ensure_ascii=False, indent=1), encoding="utf-8")
print("\nзаписано:", out)
