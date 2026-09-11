#!/usr/bin/env python3
"""Вторая половина bundle: OpenAPI, AsyncAPI, матрицы, каталоги, манифест."""
from __future__ import annotations
import datetime as dt, hashlib, json, pathlib

ВЕРСИЯ = "1.0.0"
КОРЕНЬ = pathlib.Path("/srv/site-factory/control-plane-contracts") / ВЕРСИЯ
БАЗА_ID = "https://contracts.site-factory.internal/fleet/1.0.0"
СЕЙЧАС = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

# ---------------------------------------------------------------- OpenAPI
def путь(summary, owner, статус="AVAILABLE", params=None, коды=None):
    ответы = {str(k): {"description": v} for k, v in (коды or {200: "ok"}).items()}
    ответы.setdefault("503", {"description": "зависимость недоступна"})
    d = {"get": {"summary": summary, "x-owner": owner, "x-status": статус,
                 "responses": ответы}}
    if params:
        d["get"]["parameters"] = params
    return d

OPENAPI = {
 "openapi": "3.0.3",
 "info": {"title": "Fleet Control Plane", "version": ВЕРСИЯ,
          "description": ("Единый внешний контракт внутренних контуров. "
                          "Единый язык и discovery, но НЕ общая БД: каждый "
                          "сервис владеет только своими данными.")},
 "servers": [{"url": "http://127.0.0.1:8790",
              "description": "внутренний контур; наружу не публикуется"}],
 "paths": {
  "/api/v1/contracts/manifest": путь("Манифест bundle", "architect"),
  "/api/v1/contracts/openapi": путь("OpenAPI bundle", "architect"),
  "/api/v1/contracts/asyncapi": путь("AsyncAPI bundle", "architect"),
  "/api/v1/contracts/schemas/{schema_id}": путь(
      "JSON Schema по идентификатору", "architect",
      params=[{"name": "schema_id", "in": "path", "required": True,
               "schema": {"type": "string"}}],
      коды={200: "схема", 404: "нет такой схемы"}),
  "/api/v1/capabilities": путь("Каталог возможностей", "architect"),
  "/api/v1/capabilities/{capability_id}": путь(
      "Возможность", "architect",
      params=[{"name": "capability_id", "in": "path", "required": True,
               "schema": {"type": "string"}}],
      коды={200: "возможность", 404: "нет такой возможности"}),
  "/api/v1/control-plane/version": путь("Версия Control Plane", "architect"),
  "/api/v1/sites": путь("Список сайтов", "architect",
      params=[{"name": "environment", "in": "query",
               "schema": {"type": "string"}},
              {"name": "lifecycle_state", "in": "query",
               "schema": {"type": "string"}}]),
  "/api/v1/sites/{site_id}": путь("Сайт", "architect",
      params=[{"name": "site_id", "in": "path", "required": True,
               "schema": {"type": "string"}}],
      коды={200: "запись", 404: "нет такого сайта"}),
  "/api/v1/registry/version": путь("Версия реестра", "architect"),
  "/api/v1/registry/snapshot": путь("Снимок ACTIVE production", "architect"),
  "/api/v1/events": путь("Лента событий по курсору", "architect",
      params=[{"name": "after", "in": "query", "schema": {"type": "integer"}},
              {"name": "limit", "in": "query", "schema": {"type": "integer"}}]),
  "/health": путь("Живость", "architect"),
  "/ready": путь("Готовность", "architect", коды={200: "готов", 503: "не готов"}),
  # Зарезервированные пространства имён. Реализаций нет намеренно: поднять
  # пустой адрес и объявить его работающим — то же, что соврать потребителю.
  **{p: {"get": {"summary": s, "x-owner": o, "x-status": "PLANNED",
                 "description": ("зарезервировано; владелец ещё не реализовал. "
                                 "Адреса нет — обращаться нельзя"),
                 "responses": {"501": {"description": "не реализовано"}}}}
     for p, s, o in [
       ("/api/v1/actions", "Журнал действий", "architect"),
       ("/api/v1/workflows", "Процессы", "architect"),
       ("/api/v1/changesets", "Наборы изменений", "architect"),
       ("/api/v1/evidence", "Доказательства", "architect"),
       ("/api/v1/integrations", "Внешние интеграции", "architect"),
       ("/api/v1/observations", "Наблюдения", "monitoring"),
       ("/api/v1/alerts", "Оповещения", "monitoring"),
       ("/api/v1/backups", "Резервные копии", "backup")]},
 },
 "components": {"schemas": {
     имя: {"$ref": f"{БАЗА_ID}/schemas/{имя}.json"} for имя in
     ("SiteRef", "ActorRef", "ObservedValue", "CorrelationContext",
      "VersionRef", "EvidenceRef", "DesiredObservedState",
      "CommandEnvelope.v1", "CommandReceipt.v1", "EventEnvelope.v1",
      "Problem.v1", "Page.v1", "Capability.v1")}},
}

