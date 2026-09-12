"""SUITE_2 — законный путь выкладки релиза шаблона на изолированный стенд.

По одному набору изменений на site_id. Подстановочных и многосайтовых
разрешений нет: разрешение, покрывающее несколько витрин, лишает возможности
сказать, на какой из них действие было позволено.
"""
from __future__ import annotations

import json
import urllib.error
import urllib.request

import pytest

from factory.site_engine.changeset import engine as E
from factory.site_engine.changeset import model as M
from factory.site_engine.changeset import store as S
from factory.site_engine.provisioner import grant as G
from factory.site_engine.provisioner.templates_executor import TemplatesExecutor

from .conftest import ВИТРИНЫ, ОКРУЖЕНИЕ_СТЕНДА, через_час

РЕСУРС = "template.release"
#: Кандидаты, собранные этим заданием. Отпечатки берутся из файла, а не
#: вписываются в тест: вписанное значение перестаёт проверять сборку.
КАНДИДАТЫ = json.load(open("artifacts/zone-tpl-001/candidate-artifacts.json",
                           encoding="utf-8"))
ПО_САЙТУ = {s: (продукт, св) for продукт, св in КАНДИДАТЫ.items()
            for s in св["site_ids"]}


class ФейковыйСтенд:
    """Изолированная цель: какой артефакт сейчас разложен на витрине."""

    provider_type = "template"
    resource_kind = "counter_tag"          # род цели мостика контура
    live_writes = False

    def __init__(self) -> None:
        self.состояние: dict[str, str] = {}
        self.эффекты: list[dict] = []
        self.откаты: list[dict] = []

    def разложить(self, site_id: str, digest: str) -> dict:
        прежний = self.состояние.get(site_id)
        if прежний == digest:
            return {"changed": False, "artifact": digest,
                    "rollback_artifact": прежний}
        self.состояние[site_id] = digest
        self.эффекты.append({"site_id": site_id, "artifact": digest,
                             "rollback_artifact": прежний})
        return {"changed": True, "artifact": digest,
                "rollback_artifact": прежний}

    def откатить(self, site_id: str) -> dict:
        эффект = next((э for э in reversed(self.эффекты)
                       if э["site_id"] == site_id), None)
        if эффект is None:
            return {"rolled_back": False}
        self.состояние[site_id] = эффект["rollback_artifact"]
        self.откаты.append({"site_id": site_id,
                            "restored": эффект["rollback_artifact"]})
        return {"rolled_back": True, "artifact": эффект["rollback_artifact"]}

    def эффектов(self, site_id: str | None = None) -> int:
        return len([э for э in self.эффекты
                    if site_id is None or э["site_id"] == site_id])


def создать_набор(стенд, site_id: str, *, ключ: str):
    продукт, св = ПО_САЙТУ[site_id]
    запись = стенд["реестр"].сайт(site_id)
    заявка = {
        "resource_type": РЕСУРС,
        "resource_id": f"{site_id}:template-release",
        "operation_type": "publish",
        "target_site_ids": [site_id],          # ровно одна витрина
        "idempotency_key": ключ,
        "correlation_id": f"zone-tpl-001-{site_id}",
        "requested_change": {
            "site_id": site_id,
            "environment": запись["environment"],
            "artifact_digest": св["artifact_sha256"],
            "route_map_hash": св["route_map_sha256"],
            "routes": св["routes"],
            "product": продукт},
    }
    создано = S.создать(стенд["соед"], заявка, producer_service="templates",
                        actor_id="service:templates", actor_type="SERVICE")
    return создано["changeset_id"], св


