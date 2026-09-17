#!/usr/bin/env python3
"""Сборка bundle 1.4.0 — состояния, класс риска и условие запроса.

Что меняется и почему именно так
--------------------------------

1.3.1 объявляет восемнадцать состояний набора изменений, в которых «эффект
создан» и «эффект подтверждён наблюдением» — одно и то же. Различаются они
последствиями: после первого нужен откат, после второго нет, — и контракт,
который их не различает, заставляет читающего догадываться.

Там же risk_class принимает LOW/MEDIUM/HIGH. Эта шкала отвечает на вопрос
«сколько и где», а решения по ней принимаются как о вопросе «что затронуто».
Значения заменены на R0–R4 (по последствиям), а прежняя шкала осталась
отдельным полем impact_level — потому что измеряет она другое и нужна тоже.

Замена значений перечисления — единственное неаддитивное изменение здесь,
поэтому растёт минорная версия, а 1.3.1 остаётся на месте: читающие по нему
продолжают работать, пока не перейдут.
"""

from __future__ import annotations

import datetime as _d
import hashlib
import json
import pathlib

КОРЕНЬ = pathlib.Path(__file__).resolve().parent
ИЗ, В = "1.3.1", "1.4.0"

НОВЫЕ_СОСТОЯНИЯ = ["APPLIED", "VERIFIED", "ROLLBACK_REQUESTED"]
КЛАССЫ_РИСКА = ["R0", "R1", "R2", "R3", "R4"]
УРОВНИ_ВЛИЯНИЯ = ["LOW", "MEDIUM", "HIGH"]

НОВЫЕ_ОШИБКИ = [
    {
        "error_code": "VERSION_CONFLICT",
        "status": 409,
        "retryable": True,
        "owner": "control-plane",
        "detail": "версия ресурса разошлась с ожидаемой",
    },
    {
        "error_code": "EXPECTED_VERSION_INVALID",
        "status": 422,
        "retryable": False,
        "owner": "control-plane",
        "detail": "expected_resource_version или If-Match разобрать нельзя, "
        "либо они расходятся между собой",
    },
    {
        "error_code": "FILTER_VALUE_UNKNOWN",
        "status": 422,
        "retryable": False,
        "owner": "control-plane",
        "detail": "значение фильтра не принадлежит перечислению",
    },
    {
        "error_code": "EVENT_VERSION_UNKNOWN",
        "status": 422,
        "retryable": False,
        "owner": "control-plane",
        "detail": "версия события неизвестна этому выпуску; запись задержана",
    },
    {
        "error_code": "LEDGER_UNAVAILABLE_EXHAUSTED",
        "status": 503,
        "retryable": False,
        "owner": "control-plane",
        "detail": "журнал недоступен дольше предела повторов; запись ушла "
        "в очередь недоставленного",
    },
]

#: Коды, которые контур возвращал и раньше, но каталог о них не знал. Найдены
#: проверкой паритета: она разбирает исходники и сравнивает с каталогом, а не
#: полагается на то, что список поддерживали вручную.
РАНЕЕ_НЕ_ОБЪЯВЛЕННЫЕ = [
    ("CHANGESET_NOT_FOUND", 404, False, "набора изменений с таким идентификатором нет"),
    (
        "DRY_RUN_HAD_EFFECTS",
        500,
        False,
        "сухой прогон создал эффекты: планировщик неисправен, применение закрыто",
    ),
    (
        "FENCING_TOKEN_REQUIRED",
        409,
        True,
        "действие требует маркера ограждения: сначала берётся аренда",
    ),
    (
        "FENCING_TOKEN_UNKNOWN",
        409,
        False,
        "предъявлен маркер, который не выдавался или уже перекрыт новым",
    ),
    ("FIELD_REQUIRED", 422, False, "обязательное поле запроса не заполнено"),
    (
        "FILTER_VALUE_INVALID",
        422,
        False,
        "значение параметра не разбирается: after и limit — целые",
    ),
    (
        "IRREVERSIBLE_PLAN",
        422,
        False,
        "план не имеет отката: необратимое изменение через контур не проводится",
    ),
    ("LEASE_REQUIRED", 409, True, "действие требует действующей аренды"),
    ("LIFECYCLE_FORBIDDEN", 409, False, "состояние жизненного цикла цели не допускает изменения"),
    ("METHOD_NOT_ALLOWED", 405, False, "маршрут не принимает этот метод"),
    ("NOT_FOUND", 404, False, "маршрут или действие не найдено"),
    ("OPERATION_UNKNOWN", 422, False, "род операции неизвестен"),
    ("OPERATION_UNSUPPORTED", 422, False, "род ресурса такой операции не допускает"),
    ("OWNERSHIP_MISMATCH", 409, False, "ресурс принадлежит другой службе: чужую запись не меняют"),
    ("PAYLOAD_KEY_INVALID", 422, False, "ключ в содержимом запроса недопустим"),
    ("PAYLOAD_TOO_DEEP", 422, False, "вложенность содержимого больше предела"),
    ("PAYLOAD_TOO_LARGE", 422, False, "содержимое длиннее предела"),
    ("PAYLOAD_TYPE_INVALID", 422, False, "тип значения в содержимом недопустим"),
    ("PLAN_REQUIRED", 422, True, "одобрять нечего: план ещё не построен"),
    ("TARGETS_REQUIRED", 422, False, "нужен хотя бы один site_id"),
]
НОВЫЕ_ОШИБКИ += [
    {"error_code": к, "status": с, "retryable": п, "owner": "control-plane", "detail": д}
    for к, с, п, д in РАНЕЕ_НЕ_ОБЪЯВЛЕННЫЕ
]

