"""SUITE_1 — контракт разрешения на исполнение template.release.

Один положительный сквозной цикл через настоящие API и машину состояний и
восемь отрицательных случаев на границе. Служба подписи — подпроцесс того же
выложенного релиза: упрощённая ветка кода доказывала бы только сама себя.
"""
from __future__ import annotations

import datetime as _d
import json
import urllib.error
import urllib.request

import pytest

from factory.site_engine.changeset import engine as E
from factory.site_engine.changeset import model as M
from factory.site_engine.changeset import store as S
from factory.site_engine.provisioner import grant as G
from factory.site_engine.provisioner.changeset_adapter import ProviderTargetAdapter
from factory.site_engine.provisioner.intent import OnboardingIntent
from factory.site_engine.provisioner.mapping import Связи
from factory.site_engine.provisioner.providers import fake as F
from factory.site_engine.provisioner.templates_executor import TemplatesExecutor

from .conftest import через_час

РЕСУРС = "template.release"


# --- общая часть -------------------------------------------------------------

def намерение(site_id: str) -> OnboardingIntent:
    return OnboardingIntent.разобрать({
        "requested_by": "service:templates",
        "canonical_domain": f"{site_id}.invalid",
        "template_family": "yummy", "template_profile": "catalog-search",
        "language": "ru", "region": "RU",
        "correlation_id": f"core003-{site_id}",
        "idempotency_key": f"core003-{site_id}"})


def цель(стенд, метка: str = ""):
    мир = F.Мир()
    витрина = F.ФейковаяВитрина(мир)
    витрина.установить_счётчик(90000001)
    связи = Связи(str(стенд["tmp"] / f"links{метка}.sqlite3"))
    адаптер = ProviderTargetAdapter(витрина, намерение(стенд["site_id"]), связи,
                                    resource_type=РЕСУРС)
    return {"мир": мир, "витрина": витрина, "связи": связи, "адаптер": адаптер}


def approved(стенд, ц, *, ключ="core003-1", действие="publish"):
    """Templates предлагает, control-plane валидирует, одобряет человек."""
    заявка = {"resource_type": РЕСУРС,
              "resource_id": f"{стенд['site_id']}:release",
              "operation_type": действие,
              "target_site_ids": [стенд["site_id"]],
              "idempotency_key": ключ,
              "correlation_id": f"core003-{ключ}",
              "requested_change": {"canonical_domain":
                                   f"{стенд['site_id']}.invalid"}}
    создано = S.создать(стенд["соед"], заявка, producer_service="templates",
                        actor_id="service:templates", actor_type="SERVICE")
    cid = создано["changeset_id"]
    ц["адаптер"].changeset_id = cid
    движок = E.Engine(стенд["соед"], адаптер=ц["адаптер"],
                      реестр=_реестр(стенд), требовать_журнал=False)
    движок.валидировать(cid, actor_id="service:control-plane",
                        служба="control-plane")
    движок.запросить_одобрение(cid, actor_id="service:templates",
                               служба="templates", expires_at=через_час())
    движок.одобрить(cid, approver_id="human:test-approver",
                    служба="human_owner", actor_type="HUMAN",
                    expires_at=через_час())
    return cid, движок


def _реестр(стенд):
    from factory.site_engine.changeset.registry_client import RegistryClient
    return RegistryClient(стенд["registry_base"])


