#!/usr/bin/env python3
"""Валидация bundle: схемы, примеры, уникальность $id, секреты, инвентарь."""
from __future__ import annotations
import hashlib, json, re, sys, urllib.request
from pathlib import Path

# Версия задаётся аргументом, а не зашита в путь: копия валидатора под каждую
# версию расходится с оригиналом на первой же правке, и проверять начинают
# разные вещи под одним именем.
БАЗА = Path(__file__).resolve().parent
ВЕРСИЯ = sys.argv[1] if len(sys.argv) > 1 else "1.2.0"
ПРЕДЫДУЩАЯ = sys.argv[2] if len(sys.argv) > 2 else None
КОРЕНЬ = БАЗА / ВЕРСИЯ
ОТЧЁТ = БАЗА / "evidence"
провалы: list[str] = []

def шаг(имя, условие, деталь=""):
    print("  %-52s %s %s" % (имя, "PASS" if условие else "FAIL", деталь))
    if not условие:
        провалы.append(имя)

try:
    from jsonschema import Draft202012Validator
    есть_валидатор = True
except ImportError:
    есть_валидатор = False

# --- JSON Schemas ------------------------------------------------------------
схемы = sorted((КОРЕНЬ / "schemas").glob("*.json"))
ids, битые = [], []
for p in схемы:
    d = json.loads(p.read_text(encoding="utf-8"))
    ids.append(d.get("$id"))
    if есть_валидатор:
        try:
            Draft202012Validator.check_schema(d)
        except Exception as e:  # noqa: BLE001
            битые.append(f"{p.name}: {type(e).__name__}")
# Число схем растёт с версиями; проверяется, что они все разобрались, а не
# что их ровно столько, сколько было когда-то.
шаг("JSON Schemas разбираются", len(схемы) >= 13 and not битые, f"{len(схемы)}")
шаг("схемы валидны по Draft 2020-12", есть_валидатор and not битые,
    ", ".join(битые) if битые else ("нет jsonschema" if not есть_валидатор else ""))
шаг("$id уникальны и заполнены",
    len(ids) == len(set(ids)) and all(ids), f"{len(set(ids))}")

# --- примеры проверяются схемами --------------------------------------------
if есть_валидатор:
    ov = json.loads((КОРЕНЬ / "schemas" / "ObservedValue.json").read_text())
    v = Draft202012Validator(ov)
    честный_ноль = {"state": "PRESENT", "value": 0, "observed_at":
                    "2026-09-11T00:00:00Z", "source": "test"}
    шаг("ObservedValue: честный 0 допустим", not list(v.iter_errors(честный_ноль)))
    неизвестно = {"state": "UNKNOWN"}
    шаг("ObservedValue: UNKNOWN без value допустим",
        not list(v.iter_errors(неизвестно)))
    плохо = {"state": "PRESENT", "value": 1}
    шаг("ObservedValue: PRESENT без observed_at отвергается",
        bool(list(v.iter_errors(плохо))))
    cap = Draft202012Validator(json.loads(
        (КОРЕНЬ / "schemas" / "Capability.v1.json").read_text()))
    планируемая = {"capability_id": "x", "owner_service": "y", "version": "1.0.0",
                   "status": "PLANNED", "read_endpoint": None,
                   "command_endpoint": None}
    шаг("Capability: PLANNED без адреса допустим",
        not list(cap.iter_errors(планируемая)))
    ложная = dict(планируемая, status="PLANNED", read_endpoint="/api/v1/x")
    шаг("Capability: PLANNED с адресом отвергается",
        bool(list(cap.iter_errors(ложная))))

# --- OpenAPI / AsyncAPI ------------------------------------------------------
oa = json.loads((КОРЕНЬ / "openapi.json").read_text(encoding="utf-8"))
шаг("OpenAPI 3.x с путями", oa.get("openapi", "").startswith("3.")
    and len(oa.get("paths", {})) >= 20, f"{len(oa.get('paths', {}))} путей")
aa = json.loads((КОРЕНЬ / "asyncapi.json").read_text(encoding="utf-8"))
шаг("AsyncAPI 2.x с каналами", aa.get("asyncapi", "").startswith("2.")
    and len(aa.get("channels", {})) >= 28, f"{len(aa.get('channels', {}))} каналов")
# Инвариант не в числе каналов, а в том, что ни один канал предыдущей версии
# не потерял статус: иначе потребитель, работавший вчера, сегодня молча
# перестал бы получать события.
_стало = {k for k, v in aa["channels"].items()
          if v["subscribe"].get("x-status") == "AVAILABLE"}
if ПРЕДЫДУЩАЯ and (БАЗА / ПРЕДЫДУЩАЯ / "asyncapi.json").exists():
    _база = json.loads((БАЗА / ПРЕДЫДУЩАЯ / "asyncapi.json").read_text(encoding="utf-8"))
    _было = {k for k, v in _база["channels"].items()
             if v["subscribe"].get("x-status") == "AVAILABLE"}
    шаг(f"каналы {ПРЕДЫДУЩАЯ} остались AVAILABLE", _было <= _стало,
        "потеряно: %s" % sorted(_было - _стало) if _было - _стало
        else "%d из %s" % (len(_было), ПРЕДЫДУЩАЯ))
else:
    шаг("доступные каналы объявлены", bool(_стало), str(len(_стало)))

