"""REQ-TRACING: путь запроса восстанавливается по идентификатору.

Отрезки, которые невозможно собрать в цепочку, — это данные, которых никто не
читает. Поэтому проверяется не наличие записи, а способность ответить на
вопрос «что произошло с запросом X» для успеха, отказа по праву, конфликта,
повтора и застрявшей заявки.
"""
import json
from pathlib import Path

import pytest

from factory import locks
from factory.paths import PATHS
from factory.site_engine.api import tracing
from factory.site_engine.api.control import ControlApi
from factory.site_engine.api.tracing import (
    TRACEPARENT,
    Tracer,
    new_context,
    parse_traceparent,
    path_template,
)

REPO = Path(__file__).resolve().parents[2]
SITE = "trace-site"
ADMIN = "tr-admin"
READER = "tr-reader"
ENV = {
    "SITE_ENGINE_CONTROL_WRITES": "1",
    "SITE_ENGINE_CONTROL_TOKENS": (
        f"{ADMIN}=read,jobs:write,config:write,cache:write,audit:read|{READER}=read"
    ),
}
AUTH = {"Authorization": f"Bearer {ADMIN}"}


@pytest.fixture
def sandbox(tmp_path, monkeypatch):
    monkeypatch.setattr(PATHS, "root", tmp_path)
    profiles = tmp_path / "config" / "site-profiles"
    profiles.mkdir(parents=True)
    образец = json.loads(
        (REPO / "config" / "site-profiles" / "lords-01.json").read_text(encoding="utf-8"))
    образец.update({"site_id": SITE, "domains": ["tr.test"], "canonical_host": "tr.test"})
    (profiles / f"{SITE}.json").write_text(json.dumps(образец, ensure_ascii=False),
                                           encoding="utf-8")
    for sub in ("queue/inbox", "queue/processing", "queue/done", "queue/failed",
                "queue/quarantine", "var/locks", "var/audit", "var/state"):
        (tmp_path / sub).mkdir(parents=True, exist_ok=True)
    return tmp_path


@pytest.fixture
def api(sandbox):
    # Выборка полная: проверяется содержание следа, а не работа выборки.
    return ControlApi(root=sandbox, env=ENV,
                      tracer=Tracer(sandbox / "var" / "state", read_sample=1.0))


def след_из(ответ):
    ctx = parse_traceparent(ответ.body.get("traceparent"))
    assert ctx is not None, "в ответе нет годного traceparent"
    return ctx.trace_id


# ---- формат контекста -------------------------------------------------------

def test_негодный_traceparent_не_отвергает_запрос():
    """Чужая ошибка в разметке — не повод отказать в обслуживании."""
    assert parse_traceparent("мусор") is None
    assert parse_traceparent("") is None
    assert parse_traceparent(None) is None


def test_нулевые_идентификаторы_не_принимаются():
    assert parse_traceparent("00-" + "0" * 32 + "-" + "1" * 16 + "-01") is None
    assert parse_traceparent("00-" + "1" * 32 + "-" + "0" * 16 + "-01") is None


def test_контекст_продолжается_а_не_начинается_заново(api):
    родитель = new_context()
    r = api.handle("GET", "/api/v1/metrics",
                   headers={**AUTH, TRACEPARENT: родитель.header()})
    assert след_из(r) == родитель.trace_id, "след оборвался на границе службы"


def test_шаблон_пути_вместо_идентификаторов():
    """Иначе имена отрезков размножаются по числу витрин."""
    assert path_template("/api/v1/sites/abc/jobs") == "/api/v1/sites/{siteId}/jobs"
    assert path_template("/api/v1/jobs/xyz") == "/api/v1/jobs/{jobId}"
    assert path_template("/api/v1/health") == "/api/v1/health"


# ---- диагностические пути ---------------------------------------------------

def test_успех_восстанавливается_по_следу(api):
    r = api.handle("POST", f"/api/v1/sites/{SITE}/jobs",
                   body={"action": "reindex"}, headers=AUTH)
    assert r.status == 202
    след = api.handle("GET", f"/api/v1/traces/{след_из(r)}", headers=AUTH)
    assert след.status == 200
    отрезок = след.body["spans"][0]
    assert отрезок["attrs"]["outcome"] == "ok"
    assert отрезок["attrs"]["path_template"] == "/api/v1/sites/{siteId}/jobs"
    assert отрезок["duration_ms"] >= 0


def test_отказ_по_праву_восстанавливается(api):
    r = api.handle("POST", f"/api/v1/sites/{SITE}/jobs", body={"action": "reindex"},
                   headers={"Authorization": f"Bearer {READER}"})
    assert r.status == 403
    след = api.handle("GET", f"/api/v1/traces/{след_из(r)}", headers=AUTH)
    assert след.status == 200
    assert след.body["spans"][0]["attrs"]["error_code"] == "forbidden"


def test_конфликт_версии_восстанавливается(api):
    r = api.handle("PATCH", f"/api/v1/sites/{SITE}/settings",
                   body={"changes": {"keep_releases": 9},
                         "expectedVersion": "sha256:устарело"}, headers=AUTH)
    assert r.status == 409
    след = api.handle("GET", f"/api/v1/traces/{след_из(r)}", headers=AUTH)
    assert след.body["spans"][0]["attrs"]["error_code"] == "version_conflict"


def test_повтор_мутации_восстанавливается(api):
    h = {**AUTH, "Idempotency-Key": "trace-dup-1"}
    api.handle("POST", f"/api/v1/sites/{SITE}/jobs", body={"action": "reindex"}, headers=h)
    r = api.handle("POST", f"/api/v1/sites/{SITE}/jobs", body={"action": "enrich"}, headers=h)
    assert r.status == 409
    след = api.handle("GET", f"/api/v1/traces/{след_из(r)}", headers=AUTH)
    assert след.body["spans"][0]["attrs"]["error_code"] == "idempotency_key_reused"


