"""REQ-OBSERVABILITY: метрики отвечают на вопрос «что происходит вообще».

Проверяется не только наличие чисел, но и свойства, из-за которых метрики
обычно становятся бесполезными: разросшаяся размерность меток, отсутствие
защиты маршрута и падение опроса при недоступном источнике.
"""
import json

import pytest

from factory import queue
from factory.paths import PATHS
from factory.site_engine.api.control import ControlApi
from factory.site_engine.api.metrics import Metrics, status_class

ADMIN = "m-admin"
READER = "m-reader"
ENV = {
    "SITE_ENGINE_CONTROL_WRITES": "1",
    "SITE_ENGINE_CONTROL_TOKENS": f"{ADMIN}=read,jobs:write,config:write|{READER}=jobs:write",
}
AUTH = {"Authorization": f"Bearer {ADMIN}"}
SITE = "metrics-site"


@pytest.fixture
def sandbox(tmp_path, monkeypatch):
    monkeypatch.setattr(PATHS, "root", tmp_path)
    profiles = tmp_path / "config" / "site-profiles"
    profiles.mkdir(parents=True)
    for name in (SITE, "second-site"):
        (profiles / f"{name}.json").write_text(json.dumps({
            "site_id": name, "keep_releases": 5, "cache_policy": {}, "feature_flags": {},
        }, ensure_ascii=False), encoding="utf-8")
    for sub in ("queue/inbox", "queue/processing", "queue/done", "queue/failed",
                "queue/quarantine", "var/locks", "var/audit", "var/state"):
        (tmp_path / sub).mkdir(parents=True, exist_ok=True)
    return tmp_path


@pytest.fixture
def api(sandbox):
    return ControlApi(root=sandbox, env=ENV, metrics=Metrics())


def текст(api):
    return api.handle("GET", "/api/v1/metrics", headers=AUTH).body["prometheus"]


# ---- защита -----------------------------------------------------------------

def test_метрики_требуют_права_чтения(api):
    r = api.handle("GET", "/api/v1/metrics", headers={"Authorization": f"Bearer {READER}"})
    assert r.status == 403
    assert r.body["error"]["required_scope"] == "read"


def test_метрики_без_токена_недоступны(api):
    assert api.handle("GET", "/api/v1/metrics").status == 401


# ---- формат -----------------------------------------------------------------

def test_формат_содержит_help_и_type(api):
    api.handle("GET", "/api/v1/metrics", headers=AUTH)  # чтобы счётчик появился
    body = текст(api)
    assert "# HELP site_engine_control_requests_total" in body
    assert "# TYPE site_engine_control_requests_total counter" in body
    assert body.endswith("\n")


def test_счётчик_появляется_только_с_первым_наблюдением(api):
    """Свойство, а не упущение: ряд без наблюдений не выводится.

    Значит панель, построенная на site_engine_control_requests_total, на свежем
    процессе увидит отсутствие ряда, а не ноль. Для счётчика это правильно —
    ноль означал бы «запросов не было», а отсутствие означает «ещё не мерили», —
    но знать об этом нужно заранее, а не в момент разбора инцидента.
    """
    первый = текст(api)
    assert "site_engine_control_requests_total" not in первый
    assert "site_engine_sites" in первый, "показатели состояния выводятся сразу"
    второй = текст(api)
    assert "site_engine_control_requests_total" in второй


def test_тип_объявляется_один_раз_на_метрику(api):
    api.handle("GET", "/api/v1/metrics", headers=AUTH)
    api.handle("GET", "/api/v1/nope", headers=AUTH)
    body = текст(api)
    for line in body.splitlines():
        if line.startswith("# TYPE"):
            name = line.split()[2]
            assert body.count(f"# TYPE {name} ") == 1, f"дубль TYPE для {name}"


def test_значения_меток_экранируются():
    m = Metrics()
    m.inc("site_engine_control_refusals_total", code='с "кавычкой"\\и слешем')
    body = m.render()
    assert '\\"кавычкой\\"' in body and "\\\\и" in body


# ---- содержание -------------------------------------------------------------

def test_запросы_считаются_по_классу_ответа(api):
    api.handle("GET", "/api/v1/metrics", headers=AUTH)
    api.handle("GET", "/api/v1/audit", headers=AUTH)          # 403: нет audit:read
    assert api.metrics.value("site_engine_control_requests_total",
                             method="GET", status="2xx") >= 1
    assert api.metrics.value("site_engine_control_requests_total",
                             method="GET", status="4xx") >= 1


def test_отказы_считаются_по_коду(api):
    api.handle("POST", f"/api/v1/sites/{SITE}/jobs",
               body={"action": "недопустимо"}, headers=AUTH)
    assert api.metrics.value("site_engine_control_refusals_total",
                             code="invalid_action") == 1


def test_очередь_видна_по_стадиям(api):
    api.handle("POST", f"/api/v1/sites/{SITE}/jobs",
               body={"action": "reindex"}, headers=AUTH)
    body = текст(api)
    assert 'site_engine_queue_items{stage="inbox"} 1' in body
    assert 'site_engine_queue_items{stage="done"} 0' in body


def test_число_витрин_считается_из_профилей(api):
    assert "site_engine_sites 2" in текст(api)


def test_зарегистрированный_показатель_попадает_в_вывод(api):
    api.register_gauge("site_engine_admin_sessions", lambda: [({}, 3)])
    assert "site_engine_admin_sessions 3" in текст(api)


def test_упавший_источник_показателя_не_роняет_опрос(api):
    """Система сбора должна получить остальное и заметить пропажу."""
    def сломан():
        raise RuntimeError("источник недоступен")
    api.register_gauge("site_engine_admin_sessions", сломан)
    body = текст(api)
    assert "site_engine_admin_sessions" not in body
    assert "site_engine_sites" in body


# ---- размерность ------------------------------------------------------------

def test_метки_не_содержат_идентификаторов_витрин(api):
    """На массиве сайтов такая метка превращает ряды в тысячи."""
    for site in (SITE, "second-site"):
        api.handle("POST", f"/api/v1/sites/{site}/jobs",
                   body={"action": "reindex", "dryRun": True}, headers=AUTH)
    body = текст(api)
    for line in body.splitlines():
        if line.startswith("site_engine_control_"):
            assert SITE not in line and "second-site" not in line


def test_класс_ответа_вместо_точного_кода():
    assert status_class(200) == "2xx"
    assert status_class(404) == "4xx"
    assert status_class(503) == "5xx"


def test_счётчики_обнуляются_сбросом(api):
    api.handle("GET", "/api/v1/metrics", headers=AUTH)
    assert api.metrics.snapshot()
    api.metrics.reset()
    assert api.metrics.snapshot() == {}
