#!/usr/bin/env python3
"""Сборка bundle 1.2.0: разделение сырой ленты и операционной проекции.

Почему 1.2.0, а не 1.1.1. Патч-версия означала бы исправление без изменения
поверхности. Здесь добавлены новая внешняя возможность (operational API),
новые события карантина и требование роли на чтение сырой ленты — последнее
меняет поведение уже объявленного маршрута. Оставить 1.1.0 было бы прямой
ложью о контракте; назвать это патчем — ложью помягче.
"""
from __future__ import annotations

import hashlib, json, shutil, sys
from pathlib import Path

БАЗА = Path(__file__).resolve().parent
ИСТ, НОВ = БАЗА / "1.1.0", БАЗА / "1.2.0"
if not ИСТ.exists():
    sys.exit("нет исходного бандла 1.1.0")
if НОВ.exists():
    shutil.rmtree(НОВ)
shutil.copytree(ИСТ, НОВ)
ВЕРСИЯ = "1.2.0"
С = f"https://contracts.site-factory.internal/{ВЕРСИЯ}"

sys.path.insert(0, str(БАЗА.parents[1]))
from factory.site_engine.audit import quarantine as qr


def записать(путь: Path, данные) -> None:
    путь.write_text(json.dumps(данные, ensure_ascii=False, indent=2) + "\n",
                    encoding="utf-8")


def перецелить(узел):
    """Переписать ссылки на схемы со старой версии на новую."""
    if isinstance(узел, dict):
        return {k: (v.replace("/1.1.0/", f"/{ВЕРСИЯ}/")
                    if k == "$ref" and isinstance(v, str) else перецелить(v))
                for k, v in узел.items()}
    if isinstance(узел, list):
        return [перецелить(x) for x in узел]
    return узел


for p in (НОВ / "schemas").glob("*.json"):
    d = json.loads(p.read_text(encoding="utf-8"))
    d["$id"] = d["$id"].replace("/1.1.0/", f"/{ВЕРСИЯ}/")
    записать(p, перецелить(d))

# --- схемы карантина и проекции ----------------------------------------------
записать(НОВ / "schemas" / "QuarantineDecision.v1.json", {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "$id": f"{С}/schemas/QuarantineDecision.v1.json",
    "title": "QuarantineDecision.v1",
    "description": (
        "Решение о том, что множество записей журнала непригодно для рабочих "
        "решений. Записи при этом не удаляются и не изменяются: журнал только "
        "на добавление, и исправление ошибки — тоже запись. Перечень "
        "идентификаторов хранится в манифесте доказательств, а не в теле "
        "события: шестьдесят строк в payload перестали бы читаться, а хэш "
        "манифеста связывает решение со списком не слабее."),
    "type": "object",
    "required": ["reason", "owner", "decision_authority", "event_count",
                 "manifest_uri", "manifest_sha256", "first_ledger_seq",
                 "last_ledger_seq", "classified_at", "prompt_id", "prompt_rev"],
    "additionalProperties": False,
    "properties": {
        "reason": {"enum": [qr.ПРИЧИНА_HARNESS]},
        "owner": {"const": "ARCHITECT"},
        "decision_authority": {"enum": ["AUTHORIZE", "EXECUTE"]},
        "event_count": {"type": "integer", "minimum": 1},
        "manifest_uri": {"type": "string"},
        "manifest_sha256": {"type": "string", "pattern": "^[0-9a-f]{64}$"},
        "first_ledger_seq": {"type": "integer", "minimum": 1},
        "last_ledger_seq": {"type": "integer", "minimum": 1},
        "classified_at": {"type": "string", "format": "date-time"},
        "prompt_id": {"type": "string"},
        "prompt_rev": {"type": "string"},
        "source_commit": {"type": ["string", "null"]},
        "correction_action_id": {"type": ["string", "null"]},
    },
})

записать(НОВ / "schemas" / "ProjectionState.v1.json", {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "$id": f"{С}/schemas/ProjectionState.v1.json",
    "title": "ProjectionState.v1",
    "description": (
        "Состояние операционной проекции. Проекция — индекс над журналом, а "
        "не его копия, и полностью пересобирается из него. Вторым источником "
        "истины она не является: при расхождении прав журнал."),
    "type": "object",
    "required": ["projection", "active_table", "rebuildable_from"],
    "additionalProperties": True,
    "properties": {
        "projection": {"type": "string"},
        "active_table": {"type": "string"},
        "rollback_table": {"type": ["string", "null"]},
        "rebuildable_from": {"const": "ledger_event"},
        "watermark_seq": {"type": "integer"},
        "event_count": {"type": "integer"},
        "excluded_count": {"type": "integer"},
        "built_at": {"type": "string", "format": "date-time"},
        "source_commit": {"type": ["string", "null"]},
    },
})