def test_занятая_витрина_восстанавливается(api, sandbox):
    """Ожидание чужой операции — тот случай, который выглядит как таймаут."""
    with locks.site_lock(SITE, "staging", timeout=0):
        r = api.handle("POST", f"/api/v1/sites/{SITE}/jobs",
                       body={"action": "reindex"}, headers=AUTH)
    assert r.status == 409
    след = api.handle("GET", f"/api/v1/traces/{след_из(r)}", headers=AUTH)
    assert след.body["spans"][0]["attrs"]["error_code"] == "site_busy"


def test_недоступная_витрина_восстанавливается(api, sandbox):
    (sandbox / "config" / "site-profiles" / f"{SITE}.json").write_text("{битый",
                                                                      encoding="utf-8")
    r = api.handle("POST", f"/api/v1/sites/{SITE}/jobs",
                   body={"action": "reindex"}, headers=AUTH)
    assert r.status == 409
    след = api.handle("GET", f"/api/v1/traces/{след_из(r)}", headers=AUTH)
    assert след.body["spans"][0]["attrs"]["error_code"] == "incompatible_contract"


# ---- перенос в асинхронную часть --------------------------------------------

def test_контекст_переносится_в_задание(api, sandbox):
    """Без переноса цепочка обрывается там, где начинается асинхронная часть."""
    r = api.handle("POST", f"/api/v1/sites/{SITE}/jobs",
                   body={"action": "reindex"}, headers=AUTH)
    файлы = list((sandbox / "queue" / "inbox").glob("*.json"))
    assert файлы
    задание = json.loads(файлы[0].read_text(encoding="utf-8"))
    assert "traceparent" in задание, "задание не несёт контекста следа"
    assert parse_traceparent(задание["traceparent"]).trace_id == след_из(r)


def test_идентификатор_следа_попадает_в_аудит(api, sandbox):
    from factory import audit
    r = api.handle("POST", f"/api/v1/sites/{SITE}/jobs",
                   body={"action": "reindex"}, headers=AUTH)
    записи = [e for e in audit.read_all() if e.get("action") == "control.job.reindex"]
    assert записи and записи[-1]["extra"]["trace_id"] == след_из(r)


# ---- права и защита данных --------------------------------------------------

def test_след_требует_права_на_журнал(api):
    r = api.handle("POST", f"/api/v1/sites/{SITE}/jobs",
                   body={"action": "reindex"}, headers=AUTH)
    чужой = api.handle("GET", f"/api/v1/traces/{след_из(r)}",
                       headers={"Authorization": f"Bearer {READER}"})
    assert чужой.status == 403


def test_несуществующий_след_даёт_404(api):
    r = api.handle("GET", "/api/v1/traces/" + "a" * 32, headers=AUTH)
    assert r.status == 404
    assert r.body["error"]["code"] == "trace_not_found"


def test_негодный_идентификатор_следа_не_роняет(api):
    assert api.handle("GET", "/api/v1/traces/не-шестнадцатеричный",
                      headers=AUTH).status == 404


def test_в_след_не_попадают_значения_настроек(api):
    """След не должен становиться вторым местом, где лежат данные."""
    секрет = "значение-которого-не-должно-быть"
    r = api.handle("PATCH", f"/api/v1/sites/{SITE}/settings",
                   body={"changes": {"feature_flags": {секрет: True}}}, headers=AUTH)
    след = api.handle("GET", f"/api/v1/traces/{след_из(r)}", headers=AUTH)
    assert секрет not in json.dumps(след.body, ensure_ascii=False)


def test_посторонние_атрибуты_отбрасываются():
    очищенные = tracing.sanitize_attrs({"site_id": "ok", "password": "секрет",
                                        "authorization": "Bearer x"})
    assert очищенные == {"site_id": "ok"}


# ---- выборка ----------------------------------------------------------------

def test_изменяющие_и_ошибки_пишутся_всегда(sandbox):
    редкий = Tracer(sandbox / "var" / "state", read_sample=0.0)
    assert редкий.should_sample(mutating=True, failed=False) is True
    assert редкий.should_sample(mutating=False, failed=True) is True
    assert редкий.should_sample(mutating=False, failed=False) is False


def test_унаследованное_решение_уважается(sandbox):
    """Обрывать след на середине бессмысленно: получится половина пути."""
    редкий = Tracer(sandbox / "var" / "state", read_sample=0.0)
    assert редкий.should_sample(mutating=False, failed=False, inherited=True) is True


def test_старые_следы_убираются(sandbox):
    """Файл состаривается по-настоящему: очистка смотрит на время изменения."""
    import os
    import time as _t

    t = Tracer(sandbox / "var" / "state", retention_seconds=100)
    ctx = new_context()
    with t.span("проба", ctx):
        pass
    assert t.read_trace(ctx.trace_id)
    путь = sandbox / "var" / "state" / "trace" / f"{ctx.trace_id}.jsonl"
    старое_время = _t.time() - 1000
    os.utime(путь, (старое_время, старое_время))
    assert t.cleanup() >= 1
    assert t.read_trace(ctx.trace_id) == []


def test_свежие_следы_не_трогаются(sandbox):
    t = Tracer(sandbox / "var" / "state", retention_seconds=3600)
    ctx = new_context()
    with t.span("проба", ctx):
        pass
    assert t.cleanup() == 0
    assert t.read_trace(ctx.trace_id)
