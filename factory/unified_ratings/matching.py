"""Сопоставление канонического тайтла с записью внешнего источника.

Порядок приоритетов задан владельцем и в коде не меняется:

1. точный внешний ID;
2. ранее подтверждённое сопоставление;
3. оригинальное название + год + тип;
4. альтернативное название + год + тип;
5. название + сезон + количество эпизодов;
6. fuzzy — только кандидат в очередь проверки.

Похожее название само по себе не связывает ничего. «Стальной алхимик» и
«Стальной алхимик: Братство» различаются одним словом и являются разными
произведениями с разными оценками; правило, которое связывает их по
близости строк, ошибается тем чаще, чем известнее франшиза.

Точный ID тоже не является безусловным основанием. Если внешний источник
по нашему MAL ID отдаёт фильм 2009 года там, где каталог знает сериал
2016-го, сходится не тайтл, а ошибка в одном из двух каталогов, и такая
связь уходит в очередь проверки со статусом ``conflict``.
"""

from __future__ import annotations

import difflib
import re
import unicodedata
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

#: Разница в годах, которую не считаем расхождением: сезон, начавшийся в
#: декабре, у одного каталога отнесён к этому году, у другого к следующему.
YEAR_TOLERANCE = 1

#: Ниже этого порога fuzzy-кандидат не предлагается даже в очередь.
FUZZY_FLOOR = 0.82

#: Порог, ниже которого сопоставление по названию не принимается никогда.
MIN_ACCEPT_CONFIDENCE = 0.95


class MatchMethod(str, Enum):
    EXACT_EXTERNAL_ID = "exact_external_id"
    CONFIRMED_MAPPING = "confirmed_mapping"
    ORIGINAL_TITLE_YEAR_KIND = "original_title_year_kind"
    ALT_TITLE_YEAR_KIND = "alt_title_year_kind"
    TITLE_SEASON_EPISODES = "title_season_episodes"
    FUZZY_CANDIDATE = "fuzzy_candidate"
    NONE = "none"


class MatchStatus(str, Enum):
    EXACT = "exact"
    REVIEWED = "reviewed"
    PENDING = "pending"
    REJECTED = "rejected"
    CONFLICT = "conflict"


class QuarantineReason(str, Enum):
    YEAR_MISMATCH = "YEAR_MISMATCH"
    MOVIE_VS_SERIES = "MOVIE_VS_SERIES"
    SEASON_MISMATCH = "SEASON_MISMATCH"
    FRANCHISE_MISMATCH = "FRANCHISE_MISMATCH"
    REMAKE = "REMAKE"
    SPECIAL_OVA_VS_MAIN = "SPECIAL_OVA_VS_MAIN"
    EXTERNAL_ID_CONFLICT = "EXTERNAL_ID_CONFLICT"
    INSUFFICIENT_CONFIDENCE = "INSUFFICIENT_CONFIDENCE"
    MULTIPLE_EQUAL_CANDIDATES = "MULTIPLE_EQUAL_CANDIDATES"


# ---------------------------------------------------------------------------
# Типы контента
# ---------------------------------------------------------------------------

_SERIES_KINDS = {"tv", "tv_short", "ona", "series", "tv_special"}
_MOVIE_KINDS = {"movie", "film"}
_SIDE_KINDS = {"ova", "oav", "special", "music"}


def kind_class(kind: str) -> str:
    """Свести обозначения источников к трём классам."""
    normalized = (kind or "").strip().lower().replace("-", "_")
    if normalized in _MOVIE_KINDS:
        return "movie"
    if normalized in _SIDE_KINDS:
        return "side"
    if normalized in _SERIES_KINDS:
        return "series"
    return "unknown"


def effective_kind_class(facts: TitleFacts) -> str:
    """Класс с учётом пометок в названии.

    Наш каталог знает только ``tv`` и ``movie``, тогда как AniList и Kitsu
    различают OVA, ONA и спецвыпуски. Сравнение одних только объявленных
    типов сделало бы «наш OVA ↔ их OVA» расхождением, а такой карантин
    срабатывает на каждом втором спецвыпуске и перестаёт что-либо значить.
    Пометка в названии — это тоже заявление каталога о типе, и здесь она
    учитывается наравне с полем.
    """
    text = " ".join(normalize_title(t) for t in facts.all_titles)
    if any(marker in text for marker in _SIDE_MARKERS):
        return "side"
    return kind_class(facts.kind)


# ---------------------------------------------------------------------------
# Нормализация названий
# ---------------------------------------------------------------------------

_PUNCT = re.compile(r"[^\w\s]", re.UNICODE)
_SPACES = re.compile(r"\s+")

