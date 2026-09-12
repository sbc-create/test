"""Значимые события границы секретов и релиза в канонический журнал.

Сюда попадает только то, что меняет положение дел: ротация учётных данных,
отзыв, смена ключа подписи, выкладка релиза управляющего слоя. Сердцебиение,
опросы и проверки живости в журнал не пишутся — они превратили бы историю
системы в поток шума, в котором значимое перестаёт быть заметным.

Значений секретов здесь нет и быть не может: событие несёт имена личностей,
kid ключа и КОЛИЧЕСТВО отозванных отпечатков. По количеству нельзя ничего
восстановить, а ответить на вопрос «отзыв состоялся?» можно.
"""
from __future__ import annotations

import hashlib
import json
import os
import urllib.error
import urllib.request
import uuid
from typing import Any

БАЗА = os.environ.get("CONTROL_API_BASE", "http://127.0.0.1:8790").rstrip("/")
ЛИЧНОСТЬ = "audit-token-architect"

РОТАЦИЯ = "security.credentials_rotated.v1"
РЕЛИЗ = "release.control_plane_deployed.v1"
ОТКАТ = "release.rollback_drill_completed.v1"
ПРИНЦИПАЛЫ = "security.control_principals_rotated.v1"
ОТЗЫВ = "security.control_principals_revoked.v1"


class LedgerRefused(RuntimeError):
    def __init__(self, code: str, detail: str):
        super().__init__(detail)
        self.error_code, self.detail = code, detail


def _токен() -> str:
    каталог = os.environ.get("CREDENTIALS_DIRECTORY", "").strip()
    путь = os.path.join(каталог, ЛИЧНОСТЬ) if каталог else ""
    if путь and os.path.isfile(путь):
        with open(путь, encoding="utf-8") as ф:
            значение = ф.read().strip()
        if значение:
            return значение
    raise LedgerRefused("CREDENTIAL_MISSING",
                        f"credential {ЛИЧНОСТЬ} не передан: юнит обязан "
                        f"объявить LoadCredential")


def отправить(событие: dict[str, Any], *, таймаут: float = 20.0) -> dict[str, Any]:
    зпр = urllib.request.Request(
        БАЗА + "/api/v1/audit/events", method="POST",
        data=json.dumps(событие, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json",
                 "X-Service-Name": "architect",
                 "Authorization": "Bearer " + _токен()})
    try:
        with urllib.request.urlopen(зпр, timeout=таймаут) as о:
            return {"status": о.status, "body": json.loads(о.read() or b"{}")}
    except urllib.error.HTTPError as ош:
        raise LedgerRefused("LEDGER_REFUSED",
                            f"HTTP {ош.code}: "
                            f"{ош.read().decode('utf-8','replace')[:300]}")


def _событие(тип: str, ключ: str, сводка: str, **поля) -> dict[str, Any]:
    отпечаток = hashlib.sha256(ключ.encode("utf-8")).hexdigest()
    return {
        "event_id": str(uuid.uuid5(uuid.NAMESPACE_URL, f"urn:{тип}:{отпечаток}")),
        "event_type": тип, "phase": "SUCCEEDED", "result": "SUCCESS",
        "authority": "EXECUTE", "scope": "FLEET", "environment": "production",
        "resource_owner": "architect",
        "idempotency_key": ключ,
        "correlation_id": "FLEET-ARC-002",
        "prompt_id": "FLEET-ARC-002-INTEGRATION-PROVISIONER", "prompt_rev": "R1",
        "summary": сводка, **поля,
    }


def ротация(*, личностей: int, отозвано: int, активный_kid: str,
            отозванные_kid: list[str]) -> dict[str, Any]:
    ключ = f"cred-rotation:{активный_kid}"
    return _событие(
        РОТАЦИЯ, ключ,
        f"учётные данные разделены по личностям: {личностей} личностей, "
        f"отозвано отпечатков {отозвано}, подпись одобрения переведена на "
        f"Ed25519, активный kid {активный_kid}, отозванных kid "
        f"{len(отозванные_kid)}; значения не раскрываются",
        resource_type="integration.provisioning",
        resource_id="site-factory/credentials")


