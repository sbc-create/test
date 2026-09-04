"""REQ-ISOLATION: отказ одной витрины не выходит за её пределы.

Проверяется внедрением отказов, а не рассуждением об архитектуре: портится
конкретная витрина и измеряется, что делается с соседней. Изоляция, о которой
известно только из схемы, — это предположение.
"""
import json
import os
import stat

import pytest

from factory import audit, locks, queue
from factory.paths import PATHS
from factory.site_engine.api.control import ControlApi

TOKEN = "b-admin"
ENV = {
    "SITE_ENGINE_CONTROL_WRITES": "1",
    "SITE_ENGINE_CONTROL_TOKENS": f"{TOKEN}=read,jobs:write,config:write,cache:write,audit:read",
}
AUTH = {"Authorization": f"Bearer {TOKEN}"}
БОЛЬНАЯ = "sick-site"
ЗДОРОВАЯ = "healthy-site"


@pytest.fixture
def sandbox(tmp_path, monkeypatch):
    monkeypatch.setattr(PATHS, "root", tmp_path)
    profiles = tmp_path / "config" / "site-profiles"
    profiles.mkdir(parents=True)
    for name in (БОЛЬНАЯ, ЗДОРОВАЯ):
        (profiles / f"{name}.json").write_text(json.dumps({
            "site_id": name, "site_type": "anime", "cms_contract": "1.2.0",
            "keep_releases": 5, "cache_policy": {}, "feature_flags": {},
        }, ensure_ascii=False), encoding="utf-8")
    for sub in ("queue/inbox", "queue/processing", "queue/done", "queue/failed",
                "queue/quarantine", "var/locks", "var/audit", "var/state"):
        (tmp_path / sub).mkdir(parents=True, exist_ok=True)
    return tmp_path


@pytest.fixture
def api(sandbox):
    return ControlApi(root=sandbox, env=ENV)


def задание(api, site):
    return api.handle("POST", f"/api/v1/sites/{site}/jobs",
                      body={"action": "reindex"}, headers=AUTH)


# ---- порча конфигурации одной витрины ---------------------------------------

def test_испорченный_профиль_не_задевает_соседнюю(api, sandbox):
    """Негодный JSON в одном профиле не должен останавливать массив."""
    (sandbox / "config" / "site-profiles" / f"{БОЛЬНАЯ}.json").write_text(
        "{это не json", encoding="utf-8")
    больная = задание(api, БОЛЬНАЯ)
    здоровая = задание(api, ЗДОРОВАЯ)
    assert больная.status == 409, "витрина с нечитаемым профилем не управляется"
    assert больная.body["error"]["code"] == "incompatible_contract"
    assert здоровая.status == 202, "соседняя витрина обязана работать"


def test_пропавший_профиль_не_задевает_соседнюю(api, sandbox):
    (sandbox / "config" / "site-profiles" / f"{БОЛЬНАЯ}.json").unlink()
    assert задание(api, БОЛЬНАЯ).status == 404
    assert задание(api, ЗДОРОВАЯ).status == 202


def test_чужой_контракт_не_задевает_соседнюю(api, sandbox):
    путь = sandbox / "config" / "site-profiles" / f"{БОЛЬНАЯ}.json"
    данные = json.loads(путь.read_text(encoding="utf-8"))
    данные["cms_contract"] = "99.0.0"
    путь.write_text(json.dumps(данные), encoding="utf-8")
    assert задание(api, БОЛЬНАЯ).status == 409
    assert задание(api, ЗДОРОВАЯ).status == 202


def test_матрица_показывает_ровно_одну_пострадавшую(api, sandbox):
    путь = sandbox / "config" / "site-profiles" / f"{БОЛЬНАЯ}.json"
    данные = json.loads(путь.read_text(encoding="utf-8"))
    данные["cms_contract"] = "99.0.0"
    путь.write_text(json.dumps(данные), encoding="utf-8")
    r = api.handle("GET", "/api/v1/compatibility", headers=AUTH)
    assert r.body["total"] == 2 and r.body["manageable"] == 1
    пострадавшие = [s["siteId"] for s in r.body["sites"] if not s["manageable"]]
    assert пострадавшие == [БОЛЬНАЯ]