_REMAKE_MARKERS = ("remake", "ремейк", "реборн", "reboot", "２０", "new edition")
_SIDE_MARKERS = ("ova", "оva", "special", "спецвыпуск", "спешл", "picture drama", "recap")


def normalize_title(value: str) -> str:
    text = unicodedata.normalize("NFKC", value or "").casefold()
    text = text.replace("ё", "е")
    text = _PUNCT.sub(" ", text)
    return _SPACES.sub(" ", text).strip()


def similarity(left: str, right: str) -> float:
    a, b = normalize_title(left), normalize_title(right)
    if not a or not b:
        return 0.0
    if a == b:
        return 1.0
    return difflib.SequenceMatcher(None, a, b).ratio()


def _season_from_title(value: str) -> int | None:
    text = normalize_title(value)
    match = re.search(r"\b(?:сезон|season)\s*(\d{1,2})\b", text)
    if match:
        return int(match.group(1))
    match = re.search(r"\b(\d{1,2})\s*(?:сезон|season)\b", text)
    if match:
        return int(match.group(1))
    # «Название 2» в конце — распространённая запись второго сезона
    match = re.search(r"\s(\d)$", text)
    if match:
        return int(match.group(1))
    return None


# ---------------------------------------------------------------------------
# Данные для сравнения
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class TitleFacts:
    """Факты о тайтле с одной стороны сравнения."""

    title_id: str
    title_ru: str = ""
    title_original: str = ""
    alt_titles: tuple[str, ...] = ()
    year: int | None = None
    kind: str = ""
    season_number: int | None = None
    episode_count: int | None = None
    external_ids: dict[str, str] = field(default_factory=dict)

    @property
    def all_titles(self) -> tuple[str, ...]:
        values = [self.title_ru, self.title_original, *self.alt_titles]
        return tuple(v for v in values if v)

    @property
    def effective_season(self) -> int | None:
        if self.season_number is not None:
            return self.season_number
        for candidate in self.all_titles:
            season = _season_from_title(candidate)
            if season is not None:
                return season
        return None


@dataclass(frozen=True)
class MatchDecision:
    status: MatchStatus
    method: MatchMethod
    confidence: float
    external_id: str = ""
    reasons: tuple[QuarantineReason, ...] = ()
    detail: str = ""
    candidates: tuple[dict[str, Any], ...] = ()

    @property
    def auto_acceptable(self) -> bool:
        return self.status is MatchStatus.EXACT

    def as_dict(self) -> dict[str, Any]:
        return {
            "status": self.status.value,
            "method": self.method.value,
            "confidence": round(self.confidence, 4),
            "external_id": self.external_id,
            "reasons": [r.value for r in self.reasons],
            "detail": self.detail,
            "candidates": list(self.candidates),
        }


# ---------------------------------------------------------------------------
# Проверка согласованности
# ---------------------------------------------------------------------------


def disagreements(ours: TitleFacts, theirs: TitleFacts) -> list[QuarantineReason]:
    """Расхождения, из-за которых связь нельзя принимать автоматически."""
    reasons: list[QuarantineReason] = []

    if (
        ours.year is not None
        and theirs.year is not None
        and abs(ours.year - theirs.year) > YEAR_TOLERANCE
    ):
        reasons.append(QuarantineReason.YEAR_MISMATCH)

    our_kind, their_kind = effective_kind_class(ours), effective_kind_class(theirs)
    if "unknown" not in (our_kind, their_kind) and our_kind != their_kind:
        if {our_kind, their_kind} == {"movie", "series"}:
            reasons.append(QuarantineReason.MOVIE_VS_SERIES)
        else:
            reasons.append(QuarantineReason.SPECIAL_OVA_VS_MAIN)

    our_season, their_season = ours.effective_season, theirs.effective_season
    if our_season is not None and their_season is not None and our_season != their_season:
        reasons.append(QuarantineReason.SEASON_MISMATCH)

    combined = " ".join(normalize_title(t) for t in (*ours.all_titles, *theirs.all_titles))
    ours_text = " ".join(normalize_title(t) for t in ours.all_titles)
    theirs_text = " ".join(normalize_title(t) for t in theirs.all_titles)
    if any(marker in combined for marker in _REMAKE_MARKERS):
        our_remake = any(m in ours_text for m in _REMAKE_MARKERS)
        their_remake = any(m in theirs_text for m in _REMAKE_MARKERS)
        if our_remake != their_remake:
            reasons.append(QuarantineReason.REMAKE)

    for space, our_value in ours.external_ids.items():
        their_value = theirs.external_ids.get(space)
        if our_value and their_value and str(our_value) != str(their_value):
            reasons.append(QuarantineReason.EXTERNAL_ID_CONFLICT)
            break

    return reasons


