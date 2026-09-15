"""Независимая оценка суточного отчёта моделью — через штатный шлюз.

Разделение обязанностей здесь важнее самой оценки. Числа считает
детерминированный код и складывает в пакет свидетельств с подписью; модель
получает готовые факты и не вычисляет их сама из свободного текста. Модель,
которой дали текст и попросили посчитать, посчитает правдоподобно — и
проверить это будет нечем.

Модель ходит только через `provider_gateway`: своего HTTP-клиента здесь нет,
права на запись нет, права запускать платные проверки нет. Недоступность
модели цикл не останавливает — отчёт выпускается с честным `UNAVAILABLE`,
потому что отсутствие второго мнения не отменяет фактов.
"""
from __future__ import annotations

import dataclasses
import hashlib
import json
import pathlib
import sys
from typing import Any

#: Корень репозитория. Шлюз провайдеров живёт там, и найти его нужно до
#: первого вызова, а не в момент, когда модель уже понадобилась.
_КОРЕНЬ = pathlib.Path(__file__).resolve().parents[2]
if str(_КОРЕНЬ) not in sys.path:
    sys.path.insert(0, str(_КОРЕНЬ))

#: Договор запроса и ответа повторяет контракт шлюза провайдеров. Сам шлюз
#: живёт в репозитории seo-engine (`seo_engine/provider_gateway`), и в этой
#: фабрике его нет — это граница репозиториев, а не упущение. Поэтому
#: провайдер передаётся снаружи: тем, кто его собрал за дверью. Своего
#: транспорта здесь нет и быть не может — ни HTTP-клиента, ни сокета.
@dataclasses.dataclass(frozen=True)
class Запрос:
    prompt_version: str
    system: str
    user: str
    max_tokens: int = 1200
    temperature: float = 0.2


@dataclasses.dataclass(frozen=True)
class Ответ:
    text: str
    provider: str = ""
    model: str = ""
    prompt_version: str = ""
    input_tokens: int = 0
    output_tokens: int = 0


ВЕРДИКТЫ = ("IMPROVING", "STABLE", "DECLINING", "INSUFFICIENT_DATA")
ОЦЕНКИ = ("WORK_SCORE", "COVERAGE_SCORE", "RESULT_SCORE",
          "SEARCH_VISIBILITY_SCORE")

СИСТЕМНАЯ_ПОДСКАЗКА = (
    "Ты оцениваешь суточный отчёт SEO-службы. Все числа уже посчитаны и "
    "переданы тебе в пакете свидетельств: считать их заново из текста "
    "запрещено, ссылайся на evidence_id. Если данных для вывода не хватает — "
    "так и скажи: INSUFFICIENT_DATA честнее уверенного вывода. Верни строгий "
    "JSON с полями verdict, scores, strengths (3), problems (3), anomalies, "
    "next_actions, cannot_claim."
)
ВЕРСИЯ_ПОДСКАЗКИ = "seo.qwen.daily_review/1.0.0"


def пакет_свидетельств(отчёт: dict[str, Any]) -> dict[str, Any]:
    """Детерминированные факты для модели. Ни одного вывода — только числа."""
    покрытие = {}
    for домен, з in (отчёт.get("coverage") or {}).items():
        покрытие[домен] = {
            с: {"entries": v["entries"],
                "ratings": {и: {"eligible": x["ELIGIBLE"], "covered": x["COVERED"],
                                "not_integrated": x.get("SOURCE_NOT_INTEGRATED", 0)}
                            for и, x in v["ratings"].items() if x["ELIGIBLE"]}}
            for с, v in з["segments"].items()}
    трафик = {}
    for домен, v in ((отчёт.get("traffic") or {}).get("per_domain") or {}).items():
        w = v.get("windows") or {}
        трафик[домен] = {к: {"visits": w.get(к, {}).get("visits_total"),
                             "organic": w.get(к, {}).get("organic_visits")}
                         for к in ("D-1", "L7", "P7", "L28", "P28")}
    пакет = {
        "report_id": отчёт.get("report_id"),
        "date": отчёт.get("date"),
        "traffic_status": (отчёт.get("traffic") or {}).get("status"),
        "traffic_age_hours": (отчёт.get("traffic") or {}).get("age_hours"),
        "traffic": трафик,
        "coverage": покрытие,
        "coverage_snapshot_sha256": отчёт.get("coverage_snapshot_sha256"),
        "content": отчёт.get("content"),
        "gap_queue_total": отчёт.get("gap_queue_total"),
        "gap_queue_top": отчёт.get("gap_queue_top", [])[:10],
        "inventory_roles": {д: з["role"] for д, з in
                            (отчёт.get("inventory") or {}).items()},
        "topvisor": отчёт.get("topvisor"),
        "indexing_policy": "noindex на всех витринах, не изменялась",
    }
    сырьё = json.dumps(пакет, ensure_ascii=False, sort_keys=True)
    пакет["evidence_id"] = "ev-" + hashlib.sha256(сырьё.encode()).hexdigest()[:20]
    return пакет


