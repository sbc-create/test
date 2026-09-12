"""Импорт результата аудита FLEET-TPL-005 в канонический Audit Ledger.

Одно событие на весь аудит, а не пятьдесят три. Реестр дефектов — это один
наблюдательный акт с одним набором доказательств; разложив его на события по
дефектам, мы получили бы пятьдесят три записи, каждая из которых утверждает
о флоте то, что проверялось разом, и ни одна не сослалась бы на остальные.

Идемпотентность выводится ИЗ СОДЕРЖИМОГО манифеста, а не из времени запуска.
Ключ, включающий время, сделал бы каждый повторный запуск новым событием —
то есть ровно тем дублированием, которого требование избегает. Тот же
манифест даёт тот же ключ и второй записи не создаёт.

Фаза — OBSERVED, полномочие — OBSERVE. Аудит ничего не менял, и записывать
его как исполнение значило бы соврать журналу о характере действия.

Токен службы берётся из окружения, которое ВНЕДРЯЕТ systemd. Файл с
секретами здесь не читается и читаться не должен: значение не проходит ни
через оболочку, ни через аргументы, ни через отчёт.
"""
from __future__ import annotations

import hashlib
import json
import os
import urllib.error
import urllib.request
import uuid
from pathlib import Path
from typing import Any

БАЗА = os.environ.get("CONTROL_API_BASE", "http://127.0.0.1:8790").rstrip("/")
ПЕРЕМЕННАЯ = "AUDIT_TOKEN_TEMPLATES"
ТИП_СОБЫТИЯ = "templates.fleet_audit.imported.v1"
ПРОМПТ = "FLEET-TPL-005"

#: Файлы доказательств, на которые ссылается событие. Скриншоты в журнал не
#: попадают: там место ссылке и отпечатку, а не содержимому.
ДОКАЗАТЕЛЬСТВА = ("audit-manifest.json", "DEFECT-REGISTRY.md", "FIX-PLAN.md",
                  "routes.json", "card-links.json", "browser-matrix.json",
                  "functional.json", "measurements.json", "perf.json")


class ImportError_(RuntimeError):
    def __init__(self, code: str, detail: str):
        super().__init__(detail)
        self.error_code, self.detail = code, detail


def _хэш_файла(путь: Path) -> str:
    return "sha256:" + hashlib.sha256(путь.read_bytes()).hexdigest()


#: Что процессу Templates принадлежать не должно ни при каких условиях.
ЧУЖОЕ = ("CHANGESET_APPROVAL_KEY",)


def изолировать_окружение() -> dict[str, bool]:
    """Оставить себе только свою личность, остальное убрать из процесса.

    Сегодня служебные токены всех девяти служб и приватный ключ подписи
    одобрения лежат в ОДНОМ файле окружения. Значит получить токен Templates,
    не получив вместе с ним чужие личности и ключ signer, средствами systemd
    нельзя: `EnvironmentFile` отдаёт файл целиком.

    Пока это не разделено владельцем контура, граница держится здесь: своё
    берётся один раз, всё остальное немедленно удаляется из окружения
    процесса — чтобы ни этот код, ни любой его потомок не смог ни подписать
    одобрение, ни представиться чужой службой.

    Это смягчение, а не изоляция. Настоящее решение — отдельный секрет на
    личность и `LoadCredential` под каждую службу.
    """
    убрано = {}
    for имя in list(os.environ):
        чужой_токен = имя.startswith("AUDIT_TOKEN_") and имя != ПЕРЕМЕННАЯ
        if чужой_токен or имя in ЧУЖОЕ:
            os.environ.pop(имя, None)
            убрано[имя] = True
    остались = [и for и in ЧУЖОЕ if os.environ.get(и)]
    if остались:
        raise ImportError_("FOREIGN_CREDENTIAL_PRESENT",
                           f"не удалось убрать из окружения: {остались}")
    return убрано


def _токен() -> str:
    т = os.environ.get(ПЕРЕМЕННАЯ, "").strip()
    if not т:
        raise ImportError_(
            "SERVICE_TOKEN_MISSING",
            f"{ПЕРЕМЕННАЯ} не внедрён: запуск обязан идти через systemd с "
            f"EnvironmentFile, а не из оболочки")
    return т


