#!/usr/bin/env python3
"""Инвентаризация технического долга: реестр с владельцем, доказательством и проверкой.

Почему инструментом, а не чтением
---------------------------------

Долг, найденный чтением, — это список впечатлений: он не воспроизводится, не
сравнивается с прошлым замером и не показывает, что исправление подействовало.
Здесь каждый пункт имеет файл, строку, способ проверки и владельца, а сам
реестр пересчитывается одной командой до и после работы.

Разбор идёт по дереву разбора, а не поиском по тексту. Поиск по тексту находит
`except Exception` в комментарии и не находит его же, разбитого переносом; для
реестра, по которому принимают решения, этого мало.

Владение
--------

Полоса шаблонов правит своё. Пункты в чужих файлах остаются в реестре, но
помечены владельцем: их закрывает тот, кому они принадлежат, а здесь они
существуют, чтобы не выглядеть отсутствующими.

Запуск:
    .venv/bin/python scripts/debt_audit.py            # таблица
    .venv/bin/python scripts/debt_audit.py --json     # реестр целиком
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import re
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "artifacts" / "evidence" / "debt" / "debt-register.json"

#: Что принадлежит полосе шаблонов. Порядок важен: первое совпадение выигрывает.
OWNERSHIP = (
    ("factory/lords/", "TEMPLATES"),
    ("factory/templates/", "TEMPLATES"),
    ("factory/products/", "TEMPLATES"),
    ("factory/yummy/", "TEMPLATES"),
    ("themes/", "TEMPLATES"),
    ("blueprints/lords/", "TEMPLATES"),
    ("tests/e2e-lords/", "TEMPLATES"),
    ("tests/e2e-products/", "TEMPLATES"),
    ("tests/e2e-live/", "TEMPLATES"),
    ("tests/e2e-families/", "TEMPLATES"),
    ("docs/templates/", "TEMPLATES"),
    ("seo_operator/", "SEO"),
    ("factory/admin", "CORE"),
    ("factory/secret_hub/", "CORE"),
    ("automation/", "OPS"),
    ("factory/", "CORE"),
    ("scripts/", "TEMPLATES"),
    ("tests/", "TEMPLATES"),
    ("var/product-preview/", "TEMPLATES"),
)

SEVERITY_ORDER = ("критический", "высокий", "средний", "низкий")


@dataclass
class Finding:
    kind: str
    severity: str
    path: str
    line: int
    detail: str
    risk: str
    verify: str
    owner: str = ""

    def as_dict(self) -> dict:
        return {"kind": self.kind, "severity": self.severity, "owner": self.owner,
                "path": self.path, "line": self.line, "detail": self.detail,
                "risk": self.risk, "verify": self.verify}


def owner_of(path: str) -> str:
    for prefix, owner in OWNERSHIP:
        if path.startswith(prefix):
            return owner
    return "UNASSIGNED"


def python_files() -> list[Path]:
    found = []
    for base in ("factory", "scripts", "tests", "seo_operator"):
        target = ROOT / base
        if not target.is_dir():
            continue
        found.extend(p for p in target.rglob("*.py") if "__pycache__" not in p.parts)
    return sorted(found)


def rel(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


# --------------------------------------------------------------------------
# Проверки


def _swallows(handler: ast.ExceptHandler) -> bool:
    """Обработчик, не оставляющий следа: тело — только `pass`, `continue` или литерал."""
    for node in handler.body:
        if isinstance(node, ast.Pass):
            continue
        if isinstance(node, (ast.Continue, ast.Break)):
            continue
        if isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant):
            continue
        return False
    return True


def check_exceptions(tree: ast.AST, path: str) -> list[Finding]:
    out = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.ExceptHandler):
            continue
        bare = node.type is None
        broad = isinstance(node.type, ast.Name) and node.type.id in ("Exception", "BaseException")
        if not (bare or broad):
            continue
        swallowed = _swallows(node)
        if swallowed:
            out.append(Finding(
                "подавленное исключение", "высокий", path, node.lineno,
                ("голый except" if bare else f"except {node.type.id}") + " без следа в теле",
                "отказ проходит молча: сбой источника, прав или разбора выглядит как успех",
                "тест, воспроизводящий отказ, обязан увидеть его в состоянии или журнале"))
        elif bare:
            out.append(Finding(
                "голый except", "средний", path, node.lineno,
                "except без типа перехватывает и KeyboardInterrupt, и SystemExit",
                "прерывание и остановка процесса перехватываются как ошибка данных",
                "заменить на конкретный тип или Exception и убедиться, что тесты проходят"))
    return out


def check_markers() -> list[Finding]:
    out = []
    pattern = re.compile(r"\b(TODO|FIXME|HACK|XXX)\b")
    for path in python_files() + sorted(
            p for p in (ROOT / "tests").rglob("*.js") if "node_modules" not in p.parts):
        for i, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            m = pattern.search(line)
            if m:
                out.append(Finding(
                    f"маркер {m.group(1)}", "низкий", rel(path), i, line.strip()[:140],
                    "незавершённая работа, о которой знает только этот файл",
                    "закрыть либо перенести в реестр задач с владельцем"))
    return out


def _referenced_by_name() -> str:
    """Всё, где модуль может быть назван по имени файла, а не импортирован.

    Оболочечные сценарии, CI и документация запускают `python tests/tools/x.py`
    — импорта при этом нет. Первая редакция проверки объявила мёртвыми
    девятнадцать таких инструментов; все девятнадцать оказались рабочими и
    упоминались в `tests/run-all.sh`, рабочих процессах CI и документации.

    Удалять по такому «доказательству» значило бы выломать рабочий прогон,
    и правило этапа прямое: сначала доказать неиспользование программно.
    """
    chunks = []
    for pattern in ("*.sh", "*.yml", "*.yaml", "*.md", "*.json", "*.toml", "*.cfg"):
        for path in ROOT.rglob(pattern):
            text = path.as_posix()
            if "node_modules" in text or "/var/" in text or "/.git/" in text:
                continue
            try:
                chunks.append(path.read_text(encoding="utf-8", errors="ignore"))
            except OSError:
                continue
    return "\n".join(chunks)


def check_dead_modules() -> list[Finding]:
    """Модули, которые никто не импортирует и никто не называет по имени."""
    files = python_files()
    imported: set[str] = set()
    for path in files:
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imported.add(alias.name.split(".")[-1])
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    imported.add(node.module.split(".")[-1])
                for alias in node.names:
                    imported.add(alias.name)
    by_name = _referenced_by_name()
    out = []
    for path in files:
        name = path.stem
        if name in ("__init__", "conftest", "__main__") or name.startswith("test_"):
            # `__main__` запускается как `python -m пакет`: его не импортируют
            # по устройству, и «никем не импортируется» о нём ничего не значит.
            continue
        if rel(path).startswith("scripts/"):
            # Сценарии — точки входа: их запускают, а не импортируют.
            body = path.read_text(encoding="utf-8")
            if "__main__" in body:
                continue
        if name in imported:
            continue
        if path.name in by_name:
            # Запускается по имени файла из оболочки, CI или документации.
            continue
        out.append(Finding(
            "модуль никем не импортируется", "средний", rel(path), 1,
            f"{name} не встречается ни в одном импорте и не имеет точки входа",
            "мёртвый код читают, правят и поддерживают наравне с живым",
            "доказать неиспользование программно, затем удалить одним коммитом с "
            "регрессионной проверкой"))
    return out


def check_test_assertions() -> list[Finding]:
    out = []
    for path in sorted((ROOT / "tests").rglob("test_*.py")):
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            if not node.name.startswith("test_"):
                continue
            has_assert = any(isinstance(n, ast.Assert) for n in ast.walk(node))
            calls_raises = any(
                isinstance(n, ast.Attribute) and n.attr in ("raises", "warns", "fail", "skip",
                                                            "xfail", "check_schema", "validate")
                for n in ast.walk(node))
            if has_assert or calls_raises:
                continue
            # Тело из вызовов — это проверка «не должно бросить»: `ast.parse`
            # на сломанном модуле падает, и зелёный результат кое-что значит.
            # Тело без единого вызова не значит ничего и проходит всегда.
            # Смешивать их в одном пункте — значит завышать реестр.
            calls = any(isinstance(n, ast.Call) for n in ast.walk(node))
            if calls:
                out.append(Finding(
                    "неявное утверждение в тесте", "низкий", rel(path), node.lineno,
                    f"{node.name} проверяет только отсутствие исключения",
                    "намерение читается из тела, а не из утверждения: следующий "
                    "правящий не узнает, что именно обязано выполниться",
                    "назвать проверяемое утверждением или комментарием у вызова"))
            else:
                out.append(Finding(
                    "тест без утверждения", "высокий", rel(path), node.lineno,
                    f"{node.name} не содержит ни assert, ни вызова, который может упасть",
                    "зелёный результат ничего не подтверждает: тест проходит всегда",
                    "добавить утверждение и убедиться, что тест падает на сломанном коде"))
    return out


#: Зарезервированные пространства имён: адрес из них не может быть настоящим.
СЛУЖЕБНЫЕ = (".test", ".invalid", ".localhost", "localhost")


def _placeholder_domain(product: str) -> str | None:
    """Домен пакета витрины, если он служебный. Читается, а не угадывается."""
    import yaml

    report = ROOT / "var" / "product-preview" / product / "preview-report.json"
    if not report.is_file():
        return None
    try:
        package = json.loads(report.read_text(encoding="utf-8")).get("package")
    except json.JSONDecodeError:
        return None
    manifest = ROOT / "sites" / str(package) / "package.yaml"
    if not manifest.is_file():
        return None
    domain = (yaml.safe_load(manifest.read_text(encoding="utf-8")) or {}).get("domain") or ""
    return domain if any(domain.endswith(s) or s == domain for s in СЛУЖЕБНЫЕ) else None


def check_release_fixtures() -> list[Finding]:
    """Fixture-метки в **собранном выводе**, а не в исходнике.

    Первая редакция искала подстроку в модулях состава артефакта и объявляла
    критическим долгом строку `FIXTURE_DATA_SOURCE = "fixture/test"`. Это
    неверно: метка условная и подписывает синтетический каталог синтетическим —
    ровно так, как должна. Дефектом было бы её появление на витрине, собранной
    из живого источника, и проверять надо это.

    Реестр с выдуманными пунктами хуже отсутствующего: по нему правят живой
    код, чтобы погасить несуществующую тревогу.
    """
    out = []
    pattern = re.compile(r"(fixture/test|127\.0\.0\.1|localhost)")
    for build in sorted((ROOT / "var" / "product-preview").glob("*")):
        if not build.is_dir():
            continue
        report = build / "preview-report.json"
        if report.is_file():
            try:
                meta = json.loads(report.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                meta = {}
            # Витрины на синтетическом наборе метку обязаны нести: она честна.
            if meta.get("catalog") == "fixture" or meta.get("fixture"):
                continue
        # Пакет со служебным доменом (`.test`, `.invalid`, `localhost`) обязан
        # нести его в собранных страницах — иначе адрес был бы выдуман. Такая
        # витрина не выкладывается вовсе, и держит её отсутствие адреса
        # владельца, а не дефект кода. Критическим это станет ровно тогда,
        # когда пакет объявит настоящий домен, а метка останется.
        служебный = _placeholder_domain(build.name)
        for page in sorted(build.rglob("*.html")):
            text = page.read_text(encoding="utf-8", errors="replace")
            m = pattern.search(text)
            if m:
                if служебный:
                    out.append(Finding(
                        "служебный домен в собранном выводе", "низкий",
                        page.relative_to(ROOT).as_posix(), 1,
                        f"{m.group(1)} в витрине {build.name}: пакет объявляет {служебный}",
                        "витрина не может быть выложена, пока адрес не передан владельцем",
                        "ожидание входа owner.live_urls; после адреса — повторная сборка"))
                else:
                    out.append(Finding(
                        "fixture-метка в собранном выводе", "критический",
                        page.relative_to(ROOT).as_posix(), 1,
                        f"{m.group(1)} в собранной странице витрины {build.name}",
                        "выдуманное значение выглядит настоящим; именно по такой метке "
                        "handoff CORE_TO_OWNER-011 заключил, что боевые витрины отдают "
                        "синтетику, и вывод был неверным",
                        "тест, запрещающий эти подстроки в выводе на живом источнике"))
                break  # одной страницы довольно, чтобы назвать сборку
    return out


def check_duplication() -> list[Finding]:
    """Повторяющиеся блоки: окно нормализованных строк, повторённое дословно."""
    WINDOW = 8
    seen: dict[str, list[tuple[str, int]]] = defaultdict(list)
    for path in python_files():
        lines = [l.strip() for l in path.read_text(encoding="utf-8").splitlines()]
        meaningful = [(i + 1, l) for i, l in enumerate(lines)
                      if l and not l.startswith("#") and not l.startswith('"""')]
        for i in range(len(meaningful) - WINDOW):
            window = meaningful[i:i + WINDOW]
            body = "\n".join(l for _, l in window)
            if len(set(l for _, l in window)) < WINDOW - 2:
                continue  # однообразные блоки вроде списков полей — не дублирование
            key = hashlib.sha256(body.encode("utf-8")).hexdigest()
            seen[key].append((rel(path), window[0][0]))
    out = []
    reported: set[str] = set()
    for key, places in seen.items():
        files = {p for p, _ in places}
        if len(files) < 2:
            continue
        signature = "|".join(sorted(files))
        if signature in reported:
            continue
        reported.add(signature)
        first = sorted(places)[0]
        out.append(Finding(
            "повторённый блок", "средний", first[0], first[1],
            f"{WINDOW} строк повторяются дословно в: " + ", ".join(sorted(files)),
            "правка в одной копии и пропуск в другой — именно так очистка каталога "
            "оказалась забыта в двух точках вызова из четырёх",
            "вынести в общий модуль и заменить обе копии вызовом"))
    return out


