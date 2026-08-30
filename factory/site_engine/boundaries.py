"""Гейт границ модулей: правила, которые нельзя нарушить незаметно.

Документ о том, «кто кого не должен импортировать», расходится с кодом за
неделю. Этот гейт читает реестр модулей и сам код и падает, когда они
расходятся.

Проверяется семь правил, и каждое соответствует уже случившемуся смешению:

1. Модуль импортирует публичный интерфейс другого, а не его внутренние файлы.
2. Модуль не импортирует того, что ему запрещено реестром.
3. Ядро контрактов не зависит ни от чего.
4. Ядро не знает названий конкретных сайтов и технологий.
5. Между модулями нет взаимных зависимостей.
6. Заявленная реализация существует.
7. Модуль, помеченный CONTRACT_ONLY, не притворяется реализованным.
"""
from __future__ import annotations

import ast
import json
import re
from dataclasses import dataclass, field
from pathlib import Path

PACKAGE = "factory.site_engine"
REGISTRY_PATH = Path("config/site-engine/module-registry.json")

#: Слова, которых не должно быть в универсальном ядре. Список живёт здесь же,
#: поэтому сам этот файл из проверки исключён — иначе он ловил бы сам себя.
DOMAIN_WORDS = ("yummy", "anime", "lords", "dle", "lordfilm", "lordserial", "yummyani")

#: Файлы, которым разрешено называть предметную область: адаптеры для того и
#: существуют, чтобы знать про конкретную реализацию, а гейты вынуждены хранить
#: сам список запрещённых слов.
DOMAIN_AWARE = ("adapters/", "boundaries.py", "gate.py")

#: Пакеты, у которых есть публичный интерфейс в `__init__`, а остальное —
#: устройство. Обращаться к их внутренностям снаружи нельзя.
PRIVATE_PACKAGES = ("api",)


def code_without_prose(source: str) -> str:
    """Исходник без комментариев и строк документации.

    Правило запрещает ядру *вести себя* по-разному для разных сайтов, а не
    упоминать их в объяснении. Комментарий «витрины Lords месяцами показывали
    старый каталог» — это причина, по которой код написан именно так, и она
    ценнее, чем формальная чистота текста. А вот литерал "lords-01" внутри
    условия — настоящее нарушение, и он остаётся видимым.
    """
    import io
    import tokenize

    kept: list[str] = []
    previous = tokenize.INDENT
    try:
        tokens = list(tokenize.generate_tokens(io.StringIO(source).readline))
    except (tokenize.TokenError, IndentationError):
        return source
    for token in tokens:
        if token.type == tokenize.COMMENT:
            continue
        if token.type == tokenize.STRING and previous in (
            tokenize.INDENT,
            tokenize.NEWLINE,
            tokenize.NL,
            tokenize.DEDENT,
        ):
            # Строка на месте инструкции — это docstring.
            previous = token.type
            continue
        kept.append(token.string)
        if token.type not in (tokenize.NL, tokenize.NEWLINE):
            previous = token.type
    return " ".join(kept)


@dataclass
class BoundaryResult:
    problems: list[str] = field(default_factory=list)
    checked_modules: int = 0
    checked_files: int = 0

    @property
    def passed(self) -> bool:
        return not self.problems

    def fail(self, message: str) -> None:
        self.problems.append(message)