def собрать(каталог: str | Path) -> dict[str, Any]:
    """Построить событие из артефактов аудита. Ни одного обращения к сети."""
    к = Path(каталог)
    манифест = json.loads((к / "audit-manifest.json").read_text("utf-8"))
    записи = манифест.get("records") or []

    доказательства = []
    for имя in ДОКАЗАТЕЛЬСТВА:
        ф = к / имя
        if ф.exists():
            доказательства.append({"ref": f"artifacts/fleet-audit/{имя}",
                                   "hash": _хэш_файла(ф)})
    if not any(d["ref"].endswith("audit-manifest.json") for d in доказательства):
        raise ImportError_("MANIFEST_MISSING", "манифест аудита не найден")

    # Ключ идемпотентности покрывает всё, что определяет смысл импорта.
    основа = {"prompt_id": манифест.get("prompt_id") or ПРОМПТ,
              "prompt_rev": манифест.get("prompt_rev"),
              "schema_version": манифест.get("schema_version"),
              "records": записи,
              "evidence": доказательства}
    отпечаток = hashlib.sha256(
        json.dumps(основа, ensure_ascii=False, sort_keys=True,
                   separators=(",", ":")).encode("utf-8")).hexdigest()
    ключ = f"fleet-audit-import:{отпечаток[:32]}"

    сайты = sorted({з.get("site_id") for з in записи if з.get("site_id")})
    # Группа дефекта — это сам defect_id. Срезать у него хвост значило бы
    # слить разные дефекты одного семейства в один и занизить отчёт.
    группы = sorted({з["defect_id"] for з in записи if з.get("defect_id")})
    тяжесть: dict[str, int] = {}
    for з in записи:
        с = з.get("severity") or "UNSPECIFIED"
        тяжесть[с] = тяжесть.get(с, 0) + 1

    сводка = (f"импорт аудита {ПРОМПТ}: {len(записи)} записей, "
              f"{len(группы)} групп дефектов, {len(сайты)} сайтов; "
              f"по тяжести: {', '.join(f'{k}={v}' for k, v in sorted(тяжесть.items()))}; "
              f"изменений не вносилось")

    событие = {
        # event_id детерминирован: повтор не порождает нового идентификатора
        # даже если проверка идемпотентности почему-то не сработает.
        "event_id": str(uuid.uuid5(uuid.NAMESPACE_URL,
                                   f"urn:fleet-audit-import:{отпечаток}")),
        "event_type": ТИП_СОБЫТИЯ,
        "phase": "OBSERVED",
        "result": "SUCCESS",
        "authority": "OBSERVE",
        "scope": "FLEET",
        "environment": "production",
        "resource_type": "monitoring.observation",
        "resource_id": f"{ПРОМПТ}-audit",
        "resource_owner": "templates",
        "idempotency_key": ключ,
        "correlation_id": f"{ПРОМПТ}-import",
        "prompt_id": ПРОМПТ,
        "prompt_rev": манифест.get("prompt_rev") or "R1",
        "occurred_at": манифест.get("generated_at"),
        "summary": сводка,
        "after_hash": "sha256:" + отпечаток,
        "evidence_refs": доказательства,
    }
    return {"event": событие, "fingerprint": отпечаток,
            "records": len(записи), "defect_groups": len(группы),
            "sites": сайты, "severity": тяжесть}


def отправить(событие: dict[str, Any], *, таймаут: float = 20.0) -> dict[str, Any]:
    зпр = urllib.request.Request(
        БАЗА + "/api/v1/audit/events", method="POST",
        data=json.dumps(событие, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json",
                 "X-Service-Name": "templates",
                 "Authorization": "Bearer " + _токен()})
    try:
        with urllib.request.urlopen(зпр, timeout=таймаут) as о:
            return {"status": о.status, "body": json.loads(о.read() or b"{}")}
    except urllib.error.HTTPError as ош:
        тело = ош.read().decode("utf-8", "replace")[:400]
        raise ImportError_("LEDGER_REFUSED", f"HTTP {ош.code}: {тело}") from ош


def импортировать(каталог: str | Path) -> dict[str, Any]:
    убрано = изолировать_окружение()
    собрано = собрать(каталог)
    ответ = отправить(собрано["event"])
    тело = ответ["body"]
    return {"foreign_credentials_dropped": sorted(убрано),
            "http_status": ответ["status"],
            "event_id": тело.get("event_id") or собрано["event"]["event_id"],
            "idempotent_replay": bool(тело.get("idempotent_replay")),
            "ledger_seq": тело.get("ledger_seq"),
            "event_type": ТИП_СОБЫТИЯ,
            "idempotency_key": собрано["event"]["idempotency_key"],
            "records": собрано["records"],
            "defect_groups": собрано["defect_groups"],
            "sites": собрано["sites"]}


if __name__ == "__main__":
    import sys
    к = sys.argv[1] if len(sys.argv) > 1 else "artifacts/fleet-audit"
    print(json.dumps(импортировать(к), ensure_ascii=False, indent=1))