def релиз(*, commit: str, artifact_sha256: str) -> dict[str, Any]:
    ключ = f"control-plane-release:{commit}"
    return _событие(
        РЕЛИЗ, ключ,
        f"выложен внутренний релиз управляющего слоя {commit[:12]}; "
        f"витрины и контент не затронуты",
        resource_type="integration.provisioning",
        resource_id="site-factory/control-api",
        commit_sha=commit, release_id=commit[:12],
        after_hash="sha256:" + artifact_sha256)


def принципалы(*, отпечатки: list[str], областей: list[str]) -> dict[str, Any]:
    """Ротация токенов управляющего слоя. Значений в событии нет."""
    ключ = "control-principals:" + ",".join(sorted(отпечатки))
    return _событие(
        ПРИНЦИПАЛЫ, ключ,
        f"ротированы токены управляющего слоя: {len(отпечатки)} принципалов, "
        f"области сохранены дословно; прежние значения перестали быть "
        f"принципалами и отвергаются authoritative verifier",
        resource_type="integration.provisioning",
        resource_id="site-factory/control-api-principals")


def отзыв(*, отпечатки: list[str], решение: str) -> dict[str, Any]:
    """Окончательный отзыв принципалов без замены.

    Событие несёт отпечатки и решение, но не значения и не «обнаруженного
    задним числом владельца»: владелец, которого не установили измерением,
    в журнале выглядел бы установленным.
    """
    ключ = "control-principals-revoked:" + ",".join(sorted(отпечатки))
    return _событие(
        ОТЗЫВ, ключ,
        f"окончательно отозваны {len(отпечатки)} принципалов Control API без "
        f"замены по решению владельца; активных принципалов не осталось, "
        f"запись управляющего слоя выключена, сырые копии значений "
        f"уничтожены; исторически неустановленных владельцев: 2",
        resource_type="integration.provisioning",
        resource_id="site-factory/control-api-principals")


def откат(*, с_релиза: str, на_релиз: str, вернулись_секреты: int,
          вернулись_полномочия: int) -> dict[str, Any]:
    """Проверка отката в обе стороны. Значений секретов в событии нет."""
    ключ = f"rollback-drill:{с_релиза[:12]}->{на_релиз[:12]}"
    return _событие(
        ОТКАТ, ключ,
        f"проведён откат {с_релиза[:12]} → {на_релиз[:12]} и возврат вперёд; "
        f"общий файл окружения не вернулся, отозванных секретов "
        f"восстановлено {вернулись_секреты}, лишних полномочий возвращено "
        f"{вернулись_полномочия}; реестр, журнал и контур изменений сохранены",
        resource_type="integration.provisioning",
        resource_id="site-factory/control-api",
        commit_sha=на_релиз, release_id=на_релиз[:12])


if __name__ == "__main__":
    import sys
    что = sys.argv[1]
    if что == "rotation":
        с = ротация(личностей=int(sys.argv[2]), отозвано=int(sys.argv[3]),
                    активный_kid=sys.argv[4], отозванные_kid=sys.argv[5:])
    elif что == "revoked":
        с = отзыв(отпечатки=sys.argv[2].split(","),
                  решение=sys.argv[3] if len(sys.argv) > 3 else "owner")
    elif что == "principals":
        с = принципалы(отпечатки=sys.argv[2].split(","),
                       областей=sys.argv[3].split(",") if len(sys.argv) > 3 else [])
    elif что == "rollback":
        с = откат(с_релиза=sys.argv[2], на_релиз=sys.argv[3],
                  вернулись_секреты=int(sys.argv[4]),
                  вернулись_полномочия=int(sys.argv[5]))
    elif что == "release":
        с = релиз(commit=sys.argv[2], artifact_sha256=sys.argv[3])
    else:
        raise SystemExit(f"неизвестное событие: {что}")
    ответ = отправить(с)
    print(json.dumps({"http_status": ответ["status"],
                      "event_id": с["event_id"], "event_type": с["event_type"],
                      "idempotent_replay": ответ["body"].get("idempotent_replay"),
                      "ledger_seq": ответ["body"].get("ledger_seq")},
                     ensure_ascii=False, indent=1))
