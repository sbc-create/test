"""Путь независимой оценки: проверяется до того, как модель появится.

Смысл этих проверок в том, чтобы слово «недоступно» относилось к учётным
данным, а не к ненаписанному коду. Когда у способности появится адрес, здесь
не должно остаться работы — только ключ.
"""
from __future__ import annotations

import importlib.util
import json
import pathlib
import sys

import pytest

КОРЕНЬ = pathlib.Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location(
    "_qwen_review", КОРЕНЬ / "automation/host/seo_qwen_review.py")
R = importlib.util.module_from_spec(spec)
# Регистрация до исполнения обязательна: dataclass ищет свой модуль в
# sys.modules, и без записи падает на разборе аннотаций.
sys.modules["_qwen_review"] = R
spec.loader.exec_module(R)

ОТЧЁТ = {
    "report_id": "seo-daily-2026-09-15", "date": "2026-09-15",
    "coverage_snapshot_sha256": "abc123",
    "traffic": {"status": "CURRENT", "age_hours": 0.0, "per_domain": {
        "d.ru": {"windows": {"D-1": {"visits_total": 10, "organic_visits": 0},
                             "L7": {"visits_total": 70, "organic_visits": 1},
                             "P7": {"visits_total": 65, "organic_visits": 0},
                             "L28": {"visits_total": 280, "organic_visits": 2},
                             "P28": {"visits_total": 0, "organic_visits": 0}}}}},
    "coverage": {"d.ru": {"segments": {"FILMS": {
        "entries": 100, "details_available": 100, "fields": {},
        "ratings": {"imdb": {"ELIGIBLE": 90, "COVERED": 80,
                             "SOURCE_NOT_INTEGRATED": 0}}}}}},
    "content": {"published": 1, "live_verified": 1},
    "gap_queue_total": 72, "gap_queue_top": [],
    "inventory": {"d.ru": {"role": "MANAGED_PRODUCTION"}},
    "topvisor": {"daily_runs": 0},
}

ХОРОШИЙ = {
    "verdict": "STABLE",
    "scores": {"WORK_SCORE": 70, "COVERAGE_SCORE": 55,
               "RESULT_SCORE": "INSUFFICIENT_DATA",
               "SEARCH_VISIBILITY_SCORE": "NOT_MEASURED"},
    "strengths": ["а", "б", "в"], "problems": ["г", "д", "е"],
    "anomalies": [], "next_actions": ["ж"], "cannot_claim": ["з"],
}


class Дверь:
    """Заглушка провайдера. Сети за ней нет."""

    def __init__(self, текст: str):
        self.текст, self.запросы = текст, []

    def generate(self, request):
        self.запросы.append(request)
        return R.Ответ(text=self.текст, provider="stub", model="stub",
                       prompt_version=request.prompt_version,
                       input_tokens=10, output_tokens=5)


# --- пакет свидетельств ----------------------------------------------------
def test_пакет_содержит_числа_а_не_текст():
    п = R.пакет_свидетельств(ОТЧЁТ)
    assert п["traffic"]["d.ru"]["L7"]["visits"] == 70
    assert п["coverage"]["d.ru"]["FILMS"]["ratings"]["imdb"]["covered"] == 80
    assert п["evidence_id"].startswith("ev-")


def test_отпечаток_пакета_устойчив_и_различает():
    a = R.пакет_свидетельств(ОТЧЁТ)["evidence_id"]
    b = R.пакет_свидетельств(ОТЧЁТ)["evidence_id"]
    другой = dict(ОТЧЁТ, gap_queue_total=71)
    assert a == b
    assert R.пакет_свидетельств(другой)["evidence_id"] != a


def test_возраст_трафика_передаётся_модели():
    """Модель обязана знать, что число вчерашнее, иначе назовёт его сегодняшним."""
    п = R.пакет_свидетельств(dict(ОТЧЁТ, traffic={
        "status": "STALE", "age_hours": 30.0, "per_domain": {}}))
    assert п["traffic_status"] == "STALE" and п["traffic_age_hours"] == 30.0


