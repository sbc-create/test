"""Расчёт визуального соответствия по контракту visual-scoring.

Модуль — исполнимая форма контракта `contracts/visual-scoring/<версия>/`. Он не
решает, годится ли конкретный кандидат: он применяет заранее закреплённое
правило и показывает, из чего сложился каждый балл.

Почему правило вынесено в отдельный versioned контракт, а не зашито здесь:
назначить веса и порог тем же заданием, которое потом по ним аттестуется, — это
подгонка. Числа живут в JSON с неизменяемой версией, код читает их оттуда и
отказывается работать, если матрицы весов не сходятся в 100.

Три свойства, ради которых написан модуль:

* **детерминированность** — повторный запуск на тех же входных данных даёт тот
  же результат; порядок обхода задаётся сортировкой, а не порядком поступления;
* **прослеживаемость** — промежуточные значения token -> component -> ячейка ->
  surface -> overall сохраняются, округляется только отчётное значение;
* **невозможность тихого успеха** — ноль выполненных сравнений, отсутствующее
  измерение и позднее исключение не могут дать PASS.
"""
from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from decimal import ROUND_HALF_EVEN, Decimal
from pathlib import Path
from typing import Any

CONTRACT_ROOT = Path(__file__).resolve().parent.parent / "contracts" / "visual-scoring"

#: Единицы, которые не участвуют в расчёте баллов. Дайджест снимка — evidence,
#: а не измерение: усреднять его с шириной контейнера бессмысленно.
_HUNDRED = Decimal("100")
_ZERO = Decimal("0")
_CENT = Decimal("0.01")


class ContractError(RuntimeError):
    """Контракт нельзя загрузить или он внутренне противоречив."""


@dataclass(frozen=True)
class Identity:
    """Субъект действия. Сравнение независимости идёт по `id`."""

    id: str
    role: str

    def as_dict(self) -> dict[str, str]:
        return {"id": self.id, "role": self.role}


@dataclass
class ComponentScore:
    surface: str
    viewport: int
    component: str
    score: Decimal
    weight: Decimal
    tokens_compared: int
    tokens_missing: int
    excluded: bool = False
    exclusion_reason: str | None = None


@dataclass
class ScoringResult:
    overall_score: Decimal
    surface_scores: dict[str, Decimal]
    viewport_scores: dict[int, Decimal]
    component_scores: list[ComponentScore]
    hard_failures: list[dict[str, Any]]
    evidence_completeness: Decimal
    comparisons_performed: int
    certification_status: str
    blocked_reasons: list[str]
    weight_redistribution: list[dict[str, Any]] = field(default_factory=list)


# --- загрузка контракта ------------------------------------------------------


def load_contract(version: str = "1.0.0", root: Path | None = None) -> dict[str, Any]:
    """Прочитать контракт и проверить его самосогласованность.

    Отсутствующий контракт — не повод посчитать по умолчанию: без правила
    сравнивать нечем, и вызывающий обязан вернуть BLOCKED_SCORING_CONTRACT_MISSING.
    """
    base = root if root is not None else CONTRACT_ROOT
    path = base / version / "scoring-contract.json"
    if not path.is_file():
        raise FileNotFoundError(str(path))
    contract = json.loads(path.read_text(encoding="utf-8"))
    problems = check_weight_sums(contract)
    if problems:
        raise ContractError("; ".join(problems))
    return contract


def check_weight_sums(contract: dict[str, Any]) -> list[str]:
    """Каждая матрица весов обязана суммироваться в 100.

    Проверка вычислительная, а не декларативная: строка «сумма 100» в документе
    не мешает опечатке в числах.
    """
    problems: list[str] = []
    weights = contract["weights"]
    expected = weights["sum_check"]
    for matrix in ("surfaces", "viewports", "components"):
        total = sum(Decimal(str(v)) for v in weights[matrix].values())
        want = Decimal(str(expected[matrix]))
        if total != want:
            problems.append(f"матрица весов {matrix} даёт {total}, ожидалось {want}")
    return problems


# --- классификация токенов ---------------------------------------------------