НОВЫЕ_СОБЫТИЯ = {
    "changeset.verifying.v1": "проверка начата: наблюдение читается заново",
    "changeset.verified.v1": "наблюдение совпало с ожидаемым",
    "changeset.rollback_requested.v1": "компенсация запрошена, но не начата",
}


def sha256(п: pathlib.Path) -> str:
    return hashlib.sha256(п.read_bytes()).hexdigest()


def записать(п: pathlib.Path, данные) -> None:
    п.write_text(json.dumps(данные, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")


def _прочитать(п: pathlib.Path):
    return json.loads(п.read_text("utf-8"))


def собрать() -> dict:
    import shutil

    источник, цель = КОРЕНЬ / ИЗ, КОРЕНЬ / В
    if цель.exists():
        shutil.rmtree(цель)
    shutil.copytree(источник, цель)

    # --- схема набора изменений ------------------------------------------
    сх = _прочитать(цель / "schemas/ChangeSet.v1.json")
    св = сх["properties"]
    статусы = list(св["status"]["enum"])
    for с in НОВЫЕ_СОСТОЯНИЯ:
        if с not in статусы:
            # Порядок не алфавитный, а по ходу жизни набора: перечисление
            # читают люди, и APPLIED между APPLYING и VERIFYING говорит о
            # машине больше, чем та же строка в конце списка.
            якорь = {
                "APPLIED": "APPLYING",
                "VERIFIED": "VERIFYING",
                "ROLLBACK_REQUESTED": "APPLY_FAILED",
            }[с]
            статусы.insert(статусы.index(якорь) + 1, с)
    св["status"]["enum"] = статусы
    св["status"]["description"] = (
        "Состояние набора. APPROVED, APPLIED и VERIFIED — три разных "
        "утверждения: разрешено начать, мир изменён, изменение подтверждено "
        "наблюдением. Сводить их в одно значило бы терять разницу, ради "
        "которой состояние и смотрят."
    )

    св["risk_class"]["enum"] = [*КЛАССЫ_РИСКА, None]
    св["risk_class"]["description"] = (
        "Класс риска по тому, ЧТО затронуто: R0 — чтение и аудит; "
        "R1 — черновики и теневой контур; R2 — содержимое, метаданные и "
        "ссылки; R3 — canonical, robots, sitemap, перенаправления, "
        "индексация и массовые изменения; R4 — DNS, секреты, права, "
        "удаление и принудительные операции. Неизвестный род ресурса "
        "относится к R3: отсутствие сведений не довод считать изменение "
        "безобидным."
    )
    св["impact_level"] = {
        "type": ["string", "null"],
        "enum": [*УРОВНИ_ВЛИЯНИЯ, None],
        "description": "Ширина охвата: сколько целей и в каком окружении. "
        "Отдельная от risk_class величина — правка текста на "
        "девяти витринах шире по охвату, чем смена DNS на "
        "одной, но дешевле по последствиям.",
    }
    св["request_id"] = {
        "type": ["string", "null"],
        "maxLength": 200,
        "description": "Идентификатор запроса, вызвавшего изменение. "
        "Принимается полем тела или заголовком X-Request-Id.",
    }
    записать(цель / "schemas/ChangeSet.v1.json", сх)

    # --- схема перехода ---------------------------------------------------
    сп = _прочитать(цель / "schemas/ChangeSetTransition.v1.json")
    if "status" in сп.get("properties", {}):
        pass
    сп["properties"]["request_id"] = {
        "type": ["string", "null"],
        "maxLength": 200,
        "description": "Запрос, которым вызван переход.",
    }
    for имя in ("from_status", "to_status"):
        if имя in сп["properties"] and "enum" in сп["properties"][имя]:
            сп["properties"][имя]["enum"] = статусы
    записать(цель / "schemas/ChangeSetTransition.v1.json", сп)

    # --- каталог ошибок ----------------------------------------------------
    ош = _прочитать(цель / "error-catalog.json")

    # В каталоге уживаются две формы записи — унаследованная разнобойность.
    # Приводить её к одной здесь не место: это отдельное изменение, и смешав
    # его с этим, нельзя было бы сказать, что именно сломалось.
    def код(з: dict) -> str:
        return з.get("error_code") or з.get("code") or ""

    есть = {код(з) for з in ош["errors"]}
    for з in НОВЫЕ_ОШИБКИ:
        if з["error_code"] not in есть:
            ош["errors"].append(з)
    ош["errors"].sort(key=код)
    записать(цель / "error-catalog.json", ош)

    # --- события -----------------------------------------------------------
    ас = _прочитать(цель / "asyncapi.json")
    каналы = ас.setdefault("channels", {})
    # Имя канала — не имя события: у каналов свой префикс, и собрать его
    # «по смыслу» нельзя, поэтому образец берётся из уже объявленного
    # события того же семейства вместе со всей его обвязкой.
    образец_имя = next((и for и in каналы if и.endswith("/changeset.applied.v1")), None)
    if образец_имя is None:
        raise SystemExit("не найден образец канала changeset.applied.v1")
    префикс = образец_имя[: образец_имя.rindex("/") + 1]
    for имя, пояснение in НОВЫЕ_СОБЫТИЯ.items():
        ключ = префикс + имя
        if ключ in каналы:
            continue
        канал = json.loads(json.dumps(каналы[образец_имя]))
        подписка = канал.setdefault("subscribe", {})
        подписка["summary"] = пояснение
        подписка["operationId"] = имя.replace(".", "_")
        подписка.setdefault("message", {})["name"] = имя
        каналы[ключ] = канал
    записать(цель / "asyncapi.json", ас)

    # --- OpenAPI -----------------------------------------------------------
    o = _прочитать(цель / "openapi.json")
    список = o["paths"]["/api/v1/changesets"]["get"]
    параметры = список.setdefault("parameters", [])
    по_имени = {p.get("name"): p for p in параметры}
    if "status" in по_имени:
        по_имени["status"].setdefault("schema", {})["enum"] = статусы
    if "risk_class" in по_имени:
        по_имени["risk_class"].setdefault("schema", {})["enum"] = КЛАССЫ_РИСКА
    if "impact_level" not in по_имени:
        параметры.insert(
            параметры.index(по_имени["risk_class"]) + 1
            if "risk_class" in по_имени
            else len(параметры),
            {
                "name": "impact_level",
                "in": "query",
                "required": False,
                "description": "Фильтр по ширине охвата.",
                "schema": {"type": "string", "enum": УРОВНИ_ВЛИЯНИЯ},
            },
        )

    заголовок_версии = {
        "name": "If-Match",
        "in": "header",
        "required": False,
        "description": "Версия ресурса, на которую опирается отправитель. "
        "Расхождение даёт 409 и ничего не записывает.",
        "schema": {"type": "string"},
    }
    для_действий = [p for p in o["paths"] if p.startswith("/api/v1/changesets/{changeset_id}")]
    for путь in для_действий:
        for метод, оп in o["paths"][путь].items():
            if метод == "get":
                отв = оп.get("responses", {}).get("200")
                if isinstance(отв, dict):
                    отв.setdefault("headers", {})["ETag"] = {
                        "description": "Версия ресурса; возвращается обратно " "в If-Match.",
                        "schema": {"type": "string"},
                    }
                continue
            пар = оп.setdefault("parameters", [])
            if not any(p.get("name") == "If-Match" for p in пар):
                пар.append(dict(заголовок_версии))
            тело = (
                оп.setdefault("requestBody", {})
                .setdefault("content", {})
                .setdefault("application/json", {})
                .setdefault("schema", {"type": "object", "properties": {}})
            )
            св_тела = тело.setdefault("properties", {})
            св_тела.setdefault(
                "expected_resource_version",
                {
                    "type": "integer",
                    "minimum": 1,
                    "description": "То же, что If-Match, полем тела. Заданы оба "
                    "и расходятся — запрос отклоняется.",
                },
            )
            св_тела.setdefault(
                "request_id",
                {
                    "type": "string",
                    "maxLength": 200,
                    "description": "Идентификатор запроса для истории.",
                },
            )
            оп.setdefault("responses", {}).setdefault(
                "409",
                {
                    "description": "версия ресурса или ключ идемпотентности "
                    "разошлись с текущим состоянием"
                },
            )
    записать(цель / "openapi.json", o)

    # --- сопроводительные тексты -------------------------------------------
    дата = _d.datetime.now(_d.timezone.utc).strftime("%Y-%m-%d")
    чл = (цель / "CHANGELOG.md").read_text("utf-8")
    (цель / "CHANGELOG.md").write_text(
        f"""## {В} — {дата}

Добавлены состояния APPLIED, VERIFIED и ROLLBACK_REQUESTED. Прежде «эффект
создан» и «эффект подтверждён наблюдением» были одним состоянием, а
различаются они последствиями: после первого нужен откат, после второго нет.

risk_class сменил значения с LOW/MEDIUM/HIGH на R0–R4. Прежняя шкала отвечала
на вопрос «сколько и где», а читалась как «что затронуто». Ширина охвата
осталась отдельным полем impact_level.

Добавлены expected_resource_version и заголовки If-Match/ETag: отправитель
теперь может сказать, на какую картину мира он опирается, и не применить
изменение поверх того, чего не видел. Добавлен request_id.

Новые коды ошибок: VERSION_CONFLICT, EXPECTED_VERSION_INVALID,
FILTER_VALUE_UNKNOWN, EVENT_VERSION_UNKNOWN, LEDGER_UNAVAILABLE_EXHAUSTED.

Замена значений risk_class — неаддитивное изменение, поэтому растёт минорная
версия. {ИЗ} остаётся на месте: читающие по нему работают, пока не перейдут.

"""
        + чл,
        encoding="utf-8",
    )

    (цель / "MIGRATION.md").write_text(
        f"""# Переход {ИЗ} → {В}

## risk_class

Значения LOW/MEDIUM/HIGH заменены на R0–R4. Прямого соответствия нет и быть
не может: старая шкала измеряла охват, новая — последствия. Тот, кому нужен
именно охват, читает новое поле impact_level; его значения совпадают со
старыми буквально.

## Состояния

APPLIED, VERIFIED и ROLLBACK_REQUESTED добавлены в середину жизненного цикла.
Читающий, который сравнивал состояние с SUCCEEDED, продолжает работать.
Читающий, который считал, что за APPLYING сразу следует VERIFYING, увидит
между ними APPLIED — и это ровно та разница, ради которой состояние введено.

## Условие запроса

expected_resource_version и If-Match необязательны. Запрос без них ведёт себя
как прежде — с той оговоркой, что «как прежде» означает «без защиты от
записи поверх чужого изменения».
""",
        encoding="utf-8",
    )

    # --- манифест и контрольные суммы --------------------------------------
    м = _прочитать(цель / "manifest.json")
    м["version"] = В
    м["generated_at"] = _d.datetime.now(_d.timezone.utc).isoformat().replace("+00:00", "Z")
    м["schemas_count"] = len(list((цель / "schemas").glob("*.json")))
    записать(цель / "manifest.json", м)

    суммы = {"version": В, "algorithm": "sha256", "files": {}}
    for п in sorted(цель.rglob("*")):
        if п.is_file() and п.name != "checksums.json":
            суммы["files"][str(п.relative_to(цель))] = sha256(п)
    записать(цель / "checksums.json", суммы)
    return {
        "version": В,
        "files": len(суммы["files"]),
        "statuses": len(статусы),
        "errors": len(ош["errors"]),
    }


if __name__ == "__main__":
    print(json.dumps(собрать(), ensure_ascii=False, indent=1))
