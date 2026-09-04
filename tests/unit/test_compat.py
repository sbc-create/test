"""REQ-CMS-UNIFICATION: один движок, разные типы витрин, явный контракт.

Единство кодовой базы проверяется не тем, что файлы лежат в одном каталоге, а
тем, что один и тот же движок управляет разнородными витринами по одному
контракту — и отказывается управлять теми, чей контракт он не реализует.
"""
import json
from pathlib import Path

import pytest

from factory import queue
from factory.paths import PATHS
from factory.site_engine.api import compat
from factory.site_engine.api.control import ControlApi

REPO = Path(__file__).resolve().parents[2]
TOKEN = "c-admin"
READER = "c-reader"
ENV = {
    "SITE_ENGINE_CONTROL_WRITES": "1",
    "SITE_ENGINE_CONTROL_TOKENS": f"{TOKEN}=read,jobs:write,config:write,cache:write|{READER}=jobs:write",
}
AUTH = {"Authorization": f"Bearer {TOKEN}"}


def _profile(**overrides):
    base = {"site_id": "s", "site_type": "anime", "keep_releases": 5,
            "cache_policy": {}, "feature_flags": {}}
    base.update(overrides)
    return base


@pytest.fixture
def sandbox(tmp_path, monkeypatch):
    monkeypatch.setattr(PATHS, "root", tmp_path)
    (tmp_path / "config" / "site-profiles").mkdir(parents=True)
    for sub in ("queue/inbox", "queue/processing", "queue/done", "queue/failed",
                "queue/quarantine", "var/locks", "var/audit", "var/state"):
        (tmp_path / sub).mkdir(parents=True, exist_ok=True)
    return tmp_path


def положить(sandbox, site_id, **overrides):
    путь = sandbox / "config" / "site-profiles" / f"{site_id}.json"
    путь.write_text(json.dumps(_profile(site_id=site_id, **overrides), ensure_ascii=False),
                    encoding="utf-8")
    return путь


@pytest.fixture
def api(sandbox):
    return ControlApi(root=sandbox, env=ENV)


# ---- разбор соотношения -----------------------------------------------------

def test_совпадающие_контракты_согласованы():
    r = compat.evaluate(_profile(cms_contract=compat.ENGINE_CONTRACT))
    assert r.state == compat.STATE_OK and r.manageable


def test_профиль_без_объявления_считается_совместимым():
    """Иначе введение контракта разом остановило бы весь массив."""
    r = compat.evaluate(_profile())
    assert r.state == compat.STATE_UNVERSIONED and r.manageable
    assert r.declared is None


def test_младшая_версия_выше_движковой_это_ограниченная_работа():
    r = compat.evaluate(_profile(cms_contract="1.9.0"), engine="1.2.0")
    assert r.state == compat.STATE_DEGRADED and r.manageable
    assert "отсутствует" in r.reason


def test_младшая_версия_ниже_допустима():
    r = compat.evaluate(_profile(cms_contract="1.0.0"), engine="1.2.0")
    assert r.state == compat.STATE_OK


@pytest.mark.parametrize("declared", ["2.0.0", "0.9.0"])
def test_расхождение_старших_версий_несовместимо(declared):
    r = compat.evaluate(_profile(cms_contract=declared), engine="1.2.0")
    assert r.state == compat.STATE_INCOMPATIBLE and not r.manageable


@pytest.mark.parametrize("declared", ["последняя", "1", "1.2.3.4", "", " ", "v1.2"])
def test_неразобранная_версия_считается_несовместимой(declared):
    """Отказ громкий и обратимый; пропуск тихий и нет."""
    r = compat.evaluate(_profile(cms_contract=declared), engine="1.2.0")
    if declared.strip() == "":
        assert r.state == compat.STATE_UNVERSIONED
    else:
        assert r.state == compat.STATE_INCOMPATIBLE, declared


def test_испорченная_версия_движка_не_объявляет_всё_исправным():
    r = compat.evaluate(_profile(cms_contract="1.0.0"), engine="не версия")
    assert r.state == compat.STATE_INCOMPATIBLE


# ---- ворота перед мутациями -------------------------------------------------

