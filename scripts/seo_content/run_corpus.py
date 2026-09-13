#!/usr/bin/env python3
"""Прогон корпуса через контур качества и сводка исходов.

    python3 scripts/seo_content/run_corpus.py \
        --corpus tests/seo_content/fixtures/golden.json \
        --out artifacts/evidence/fleet-seo-004/golden-run.json

Хранилище эфемерное и создаётся под прогон. Общий Changeset Store не
открывается ни на чтение состояния, ни на запись: у контура своя база, и это
проверяется отдельно.
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys
import tempfile
from collections import Counter

КОРЕНЬ = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(КОРЕНЬ))

from factory.seo_content import identity as ID          # noqa: E402
from factory.seo_content import store as ST             # noqa: E402
from factory.seo_content.dedup import (CorpusEntry,     # noqa: E402
                                       NearDuplicateDetector, corpus_patterns)
from factory.seo_content.draft import ClaimVerdict, GateStatus  # noqa: E402
from factory.seo_content.pipeline import (ContentPipeline,      # noqa: E402
                                          SiteContext)


def маршрут(сырой: dict) -> ID.Route:
    return ID.Route(
        url=сырой["url"], resolved_entity_id=сырой.get("resolved_entity_id"),
        url_number=сырой.get("url_number"),
        numbering_scheme=сырой.get("numbering_scheme"),
        season_url_number=сырой.get("season_url_number"),
        listing_truncated_at=сырой.get("listing_truncated_at"),
        canonical=сырой.get("canonical"),
        breadcrumbs=tuple(сырой.get("breadcrumbs") or ()))


def витрина(сырой: dict) -> SiteContext:
    return SiteContext(
        site_id=сырой["site_id"], site_url=сырой["site_url"],
        own_angle=сырой.get("own_angle"),
        sibling_sites=tuple(сырой.get("sibling_sites") or ()),
        same_catalog=bool(сырой.get("same_catalog")))


def прогон(случаи: list[dict], *, база: pathlib.Path,
           корпус_дублей: list[CorpusEntry] | None = None) -> dict:
    соед = ST.открыть(база)
    детектор = NearDuplicateDetector(корпус_дублей or [])
    конвейер = ContentPipeline(detector=детектор)

    исходы: Counter = Counter()
    причины: Counter = Counter()
    вердикты: Counter = Counter()
    записи: list[dict] = []
    тела: list[str] = []
    имена_тел: list[tuple[str, ...]] = []
    длины: list[int] = []
    # Два набора счётчиков. Общий описывает весь прогон, включая враждебные
    # случаи, ошибки в которых — ожидаемый результат. Второй считает только
    # то, что контур ПРИНЯЛ: ворота задания относятся именно к нему, иначе
    # «ноль опровергнутых утверждений» означал бы, что проверять было нечего.
    счёт = {"contradicted": 0, "unsupported_material": 0,
            "player_false": 0, "identity_errors": 0, "number_errors": 0,
            "language_critical": 0, "cliches": 0, "grammar": 0,
            "structured_errors": 0, "canonical_conflicts": 0,
            "visible_mismatches": 0, "fake_review_markup": 0,
            "exact_duplicates": 0, "normalized_duplicates": 0,
            "cross_site_copies": 0, "unresolved_near_duplicates": 0,
            "keyword_stuffing": 0, "injection_detected": 0,
            "injection_escaped": 0, "notes_emitted": 0, "notes_rejected": 0,
            "faq_emitted": 0}
    принято = {k: 0 for k in ("contradicted", "unsupported_material",
        "player_false", "identity_errors", "number_errors",
        "language_critical", "cliches", "structured_errors",
        "canonical_conflicts", "visible_mismatches", "fake_review_markup",
        "unresolved_near_duplicates", "keyword_stuffing",
        "exact_duplicates", "normalized_duplicates", "cross_site_copies",
        # Побег инъекции в ПРИНЯТЫЙ черновик. Обнаружение в источнике сюда не
        # входит: подозрительное название остаётся названием, и считать его
        # побегом значило бы записать в успех то, чего не случилось.
        "injection_escaped")}
    баллы: list[float] = []

    for случай in случаи:
        р = конвейер.run_event(
            случай["event"], site=витрина(случай["site"]),
            route=маршрут(случай["route"]), соед=соед,
            visible_breadcrumbs=tuple(случай["route"].get("breadcrumbs") or ()),
            canonical_sitemap=случай["route"].get("canonical"),
            video_present=(случай["event"].get("video_present", False)))
        ч = р.draft
        исходы[ч.quality_gate_status.value] += 1
        for причина in ч.rejection_reasons:
            причины[причина.split(":", 1)[0]] += 1
        for c in ч.claim_map:
            вердикты[c.verdict.value] += 1
        счёт["contradicted"] += len(р.outcome.claims.contradicted)
        счёт["unsupported_material"] += len(р.outcome.claims.unsupported_material)
        счёт["player_false"] += len(р.outcome.claims.player_false)
        if not р.outcome.identity.ok:
            счёт["identity_errors"] += 1
            if р.outcome.identity.code in (
                    ID.IdentityCode.URL_NUMBER_MISMATCH,
                    ID.IdentityCode.SEASON_NUMBER_MISMATCH,
                    ID.IdentityCode.EPISODE_BEYOND_ACTUAL,
                    ID.IdentityCode.EPISODE_NOT_REACHABLE):
                счёт["number_errors"] += 1
        счёт["language_critical"] += len(р.outcome.language.critical)
        счёт["cliches"] += len(р.outcome.language.cliches)
        счёт["grammar"] += len(р.outcome.language.grammar)
        счёт["keyword_stuffing"] += sum(
            1 for i in р.outcome.language.issues
            if i.code == "KEYWORD_STUFFING")
        if р.structured is not None:
            счёт["structured_errors"] += len(р.structured.errors)
            счёт["canonical_conflicts"] += р.structured.canonical_conflicts
            счёт["visible_mismatches"] += р.structured.visible_mismatches
            счёт["fake_review_markup"] += р.structured.fake_review_markup
        u = р.outcome.uniqueness
        счёт["exact_duplicates"] += u.exact_duplicates
        счёт["normalized_duplicates"] += u.normalized_duplicates
        счёт["cross_site_copies"] += u.cross_site_template_copies
        счёт["unresolved_near_duplicates"] += (
            u.review_required if ч.quality_gate_status is GateStatus.PASSED
            else 0)
        if р.outcome.injection.detected:
            счёт["injection_detected"] += 1
        if any(п.startswith("PROMPT_INJECTION_ESCAPED")
               for п in ч.rejection_reasons):
            счёт["injection_escaped"] += 1
        if ч.quality_gate_status is GateStatus.PASSED:
            принято["contradicted"] += len(р.outcome.claims.contradicted)
            принято["unsupported_material"] += len(
                р.outcome.claims.unsupported_material)
            принято["player_false"] += len(р.outcome.claims.player_false)
            принято["identity_errors"] += 0 if р.outcome.identity.ok else 1
            принято["number_errors"] += 0
            принято["language_critical"] += len(р.outcome.language.critical)
            принято["cliches"] += len(р.outcome.language.cliches)
            принято["keyword_stuffing"] += sum(
                1 for i in р.outcome.language.issues
                if i.code == "KEYWORD_STUFFING")
            if р.structured is not None:
                принято["structured_errors"] += len(р.structured.errors)
                принято["canonical_conflicts"] += р.structured.canonical_conflicts
                принято["visible_mismatches"] += р.structured.visible_mismatches
                принято["fake_review_markup"] += р.structured.fake_review_markup
            принято["unresolved_near_duplicates"] += u.review_required
            принято["exact_duplicates"] += u.exact_duplicates
            принято["normalized_duplicates"] += u.normalized_duplicates
            принято["cross_site_copies"] += u.cross_site_template_copies
            принято["injection_escaped"] += sum(
                1 for п in ч.rejection_reasons
                if п.startswith("PROMPT_INJECTION_ESCAPED"))
        счёт["notes_emitted"] += len(ч.editorial_notes)
        счёт["notes_rejected"] += len(р.outcome.notes.rejected)
        счёт["faq_emitted"] += len(ч.faq_items)
        баллы.append(р.outcome.judge.total)
        if ч.body_description:
            тела.append(ч.body_description)
            имена_тел.append(tuple(
                и for и in (ч.h1_recommendation or "").split(".") if и.strip()))
            длины.append(len(ч.body_description))
            # Принятый текст немедленно становится частью корпуса, с которым
            # сверяется следующий кандидат. Иначе пятьдесят серий с одним и
            # тем же скудным пакетом фактов прошли бы одна за другой, и
            # каждая была бы «уникальной» — просто потому, что сравнивать
            # было не с чем.
            if ч.quality_gate_status is GateStatus.PASSED:
                имена = [ч.h1_recommendation or "", ч.entity_id]
                детектор.add(CorpusEntry(
                    entry_id=f"run-{ч.entity_id}", site_id=ч.site_id,
                    entity_type=ч.entity_type, entity_id=ч.entity_id,
                    text=ч.body_description, kind="approved",
                    names=tuple(и for и in имена if и)))

        записи.append({
            "case_id": случай["case_id"], "kind": случай["kind"],
            "tags": случай["tags"], "status": ч.quality_gate_status.value,
            "reasons": list(ч.rejection_reasons),
            "warnings": list(ч.warnings),
            "blind_score": р.outcome.judge.total,
            "judge_critical": р.outcome.judge.critical,
            "identity": р.outcome.identity.to_dict(),
            "draft_id": р.draft_id, "created": р.created,
            "body_len": len(ч.body_description or ""),
            "meta_title_len": len(ч.meta_title or ""),
            "meta_description_len": len(ч.meta_description or ""),
            "notes": [n.text for n in ч.editorial_notes],
            "notes_rejected": р.outcome.notes.rejected,
            "expect": случай.get("expect", {}),
            "texts": {"meta_title": ч.meta_title,
                      "meta_description": ч.meta_description,
                      "h1": ч.h1_recommendation,
                      "body": ч.body_description},
        })

    # Сверка с ожиданиями. Считается здесь, а не в тесте, чтобы отчёт и
    # проверка опирались на одно и то же число.
    расхождения: list[dict] = []
    дубль_допущен = 0
    for з in записи:
        о = з.get("expect") or {}
        причины_ = з["reasons"]
        только_дубль = bool(причины_) and all(
            п.startswith("DUPLICATE") for п in причины_)
        if о.get("allow_duplicate_rejection") and только_дубль:
            дубль_допущен += 1
        elif о.get("status_in") and з["status"] not in о["status_in"]:
            расхождения.append({"case_id": з["case_id"], "got": з["status"],
                                "want": о["status_in"],
                                "reasons": причины_})
        свойства = []
        if о.get("no_contradicted") and any(
                п.startswith("CONTRADICTED") for п in причины_):
            свойства.append("no_contradicted")
        if о.get("no_unsupported_material") and any(
                п.startswith("UNSUPPORTED_MATERIAL") for п in причины_):
            свойства.append("no_unsupported_material")
        if о.get("identity_ok") and not з["identity"]["ok"]:
            свойства.append("identity_ok")
        if свойства:
            расхождения.append({"case_id": з["case_id"],
                                "violated": свойства, "reasons": причины_})

    образцы = corpus_patterns(тела, имена_тел)
    состояние = ST.счётчики(соед)
    соед.close()
    return {
        "cases": len(случаи), "statuses": dict(исходы),
        "reason_codes": dict(причины), "claim_verdicts": dict(вердикты),
        "counters": счёт, "accepted_counters": принято,
        "store": состояние,
        "corpus_patterns": образцы.to_dict(),
        "expectations": {"mismatches": len(расхождения),
                         "template_collisions_allowed": дубль_допущен,
                         "detail": расхождения},
        "blind_scores": {
            "average": round(sum(баллы) / len(баллы), 2) if баллы else 0.0,
            "lowest": round(min(баллы), 2) if баллы else 0.0,
            "highest": round(max(баллы), 2) if баллы else 0.0},
        "body_length": {
            "min": min(длины) if длины else 0, "max": max(длины) if длины else 0,
            "average": round(sum(длины) / len(длины)) if длины else 0,
            "within_700_1400": sum(1 for д in длины if 700 <= д <= 1400)},
        "budget": конвейер.budget.to_dict(),
        "writer": {"mode": конвейер.writer.mode,
                   "model_version": конвейер.writer.model_version,
                   "live_calls": конвейер.writer.live_calls,
                   "model_downloads": конвейер.writer.model_downloads,
                   "calls": конвейер.writer.calls},
        "records": записи,
    }


def главное(аргв=None) -> int:
    р = argparse.ArgumentParser(description=__doc__)
    р.add_argument("--corpus", required=True)
    р.add_argument("--out", required=True)
    р.add_argument("--db", default=None,
                   help="путь к эфемерной базе; по умолчанию — временный файл")
    а = р.parse_args(аргв)

    данные = json.loads(pathlib.Path(а.corpus).read_text("utf-8"))
    случаи = данные["cases"]
    база = pathlib.Path(а.db) if а.db else \
        pathlib.Path(tempfile.mkdtemp()) / "seo-drafts.sqlite3"
    итог = прогон(случаи, база=база)
    итог["corpus"] = а.corpus
    итог["db"] = str(база)
    путь = pathlib.Path(а.out)
    путь.parent.mkdir(parents=True, exist_ok=True)
    путь.write_text(json.dumps(итог, ensure_ascii=False, indent=1),
                    encoding="utf-8")
    краткое = {k: v for k, v in итог.items() if k != "records"}
    print(json.dumps(краткое, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(главное())