def check_schema_versions() -> list[Finding]:
    out = []
    for path in sorted((ROOT / "schemas").glob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as error:
            out.append(Finding("схема не разбирается", "критический", rel(path), 1,
                               str(error), "проверка данных не выполняется вовсе",
                               "исправить и прогнать validate_schemas.py"))
            continue
        if "$schema" not in data:
            out.append(Finding(
                "схема без объявления диалекта", "средний", rel(path), 1,
                "нет $schema", "проверяющий выбирает диалект сам, и он может отличаться",
                "добавить $schema и прогнать компиляцию"))
        if "$id" not in data:
            out.append(Finding(
                "схема без $id", "низкий", rel(path), 1, "нет $id",
                "ссылка на схему из другой схемы невозможна",
                "добавить $id"))
        if data.get("type") == "object" and "additionalProperties" not in data:
            out.append(Finding(
                "схема допускает неизвестные поля", "высокий", rel(path), 1,
                "additionalProperties не задан на верхнем уровне",
                "опечатка в имени поля проходит проверку молча",
                "выключить additionalProperties и добавить отрицательный тест"))
    return out


CHECKS = (
    ("markers", check_markers),
    ("dead_modules", check_dead_modules),
    ("test_assertions", check_test_assertions),
    ("release_fixtures", check_release_fixtures),
    ("duplication", check_duplication),
    ("schema_versions", check_schema_versions),
)


def collect() -> list[Finding]:
    findings: list[Finding] = []
    for path in python_files():
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except SyntaxError:
            continue
        findings.extend(check_exceptions(tree, rel(path)))
    for _, check in CHECKS:
        findings.extend(check())
    for finding in findings:
        finding.owner = owner_of(finding.path)
    findings.sort(key=lambda f: (SEVERITY_ORDER.index(f.severity), f.path, f.line))
    return findings


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--owner", default=None, help="только пункты этого владельца")
    args = parser.parse_args()

    findings = collect()
    if args.owner:
        findings = [f for f in findings if f.owner == args.owner]

    report = {
        "artifact": "TEMPLATE_DEBT_REGISTER",
        "total": len(findings),
        "by_severity": {s: sum(1 for f in findings if f.severity == s) for s in SEVERITY_ORDER},
        "by_owner": {o: sum(1 for f in findings if f.owner == o)
                     for o in sorted({f.owner for f in findings})},
        "by_kind": {k: sum(1 for f in findings if f.kind == k)
                    for k in sorted({f.kind for f in findings})},
        "findings": [f.as_dict() for f in findings],
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0

    print(f"пунктов долга: {report['total']}")
    print("по важности: " + ", ".join(f"{k} {v}" for k, v in report["by_severity"].items() if v))
    print("по владельцу: " + ", ".join(f"{k} {v}" for k, v in report["by_owner"].items()))
    print()
    for severity in SEVERITY_ORDER:
        block = [f for f in findings if f.severity == severity]
        if not block:
            continue
        print(f"--- {severity} ({len(block)}) ---")
        for f in block[:40]:
            print(f"  [{f.owner:9}] {f.path}:{f.line} — {f.kind}: {f.detail[:90]}")
        if len(block) > 40:
            print(f"  … ещё {len(block) - 40}")
        print()
    print(OUT.relative_to(ROOT))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
