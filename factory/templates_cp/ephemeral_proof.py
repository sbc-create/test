"""Доказательство адаптера в эфемерной среде через канонический контур.

Машина состояний, планировщик, политика, аренда и fencing берутся из Control
Plane как есть. Здесь не воспроизводится ничего из этого: своя машина
состояний рядом с чужой означала бы два разных ответа на вопрос, что сейчас
происходит с изменением.

Эфемерность здесь не «тестовый режим», а условие безопасности. База набора
изменений создаётся на один прогон, цель — сайт окружения `test`, а ключ
подписи одобрения генерируется здесь же и нигде не сохраняется: боевой
приватный ключ подписи Templates не принадлежит и передан ему быть не может.

Проверяется не «вызвалось без исключения», а следствия: сухой прогон не
создал эффектов, повтор применения не создал второго, откат вернул прежний
отпечаток, а применение в production отвергнуто.
"""
from __future__ import annotations

import datetime as _d
import importlib.util
import json
import os
import secrets
import sys
import tempfile
from pathlib import Path
from typing import Any

КОНТРОЛЬ = "/srv/site-factory/control-api/current"
ЭФЕМЕРНОЕ_ОКРУЖЕНИЕ = ("test", "non-production")


def _канон():
    """Канонические модули контура. Загружаются из Control Plane, не копируются."""
    if КОНТРОЛЬ not in sys.path:
        sys.path.insert(0, КОНТРОЛЬ)
    from factory.site_engine.changeset import (engine as E, model as M,
                                               policy as POL, store as S)
    from factory.site_engine.changeset.registry_client import RegistryClient
    return E, M, POL, S, RegistryClient


def _адаптер_модуль():
    сп = importlib.util.spec_from_file_location(
        "templates_adapter", str(Path(__file__).with_name("adapter.py")))
    м = importlib.util.module_from_spec(сп)
    сп.loader.exec_module(м)
    return м


def _через_час() -> str:
    т = _d.datetime.now(_d.timezone.utc) + _d.timedelta(hours=1)
    return т.isoformat().replace("+00:00", "Z")


