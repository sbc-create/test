"""REQ-IDEMPOTENCY: повтор запроса службы не применяется дважды.

Механизм повтора в управляющем слое уже есть — здесь проверяется, что он
действительно закрывает случай, ради которого нужен: служебная учётная запись
повторяет запрос при разрыве, таймауте и перезапуске, и «применить настройки»
не должно сработать дважды.

Проверка написана после того, как рядом чуть не появился второй такой механизм.
Отдельный модуль повтора выглядел бы разумно и работал бы правильно — и ровно
поэтому был бы опасен: два места, решающих одну задачу, расходятся молча.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from factory.paths import PATHS
from factory.site_engine.api.control import ControlApi

REPO = Path(__file__).resolve().parents[2]
САЙТ = "lords-01"
ТОКЕН = "tok-write"
ENV = {
    "SITE_ENGINE_CONTROL_WRITES": "1",
    "SITE_ENGINE_CONTROL_TOKENS": f"{ТОКЕН}=read,config:write",
}
ЗАГОЛОВКИ = {"Authorization": f"Bearer {ТОКЕН}"}


@pytest.fixture
def песочница(tmp_path, monkeypatch):
    monkeypatch.setattr(PATHS, "root", tmp_path)
    профили = tmp_path / "config" / "site-profiles"
    профили.mkdir(parents=True)
    образец = json.loads(
        (REPO / "config" / "site-profiles" / f"{САЙТ}.json").read_text(encoding="utf-8"))
    (профили / f"{САЙТ}.json").write_text(json.dumps(образец, ensure_ascii=False),
                                          encoding="utf-8")
    for под in ("var/audit", "var/state", "var/locks", "queue/inbox"):
        (tmp_path / под).mkdir(parents=True, exist_ok=True)
    return tmp_path


@pytest.fixture
def api(песочница):
    return ControlApi(root=песочница, env=ENV)


def _профиль(песочница) -> dict:
    return json.loads(
        (песочница / "config" / "site-profiles" / f"{САЙТ}.json").read_text(encoding="utf-8"))


def _патч(api, тело, ключ=None):
    заголовки = dict(ЗАГОЛОВКИ)
    if ключ:
        заголовки["idempotency-key"] = ключ
    return api.handle("PATCH", f"/api/v1/sites/{САЙТ}/settings", headers=заголовки, body=тело)


def test_повтор_с_тем_же_ключом_и_телом_не_применяет_дважды(api, песочница):
    тело = {"changes": {"keep_releases": 5}}
    первый = _патч(api, тело, "key-1")
    assert первый.status == 200 and первый.body["applied"] is True

    второй = _патч(api, тело, "key-1")
    assert второй.status == 200
    assert второй.body.get("idempotentReplay") is True, "повтор не назван повтором"
    # Сравниваются значимые поля, а не весь ответ: correlationId у каждого
    # запроса свой, и требовать его совпадения значило бы требовать, чтобы два
    # разных запроса выглядели одним.
    for поле in ("applied", "diff", "version", "previousVersion"):
        assert второй.body.get(поле) == первый.body.get(поле), (
            f"{поле} у повтора другое — значит, он выполнился заново")
    assert _профиль(песочница)["keep_releases"] == 5


def test_тот_же_ключ_с_другим_телом_отклонён(api, песочница):
    _патч(api, {"changes": {"keep_releases": 5}}, "key-2")
    другой = _патч(api, {"changes": {"keep_releases": 9}}, "key-2")
    assert другой.status >= 400
    assert "idempotency" in json.dumps(другой.body, ensure_ascii=False)
    assert _профиль(песочница)["keep_releases"] == 5, "второе тело всё-таки применилось"


def test_негодный_ключ_отвергается_названной_причиной(api):
    ответ = _патч(api, {"changes": {"keep_releases": 3}}, "../../побег")
    assert ответ.status == 400
    assert ответ.body["error"]["code"] == "invalid_idempotency_key"


def test_сухой_прогон_ключ_не_занимает(api, песочница):
    """Пробный запуск ничего не меняет: занять под него ключ — запретить боевое."""
    сухой = _патч(api, {"changes": {"keep_releases": 8}, "dryRun": True}, "key-3")
    assert сухой.body["dryRun"] is True
    боевой = _патч(api, {"changes": {"keep_releases": 8}}, "key-3")
    assert боевой.body["applied"] is True
    assert _профиль(песочница)["keep_releases"] == 8


def test_разные_ключи_применяются_каждый(api, песочница):
    _патч(api, {"changes": {"keep_releases": 4}}, "key-4")
    _патч(api, {"changes": {"keep_releases": 6}}, "key-5")
    assert _профиль(песочница)["keep_releases"] == 6


def test_читающий_запрос_ключа_не_требует(api):
    ответ = api.handle("GET", f"/api/v1/settings/{САЙТ}", headers=ЗАГОЛОВКИ, body=None)
    assert ответ.status == 200
