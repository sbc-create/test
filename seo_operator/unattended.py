"""Профиль UNATTENDED_SAFE: какие операции выполняются без подтверждения.

Модуль отвечает ровно на один вопрос: «это обычная работа над репозиторием?».
Он умеет **только разрешать**. Все запреты остаются там, где были: в
``.claude/hooks/guard_rules`` (слой фабрики) и в
``seo_operator.guardrails.BLOCKED_PATTERNS`` (слой оператора). Хуки сначала
спрашивают запреты и только потом обращаются сюда, поэтому ни одно правило
этого файла не способно снять существующую защиту.

Разбор команды намеренно синтаксический, а не «по подстроке»: составная
команда режется на сегменты, у каждого сегмента снимаются переменные
окружения, обёртки (``timeout``, ``env``, ``nice``) и перенаправления, и
разрешение выдаётся, только если **каждый** сегмент опознан как рутинный.
Один непонятный сегмент означает, что вся команда уходит на подтверждение:
безопасная команда не поручается за то, что к ней приписали.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass

from seo_operator.guardrails import split_segments as _fallback_segments

ALLOW = "allow"
PASS = "pass"  # профиль не высказывается: решают обычные permission rules

PROFILE = "UNATTENDED_SAFE"


@dataclass(frozen=True)
class Verdict:
    decision: str
    reason: str = ""


# --------------------------------------------------------------------------
# Обязательные стоп-сигналы. Дублируют запреты соседних слоёв: профиль обязан
# оставаться безопасным даже если его вызовут в одиночку.
# --------------------------------------------------------------------------
STOP_PATTERNS: tuple[tuple[str, str], ...] = (
    (
        r"git\s+push\b[^;&|\n]*(?:--force\b|--force-with-lease\b|\s-f\b|\+refs/)",
        "force push",
    ),
    (
        r"git\s+push\b[^;&|\n]*\s--delete\b|git\s+push\b[^;&|\n]*\s:\s*\S",
        "удаление удалённой ветки",
    ),
    # Ограничение одним сегментом обязательно: `git push origin claude/x &&
    # git checkout main` — обычная последовательность, а не push в main.
    (r"git\s+push\b[^;&|\n]*\b(?:main|master)\b", "push напрямую в main"),
    (r"git\s+(?:reset\s+--hard|filter-branch|filter-repo)\b", "переписывание истории"),
    (
        r"git\s+rebase\b[^;&|\n]*\s-i\b|git\s+rebase\b[^;&|\n]*--interactive",
        "интерактивный rebase",
    ),
    (r"git\s+branch\s+-[dD]\b|git\s+update-ref\s+-d\b", "удаление ветки"),
    (r"git\s+clean\b", "удаление неотслеживаемых файлов"),
    (r"\b(?:dropdb|dropuser)\b", "удаление базы или роли"),
    (r"\bDROP\s+(?:DATABASE|SCHEMA|TABLE)\b|\bTRUNCATE\b", "разрушительный SQL"),
    (r"\bDELETE\s+FROM\b(?![^;&|\n]*\bWHERE\b)", "DELETE без WHERE"),
    (r"\bterraform\s+destroy\b|\baws\s+s3\s+rb\b", "удаление инфраструктуры"),
    (
        r"\b(?:backup|backups|snapshot)\b[^;&|\n]*\b(?:rm|delete|destroy|purge)\b",
        "удаление бэкапа",
    ),
    (r"\b(?:rm|delete|destroy|purge)\b[^;&|\n]*\b(?:backup|backups)\b", "удаление бэкапа"),
    (
        r"\b(?:zone|domain|domains)\b[^;&|\n]*\b(?:delete|destroy|transfer|release)\b",
        "удаление или перенос зоны/домена",
    ),
    (r"\b(?:domain|domains|dns)\b[^;&|\n]*\b(?:register|purchase|buy|renew)\b", "покупка домена"),
    (
        r"\b(?:billing|payment|invoice|subscription|checkout)\b[^;&|\n]*"
        r"\b(?:create|pay|charge|confirm)\b",
        "оплата услуг",
    ),
    (
        r"--dangerously-skip-permissions|bypassPermissions|dangerouslyDisableSandbox",
        "обход разрешений",
    ),
    (r"--no-verify\b", "обход git-хуков"),
    (r"(?:rm|mv|chmod\s+-x)\s+[^;&|\n]*\.claude/hooks/", "отключение хуков"),
    (r"\$\{?(?:[A-Z_]*(?:SECRET|TOKEN|PASSWORD|API_KEY)[A-Z_]*)\b", "подстановка значения секрета"),
    (r"(?:^|[;&|]\s*)printenv\b|(?:^|[;&|]\s*)env\s*(?:\||>|;|$)", "дамп окружения"),
    # Секретные пути закрыты и здесь: профиль обязан быть безопасным в одиночку,
    # а не только в паре с guard_rules.
    (
        r"(?:^|[\s'\"=/])(?:\.env(?:\.[\w.-]+)?|secrets/|id_rsa|id_ed25519|id_ecdsa"
        r"|\.pem\b|\.p12\b|\.pfx\b|authorized_keys|\.ssh/|\.aws/credentials|\.npmrc|\.pypirc)",
        "обращение к секретному пути",
    ),
    # Необратимые операции над production подтверждает человек, даже когда
    # выполняет их сама фабрика: разрешение выдаётся на команду, а не на среду.
    (r"--environment[= ]\s*production\b|--env[= ]\s*production\b", "операция над production"),
    (
        r"\bfactory\s+(?:deploy|rollback)\b(?![^;&|\n]*--environment[= ]\s*staging\b)",
        "выкат или откат вне staging",
    ),
    (
        r"\b(?:kubectl|helm)\s+(?:apply|delete|rollout)\b|\bterraform\s+apply\b",
        "мутация инфраструктуры",
    ),
    # Удаление истории, конфигурации защиты, знаний и самих сайтов — не рутина.
    (
        r"(?:^|[;&|]\s*)(?:\S*/)?rm\b[^;&|\n]*(?:\s|/)"
        r"(?:\.git|\.claude|sites|knowledge|inventory|artifacts)(?:/|\s|$)",
        "удаление истории, защиты, знаний или сайтов",
    ),
    # Отключение наблюдаемости — тот же класс, что удаление бэкапа: после него
    # уже нельзя доказать, что произошло.
    (
        r"(?:^|[;&|]\s*)(?:\S*/)?(?:rm|mv|truncate|shred)\b[^;&|\n]*"
        r"\b(?:audit|journal|var/log)\b|"
        r"(?:^|[;&|]\s*)(?:\S*/)?(?:rm|mv|truncate|shred)\b[^;&|\n]*\.jsonl\b",
        "удаление журнала или аудита",
    ),
    (r">\s*(?:var/audit|var/log)/", "затирание журнала перенаправлением"),
    # Выключение бэкапа, отката или health-check правкой пакета из команды.
    # Та же правка через редактор ловится не здесь, а тестом
    # `test_site_packages_keep_recovery_enabled`: команда — не единственный путь,
    # и делать вид, что разбор команд закрывает оба, было бы неправдой.
    (
        r"(?:^|[;&|]\s*)(?:\S*/)?(?:sed|perl|awk)\b[^;&|\n]*"
        r"(?:before_mutation|auto_rollback_on_smoke_failure"
        r"|restore_test|health_endpoint|keep_releases)",
        "выключение бэкапа, отката или health-check",
    ),
    # Ослабление защиты ветки на стороне GitHub.
    (
        r"\bbranch(?:es)?/[^\s]*/protection\b|\benforce_admins\b\s*=?\s*false|"
        r"\brequired_status_checks\b[^;&|\n]*\bnull\b",
        "изменение branch protection",
    ),
)

STOP_RE = tuple((re.compile(pattern, re.IGNORECASE), label) for pattern, label in STOP_PATTERNS)


# --------------------------------------------------------------------------
# Разбор сегмента
# --------------------------------------------------------------------------
ASSIGNMENT_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=")
WRAPPERS = {"timeout", "env", "nice", "ionice", "stdbuf", "nohup", "command", "time", "chronic"}
WRAPPER_VALUE_RE = re.compile(r"^[0-9]+(?:\.[0-9]+)?[smhd]?$")

FD_DUP_RE = re.compile(r"^\d*(?:>>?|<)&\d*-?$")
REDIR_OP_RE = re.compile(r"^(?:\d*(?:>>?|<)|&>>?)$")
REDIR_ATTACHED_RE = re.compile(r"^(?:\d*(?:>>?|<)|&>>?)\S+$")
REDIR_HEAD_RE = re.compile(r"^(?:\d*(?:>>?|<)|&>>?)")


def redirect_targets(segment: str) -> list[str]:
    """Файлы, в которые сегмент перенаправляет вывод (без дублирования дескрипторов)."""
    targets: list[str] = []
    tokens = segment.split()
    expect = False
    for token in tokens:
        if expect:
            expect = False
            targets.append(token.strip("'\""))
            continue
        if FD_DUP_RE.match(token):
            continue
        if REDIR_OP_RE.match(token):
            expect = True
            continue
        if REDIR_ATTACHED_RE.match(token):
            targets.append(REDIR_HEAD_RE.sub("", token).strip("'\""))
    return [t for t in targets if t]


def strip_redirections(segment: str) -> str:
    """Убирает перенаправления: `2>&1`, `>out.log`, `&> /dev/null`, `< in`."""
    out: list[str] = []
    expect = False
    for token in segment.split():
        if expect:
            expect = False
            continue
        if FD_DUP_RE.match(token) or REDIR_ATTACHED_RE.match(token):
            continue
        if REDIR_OP_RE.match(token):
            expect = True
            continue
        out.append(token)
    return " ".join(out)


def strip_wrappers(segment: str) -> str:
    """Срезает `VAR=1 env FOO=2 timeout 300 nice cmd …` до фактической команды."""
    tokens = segment.split()
    while tokens:
        head = tokens[0]
        if ASSIGNMENT_RE.match(head):
            tokens = tokens[1:]
            continue
        if os.path.basename(head) in WRAPPERS:
            tokens = tokens[1:]
            while tokens and (
                tokens[0].startswith("-")
                or ASSIGNMENT_RE.match(tokens[0])
                or WRAPPER_VALUE_RE.match(tokens[0])
            ):
                tokens = tokens[1:]
            continue
        break
    return " ".join(tokens)


#: Флаги xargs, у которых есть значение: `-a FILE`, `-I {}`, `-n 4`.
XARGS_VALUE_FLAGS = {"-a", "-I", "-i", "-n", "-P", "-d", "-E", "-e", "-s", "-L", "-l", "--arg-file"}


def _unwrap_xargs(tokens: list) -> list:
    """Команда, которую запустит xargs: флаги и их значения отбрасываются."""
    rest = tokens[1:]
    out: list = []
    skip = False
    for index, token in enumerate(rest):
        if skip:
            skip = False
            continue
        if token.startswith("-"):
            flag = token.split("=", 1)[0]
            if flag in XARGS_VALUE_FLAGS and "=" not in token:
                skip = True
            continue
        out = rest[index:]
        break
    return out


def segments(command: str) -> list:
    """Сегменты составной команды.

    Разбор берётся у слоя фабрики: он уже знает `|&`, перевод строки, кавычки и
    перенаправления. Вторая реализация того же разбора неизбежно разойдётся с
    первой, а расхождение здесь означает разрешение там, где запрет.
    """
    rules = _guard_rules()
    if rules is not None:
        return rules.split_subcommands(command)
    return _fallback_segments(command)


def normalize(segment: str) -> str:
    text = strip_redirections(segment.strip())
    # xargs распаковывается до снятия обёрток: общий срез обёрток убирает слово
    # `xargs` вместе с его флагами, но оставляет значение флага (`-a FILE`)
    # первым токеном, и файл становится «командой».
    for _ in range(3):
        tokens = text.split()
        while tokens and ASSIGNMENT_RE.match(tokens[0]):
            tokens = tokens[1:]
        if tokens and os.path.basename(tokens[0]) == "xargs":
            text = " ".join(_unwrap_xargs(tokens))
            continue
        break
    rules = _guard_rules()
    return rules.strip_wrappers(text) if rules is not None else strip_wrappers(text)


# --------------------------------------------------------------------------
# Инвентарь: цели SSH и зоны DNS читает слой фабрики, второй копии списка нет
# --------------------------------------------------------------------------
def _repo_root() -> str:
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


_GUARD_RULES = None


def _guard_rules():
    """Модуль правил фабрики. Недоступен — считаем инвентарь пустым (fail closed)."""
    global _GUARD_RULES
    if _GUARD_RULES is not None:
        return _GUARD_RULES or None
    import importlib.util
    import sys

    path = os.path.join(_repo_root(), ".claude", "hooks", "guard_rules.py")
    if not os.path.exists(path):
        _GUARD_RULES = False
        return None
    try:
        name = "guard_rules"
        module = sys.modules.get(name)
        if module is None or not hasattr(module, "inventory_ssh_hosts"):
            spec = importlib.util.spec_from_file_location(name, path)
            module = importlib.util.module_from_spec(spec)
            # Регистрация до исполнения обязательна: `@dataclass` заглядывает в
            # sys.modules по имени модуля, и без записи загрузка падает.
            sys.modules[name] = module
            spec.loader.exec_module(module)
        _GUARD_RULES = module
        return module
    except Exception:
        _GUARD_RULES = False
        return None


class _inventory_at:
    """Читает инвентарь из указанного корня, не трогая боевой реестр."""

    def __init__(self, root: str | None):
        self.root = root
        self.previous = None

    def _overrides(self) -> bool:
        # Корень репозитория — значение по умолчанию, а не выбор вызывающего.
        # Затирать им переменную окружения нельзя: иначе инвентарь, подставленный
        # снаружи (в проверке — временный), молча заменяется боевым.
        return bool(self.root) and os.path.realpath(self.root) != os.path.realpath(_repo_root())

    def __enter__(self):
        rules = _guard_rules()
        if rules and self._overrides():
            self.previous = os.environ.get(rules.INVENTORY_ROOT_ENV)
            os.environ[rules.INVENTORY_ROOT_ENV] = self.root
        return rules

    def __exit__(self, *exc):
        rules = _guard_rules()
        if rules and self._overrides():
            if self.previous is None:
                os.environ.pop(rules.INVENTORY_ROOT_ENV, None)
            else:
                os.environ[rules.INVENTORY_ROOT_ENV] = self.previous
        return False


def inventory_hosts(root: str | None = None) -> set:
    with _inventory_at(root) as rules:
        return rules.inventory_ssh_hosts() if rules else set()


def inventory_zones(root: str | None = None) -> set:
    with _inventory_at(root) as rules:
        return rules.inventory_dns_zones() if rules else set()


def _read_hosts_file(root: str, name: str, section: str) -> set:
    with _inventory_at(root) as rules:
        if not rules:
            return set()
        values = set()
        for entry in rules._read_inventory(name, section):
            for key in ("host", "hostname", "address", "domain"):
                if entry.get(key):
                    values.add(entry[key].lower())
        return values


def inventory_targets(root: str | None = None) -> list:
    """Цели выката из `inventory/targets.yaml`."""
    with _inventory_at(root) as rules:
        return rules._read_inventory("targets.yaml", "targets") if rules else []


def network_hosts(root: str | None = None) -> set:
    """Хосты интеграций, к которым разрешены обычные запросы.

    Пока контракты CDNVideoHub, CMS, VK и аналитики не переданы, список пуст —
    это не поломка, а честное отсутствие входных данных.
    """
    root = root or _repo_root()
    hosts = _read_hosts_file(root, "network-allowlist.yaml", "hosts")
    raw = os.environ.get("FACTORY_NETWORK_ALLOWLIST", "")
    hosts |= {h.strip().lower() for h in raw.split(",") if h.strip()}
    return hosts


# --------------------------------------------------------------------------
# Наборы рутинных программ
# --------------------------------------------------------------------------
READ_ONLY = {
    "ls",
    "cat",
    "head",
    "tail",
    "wc",
    "find",
    "grep",
    "rg",
    "egrep",
    "fgrep",
    "awk",
    "sort",
    "uniq",
    "cut",
    "tr",
    "diff",
    "stat",
    "file",
    "tree",
    "jq",
    "yq",
    "basename",
    "dirname",
    "realpath",
    "readlink",
    "date",
    "pwd",
    "echo",
    "printf",
    "true",
    "false",
    "test",
    "md5sum",
    "sha256sum",
    "sha1sum",
    "column",
    "nl",
    "tac",
    "comm",
    "du",
    "which",
    "command",
    "seq",
    "xxd",
    "cd",
}
#: `sed` читает только без `-i`; запись разбирается отдельно.
READ_ONLY_UNLESS_INPLACE = {"sed", "perl"}

FILE_WORK = {
    "mkdir",
    "touch",
    "cp",
    "mv",
    "ln",
    "rm",
    "rmdir",
    "chmod",
    "tee",
    "unzip",
    "tar",
    "zip",
    "gzip",
}

RUNTIMES = {
    "python",
    "python3",
    "pytest",
    "ruff",
    "mypy",
    "black",
    "isort",
    "pip",
    "pip3",
    "uv",
    "poetry",
    "node",
    "npm",
    "npx",
    "pnpm",
    "yarn",
    "corepack",
    "tsc",
    "eslint",
    "prettier",
    "playwright",
    "vitest",
    "jest",
    "php",
    "composer",
    "docker",
    "docker-compose",
    "podman",
    "make",
    "ansible-lint",
    "shellcheck",
    "hadolint",
    "psalm",
    "phpstan",
    "phpunit",
}
#: Удалённые исполнители: разрешены только к целям из inventory.
REMOTE = {"ssh", "scp", "sftp", "rsync", "ansible", "ansible-playbook"}
DNS_TOOLS = {"nsupdate"}
FETCH = {"curl", "wget", "http", "httpie"}

#: Чтение системного журнала. Только чтение: `journalctl` без флагов очистки не
#: меняет ничего, а без него диагностика службы сводится к угадыванию. Флаги,
#: которые удаляют записи (`--vacuum-*`, `--rotate`, `--flush`), в список не
#: входят — удаление журнала закрыто и стоп-сигналом выше.
JOURNAL = {"journalctl"}
JOURNAL_MUTATING_FLAGS = ("--vacuum", "--rotate", "--flush", "--sync", "--relinquish-var")
SHELLS = {"bash", "sh", "zsh"}

GIT_READ = {
    "status",
    "diff",
    "log",
    "show",
    "branch",
    "rev-parse",
    "rev-list",
    "ls-files",
    "ls-remote",
    "ls-tree",
    "fetch",
    "blame",
    "describe",
    "shortlog",
    "cat-file",
    "for-each-ref",
    "merge-base",
    "name-rev",
    "grep",
    "whatchanged",
    "count-objects",
    "remote",
    "config",
    "worktree",
    "stash",
    "check-ignore",
    "check-attr",
    "diff-tree",
    "diff-index",
    "symbolic-ref",
    "show-ref",
    "reflog",
    "verify-commit",
    "annotate",
    "archive",
    "hash-object",
    "help",
    "version",
    "notes",
    "bundle",
}
GIT_WRITE = {
    "add",
    "commit",
    "checkout",
    "switch",
    "restore",
    "merge",
    "rebase",
    "tag",
    "cherry-pick",
    "revert",
    "reset",
    "mv",
    "pull",
    "init",
    "apply",
    "am",
}
#: Ветки, в которые разрешён обычный push.
PUSH_BRANCH_RE = re.compile(r"(?:^|[\s:/])claude/[A-Za-z0-9._\-/]+")

#: Работа с GitHub через штатный CLI. Разрешаются чтение и работа с pull
#: request и issue — это обычная часть цикла. Всё, что удаляет, переносит
#: владение или трогает защиту ветки, в список не входит и остаётся под
#: default-deny; отдельные формы (`gh repo delete`, `gh api -X DELETE`,
#: `branches/*/protection`) закрыты стоп-сигналами и deny-правилами выше.
GH_READ = {
    "pr",
    "issue",
    "repo",
    "run",
    "workflow",
    "release",
    "api",
    "search",
    "status",
    "browse",
    "label",
    "cache",
    "version",
    "help",
}
# `auth` в списке нет намеренно: `gh auth token` печатает токен в stdout, а
# `gh auth status --show-token` — в stderr. Отдельно это же закрыто запретом в
# `guardrails.BLOCKED_PATTERNS`, чтобы правило не держалось на одном списке.
#: Подкоманды, которые сами по себе не считаются рутиной ни у одного объекта.
GH_FORBIDDEN_VERBS = {"delete", "transfer", "archive", "rename", "fork", "unarchive"}


def _gh_ok(tokens: list) -> bool:
    args = [t for t in tokens[1:] if not t.startswith("-")]
    if not args:
        return True  # `gh --version`, `gh --help`
    if args[0] not in GH_READ:
        return False
    # `gh repo delete`, `gh release delete`, `gh pr ... transfer` — не рутина.
    if any(verb in GH_FORBIDDEN_VERBS for verb in args[1:3]):
        return False
    # `gh api` умеет менять что угодно: разрешаются только читающие методы.
    if args[0] == "api":
        joined = " ".join(tokens[1:])
        method = re.search(r"(?:-X|--method)[= ]\s*([A-Za-z]+)", joined)
        if method and method.group(1).upper() not in {"GET", "HEAD"}:
            return False
    return True


DEP_SUBCOMMANDS = {"install", "ci", "sync", "add", "update", "i", "require"}

#: Каталоги вне репозитория, запись в которые считается рабочей.
SCRATCH_PREFIXES = ("/tmp/claude-", "/dev/null", "/dev/stdout", "/dev/stderr")


def _inside_repo(path: str, root: str) -> bool:
    """Путь внутри репозитория (или в рабочем scratch-каталоге сессии)."""
    candidate = path.strip().strip("'\"")
    if not candidate or candidate.startswith("-"):
        return True
    if candidate.startswith(SCRATCH_PREFIXES):
        return True
    absolute = candidate if os.path.isabs(candidate) else os.path.join(root, candidate)
    resolved = os.path.normpath(absolute)
    return resolved == root or resolved.startswith(root + os.sep)


def _paths_of(tokens: list, root: str) -> bool:
    return all(_inside_repo(token, root) for token in tokens[1:] if not token.startswith("-"))


def _remote_hosts(tokens: list) -> list:
    """Цели удалённой команды. Разбор общий со слоем фабрики."""
    rules = _guard_rules()
    if rules is not None:
        return rules.remote_targets(tokens)
    return [
        t.split("@", 1)[-1].split(":", 1)[0].lower()
        for t in tokens[1:]
        if not t.startswith("-") and "/" not in t
    ]


def _git_ok(tokens: list) -> bool:
    args = [t for t in tokens[1:] if not t.startswith("-")]
    if not args:
        return True  # `git --version`, `git --help`
    verb = args[0]
    if verb in GIT_READ or verb in GIT_WRITE:
        return True
    if verb == "push":
        # Обычный push разрешён только в собственную ветку `claude/*`.
        # Форма `git push` без аргументов не разрешается: цель определяет
        # upstream, а не команда, и профиль не может её проверить.
        return bool(PUSH_BRANCH_RE.search(" ".join(tokens[2:])))
    return False


def _dependency_install(prog: str, tokens: list) -> bool:
    args = [t for t in tokens[1:] if not t.startswith("-")]
    if prog in {"npm", "pnpm", "yarn", "composer", "poetry", "corepack"}:
        return bool(args) and args[0] in DEP_SUBCOMMANDS
    if prog in {"pip", "pip3", "uv"}:
        return bool(args) and args[0] in DEP_SUBCOMMANDS or "pip" in args
    return False


def classify_segment(segment: str, root: str) -> tuple[bool, str]:
    """`(рутинная ли команда, пояснение)` для одного сегмента."""
    text = normalize(segment)
    if not text:
        return True, "пустой сегмент"

    for target in redirect_targets(segment):
        if not _inside_repo(target, root):
            return False, f"перенаправление за пределы репозитория: {target}"

    tokens = text.split()
    prog = os.path.basename(tokens[0].strip("'\""))

    if prog == "git":
        if _git_ok(tokens):
            return True, "git в собственной ветке"
        return False, "git-операция вне профиля"

    if prog == "gh":
        if _gh_ok(tokens):
            return True, "работа с GitHub: чтение и pull request"
        return False, "операция GitHub вне профиля"

    if prog in READ_ONLY:
        return True, "чтение и локальный анализ"

    if prog in READ_ONLY_UNLESS_INPLACE:
        inplace = any(
            t == "-i" or t.startswith("-i") or t.startswith("--in-place") for t in tokens[1:]
        )
        if not inplace:
            return True, "чтение"
        if _paths_of(tokens, root):
            return True, "правка файла в репозитории"
        return False, "правка файла вне репозитория"

    if prog in FILE_WORK:
        if _paths_of(tokens, root):
            return True, "работа с файлами репозитория"
        return False, "файловая операция вне репозитория"

    if prog in RUNTIMES:
        if _dependency_install(prog, tokens):
            return True, "установка зависимостей проекта"
        return True, "сборка, тесты и локальные инструменты"

    if prog in SHELLS:
        args = [t for t in tokens[1:] if not t.startswith("-")]
        if any(t == "-c" for t in tokens[1:]):
            return False, "shell -c разбирается отдельным слоем, профиль не ручается"
        if args and _paths_of(tokens, root):
            return True, "запуск скрипта репозитория"
        return False, "интерактивный shell"

    if prog in REMOTE:
        hosts = _remote_hosts(tokens)
        approved = inventory_hosts(root)
        if hosts and all(host in approved for host in hosts):
            return True, f"цель {hosts[0]} внесена в inventory"
        missing = next((h for h in hosts if h not in approved), "")
        return False, f"хост «{missing or 'не определён'}» отсутствует в inventory/ssh-hosts.yaml"

    if prog in DNS_TOOLS:
        zones = inventory_zones(root)
        low = text.lower()
        if any(zone and zone in low for zone in zones):
            return True, "зона внесена в inventory"
        return False, "зона отсутствует в inventory/dns-zones.yaml"

    if prog in JOURNAL:
        if any(flag in text for flag in JOURNAL_MUTATING_FLAGS):
            return False, "journalctl с флагом, меняющим журнал"
        return True, "чтение системного журнала"

    if prog in FETCH:
        match = re.search(r"https?://([^/\s'\"]+)", text)
        host = match.group(1).lower() if match else ""
        bare = host.split(":")[0]
        if bare in {"127.0.0.1", "localhost", "::1"}:
            return True, "локальный стенд"
        if bare and bare in network_hosts(root):
            return True, f"интеграция {bare} по переданному контракту"
        return False, f"хост «{bare or 'не определён'}» не входит в переданные контракты"

    if text.startswith(("./", ".venv/", "bin/")):
        if _inside_repo(tokens[0], root):
            return True, "исполняемый файл репозитория"
        return False, "исполняемый файл вне репозитория"

    return False, f"команда {prog!r} не входит в профиль {PROFILE}"


def strip_heredocs(command: str) -> tuple:
    """Отделяет тела heredoc от самой команды.

    Тело heredoc — данные, а не код: `git commit -F - <<MSG` пишет сообщение,
    `cat > file <<PY` пишет файл. Разбирая тело как команды, профиль видел в
    тексте сообщения «команду» и снимал разрешение со всей строки — то есть
    коммит с описанием работы останавливал работу.

    Возвращает `(команда без тел, тела, которые кто-то исполняет)`. Тело,
    исполняемое оболочкой, разбирается дальше как обычная команда; тело
    скриптового интерпретатора — как локальный код: ровно то же самое, что
    `python3 script.py`, которое профиль и так разрешает. Запреты к телу
    применяет слой фабрики (`evaluate_interpreter_body`) до профиля.
    """
    rules = _guard_rules()
    if rules is None:
        return command, []
    text, bodies = rules.strip_heredoc_bodies(command)
    return text, [body for body in bodies if body.partition("\n")[0]]


#: Стоп-сигналы, которые снимаются выполненными условиями production.
PRODUCTION_STOP_LABELS = {"операция над production", "выкат или откат вне staging"}

SITE_ARG_RE = re.compile(r"--site[= ]\s*([A-Za-z0-9._-]+)")
FACTORY_MUTATION_RE = re.compile(r"\bfactory\s+(?:deploy|rollback)\b")


def _load_package(site_id: str, root: str):
    """Пакет сайта. Ошибка чтения — не «условие выполнено», а отсутствие данных."""
    path = os.path.join(root, "sites", site_id, "package.yaml")
    if not os.path.exists(path):
        return None
    try:
        import yaml
    except Exception:
        return None
    try:
        with open(path, encoding="utf-8") as handle:
            data = yaml.safe_load(handle)
    except Exception:
        return None
    return data if isinstance(data, dict) else None


ENVIRONMENT_FLAG_RE = re.compile(
    r"--environment[= ]\s*([A-Za-z0-9_-]+)|--env[= ]\s*([A-Za-z0-9_-]+)"
)

#: Единственное окружение, выкат в которое требует выполненных условий.
PRODUCTION = "production"


def targets_production(command: str, root: str | None = None) -> tuple:
    """Метит ли команда в боевое окружение. `(да, пояснение)`.

    Флаг сильнее пакета: явно указанное окружение решает, чей бы пакет ни был
    назван. Без флага решает поле `environment` самого пакета: штатный
    `factory deploy --site X` выкатывает ровно туда, куда написано в manifest,
    и требовать подтверждения у выката на стенд значит останавливать обычную
    работу. Нечитаемый пакет и неназванный сайт считаются боевыми: не знать,
    куда метит команда, — это не то же самое, что знать, что она безопасна.
    """
    root = os.path.realpath(root or _repo_root())
    match = ENVIRONMENT_FLAG_RE.search(command)
    if match:
        value = (match.group(1) or match.group(2) or "").lower()
        return value == PRODUCTION, f"флаг окружения: {value}"

    site = SITE_ARG_RE.search(command)
    if not site:
        return True, "в команде не указан --site, окружение неизвестно"
    package = _load_package(site.group(1), root)
    if package is None:
        return True, f"пакет sites/{site.group(1)}/package.yaml не прочитан"
    environment = str(package.get("environment") or "").lower()
    if not environment:
        return True, "в пакете не указано environment"
    return environment == PRODUCTION, f"пакет объявляет environment={environment}"


def production_gate(command: str, root: str | None = None) -> tuple:
    """Выполнены ли условия штатного выката на production.

    Проверяются статические условия, которые видны из пакета сайта и реестров:
    цель в inventory и пригодна для production, домен связан с этим пакетом,
    объявлены проверенный бэкап, атомарность релиза, health-check и rollback,
    переданы права и авторизация владельца.

    Условия «секреты не попали в лог и git», «все обязательные тесты прошли» и
    «изменение отражено в audit log» здесь не проверяются и не объявляются
    выполненными: их обеспечивает сам конвейер во время работы
    (`factory.redaction`, ворота `factory/pipeline.py`, `factory/audit.py`), и
    без них выкат не состоится. Разрешение на команду не подменяет эти ворота,
    а лишь снимает лишний вопрос перед их запуском.

    Возвращает `(готово, причина)`. Причина называет первое невыполненное
    условие — молчаливый отказ не даёт понять, чего не хватает.
    """
    root = os.path.realpath(root or _repo_root())
    match = SITE_ARG_RE.search(command)
    if not match:
        return False, "в команде не указан --site"
    site_id = match.group(1)

    package = _load_package(site_id, root)
    if package is None:
        return False, f"пакет sites/{site_id}/package.yaml не прочитан"

    if package.get("fixture", False):
        return False, "пакет помечен fixture: тестовые данные в production запрещены"
    if not package.get("production_authorized", False):
        return False, "в manifest нет production_authorized: true"

    content_source = package.get("content_source") or {}
    if not content_source.get("rights_confirmed", False):
        return False, "права на контент не подтверждены (rights_confirmed)"
    if not content_source.get("rights_manifest_ref"):
        return False, "не передан rights_manifest_ref"

    domain = str(package.get("domain") or "").strip().lower()
    if not domain or domain.endswith((".localhost", ".localhost.test", ".test", ".local")):
        return False, f"домен «{domain or 'не указан'}» не является боевым"
    canonical = str(package.get("canonical_url") or "")
    if domain not in canonical:
        return False, "canonical_url не связан с доменом пакета"

    target_ref = str(package.get("target_ref") or "").strip()
    if not target_ref:
        return False, "в пакете нет target_ref"
    targets = {t.get("ref"): t for t in inventory_targets(root) if t.get("ref")}
    target = targets.get(target_ref)
    if target is None:
        return False, f"цель «{target_ref}» отсутствует в inventory/targets.yaml"
    if str(target.get("production_capable", "false")).lower() != "true":
        return False, f"цель «{target_ref}» не помечена production_capable"

    backup = package.get("backup_policy") or {}
    if not backup.get("before_mutation", False):
        return False, "backup_policy.before_mutation не включён"
    if not backup.get("restore_test"):
        return False, "backup_policy.restore_test не задан: бэкап не проверяется"

    rollback = package.get("rollback_policy") or {}
    if not rollback.get("auto_rollback_on_smoke_failure", False):
        return False, "rollback_policy.auto_rollback_on_smoke_failure выключен"
    if int(rollback.get("keep_releases") or 0) < 1:
        return False, "rollback_policy.keep_releases меньше одного: откат невозможен"

    monitoring = package.get("monitoring_policy") or {}
    if not monitoring.get("health_endpoint"):
        return False, "monitoring_policy.health_endpoint не задан"
    if not (monitoring.get("checks") or []):
        return False, "monitoring_policy.checks пуст: health-check нечем выполнить"

    return True, f"условия production выполнены для {site_id} на цели {target_ref}"


def mandatory_confirmation(command: str, root: str | None = None) -> str:
    """Название стоп-сигнала, если команда его задевает, иначе пустая строка.

    Стоп-сигнал сильнее любого разрешающего правила: разрешение выдаётся на
    команду целиком, поэтому совпадение в любой её части снимает автоматизм.

    Исключение одно и оно проверяемое: штатный выкат фабрики на утверждённую
    цель. Если все условия production выполнены, вопрос снимается; если хоть
    одно не выполнено, стоп-сигнал называет именно его.
    """
    # Тело heredoc отделяется и здесь: стоп-сигнал ищется в команде, а не в
    # тексте, который команда записывает. Иначе сообщение коммита, называющее
    # запрещённое действие, само становилось запрещённым действием.
    text, bodies = strip_heredocs((command or "").strip())
    # Стоп-сигнал ищется и в теле, которое исполняет оболочка: `bash <<EOF` с
    # `git push --force` внутри — это push --force, а не текст.
    searched = "\n".join(
        [text] + [b.partition("\n")[2] for b in bodies if b.partition("\n")[0] == "shell"]
    )
    hits = [label for pattern, label in STOP_RE if pattern.search(searched)]
    if not hits:
        return ""
    if set(hits) <= PRODUCTION_STOP_LABELS and FACTORY_MUTATION_RE.search(text):
        # Выкат на стенд — обычная работа, а не необратимое действие: стенд
        # пересоздаётся, и останавливать его подтверждением значит остановить
        # весь цикл разработки ради операции, которую и так можно повторить.
        production, _why = targets_production(text, root)
        if not production:
            return ""
        ready, reason = production_gate(text, root)
        return "" if ready else f"{hits[0]} — {reason}"
    return hits[0]


def evaluate(command: str, root: str | None = None) -> Verdict:
    """Разрешение по профилю. ALLOW — только если рутинен каждый сегмент."""
    root = os.path.realpath(root or _repo_root())
    text = (command or "").strip()
    if not text:
        return Verdict(PASS, "пустая команда")

    stop = mandatory_confirmation(text, root)
    if stop:
        return Verdict(PASS, f"обязательное подтверждение: {stop}")

    text, bodies = strip_heredocs(text)

    parts = list(segments(text))
    scripted = False
    for body in bodies:
        kind, _, payload = body.partition("\n")
        if kind == "shell":
            # Оболочка исполнит тело как команды — разбираем их наравне с прочими.
            parts.extend(segments(payload))
        else:
            # Скриптовое тело эквивалентно `python3 script.py`, которое профиль
            # и так разрешает: он не разбирает чужой язык и не притворяется, что
            # разбирает. Границу держат запреты слоя фабрики
            # (`evaluate_interpreter_body` уже проверил тело) и права файловой
            # системы, а не этот разбор.
            scripted = True

    reasons: list[str] = []
    for segment in parts:
        if not segment.strip():
            continue
        ok, reason = classify_segment(segment, root)
        if not ok:
            return Verdict(PASS, reason)
        reasons.append(reason)
    if scripted:
        reasons.append("локальный код интерпретатора")
    if not reasons:
        return Verdict(PASS, "нечего разбирать")
    return Verdict(ALLOW, "; ".join(dict.fromkeys(reasons)))


def evaluate_path(path: str, root: str | None = None) -> Verdict:
    """Разрешение на запись файла: внутри репозитория — да, наружу — нет."""
    root = os.path.realpath(root or _repo_root())
    if not path:
        return Verdict(PASS, "путь не указан")
    return (
        Verdict(ALLOW, "запись внутри репозитория")
        if _inside_repo(path, root)
        else Verdict(PASS, "запись за пределами репозитория")
    )