@pytest.mark.parametrize("метод,путь,тело", [
    ("POST", "jobs", {"action": "reindex"}),
    ("PATCH", "settings", {"changes": {"keep_releases": 8}}),
    ("POST", "cache/invalidate", {"scope": "catalog"}),
])
def test_несовместимой_витриной_управлять_нельзя(api, sandbox, метод, путь, тело):
    положить(sandbox, "old-site", cms_contract="2.0.0")
    r = api.handle(метод, f"/api/v1/sites/old-site/{путь}", body=тело, headers=AUTH)
    assert r.status == 409
    assert r.body["error"]["code"] == "incompatible_contract"
    assert r.body["error"]["state"] == compat.STATE_INCOMPATIBLE
    assert queue.counts()["inbox"] == 0


def test_отказ_называет_обе_версии(api, sandbox):
    положить(sandbox, "old-site", cms_contract="2.0.0")
    r = api.handle("POST", "/api/v1/sites/old-site/jobs",
                   body={"action": "reindex"}, headers=AUTH)
    assert r.body["error"]["declared"] == "2.0.0"
    assert r.body["error"]["engine"] == compat.ENGINE_CONTRACT


def test_ограниченной_витриной_управлять_можно(api, sandbox):
    """degraded — повод знать, а не повод остановить управление."""
    старшая = compat.parse(compat.ENGINE_CONTRACT)[0]
    положить(sandbox, "ahead", cms_contract=f"{старшая}.99.0")
    r = api.handle("POST", "/api/v1/sites/ahead/jobs",
                   body={"action": "reindex"}, headers=AUTH)
    assert r.status == 202
    assert queue.counts()["inbox"] == 1


def test_проверка_совместимости_не_обходится_пробным_запуском(api, sandbox):
    """dryRun не должен быть лазейкой мимо ворот."""
    положить(sandbox, "old-site", cms_contract="2.0.0")
    r = api.handle("POST", "/api/v1/sites/old-site/jobs",
                   body={"action": "reindex", "dryRun": True}, headers=AUTH)
    assert r.status == 409


# ---- матрица ----------------------------------------------------------------

def test_матрица_перечисляет_витрины_и_состояния(api, sandbox):
    положить(sandbox, "a", cms_contract=compat.ENGINE_CONTRACT)
    положить(sandbox, "b")
    положить(sandbox, "c", cms_contract="2.0.0")
    r = api.handle("GET", "/api/v1/compatibility", headers=AUTH)
    assert r.status == 200
    assert r.body["total"] == 3 and r.body["manageable"] == 2
    assert r.body["byState"][compat.STATE_INCOMPATIBLE] == 1
    assert r.body["engine"] == compat.ENGINE_CONTRACT


def test_матрица_по_одной_витрине(api, sandbox):
    положить(sandbox, "a", cms_contract=compat.ENGINE_CONTRACT)
    r = api.handle("GET", "/api/v1/compatibility/a", headers=AUTH)
    assert r.status == 200 and r.body["state"] == compat.STATE_OK


def test_матрица_требует_права_чтения(api, sandbox):
    положить(sandbox, "a")
    r = api.handle("GET", "/api/v1/compatibility",
                   headers={"Authorization": f"Bearer {READER}"})
    assert r.status == 403


def test_несуществующая_витрина_в_матрице(api, sandbox):
    assert api.handle("GET", "/api/v1/compatibility/нет", headers=AUTH).status == 400


# ---- один движок на разнородные витрины -------------------------------------

def test_один_движок_обслуживает_разные_типы_витрин(api, sandbox):
    """Настоящие профили массива, а не выдуманные: типы должны различаться."""
    источник = REPO / "config" / "site-profiles"
    взято = 0
    типы = set()
    for файл in sorted(источник.glob("*.json"))[:12]:
        raw = json.loads(файл.read_text(encoding="utf-8"))
        тип = raw.get("site_type")
        if not тип:
            continue
        (sandbox / "config" / "site-profiles" / файл.name).write_text(
            json.dumps(raw, ensure_ascii=False), encoding="utf-8")
        типы.add(тип)
        взято += 1
    assert взято >= 3 and len(типы) >= 2, f"нужны разные типы, получено {типы}"
    r = api.handle("GET", "/api/v1/compatibility", headers=AUTH)
    assert r.status == 200
    assert r.body["total"] == взято
    # Ни одна настоящая витрина не должна оказаться неуправляемой из-за того,
    # что контракт введён сегодня.
    assert r.body["manageable"] == взято, r.body["byState"]
    assert {row["siteType"] for row in r.body["sites"]} == типы
