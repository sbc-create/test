"""REQ-FLEET-API: флот виден через тот же Control API, а не через вторую систему.

Каждое действие центра управления обязано иметь машинный эквивалент — иначе
рядом с интерфейсом заводится второй способ управлять теми же витринами, и
однажды они разойдутся.

Отдельно проверяется сужение: привязанный к витрине видит во флоте только свою
строку. Список без сужения — это утечка, а не удобство: по нему видно домены,
релизы и состояние соседей.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from factory.paths import PATHS
from factory.site_engine.api.control import ControlApi

REPO = Path(__file__).resolve().parents[2]
СВОЙ, ЧУЖОЙ = "lords-01", "lords-02"
МЕСТНЫЙ, СУПЕР, ТОЛЬКО_ЧТЕНИЕ = "tok-local", "tok-super", "tok-ro"

ENV = {
    "SITE_ENGINE_CONTROL_TOKENS": (
        f"{МЕСТНЫЙ}=read,config:write@{СВОЙ}"
        f"|{СУПЕР}=read,config:write,operators:write"
        f"|{ТОЛЬКО_ЧТЕНИЕ}=read"
    ),
}
H_МЕСТНЫЙ = {"Authorization": f"Bearer {МЕСТНЫЙ}", "X-Site-Id": СВОЙ}
H_СУПЕР = {"Authorization": f"Bearer {СУПЕР}"}
H_ЧТЕНИЕ = {"Authorization": f"Bearer {ТОЛЬКО_ЧТЕНИЕ}"}


@pytest.fixture
def песочница(tmp_path, monkeypatch):
    monkeypatch.setattr(PATHS, "root", tmp_path)
    профили = tmp_path / "config" / "site-profiles"
    профили.mkdir(parents=True)
    образец = json.loads(
        (REPO / "config" / "site-profiles" / "lords-01.json").read_text(encoding="utf-8"))
    for сайт in (СВОЙ, ЧУЖОЙ):
        d = dict(образец)
        d.update({"site_id": сайт, "domains": [f"{сайт}.test"],
                  "canonical_host": f"{сайт}.test"})
        (профили / f"{сайт}.json").write_text(json.dumps(d, ensure_ascii=False),
                                              encoding="utf-8")
    (tmp_path / "config" / "fleet-sources.yaml").write_text(
        "version: 1\nruntime:\n  root: /nonexistent\n", encoding="utf-8")
    for под in ("var/audit", "var/state", "var/locks", "queue/inbox"):
        (tmp_path / под).mkdir(parents=True, exist_ok=True)
    return tmp_path


@pytest.fixture
def api(песочница):
    return ControlApi(root=песочница, env=ENV)


def test_супер_видит_весь_флот(api):
    ответ = api.handle("GET", "/api/v1/fleet", headers=H_СУПЕР, body=None)
    assert ответ.status == 200
    assert ответ.body["total"] == 2
    assert {з["siteId"] for з in ответ.body["sites"]} == {СВОЙ, ЧУЖОЙ}


def test_привязанный_видит_только_свою_строку(api):
    ответ = api.handle("GET", "/api/v1/fleet", headers=H_МЕСТНЫЙ, body=None)
    assert ответ.status == 200
    assert ответ.body["total"] == 1
    assert ответ.body["sites"][0]["siteId"] == СВОЙ
    assert ответ.body["scopedTo"] == СВОЙ
    # Домена соседа в ответе нет ни в каком виде.
    assert ЧУЖОЙ not in json.dumps(ответ.body, ensure_ascii=False)


def test_чужая_запись_в_адресе_отклонена(api):
    ответ = api.handle("GET", f"/api/v1/fleet/{ЧУЖОЙ}", headers=H_МЕСТНЫЙ, body=None)
    assert ответ.status == 403
    assert ответ.body["error"]["code"] == "cross_tenant"


def test_своя_запись_доступна(api):
    ответ = api.handle("GET", f"/api/v1/fleet/{СВОЙ}", headers=H_МЕСТНЫЙ, body=None)
    assert ответ.status == 200
    assert ответ.body["siteId"] == СВОЙ
    assert ответ.body["fields"]["domains"]["source"]


def test_несуществующая_витрина_отклонена(api):
    ответ = api.handle("GET", "/api/v1/fleet/нет-такой", headers=H_СУПЕР, body=None)
    assert ответ.status in (400, 404)


def test_каждое_поле_несёт_состояние_и_источник(api):
    ответ = api.handle("GET", f"/api/v1/fleet/{СВОЙ}", headers=H_СУПЕР, body=None)
    поля = ответ.body["fields"]
    assert поля, "запись пуста"
    for имя, поле in поля.items():
        assert поле["state"], f"{имя}: нет состояния"
        assert поле["source"], f"{имя}: нет источника"


def test_читающий_токен_не_меняет_ничего(api):
    """Отрицательная проверка для служебной учётной записи нейросети."""
    ответ = api.handle("POST", "/api/v1/fleet", headers=H_ЧТЕНИЕ, body={})
    assert ответ.status in (403, 404, 405), (
        "запись во флот принята токеном только на чтение")