# ---------------------------------------------------------------- AsyncAPI
def событие(имя, producer, consumers, aggregate, статус, дедуп, retry):
    return {"x-owner": producer, "x-consumers": consumers,
            "x-aggregate-key": aggregate, "x-order-key": aggregate,
            "x-status": статус, "x-dedup-key": дедуп, "x-retryable": retry,
            "x-evidence-required": статус == "AVAILABLE",
            "message": {"name": имя, "contentType": "application/json",
                        "payload": {"$ref": f"{БАЗА_ID}/schemas/EventEnvelope.v1.json"}}}

СОБЫТИЯ = {
 # Существующие — не ломать.
 "site.registered.v1": событие("site.registered.v1", "architect",
   ["templates","seo","content","monitoring","backup","qwen"], "site_id",
   "AVAILABLE", "event_id", False),
 "site.updated.v1": событие("site.updated.v1", "architect",
   ["templates","seo","content","monitoring","backup","qwen"], "site_id",
   "AVAILABLE", "event_id", False),
 "site.activated.v1": событие("site.activated.v1", "architect",
   ["templates","seo","content","monitoring","backup","qwen"], "site_id",
   "AVAILABLE", "event_id", False),
 "site.retired.v1": событие("site.retired.v1", "architect",
   ["templates","seo","content","monitoring","backup","qwen"], "site_id",
   "AVAILABLE", "event_id", False),
}
ПЛАНИРУЕМЫЕ = [
 ("template.release.published.v1","templates",["architect","content","seo"]),
 ("template.deployment.observed.v1","templates",["architect","monitoring"]),
 ("content.refresh.completed.v1","content",["architect","seo","monitoring"]),
 ("content.refresh.failed.v1","content",["architect","monitoring"]),
 ("content.freshness.breached.v1","content",["monitoring","seo"]),
 ("seo.audit.completed.v1","seo",["architect","content"]),
 ("seo.changeset.proposed.v1","seo",["architect"]),
 ("seo.publish.completed.v1","seo",["architect","monitoring"]),
 ("integration.provision.requested.v1","architect",["seo","monitoring"]),
 ("integration.provision.completed.v1","architect",["seo","monitoring"]),
 ("integration.provision.failed.v1","architect",["seo","monitoring"]),
 ("monitor.alert.opened.v1","monitoring",["architect","qwen"]),
 ("monitor.alert.resolved.v1","monitoring",["architect","qwen"]),
 ("backup.completed.v1","backup",["architect","monitoring"]),
 ("backup.failed.v1","backup",["architect","monitoring"]),
 ("backup.restore.verified.v1","backup",["architect"]),
 ("workflow.started.v1","architect",["monitoring","qwen"]),
 ("workflow.completed.v1","architect",["monitoring","qwen"]),
 ("workflow.blocked.v1","architect",["monitoring","qwen"]),
 ("changeset.approved.v1","architect",["templates","seo","content"]),
 ("changeset.applied.v1","architect",["templates","seo","content"]),
 ("changeset.failed.v1","architect",["templates","seo","content"]),
 ("changeset.rolled_back.v1","architect",["templates","seo","content"]),
 ("action.recorded.v1","architect",["monitoring"]),
]
for имя, prod, cons in ПЛАНИРУЕМЫЕ:
    СОБЫТИЯ[имя] = событие(имя, prod, cons, "site_id", "PLANNED",
                           "event_id", True)

ASYNCAPI = {
 "asyncapi": "2.6.0",
 "info": {"title": "Fleet Control Plane Events", "version": ВЕРСИЯ,
          "description": ("Доставка at-least-once. Потребитель обязан быть "
                          "идемпотентным по event_id и держать durable "
                          "cursor: повтор события — норма, а не сбой.")},
 "defaultContentType": "application/json",
 "channels": {f"fleet/{имя}": {"subscribe": {"operationId": имя.replace(".", "_"),
                                             **тело}}
              for имя, тело in СОБЫТИЯ.items()},
}