def assign_component(token: dict[str, Any], contract: dict[str, Any]) -> str:
    """Определить компонент токена по контракту.

    Явное поле `component` сильнее шаблонов: пакет, который знает про себя
    больше, не обязан подгонять имена под регулярные выражения.
    """
    explicit = token.get("component")
    if explicit:
        return str(explicit)
    name = str(token.get("name", ""))
    for rule in contract["component_assignment"]["order"]:
        for pattern in rule["name_patterns"]:
            if re.match(pattern, name):
                return rule["component"]
    return "UNASSIGNED"


# --- сравнение значений ------------------------------------------------------


def score_numeric(reference: float, candidate: float, contract: dict[str, Any]) -> Decimal:
    """Линейное снижение между полосами допуска.

    Ноль в эталоне не делится: совпадение с нулём — это 100, любое иное
    значение — 0. Делить на ноль ради «процента отклонения» значит выдумать
    число, которого нет.
    """
    bands = contract["scoring_rules"]["numeric"]["bands"]
    full = Decimal(str(bands[0]["max_relative_deviation"]))
    zero_at = Decimal(str(bands[2]["from_relative_deviation"]))

    ref = Decimal(str(reference))
    cand = Decimal(str(candidate))
    if ref == 0:
        return _HUNDRED if cand == 0 else _ZERO

    relative = abs(cand - ref) / abs(ref)
    if relative <= full:
        return _HUNDRED
    if relative >= zero_at:
        return _ZERO
    return _HUNDRED * (zero_at - relative) / (zero_at - full)


def score_categorical(reference: Any, candidate: Any) -> Decimal:
    """Точное совпадение или ноль. Промежуточных состояний у enum нет."""
    return _HUNDRED if reference == candidate else _ZERO


def _srgb_to_lab(hex_color: str) -> tuple[float, float, float]:
    """sRGB -> CIELAB, осветитель D65, наблюдатель 2 градуса."""
    value = hex_color.strip().lstrip("#")
    if len(value) == 3:
        value = "".join(ch * 2 for ch in value)
    if len(value) != 6:
        raise ValueError(f"не цвет: {hex_color!r}")
    channels = [int(value[i:i + 2], 16) / 255.0 for i in (0, 2, 4)]
    linear = [c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4 for c in channels]
    r, g, b = linear
    x = 0.4124564 * r + 0.3575761 * g + 0.1804375 * b
    y = 0.2126729 * r + 0.7151522 * g + 0.0721750 * b
    z = 0.0193339 * r + 0.1191920 * g + 0.9503041 * b
    white = (0.95047, 1.00000, 1.08883)
    delta = 6.0 / 29.0

    def f(t: float) -> float:
        return t ** (1.0 / 3.0) if t > delta ** 3 else t / (3 * delta ** 2) + 4.0 / 29.0

    fx, fy, fz = (f(c / w) for c, w in zip((x, y, z), white, strict=True))
    return (116 * fy - 16, 500 * (fx - fy), 200 * (fy - fz))


def delta_e_2000(first: str, second: str) -> float:
    """CIEDE2000 между двумя цветами sRGB.

    Метрика выбрана контрактом, а не кодом: она опубликована, воспроизводима и
    её пороги можно проверить числом, а не словами «похожий оттенок».
    """
    import math

    l1, a1, b1 = _srgb_to_lab(first)
    l2, a2, b2 = _srgb_to_lab(second)

    avg_l = (l1 + l2) / 2.0
    c1 = math.hypot(a1, b1)
    c2 = math.hypot(a2, b2)
    avg_c = (c1 + c2) / 2.0
    g = 0.5 * (1 - math.sqrt(avg_c ** 7 / (avg_c ** 7 + 25 ** 7))) if avg_c > 0 else 0.0
    a1p, a2p = a1 * (1 + g), a2 * (1 + g)
    c1p, c2p = math.hypot(a1p, b1), math.hypot(a2p, b2)
    avg_cp = (c1p + c2p) / 2.0

    def hue(ap: float, bp: float) -> float:
        if ap == 0 and bp == 0:
            return 0.0
        angle = math.degrees(math.atan2(bp, ap))
        return angle + 360 if angle < 0 else angle

    h1p, h2p = hue(a1p, b1), hue(a2p, b2)
    if c1p * c2p == 0:
        dhp = 0.0
        avg_hp = h1p + h2p
    else:
        diff = h2p - h1p
        dhp = diff if abs(diff) <= 180 else (diff - 360 if diff > 180 else diff + 360)
        avg_hp = (h1p + h2p + (360 if abs(h1p - h2p) > 180 else 0)) / 2.0

    dlp = l2 - l1
    dcp = c2p - c1p
    dhp_term = 2 * math.sqrt(c1p * c2p) * math.sin(math.radians(dhp) / 2.0)

    t = (1 - 0.17 * math.cos(math.radians(avg_hp - 30))
         + 0.24 * math.cos(math.radians(2 * avg_hp))
         + 0.32 * math.cos(math.radians(3 * avg_hp + 6))
         - 0.20 * math.cos(math.radians(4 * avg_hp - 63)))
    sl = 1 + (0.015 * (avg_l - 50) ** 2) / math.sqrt(20 + (avg_l - 50) ** 2)
    sc = 1 + 0.045 * avg_cp
    sh = 1 + 0.015 * avg_cp * t
    rt = (-2 * math.sqrt(avg_cp ** 7 / (avg_cp ** 7 + 25 ** 7))
          * math.sin(math.radians(60 * math.exp(-(((avg_hp - 275) / 25) ** 2))))) if avg_cp > 0 else 0.0

    return math.sqrt(
        (dlp / sl) ** 2 + (dcp / sc) ** 2 + (dhp_term / sh) ** 2
        + rt * (dcp / sc) * (dhp_term / sh)
    )