# --- OpenAPI -----------------------------------------------------------------
oa = перецелить(json.loads((НОВ / "openapi.json").read_text(encoding="utf-8")))
oa["info"]["version"] = ВЕРСИЯ
ссылка = lambda имя: {"$ref": f"{С}/schemas/{имя}.json"}
проблема = {"content": {"application/problem+json": {"schema": ссылка("Problem.v1")}}}
фильтры = [p for p in oa["paths"]["/api/v1/audit/events"]["get"]["parameters"]]

# Сырая лента закрывается ролью: она показывает и собственные ошибки системы.
сырой = oa["paths"]["/api/v1/audit/events"]["get"]
сырой["description"] = (
    "Полная неизменяемая история, включая записи, помещённые в карантин; их "
    "статус виден в поле surface и в проекции. Доступ — только роль "
    "audit-admin: по этой ленте не принимают рабочих решений, по ней "
    "разбирают историю, в том числе ошибки самой системы.")
сырой["responses"]["401"] = dict(проблема, description="Токен не предъявлен или не распознан")
сырой["responses"]["403"] = dict(проблема, description="ROLE_DENIED или TOKEN_REVOKED")

oa["paths"]["/api/v1/audit/operational/events"] = {"get": {
    "operationId": "listOperationalAuditEvents",
    "summary": "Рабочая проекция журнала",
    "description": (
        "События, пригодные для рабочих решений: карантинные исключены. "
        "Именно эту поверхность используют Templates, Content, SEO, "
        "Monitoring, Backup и Qwen. Проекция пересобирается из журнала и "
        "источником истины не является."),
    "parameters": фильтры + [
        {"name": "include_quarantined", "in": "query",
         "schema": {"type": "boolean"},
         "description": "Только для роли audit-admin; иначе 403 ROLE_DENIED."}],
    "responses": {
        "200": {"description": "Страница рабочих событий"},
        "401": dict(проблема, description="Токен не предъявлен или не распознан"),
        "403": dict(проблема, description="ROLE_DENIED или TOKEN_REVOKED"),
        "422": dict(проблема, description="Неизвестный, пустой или противоречивый фильтр"),
    }}}

oa["paths"]["/api/v1/audit/projection"] = {"get": {
    "operationId": "getAuditProjectionState",
    "summary": "Состояние операционной проекции",
    "responses": {"200": {"description": "Состояние",
                          "content": {"application/json": {
                              "schema": ссылка("ProjectionState.v1")}}}}}}

for путь in ("/api/v1/audit/actions/{action_id}",
             "/api/v1/audit/correlations/{correlation_id}"):
    узел = oa["paths"][путь]["get"]
    узел["description"] = (
        "По умолчанию нить рабочая: карантинные события исключены, а их число "
        "показано отдельным счётчиком quarantined_count — укоротить нить "
        "молча значило бы скрыть сам факт изъятия. include_quarantined "
        "доступен только роли audit-admin.")
    узел.setdefault("parameters", []).append(
        {"name": "include_quarantined", "in": "query",
         "schema": {"type": "boolean"}})
    узел["responses"]["401"] = dict(проблема, description="Токен не предъявлен")
    узел["responses"]["403"] = dict(проблема, description="ROLE_DENIED")
записать(НОВ / "openapi.json", oa)

# --- AsyncAPI ----------------------------------------------------------------
aa = перецелить(json.loads((НОВ / "asyncapi.json").read_text(encoding="utf-8")))
aa["info"]["version"] = ВЕРСИЯ
НОВЫЕ = {
    qr.СОБЫТИЕ_КАРАНТИН: (
        "Множество записей объявлено непригодным для рабочих решений. "
        "Записи не удаляются и не изменяются; исключение действует только в "
        "операционной проекции."),
    qr.СОБЫТИЕ_ОТМЕНА: (
        "Решение о карантине отменено. Отмена — тоже запись: ошибочная "
        "классификация не стирается, а перекрывается."),
    "audit.projection.rebuilt.v1":
        "Операционная проекция пересобрана и переключена.",
}
for имя, описание in НОВЫЕ.items():
    aa["channels"][f"fleet/{имя}"] = {"subscribe": {
        "operationId": имя.replace(".", "_"),
        "description": описание,
        "x-owner": "architect",
        "x-consumers": ["architect", "monitoring", "backup", "qwen"],
        "x-aggregate-key": "correlation_id",
        "x-order-key": "ledger_seq",
        "x-status": "AVAILABLE",
        "x-dedup-key": "event_id",
        "x-retryable": True,
        "x-evidence-required": имя != "audit.projection.rebuilt.v1",
        "x-self-event": False,
        "message": {"name": имя, "contentType": "application/json",
                    "payload": {"$ref": f"{С}/schemas/EventEnvelope.v1.json"}},
    }}
записать(НОВ / "asyncapi.json", aa)