# ------------------------------------------------------- ownership matrix
OWNERSHIP = {
 "schema_version": "1.0.0", "generated_at": СЕЙЧАС,
 "rule": ("У каждого ресурса ровно один писатель. Два независимых писателя "
          "одного поля — это не гибкость, а гарантированное расхождение."),
 "resources": [
  {"resource": "site.identity", "fields": ["site_id","canonical_domain","aliases",
    "family","environment","lifecycle_state"],
   "single_writer": "architect", "readers": ["templates","seo","content",
    "monitoring","backup","qwen"],
   "commands": ["register","update","activate","retire"],
   "emits": ["site.registered.v1","site.updated.v1","site.activated.v1",
             "site.retired.v1"], "consumes": [],
   "source_of_truth": "registry.sqlite3 (architect)",
   "retention_owner": "architect", "secret_class": "NONE",
   "mutation_policy": "command API + Idempotency-Key + If-Match"},
  {"resource": "site.template_binding",
   "fields": ["template_id","template_version","build_id","release_id"],
   "single_writer": "architect",
   "note": ("Templates ПРЕДЛАГАЕТ значения событием, но записывает их в "
            "реестр architect. Иначе у поля было бы два писателя."),
   "readers": ["templates","seo","content","monitoring","qwen"],
   "commands": ["update"], "emits": ["site.updated.v1"],
   "consumes": ["template.release.published.v1",
                "template.deployment.observed.v1"],
   "source_of_truth": "registry.sqlite3 (architect)",
   "retention_owner": "architect", "secret_class": "NONE",
   "mutation_policy": "command API"},
  {"resource": "template.artifact",
   "fields": ["artifact_sha256","design_version","source_commit","built_at"],
   "single_writer": "templates", "readers": ["architect","seo","qwen"],
   "commands": [], "emits": ["template.release.published.v1"],
   "consumes": ["changeset.approved.v1"],
   "source_of_truth": "templates (собственное хранилище)",
   "retention_owner": "templates", "secret_class": "NONE",
   "mutation_policy": "PLANNED"},
  {"resource": "content.catalog",
   "fields": ["entity_id","canonical_path","published_at","airing_status",
              "episodes_released"],
   "single_writer": "content", "readers": ["architect","seo","monitoring","qwen"],
   "commands": [], "emits": ["content.refresh.completed.v1",
    "content.refresh.failed.v1","content.freshness.breached.v1"],
   "consumes": ["site.activated.v1"],
   "source_of_truth": "content (yummy-content.sqlite3)",
   "retention_owner": "content", "secret_class": "NONE",
   "mutation_policy": "PLANNED"},
  {"resource": "seo.audit",
   "fields": ["audit_id","findings","proposals"],
   "single_writer": "seo", "readers": ["architect","qwen"],
   "commands": [], "emits": ["seo.audit.completed.v1",
    "seo.changeset.proposed.v1","seo.publish.completed.v1"],
   "consumes": ["site.activated.v1","content.refresh.completed.v1"],
   "source_of_truth": "seo (собственное хранилище)",
   "retention_owner": "seo", "secret_class": "NONE",
   "mutation_policy": "PLANNED"},
  {"resource": "integration.external_resource",
   "fields": ["provider","public_id","provisioned_at"],
   "single_writer": "architect",
   "note": ("Счётчики Метрики и проекты Topvisor создаёт ТОЛЬКО architect. "
            "SEO запрашивает и использует выданный public_id, но не создаёт "
            "ресурс сам: иначе два контура заводили бы дубли у провайдера."),
   "readers": ["seo","monitoring","qwen"],
   "commands": ["provision_integration"],
   "emits": ["integration.provision.requested.v1",
             "integration.provision.completed.v1",
             "integration.provision.failed.v1"],
   "consumes": [], "source_of_truth": "architect",
   "retention_owner": "architect",
   "secret_class": "REF_ONLY (только несекретные public ID и имена ссылок)",
   "mutation_policy": "PLANNED"},
  {"resource": "monitoring.observation",
   "fields": ["observation_id","metric","observed_value","slo_state"],
   "single_writer": "monitoring", "readers": ["architect","qwen","seo"],
   "commands": [], "emits": ["monitor.alert.opened.v1",
                             "monitor.alert.resolved.v1"],
   "consumes": ["site.activated.v1","site.retired.v1"],
   "source_of_truth": "monitoring", "retention_owner": "monitoring",
   "secret_class": "NONE", "mutation_policy": "PLANNED"},
  {"resource": "backup.run",
   "fields": ["run_id","policy_ref","checksum","restore_verified_at"],
   "single_writer": "backup", "readers": ["architect","monitoring","qwen"],
   "commands": [], "emits": ["backup.completed.v1","backup.failed.v1",
                             "backup.restore.verified.v1"],
   "consumes": ["site.activated.v1"],
   "source_of_truth": "backup", "retention_owner": "backup",
   "secret_class": "NONE", "mutation_policy": "PLANNED"},
  {"resource": "qwen.proposal",
   "fields": ["proposal_id","changeset","rationale"],
   "single_writer": "qwen",
   "note": ("Qwen — actor_type=MODEL. Пишет только собственные предложения и "
            "не владеет ни одним доменным ресурсом. Применение предложения "
            "делает владелец данных через ChangeSet и policy."),
   "readers": ["architect"], "commands": [], "emits": [],
   "consumes": ["site.activated.v1","monitor.alert.opened.v1"],
   "source_of_truth": "qwen", "retention_owner": "qwen",
   "secret_class": "NONE",
   "mutation_policy": "PROPOSAL_ONLY; production apply запрещён"},
 ],
}