def score_color(reference: str, candidate: str, contract: dict[str, Any]) -> Decimal:
    """Точное совпадение — 100, иначе линейное снижение по CIEDE2000."""
    rules = contract["scoring_rules"]["color"]
    if str(reference).strip().lower().lstrip("#") == str(candidate).strip().lower().lstrip("#"):
        return _HUNDRED
    bands = rules["bands"]
    full = Decimal(str(bands[0]["max_delta_e"]))
    zero_at = Decimal(str(bands[2]["from_delta_e"]))
    distance = Decimal(str(delta_e_2000(reference, candidate)))
    if distance <= full:
        return _HUNDRED
    if distance >= zero_at:
        return _ZERO
    return _HUNDRED * (zero_at - distance) / (zero_at - full)


def score_token(reference: dict[str, Any], candidate: dict[str, Any] | None,
                contract: dict[str, Any]) -> Decimal:
    """Балл одного токена. Отсутствие кандидата — ноль, а не пропуск."""
    if candidate is None:
        return Decimal(str(contract["scoring_rules"]["missing_measurement"]["score"]))
    unit = str(reference.get("unit", ""))
    rules = contract["scoring_rules"]
    if unit in rules["numeric"]["applies_to_units"]:
        return score_numeric(float(reference["value"]), float(candidate["value"]), contract)
    if unit in rules["color"]["applies_to_units"]:
        return score_color(str(reference["value"]), str(candidate["value"]), contract)
    return score_categorical(reference["value"], candidate["value"])


# --- исключения --------------------------------------------------------------