class АдаптерРелиза:
    """Мостик между контуром и изолированным стендом."""

    owner_service = "templates"

    def __init__(self, цель: ФейковыйСтенд, digest: str, карта: str) -> None:
        self.цель, self.digest, self.карта = цель, digest, карта
        self.resource_type = РЕСУРС
        self.changeset_id = None

    def capabilities(self):
        return {"owner_service": self.owner_service,
                "resource_types": [РЕСУРС],
                "operations": ["publish", "rollback"],
                "reversible": True, "dry_run": True}

    def observe(self, *, site_id, resource_id):
        текущий = self.цель.состояние.get(site_id)
        состояние = {"artifact": текущий, "route_map": self.карта if текущий else None}
        import hashlib
        отпечаток = "sha256:" + hashlib.sha256(
            json.dumps(состояние, sort_keys=True).encode()).hexdigest()[:32]
        return {"state": состояние, "fingerprint": отпечаток,
                "resource_type": РЕСУРС, "resource_id": resource_id,
                "site_id": site_id}

    def plan(self, *, site_id, resource_id, operation, requested_change, observed):
        import hashlib
        целевое = {"artifact": self.digest, "route_map": self.карта}
        ожидаемый = "sha256:" + hashlib.sha256(
            json.dumps(целевое, sort_keys=True).encode()).hexdigest()[:32]
        пусто = observed["state"].get("artifact") == self.digest
        return {"diff": {} if пусто else {"artifact": self.digest},
                "empty": пусто, "reversible": True,
                "before_state": observed["state"],
                "before_fingerprint": observed["fingerprint"],
                "expected_state": целевое, "expected_fingerprint": ожидаемый,
                "resource_id": resource_id, "operation": operation}

    def dry_run(self, *, site_id, plan):
        до = self.цель.эффектов()
        итог = {"effects": 0, "would_change": plan["diff"]}
        assert self.цель.эффектов() == до
        return итог

    def apply(self, *, site_id, plan, fencing_token):
        r = self.цель.разложить(site_id, self.digest)
        return {"applied": True, "idempotent_replay": not r["changed"],
                "effects": 1 if r["changed"] else 0,
                "external_id": f"{site_id}:{self.digest[:12]}",
                "rollback_artifact": r["rollback_artifact"],
                "fencing_token": fencing_token}

    def verify(self, *, site_id, plan, observed):
        свежее = self.observe(site_id=site_id, resource_id=plan["resource_id"])
        совпало = свежее["fingerprint"] == plan["expected_fingerprint"]
        return {"ok": совпало, "verified": совпало,
                "reason": "" if совпало else "артефакт на стенде не тот",
                "observed_fingerprint": свежее["fingerprint"],
                "expected_fingerprint": plan["expected_fingerprint"],
                "evidence": ["observed_state"]}

    def rollback(self, *, site_id, plan, before_fingerprint, fencing_token):
        r = self.цель.откатить(site_id)
        стало = self.observe(site_id=site_id, resource_id=plan["resource_id"])
        return {"rolled_back": стало["fingerprint"] == before_fingerprint,
                "effects": 1 if r.get("rolled_back") else 0}


def провести(стенд, цель, site_id, *, ключ):
    from factory.site_engine.changeset.registry_client import RegistryClient
    cid, св = создать_набор(стенд, site_id, ключ=ключ)
    адаптер = АдаптерРелиза(цель, св["artifact_sha256"], св["route_map_sha256"])
    адаптер.changeset_id = cid
    движок = E.Engine(стенд["соед"], адаптер=адаптер,
                      реестр=RegistryClient(стенд["registry_base"]),
                      требовать_журнал=False)
    движок.валидировать(cid, actor_id="service:control-plane",
                        служба="control-plane")
    движок.запросить_одобрение(cid, actor_id="service:templates",
                               служба="templates", expires_at=через_час())
    движок.одобрить(cid, approver_id="human:staging-approver",
                    служба="human_owner", actor_type="HUMAN",
                    expires_at=через_час())
    аренда = S.взять_аренду(стенд["соед"], cid, "changeset-worker")
    return cid, движок, адаптер, аренда["fencing_token"], св


def просить_grant(стенд, cid, *, маркер, audience="templates-executor",
                  вызывающий="changeset-worker"):
    токен = стенд["ключи"]["caller_tokens"].get(вызывающий, "unknown")
    зпр = urllib.request.Request(
        стенд["signer"].база + "/grant", method="POST",
        data=json.dumps({"changeset_id": cid, "audience": audience,
                         "fencing_token": маркер}).encode(),
        headers={"Content-Type": "application/json",
                 "Authorization": "Bearer " + токен})
    try:
        with urllib.request.urlopen(зпр, timeout=15) as о:
            return о.status, json.loads(о.read() or b"{}")
    except urllib.error.HTTPError as ош:
        return ош.code, json.loads(ош.read() or b"{}")