# --- разбор и проверка ответа ----------------------------------------------
def test_полный_ответ_принимается():
    о = R.оценить(ОТЧЁТ, provider=Дверь(json.dumps(ХОРОШИЙ, ensure_ascii=False)))
    assert о["status"] == "OK" and о["verdict"] == "STABLE"
    assert о["evidence_id"].startswith("ev-")
    assert len(о["strengths"]) == 3 and len(о["problems"]) == 3


def test_ответ_в_ограждении_разбирается():
    текст = "```json\n" + json.dumps(ХОРОШИЙ) + "\n```"
    assert R.оценить(ОТЧЁТ, provider=Дверь(текст))["status"] == "OK"


@pytest.mark.parametrize("порча,почему", [
    ({"verdict": "ОТЛИЧНО"}, "verdict вне перечня"),
    ({"scores": {"WORK_SCORE": 1}}, "не заполнены оценки"),
    ({"strengths": ["а"]}, "strengths"),
    ({"problems": []}, "problems"),
    ({"anomalies": "нет"}, "anomalies"),
])
def test_неполный_ответ_не_принимается(порча, почему):
    """Половина оценки — не оценка: принять её значит выдать пробел за вывод."""
    о = R.оценить(ОТЧЁТ, provider=Дверь(json.dumps({**ХОРОШИЙ, **порча})))
    assert о["status"] == "INVALID_RESPONSE"
    assert о["verdict"] == "INSUFFICIENT_DATA"
    assert почему in о["reason"]


def test_не_json_не_принимается():
    о = R.оценить(ОТЧЁТ, provider=Дверь("в целом всё неплохо"))
    assert о["status"] == "INVALID_RESPONSE" and о["verdict"] == "INSUFFICIENT_DATA"


def test_падение_провайдера_не_роняет_цикл():
    class Падает:
        def generate(self, request): raise TimeoutError("не дождались")
    о = R.оценить(ОТЧЁТ, provider=Падает())
    assert о["status"] == "UNAVAILABLE" and о["verdict"] == "INSUFFICIENT_DATA"
    assert "TimeoutError" in о["reason"]


# --- границы ---------------------------------------------------------------
def test_модель_получает_факты_а_не_свободный_текст():
    д = Дверь(json.dumps(ХОРОШИЙ))
    R.оценить(ОТЧЁТ, provider=д)
    полезное = json.loads(д.запросы[0].user)
    assert "evidence_id" in полезное and "traffic" in полезное
    assert "Ты оцениваешь" in д.запросы[0].system
    assert "считать их заново из текста" in д.запросы[0].system


def test_своего_http_клиента_нет():
    т = (КОРЕНЬ / "automation/host/seo_qwen_review.py").read_text(encoding="utf-8")
    for запрещено in ("import httpx", "import requests", "urllib.request",
                      "socket.", "http.client"):
        assert запрещено not in т, запрещено
    assert "provider_gateway" in т


def test_mock_не_выдаётся_за_независимую_оценку():
    """Mock — поддерживаемый режим продукта, но не второе мнение."""
    провайдер, причина = R._провайдер(pathlib.Path("/srv/site-factory/repo"))
    assert провайдер is None
    assert "подделать второе мнение" in причина
    assert "PLANNED" in причина


def test_недоступность_даёт_предусмотренный_исход():
    о = R.оценить(ОТЧЁТ, корень=pathlib.Path("/srv/site-factory/repo"))
    assert о["status"] in ("UNAVAILABLE", "OK")
    assert о["verdict"] in R.ВЕРДИКТЫ
    assert о["evidence_id"].startswith("ev-")


def test_секретов_в_модуле_нет():
    т = (КОРЕНЬ / "automation/host/seo_qwen_review.py").read_text(encoding="utf-8")
    for о in ("Bearer ", "sk-", "api_key=", "y0_", "AQAA"):
        assert о not in т, о