def просить_grant(стенд, cid: str, *, audience="templates-executor",
                  fencing_token: int, вызывающий="changeset-worker"):
    токен = стенд["ключи"]["caller_tokens"].get(вызывающий, "unknown-caller")
    зпр = urllib.request.Request(
        стенд["signer"].база + "/grant", method="POST",
        data=json.dumps({"changeset_id": cid, "audience": audience,
                         "fencing_token": fencing_token}).encode(),
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
    путь = стенд["tmp"] / "credentials" / SIGNER.НАБОР
    return K.НаборКлючей.из_json(путь.read_text("utf-8"))


def ожидания(стенд, cid, набор, план, маркер) -> G.Ожидания:
    import hashlib
    return G.Ожидания(
        changeset_id=cid, site_id=стенд["site_id"], resource_kind=РЕСУРС,
        plan_hash=набор["plan_hash"],
        artifact_digest=план["expected_fingerprint"],
        registry_fingerprint=hashlib.sha256(
            f"registry-version:{стенд['реестр'].версия()}".encode()).hexdigest()[:16],
        fencing_token=маркер)


# =============================================================================
# Положительный сквозной цикл
# =============================================================================

class TestЗаконныйЦикл:
    def test_полный_цикл_до_терминального_состояния(self, стенд):
        ц = цель(стенд)
        cid, движок = approved(стенд, ц)
        аренда = S.взять_аренду(стенд["соед"], cid, "changeset-worker")
        маркер = аренда["fencing_token"]
        набор = S.получить(стенд["соед"], cid)
        план = набор["dry_run_result"]["per_site_plan"][стенд["site_id"]]

        # Разрешение просит рабочий процесс контура — не предлагающий и не
        # исполнитель.
        код, тело = просить_grant(стенд, cid, fencing_token=маркер)
        assert код == 200, тело
        разрешение = тело["grant"]
        assert разрешение["audience"] == "templates-executor"
        assert разрешение["resource_kind"] == РЕСУРС
        assert разрешение["action"] == "publish"
        assert разрешение["environment"] == "test"
        for притязание in G.ОБЯЗАТЕЛЬНЫЕ:
            assert разрешение.get(притязание), f"нет притязания {притязание}"

        исполнитель = TemplatesExecutor(стенд["tmp"] / "exec.sqlite3",
                                        ц["адаптер"], набор_ключей(стенд))
        исход = исполнитель.выполнить(
            подпись=тело["signature"], полезное=разрешение,
            ожидания=ожидания(стенд, cid, набор, план, маркер), план=план,
            idempotency_key=разрешение["idempotency_key"])
        assert исход.applied and исход.effects == 1

        наблюдение = ц["адаптер"].observe(site_id=стенд["site_id"],
                                          resource_id=набор["resource_id"])
        сверка = ц["адаптер"].verify(site_id=стенд["site_id"], plan=план,
                                     observed=наблюдение)
        assert сверка["ok"] is True

        итог = движок.применить(cid, actor_id="service:control-plane",
                                служба="control-plane", fencing_token=маркер)
        assert итог["status"] == M.SUCCEEDED
        assert M.SUCCEEDED in M.ТЕРМИНАЛЬНЫЕ
        assert ц["мир"].эффектов("create") == 1

    def test_разделение_обязанностей(self, стенд):
        ц = цель(стенд, "-sod")
        cid, _ = approved(стенд, ц, ключ="core003-sod")
        набор = S.получить(стенд["соед"], cid)
        assert набор["actor_id"] == "service:templates"
        assert набор["approval"]["approver_id"] == "human:test-approver"
        assert набор["approval"]["approver_id"] != набор["actor_id"]
        аренда = S.взять_аренду(стенд["соед"], cid, "changeset-worker")
        _, тело = просить_grant(стенд, cid,
                                fencing_token=аренда["fencing_token"])
        assert тело["grant"]["subject"] == "templates-executor"
        assert тело["grant"]["issuer"] == "site-factory-approval-signer"

    def test_тестовый_ключ_не_доверен_боевым_набором(self, стенд):
        """Публичная часть тестового ключа отсутствует в боевом наборе."""
        боевой = json.loads(
            open("/etc/site-factory/credentials/approval-verify-keys").read()
            if False else "{}") if False else None
        with urllib.request.urlopen("http://127.0.0.1:8795/jwks", timeout=10) as о:
            боевой = json.loads(о.read())
        боевые_kid = {к["kid"] for к in боевой["keys"]}
        assert стенд["ключи"]["kid"] not in боевые_kid


# =============================================================================
# Восемь отрицательных случаев
# =============================================================================

class TestОтрицательные:
    def _подготовить(self, стенд, метка):
        ц = цель(стенд, метка)
        cid, движок = approved(стенд, ц, ключ=f"neg{метка}")
        аренда = S.взять_аренду(стенд["соед"], cid, "changeset-worker")
        набор = S.получить(стенд["соед"], cid)
        план = набор["dry_run_result"]["per_site_plan"][стенд["site_id"]]
        return ц, cid, движок, аренда["fencing_token"], набор, план

    def test_01_предлагающий_сам_просит_разрешение(self, стенд):
        ц, cid, _, маркер, _, _ = self._подготовить(стенд, "-1")
        код, тело = просить_grant(стенд, cid, fencing_token=маркер,
                                  вызывающий="control-api")
        assert код == 403 and тело["error_code"] == "CALLER_NOT_ALLOWED"
        assert ц["мир"].эффектов("create") == 0

    def test_02_исполнитель_пытается_выпустить_себе(self, стенд):
        ц, cid, _, маркер, _, _ = self._подготовить(стенд, "-2")
        код, тело = просить_grant(стенд, cid, fencing_token=маркер,
                                  вызывающий="templates-executor")
        assert код == 401 and тело["error_code"] == "UNAUTHENTICATED"
        assert ц["мир"].эффектов("create") == 0

    def test_03_недопустимое_состояние_набора(self, стенд):
        ц = цель(стенд, "-3")
        заявка = {"resource_type": РЕСУРС, "resource_id": "r", 
                  "operation_type": "publish",
                  "target_site_ids": [стенд["site_id"]],
                  "idempotency_key": "neg-3", "correlation_id": "neg-3",
                  "requested_change": {}}
        создано = S.создать(стенд["соед"], заявка, producer_service="templates",
                            actor_id="service:templates", actor_type="SERVICE")
        код, тело = просить_grant(стенд, создано["changeset_id"],
                                  fencing_token=1)
        assert код == 409 and тело["error_code"] == "CHANGESET_STATE_INVALID"
        assert ц["мир"].эффектов("create") == 0

    def test_04_старое_разрешение_без_новых_притязаний(self, стенд):
        """Разрешение прежнего образца исполнителем не принимается."""
        ц, cid, _, маркер, набор, план = self._подготовить(стенд, "-4")
        _, тело = просить_grant(стенд, cid, fencing_token=маркер)
        урезанное = {к: v for к, v in тело["grant"].items()
                     if к not in ("resource_kind", "artifact_digest", "jti")}
        исполнитель = TemplatesExecutor(стенд["tmp"] / "e4.sqlite3",
                                        ц["адаптер"], набор_ключей(стенд))
        with pytest.raises(G.GrantError) as ош:
            исполнитель.выполнить(подпись=тело["signature"], полезное=урезанное,
                                  ожидания=ожидания(стенд, cid, набор, план,
                                                    маркер),
                                  план=план, idempotency_key="neg-4")
        assert ош.value.error_code == "GRANT_CLAIMS_INCOMPLETE"
        assert ц["мир"].эффектов("create") == 0

    def test_05_подменён_артефакт_или_план(self, стенд):
        ц, cid, _, маркер, набор, план = self._подготовить(стенд, "-5")
        _, тело = просить_grant(стенд, cid, fencing_token=маркер)
        подделка = {**тело["grant"], "artifact_digest": "sha256:" + "0" * 32}
        исполнитель = TemplatesExecutor(стенд["tmp"] / "e5.sqlite3",
                                        ц["адаптер"], набор_ключей(стенд))
        with pytest.raises(G.GrantError) as ош:
            исполнитель.выполнить(подпись=тело["signature"], полезное=подделка,
                                  ожидания=ожидания(стенд, cid, набор, план,
                                                    маркер),
                                  план=план, idempotency_key="neg-5")
        # Подпись проверяется до притязаний: подменённое тело не сверяется.
        assert ош.value.error_code == "APPROVAL_SIGNATURE_INVALID"
        assert ц["мир"].эффектов("create") == 0

    def test_06_неверная_аудитория_или_род_ресурса(self, стенд):
        ц, cid, _, маркер, набор, план = self._подготовить(стенд, "-6")
        код, тело = просить_grant(стенд, cid, fencing_token=маркер,
                                  audience="qwen")
        assert код == 403 and тело["error_code"] == "AUDIENCE_NOT_ALLOWED"
        # Допустимая аудитория, но чужой род ресурса.
        код2, тело2 = просить_grant(стенд, cid, fencing_token=маркер,
                                    audience="changeset-worker")
        assert код2 == 200, тело2
        исполнитель = TemplatesExecutor(стенд["tmp"] / "e6.sqlite3",
                                        ц["адаптер"], набор_ключей(стенд))
        with pytest.raises(G.GrantError) as ош:
            исполнитель.выполнить(подпись=тело2["signature"],
                                  полезное=тело2["grant"],
                                  ожидания=ожидания(стенд, cid, набор, план,
                                                    маркер),
                                  план=план, idempotency_key="neg-6")
        assert ош.value.error_code == "GRANT_AUDIENCE_MISMATCH"
        assert ц["мир"].эффектов("create") == 0

    def test_07_истёкшее_разрешение(self, стенд):
        ц, cid, _, маркер, набор, план = self._подготовить(стенд, "-7")
        _, тело = просить_grant(стенд, cid, fencing_token=маркер)
        from factory.site_engine.approval import keyring as K
        прошлое = (_d.datetime.now(_d.timezone.utc)
                   - _d.timedelta(seconds=30)).isoformat().replace("+00:00", "Z")
        просроченное = {**тело["grant"], "expires_at": прошлое}
        pem = (стенд["tmp"] / "credentials" / "approval-signing-key").read_text()
        подпись = K.подписать(pem, json.dumps(просроченное, ensure_ascii=False,
                                              sort_keys=True,
                                              separators=(",", ":")))
        исполнитель = TemplatesExecutor(стенд["tmp"] / "e7.sqlite3",
                                        ц["адаптер"], набор_ключей(стенд))
        with pytest.raises(G.GrantError) as ош:
            исполнитель.выполнить(подпись=подпись, полезное=просроченное,
                                  ожидания=ожидания(стенд, cid, набор, план,
                                                    маркер),
                                  план=план, idempotency_key="neg-7")
        assert ош.value.error_code == "GRANT_EXPIRED"
        assert ц["мир"].эффектов("create") == 0

    def test_08_production_при_выключенном_применении(self, стенд):
        """Окружение перепроверяется В МОМЕНТ выдачи, а не только при валидации.

        Валидация отвергает production раньше — и правильно делает. Но сайт
        может переехать в production ПОСЛЕ одобрения, и разрешение,
        опирающееся на окружение времени валидации, разрешило бы боевое
        действие по несвежему основанию.
        """
        ц = цель(стенд, "-8")
        cid, _ = approved(стенд, ц, ключ="neg-8")          # окружение test
        аренда = S.взять_аренду(стенд["соед"], cid, "changeset-worker")
        # Версию намеренно не поднимаем: иначе сработает более ранняя
        # проверка устаревания плана, и ворота production останутся
        # непроверенными.
        стенд["реестр"].сменить_окружение(стенд["site_id"], "production",
                                          поднять_версию=False)
        код, тело = просить_grant(стенд, cid,
                                  fencing_token=аренда["fencing_token"])
        assert код == 403, тело
        assert тело["error_code"] == "PRODUCTION_APPLY_DISABLED"
        assert ц["мир"].эффектов("create") == 0

    def test_08b_валидация_тоже_не_пускает_production(self, стенд):
        """Второй слой: набор для production не доходит и до одобрения."""
        ц = цель(стенд, "-8b")
        стенд["реестр"].сменить_окружение(стенд["site_id"], "production")
        with pytest.raises(S.ChangeSetError) as ош:
            approved(стенд, ц, ключ="neg-8b")
        assert "production" in str(ош.value)
        assert ц["мир"].эффектов("create") == 0

    def test_09_отказы_не_выдали_ни_одного_разрешения(self, стенд):
        """Счётчик службы: отказ не должен порождать подпись."""
        ц, cid, _, маркер, _, _ = self._подготовить(стенд, "-9")
        просить_grant(стенд, cid, fencing_token=маркер, вызывающий="control-api")
        просить_grant(стенд, cid, fencing_token=маркер, audience="qwen")
        просить_grant(стенд, cid, fencing_token=999999)
        with urllib.request.urlopen(стенд["signer"].база + "/healthz",
                                    timeout=10) as о:
            здоровье = json.loads(о.read())
        assert здоровье["grants_issued"] == 0
        assert здоровье["accepts_raw_payload"] is False
        assert здоровье["refusals"] >= 3
