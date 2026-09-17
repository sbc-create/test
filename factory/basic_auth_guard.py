"""Запрет Basic Auth на публичных сайтах.

Правило владельца: на публичном сайте не должно быть ни `auth_basic`, ни
`.htpasswd`, ни ответа `401` с заголовком `WWW-Authenticate`. Пароль,
случайно оставшийся после отката соседнего изменения, закрывает сайт от
пользователей и от поисковых роботов одновременно, а заметить это по логам
деплоя невозможно: nginx стартует нормально.

Проверка статическая и работает по репозиторию: шаблоны, генераторы,
конфигурации nginx и скрипты выкладки. Живой ответ сайта она не заменяет —
для него есть `check_live_response`, которую запускает сессия на хосте.

Область действия — ПУБЛИЧНЫЕ сайты. Незапущенный стенд под паролем нарушением
не является: он и не публичен. Но как только домен помечен запущенным, тот же
самый текст становится ошибкой — поэтому проверка смотрит не на слово
«staging» в имени файла, а на фактический статус домена в реестрах.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

#: `auth_basic off;` не включает защиту, а снимает её. Запрещать его нельзя:
#: именно им открывают ACME-challenge внутри закрытого блока.
_AUTH_BASIC_OFF = re.compile(r"\bauth_basic\s+off\s*;")

PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"\bauth_basic\s+(?!off\s*;)\S"), "директива auth_basic включает пароль"),
    (re.compile(r"\bauth_basic_user_file\b"), "ссылка на файл паролей"),
    (re.compile(r"\.htpasswd\b"), "путь к .htpasswd"),
    (re.compile(r"\bhtpasswd\b\s+-"), "вызов утилиты htpasswd"),
    (re.compile(r"WWW-Authenticate", re.IGNORECASE), "выдача заголовка WWW-Authenticate"),
)

#: Что просматривается. Расширения и каталоги подобраны так, чтобы попадали
#: генераторы конфигураций, а не только сами конфигурации: пароль обычно
#: приходит из шаблона, а не из руками написанного файла.
SCAN_SUFFIXES = frozenset({
    ".conf", ".nginx", ".template", ".tmpl", ".j2", ".py", ".sh", ".bash",
    ".yaml", ".yml", ".json", ".ts", ".tsx", ".js", ".jsx", ".html", ".htm",
})

SKIP_DIRS = frozenset({
    ".git", "__pycache__", ".pytest_cache", ".venv", "node_modules",
    ".mypy_cache", ".ruff_cache", "dist", "build", "var", "artifacts",
})

#: Файлы, где упоминание Basic Auth — это описание запрета, а не его включение.
#: Список точечный: каталог целиком не исключается, иначе проверка перестанет
#: видеть реальный генератор, положенный рядом с тестом.
ALLOWLIST_SUFFIX = (
    "factory/basic_auth_guard.py",
    "tests/unit/test_basic_auth_guard.py",
    "docs/lords/NO_BASIC_AUTH.md",
)

#: Каталоги, содержимое которых не попадает на сервер. Упоминание Basic Auth
#: здесь не включает его нигде: тест, проверяющий отсутствие пароля, обязан
#: называть то, что проверяет. Проверка их всё равно просматривает, но
#: нарушением не считает — иначе enforcement-код срабатывал бы как нарушение,
#: и первым делом отключили бы саму проверку.
NON_DEPLOYABLE_PREFIXES = ("tests/", "docs/", "knowledge/", "adr/")

#: Признаки того, что строка ИЩЕТ Basic Auth или УДАЛЯЕТ его, а не включает.
#: Скрипт, который грепает конфиг в поисках пароля или вычищает его `sed`-ом,
#: — часть запрета, а не его нарушение. Без этого различия проверка ругалась бы
#: на собственный enforcement и её отключили бы первой.
_NOT_ENABLING = re.compile(
    # поиск и проверка
    r"\bgrep\b|\bassert\b|\bnot\s+in\b|!=|\bif\s|\brefute\b|\bexpect\b"
    r"|\bcheck\b|\bbad\b|\bfail\b"
    # удаление и очистка
    r"|\bsed\b|\brm\b|\bunlink\b|\bremove\b|\bdelete\b|\bstale\b|\bcleanup\b"
    r"|/d'|/d\"|\bmissing_ok\b"
    # комментарии
    r"|^\s*#|^\s*//|^\s*\*"
)


class Severity(str, Enum):
    ERROR = "error"       # публичный домен — нарушение правила
    WARNING = "warning"   # непубличный стенд — станет ошибкой при запуске


@dataclass(frozen=True)
class Finding:
    path: str
    line: int
    text: str
    reason: str
    severity: Severity
    domains: tuple[str, ...] = ()

    def render(self) -> str:
        scope = f" [{', '.join(self.domains)}]" if self.domains else ""
        return f"{self.path}:{self.line}{scope}: {self.reason} — {self.text.strip()[:100]}"


@dataclass
class GuardReport:
    findings: list[Finding] = field(default_factory=list)
    public_domains: tuple[str, ...] = ()
    scanned_files: int = 0

    @property
    def errors(self) -> list[Finding]:
        return [f for f in self.findings if f.severity is Severity.ERROR]

    @property
    def warnings(self) -> list[Finding]:
        return [f for f in self.findings if f.severity is Severity.WARNING]

    @property
    def passed(self) -> bool:
        return not self.errors

    def render(self) -> str:
        lines = [f"BASIC_AUTH_GUARD={'pass' if self.passed else 'fail'}",
                 f"просмотрено файлов: {self.scanned_files}",
                 f"публичные домены: {', '.join(self.public_domains) or 'нет'}"]
        if self.errors:
            lines.append("")
            lines.append("НАРУШЕНИЯ (публичные сайты):")
            lines += [f"  - {f.render()}" for f in self.errors]
        if self.warnings:
            lines.append("")
            lines.append("Предупреждения (непубличный стенд; станут ошибкой при запуске):")
            lines += [f"  - {f.render()}" for f in self.warnings]
        return "\n".join(lines)


def public_domains(repo_root: Path) -> set[str]:
    """
    Домены, считающиеся публичными. Собираются из реестров, а не из имён файлов.

    Публичным считается домен, который либо помечен запущенным в реестре
    направления, либо уже имеет включённую аналитику: и то и другое означает,
    что на него ходят люди.
    """
    found: set[str] = set()

    directions = repo_root / "config" / "directions"
    if directions.is_dir():
        for path in sorted(directions.glob("*.json")):
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            for entry in data.get("domains") or []:
                if entry.get("launched"):
                    apex = entry.get("apex")
                    if apex:
                        found.add(apex.lower())

    analytics = repo_root / "config" / "analytics.json"
    if analytics.exists():
        try:
            data = json.loads(analytics.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            data = {}
        for prop in data.get("properties") or []:
            domain = prop.get("domain")
            if domain and prop.get("analytics_enabled"):
                found.add(domain.lower())

    portfolio = repo_root / "config" / "portfolio.json"
    if portfolio.exists():
        try:
            data = json.loads(portfolio.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            data = {}
        for site in data.get("sites") or []:
            url = site.get("base_url") or ""
            match = re.search(r"https?://([^/]+)", url)
            if match:
                found.add(match.group(1).lower())

    return found


def _domains_in(text: str, candidates: set[str]) -> tuple[str, ...]:
    lowered = text.lower()
    return tuple(sorted(d for d in candidates if d in lowered))


def _is_allowlisted(rel: str) -> bool:
    return any(rel.endswith(suffix) for suffix in ALLOWLIST_SUFFIX)


def scan(repo_root: Path, extra_public: set[str] | None = None) -> GuardReport:
    """Статическая проверка репозитория."""
    repo_root = Path(repo_root)
    publics = public_domains(repo_root) | {d.lower() for d in (extra_public or set())}
    report = GuardReport(public_domains=tuple(sorted(publics)))

    for path in sorted(repo_root.rglob("*")):
        if not path.is_file() or path.suffix not in SCAN_SUFFIXES:
            continue
        rel_parts = path.relative_to(repo_root).parts
        if SKIP_DIRS & set(rel_parts):
            continue
        rel = "/".join(rel_parts)
        if _is_allowlisted(rel):
            continue

        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        report.scanned_files += 1

        for lineno, line in enumerate(text.splitlines(), start=1):
            if _AUTH_BASIC_OFF.search(line):
                continue
            for pattern, reason in PATTERNS:
                if not pattern.search(line):
                    continue
                # Файл целиком решает, на какие домены он влияет: пароль
                # обычно объявлен в одной строке, а домен — в другой.
                touched = _domains_in(text, publics)
                deployable = not rel.startswith(NON_DEPLOYABLE_PREFIXES)
                enables = not _NOT_ENABLING.search(line)
                severity = (Severity.ERROR
                            if touched and deployable and enables
                            else Severity.WARNING)
                report.findings.append(Finding(
                    path=rel, line=lineno, text=line, reason=reason,
                    severity=severity, domains=touched))
                break

    return report


# --------------------------------------------------------------------------
# Живая проверка — запускается сессией на хосте
# --------------------------------------------------------------------------

@dataclass(frozen=True)
class LiveResult:
    domain: str
    status_code: int | None
    has_www_authenticate: bool
    error: str = ""

    @property
    def passed(self) -> bool:
        return (self.error == "" and self.status_code == 200
                and not self.has_www_authenticate)

    def render(self) -> str:
        if self.error:
            return f"{self.domain}: НЕ ПРОВЕРЕНО — {self.error}"
        mark = "ok" if self.passed else "FAIL"
        auth = " WWW-Authenticate присутствует" if self.has_www_authenticate else ""
        return f"{self.domain}: {mark} HTTP {self.status_code}{auth}"


def check_live_response(domain: str, opener=None, timeout: float = 15.0) -> LiveResult:
    """
    Публичный ответ домена. Статическая проверка сюда не заглядывает и
    заменить её не может: пароль может быть добавлен на сервере вручную,
    минуя репозиторий.

    Сетевая ошибка возвращается как error, а не как «пройдено»: недоступный
    сайт не является сайтом без Basic Auth.
    """
    if opener is None:  # pragma: no cover - сеть не используется в тестах
        from urllib.request import urlopen

        opener = urlopen

    url = f"https://{domain}/"
    try:
        with opener(url, timeout=timeout) as response:
            headers = getattr(response, "headers", {})
            return LiveResult(
                domain=domain,
                status_code=getattr(response, "status", None) or response.getcode(),
                has_www_authenticate=bool(headers.get("WWW-Authenticate")),
            )
    except Exception as exc:  # noqa: BLE001 - любая ошибка означает «не проверено»
        status = getattr(exc, "code", None)
        headers = getattr(exc, "headers", {}) or {}
        if status is not None:
            return LiveResult(
                domain=domain, status_code=status,
                has_www_authenticate=bool(headers.get("WWW-Authenticate")))
        return LiveResult(domain=domain, status_code=None, has_www_authenticate=False,
                          error=f"{type(exc).__name__}: {exc}")