def load_registry(root: Path) -> dict:
    path = root / REGISTRY_PATH
    if not path.exists():
        raise FileNotFoundError(f"реестра модулей нет: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def _imports(source: str) -> set[str]:
    """Импорты по разбору AST.

    Именно AST, а не поиск по тексту: слово «import» в комментарии или в строке
    документации импортом не является, и гейт, который этого не различает,
    падает на собственной документации.
    """
    found: set[str] = set()
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return found
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module and not node.level:
            found.add(node.module)
    return found


def _module_of(path: Path, root: Path) -> str:
    """Какому модулю реестра принадлежит файл."""
    rel = path.relative_to(root / "factory" / "site_engine")
    stem = rel.as_posix()
    mapping = {
        "contracts.py": "core-contracts",
        "profiles.py": "site-configuration",
        "scaffold.py": "site-configuration",
        "providers.py": "provider-adapters",
        "ingestion.py": "content-ingestion",
        "store.py": "normalized-content",
        "cache.py": "cache-invalidation",
        "editorial.py": "editorial",
        "audit.py": "audit",
        "renderers.py": "renderer-adapters",
    }
    if stem in mapping:
        return mapping[stem]
    if stem.startswith("adapters/"):
        return "renderer-adapters" if stem.endswith("_renderer.py") else "provider-adapters"
    if stem.startswith("api/"):
        return "site-engine-api"
    return ""


def check(root: Path | str = ".") -> BoundaryResult:
    root = Path(root)
    result = BoundaryResult()
    registry = load_registry(root)
    modules = {m["id"]: m for m in registry["modules"]}
    result.checked_modules = len(modules)

    implementations = {
        m["id"]: m["implementation"] for m in registry["modules"] if m.get("implementation")
    }

    # 6. Заявленная реализация существует.
    for module_id, rel in implementations.items():
        if not (root / rel).exists():
            result.fail(f"{module_id}: реализация заявлена как {rel}, а файла нет")

    # 7. CONTRACT_ONLY не притворяется реализованным.
    for module in registry["modules"]:
        if module["status"] == "CONTRACT_ONLY" and module.get("implementation"):
            result.fail(
                f"{module['id']}: помечен CONTRACT_ONLY, но объявляет реализацию "
                f"{module['implementation']}"
            )

    file_module: dict[Path, str] = {}
    sources: dict[Path, str] = {}
    engine_dir = root / "factory" / "site_engine"
    for path in sorted(engine_dir.rglob("*.py")):
        if "__pycache__" in path.parts:
            continue
        sources[path] = path.read_text(encoding="utf-8")
        file_module[path] = _module_of(path, root)
    result.checked_files = len(sources)

    edges: dict[str, set[str]] = {}
    for path, source in sources.items():
        owner = file_module[path]
        rel = path.relative_to(engine_dir).as_posix()
        for imported in _imports(source):
            if not imported.startswith(PACKAGE):
                continue
            tail = imported[len(PACKAGE) :].lstrip(".")
            if not tail:
                continue

            # 1. Только публичный интерфейс.
            #
            # Пакет `api` реэкспортирует то, чем можно пользоваться; всё
            # остальное в нём — устройство, а не интерфейс. Обращение к
            # `api.app` в обход `api` — именно та связь, которая потом мешает
            # переписать реализацию, не тронув потребителей. Пакет `adapters`
            # устроен иначе: конкретный адаптер и есть то, что берут, поэтому
            # обращение к нему по имени законно.
            parts = tail.split(".")
            package = parts[0]
            inside_same_package = rel.startswith(f"{package}/")
            if package in PRIVATE_PACKAGES and len(parts) > 1 and not inside_same_package:
                result.fail(
                    f"{rel}: импорт {imported} лезет во внутренности пакета "
                    f"«{package}»; у него есть публичный интерфейс"
                )
            if len(parts) > 2:
                result.fail(
                    f"{rel}: импорт {imported} лезет во внутренние файлы; "
                    "модули общаются публичным интерфейсом"
                )

            target_path = engine_dir / (parts[0] + ".py")
            if not target_path.exists():
                target_path = engine_dir / parts[0] / (parts[1] + ".py" if len(parts) > 1 else "")
            target = file_module.get(target_path, "")
            if owner and target and owner != target:
                edges.setdefault(owner, set()).add(target)
                forbidden = set(modules[owner]["forbidden"])
                if target in forbidden:
                    result.fail(
                        f"{owner} импортирует {target}, что запрещено его контрактом "
                        f"({rel} -> {imported})"
                    )
                allowed = set(modules[owner]["depends_on"])
                if allowed and target not in allowed:
                    result.fail(
                        f"{owner} импортирует {target}, которого нет в его depends_on "
                        f"({rel} -> {imported})"
                    )

    # 3. Ядро контрактов ни от кого не зависит.
    if edges.get("core-contracts"):
        result.fail(
            "core-contracts зависит от "
            f"{sorted(edges['core-contracts'])}: ядро обязано быть свободным"
        )

    # 5. Взаимных зависимостей нет.
    for a, targets in edges.items():
        for b in targets:
            if a in edges.get(b, set()):
                result.fail(f"взаимная зависимость {a} <-> {b}: границу нельзя пересекать в обе стороны")

    # 4. Ядро не знает названий сайтов и технологий.
    for path, source in sources.items():
        rel = path.relative_to(engine_dir).as_posix()
        if any(rel.startswith(prefix) or rel == prefix for prefix in DOMAIN_AWARE):
            continue
        lowered = code_without_prose(source).lower()
        for word in DOMAIN_WORDS:
            if re.search(rf"\b{word}\b", lowered):
                result.fail(
                    f"{rel}: универсальный модуль называет {word!r}; "
                    "различия сайтов живут в профилях и адаптерах"
                )
                break

    return result
