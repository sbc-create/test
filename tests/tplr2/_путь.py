"""Сборка законного пути до выдачи разрешения. Общая часть проверок."""
from __future__ import annotations

import json
import urllib.error
import urllib.request

from factory.site_engine.changeset import engine as E
from factory.site_engine.changeset import model as M
from factory.site_engine.changeset import store as S
from factory.site_engine.provisioner.changeset_adapter import ProviderTargetAdapter
from factory.site_engine.provisioner.intent import OnboardingIntent
from factory.site_engine.provisioner.mapping import Связи
from factory.site_engine.provisioner.providers import fake as F

from .conftest import через_час

РЕСУРС = "template.build"


def намерение(site_id: str) -> OnboardingIntent:
    return OnboardingIntent.разобрать({
        "requested_by": "service:templates",
        "canonical_domain": f"{site_id}.invalid",
        "template_family": "yummy", "template_profile": "catalog-search",
        "language": "ru", "region": "RU",
        "correlation_id": f"tplr2-{site_id}",
        "idempotency_key": f"tplr2-{site_id}"})


def собрать_цель(стенд, *, счётчик: int = 90000001, мир=None, метка: str = ""):
    """Поддельная цель и адаптер Templates поверх неё.

    `мир` можно передать общий: два рабочих процесса над ОДНОЙ целью — это и
    есть условие гонки. Локальное состояние (связи) у каждого своё, как и в
    жизни.
    """
    мир = мир or F.Мир()
    витрина = F.ФейковаяВитрина(мир)
    витрина.установить_счётчик(счётчик)
    связи = Связи(str(стенд["tmp"] / f"links-{счётчик}{метка}.sqlite3"))
    адаптер = ProviderTargetAdapter(витрина, намерение(стенд["site_id"]), связи,
                                    resource_type=РЕСУРС)
    return {"мир": мир, "витрина": витрина, "связи": связи, "адаптер": адаптер}


def довести_до_approved(стенд, цель, *, ключ: str = "tplr2-1") -> str:
    """Proposer=templates, validator=control-plane, approver=человек."""
    соед = стенд["соед"]
    заявка = {
        "resource_type": РЕСУРС,
        "resource_id": f"{стенд['site_id']}:template-release",
        "operation_type": "update",
        "target_site_ids": [стенд["site_id"]],
        "idempotency_key": ключ,
        "correlation_id": f"tplr2-{ключ}",
        "requested_change": {"canonical_domain": f"{стенд['site_id']}.invalid"},
    }
    создано = S.создать(соед, заявка, producer_service="templates",
                        actor_id="service:templates", actor_type="SERVICE")
    cid = создано["changeset_id"]
    цель["адаптер"].changeset_id = cid
    движок = E.Engine(соед, адаптер=цель["адаптер"], реестр=стенд["реестр"],
                      требовать_журнал=False)
    движок.валидировать(cid, actor_id="service:control-plane",
                        служба="control-plane")
    движок.запросить_одобрение(cid, actor_id="service:templates",
                               служба="templates", expires_at=через_час())
    движок.одобрить(cid, approver_id="human:owner", служба="human_owner",
                    actor_type="HUMAN", expires_at=через_час())
    return cid, движок


def запросить_grant(стенд, cid: str, *, audience: str, fencing_token: int,
                    вызывающий: str = "changeset-worker"):
    """Прямой запрос к службе подписи. Возвращает (код, тело)."""
    токен = стенд["signer"]["caller_tokens"].get(вызывающий, "unknown-caller")
    зпр = urllib.request.Request(
        стенд["signer"]["base"] + "/grant", method="POST",
        data=json.dumps({"changeset_id": cid, "audience": audience,
                         "fencing_token": fencing_token}).encode(),
        headers={"Content-Type": "application/json",
                 "Authorization": "Bearer " + токен})
    try:
        with urllib.request.urlopen(зпр, timeout=10) as о:
            return о.status, json.loads(о.read() or b"{}")
    except urllib.error.HTTPError as ош:
        return ош.code, json.loads(ош.read() or b"{}")


# --- выпуск разрешений тестовым ключом ---------------------------------------
#
# Служба подписи сегодня не выдаёт разрешение аудитории templates-executor —
# это зафиксированный блокер. Чтобы проверить ГРАНИЦУ АДАПТЕРА, разрешения
# выпускаются тестовым ключом стенда: проверяется то, что делает адаптер,
# а не то, что умеет выдавать служба.

import datetime as _d
import uuid as _uuid

from factory.site_engine.approval import keyring as K
from factory.site_engine.approval import service as SIGNER
from factory.site_engine.provisioner import grant as G


def набор_ключей(стенд) -> K.НаборКлючей:
    путь = стенд["tmp"] / "credentials" / SIGNER.НАБОР
    return K.НаборКлючей.из_json(путь.read_text("utf-8"))


def _pem(стенд) -> str:
    return (стенд["tmp"] / "credentials" / SIGNER.ПРИВАТНЫЙ).read_text("utf-8")


def выпустить_grant(стенд, *, changeset_id: str, site_id: str,
                    plan_hash: str, artifact_digest: str,
                    registry_fingerprint: str, fencing_token: int,
                    audience: str = G.АУДИТОРИЯ,
                    resource_kind: str = "template.release",
                    срок_сек: int = 120, jti: str | None = None):
    """Полное разрешение со всеми притязаниями, которых требует адаптер."""
    истекает = (_d.datetime.now(_d.timezone.utc)
                + _d.timedelta(seconds=срок_сек))
    полезное = {
        "typ": "execution-grant", "changeset_id": changeset_id,
        "site_id": site_id, "resource_kind": resource_kind,
        "plan_hash": plan_hash, "artifact_digest": artifact_digest,
        "registry_fingerprint": registry_fingerprint,
        "audience": audience, "fencing_token": int(fencing_token),
        "jti": jti or str(_uuid.uuid4()),
        "expires_at": истекает.isoformat().replace("+00:00", "Z"),
    }
    тело = json.dumps(полезное, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":"))
    return K.подписать(_pem(стенд), тело), полезное


def ожидания(*, changeset_id: str, site_id: str, plan_hash: str,
             artifact_digest: str, registry_fingerprint: str,
             fencing_token: int) -> G.Ожидания:
    return G.Ожидания(changeset_id=changeset_id, site_id=site_id,
                      resource_kind="template.release", plan_hash=plan_hash,
                      artifact_digest=artifact_digest,
                      registry_fingerprint=registry_fingerprint,
                      fencing_token=fencing_token)


def отпечаток_реестра(стенд) -> str:
    return G.хэш(f"registry-version:{стенд['реестр'].версия()}")
