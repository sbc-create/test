"""Ворота качества: единственное место, где выносится решение о черновике.

Порядок проверок здесь не косметический. Сначала исходы, описывающие
состояние данных — «фактов не хватает», «источники расходятся». Только потом
исходы, описывающие брак текста. Разница существенна: `NEEDS_FACTS` — это
исправная работа контура, а `REJECTED` — сообщение о том, что текст был
написан и оказался негодным. Слить их в один код значило бы скрыть, что
данных нет, за видимостью неудачной генерации.

Критическая ошибка не компенсируется баллом. Порог судьи и фактические
ворота — разные вещи, и ни один балл не отменяет перепутанную серию.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Iterable, Mapping, Sequence

from . import editorial as ED
from . import identity as ID
from . import injection
from .claims import ClaimExtractor, ClaimReport
from .draft import (Claim, ClaimVerdict, FaqItem, GateStatus, SEOContentDraft,
                    idempotency_key)
from .dedup import NearDuplicateDetector, UniquenessReport, doorway_risk
from .factpack import SEOFactPack
from .judge import BlindJudge, JudgeScore
from .language import LanguageReport, LanguageValidator
from .structured_data import StructuredDataReport


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@dataclass
class GateInputs:
    """Всё, что ворота получают снаружи. Ничего не добывают сами."""

    pack: SEOFactPack
    content: Mapping[str, Any]
    route: ID.Route
    model_version: str
    prompt_version: str
    generation_parameters: Mapping[str, Any]
    detector: NearDuplicateDetector | None = None
    structured: StructuredDataReport | None = None
    corpus_note_hashes: tuple[str, ...] = ()
    site_own_angle: str | None = None
    sibling_sites: tuple[str, ...] = ()
    same_catalog: bool = False
    target_environment: str = "test"


@dataclass
class GateOutcome:
    draft: SEOContentDraft
    claims: ClaimReport
    identity: ID.IdentityReport
    language: LanguageReport
    uniqueness: UniquenessReport
    judge: JudgeScore
    notes: ED.NotesReport
    injection: injection.ОтчётОбИнъекции
    structured: StructuredDataReport | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "draft": self.draft.payload(),
            "claims": self.claims.to_dict(),
            "identity": self.identity.to_dict(),
            "language": self.language.to_dict(),
            "uniqueness": self.uniqueness.to_dict(),
            "judge": self.judge.to_dict(),
            "editorial_notes": self.notes.to_dict(),
            "injection": self.injection.to_dict(),
            "structured_data": (self.structured.to_dict()
                                if self.structured else None),
        }


def _заметки(pack: SEOFactPack, сырые: Sequence[Mapping[str, Any]], *,
             body: str | None, model_version: str, prompt_version: str,
             corpus_note_hashes: Iterable[str]) -> ED.NotesReport:
    собранные: list[ED.EditorialNote] = []
    for i, з in enumerate(сырые or ()):
        ED.reject_ugc_fields(з)
        собранные.append(ED.EditorialNote(
            note_id=f"{pack.entity_id}-note-{i + 1}", site_id=pack.site_id,
            entity_type=pack.entity_type, entity_id=pack.entity_id,
            locale=pack.locale, text=str(з.get("text") or ""),
            fact_refs=tuple(з.get("fact_refs") or ()),
            angle=str(з.get("angle") or "general"),
            model_version=model_version, prompt_version=prompt_version))
    return ED.validate_notes(
        собранные, pack=pack, body=body,
        corpus_note_hashes=corpus_note_hashes,
        allowed_spoiler=str(pack.value("/spoiler_level") or "NONE"))


def evaluate(входы: GateInputs) -> GateOutcome:
    pack, содержимое = входы.pack, dict(входы.content)
    причины: list[str] = []
    предупреждения: list[str] = []

    инъекции = injection.scan_pack(pack)
    if инъекции.detected:
        # Подозрительное название остаётся настоящим названием: сам факт
        # находки не отклоняет пакет. Блокирует только побег в выдачу.
        предупреждения.append(
            "PROMPT_INJECTION_IN_SOURCE:"
            + ",".join(sorted({н.pattern_code for н in инъекции.findings})))

    личность = ID.resolve(pack, входы.route)
    номер = личность.display_number
    сезон = pack.value("/season_number")

    # --- тексты ----------------------------------------------------------
    тексты = {k: v for k, v in (
        ("meta_title", содержимое.get("meta_title")),
        ("meta_description", содержимое.get("meta_description")),
        ("h1_recommendation", содержимое.get("h1_recommendation")),
        ("body_description", содержимое.get("body_description")),
    ) if v}

    отчёт_заметок = _заметки(
        pack, содержимое.get("editorial_notes") or (),
        body=содержимое.get("body_description"),
        model_version=входы.model_version, prompt_version=входы.prompt_version,
        corpus_note_hashes=входы.corpus_note_hashes)
    for i, н in enumerate(отчёт_заметок.notes):
        тексты[f"editorial_note[{i}]"] = н.text
    faq = tuple(FaqItem(question=str(f.get("question")),
                        answer=str(f.get("answer")),
                        fact_refs=tuple(f.get("fact_refs") or ()))
                for f in (содержимое.get("faq_items") or ()))
    for i, f in enumerate(faq):
        тексты[f"faq[{i}].answer"] = f.answer

    # --- проверки ---------------------------------------------------------
    утверждения = ClaimExtractor(pack).extract(тексты)
    название = pack.value("/canonical_title_ru")
    язык = LanguageValidator(
        canonical_title=название,
        allowed_titles=[название] + list(pack.value("/alternative_titles") or ()),
    ).validate(содержимое.get("body_description") or "")

    уникальность = UniquenessReport()
    if входы.detector is not None and содержимое.get("body_description"):
        имена = [название] + list(pack.value("/alternative_titles") or ())
        уникальность = входы.detector.check(
            содержимое["body_description"], site_id=pack.site_id,
            entity_id=pack.entity_id, names=[и for и in имена if и],
            franchise_id=pack.value("/franchise_id"),
            allowed_titles=[и for и in имена if и])
    уровень, пояснение = doorway_risk(
        site_id=pack.site_id, own_angle=входы.site_own_angle,
        sibling_sites=list(входы.sibling_sites), same_catalog=входы.same_catalog)
    уникальность.doorway_risk, уникальность.doorway_detail = уровень, пояснение

    судья = BlindJudge(uniqueness_report=уникальность,
                       identity_report=личность).score(pack, тексты)

    # --- решение ----------------------------------------------------------
    статус = GateStatus.PASSED
    исход_автора = содержимое.get("outcome")

    # Личность проверяется ВСЕГДА и раньше всего остального. Страница, ведущая
    # не к той сущности, сломана независимо от того, решили мы писать о ней
    # текст или нет: «фактов не хватает» на сломанном маршруте скрыло бы
    # поломку за исправным на вид исходом.
    конфликты = pack.conflicts()
    if not личность.ok:
        статус = GateStatus.REJECTED
        код = (ID.EPISODE_IDENTITY_CONFLICT
               if pack.entity_type == "episode" else "ENTITY_IDENTITY_ERROR")
        причины.append(f"{код}:{личность.code}")
        причины.extend(f"IDENTITY_DETAIL:{п}" for п in личность.problems)
    elif конфликты:
        статус = GateStatus.FACT_CONFLICT
        причины.append("FACT_CONFLICT:" + ",".join(конфликты))
    elif исход_автора == "NEEDS_FACTS":
        статус = GateStatus.NEEDS_FACTS
        причины.append("NEEDS_FACTS:"
                       + ",".join(содержимое.get("missing") or ()))
    elif исход_автора == "EPISODE_IDENTITY_CONFLICT":
        статус = GateStatus.REJECTED
        причины.append("EPISODE_IDENTITY_CONFLICT:"
                       + str(содержимое.get("detail") or ""))
    else:
        побеги = injection.escaped_draft(
            {**содержимое, "editorial_notes":
                [{"text": н.text} for н in отчёт_заметок.notes]},
            инъекции, pack)
        if побеги:
            статус = GateStatus.REJECTED
            причины.append("PROMPT_INJECTION_ESCAPED:" + ",".join(побеги))

        отставшие = ID.stale_number_scan(
            {**тексты,
             "canonical": входы.route.canonical or "",
             "breadcrumbs": " / ".join(входы.route.breadcrumbs),
             "url": входы.route.url},
            episode_number=номер if pack.entity_type == "episode" else None,
            season_number=int(сезон) if сезон is not None
            and pack.entity_type in ("season", "episode") else None)
        if отставшие:
            статус = GateStatus.REJECTED
            причины.append("STALE_NUMBER:" + "; ".join(отставшие))

        if утверждения.contradicted:
            статус = GateStatus.REJECTED
            причины.append(
                "CONTRADICTED_CLAIMS:"
                + "; ".join(f"{c.claim_type}={c.detail}"
                            for c in утверждения.contradicted[:5]))
        if утверждения.unsupported_material:
            статус = GateStatus.REJECTED
            причины.append(
                "UNSUPPORTED_MATERIAL_CLAIMS:"
                + "; ".join(f"{c.claim_type}:{c.text[:40]}"
                            for c in утверждения.unsupported_material[:5]))
        if утверждения.player_false:
            причины.append("PLAYER_AVAILABILITY_FALSE_CLAIM")

        if язык.critical:
            статус = GateStatus.REJECTED
            причины.append("LANGUAGE_CRITICAL:"
                           + ",".join(sorted({i.code for i in язык.critical})))

        if уникальность.blocked:
            статус = GateStatus.REJECTED
            причины.append(
                "DUPLICATE:" + ",".join(sorted({f.method for f in
                                                уникальность.findings
                                                if f.severity == "BLOCK"})))
        if входы.structured is not None and входы.structured.errors:
            статус = GateStatus.REJECTED
            причины.append("STRUCTURED_DATA:"
                           + ",".join(sorted({i.code for i in
                                              входы.structured.errors})))

        if статус is GateStatus.PASSED:
            if уровень == "HIGH":
                статус = GateStatus.NOINDEX_RECOMMENDED
                причины.append("DOORWAY_RISK:" + пояснение)
            elif уникальность.review_required:
                статус = GateStatus.REVIEW_REQUIRED
                причины.append("NEAR_DUPLICATE_REVIEW")
            elif not судья.passed:
                статус = GateStatus.REVIEW_REQUIRED
                причины.append(
                    f"BLIND_SCORE={судья.total} < {85}"
                    + (f"; critical={судья.critical}" if судья.critical else ""))

    if отчёт_заметок.rejected:
        предупреждения.append(
            "EDITORIAL_NOTES_REJECTED:"
            + ",".join(sorted({r for з in отчёт_заметок.rejected
                               for r in з["reasons"]})))

    ключ = idempotency_key(
        site_id=pack.site_id, entity_type=pack.entity_type,
        entity_id=pack.entity_id, fact_pack_sha256=pack.sha256,
        prompt_version=входы.prompt_version, locale=pack.locale)

    черновик = SEOContentDraft(
        site_id=pack.site_id, entity_type=pack.entity_type,
        entity_id=pack.entity_id, locale=pack.locale,
        fact_pack_version=pack.version, fact_pack_sha256=pack.sha256,
        model_version=входы.model_version, prompt_version=входы.prompt_version,
        generation_parameters=dict(входы.generation_parameters),
        meta_title=содержимое.get("meta_title"),
        meta_description=содержимое.get("meta_description"),
        h1_recommendation=содержимое.get("h1_recommendation"),
        body_description=содержимое.get("body_description"),
        editorial_notes=tuple(отчёт_заметок.notes), faq_items=faq,
        claim_map=tuple(утверждения.claims), warnings=tuple(предупреждения),
        quality_scores=судья.to_dict(), quality_gate_status=статус,
        rejection_reasons=tuple(причины), idempotency_key=ключ,
        created_at=utcnow(), target_environment=входы.target_environment,
        technical_recommendations=_рекомендации(pack, входы, личность))

    return GateOutcome(черновик, утверждения, личность, язык, уникальность,
                       судья, отчёт_заметок, инъекции, входы.structured)


def _рекомендации(pack: SEOFactPack, входы: GateInputs,
                  личность: ID.IdentityReport) -> dict[str, Any]:
    """Согласованный набор: H1, canonical, крошки и JSON-LD об одной сущности."""
    return {
        "h1": входы.content.get("h1_recommendation"),
        "canonical": входы.route.canonical or входы.route.url,
        "breadcrumbs": list(входы.route.breadcrumbs),
        "jsonld_type": {"title": "Movie|TVSeries", "season": "TVSeason",
                        "episode": "TVEpisode"}[pack.entity_type],
        "entity_id": pack.entity_id,
        "display_number": личность.display_number,
        "season_number": pack.value("/season_number"),
        "noindex_recommended": входы.same_catalog and not входы.site_own_angle,
    }
