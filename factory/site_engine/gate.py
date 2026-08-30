"""Архитектурный гейт: что обязан иметь сайт, чтобы его можно было принять.

Проверки здесь не абстрактные. Каждая выросла из поломки, которая уже
случалась в этом проекте:

* витрина ходила в API поставщика прямо из отрисовки — сотни запросов на
  открытие главной;
* SEO и загрузчик жили в одном месте, и правка текстов задевала снимок;
* схема без версии молча меняла смысл поля, и потребитель этого не замечал;
* каталог обрезался на 4800 записях из 53 115, потому что никто не проверял
  признак обрыва;
* одна новая серия запускала пересборку всего каталога.

Гейт нужен не для новых сайтов вообще, а для того, чтобы каждый следующий не
повторял этот список заново.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

import jsonschema

SCHEMA_DIR = "schemas/site-engine"
PROFILE_DIR = "config/site-profiles"

#: Слова, которые не должны появляться в общем ядре. Отдельные адаптеры с
#: такими именами допустимы — ядро, знающее про аниме, потребует правки при
#: первом же сайте другого рода.
DOMAIN_SPECIFIC_WORDS = ("anime", "yummy", "lords", "аниме")

#: Поля, в которых секрет узнаётся по форме, а не по имени.
SECRET_SHAPE = re.compile(r"[A-Za-z0-9_\-]{24,}")

#: Имена, намекающие на секрет.
SECRET_KEYS = re.compile(r"(?i)(token|secret|password|api[_-]?key|credential(?!s_ref))")


@dataclass
class GateResult:
    site_id: str
    problems: list[str] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return not self.problems

    def fail(self, message: str) -> None:
        self.problems.append(message)


def _load_schema(root: Path, name: str) -> dict:
    return json.loads((root / SCHEMA_DIR / name).read_text(encoding="utf-8"))


def _validator(root: Path):
    """Валидатор, умеющий разрешать ссылки между схемами каталога."""
    registry = {}
    for path in (root / SCHEMA_DIR).glob("*.json"):
        schema = json.loads(path.read_text(encoding="utf-8"))
        registry[path.name] = schema
        registry[schema.get("$id", path.name)] = schema

    def retrieve(uri: str):
        key = uri.rsplit("/", 1)[-1]
        if key in registry:
            return jsonschema.validators.Resource.from_contents(
                registry[key], default_specification=jsonschema.validators.Draft202012Validator.META_SCHEMA
            )
        raise jsonschema.exceptions._RefResolutionError(f"неизвестная ссылка {uri}")

    return retrieve, registry


def _find_secrets(node, path: str = "") -> list[str]:
    """Секрет в профиле — это утечка: профиль лежит в git."""
    found: list[str] = []
    if isinstance(node, dict):
        for key, value in node.items():
            here = f"{path}.{key}" if path else key
            if SECRET_KEYS.search(key) and isinstance(value, str) and SECRET_SHAPE.fullmatch(value):
                found.append(f"похоже на секрет в поле {here}")
            found.extend(_find_secrets(value, here))
    elif isinstance(node, list):
        for index, value in enumerate(node):
            found.extend(_find_secrets(value, f"{path}[{index}]"))
    return found


#: Чем может быть удовлетворено требование нормализованного контента.
NORMALIZED_CONTENT_KINDS = ("content-ingestion", "site-engine-api", "adapter")


def _normalized_content_problem(profile: dict, modules: set[str]) -> str | None:
    """Есть ли у сайта источник нормализованного контента.

    Три законных способа: собственный загрузчик, общий Site Engine API или
    другой зарегистрированный адаптер. Любой из них снимает вопрос; отсутствие
    всех трёх означает, что SEO пришлось бы добывать содержимое самому — а это
    ровно то смешение, которого гейт и не допускает.
    """
    if "content-ingestion" in modules:
        return None

    source = profile.get("normalized_content_source")
    if not isinstance(source, dict) or not source:
        return (
            "SEO включён, но источник нормализованного контента не объявлен: "
            "нужен собственный content-ingestion, общий Site Engine API либо "
            "другой зарегистрированный адаптер"
        )
    kind = source.get("kind")
    if kind not in NORMALIZED_CONTENT_KINDS:
        return (
            f"источник нормализованного контента «{kind}» не из числа "
            f"разрешённых: {', '.join(NORMALIZED_CONTENT_KINDS)}"
        )
    if not str(source.get("ref") or "").strip():
        # Объявить источник и не назвать его — то же, что не объявить.
        return f"источник нормализованного контента «{kind}» объявлен без ссылки"
    return None


def check_profile(profile: dict, root: Path) -> GateResult:
    result = GateResult(site_id=str(profile.get("site_id") or "<без site_id>"))

    # 1. Схема и её версия.
    if not profile.get("schema_version"):
        result.fail("нет schema_version: потребитель не сможет отличить версии контракта")
    try:
        schema = _load_schema(root, "site-profile.schema.json")
        cache_schema = _load_schema(root, "cache-policy.schema.json")
        merged = json.loads(json.dumps(schema).replace(
            '{"$ref": "cache-policy.schema.json"}', json.dumps(cache_schema)))
        jsonschema.Draft202012Validator(merged).validate(profile)
    except jsonschema.ValidationError as error:
        location = "/".join(str(p) for p in error.path) or "(корень)"
        result.fail(f"профиль не проходит схему: {location}: {error.message}")
    except FileNotFoundError as error:
        result.fail(f"схема не найдена: {error}")

    # 2. Секреты.
    for problem in _find_secrets(profile):
        result.fail(problem)

    # 3. Стратегия рендера и политика кэша.
    if not (profile.get("render_strategy") or {}).get("mode"):
        result.fail("не задана стратегия рендера")
    cache = profile.get("cache_policy") or {}
    if not cache.get("layers"):
        result.fail("не задана политика кэша: сроки для разных данных различаются")

    # 4. Одно событие не должно пересобирать всё.
    event_map = ((cache.get("invalidation") or {}).get("event_map") or {})
    if event_map:
        for event, tags in event_map.items():
            if any(tag in ("*", "all", "everything") for tag in tags):
                result.fail(
                    f"событие {event} сбрасывает весь кэш: пересборка каталога ради "
                    "одного изменения занимает часы"
                )

    # 5. Health и покрытие.
    if not profile.get("health_endpoint"):
        result.fail("нет health endpoint: остановку нечем заметить")
    if not profile.get("coverage_endpoint"):
        result.fail("нет coverage endpoint: неполный каталог нечем поймать")

    # 6. Модули и владельцы.
    modules = set(profile.get("enabled_modules") or [])
    # Адаптер поставщика нужен тому, кто к поставщику ходит. Сайт, берущий
    # готовый нормализованный контент из общего API, к поставщику не ходит
    # вовсе — требовать от него адаптер значит требовать код, которому нечего
    # делать. Это ровно та же ошибка, что была с SEO: правило называло модуль
    # там, где речь о способности.
    goes_to_provider = "content-ingestion" in modules or bool(profile.get("content_providers"))
    if goes_to_provider and "provider-adapters" not in modules:
        result.fail("нет provider-adapters: витрина обращалась бы к поставщику напрямую")
    if not goes_to_provider and "provider-adapters" in modules:
        result.fail(
            "объявлен provider-adapters, но сайт не ходит к поставщику: "
            "ни content-ingestion, ни content_providers"
        )
    if "renderer-adapters" not in modules:
        result.fail("нет renderer-adapters")
    if not profile.get("owners"):
        result.fail("не указаны владельцы модулей")

    # 7. SEO нужен нормализованный контент — но не обязательно свой загрузчик.
    #
    # Прежнее правило требовало модуль `content-ingestion` и тем самым
    # запрещало правильную схему: витрину, которая берёт готовый контент из
    # общего Site Engine API и ничего не загружает сама. Требование — наличие
    # источника нормализованного контента, а откуда он приходит, сайт вправе
    # решать.
    if "seo" in modules and (profile.get("seo_profile") or {}).get("enabled", True):
        problem = _normalized_content_problem(profile, modules)
        if problem:
            result.fail(problem)

    # 8. Откат.
    release = profile.get("release_policy") or {}
    if not release.get("rollback_ready"):
        result.fail("не объявлена готовность отката")
    if int(release.get("keep_releases") or 0) < 2:
        result.fail("хранится меньше двух релизов: откатываться некуда")

    return result


def check_core_neutrality(root: Path, core_paths: tuple[str, ...]) -> list[str]:
    """Ядро не должно знать про конкретные сайты.

    Проверяются только общие модули: адаптер с именем провайдера — это норма,
    а вот условие «если аниме» внутри общего кода означает, что следующий тип
    сайта потребует правки ядра.
    """
    problems: list[str] = []
    for relative in core_paths:
        path = root / relative
        if not path.exists():
            continue
        for file in path.rglob("*.py"):
            # Сам гейт из проверки исключён: список запрещённых слов лежит
            # в нём, и он справедливо находил бы себя. Адаптеры тоже: имя
            # поставщика в адаптере — это норма, а не протечка в ядро.
            if (
                "__pycache__" in str(file)
                or "adapters" in str(file)
                # Оба гейта вынуждены хранить сам список запрещённых
                # слов и потому ловили бы сами себя.
                or file.name in ("gate.py", "boundaries.py")
            ):
                continue
            text = file.read_text(encoding="utf-8", errors="ignore").lower()
            # Ищем в коде, а не в комментариях: объяснить, откуда взялось
            # правило, комментарий имеет право.
            code = "\n".join(
                line for line in text.splitlines()
                if not line.strip().startswith("#")
            )
            for word in DOMAIN_SPECIFIC_WORDS:
                if re.search(rf'["\']\w*{word}\w*["\']', code):
                    problems.append(f"{file.relative_to(root)}: в ядре встречается «{word}»")
                    break
    return problems


def run(root: Path | str = ".") -> tuple[bool, list[GateResult], list[str]]:
    root = Path(root)
    results = []
    for path in sorted((root / PROFILE_DIR).glob("*.json")):
        profile = json.loads(path.read_text(encoding="utf-8"))
        results.append(check_profile(profile, root))
    core = check_core_neutrality(root, ("factory/site_engine",))
    ok = all(r.passed for r in results) and not core
    return ok, results, core
