"""Blind Content Judge: оценка текста без доступа к рассуждениям автора.

Слепота здесь буквальная. Судья получает три вещи: пакет фактов, готовый
текст и рубрику. Он не видит, какие поля автор считал использованными, какой
промпт применялся и что автор о своём тексте думает. Иначе оценивалось бы
намерение, а читателю достаётся результат.

Судья детерминированный, и это записано прямо: живой модели в контуре нет,
и выдавать оценку счётчика за суждение модели или человека нельзя. Балл
судьи — не доказательство качества; он лишь ещё одно измерение рядом с
фактическими воротами, и общий PASS на нём не строится.

Рубрика — сто баллов, проходной — 85. Критическая ошибка не компенсируется
средним баллом: она обнуляет свою часть целиком и помечает результат
отдельным флагом.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, Sequence

from .claims import ClaimExtractor
from .draft import ClaimVerdict
from .factpack import SEOFactPack
from .language import LanguageValidator

РУБРИКА = {
    "factual_accuracy": 35,
    "entity_match": 20,
    "naturalness": 15,
    "usefulness": 10,
    "uniqueness": 10,
    "no_spam": 5,
    "meta_fields": 5,
}
ПРОХОДНОЙ_БАЛЛ = 85

#: Ориентиры длины. Не KPI: отклонение стоит баллов полезности, но само по
#: себе не проваливает текст, если фактов действительно мало.
ОРИЕНТИРЫ = {
    "meta_title": (45, 65),
    "meta_description": (130, 170),
    "body_title": (700, 1400),
    "body_season": (350, 800),
}


@dataclass
class JudgeScore:
    scores: dict[str, float] = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)
    critical: list[str] = field(default_factory=list)

    @property
    def total(self) -> float:
        return round(sum(self.scores.values()), 2)

    @property
    def passed(self) -> bool:
        """Проходной балл И отсутствие критической ошибки.

        Два условия, а не одно: 96 баллов при перепутанной серии — это не
        «почти отлично», это не та серия.
        """
        return self.total >= ПРОХОДНОЙ_БАЛЛ and not self.critical

    def to_dict(self) -> dict[str, Any]:
        return {"scores": {k: round(v, 2) for k, v in self.scores.items()},
                "total": self.total, "pass_mark": ПРОХОДНОЙ_БАЛЛ,
                "passed": self.passed, "critical": list(self.critical),
                "notes": list(self.notes),
                "judge_type": "DETERMINISTIC",
                "judge_disclaimer": (
                    "оценка вычислена детерминированным судьёй; это не "
                    "суждение модели и не человеческая проверка")}


class BlindJudge:
    """Оценщик. Видит пакет, текст и рубрику — и ничего больше."""

    def __init__(self, *, uniqueness_report=None, identity_report=None):
        self.uniqueness = uniqueness_report
        self.identity = identity_report

    def score(self, pack: SEOFactPack, тексты: Mapping[str, str], *,
              entity_type: str | None = None) -> JudgeScore:
        итог = JudgeScore()
        сущность = entity_type or pack.entity_type
        тело = тексты.get("body_description") or ""

        # --- фактическая точность (35) ---------------------------------
        отчёт = ClaimExtractor(pack).extract(dict(тексты))
        проверяемые = [c for c in отчёт.claims
                       if c.verdict is not ClaimVerdict.NON_FACTUAL_STYLE]
        опровергнутые = отчёт.contradicted
        недоказанные = отчёт.unsupported_material
        if опровергнутые:
            итог.scores["factual_accuracy"] = 0.0
            итог.critical.append(
                f"CONTRADICTED_CLAIMS={len(опровергнутые)}: "
                + "; ".join(c.detail for c in опровергнутые[:3]))
        elif not проверяемые:
            # Текст без единого проверяемого утверждения безупречен по
            # фактам ровно потому, что ничего не сообщает. Это не отличный
            # результат, и полным баллом он быть не может.
            итог.scores["factual_accuracy"] = РУБРИКА["factual_accuracy"] * 0.4
            итог.notes.append("ни одного проверяемого утверждения")
        else:
            доля = 1 - len(недоказанные) / max(1, len(проверяемые))
            итог.scores["factual_accuracy"] = round(
                РУБРИКА["factual_accuracy"] * max(0.0, доля), 2)
            if недоказанные:
                итог.notes.append(
                    f"недоказанных существенных утверждений: "
                    f"{len(недоказанные)}")

        # --- соответствие сущности (20) --------------------------------
        балл = float(РУБРИКА["entity_match"])
        название = pack.value("/canonical_title_ru")
        if название and название.lower() not in " ".join(тексты.values()).lower():
            балл -= 10
            итог.notes.append("каноническое название в тексте не встречается")
        if self.identity is not None and not self.identity.ok:
            балл = 0.0
            итог.critical.append(f"ENTITY_IDENTITY:{self.identity.code}")
        номерные = [c for c in отчёт.claims
                    if c.claim_type in ("episode_number", "season_number",
                                        "episode_count", "season_count")
                    and c.verdict is ClaimVerdict.CONTRADICTED]
        if номерные:
            балл = 0.0
            итог.critical.append(
                f"SEASON_EPISODE_NUMBER_ERRORS={len(номерные)}")
        итог.scores["entity_match"] = max(0.0, балл)

        # --- естественность (15) ---------------------------------------
        язык = LanguageValidator(
            canonical_title=название,
            allowed_titles=[название] + list(pack.value("/alternative_titles")
                                             or [])).validate(тело)
        критические = [i for i in язык.issues if i.severity == "CRITICAL"
                       and i.code != "KEYWORD_STUFFING"]
        ошибки = [i for i in язык.issues if i.severity == "ERROR"]
        предупреждения = [i for i in язык.issues if i.severity == "WARNING"]
        if критические:
            итог.scores["naturalness"] = 0.0
            итог.critical.append(
                "LANGUAGE_CRITICAL=" + ",".join(sorted({i.code for i in критические})))
        else:
            штраф = 2.0 * len(ошибки) + 0.5 * len(предупреждения)
            итог.scores["naturalness"] = max(
                0.0, РУБРИКА["naturalness"] - штраф)

        # --- полезность (10) -------------------------------------------
        итог.scores["usefulness"] = self._полезность(pack, тексты, сущность,
                                                     отчёт, итог)

        # --- уникальность (10) -----------------------------------------
        if self.uniqueness is None:
            итог.scores["uniqueness"] = 0.0
            итог.notes.append("уникальность не измерялась — баллы не начислены")
        elif self.uniqueness.blocked:
            итог.scores["uniqueness"] = 0.0
            итог.critical.append("DUPLICATE_BLOCKED")
        elif self.uniqueness.review_required:
            итог.scores["uniqueness"] = РУБРИКА["uniqueness"] * 0.5
            итог.notes.append("близкие тексты требуют разбора")
        else:
            итог.scores["uniqueness"] = float(РУБРИКА["uniqueness"])

        # --- отсутствие спама (5) --------------------------------------
        спам = [i for i in язык.issues
                if i.code in ("KEYWORD_STUFFING", "ADVERTISING_TONE",
                              "FORBIDDEN_CLICHE")]
        итог.scores["no_spam"] = 0.0 if спам else float(РУБРИКА["no_spam"])
        if any(i.code == "KEYWORD_STUFFING" for i in спам):
            итог.critical.append("KEYWORD_STUFFING")

        # --- meta-поля (5) ----------------------------------------------
        итог.scores["meta_fields"] = self._мета(тексты, итог)
        return итог

    # --- части --------------------------------------------------------

    def _полезность(self, pack: SEOFactPack, тексты: Mapping[str, str],
                    сущность: str, отчёт, итог: JudgeScore) -> float:
        """Сообщает ли текст то, ради чего человек его открыл."""
        тело = тексты.get("body_description") or ""
        балл = 0.0
        обязательные = {
            "title": ("/canonical_title_ru", "/premise_subject",
                      "/premise_conflict", "/genres"),
            "season": ("/canonical_title_ru", "/season_number"),
            "episode": ("/canonical_title_ru",),
        }[сущность]
        покрыто = 0
        for путь in обязательные:
            значение = pack.value(путь)
            if значение is None:
                continue
            куски = значение if isinstance(значение, (list, tuple)) else [значение]
            if any(str(к).split(",")[0][:24].lower() in тело.lower()
                   for к in куски):
                покрыто += 1
        балл += РУБРИКА["usefulness"] * 0.7 * (покрыто / max(1, len(обязательные)))

        ключ = {"title": "body_title", "season": "body_season"}.get(сущность)
        if ключ:
            низ, верх = ОРИЕНТИРЫ[ключ]
            if низ <= len(тело) <= верх:
                балл += РУБРИКА["usefulness"] * 0.3
            else:
                итог.notes.append(
                    f"длина тела {len(тело)} вне ориентира {низ}–{верх} "
                    f"(ориентир, не порог)")
                балл += РУБРИКА["usefulness"] * 0.15
        else:
            балл += РУБРИКА["usefulness"] * 0.3
        return round(min(балл, float(РУБРИКА["usefulness"])), 2)

    def _мета(self, тексты: Mapping[str, str], итог: JudgeScore) -> float:
        балл = float(РУБРИКА["meta_fields"])
        for поле, ключ in (("meta_title", "meta_title"),
                           ("meta_description", "meta_description")):
            значение = тексты.get(поле)
            if not значение:
                балл -= 2.5
                итог.notes.append(f"{поле} отсутствует")
                continue
            низ, верх = ОРИЕНТИРЫ[ключ]
            if not (низ <= len(значение) <= верх):
                балл -= 1.0
                итог.notes.append(
                    f"{поле}: {len(значение)} символов вне ориентира "
                    f"{низ}–{верх}")
        return max(0.0, балл)