def best_title_similarity(ours: TitleFacts, theirs: TitleFacts) -> tuple[float, str, str]:
    best = (0.0, "", "")
    for a in ours.all_titles:
        for b in theirs.all_titles:
            score = similarity(a, b)
            if score > best[0]:
                best = (score, a, b)
    return best


# ---------------------------------------------------------------------------
# Решение
# ---------------------------------------------------------------------------


def match(
    ours: TitleFacts,
    candidates: list[TitleFacts],
    *,
    id_space: str = "",
    confirmed_external_id: str = "",
) -> MatchDecision:
    """Выбрать сопоставление или отправить его в очередь проверки."""
    if not candidates:
        return MatchDecision(
            status=MatchStatus.REJECTED,
            method=MatchMethod.NONE,
            confidence=0.0,
            detail="источник не вернул ни одного кандидата",
        )

    # 2. Ранее подтверждённое сопоставление имеет приоритет над любым
    #    пересчётом: подтверждал его человек, а не эвристика.
    if confirmed_external_id:
        for candidate in candidates:
            if candidate.title_id == confirmed_external_id:
                return MatchDecision(
                    status=MatchStatus.REVIEWED,
                    method=MatchMethod.CONFIRMED_MAPPING,
                    confidence=1.0,
                    external_id=confirmed_external_id,
                    detail="ранее подтверждённое сопоставление",
                )

    # 1. Точный внешний ID.
    our_external = ours.external_ids.get(id_space) if id_space else None
    if our_external:
        exact = [c for c in candidates if str(c.external_ids.get(id_space) or "") == str(our_external)]
        if len(exact) > 1:
            return MatchDecision(
                status=MatchStatus.CONFLICT,
                method=MatchMethod.EXACT_EXTERNAL_ID,
                confidence=0.0,
                reasons=(QuarantineReason.EXTERNAL_ID_CONFLICT,),
                detail=f"один {id_space}={our_external} указывает на {len(exact)} записей источника",
                candidates=tuple(_describe(c) for c in exact),
            )
        if exact:
            candidate = exact[0]
            problems = disagreements(ours, candidate)
            if problems:
                return MatchDecision(
                    status=MatchStatus.CONFLICT,
                    method=MatchMethod.EXACT_EXTERNAL_ID,
                    confidence=0.0,
                    external_id=candidate.title_id,
                    reasons=tuple(problems),
                    detail=(
                        f"{id_space} совпал, но факты расходятся: "
                        + ", ".join(r.value for r in problems)
                    ),
                    candidates=(_describe(candidate),),
                )
            return MatchDecision(
                status=MatchStatus.EXACT,
                method=MatchMethod.EXACT_EXTERNAL_ID,
                confidence=1.0,
                external_id=candidate.title_id,
                detail=f"{id_space}={our_external}",
            )

    # 3–5. Сопоставление по фактам. Год и тип обязательны: без них
    #      совпадение названия ничего не доказывает.
    scored: list[tuple[float, TitleFacts, MatchMethod]] = []
    for candidate in candidates:
        problems = disagreements(ours, candidate)
        if problems:
            continue
        score, ours_used, _ = best_title_similarity(ours, candidate)
        if score < FUZZY_FLOOR:
            continue
        if ours.year is None or candidate.year is None:
            # Без года остаётся только название — этого недостаточно.
            continue
        method = MatchMethod.ORIGINAL_TITLE_YEAR_KIND
        if ours.title_original and normalize_title(ours_used) != normalize_title(ours.title_original):
            method = MatchMethod.ALT_TITLE_YEAR_KIND
        if (
            ours.episode_count is not None
            and candidate.episode_count is not None
            and ours.episode_count == candidate.episode_count
            and ours.effective_season is not None
        ):
            method = MatchMethod.TITLE_SEASON_EPISODES
            score = min(1.0, score + 0.02)
        scored.append((score, candidate, method))

    if not scored:
        problems: list[QuarantineReason] = []
        for candidate in candidates:
            problems.extend(disagreements(ours, candidate))
        unique = tuple(dict.fromkeys(problems)) or (QuarantineReason.INSUFFICIENT_CONFIDENCE,)
        return MatchDecision(
            status=MatchStatus.PENDING,
            method=MatchMethod.FUZZY_CANDIDATE,
            confidence=0.0,
            reasons=unique,
            detail="ни один кандидат не прошёл проверку фактов",
            candidates=tuple(_describe(c) for c in candidates[:5]),
        )

    scored.sort(key=lambda row: row[0], reverse=True)
    top_score, top_candidate, top_method = scored[0]

    ties = [row for row in scored if abs(row[0] - top_score) < 0.01]
    if len(ties) > 1:
        return MatchDecision(
            status=MatchStatus.PENDING,
            method=MatchMethod.FUZZY_CANDIDATE,
            confidence=top_score,
            reasons=(QuarantineReason.MULTIPLE_EQUAL_CANDIDATES,),
            detail=f"{len(ties)} равноправных кандидата с близостью ≈{top_score:.3f}",
            candidates=tuple(_describe(row[1]) for row in ties[:5]),
        )

    if top_score < MIN_ACCEPT_CONFIDENCE:
        return MatchDecision(
            status=MatchStatus.PENDING,
            method=MatchMethod.FUZZY_CANDIDATE,
            confidence=top_score,
            external_id=top_candidate.title_id,
            reasons=(QuarantineReason.INSUFFICIENT_CONFIDENCE,),
            detail=f"близость {top_score:.3f} ниже порога принятия {MIN_ACCEPT_CONFIDENCE}",
            candidates=(_describe(top_candidate),),
        )

    # Совпадение фактов и почти идентичное название — но это всё ещё не
    # точный идентификатор, поэтому связь требует подтверждения человеком.
    return MatchDecision(
        status=MatchStatus.PENDING,
        method=top_method,
        confidence=top_score,
        external_id=top_candidate.title_id,
        reasons=(),
        detail=(
            f"название, год и тип сходятся (близость {top_score:.3f}), "
            "но точного внешнего идентификатора нет — нужна проверка"
        ),
        candidates=(_describe(top_candidate),),
    )