def exclusions_digest(exclusions: list[dict[str, Any]]) -> str:
    """Дайджест списка исключений в канонической форме.

    Снимается до сравнения. Любое расхождение потом означает, что исключение
    появилось задним числом.

    Список сортируется перед хешированием: перестановка тех же исключений —
    не подмена, и обвинять в ней автора пакета нельзя. Значение имеет состав,
    а не порядок строк в файле.
    """
    canonical = sorted(
        json.dumps(item, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        for item in exclusions
    )
    payload = "[" + ",".join(canonical) + "]"
    return "sha256:" + hashlib.sha256(payload.encode("utf-8")).hexdigest()


def valid_exclusion(exclusion: dict[str, Any], contract: dict[str, Any]) -> bool:
    """Исключение действительно только с причиной и provenance."""
    required = contract["exclusions"]["required_fields"]
    return all(str(exclusion.get(f, "")).strip() for f in required)


# --- агрегация ---------------------------------------------------------------


def _quantize(value: Decimal) -> Decimal:
    return value.quantize(_CENT, rounding=ROUND_HALF_EVEN)


def _redistribute(weights: dict[str, Decimal], excluded: set[str]) -> dict[str, Decimal]:
    """Вес исключённого компонента разносится пропорционально между остальными.

    Не поровну: пропорционально, иначе исключение мелкого компонента подняло бы
    вес самого лёгкого из оставшихся сильнее прочих без основания.
    """
    kept = {k: v for k, v in weights.items() if k not in excluded}
    if not kept:
        return {}
    kept_total = sum(kept.values())
    if kept_total == 0:
        return kept
    freed = sum(v for k, v in weights.items() if k in excluded)
    return {k: v + freed * v / kept_total for k, v in kept.items()}


def aggregate(component_scores: list[ComponentScore], contract: dict[str, Any]
              ) -> tuple[Decimal, dict[str, Decimal], dict[int, Decimal]]:
    """token -> component -> ячейка -> surface -> overall.

    Промежуточные значения не округляются: округление на каждом шаге копит
    ошибку, и итог перестаёт воспроизводиться.
    """
    surface_w = {k: Decimal(str(v)) for k, v in contract["weights"]["surfaces"].items()}
    viewport_w = {int(k): Decimal(str(v)) for k, v in contract["weights"]["viewports"].items()}

    cells: dict[tuple[str, int], Decimal] = {}
    grouped: dict[tuple[str, int], list[ComponentScore]] = {}
    for item in component_scores:
        grouped.setdefault((item.surface, item.viewport), []).append(item)

    for key in sorted(grouped):
        parts = sorted(grouped[key], key=lambda c: c.component)
        active = [p for p in parts if not p.excluded]
        total_weight = sum(p.weight for p in active)
        if total_weight == 0:
            cells[key] = _ZERO
            continue
        cells[key] = sum(p.score * p.weight for p in active) / total_weight

    surfaces: dict[str, Decimal] = {}
    for surface in sorted(surface_w):
        total_w = sum(viewport_w[vp] for vp in sorted(viewport_w) if (surface, vp) in cells)
        if total_w == 0:
            surfaces[surface] = _ZERO
            continue
        surfaces[surface] = sum(
            cells[(surface, vp)] * viewport_w[vp] for vp in sorted(viewport_w) if (surface, vp) in cells
        ) / total_w

    viewports: dict[int, Decimal] = {}
    for vp in sorted(viewport_w):
        total_w = sum(surface_w[s] for s in sorted(surface_w) if (s, vp) in cells)
        if total_w == 0:
            viewports[vp] = _ZERO
            continue
        viewports[vp] = sum(
            cells[(s, vp)] * surface_w[s] for s in sorted(surface_w) if (s, vp) in cells
        ) / total_w

    overall_w = sum(surface_w[s] for s in sorted(surface_w) if s in surfaces)
    overall = (sum(surfaces[s] * surface_w[s] for s in sorted(surfaces)) / overall_w
               if overall_w else _ZERO)
    return overall, surfaces, viewports


# --- вердикт -----------------------------------------------------------------


def check_independence(checker: Identity, pack_author: Identity,
                       candidate_author: Identity) -> list[dict[str, Any]]:
    """Checker не может принимать собственную работу."""
    failures = []
    if checker.id == pack_author.id:
        failures.append({"code": "CHECKER_NOT_INDEPENDENT",
                         "detail": "checker совпадает с автором reference pack"})
    if checker.id == candidate_author.id:
        failures.append({"code": "CHECKER_NOT_INDEPENDENT",
                         "detail": "checker совпадает с автором кандидата"})
    return failures


def check_compatibility(reference_env: dict[str, Any], candidate_env: dict[str, Any]
                        ) -> list[str]:
    """Расхождение среды делает сравнение бессмысленным, а не приблизительным."""
    forbidden = {"any", "latest", "*", "pending", ""}
    mismatches = []
    for key in sorted(set(reference_env) | set(candidate_env)):
        ref, cand = reference_env.get(key), candidate_env.get(key)
        if ref != cand:
            mismatches.append(f"{key}: эталон {ref!r}, кандидат {cand!r}")
        if isinstance(ref, str) and ref.strip().lower() in forbidden:
            mismatches.append(f"{key}: недоказуемое значение {ref!r} запрещено контрактом")
    return mismatches


def decide(result: ScoringResult, contract: dict[str, Any],
           compatibility_mismatches: list[str] | None = None) -> tuple[str, list[str]]:
    """Статус по правилам контракта с фиксированным приоритетом.

    Пороги сравниваются с уже округлённым отчётным значением: иначе отчёт мог бы
    показать 80.00 при вердикте «отклонено».
    """
    thresholds = contract["thresholds"]
    reasons: list[str] = []

    if result.hard_failures:
        codes = sorted({f["code"] for f in result.hard_failures})
        if "CHECKER_NOT_INDEPENDENT" in codes:
            return "BLOCKED_INDEPENDENCE_VIOLATION", [f"hard-fail: {c}" for c in codes]
        return "VISUAL_REJECTED", [f"hard-fail: {c}" for c in codes]

    if compatibility_mismatches:
        return "BLOCKED_COMPATIBILITY_MISMATCH", list(compatibility_mismatches)

    if result.comparisons_performed == 0:
        return "BLOCKED_EVIDENCE_INCOMPLETE", ["ноль выполненных сравнений не является успехом"]

    if result.evidence_completeness < Decimal(str(thresholds["evidence_completeness_required"])):
        return "BLOCKED_EVIDENCE_INCOMPLETE", [
            f"полнота evidence {result.evidence_completeness}, требуется 100"]

    if _quantize(result.overall_score) < Decimal(str(thresholds["overall_min"])):
        reasons.append(f"overall {_quantize(result.overall_score)} < {thresholds['overall_min']}")
    for surface in sorted(result.surface_scores):
        value = _quantize(result.surface_scores[surface])
        if value < Decimal(str(thresholds["surface_min"])):
            reasons.append(f"surface {surface} = {value} < {thresholds['surface_min']}")
    for viewport in sorted(result.viewport_scores):
        value = _quantize(result.viewport_scores[viewport])
        if value < Decimal(str(thresholds["viewport_aggregate_min"])):
            reasons.append(f"viewport {viewport} = {value} < {thresholds['viewport_aggregate_min']}")

    if reasons:
        return "VISUAL_REJECTED", reasons
    return "VISUAL_CERTIFIED", []


# --- единая точка входа ------------------------------------------------------


def _excluded_components(exclusions: list[dict[str, Any]], contract: dict[str, Any]
                         ) -> dict[str, str]:
    """Компоненты, исключённые заранее с причиной и provenance."""
    out: dict[str, str] = {}
    for item in exclusions:
        component = item.get("component")
        if component and valid_exclusion(item, contract):
            out[str(component)] = str(item.get("reason", ""))
    return out


def compare(*, reference_tokens: list[dict[str, Any]], candidate_tokens: list[dict[str, Any]],
            contract: dict[str, Any], checker: Identity, pack_author: Identity,
            candidate_author: Identity, reference_environment: dict[str, Any],
            candidate_environment: dict[str, Any],
            declared_exclusions: list[dict[str, Any]] | None = None,
            baseline_exclusions_digest: str | None = None,
            digest_checks: list[dict[str, Any]] | None = None,
            extra_hard_failures: list[dict[str, Any]] | None = None) -> ScoringResult:
    """Применить контракт к паре эталон/кандидат и вернуть полный результат.

    Единая точка входа существует затем, чтобы независимый checker не собирал
    расчёт заново: собранный вручную конвейер разойдётся с контрактом в мелочи,
    и разойдётся в удобную сторону.
    """
    exclusions = list(declared_exclusions or [])
    hard: list[dict[str, Any]] = list(extra_hard_failures or [])

    # Исключения проверяются до всего остального: если список изменился после
    # старта, считать по нему уже нельзя.
    if (baseline_exclusions_digest is not None
            and exclusions_digest(exclusions) != baseline_exclusions_digest):
        hard.append({"code": "UNDECLARED_EXCLUSION",
                     "detail": "состав исключений отличается от снятого до сравнения"})
    for item in exclusions:
        if not valid_exclusion(item, contract):
            hard.append({"code": "UNDECLARED_EXCLUSION",
                         "detail": f"исключение без причины или provenance: {item.get('scope')}"})

    hard.extend(check_independence(checker, pack_author, candidate_author))

    for check in sorted(digest_checks or [], key=lambda c: (c.get("scope", ""), c.get("name", ""))):
        if check.get("recorded") != check.get("observed"):
            hard.append({"code": "DIGEST_MISMATCH",
                         "detail": f"{check.get('scope')}/{check.get('name')}: "
                                   f"записано {check.get('recorded')}, наблюдается {check.get('observed')}"})

    non_scoring = set(contract["non_scoring_units"])

    def index(tokens: list[dict[str, Any]]) -> dict[tuple[str, int, str], dict[str, Any]]:
        return {(str(t["surface"]), int(t["viewport"]), str(t["name"])): t
                for t in tokens if str(t.get("unit", "")) not in non_scoring}

    ref_index = index(reference_tokens)
    cand_index = index(candidate_tokens)

    for side, idx in (("эталон", ref_index), ("кандидат", cand_index)):
        surfaces = {s for s, _, _ in idx}
        viewports = {v for _, v, _ in idx}
        for surface in contract["required_surfaces"]:
            if surface not in surfaces:
                hard.append({"code": "MISSING_SURFACE",
                             "detail": f"{side}: нет поверхности {surface}", "surface": surface})
        for viewport in contract["required_viewports"]:
            if viewport not in viewports:
                hard.append({"code": "MISSING_VIEWPORT",
                             "detail": f"{side}: нет ширины {viewport}", "viewport": viewport})

    provenance_fields = contract["inputs"]["token"]["provenance_fields"]
    for side, idx in (("эталон", ref_index), ("кандидат", cand_index)):
        for key in sorted(idx):
            token = idx[key]
            if not all(str(token.get(f, "")).strip() for f in provenance_fields):
                hard.append({"code": "MEASUREMENT_WITHOUT_PROVENANCE",
                             "detail": f"{side}: {key[0]}@{key[1]}/{key[2]}",
                             "surface": key[0], "viewport": key[1]})

    excluded = _excluded_components(exclusions, contract)
    weights = {k: Decimal(str(v)) for k, v in contract["weights"]["components"].items()}

    buckets: dict[tuple[str, int, str], list[Decimal]] = {}
    missing: dict[tuple[str, int, str], int] = {}
    expected = 0
    present = 0
    comparisons = 0

    for key in sorted(ref_index):
        surface, viewport, _ = key
        token = ref_index[key]
        component = assign_component(token, contract)
        if component == "UNASSIGNED":
            # Токен, который правило не относит ни к одному компоненту, нельзя
            # ни посчитать, ни тихо выбросить: он снижает полноту evidence.
            expected += 1
            continue
        if component in excluded:
            continue
        expected += 1
        candidate = cand_index.get(key)
        buckets.setdefault((surface, viewport, component), []).append(
            score_token(token, candidate, contract))
        if candidate is None:
            missing[(surface, viewport, component)] = missing.get((surface, viewport, component), 0) + 1
        else:
            present += 1
            comparisons += 1

    component_scores: list[ComponentScore] = []
    for surface in contract["required_surfaces"]:
        for viewport in contract["required_viewports"]:
            for component in sorted(weights):
                cell = (surface, viewport, component)
                if component in excluded:
                    component_scores.append(ComponentScore(
                        surface, viewport, component, _ZERO, weights[component], 0, 0,
                        excluded=True, exclusion_reason=excluded[component]))
                    continue
                scores = buckets.get(cell, [])
                if not scores:
                    # Компонент без единого эталонного токена и без объявленного
                    # исключения не перераспределяется и не обнуляется молча.
                    expected += 1
                    component_scores.append(ComponentScore(
                        surface, viewport, component, _ZERO, weights[component], 0, 1))
                    continue
                component_scores.append(ComponentScore(
                    surface, viewport, component,
                    sum(scores) / Decimal(len(scores)), weights[component],
                    len(scores) - missing.get(cell, 0), missing.get(cell, 0)))

    overall, surfaces, viewports = aggregate(component_scores, contract)
    completeness = (_HUNDRED * Decimal(present) / Decimal(expected)) if expected else _ZERO

    redistribution: list[dict[str, Any]] = []
    if excluded:
        after = _redistribute(weights, set(excluded))
        for component in sorted(after):
            redistribution.append({"component": component,
                                   "from_weight": float(weights[component]),
                                   "to_weight": float(after[component])})

    result = ScoringResult(
        overall_score=overall, surface_scores=surfaces, viewport_scores=viewports,
        component_scores=component_scores, hard_failures=hard,
        evidence_completeness=completeness, comparisons_performed=comparisons,
        certification_status="", blocked_reasons=[], weight_redistribution=redistribution)

    mismatches = check_compatibility(reference_environment, candidate_environment)
    result.certification_status, result.blocked_reasons = decide(result, contract, mismatches)
    return result