# ------------------------------------------------------------ error catalog
ОШИБКИ = {
 "schema_version": "1.0.0", "generated_at": СЕЙЧАС,
 "http_semantics": {
  "200": "завершённый синхронный результат", "201": "ресурс создан",
  "202": "асинхронная команда ПРИНЯТА, но не выполнена",
  "400": "запрос не разобран", "401": "не аутентифицирован",
  "403": "нет прав", "404": "ресурс неизвестен",
  "409": "конфликт состояния или ключа идемпотентности",
  "412": "предусловие версии не выполнено",
  "422": "схема или бизнес-правило нарушены", "429": "ограничение частоты",
  "503": "зависимость недоступна"},
 "errors": [
  {"error_code": "REGISTRY_UNAVAILABLE", "status": 503, "retryable": True,
   "owner": "architect", "detail": "хранилище реестра недоступно"},
  {"error_code": "SITE_NOT_FOUND", "status": 404, "retryable": False,
   "owner": "architect", "detail": "сайта с таким site_id нет"},
  {"error_code": "SCHEMA_UNKNOWN", "status": 404, "retryable": False,
   "owner": "architect", "detail": "схемы с таким идентификатором нет"},
  {"error_code": "CAPABILITY_UNKNOWN", "status": 404, "retryable": False,
   "owner": "architect", "detail": "возможности с таким идентификатором нет"},
  {"error_code": "IDEMPOTENCY_KEY_REQUIRED", "status": 422, "retryable": False,
   "owner": "architect", "detail": "мутация без Idempotency-Key не принимается"},
  {"error_code": "VERSION_CONFLICT", "status": 412, "retryable": False,
   "owner": "architect",
   "detail": "expected_version не совпал; перечитайте и повторите"},
  {"error_code": "DOMAIN_TAKEN", "status": 409, "retryable": False,
   "owner": "architect", "detail": "домен уже принадлежит другому сайту"},
  {"error_code": "UNAUTHORIZED", "status": 401, "retryable": False,
   "owner": "architect", "detail": "служебный токен отсутствует или неверен"},
  {"error_code": "NOT_IMPLEMENTED", "status": 501, "retryable": False,
   "owner": "architect",
   "detail": "пространство имён зарезервировано, владелец ещё не реализовал"},
  {"error_code": "DEADLINE_EXCEEDED", "status": 503, "retryable": True,
   "owner": "architect",
   "detail": "истёк срок; НЕ считать успехом и не помечать SUCCEEDED"},
 ],
 "reliability_rules": {
  "idempotency": "Idempotency-Key обязателен для всех мутаций",
  "concurrency": "If-Match / expected_version; несовпадение — 412",
  "correlation": "X-Correlation-ID обязателен",
  "timeout": "ограниченный дедлайн, распространяется вниз по цепочке",
  "retry": "только retryable=true",
  "backoff": "экспоненциальный с джиттером и верхней границей",
  "circuit_breaker": "обязателен для внешних провайдеров",
  "backpressure": "ограниченная очередь; переполнение — 429, не молчание",
  "cursor": "durable, переживает перезапуск потребителя",
  "dead_letter": "терминальное состояние; НИКОГДА не SUCCESS",
  "stale_heartbeat": "не считается RUNNING",
  "terminal_statuses": ["SUCCEEDED", "FAILED", "BLOCKED", "CANCELLED"],
  "serving_plane": ("публичные сайты не зависят синхронно от Control Plane; "
                    "last-known-good — для выдачи, но не источник истины")},
}

def записать(отн, данные):
    п = КОРЕНЬ / отн
    п.parent.mkdir(parents=True, exist_ok=True)
    п.write_text(json.dumps(данные, ensure_ascii=False, indent=1) + "\n"
                 if not isinstance(данные, str) else данные, encoding="utf-8")
    return hashlib.sha256(п.read_bytes()).hexdigest()

if __name__ == "__main__":
    записать("openapi.json", OPENAPI)
    записать("asyncapi.json", ASYNCAPI)
    записать("ownership-matrix.json", OWNERSHIP)
    записать("error-catalog.json", ОШИБКИ)
    print("openapi путей:", len(OPENAPI["paths"]))
    print("asyncapi каналов:", len(ASYNCAPI["channels"]))
    print("ресурсов в ownership:", len(OWNERSHIP["resources"]))
    print("ошибок в каталоге:", len(ОШИБКИ["errors"]))
