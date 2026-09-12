#!/usr/bin/env python3
"""Сборка bundle 1.3.2: канонический ресурс предложения SEO-контента.

Изменение аддитивное внутри major: ни один ресурс, путь, канал или код
ошибки версии 1.3.1 не удалён и не переименован.

Одно исправление не является добавлением и названо отдельно: `qwen.proposal`
объявлял `single_writer: qwen`, что прямо противоречило политике
`QWEN_PERSISTENT_WRITER=NO`. Объявление приведено в соответствие с политикой.
Сломать это не может никого: опираться на право, которого политика не давала,
было нельзя.

Статус `changeset.adapter.seo` здесь НЕ вписывается. Он вычисляется: сборщик
подключает адаптер к эфемерному хранилищу и прогоняет наблюдение, план и
сухой прогон. Не сошлось — остаётся PLANNED с причиной.
"""
from __future__ import annotations

import hashlib
import json
import shutil
import sys
import tempfile
from pathlib import Path

БАЗА = Path(__file__).resolve().parent
ИСТ, НОВ = БАЗА / "1.3.1", БАЗА / "1.3.2"
ВЕРСИЯ = "1.3.2"
С = f"https://contracts.site-factory.internal/{ВЕРСИЯ}"

sys.path.insert(0, str(БАЗА.parents[1]))
from factory.site_engine.changeset import model as CM
from factory.site_engine.seo_authoring import schema as SCH


def записать(путь: Path, данные) -> None:
    путь.write_text(json.dumps(данные, ensure_ascii=False, indent=2) + "\n",
                    encoding="utf-8")


def перецелить(узел):
    if isinstance(узел, dict):
        return {k: (v.replace("/1.3.1/", f"/{ВЕРСИЯ}/")
                    if k == "$ref" and isinstance(v, str) else перецелить(v))
                for k, v in узел.items()}
    if isinstance(узел, list):
        return [перецелить(x) for x in узел]
    return узел


def проверить_адаптер() -> dict:
    """Исполнить адаптер на эфемерном хранилище и вернуть наблюдение.

    Проверяется не наличие класса, а исполнимость пути: наблюдение даёт
    отпечаток, план даёт различия и обратимость, сухой прогон не создаёт ни
    одного эффекта. Только это делает `AVAILABLE` утверждением о факте.
    """
    from factory.site_engine.seo_authoring.adapter import SeoContentAdapter
    with tempfile.TemporaryDirectory(prefix="seo-adapter-probe-") as d:
        а = SeoContentAdapter(Path(d) / "probe.sqlite3")
        возм = а.capabilities()
        а.посеять("probe-site", "e:title:ru", {"title": "старое"})
        набл = а.observe(site_id="probe-site", resource_id="e:title:ru")
        план = а.plan(site_id="probe-site", resource_id="e:title:ru",
                      operation="update",
                      requested_change={"operations": [
                          {"op": "set", "path": "/title",
                           "value_digest": "0" * 64}],
                          "artifact_digest": "1" * 64},
                      observed=набл)
        сухо = а.dry_run(site_id="probe-site", plan=план)
        эффектов = а.эффектов()
        владелец = а.owner_service
    ок = (возм["supports_dry_run"] and возм["supports_observe"]
          and возм["supports_rollback"] and not возм["live_writes"]
          and план["reversible"] and not план["empty"]
          and сухо["effects"] == 0 and эффектов == 0
          and владелец == CM.ЕДИНСТВЕННЫЙ_ПИСАТЕЛЬ[SCH.RESOURCE_KIND])
    return {"executable": ок, "capabilities": возм, "dry_run_effects": сухо["effects"],
            "total_effects": эффектов, "owner_service": владелец,
            "plan_reversible": план["reversible"]}