def набор_ключей(стенд):
    from factory.site_engine.approval import keyring as K
    from factory.site_engine.approval import service as SIGNER
    return K.НаборКлючей.из_json(
        (стенд["tmp"] / "credentials" / SIGNER.НАБОР).read_text("utf-8"))


def ожидания(стенд, cid, набор, план, маркер, св, site_id) -> G.Ожидания:
    import hashlib
    return G.Ожидания(
        changeset_id=cid, site_id=site_id, resource_kind=РЕСУРС,
        plan_hash=набор["plan_hash"],
        artifact_digest=план["expected_fingerprint"],
        registry_fingerprint=hashlib.sha256(
            f"registry-version:{стенд['реестр'].версия()}".encode()).hexdigest()[:16],
        fencing_token=маркер)


# =============================================================================

class TestЗаконныйПутьВыкладки:
    @pytest.mark.parametrize("site_id", [s for s, _ in ВИТРИНЫ])
    def test_один_эффект_на_витрину(self, стенд, site_id):
        цель = ФейковыйСтенд()
        cid, движок, адаптер, маркер, св = провести(стенд, цель, site_id,
                                                    ключ=f"zone-{site_id}")
        код, тело = просить_grant(стенд, cid, маркер=маркер)
        assert код == 200, тело
        разрешение = тело["grant"]
        assert разрешение["site_id"] == site_id
        assert разрешение["resource_kind"] == РЕСУРС
        assert разрешение["environment"] == ОКРУЖЕНИЕ_СТЕНДА
        assert разрешение["target_site_ids"] == [site_id], "разрешение на один сайт"

        набор = S.получить(стенд["соед"], cid)
        план = набор["dry_run_result"]["per_site_plan"][site_id]
        исполнитель = TemplatesExecutor(стенд["tmp"] / f"e-{site_id}.sqlite3",
                                        адаптер, набор_ключей(стенд))
        исход = исполнитель.выполнить(
            подпись=тело["signature"], полезное=разрешение,
            ожидания=ожидания(стенд, cid, набор, план, маркер, св, site_id),
            план=план, idempotency_key=разрешение["idempotency_key"])
        assert исход.applied and исход.effects == 1
        assert цель.эффектов(site_id) == 1
        assert цель.состояние[site_id] == св["artifact_sha256"]

        итог = движок.применить(cid, actor_id="service:control-plane",
                                служба="control-plane", fencing_token=маркер)
        assert итог["status"] == M.SUCCEEDED
        assert цель.эффектов(site_id) == 1, "контур не удвоил эффект"

    def test_повтор_не_добавляет_эффекта(self, стенд):
        site_id = "zona-01"
        цель = ФейковыйСтенд()
        cid, _, адаптер, маркер, св = провести(стенд, цель, site_id,
                                               ключ="zone-replay")
        _, тело = просить_grant(стенд, cid, маркер=маркер)
        набор = S.получить(стенд["соед"], cid)
        план = набор["dry_run_result"]["per_site_plan"][site_id]
        исполнитель = TemplatesExecutor(стенд["tmp"] / "e-replay.sqlite3",
                                        адаптер, набор_ключей(стенд))
        общее = dict(подпись=тело["signature"], полезное=тело["grant"],
                     ожидания=ожидания(стенд, cid, набор, план, маркер, св,
                                       site_id), план=план,
                     idempotency_key=тело["grant"]["idempotency_key"])
        первый = исполнитель.выполнить(**общее)
        второй = исполнитель.выполнить(**общее)
        assert (первый.effects, второй.effects) == (1, 0)
        assert второй.replay is True
        assert цель.эффектов(site_id) == 1

    def test_откат_и_возврат_вперёд(self, стенд):
        site_id = "zona-01"
        цель = ФейковыйСтенд()
        цель.состояние[site_id] = "предыдущий-артефакт"
        cid, движок, адаптер, маркер, св = провести(стенд, цель, site_id,
                                                    ключ="zone-rollback")
        набор = S.получить(стенд["соед"], cid)
        план = набор["dry_run_result"]["per_site_plan"][site_id]
        _, тело = просить_grant(стенд, cid, маркер=маркер)
        исполнитель = TemplatesExecutor(стенд["tmp"] / "e-rb.sqlite3", адаптер,
                                        набор_ключей(стенд))
        исполнитель.выполнить(
            подпись=тело["signature"], полезное=тело["grant"],
            ожидания=ожидания(стенд, cid, набор, план, маркер, св, site_id),
            план=план, idempotency_key=тело["grant"]["idempotency_key"])
        assert цель.состояние[site_id] == св["artifact_sha256"]

        # Откат возвращает ровно прежний артефакт.
        адаптер.rollback(site_id=site_id, plan=план,
                         before_fingerprint=план["before_fingerprint"],
                         fencing_token=маркер)
        assert цель.состояние[site_id] == "предыдущий-артефакт"

        # Возврат вперёд: тот же кандидат раскладывается снова.
        адаптер.apply(site_id=site_id, plan=план, fencing_token=маркер)
        assert цель.состояние[site_id] == св["artifact_sha256"]

    def test_подстановочных_и_многосайтовых_наборов_нет(self, стенд):
        """Набор на две витрины сразу к выдаче разрешения не допускается."""
        заявка = {"resource_type": РЕСУРС, "resource_id": "multi",
                  "operation_type": "publish",
                  "target_site_ids": ["zona-01", "animedia-01"],
                  "idempotency_key": "zone-multi",
                  "correlation_id": "zone-multi", "requested_change": {}}
        создано = S.создать(стенд["соед"], заявка, producer_service="templates",
                            actor_id="service:templates", actor_type="SERVICE")
        код, тело = просить_grant(стенд, создано["changeset_id"], маркер=1)
        assert код in (409, 422), тело
        assert тело["error_code"] in ("CHANGESET_STATE_INVALID",
                                      "GRANT_SINGLE_TARGET_REQUIRED")

    def test_production_отвергается(self, стенд):
        site_id = "zona-01"
        цель = ФейковыйСтенд()
        cid, _, _, маркер, _ = провести(стенд, цель, site_id, ключ="zone-prod")
        стенд["реестр"].сменить_окружение(site_id, "production")
        код, тело = просить_grant(стенд, cid, маркер=маркер)
        assert код == 403, тело
        assert тело["error_code"] == "PRODUCTION_APPLY_DISABLED"
        assert цель.эффектов(site_id) == 0


