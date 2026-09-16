"""REQ-TENANT-ISOLATION: тенант проверяется, а не принимается на слово.

Принадлежность у оператора появилась, но управляющий слой её пока не знает:
любой обладатель права `read` мог запросить любую витрину, назвав её в адресе.
Пока это так, изоляция существует только в каталоге людей.

Правило одно и оно жёсткое: **ни адрес, ни поле формы, ни тело запроса не
меняют тенанта**. Проверенная принадлежность приходит из сессии; параметр
запроса может лишь сузить видимое до уже разрешённого.

Отдельно проверяется супер-администратор: он переключается **явно и под
запись**, а не открытием страницы соседа. Переключение, происходящее само,
неотличимо от его отсутствия — по журналу не понять, кто и что смотрел.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from factory.paths import PATHS
from factory.site_engine.api.control import ControlApi

СВОЙ = "lords-01"
ЧУЖОЙ = "lords-02"
МЕСТНЫЙ = "tok-local"
СУПЕР = "tok-super"
REPO = Path(__file__).resolve().parents[2]

ENV = {
    "SITE_ENGINE_CONTROL_WRITES": "1",
    "SITE_ENGINE_CONTROL_TOKENS": (
        f"{МЕСТНЫЙ}=read,jobs:write,config:write,audit:read,review:write@{СВОЙ}"
        f"|{СУПЕР}=read,jobs:write,config:write,audit:read,operators:write"
    ),
    "SITE_ENGINE_CATALOG_DIR": "var/lords/lords/catalog-cache",
}
H_МЕСТНЫЙ = {"Authorization": f"Bearer {МЕСТНЫЙ}", "X-Site-Id": СВОЙ}
H_СУПЕР = {"Authorization": f"Bearer {СУПЕР}"}


@pytest.fixture
def sandbox(tmp_path, monkeypatch):
    monkeypatch.setattr(PATHS, "root", tmp_path)
    профили = tmp_path / "config" / "site-profiles"
    профили.mkdir(parents=True)
    образец = json.loads(
        (REPO / "config" / "site-profiles" / "lords-01.json").read_text(encoding="utf-8")
    )
    for сайт in (СВОЙ, ЧУЖОЙ):
        d = dict(образец)
        d.update({"site_id": сайт, "domains": [f"{сайт}.test"], "canonical_host": f"{сайт}.test"})
        (профили / f"{сайт}.json").write_text(json.dumps(d, ensure_ascii=False), encoding="utf-8")
    кэш = tmp_path / "var" / "lords" / "lords" / "catalog-cache"
    кэш.mkdir(parents=True)
    for сайт in (СВОЙ, ЧУЖОЙ):
        (кэш / f"{сайт}.json").write_text(
            json.dumps(
                {
                    "fetched_at_ms": 1788669932935,
                    "source": "test",
                    "items": [
                        {
                            "external_id": f"e-{сайт}",
                            "name": f"Запись {сайт}",
                            "type": "movie",
                            "playback": {"aggregator": "kp", "title_id": "1"},
                        }
                    ],
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
    for под in ("queue/inbox", "var/locks", "var/audit", "var/state", "artifacts/jobs"):
        (tmp_path / под).mkdir(parents=True, exist_ok=True)
    return tmp_path


@pytest.fixture
def api(sandbox):
    return ControlApi(root=sandbox, env=ENV)


class TestПривязанныйНеВидитСоседа:
    #: Маршруты, у которых витрина стоит в адресе. Проверяются все, а не один
    #: вспомненный: пропущенный маршрут — это дыра ровно там, где её не искали.
    ЧИТАЮЩИЕ = [
        f"/api/v1/site-status/{ЧУЖОЙ}",
        f"/api/v1/settings/{ЧУЖОЙ}",
        f"/api/v1/join-keys/{ЧУЖОЙ}",
        f"/api/v1/ratings/{ЧУЖОЙ}",
        f"/api/v1/content/{ЧУЖОЙ}",
        f"/api/v1/content-health/{ЧУЖОЙ}",
    ]

    @pytest.mark.parametrize("путь", ЧИТАЮЩИЕ)
    def test_чужая_витрина_в_адресе_отклонена(self, api, путь):
        ответ = api.handle("GET", путь, headers=H_МЕСТНЫЙ)
        assert ответ.status == 403, f"{путь}: {ответ.status}"
        assert ответ.body["error"]["code"] == "cross_tenant"

    def test_своя_витрина_доступна(self, api):
        assert api.handle("GET", f"/api/v1/site-status/{СВОЙ}", headers=H_МЕСТНЫЙ).status == 200

    def test_чужая_витрина_в_теле_отклонена(self, api):
        ответ = api.handle(
            "POST", f"/api/v1/sites/{ЧУЖОЙ}/jobs",
            headers=H_МЕСТНЫЙ, body={"action": "reindex", "dryRun": True},
        )
        assert ответ.status == 403
        assert ответ.body["error"]["code"] == "cross_tenant"

    def test_журнал_ограничен_своей_витриной(self, api):
        """Журнал без области видимости показывает соседа так же, как каталог."""
        from factory import audit

        for сайт in (СВОЙ, ЧУЖОЙ):
            audit.record(
                job_id="j", site_id=сайт, environment="test", action="control.test",
                target="t", exit_code=0, extra={"actor": "кто-то"},
            )
        тело = api.handle("GET", "/api/v1/audit", headers=H_МЕСТНЫЙ, body={"limit": 100}).body
        сайты = {з.get("site_id") for з in тело["entries"]}
        assert сайты <= {СВОЙ, ""}, f"в журнале видны чужие витрины: {сайты}"

    def test_список_витрин_ограничен(self, api):
        тело = api.handle("GET", "/api/v1/sites-status", headers=H_МЕСТНЫЙ).body
        видно = {с.get("siteId") for с in тело.get("items") or []}
        assert видно == {СВОЙ}, f"видны чужие витрины: {видно}"


class TestСуперАдминистратор:
    def test_видит_все_витрины(self, api):
        тело = api.handle("GET", "/api/v1/sites-status", headers=H_СУПЕР).body
        видно = {с.get("siteId") for с in тело.get("items") or []}
        assert {СВОЙ, ЧУЖОЙ} <= видно

    def test_читает_любую_витрину(self, api):
        for сайт in (СВОЙ, ЧУЖОЙ):
            assert api.handle("GET", f"/api/v1/site-status/{сайт}", headers=H_СУПЕР).status == 200

    def test_переключение_записывается(self, api):
        """Явное переключение — действие, а не побочный эффект открытия страницы."""
        from factory import audit

        ответ = api.handle(
            "POST", "/api/v1/tenant-switch", headers=H_СУПЕР, body={"siteId": ЧУЖОЙ}
        )
        assert ответ.status == 200
        assert ответ.body["siteId"] == ЧУЖОЙ
        записи = [з for з in audit.read_all() if з.get("action") == "control.tenant.switch"]
        assert записи, "переключение обязано попадать в журнал"
        assert записи[-1]["site_id"] == ЧУЖОЙ

    def test_переключение_на_несуществующее_отклонено(self, api):
        ответ = api.handle(
            "POST", "/api/v1/tenant-switch", headers=H_СУПЕР, body={"siteId": "нет-такой"}
        )
        assert ответ.status in (400, 404)

    def test_привязанный_не_переключается(self, api):
        ответ = api.handle(
            "POST", "/api/v1/tenant-switch", headers=H_МЕСТНЫЙ, body={"siteId": ЧУЖОЙ}
        )
        assert ответ.status == 403


class TestЗаголовокНеПодменяетПрава:
    def test_чужой_заголовок_не_расширяет_видимость(self, api):
        """Заголовок сужает, но не расширяет.

        Если бы принадлежность бралась из заголовка целиком, любой обладатель
        права read назначал бы себе витрину сам — и проверка тенанта стала бы
        проверкой вежливости.
        """
        подделка = {"Authorization": f"Bearer {МЕСТНЫЙ}", "X-Site-Id": ЧУЖОЙ}
        ответ = api.handle("GET", f"/api/v1/site-status/{ЧУЖОЙ}", headers=подделка)
        assert ответ.status == 403

    def test_без_заголовка_привязанный_остаётся_привязанным(self, api):
        """Принадлежность живёт в токене сессии, а не в заголовке запроса."""
        без = {"Authorization": f"Bearer {МЕСТНЫЙ}"}
        ответ = api.handle("GET", f"/api/v1/site-status/{ЧУЖОЙ}", headers=без)
        assert ответ.status == 403