# --- ownership ---------------------------------------------------------------
own = json.loads((КОРЕНЬ / "ownership-matrix.json").read_text(encoding="utf-8"))
по_рес: dict[str, set] = {}
for r in own["resources"]:
    по_рес.setdefault(r["resource"], set()).add(r["single_writer"])
конфликты = {k: v for k, v in по_рес.items() if len(v) > 1}
шаг("ресурсов с двумя писателями нет", not конфликты, str(конфликты))
шаг("каждый ресурс имеет владельца и политику",
    all(r.get("single_writer") and r.get("mutation_policy") for r in own["resources"]))

# --- секреты -----------------------------------------------------------------
ОПАСНО = re.compile(
    r"(Bearer\s+[A-Za-z0-9._\-]{16,}|(?:api[_-]?key|password|secret|token)"
    r"[\"']?\s*[:=]\s*[\"'][A-Za-z0-9._\-]{12,})", re.I)
найдено = []
for p in КОРЕНЬ.rglob("*"):
    if p.is_file():
        т = p.read_text(encoding="utf-8", errors="replace")
        for м in ОПАСНО.findall(т):
            найдено.append(f"{p.name}: {м[:24]}…")
шаг("секретов в артефактах нет", not найдено, "; ".join(найдено[:2]))

# --- статические списки сайтов ----------------------------------------------
# Ищутся ФАКТИЧЕСКИЕ боевые домены, а не всё, похожее на домен.
# Прежняя регулярка принимала за домен питоновский путь модуля
# (`factory.site_engine`, `api.site_filter`) и объявляла OpenAPI статическим
# списком сайтов. Проверка, дающая ложную тревогу, обесценивает себя: её
# начинают отключать вместо того, чтобы читать.
БОЕВЫЕ = {"lordfilm47.space", "lordserial33.biz", "1lordserials1.online",
          "yummyani.biz", "yummyani.org", "yummyani.site",
          "zonafilm.space", "animedia.icu", "animedia.space"}
списки = []
for p in КОРЕНЬ.rglob("*"):
    if p.is_file():
        т = p.read_text(encoding="utf-8", errors="replace")
        найденные = {д for д in БОЕВЫЕ if д in т}
        if len(найденные) >= 3:
            списки.append(f"{p.name}: {sorted(найденные)[:3]}")
шаг("статических production-списков не создано", not списки, "; ".join(списки))

# --- инвентарь ---------------------------------------------------------------
инвентарь = {
 "schema_version": "1.0.0",
 "entries": [
  {"name": "registry.api.v1", "owner": "architect", "kind": "http",
   "classification": "CANONICAL",
   "detail": "GET /api/v1/sites, sites/{id}, registry/version, snapshot, events"},
  {"name": "registry.events.outbox", "owner": "architect", "kind": "events",
   "classification": "CANONICAL", "detail": "site.*.v1 через durable outbox"},
  {"name": "control-plane.contracts", "owner": "architect", "kind": "http",
   "classification": "CANONICAL",
   "detail": "contracts/manifest|openapi|asyncapi|schemas, capabilities"},
  {"name": "config/site-profiles", "owner": "architect", "kind": "files",
   "classification": "COMPATIBLE_LEGACY",
   "detail": "первичное наполнение реестра; читается при недоступности БД",
   "migration": "источник истины — registry.sqlite3; профили остаются для отката"},
  {"name": "config/portfolio.json", "owner": "seo", "kind": "files",
   "classification": "COMPATIBLE_LEGACY",
   "detail": "реестр портфеля клиентов, пуст; production-доменов не содержит"},
  {"name": "config/portfolio.fixture.json", "owner": "seo", "kind": "files",
   "classification": "COMPATIBLE_LEGACY",
   "detail": "синтетический тенант example-fixture.test, synthetic:true"},
  {"name": "inventory/portfolios.yaml", "owner": "seo", "kind": "files",
   "classification": "UNKNOWN",
   "detail": "production-доменов не содержит; владелец подтверждён не был",
   "migration": "FLEET-SEO-003.R2 — подтвердить владельца и назначение"},
  {"name": "site-factory-seo-dryrun.service", "owner": "seo", "kind": "unit",
   "classification": "COMPATIBLE_LEGACY",
   "detail": "bin/seo-operator dry-run --fixture; вне полномочий ARCHITECT"},
  {"name": "COMPATIBILITY_MATRIX.yaml", "owner": "architect", "kind": "files",
   "classification": "CONFLICTING",
   "detail": "снимок живого состояния; seoEngineApi 1.4.0 против 1.5.0 у SEO",
   "migration": "пересоздавать запросом GET /api/v1/compatibility, не руками"},
  {"name": "templates/seo/content/monitoring/backup APIs", "owner": "various",
   "kind": "http", "classification": "PLANNED",
   "detail": "собственных API нет; контракты объявлены, реализаций нет"},
 ]}
(ОТЧЁТ / "contract-inventory.json").parent.mkdir(parents=True, exist_ok=True)
(ОТЧЁТ / "contract-inventory.json").write_text(
    json.dumps(инвентарь, ensure_ascii=False, indent=1), encoding="utf-8")
шаг("инвентарь текущих контрактов составлен",
    len(инвентарь["entries"]) >= 10, f"{len(инвентарь['entries'])} записей")

print("\n  провалов: %d" % len(провалы))
sys.exit(0 if not провалы else 1)