class TestНеизменностьПлеера:
    def test_отпечаток_плеера_совпадает_с_релизом(self):
        """Кандидат не трогает ни код плеера, ни его разметку."""
        import hashlib
        import pathlib
        import re
        живой = pathlib.Path("/srv/lords/zona-01/current/site")
        кандидат = pathlib.Path("var/candidate-v2/zona-cinema")
        assert живой.is_dir() and кандидат.is_dir()
        a = hashlib.sha256((живой / "assets/app.js").read_bytes()).hexdigest()
        b = hashlib.sha256((кандидат / "assets/app.js").read_bytes()).hexdigest()
        assert a == b, "код витрины (и плеер в нём) изменился"

        ПЛЕЕР = re.compile(
            r'(<iframe[^>]*>|data-player[^\s>]*|class="[^"]*player[^"]*")', re.I)

        def разметка(корень):
            каталог = корень / "title"
            for п in sorted(x for x in каталог.iterdir() if x.is_dir()):
                ф = п / "index.html"
                if ф.is_file():
                    найдено = ПЛЕЕР.findall(ф.read_text("utf-8", errors="replace"))
                    if найдено:
                        return hashlib.sha256(
                            "|".join(sorted(set(найдено))).encode()).hexdigest()
            return None
        assert разметка(живой) == разметка(кандидат), "разметка плеера изменилась"