# ---- занятая витрина --------------------------------------------------------

def test_занятая_витрина_не_блокирует_соседнюю(api, sandbox):
    """Блокировка на витрину, а не на массив."""
    with locks.site_lock(БОЛЬНАЯ, "staging", timeout=0):
        занятая = задание(api, БОЛЬНАЯ)
        свободная = задание(api, ЗДОРОВАЯ)
    assert занятая.status == 409 and занятая.body["error"]["code"] == "site_busy"
    assert свободная.status == 202


def test_блокировка_освобождается_после_операции(api, sandbox):
    assert задание(api, БОЛЬНАЯ).status == 202
    assert not locks.is_locked(БОЛЬНАЯ, "staging"), "замок остался после операции"


# ---- застрявшее задание -----------------------------------------------------

def test_застрявшее_задание_возвращается_в_очередь(api, sandbox):
    """Исполнитель умер после захвата: задание не должно пропасть."""
    задание(api, БОЛЬНАЯ)
    item = queue.claim()
    assert item is not None and queue.counts()["processing"] == 1
    итог = queue.requeue_stale(max_age_seconds=0)
    assert queue.counts()["inbox"] == 1 and queue.counts()["processing"] == 0
    assert итог


def test_трижды_неудавшееся_уходит_в_карантин(api, sandbox):
    """Отказ повторять то, что трижды не вышло, — свойство, а не сбой."""
    задание(api, БОЛЬНАЯ)
    for _ in range(queue.MAX_ATTEMPTS + 2):
        item = queue.claim()
        if item is None:
            break
        queue.requeue_stale(max_age_seconds=0, max_attempts=queue.MAX_ATTEMPTS)
    counts = queue.counts()
    assert counts["quarantine"] >= 1 or counts["failed"] >= 1, counts
    assert counts["processing"] == 0


# ---- недоступность вспомогательных путей ------------------------------------

@pytest.mark.skipif(os.geteuid() == 0, reason="под root права на запись не ограничивают")
def test_недоступный_журнал_не_превращает_отказ_в_сбой(api, sandbox):
    """Невозможность записать отказ не должна менять код ответа."""
    каталог = sandbox / "var" / "audit"
    прежние = стат = каталог.stat().st_mode
    каталог.chmod(stat.S_IRUSR | stat.S_IXUSR)
    try:
        r = api.handle("POST", f"/api/v1/sites/{БОЛЬНАЯ}/jobs",
                       body={"action": "нет-такого"}, headers=AUTH)
        assert r.status == 400, "отказ обязан остаться отказом"
    finally:
        каталог.chmod(прежние)


def test_метрики_отдаются_при_недоступной_очереди(api, sandbox, monkeypatch):
    """Система сбора получит остальное и заметит пропажу ряда."""
    def сломано():
        raise OSError("очередь недоступна")
    monkeypatch.setattr(queue, "counts", сломано)
    r = api.handle("GET", "/api/v1/metrics", headers=AUTH)
    assert r.status == 200
    assert "site_engine_sites 2" in r.body["prometheus"]
    assert "site_engine_queue_items" not in r.body["prometheus"]


# ---- след в журнале ---------------------------------------------------------

def test_авария_одной_витрины_видна_в_журнале_поимённо(api, sandbox):
    путь = sandbox / "config" / "site-profiles" / f"{БОЛЬНАЯ}.json"
    данные = json.loads(путь.read_text(encoding="utf-8"))
    данные["cms_contract"] = "99.0.0"
    путь.write_text(json.dumps(данные), encoding="utf-8")
    задание(api, БОЛЬНАЯ)
    задание(api, ЗДОРОВАЯ)
    записи = audit.read_all()
    отказы = [e for e in записи if e["action"].startswith("control.denied")]
    успехи = [e for e in записи if e["action"] == "control.job.reindex"]
    assert len(отказы) == 1 and len(успехи) == 1
    assert успехи[0]["site_id"] == ЗДОРОВАЯ
