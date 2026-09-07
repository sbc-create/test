"""REQ-AI-CONTROL: служебная учётная запись меняет ровно то, что ей разрешено.

Нейросети выдают токен, чтобы она посмотрела флот и предложила изменение. Семь
утверждений ниже — это то, без чего такой токен опасен: каждое проверяет не
намерение, а последствие.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from factory import audit
from factory.paths import PATHS
from factory.site_engine.api.control import ControlApi

REPO = Path(__file__).resolve().parents[2]
СВОЙ, СОСЕД = "lords-01", "lords-02"
ЧИТАТЕЛЬ = "tok-ai-ro"
ПРИВЯЗАННЫЙ = "tok-ai-scoped"

ENV = {
    "SITE_ENGINE_CONTROL_WRITES": "1",
    "SITE_ENGINE_CONTROL_TOKENS": (
        f"{ЧИТАТЕЛЬ}=read"
        f"|{ПРИВЯЗАННЫЙ}=read,config:write@{СВОЙ}"
    ),
}
H_ЧИТАТЕЛЬ = {"Authorization": f"Bearer {ЧИТАТЕЛЬ}"}
H_ПРИВЯЗАННЫЙ = {"Authorization": f"Bearer {ПРИВЯЗАННЫЙ}", "X-Site-Id": СВОЙ}


@pytest.fixture
def песочница(tmp_path, monkeypatch):
    monkeypatch.setattr(PATHS, "root", tmp_path)
    профили = tmp_path / "config" / "site-profiles"
    профили.mkdir(parents=True)
    образец = json.loads(
        (REPO / "config" / "site-profiles" / f"{СВОЙ}.json").read_text(encoding="utf-8"))
    for сайт in (СВОЙ, СОСЕД):
        d = dict(образец)
        d.update({"site_id": сайт, "domains": [f"{сайт}.test"],
                  "canonical_host": f"{сайт}.test", "keep_releases": 4})
        (профили / f"{сайт}.json").write_text(json.dumps(d, ensure_ascii=False),
                                              encoding="utf-8")
    for под in ("var/audit", "var/state", "var/locks", "queue/inbox"):
        (tmp_path / под).mkdir(parents=True, exist_ok=True)
    return tmp_path


@pytest.fixture
def api(песочница):
    return ControlApi(root=песочница, env=ENV)


def _профиль(песочница, сайт):
    return json.loads(
        (песочница / "config" / "site-profiles" / f"{сайт}.json").read_text(encoding="utf-8"))


def _патч(api, сайт, changes, headers, **ещё):
    return api.handle("PATCH", f"/api/v1/sites/{сайт}/settings", headers=headers,
                      body={"changes": changes, **ещё})


# 1. Только чтение — отказ на изменение.
def test_читающая_учётная_запись_получает_отказ(api, песочница):
    было = _профиль(песочница, СВОЙ)["keep_releases"]
    ответ = _патч(api, СВОЙ, {"keep_releases": 9}, H_ЧИТАТЕЛЬ)
    assert ответ.status == 403
    assert _профиль(песочница, СВОЙ)["keep_releases"] == было


# 2. Привязанная учётная запись выполняет разрешённый сухой прогон.
def test_привязанная_выполняет_сухой_прогон(api, песочница):
    было = _профиль(песочница, СВОЙ)["keep_releases"]
    ответ = _патч(api, СВОЙ, {"keep_releases": 9}, H_ПРИВЯЗАННЫЙ, dryRun=True)
    assert ответ.status == 200 and ответ.body["dryRun"] is True
    assert ответ.body["diff"]["keep_releases"]["after"] == 9
    assert _профиль(песочница, СВОЙ)["keep_releases"] == было, "сухой прогон записал"


# 3. Разрешённое изменение применяется только к своему тенанту.
def test_изменение_применяется_только_к_своему_сайту(api, песочница):
    сосед_до = _профиль(песочница, СОСЕД)
    ответ = _патч(api, СВОЙ, {"keep_releases": 9}, H_ПРИВЯЗАННЫЙ)
    assert ответ.status == 200 and ответ.body["applied"] is True
    assert _профиль(песочница, СВОЙ)["keep_releases"] == 9
    assert _профиль(песочница, СОСЕД) == сосед_до, "изменён соседний сайт"


# 4. Чужой сайт закрыт даже с правом записи на свой.
def test_чужой_сайт_закрыт(api, песочница):
    сосед_до = _профиль(песочница, СОСЕД)
    ответ = _патч(api, СОСЕД, {"keep_releases": 9},
                  {"Authorization": f"Bearer {ПРИВЯЗАННЫЙ}", "X-Site-Id": СВОЙ})
    assert ответ.status == 403
    assert (ответ.body["error"] or {}).get("code") == "cross_tenant"
    assert _профиль(песочница, СОСЕД) == сосед_до


# 5. Повтор с тем же ключом не дублирует действие.
def test_повтор_не_дублирует(api, песочница):
    заголовки = {**H_ПРИВЯЗАННЫЙ, "idempotency-key": "ai-key-1"}
    первый = _патч(api, СВОЙ, {"keep_releases": 7}, заголовки)
    второй = _патч(api, СВОЙ, {"keep_releases": 7}, заголовки)
    assert первый.body["applied"] is True
    assert второй.body.get("idempotentReplay") is True
    assert второй.body["version"] == первый.body["version"]


# 6. Журнал содержит исполнителя, сайт, версии до и после.
def test_журнал_называет_исполнителя_и_версии(api, песочница):
    _патч(api, СВОЙ, {"keep_releases": 6}, H_ПРИВЯЗАННЫЙ)
    записи = [з for з in audit.read_all() if "settings" in str(з.get("action", ""))]
    assert записи, "изменение не записано"
    последняя = записи[-1]
    assert последняя.get("site_id") == СВОЙ
    дополнительно = последняя.get("extra") or последняя
    как_текст = json.dumps(последняя, ensure_ascii=False)
    assert "version_before" in как_текст and "version_after" in как_текст, (
        "по журналу не видно, что было и что стало")
    assert дополнительно.get("actor") or "actor" in как_текст, "не видно, кто изменил"


# 7. Возврат прежнего значения восстанавливает состояние.
def test_возврат_прежнего_значения(api, песочница):
    было = _профиль(песочница, СВОЙ)["keep_releases"]
    _патч(api, СВОЙ, {"keep_releases": 11}, H_ПРИВЯЗАННЫЙ)
    assert _профиль(песочница, СВОЙ)["keep_releases"] == 11
    ответ = _патч(api, СВОЙ, {"keep_releases": было}, H_ПРИВЯЗАННЫЙ)
    assert ответ.status == 200
    assert _профиль(песочница, СВОЙ)["keep_releases"] == было


# 8. Флот сужен до своего сайта — читающий доступ не шире записывающего.
def test_флот_сужен_до_своего_сайта(api):
    ответ = api.handle("GET", "/api/v1/fleet", headers=H_ПРИВЯЗАННЫЙ, body=None)
    assert ответ.status == 200
    assert ответ.body["total"] == 1
    assert СОСЕД not in json.dumps(ответ.body, ensure_ascii=False)


# 9. Отказ структурирован: код, объяснение, correlation id.
def test_отказ_разбирается_машиной(api):
    ответ = _патч(api, СОСЕД, {"keep_releases": 9}, H_ПРИВЯЗАННЫЙ)
    ошибка = ответ.body["error"]
    assert ошибка["code"] and ошибка["message"]
    assert ответ.body["correlationId"]
