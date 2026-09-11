#!/usr/bin/env python3
"""Патч-версия bundle 1.0.1: контракт приведён в соответствие с поведением."""
import datetime as dt, hashlib, json, pathlib, shutil, sys

СТАРЫЙ = pathlib.Path("/srv/site-factory/control-plane-contracts/1.0.0")
НОВЫЙ = pathlib.Path("/srv/site-factory/control-plane-contracts/1.0.1")
СЕЙЧАС = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

if НОВЫЙ.exists():
    shutil.rmtree(НОВЫЙ)
shutil.copytree(СТАРЫЙ, НОВЫЙ)

# --- OpenAPI: фактические enum, AND-семантика, ошибки, примеры --------------
oa = json.loads((НОВЫЙ / "openapi.json").read_text(encoding="utf-8"))
oa["info"]["version"] = "1.0.1"
sites = oa["paths"]["/api/v1/sites"]["get"]
sites.pop("x-known-gap", None)
sites["description"] = (
    "Без параметров возвращает полный текущий реестр. Параметры применяются "
    "на стороне сервера ДО нарезки страниц; два параметра соединяются через "
    "AND. Недопустимое, пустое или противоречивое значение не игнорируется, "
    "а отвергается с 422 и Problem.v1.")
sites["parameters"] = [
    {"name": "environment", "in": "query", "required": False,
     "schema": {"type": "string",
                "enum": ["production", "non-production", "test"]},
     "description": ("сравнение по каноническому значению; регистр не "
                     "нормализуется, похожие значения не подставляются")},
    {"name": "lifecycle_state", "in": "query", "required": False,
     "schema": {"type": "string",
                "enum": ["DRAFT", "ACTIVE", "QUARANTINED", "RETIRED"]},
     "description": "перечень совпадает с CHECK-ограничением таблицы site"},
]
sites["responses"] = {
    "200": {"description": ("отфильтрованная выдача; пустой массив при "
                            "валидной комбинации без совпадений — это ответ, "
                            "а не ошибка")},
    "422": {"description": ("значение фильтра недопустимо, пусто или "
                            "противоречиво; error_code из перечня "
                            "FILTER_VALUE_UNKNOWN, FILTER_VALUE_EMPTY, "
                            "FILTER_VALUE_CONFLICT")},
    "503": {"description": "зависимость недоступна"},
}
sites["x-filter-semantics"] = {
    "combination": "AND", "applied": "server-side",
    "order": "фильтр применяется до pagination и cursor slicing",
    "canonical_predicate": "factory.site_engine.api.site_filter",
    "shared_with": ["/api/v1/registry/snapshot"],
    "silent_ignore": False}
sites["x-examples"] = {
    "все": {"request": "/api/v1/sites", "note": "полный реестр"},
    "боевые действующие": {
        "request": "/api/v1/sites?environment=production&lifecycle_state=ACTIVE",
        "note": "ровно та же проекция, что у /api/v1/registry/snapshot"},
    "неизвестное значение": {
        "request": "/api/v1/sites?environment=nonsense",
        "response_status": 422, "error_code": "FILTER_VALUE_UNKNOWN"},
    "пустое значение": {"request": "/api/v1/sites?environment=",
                        "response_status": 422,
                        "error_code": "FILTER_VALUE_EMPTY"},
    "конфликт ключа": {
        "request": "/api/v1/sites?environment=production&environment=test",
        "response_status": 422, "error_code": "FILTER_VALUE_CONFLICT"},
    "валидная пустая выдача": {
        "request": "/api/v1/sites?environment=non-production&lifecycle_state=RETIRED",
        "response_status": 200, "count": 0},
}
(НОВЫЙ / "openapi.json").write_text(
    json.dumps(oa, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")

# --- каталог ошибок: три кода фильтра ---------------------------------------
ec = json.loads((НОВЫЙ / "error-catalog.json").read_text(encoding="utf-8"))
существующие = {e["error_code"] for e in ec["errors"]}
for код, деталь in (
    ("FILTER_VALUE_UNKNOWN", "значение не входит в канонический перечень"),
    ("FILTER_VALUE_EMPTY", "параметр задан пустым значением"),
    ("FILTER_VALUE_CONFLICT", "параметр повторён с разными значениями")):
    if код not in существующие:
        ec["errors"].append({"error_code": код, "status": 422,
                             "retryable": False, "owner": "architect",
                             "detail": деталь})
ec["generated_at"] = СЕЙЧАС
(НОВЫЙ / "error-catalog.json").write_text(
    json.dumps(ec, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")

# --- changelog ---------------------------------------------------------------
(НОВЫЙ / "CHANGELOG.md").write_text(
    (СТАРЫЙ / "CHANGELOG.md").read_text(encoding="utf-8").replace(
        "# fleet-control-plane-contracts",
        f"""# fleet-control-plane-contracts

## 1.0.1 — {СЕЙЧАС}

Патч. Ломающих изменений нет.

Исправлено: `SITES_QUERY_FILTER_NOT_APPLIED`. Провайдер применяет
`environment` и `lifecycle_state` на стороне сервера, соединяет их через AND
и делает это до нарезки страниц. Недопустимое, пустое и противоречивое
значение больше не игнорируются — 422 с `Problem.v1` и стабильным кодом.

Корень дефекта был в двух местах, и оба молчали:

* обработчик `_sites` принимал параметры и не использовал их;
* разбор строки запроса терял пустое значение (`parse_qs` без
  `keep_blank_values`) и схлопывал повтор ключа в последнее значение,
  поэтому противоречие в запросе было невидимо.

Фильтр и `/api/v1/registry/snapshot` переведены на ОДИН предикат
(`factory.site_engine.api.site_filter`). Две независимые реализации одного
правила разошлись бы молча.

Обход через snapshot убран из референсных клиентов: они снова берут девять
боевых сайтов фильтром. Snapshot остаётся отдельной неизменяемой проекцией,
но перестал быть компенсацией сломанного endpoint.

Возможность `registry.sites.filter` объявлена AVAILABLE после прохождения
живой матрицы A–L (28 проверок).
"""), encoding="utf-8")
print("bundle 1.0.1 собран")
