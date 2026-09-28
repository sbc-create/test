"""REQ-SELF-SERVICE-PROVISION: подтверждение, выкладка, канарейка и откат.

План без исполнения — это схема. Цикл доводит заявку до работающей витрины и
обратно, и почти каждая проверка здесь написана на конкретный способ соврать.

**Подтверждают именно тот план, который выполнится.** Подтверждение привязано к
отпечатку: если между показом и подтверждением ответы изменились, подтверждение
недействительно. Иначе «сравните и подтвердите» подтверждает прошлое.

**Повтор запроса не создаёт вторую витрину.** Ключ идемпотентности возвращает то
же задание. Пользователь, нажавший кнопку дважды, не должен получать два сайта
на один домен — и не должен получать отказ, из которого непонятно, создалось ли
что-то в первый раз.

**Два процесса не занимают один домен.** Занятие домена атомарно: второй
получает отказ, а не вторую запись.

**Канарейка не индексируется и не видна как боевая витрина.** Она живёт в
отдельном наложении, а не в каталоге профилей: витрина, попавшая в общий
каталог, начинает участвовать в обходах и полках раньше, чем её проверили.

**Откат возвращает состояние полностью.** Проверяется снимком каталога до и
после: не «откат отработал без ошибки», а «ничего не осталось».
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from factory.paths import PATHS
from factory.site_engine.api.control import ControlApi

СОСЕД = "js-site"
ПИШУЩИЙ = "tok-w"
ЧИТАЮЩИЙ = "tok-r"
ENV = {
    "SITE_ENGINE_CONTROL_WRITES": "1",
    "SITE_ENGINE_CONTROL_TOKENS": (
        f"{ПИШУЩИЙ}=read,jobs:write,audit:read,config:write,sites:create"
        f"|{ЧИТАЮЩИЙ}=read,audit:read"
    ),
}
H_W = {"Authorization": f"Bearer {ПИШУЩИЙ}"}
H_R = {"Authorization": f"Bearer {ЧИТАЮЩИЙ}"}
REPO = Path(__file__).resolve().parents[2]

ОТВЕТЫ = {
    "domain": {"domain": "novaya.test", "aliases": ""},
    "profile": {"environment": "staging", "targetRef": "local-disposable",
                "seoProfile": "catalog_authority"},
    "content": {"contentSource": "fixture", "contentTypes": "movies,series"},
    "template": {"themeRef": "portal_light"},
    "branding": {"brandName": "Новая", "legalName": "ООО Новая", "primaryColor": "#1f4fd8"},
    "seo": {"canonicalHostForm": "non_www", "trailingSlash": "1"},
    "analytics": {"analyticsRef": "secret://analytics/novaya", "adsRef": ""},
    "legal": {"legalEntity": "ООО Новая", "contactEmail": "legal@novaya.test",
              "rightsConfirmed": "1"},
}


@pytest.fixture
def sandbox(tmp_path, monkeypatch):
    monkeypatch.setattr(PATHS, "root", tmp_path)
    профили = tmp_path / "config" / "site-profiles"
    профили.mkdir(parents=True)
    образец = json.loads(
        (REPO / "config" / "site-profiles" / "lords-01.json").read_text(encoding="utf-8")
    )
    образец.update({"site_id": СОСЕД, "domains": ["taken.test"], "canonical_host": "taken.test"})
    (профили / f"{СОСЕД}.json").write_text(
        json.dumps(образец, ensure_ascii=False), encoding="utf-8"
    )
    for под in ("queue/inbox", "queue/done", "var/locks", "var/audit", "var/state", "sites"):
        (tmp_path / под).mkdir(parents=True, exist_ok=True)
    (tmp_path / "schemas").symlink_to(REPO / "schemas")
    (tmp_path / "knowledge").symlink_to(REPO / "knowledge")
    # Проверка пакета читает реестры: список публичных суффиксов нужен, чтобы
    # отличить домен второго уровня от третьего. Без них проверка падает
    # исключением, а не блокером, и заявка выглядит сломанной.
    (tmp_path / "inventory").symlink_to(REPO / "inventory")
    # Пресет пакета — часть поставки, а не деталь теста: без него мастер
    # собирает пакет из пустоты, и проверка ругается на всё сразу.
    (tmp_path / "config" / "site-request-presets").symlink_to(
        REPO / "config" / "site-request-presets"
    )
    return tmp_path


@pytest.fixture
def api(sandbox):
    return ControlApi(root=sandbox, env=ENV)


@pytest.fixture
def готовая(api):
    """Заявка, заполненная целиком: дальше проверяется исполнение."""
    rid = api.handle(
        "POST", "/api/v1/site-requests", headers=H_W, body={"siteId": "novaya"}
    ).body["requestId"]
    for шаг, ответы in ОТВЕТЫ.items():
        ответ = api.handle(
            "PATCH", f"/api/v1/site-requests/{rid}", headers=H_W,
            body={"step": шаг, "answers": ответы},
        )
        assert ответ.status == 200, (шаг, ответ.body)
    return rid


def отпечаток(api, rid: str) -> str:
    return api.handle("GET", f"/api/v1/site-requests/{rid}/plan", headers=H_W).body["planHash"]


def подтвердить(api, rid: str):
    return api.handle(
        "POST", f"/api/v1/site-requests/{rid}/approve", headers=H_W,
        body={"planHash": отпечаток(api, rid)},
    )


def выложить(api, rid: str, ключ: str = "k1"):
    return api.handle(
        "POST", f"/api/v1/site-requests/{rid}/provision",
        headers={**H_W, "idempotency-key": ключ}, body={},
    )


class TestПодтверждение:
    def test_подтверждение_привязано_к_отпечатку(self, api, готовая):
        assert подтвердить(api, готовая).status == 200
        тело = api.handle("GET", f"/api/v1/site-requests/{готовая}", headers=H_W).body
        assert тело["state"] == "APPROVED"

    def test_чужой_отпечаток_не_подтверждает(self, api, готовая):
        ответ = api.handle(
            "POST", f"/api/v1/site-requests/{готовая}/approve", headers=H_W,
            body={"planHash": "sha256:чужой"},
        )
        assert ответ.status == 409

    def test_изменение_ответов_снимает_подтверждение(self, api, готовая):
        подтвердить(api, готовая)
        api.handle(
            "PATCH", f"/api/v1/site-requests/{готовая}", headers=H_W,
            body={"step": "branding", "answers": {**ОТВЕТЫ["branding"], "brandName": "Иная"}},
        )
        тело = api.handle("GET", f"/api/v1/site-requests/{готовая}", headers=H_W).body
        assert тело["state"] == "DRAFT", "подтверждение прошлого плана не переносится на новый"

    def test_без_подтверждения_не_выкладывается(self, api, готовая):
        assert выложить(api, готовая).status == 409

    def test_читатель_не_подтверждает(self, api, готовая):
        ответ = api.handle(
            "POST", f"/api/v1/site-requests/{готовая}/approve", headers=H_R,
            body={"planHash": отпечаток(api, готовая)},
        )
        assert ответ.status == 403


class TestВыкладка:
    def test_создаёт_канарейку_и_задание(self, api, готовая, sandbox):
        подтвердить(api, готовая)
        ответ = выложить(api, готовая)
        assert ответ.status in (200, 202), ответ.body
        assert ответ.body["jobId"]
        наложение = sandbox / "var" / "state" / "canary-profiles" / "novaya.json"
        assert наложение.exists(), "канарейка живёт в наложении"
        assert not (sandbox / "config" / "site-profiles" / "novaya.json").exists(), (
            "канарейка не попадает в общий каталог профилей до проверки"
        )

    def test_канарейка_не_индексируется(self, api, готовая, sandbox):
        подтвердить(api, готовая)
        выложить(api, готовая)
        профиль = json.loads(
            (sandbox / "var" / "state" / "canary-profiles" / "novaya.json").read_text(
                encoding="utf-8"
            )
        )
        assert профиль["indexing_enabled"] is False
        assert профиль.get("noindex") is True

    def test_повтор_не_создаёт_вторую_витрину(self, api, готовая, sandbox):
        подтвердить(api, готовая)
        первый = выложить(api, готовая, "k1").body["jobId"]
        второй = выложить(api, готовая, "k1")
        assert второй.body["jobId"] == первый
        assert второй.body.get("idempotentReplay") is True
        канарейки = list((sandbox / "var" / "state" / "canary-profiles").glob("*.json"))
        assert len(канарейки) == 1

    def test_другой_ключ_на_ту_же_заявку_не_дублирует(self, api, готовая, sandbox):
        подтвердить(api, готовая)
        выложить(api, готовая, "k1")
        ответ = выложить(api, готовая, "k2")
        assert ответ.status in (200, 202, 409)
        канарейки = list((sandbox / "var" / "state" / "canary-profiles").glob("*.json"))
        assert len(канарейки) == 1, "вторая выкладка той же заявки не создаёт вторую витрину"

    def test_домен_занимается_атомарно(self, api, готовая, sandbox):
        подтвердить(api, готовая)
        выложить(api, готовая)
        бронь = sandbox / "var" / "state" / "domain-reservations" / "novaya.test.json"
        assert бронь.exists()
        # Вторая заявка на тот же домен обязана получить отказ на шаге домена.
        другая = api.handle(
            "POST", "/api/v1/site-requests", headers=H_W, body={"siteId": "vtoraya"}
        ).body["requestId"]
        ответ = api.handle(
            "PATCH", f"/api/v1/site-requests/{другая}", headers=H_W,
            body={"step": "domain", "answers": {"domain": "novaya.test"}},
        )
        assert ответ.status == 409

    def test_соседняя_витрина_не_тронута(self, api, готовая, sandbox):
        сосед = sandbox / "config" / "site-profiles" / f"{СОСЕД}.json"
        было = сосед.read_bytes()
        подтвердить(api, готовая)
        выложить(api, готовая)
        assert сосед.read_bytes() == было

    def test_видна_в_заданиях_и_журнале(self, api, готовая):
        подтвердить(api, готовая)
        job_id = выложить(api, готовая).body["jobId"]
        журнал = api.handle("GET", "/api/v1/audit", headers=H_W, body={"limit": 200}).body
        действия = [з.get("action") for з in журнал["entries"]]
        assert any("provision" in str(д) for д in действия)
        задания = api.handle("GET", "/api/v1/jobs", headers=H_W, body={"limit": 50}).body
        строки = json.dumps(задания, ensure_ascii=False)
        assert job_id in строки or "novaya" in строки


class TestПроверкаИПубликация:
    def test_проверки_называются_поимённо(self, api, готовая):
        подтвердить(api, готовая)
        выложить(api, готовая)
        итог = api.handle(
            "GET", f"/api/v1/site-requests/{готовая}/verification", headers=H_W
        ).body
        assert итог["checks"], "проверка без списка проверок — не проверка"
        assert all("id" in п and "passed" in п for п in итог["checks"])

    def test_публикация_требует_разрешения_владельца(self, api, готовая):
        подтвердить(api, готовая)
        выложить(api, готовая)
        ответ = api.handle(
            "POST", f"/api/v1/site-requests/{готовая}/publish", headers=H_W, body={}
        )
        assert ответ.status == 409
        assert "OWNER" in json.dumps(ответ.body, ensure_ascii=False).upper()


class TestОткат:
    def test_откат_убирает_всё_созданное(self, api, готовая, sandbox):
        снимок = lambda: sorted(  # noqa: E731
            str(p)
            for p in sandbox.rglob("*")
            if "site-requests" not in str(p)
            and "var/state/trace" not in str(p)
            and "var/audit" not in str(p)
            and "queue" not in str(p)
            and "idempotency" not in str(p)
            and "artifacts" not in str(p)
        )
        до = снимок()
        подтвердить(api, готовая)
        выложить(api, готовая)
        assert снимок() != до, "выкладка обязана что-то создать"
        ответ = api.handle(
            "POST", f"/api/v1/site-requests/{готовая}/rollback", headers=H_W, body={}
        )
        assert ответ.status == 200, ответ.body
        появилось = sorted(set(снимок()) - set(до))
        assert not появилось, f"после отката осталось: {появилось}"

    def test_после_отката_домен_свободен(self, api, готовая):
        подтвердить(api, готовая)
        выложить(api, готовая)
        api.handle("POST", f"/api/v1/site-requests/{готовая}/rollback", headers=H_W, body={})
        другая = api.handle(
            "POST", "/api/v1/site-requests", headers=H_W, body={"siteId": "vtoraya"}
        ).body["requestId"]
        ответ = api.handle(
            "PATCH", f"/api/v1/site-requests/{другая}", headers=H_W,
            body={"step": "domain", "answers": {"domain": "novaya.test"}},
        )
        assert ответ.status == 200

    def test_откат_без_выкладки_честно_отказывает(self, api, готовая):
        ответ = api.handle(
            "POST", f"/api/v1/site-requests/{готовая}/rollback", headers=H_W, body={}
        )
        assert ответ.status == 409

    def test_повторный_откат_не_ломается(self, api, готовая):
        подтвердить(api, готовая)
        выложить(api, готовая)
        api.handle("POST", f"/api/v1/site-requests/{готовая}/rollback", headers=H_W, body={})
        второй = api.handle(
            "POST", f"/api/v1/site-requests/{готовая}/rollback", headers=H_W, body={}
        )
        assert второй.status in (200, 409)


class TestКанарейкаВидна:
    def test_канареечная_витрина_отличима_от_боевой(self, api, готовая, sandbox):
        подтвердить(api, готовая)
        выложить(api, готовая)
        витрины = api.handle("GET", "/api/v1/sites-status", headers=H_W).body
        строки = {с.get("siteId"): с for с in витрины.get("items") or []}
        assert "novaya" in строки, "канарейка обязана быть видна оператору"
        assert строки["novaya"].get("canary") is True
        assert строки[СОСЕД].get("canary") is not True