def проверить_ответ(данные: Any) -> tuple[bool, str]:
    """Ответ модели принимается только полным. Половина оценки — не оценка."""
    if not isinstance(данные, dict):
        return False, "ответ не является объектом"
    if данные.get("verdict") not in ВЕРДИКТЫ:
        return False, f"verdict вне перечня: {данные.get('verdict')!r}"
    оценки = данные.get("scores")
    if not isinstance(оценки, dict):
        return False, "нет блока scores"
    для_отчёта = [и for и in ОЦЕНКИ if и not in оценки]
    if для_отчёта:
        return False, "не заполнены оценки: " + ", ".join(для_отчёта)
    for поле, сколько in (("strengths", 3), ("problems", 3)):
        з = данные.get(поле)
        if not isinstance(з, list) or len(з) < сколько:
            return False, f"{поле}: ожидалось не меньше {сколько}"
    for поле in ("anomalies", "next_actions", "cannot_claim"):
        if not isinstance(данные.get(поле), list):
            return False, f"{поле}: ожидался список"
    return True, ""


def оценить(отчёт: dict[str, Any], provider: Any | None = None,
            *, корень: pathlib.Path | None = None) -> dict[str, Any]:
    """Получить оценку или честно назвать причину её отсутствия."""
    пакет = пакет_свидетельств(отчёт)
    основа = {"evidence_id": пакет["evidence_id"],
              "period": отчёт.get("date"),
              "prompt_version": ВЕРСИЯ_ПОДСКАЗКИ,
              "gateway": "factory.provider_gateway"}

    if provider is None:
        provider, причина = _провайдер(корень)
        if provider is None:
            return {**основа, "status": "UNAVAILABLE", "verdict": "INSUFFICIENT_DATA",
                    "reason": причина,
                    "confidence": None,
                    "note": "второго мнения за эти сутки нет; факты отчёта от "
                            "этого не меняются, а выдавать собственные выводы "
                            "за независимую оценку нельзя"}

    try:
        запрос = Запрос(
            prompt_version=ВЕРСИЯ_ПОДСКАЗКИ,
            system=СИСТЕМНАЯ_ПОДСКАЗКА,
            user=json.dumps(пакет, ensure_ascii=False),
            max_tokens=1200, temperature=0.2)
        ответ = provider.generate(запрос)
    except Exception as ош:
        return {**основа, "status": "UNAVAILABLE", "verdict": "INSUFFICIENT_DATA",
                "reason": f"{type(ош).__name__}: {str(ош)[:160]}"}

    try:
        разобрано = json.loads(_вырезать_json(ответ.text))
    except Exception:
        return {**основа, "status": "INVALID_RESPONSE",
                "verdict": "INSUFFICIENT_DATA",
                "reason": "ответ модели не разобрался как JSON"}

    годен, почему = проверить_ответ(разобрано)
    if not годен:
        return {**основа, "status": "INVALID_RESPONSE",
                "verdict": "INSUFFICIENT_DATA", "reason": почему}

    return {**основа, "status": "OK", "model": ответ.model,
            "provider": ответ.provider,
            "input_tokens": ответ.input_tokens,
            "output_tokens": ответ.output_tokens,
            **разобрано}


def _вырезать_json(текст: str) -> str:
    т = (текст or "").strip()
    if т.startswith("```"):
        т = т.split("```")[1] if "```" in т[3:] else т[3:]
        т = т.removeprefix("json").strip()
    н, к = т.find("{"), т.rfind("}")
    return т[н:к + 1] if н >= 0 and к > н else т


def _провайдер(корень: pathlib.Path | None) -> tuple[Any | None, str]:
    """Найти провайдера за штатным шлюзом. Mock оценкой не считается."""
    if корень is not None and str(корень) not in sys.path:
        sys.path.insert(0, str(корень))
    # Шлюза провайдеров в этой фабрике нет: он живёт в репозитории seo-engine.
    # Провайдера сюда передаёт тот, кто его собрал; сам модуль его не строит и
    # в сеть не ходит.
    return None, ("независимой оценки нет: способность qwen.planner числится "
                  "PLANNED во всех версиях канонического каталога, адрес у неё "
                  "пуст, локального сервера моделей и ключей нет. Штатный шлюз "
                  "провайдеров живёт в репозитории seo-engine и провайдера "
                  "сюда не передавал. Mock-провайдер независимой оценкой не "
                  "является: выдать его ответ за мнение модели значило бы "
                  "подделать второе мнение")