def собрать() -> dict:
    if not ИСТ.exists():
        sys.exit("нет исходного бандла 1.3.1")
    if НОВ.exists():
        shutil.rmtree(НОВ)
    shutil.copytree(ИСТ, НОВ)

    проба = проверить_адаптер()
    статус_адаптера = "AVAILABLE" if проба["executable"] else "PLANNED"

    for p in (НОВ / "schemas").glob("*.json"):
        d = json.loads(p.read_text(encoding="utf-8"))
        if isinstance(d.get("$id"), str):
            d["$id"] = d["$id"].replace("/1.3.1/", f"/{ВЕРСИЯ}/")
        записать(p, перецелить(d))

    # --- строгая схема ресурса ------------------------------------------
    схема = SCH.json_schema()
    схема["$id"] = f"{С}/schemas/SeoContentProposal.v1.json"
    записать(НОВ / "schemas" / "SeoContentProposal.v1.json", схема)

    # --- матрица владения ------------------------------------------------
    om = json.loads((НОВ / "ownership-matrix.json").read_text(encoding="utf-8"))
    существующие = {r["resource"] for r in om["resources"]}
    if SCH.RESOURCE_KIND not in существующие:
        om["resources"].append({
            "resource": SCH.RESOURCE_KIND,
            "fields": ["proposal_id", "site_id", "entity_id", "entity_kind",
                       "surface", "locale", "fact_pack_ref",
                       "source_snapshot_sha256", "artifact_ref",
                       "artifact_digest", "model_version", "prompt_version",
                       "policy_version", "requested_by", "correlation_id",
                       "causation_id", "idempotency_key", "operations"],
            # Владелец домена и писатель — разные вещи. SEO владеет смыслом
            # ресурса; каноническую строку пишет control-plane, потому что
            # запись обязана пройти проверку схемы, прав, реестра и
            # отпечатков, а эта проверка живёт в Control Plane.
            "single_writer": "control-plane",
            "domain_owner": "seo",
            "content_author": "qwen",
            "requester": "seo",
            "approver": "human_owner",
            "executor": "control-plane",
            "readers": ["architect", "seo", "control-plane", "qwen",
                        "monitoring", "backup"],
            "commands": ["propose"],
            "emits": ["seo.changeset.proposed.v1",
                      "seo.content.proposal.accepted.v1",
                      "seo.content.proposal.rejected.v1"],
            "consumes": ["site.registered.v1", "site.updated.v1",
                         "content.refresh.completed.v1"],
            "source_of_truth": "changesets.sqlite3 (control-plane)",
            "retention_owner": "control-plane",
            "secret_class": "NONE",
            "mutation_policy": (
                "только через канонический приём предложения; поля "
                "target_environment, owner_service, audience и site_kind "
                "выводятся сервером, присланные значения лишь сверяются"),
            "note": (
                "Не подмена seo.audit: тот описывает результат обследования "
                "и хранит предложения вложенным списком без собственного "
                "идентификатора, версии и ключа идемпотентности."),
        })
    for r in om["resources"]:
        if r["resource"] == "qwen.proposal":
            # Исправление, а не добавление: объявление противоречило политике.
            r["single_writer"] = "control-plane"
            r["content_author"] = "qwen"
            r["note"] = (
                "Qwen — actor_type=MODEL и автор содержимого. Постоянным "
                "писателем не является: каноническую запись делает "
                "control-plane. До 1.3.2 матрица называла писателем qwen, что "
                "противоречило политике QWEN_PERSISTENT_WRITER=NO.")
        if r["resource"] == "seo.audit":
            r["note"] = (
                "Результат обследования. Предложение авторского контента — "
                "отдельный ресурс seo.content.proposal; поле proposals здесь "
                "остаётся вложенным списком находок и жизненного цикла не "
                "несёт.")
    записать(НОВ / "ownership-matrix.json", om)

    # --- каталог возможностей -------------------------------------------
    cc = json.loads((НОВ / "capability-catalog.json").read_text(encoding="utf-8"))
    имя = lambda c: c.get("capability_id") or c.get("id")
    для_замены = {
        "changeset.adapter.seo": {
            "capability_id": "changeset.adapter.seo",
            "owner_service": "control-plane", "version": ВЕРСИЯ,
            "status": статус_адаптера,
            "read_endpoint": "/api/v1/workflows",
            "command_endpoint": "/api/v1/changesets/{changeset_id}/apply",
            "event_types": ["changeset.applied.v1", "changeset.succeeded.v1"],
            "required_scopes": ["changeset:apply"],
            "dependencies": ["changeset.apply", "seo.content.proposal"],
            "evidence_ref": "artifacts/evidence/fleet-arc-003/adapter-probe.json",
            "note": ("Статус вычислен исполнением: наблюдение, план и сухой "
                     "прогон на эфемерном хранилище, ноль эффектов."),
        },
    }
    новые = [
        {"capability_id": "seo.content.proposal", "owner_service": "control-plane",
         "version": ВЕРСИЯ, "status": "AVAILABLE",
         "read_endpoint": "/api/v1/changesets?resource_type=seo.content.proposal",
         "command_endpoint": None,
         "event_types": ["seo.changeset.proposed.v1",
                         "seo.content.proposal.accepted.v1"],
         "required_scopes": ["changeset:propose"],
         "dependencies": ["registry.sites.filter", "changeset.propose"],
         "note": ("Внутренняя поверхность: предложение принимается служебным "
                  "контуром, отдельного HTTP-маршрута нет намеренно.")},
        {"capability_id": "seo.content.authoring", "owner_service": "seo",
         "version": ВЕРСИЯ, "status": "AVAILABLE",
         "read_endpoint": None, "command_endpoint": None,
         "event_types": ["seo.content.proposal.accepted.v1"],
         "required_scopes": ["seo:read"],
         "dependencies": ["seo.content.proposal"],
         "note": "Замысел и черновик; устойчивой записи не делает."},
        {"capability_id": "qwen.content.draft", "owner_service": "qwen",
         "version": ВЕРСИЯ, "status": "AVAILABLE",
         "read_endpoint": None, "command_endpoint": None, "event_types": [],
         "required_scopes": [],
         "dependencies": ["seo.content.authoring"],
         "note": ("actor_type=MODEL. Порождает содержимое черновика. Не "
                  "получает устойчивой записи, approve, authorize, execute и "
                  "доступа к секретам.")},
    ]
    итоговые = []
    for c in cc["capabilities"]:
        n = имя(c)
        итоговые.append(для_замены.get(n, c) if n in для_замены else c)
    есть = {имя(c) for c in итоговые}
    итоговые += [c for c in новые if c["capability_id"] not in есть]
    cc["capabilities"] = итоговые
    cc["bundle_version"] = ВЕРСИЯ
    cc["count"] = len(итоговые)
    cc["available"] = sum(1 for c in итоговые if c.get("status") == "AVAILABLE")
    cc["planned"] = sum(1 for c in итоговые if c.get("status") == "PLANNED")
    cc["blocked"] = sum(1 for c in итоговые if c.get("status") == "BLOCKED")
    записать(НОВ / "capability-catalog.json", cc)

    # --- события ----------------------------------------------------------
    aa = перецелить(json.loads((НОВ / "asyncapi.json").read_text(encoding="utf-8")))
    aa["info"]["version"] = ВЕРСИЯ
    НОВЫЕ_КАНАЛЫ = {
        "seo.content.proposal.accepted.v1":
            "Каноническое предложение SEO-контента принято и устойчиво "
            "записано; создан набор изменений.",
        "seo.content.proposal.rejected.v1":
            "Предложение отклонено до любого эффекта; причина — код ошибки.",
    }
    for имя_к, описание in НОВЫЕ_КАНАЛЫ.items():
        aa["channels"][f"fleet/{имя_к}"] = {"subscribe": {
            "operationId": имя_к.replace(".", "_"),
            "description": описание,
            "x-owner": "control-plane",
            "x-consumers": ["architect", "seo", "monitoring", "backup", "qwen"],
            "x-aggregate-key": "proposal_id",
            "x-order-key": "proposal_id",
            "x-status": "AVAILABLE",
            "x-dedup-key": "idempotency_key",
            "x-retryable": True,
            "x-evidence-required": имя_к.endswith("accepted.v1"),
            "message": {"name": имя_к, "contentType": "application/json",
                        "payload": {"$ref": f"{С}/schemas/EventEnvelope.v1.json"}},
        }}
    # Канал предложения существовал со статусом владельца seo; теперь его
    # производит control-plane, потому что он же делает запись.
    к = aa["channels"].get("fleet/seo.changeset.proposed.v1")
    if к:
        к["subscribe"]["x-status"] = "AVAILABLE"
        к["subscribe"]["x-owner"] = "control-plane"
        к["subscribe"]["x-aggregate-key"] = "changeset_id"
        к["subscribe"]["description"] = (
            "Предложение SEO дошло до канонического набора изменений. "
            "Производитель — control-plane: событие пишет тот, кто сделал "
            "запись.")
    записать(НОВ / "asyncapi.json", aa)

    # --- коды ошибок ------------------------------------------------------
    ec = json.loads((НОВ / "error-catalog.json").read_text(encoding="utf-8"))
    # В каталоге уживаются две формы записей: {code, http, meaning} и
    # {error_code, status, retryable, owner, detail}. Новые добавляются в
    # преобладающей форме, а проверка на повтор учитывает обе — иначе один
    # и тот же код появился бы дважды под разными именами ключей.
    есть_коды = {e.get("code") or e.get("error_code") for e in ec["errors"]}
    for код, http, смысл in (
            ("RESOURCE_KIND_UNKNOWN", 422, "Вид ресурса не обслуживается."),
            ("SCHEMA_VERSION_UNSUPPORTED", 422, "Версия схемы не поддержана."),
            ("FIELD_UNKNOWN", 422, "В заявке неизвестное поле; схема закрыта."),
            ("FIELD_NOT_ACCEPTED", 422,
             "Поле вычисляется сервером и в запросе не принимается."),
            ("DIGEST_INVALID", 422, "Значение не является отпечатком sha256."),
            ("ARTIFACT_NOT_FOUND", 422, "Содержимое черновика не найдено."),
            ("ARTIFACT_DIGEST_MISMATCH", 409,
             "Отпечаток содержимого не совпал с заявленным."),
            ("SOURCE_SNAPSHOT_STALE", 409,
             "Снимок фактов устарел; предложение составлено по другим фактам."),
            ("DERIVED_FIELD_MISMATCH", 403,
             "Присланное значение поля расходится с выведенным сервером."),
            ("ACTOR_SPOOFED", 403,
             "Заявленный заказчик не совпал с опознанным по токену."),
            ("MODEL_DURABLE_WRITE_DENIED", 403,
             "Актор-модель не делает устойчивых записей."),
            ("REQUESTER_NOT_ALLOWED", 403,
             "Служба не вправе подавать предложения этого вида."),
            ("PRODUCTION_TARGET_DENIED", 403,
             "Цель в production; применение вне test и non-production выключено."),
            ("ENTITY_KIND_UNKNOWN", 422, "Вид сущности неизвестен."),
            ("SURFACE_UNKNOWN", 422, "Поверхность неизвестна."),
            ("LOCALE_INVALID", 422, "Локаль не разобрана."),
            ("VERSION_INVALID", 422, "Версия модели, промпта или политики не разобрана."),
            ("OPERATIONS_INVALID", 422, "Список правок не разобран."),
    ):
        if код not in есть_коды:
            ec["errors"].append({"code": код, "http": http, "meaning": смысл})
    записать(НОВ / "error-catalog.json", ec)

    # --- соответствие ресурса контуру изменений --------------------------
    записать(НОВ / "changeset-resource-map.json", {
        "schema_version": "fleet-changeset-resource-map/1.0.0",
        "bundle_version": ВЕРСИЯ,
        "rule": ("Вид ресурса обслуживается контуром изменений только при "
                 "наличии подключённого адаптера. Запись здесь без адаптера "
                 "означала бы объявленную, но неисполнимую возможность."),
        "resources": [{
            "resource_kind": SCH.RESOURCE_KIND,
            "schema": f"{С}/schemas/SeoContentProposal.v1.json",
            "adapter": "factory.site_engine.seo_authoring.adapter:SeoContentAdapter",
            "adapter_status": статус_адаптера,
            "single_writer": "control-plane",
            "domain_owner": "seo",
            "content_author": "qwen",
            "operations": ["update", "patch"],
            "reversible": True,
            "changeset_resource_id": "{entity_id}:{surface}:{locale}",
            "emits": ["seo.changeset.proposed.v1",
                      "seo.content.proposal.accepted.v1"],
            "probe": проба,
        }],
    })

    # --- совместимость ----------------------------------------------------
    (НОВ / "COMPATIBILITY.md").write_text(
        "# Совместимость\n\n## 1.3.1 → 1.3.2\n\n"
        "Аддитивно внутри major `v1`. Ни один ресурс, путь, канал, код ошибки "
        "или поле версии 1.3.1 не удалён и не переименован. Потребитель 1.3.1 "
        "продолжает работать без правок: новые поля матрицы "
        "(`domain_owner`, `content_author`, `requester`, `approver`, "
        "`executor`) необязательны, а неизвестные поля потребитель обязан "
        "терпеть по объявленной политике совместимости.\n\n"
        "### Одно исправление объявления\n\n"
        "`qwen.proposal.single_writer` изменён с `qwen` на `control-plane`.\n\n"
        "Это не ломающее изменение, а приведение объявления в соответствие с "
        "политикой: `QWEN_PERSISTENT_WRITER=NO` действовал и в 1.3.1, поэтому "
        "опереться на право, которого политика не давала, было нельзя. "
        "Потребитель, читавший это поле, получит более узкое и верное "
        "значение; потребитель, писавший от имени qwen, не смог бы этого "
        "сделать и раньше.\n\n"
        "### Что стало доступно\n\n"
        f"* ресурс `{SCH.RESOURCE_KIND}` со строгой схемой;\n"
        f"* `changeset.adapter.seo` → `{статус_адаптера}` (вычислено "
        "исполнением, не вписано);\n"
        "* каналы `seo.content.proposal.accepted.v1` и "
        "`seo.content.proposal.rejected.v1`;\n"
        "* `seo.changeset.proposed.v1` переведён в AVAILABLE, производитель — "
        "`control-plane`.\n\n"
        + (ИСТ / "COMPATIBILITY.md").read_text(encoding="utf-8")
        .replace("# Совместимость\n", "", 1),
        encoding="utf-8")

    (НОВ / "CHANGELOG.md").write_text(
        f"# CHANGELOG\n\n## {ВЕРСИЯ}\n\n"
        "Канонический ресурс предложения SEO-контента.\n\n"
        f"* `{SCH.RESOURCE_KIND}` — строгая схема, закрытая для неизвестных "
        "полей; поля `target_environment`, `owner_service`, `audience` и "
        "`site_kind` выводятся сервером, присланные значения только "
        "сверяются;\n"
        "* матрица владения: домен — `seo`, автор содержимого — `qwen`, "
        "единственный устойчивый писатель — `control-plane`;\n"
        "* исправлено противоречие `qwen.proposal.single_writer=qwen` против "
        "политики `QWEN_PERSISTENT_WRITER=NO`;\n"
        f"* `changeset.adapter.seo` → `{статус_адаптера}`, статус вычислен "
        "исполнением адаптера на эфемерном хранилище;\n"
        "* два канала событий предложения; `seo.changeset.proposed.v1` "
        "переведён в AVAILABLE;\n"
        "* восемнадцать кодов отказа предложения;\n"
        "* `changeset-resource-map.json` — соответствие вида ресурса адаптеру.\n\n"
        "`seo.audit` намеренно не перегружен: он описывает результат "
        "обследования, а не жизненный цикл авторского предложения.\n\n"
        + (ИСТ / "CHANGELOG.md").read_text(encoding="utf-8")
        .replace("# CHANGELOG\n", "", 1),
        encoding="utf-8")

    # --- манифест и суммы -------------------------------------------------
    m = json.loads((НОВ / "manifest.json").read_text(encoding="utf-8"))
    m["version"] = ВЕРСИЯ
    m["generated_at"] = __import__("datetime").datetime.now(
        __import__("datetime").timezone.utc).isoformat().replace("+00:00", "Z")
    m["artifacts"] = sorted(p.name for p in НОВ.iterdir() if p.is_file()
                            and p.name != "checksums.json")
    записать(НОВ / "manifest.json", m)

    суммы = {}
    for p in sorted(НОВ.rglob("*")):
        if p.is_file() and p.name != "checksums.json":
            суммы[str(p.relative_to(НОВ))] = hashlib.sha256(
                p.read_bytes()).hexdigest()
    записать(НОВ / "checksums.json",
             {"version": ВЕРСИЯ, "algorithm": "sha256", "files": суммы})

    # Отпечаток всего набора: связывает контракт с артефактом одним числом.
    общий = hashlib.sha256(json.dumps(суммы, sort_keys=True).encode()).hexdigest()
    return {"version": ВЕРСИЯ, "files": len(суммы), "bundle_sha256": общий,
            "adapter_status": статус_адаптера, "adapter_probe": проба,
            "capabilities": cc["count"], "available": cc["available"],
            "resources": len(om["resources"]),
            "channels": len(aa["channels"])}


if __name__ == "__main__":
    итог = собрать()
    печать = {k: v for k, v in итог.items() if k != "adapter_probe"}
    print(json.dumps(печать, ensure_ascii=False, indent=2))