def match_by_facts(
    ours: TitleFacts, candidates: list[TitleFacts]
) -> MatchDecision:
    """Сопоставление для источника без общего идентификатора.

    Для AMD Online внешнего ключа к нашему каталогу не существует, и
    владелец разрешил принимать связь по нормализованному названию
    вместе с годом и типом. Порог здесь не «похоже», а **точное
    совпадение нормализованного названия**: fuzzy-близость 0.95 на
    франшизах срабатывает между соседними сезонами, и один такой
    автоматический приём стоит дороже сотни записей в очереди.

    Приём возможен только когда ровно один кандидат удовлетворяет всем
    условиям сразу. Два одинаково подходящих — это неоднозначность, а не
    выбор.
    """
    if not candidates:
        return MatchDecision(
            status=MatchStatus.REJECTED,
            method=MatchMethod.NONE,
            confidence=0.0,
            detail="в каталоге нет кандидатов с таким названием",
        )

    our_names = {normalize_title(t) for t in ours.all_titles if t}
    accepted: list[TitleFacts] = []
    blocked: list[QuarantineReason] = []
    for candidate in candidates:
        problems = disagreements(ours, candidate)
        if problems:
            blocked.extend(problems)
            continue
        if ours.year is None or candidate.year is None:
            blocked.append(QuarantineReason.INSUFFICIENT_CONFIDENCE)
            continue
        their_names = {normalize_title(t) for t in candidate.all_titles if t}
        if not (our_names & their_names):
            blocked.append(QuarantineReason.INSUFFICIENT_CONFIDENCE)
            continue
        accepted.append(candidate)

    if len(accepted) == 1:
        return MatchDecision(
            status=MatchStatus.REVIEWED,
            method=MatchMethod.ORIGINAL_TITLE_YEAR_KIND,
            confidence=1.0,
            external_id=accepted[0].title_id,
            detail="точное совпадение нормализованного названия, года и типа",
            candidates=(_describe(accepted[0]),),
        )
    if len(accepted) > 1:
        return MatchDecision(
            status=MatchStatus.PENDING,
            method=MatchMethod.FUZZY_CANDIDATE,
            confidence=0.0,
            reasons=(QuarantineReason.MULTIPLE_EQUAL_CANDIDATES,),
            detail=f"{len(accepted)} кандидата с тем же названием, годом и типом",
            candidates=tuple(_describe(c) for c in accepted[:5]),
        )
    return MatchDecision(
        status=MatchStatus.PENDING,
        method=MatchMethod.FUZZY_CANDIDATE,
        confidence=0.0,
        reasons=tuple(dict.fromkeys(blocked)) or (QuarantineReason.INSUFFICIENT_CONFIDENCE,),
        detail="ни один кандидат не подтверждён названием, годом и типом одновременно",
        candidates=tuple(_describe(c) for c in candidates[:5]),
    )


def _describe(facts: TitleFacts) -> dict[str, Any]:
    return {
        "external_id": facts.title_id,
        "title_ru": facts.title_ru,
        "title_original": facts.title_original,
        "year": facts.year,
        "kind": facts.kind,
        "season": facts.effective_season,
        "episodes": facts.episode_count,
    }
