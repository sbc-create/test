"""REQ-SITE-IDENTIFIERS: идентификаторы витрины управляются, а не правятся руками.

Номер счётчика, партнёрский идентификатор, список разрешённых источников и
расписание обновления меняются без выкладки — они подставляются при отрисовке
или читаются службой. Значит, им место в управляемых настройках, а не в правке
файла по SSH: правка по SSH не проходит проверку, не попадает в журнал и не
откатывается.

Проверяется не «поле сохранилось», а границы: идентификатор с посторонними
символами уедет в разметку страницы как есть, а расписание чаще одиннадцати
минут означает, что следующий обход начнётся до конца предыдущего.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from factory.paths import PATHS
from factory.site_engine.api.control import ControlApi

REPO = Path(__file__).resolve().parents[2]
САЙТ = "lords-01"
ТОКЕН = "tok-rw"
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


def _патч(api, changes):
    return api.handle("PATCH", f"/api/v1/sites/{САЙТ}/settings", headers=ЗАГОЛОВКИ,
                      body={"changes": changes})


def _профиль(песочница):
    return json.loads(
        (песочница / "config" / "site-profiles" / f"{САЙТ}.json").read_text(encoding="utf-8"))


@pytest.mark.parametrize("ключ,значение", [
    ("analytics_counter_id", "12345678"),
    ("advertising_partner_id", "partner-42"),
    ("content_sources_allowed", ["cdnvideohub", "fixture"]),
    ("refresh_interval_minutes", 30),
])
def test_идентификаторы_меняются_через_api(api, песочница, ключ, значение):
    ответ = _патч(api, {ключ: значение})
    assert ответ.status == 200, ответ.body
    assert ответ.body["applied"] is True
    assert _профиль(песочница)[ключ] == значение


@pytest.mark.parametrize("ключ,значение,что", [
    ("analytics_counter_id", "<script>alert(1)</script>", "разметка в идентификаторе"),
    ("analytics_counter_id", "x" * 100, "идентификатор длиной в сотню символов"),
    ("advertising_partner_id", "партнёр 42", "пробелы и кириллица"),
    ("content_sources_allowed", ["ЧТО-УГОДНО"], "источник вне допустимых"),
    ("content_sources_allowed", ["a"] * 20, "двадцать источников"),
    ("refresh_interval_minutes", 1, "обновление чаще, чем длится обход"),
    ("refresh_interval_minutes", 100000, "обновление раз в два месяца"),
])
def test_негодные_значения_отклонены_с_объяснением(api, песочница, ключ, значение, что):
    ответ = _патч(api, {ключ: значение})
    assert ответ.status == 422, f"{что}: принято"
    беды = ответ.body["error"].get("problems") or []
    assert any(ключ in str(б) for б in беды), f"{что}: отказ не называет поле"
    assert ключ not in _профиль(песочница), f"{что}: значение всё-таки записано"


def test_все_нарушения_называются_сразу(api):
    ответ = _патч(api, {"analytics_counter_id": "x" * 100,
                        "refresh_interval_minutes": 1,
                        "content_sources_allowed": ["ПЛОХО"]})
    беды = ответ.body["error"].get("problems") or []
    assert len(беды) >= 3, (
        "отказ по одному полю за запрос превращает исправление в переписку")


def test_сухой_прогон_показывает_разницу_и_не_пишет(api, песочница):
    ответ = api.handle("PATCH", f"/api/v1/sites/{САЙТ}/settings", headers=ЗАГОЛОВКИ,
                       body={"changes": {"analytics_counter_id": "999"}, "dryRun": True})
    assert ответ.body["dryRun"] is True
    assert ответ.body["diff"]["analytics_counter_id"]["after"] == "999"
    assert "analytics_counter_id" not in _профиль(песочница)


def test_изменение_попадает_в_журнал(api, песочница):
    from factory import audit

    _патч(api, {"analytics_counter_id": "555"})
    записи = [з for з in audit.read_all() if "settings" in str(з.get("action", ""))]
    assert записи, "изменение идентификатора не записано в журнал"
    последняя = записи[-1]
    assert последняя.get("site_id") == САЙТ
    # Значение в журнале есть, секретов там нет и быть не может.
    assert "analytics_counter_id" in json.dumps(последняя, ensure_ascii=False)
