"""Сквозная проверка: контракт получен по HTTP, решение принимает код SEO."""
import datetime as dt, json, sys
from seo_engine.content import authoritative_kind as ak
from seo_engine.policy import eligibility as el
from seo_engine.policy import playback as pb

страница = json.load(open(sys.argv[1], encoding="utf-8"))
момент = dt.datetime.now(dt.UTC)
итог = {"BOUND": 0, "решений": {}, "отказов": []}
for b in страница["bindings"]:
    вид = ak.from_payload(b["contentIdentity"])
    код = "OK" if b["playbackReasonCode"] == "PLAYBACK_OK" else b["playbackReasonCode"]
    наблюдено = b.get("playbackObservedAt") or ""
    подтв = dt.datetime.fromisoformat(наблюдено) if наблюдено else None
    видео = pb.from_core(код, confirmed_at=подтв,
                         identifiers=tuple(b.get("externalIds") or {}))
    # Отображение состояния связи на входы политики. Без него верный контракт
    # даёт неверные решения: страница с неоднозначным маршрутом получала
    # разрешение на индекс, хотя неизвестно, чью запись она показывает.
    неоднозначен = b["bindingState"] == "ROUTE_COLLISION"
    решение = el.decide(el.Inputs(
        domain="yummyani.site", path=b["canonicalPath"], kind=вид, playback=видео,
        profile_version="yummyani-site/1.0.0",
        profile_allows_kinds=(вид.kind,) if вид.usable else (),
        confirmed_facts=6,
        is_canonical_owner=not неоднозначен,
        duplicate_of=(b["routeId"] if неоднозначен else ""),
        has_unique_text=True,
        observed_at=момент, evidence_ref="http"), today=момент.date(), now=момент)
    итог["решений"][решение.state.value] = итог["решений"].get(решение.state.value, 0) + 1
    if b["bindingState"] == "BOUND":
        итог["BOUND"] += 1
        if решение.state.value not in ("INDEXABLE_WITH_PLAYBACK",
                                       "INDEXABLE_METADATA_ONLY"):
            итог["отказов"].append({"route": b["routeId"],
                                    "state": решение.state.value})
print(json.dumps(итог, ensure_ascii=False, indent=1))