def прогнать(site_id: str | None = None) -> dict[str, Any]:
    E, M, POL, S, RegistryClient = _канон()
    АД = _адаптер_модуль()

    # Ключ подписи — одноразовый и только для этого прогона. Он не читается
    # из окружения Control Plane и не попадает ни в файл, ни в журнал.
    os.environ["CHANGESET_APPROVAL_KEY"] = secrets.token_hex(32)

    итог: dict[str, Any] = {"checks": {}}
    врем = tempfile.mkdtemp(prefix="tpl-ephemeral-")
    реестр = RegistryClient()

    сайты = {с["site_id"]: с for с in реестр.сайты()}
    цель = site_id or next(
        (с for с, з in sorted(сайты.items())
         if з.get("environment") in ЭФЕМЕРНОЕ_ОКРУЖЕНИЕ
         and з.get("lifecycle_state") in ("ACTIVE", "DRAFT")), None)
    if цель is None:
        raise RuntimeError("в реестре нет эфемерной цели: прогон невозможен")
    итог["target"] = {"site_id": цель,
                      "environment": сайты[цель].get("environment"),
                      "lifecycle_state": сайты[цель].get("lifecycle_state")}

    окружения = {с: з.get("environment") for с, з in сайты.items()}
    домены = {}          # живую витрину эфемерная цель не имеет и иметь не должна
    адаптер = АД.TemplatesAdapter(Path(врем) / "adapter.sqlite3",
                                  домены=домены, окружения=окружения)
    соед = S.открыть(Path(врем) / "changeset.sqlite3")
    движок = E.Engine(соед, адаптер=адаптер, реестр=реестр)

    заявка = {
        "resource_type": АД.РЕСУРС,
        "resource_id": f"{цель}:template-binding",
        "operation_type": "update",
        "target_site_ids": [цель],
        "idempotency_key": "ephemeral-proof-" + secrets.token_hex(8),
        "requested_change": {"template_family": "yummy",
                             "design_version": "1.4.5",
                             "profile": "catalog-search"},
    }
    создано = S.создать(соед, заявка, producer_service="templates",
                        actor_id="service:templates", actor_type="SERVICE")
    cid = создано["changeset_id"]
    итог["changeset_id"] = cid

    # --- повтор заявки с тем же ключом ------------------------------------
    повтор = S.создать(соед, заявка, producer_service="templates",
                       actor_id="service:templates", actor_type="SERVICE")
    итог["checks"]["proposal_idempotent"] = (
        повтор["changeset_id"] == cid and повтор["idempotent_replay"])

    # --- валидация и сухой прогон -----------------------------------------
    эффектов_до = адаптер.эффектов()
    # Валидирует НЕ Templates. Он PROPOSER и не более того: право проверять
    # собственное предложение сделало бы разделение обязанностей формальностью.
    провалидировано = движок.валидировать(cid, actor_id="service:control-plane",
                                          служба="control-plane")
    итог["plan_hash"] = провалидировано["plan_hash"]
    итог["risk_class"] = провалидировано["risk_class"]
    итог["environments"] = провалидировано["environments"]
    итог["checks"]["dry_run_zero_effects"] = (
        провалидировано["dry_run_effects"] == 0
        and адаптер.эффектов() == эффектов_до)

    # --- план детерминирован ----------------------------------------------
    from factory.site_engine.changeset import planner as P
    ещё_раз = P.спланировать(S.получить(соед, cid), реестр=реестр, адаптер=адаптер)
    итог["checks"]["plan_deterministic"] = (
        ещё_раз["plan_hash"] == провалидировано["plan_hash"])

    # --- одобрение --------------------------------------------------------
    движок.запросить_одобрение(cid, actor_id="service:templates",
                               служба="templates", expires_at=_через_час())
    # Одобряет человек. Службе-исполнителю одобрение собственного изменения
    # недоступно по матрице прав, и это проверяется ниже отдельно.
    движок.одобрить(cid, approver_id="human:owner", служба="architect",
                    actor_type="HUMAN", expires_at=_через_час(),
                    reason="эфемерное доказательство механизма")

    # --- применение -------------------------------------------------------
    аренда = S.взять_аренду(соед, cid, "templates-proof")
    маркер = аренда["fencing_token"]
    применено = движок.применить(cid, actor_id="service:control-plane",
                                 служба="control-plane", fencing_token=маркер)
    итог["apply_status"] = S.получить(соед, cid)["status"]
    итог["checks"]["apply_effect"] = адаптер.эффектов(цель) == 1

    # --- повторное применение не создаёт второго эффекта -------------------
    план = S.получить(соед, cid)["dry_run_result"]["per_site_plan"][цель]
    адаптер.apply(site_id=цель, plan=план, fencing_token=маркер)
    адаптер.apply(site_id=цель, plan=план, fencing_token=маркер)
    итог["checks"]["apply_idempotent"] = адаптер.эффектов(цель) == 1
    итог["effects_after_double_apply"] = адаптер.эффектов(цель)

    # --- проверка читает состояние заново ----------------------------------
    наблюдаемое = адаптер.observe(site_id=цель, resource_id=заявка["resource_id"])
    сверка = адаптер.verify(site_id=цель, plan=план, observed=наблюдаемое)
    итог["checks"]["verify_true"] = bool(сверка["verified"])

    # --- проверка обязана падать на подменённом состоянии ------------------
    подделка = dict(план)
    подделка["expected_fingerprint"] = "sha256:" + "0" * 64
    итог["checks"]["verify_detects_mismatch"] = not адаптер.verify(
        site_id=цель, plan=подделка, observed=наблюдаемое)["ok"]

    # --- откат -------------------------------------------------------------
    откат = адаптер.rollback(site_id=цель, plan=план,
                             before_fingerprint=план["before_fingerprint"],
                             fencing_token=маркер)
    после = адаптер.observe(site_id=цель, resource_id=заявка["resource_id"])
    итог["checks"]["rollback_restores"] = (
        откат["rolled_back"]
        and после["fingerprint"] == план["before_fingerprint"])
    повторный = адаптер.rollback(site_id=цель, plan=план,
                                 before_fingerprint=план["before_fingerprint"],
                                 fencing_token=маркер)
    итог["checks"]["rollback_idempotent"] = повторный["effects"] == 0

    # --- production через адаптер не применяется ---------------------------
    боевой = next((с for с, о in окружения.items() if о == "production"), None)
    отказ = None
    if боевой:
        try:
            адаптер.apply(site_id=боевой, plan={**план, "empty": False},
                          fencing_token=маркер)
        except АД.AdapterError as ош:
            отказ = ош.error_code
    итог["checks"]["production_apply_refused"] = отказ == "PRODUCTION_APPLY_FORBIDDEN"
    итог["production_refusal_code"] = отказ

    # --- Templates не вправе валидировать, одобрять и применять ------------
    #
    # Проверять это на уже завершённом наборе бессмысленно: отказ придёт по
    # состоянию, а не по роли, и запрет останется недоказанным. Поэтому под
    # каждый запрет заводится отдельный набор, доведённый ровно до того
    # состояния, в котором действие законно для того, у кого роль есть.
    def _свежий(суффикс: str) -> str:
        # Разные ресурсы намеренно: контур не даёт двум наборам одновременно
        # менять одну цель, и это его правильное поведение, а не помеха.
        з = {**заявка, "idempotency_key": f"deny-{суффикс}-" + secrets.token_hex(6),
             "resource_id": f"{цель}:template-binding-deny-{суффикс}"}
        return S.создать(соед, з, producer_service="templates",
                         actor_id="service:templates",
                         actor_type="SERVICE")["changeset_id"]

    def _код(вызов) -> str | None:
        try:
            вызов()
            return None
        except Exception as ош:
            return getattr(ош, "error_code", type(ош).__name__)

    запреты = {}

    a = _свежий("validate")                       # PROPOSED — состояние верное
    запреты["validate"] = {"state": S.получить(соед, a)["status"],
                           "code": _код(lambda: движок.валидировать(
                               a, actor_id="service:templates", служба="templates"))}

    b = _свежий("approve")
    движок.валидировать(b, actor_id="service:control-plane", служба="control-plane")
    движок.запросить_одобрение(b, actor_id="service:templates", служба="templates",
                               expires_at=_через_час())
    запреты["approve"] = {"state": S.получить(соед, b)["status"],
                          "code": _код(lambda: движок.одобрить(
                              b, approver_id="service:templates", служба="templates",
                              actor_type="SERVICE", expires_at=_через_час()))}

    c = _свежий("apply")
    движок.валидировать(c, actor_id="service:control-plane", служба="control-plane")
    движок.запросить_одобрение(c, actor_id="service:templates", служба="templates",
                               expires_at=_через_час())
    движок.одобрить(c, approver_id="human:owner", служба="architect",
                    actor_type="HUMAN", expires_at=_через_час())
    аренда_c = S.взять_аренду(соед, c, "templates-proof-deny")
    запреты["apply"] = {"state": S.получить(соед, c)["status"],
                        "code": _код(lambda: движок.применить(
                            c, actor_id="service:templates", служба="templates",
                            fencing_token=аренда_c["fencing_token"]))}

    # --- обрыв посреди применения ------------------------------------------
    #
    # Процесс, убитый сразу после перехода в APPLYING, оставляет набор в этом
    # состоянии. Возобновление обязано довести его до конца и НЕ создать
    # второго эффекта: именно ради этого apply идемпотентен по plan_hash.
    d = _свежий("resume")
    движок.валидировать(d, actor_id="service:control-plane", служба="control-plane")
    движок.запросить_одобрение(d, actor_id="service:templates", служба="templates",
                               expires_at=_через_час())
    движок.одобрить(d, approver_id="human:owner", служба="architect",
                    actor_type="HUMAN", expires_at=_через_час())
    аренда_d = S.взять_аренду(соед, d, "templates-proof-resume")
    маркер_d = аренда_d["fencing_token"]
    ресурс_d = S.получить(соед, d)["resource_id"]
    # Переход состоялся, цели не тронуты — ровно картина после падения.
    S.применить_переход(соед, d, "apply", actor_id="service:control-plane",
                        служба="control-plane", роль=M.EXECUTOR,
                        fencing_token=маркер_d)
    итог["crash_state"] = S.получить(соед, d)["status"]
    эффектов_до_возобновления = адаптер.эффектов(цель)
    возобновлено = движок.применить(d, actor_id="service:control-plane",
                                    служба="control-plane", fencing_token=маркер_d)
    # Повтор по завершённому набору отвергает сама машина состояний — это
    # сильнее идемпотентности адаптера: до адаптера вызов просто не доходит.
    итог["repeat_apply_code"] = _код(lambda: движок.применить(
        d, actor_id="service:control-plane", служба="control-plane",
        fencing_token=маркер_d))
    итог["resume_status"] = возобновлено["status"]
    итог["checks"]["crash_recovery"] = (
        итог["crash_state"] == M.APPLYING
        and возобновлено["status"] == M.SUCCEEDED
        and адаптер.эффектов(цель) == эффектов_до_возобновления + 1
        and итог["repeat_apply_code"] == "TRANSITION_NOT_ALLOWED")

    итог["templates_denied"] = запреты
    # Отказ обязан быть именно по роли. Любой другой код означает, что запрет
    # не проверен: набор не дошёл до нужного состояния.
    итог["checks"]["templates_cannot_execute"] = all(
        з["code"] == "ROLE_NOT_GRANTED" for з in запреты.values())

    адаптер.закрыть()
    соед.close()
    итог["ephemeral_dir"] = врем
    итог["passed"] = all(итог["checks"].values())
    return итог


if __name__ == "__main__":
    р = прогнать()
    print(json.dumps(р, ensure_ascii=False, indent=1))
    raise SystemExit(0 if р["passed"] else 1)