# --- возможности, ошибки, владение -------------------------------------------
cc = json.loads((НОВ / "capability-catalog.json").read_text(encoding="utf-8"))
cc["capabilities"].extend([
    {"id": "audit.operational_projection", "status": "AVAILABLE",
     "description": ("Рабочая проекция журнала без карантинных записей; "
                     "поверхность для Templates, Content, SEO, Monitoring, "
                     "Backup и Qwen.")},
    {"id": "audit.quarantine", "status": "AVAILABLE",
     "description": ("Логическое изъятие множества записей новым событием "
                     "без удаления и изменения исходных.")},
    {"id": "audit.raw_feed", "status": "AVAILABLE",
     "description": "Полная история; требует роли audit-admin."},
    {"id": "audit.token_revocation", "status": "AVAILABLE",
     "description": ("Отзыв токена по отпечатку без изменения исходного "
                     "кода и без перевыпуска остальных.")},
])
записать(НОВ / "capability-catalog.json", cc)

ec = json.loads((НОВ / "error-catalog.json").read_text(encoding="utf-8"))
ec["errors"].extend([
    {"code": "ROLE_DENIED", "http": 403,
     "meaning": "У опознанной службы нет роли, требуемой этим маршрутом."},
    {"code": "TOKEN_REVOKED", "http": 403,
     "meaning": "Токен опознан, но выведен из обращения."},
])
записать(НОВ / "error-catalog.json", ec)

om = json.loads((НОВ / "ownership-matrix.json").read_text(encoding="utf-8"))
om["resources"].append({
    "resource": "audit.operational_projection",
    "fields": ["ledger_seq", "excluded", "exclusion_reason",
               "quarantine_event_id"],
    "single_writer": "architect",
    "readers": ["architect", "templates", "seo", "content", "monitoring",
                "backup", "qwen"],
    "commands": ["rebuild", "switch"],
    "emits": ["audit.projection.rebuilt.v1"],
    "consumes": [qr.СОБЫТИЕ_КАРАНТИН, qr.СОБЫТИЕ_ОТМЕНА],
    "source_of_truth": "ledger_event (проекция пересобирается из журнала)",
    "retention_owner": "architect",
    "secret_class": "NONE",
    "mutation_policy": "полная пересборка из журнала; частичных правок нет",
    "note": ("Проекция не является источником истины: при любом расхождении "
             "верен журнал, а проекция пересобирается."),
})
for r in om["resources"]:
    if r["resource"] == "audit.event":
        r["emits"] = sorted(set(r["emits"]) | set(НОВЫЕ))
записать(НОВ / "ownership-matrix.json", om)

# --- манифест и суммы --------------------------------------------------------
m = json.loads((НОВ / "manifest.json").read_text(encoding="utf-8"))
m["version"] = ВЕРСИЯ
m["contract"] = f"fleet-control-plane-contracts/{ВЕРСИЯ}"
записать(НОВ / "manifest.json", m)
(НОВ / "_partial-checksums.json").unlink(missing_ok=True)

суммы = {}
for p in sorted(НОВ.rglob("*")):
    if p.is_file() and p.name != "checksums.json":
        суммы[str(p.relative_to(НОВ))] = hashlib.sha256(p.read_bytes()).hexdigest()
записать(НОВ / "checksums.json", {"version": ВЕРСИЯ, "algorithm": "sha256",
                                  "files": суммы})

(НОВ / "CHANGELOG.md").write_text(
    "# CHANGELOG\n\n## 1.2.0\n\n"
    "Разделены сырая лента журнала и рабочая проекция.\n\n"
    "Минорная версия, а не патч: добавлена новая внешняя возможность "
    "(`/api/v1/audit/operational/events`), добавлены события карантина, и "
    "чтение сырой ленты теперь требует роли `audit-admin` — последнее меняет "
    "поведение уже объявленного маршрута, и умолчать об этом в номере версии "
    "нельзя.\n\n"
    "* схемы `QuarantineDecision.v1`, `ProjectionState.v1`;\n"
    "* пути `/api/v1/audit/operational/events` и `/api/v1/audit/projection`;\n"
    "* `include_quarantined` — только для роли `audit-admin`;\n"
    "* `actions/{id}` и `correlations/{id}` по умолчанию рабочие, с полем "
    "`quarantined_count`;\n"
    "* каналы `audit.event_set.quarantined.v1`, "
    "`audit.event_set.quarantine_revoked.v1`, `audit.projection.rebuilt.v1`;\n"
    "* ресурс `audit.operational_projection` в матрице владения;\n"
    "* коды `ROLE_DENIED` и `TOKEN_REVOKED`.\n\n"
    "Совместимость: потребители 1.1.0, читавшие сырую ленту без токена, "
    "обязаны предъявить токен с ролью `audit-admin` либо перейти на "
    "операционную поверхность. Это единственное ломающее изменение, и оно "
    "намеренное: рабочие решения не должны приниматься по ленте, содержащей "
    "заведомо непригодные записи.\n\n"
    + (ИСТ / "CHANGELOG.md").read_text(encoding="utf-8").replace("# CHANGELOG\n", "", 1),
    encoding="utf-8")

print(json.dumps({"version": ВЕРСИЯ, "files": len(суммы),
                  "openapi_paths": len(oa["paths"]),
                  "asyncapi_channels": len(aa["channels"]),
                  "schemas": len(list((НОВ / "schemas").glob("*.json")))},
                 ensure_ascii=False))
