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

from seo_operator.guardrails import split_segments

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
    (r"git\s+push\b[^\n]*(?:--force\b|--force-with-lease\b|\s-f\b|\+refs/)", "force push"),
    (r"git\s+push\b[^\n]*\s--delete\b|git\s+push\b[^\n]*\s:\s*\S", "удаление удалённой ветки"),
    (r"git\s+push\b[^\n]*\b(?:main|master)\b", "push напрямую в main"),
    (r"git\s+(?:reset\s+--hard|filter-branch|filter-repo)\b", "переписывание истории"),
    (r"git\s+rebase\b[^\n]*\s-i\b|git\s+rebase\b[^\n]*--interactive", "интерактивный rebase"),
    (r"git\s+branch\s+-[dD]\b|git\s+update-ref\s+-d\b", "удаление ветки"),
    (r"git\s+clean\b", "удаление неотслеживаемых файлов"),
    (r"\b(?:dropdb|dropuser)\b", "удаление базы или роли"),
    (r"\bDROP\s+(?:DATABASE|SCHEMA|TABLE)\b|\bTRUNCATE\b", "разрушительный SQL"),
    (r"\bDELETE\s+FROM\b(?![^\n]*\bWHERE\b)", "DELETE без WHERE"),
    (r"\bterraform\s+destroy\b|\baws\s+s3\s+rb\b", "удаление инфраструктуры"),
    (r"\b(?:backup|backups|snapshot)\b[^\n]*\b(?:rm|delete|destroy|purge)\b", "удаление бэкапа"),
    (r"\b(?:rm|delete|destroy|purge)\b[^\n]*\b(?:backup|backups)\b", "удаление бэкапа"),
    (r"\b(?:zone|domain|domains)\b[^\n]*\b(?:delete|destroy|transfer|release)\b",
     "удаление или перенос зоны/домена"),
    (r"\b(?:domain|domains|dns)\b[^\n]*\b(?:register|purchase|buy|renew)\b",
     "покупка домена"),
    (r"\b(?:billing|payment|invoice|subscription|checkout)\b[^\n]*\b(?:create|pay|charge|confirm)\b",
     "оплата услуг"),
    (r"--dangerously-skip-permissions|bypassPermissions|dangerouslyDisableSandbox",
     "обход разрешений"),
    (r"--no-verify\b", "обход git-хуков"),
    (r"(?:rm|mv|chmod\s+-x)\s+[^\n]*\.claude/hooks/", "отключение хуков"),
    (r"\$\{?(?:[A-Z_]*(?:SECRET|TOKEN|PASSWORD|API_KEY)[A-Z_]*)\b", "подстановка значения секрета"),
    (r"(?:^|[;&|]\s*)printenv\b|(?:^|[;&|]\s*)env\s*(?:\||>|;|$)", "дамп окружения"),
    # Секретные пути закрыты и здесь: профиль обязан быть безопасным в одиночку,
    # а не только в паре с guard_rules.
    (r"(?:^|[\s'\"=/])(?:\.env(?:\.[\w.-]+)?|secrets/|id_rsa|id_ed25519|id_ecdsa"
     r"|\.pem\b|\.p12\b|\.pfx\b|authorized_keys|\.ssh/|\.aws/credentials|\.npmrc|\.pypirc)",
     "обращение к секретному пути"),
    # Необратимые операции над production подтверждает человек, даже когда
    # выполняет их сама фабрика: разрешение выдаётся на команду, а не на среду.
    (r"--environment[= ]\s*production\b|--env[= ]\s*production\b", "операция над production"),
    (r"\bfactory\s+(?:deploy|rollback)\b(?![^\n]*--environment[= ]\s*staging\b)",
     "выкат или откат вне staging"),
    (r"\b(?:kubectl|helm)\s+(?:apply|delete|rollout)\b|\bterraform\s+apply\b",
     "мутация инфраструктуры"),
    # Удаление истории, конфигурации защиты, знаний и самих сайтов — не рутина.
    (r"\brm\b[^\n]*(?:\s|/)(?:\.git|\.claude|sites|knowledge|inventory|artifacts)(?:/|\s|$)",
     "удаление истории, защиты, знаний или сайтов"),
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


def normalize(segment: str) -> str:
    return strip_wrappers(strip_redirections(segment.strip()))


# --------------------------------------------------------------------------
# Инвентарь: цели SSH и зоны DNS читает слой фабрики, второй копии списка нет
# --------------------------------------------------------------------------
def _repo_root() -> str:
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _guard_rules(root: str | None = None):
    """Модуль правил фабрики. Недоступен — считаем инвентарь пустым (fail closed)."""
    import importlib.util

    path = os.path.join(root or _repo_root(), ".claude", "hooks", "guard_rules.py")
    if not os.path.exists(path):
        return None
    try:
        spec = importlib.util.spec_from_file_location("factory_guard_rules", path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    except Exception:
        return None


def inventory_hosts(root: str | None = None) -> set:
    rules = _guard_rules(root)
    return rules.inventory_ssh_hosts() if rules else set()


def inventory_zones(root: str | None = None) -> set:
    rules = _guard_rules(root)
    return rules.inventory_dns_zones() if rules else set()


def _read_hosts_file(root: str, name: str, section: str) -> set:
    rules = _guard_rules(root)
    if not rules:
        return set()
    values = set()
    for entry in rules._read_inventory(name, section):
        for key in ("host", "hostname", "address", "domain"):
            if entry.get(key):
                values.add(entry[key].lower())
    return values


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
    "ls", "cat", "head", "tail", "wc", "find", "grep", "rg", "egrep", "fgrep",
    "awk", "sort", "uniq", "cut", "tr", "diff", "stat", "file", "tree", "jq",
    "yq", "basename", "dirname", "realpath", "readlink", "date", "pwd", "echo",
    "printf", "true", "false", "test", "md5sum", "sha256sum", "sha1sum",
    "column", "nl", "tac", "comm", "du", "which", "command", "seq", "xxd", "cd",
}
#: `sed` читает только без `-i`; запись разбирается отдельно.
READ_ONLY_UNLESS_INPLACE = {"sed", "perl"}

FILE_WORK = {
    "mkdir", "touch", "cp", "mv", "ln", "rm", "rmdir", "chmod", "tee",
    "unzip", "tar", "zip", "gzip",
}

RUNTIMES = {
    "python", "python3", "pytest", "ruff", "mypy", "black", "isort", "pip", "pip3",
    "uv", "poetry", "node", "npm", "npx", "pnpm", "yarn", "corepack", "tsc",
    "eslint", "prettier", "playwright", "vitest", "jest", "php", "composer",
    "docker", "docker-compose", "podman", "make", "ansible-lint", "shellcheck",
    "hadolint", "psalm", "phpstan", "phpunit",
}
#: Удалённые исполнители: разрешены только к целям из inventory.
REMOTE = {"ssh", "scp", "sftp", "rsync", "ansible", "ansible-playbook"}
DNS_TOOLS = {"nsupdate"}
FETCH = {"curl", "wget", "http", "httpie"}
SHELLS = {"bash", "sh", "zsh"}

GIT_READ = {
    "status", "diff", "log", "show", "branch", "rev-parse", "rev-list", "ls-files",
    "ls-remote", "ls-tree", "fetch", "blame", "describe", "shortlog", "cat-file",
    "for-each-ref", "merge-base", "name-rev", "grep", "whatchanged", "count-objects",
    "remote", "config", "worktree", "stash", "check-ignore", "check-attr",
    "diff-tree", "diff-index", "symbolic-ref", "show-ref", "reflog", "verify-commit",
    "annotate", "archive", "hash-object", "help", "version", "notes", "bundle",
}
GIT_WRITE = {
    "add", "commit", "checkout", "switch", "restore", "merge", "rebase", "tag",
    "cherry-pick", "revert", "reset", "mv", "pull", "init", "apply", "am",
}
#: Ветки, в которые разрешён обычный push.
PUSH_BRANCH_RE = re.compile(r"(?:^|[\s:/])claude/[A-Za-z0-9._\-/]+")

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


#: Файлы, которые ansible принимает аргументом: это playbook, а не цель.
PLAYBOOK_RE = re.compile(r"\.(?:ya?ml|cfg|ini)$")
LIMIT_FLAGS = {"-l", "--limit", "-i", "--inventory", "--inventory-file"}


def _remote_host(tokens: list) -> str:
    """Хост из аргументов ssh/scp/rsync/ansible.

    У ansible цель задаётся флагом `-l/--limit`, а первым позиционным
    аргументом идёт playbook. Принять playbook за хост — значит выдать
    разрешение по имени файла, поэтому пути и флаги разбираются отдельно.
    """
    expect_limit = False
    for token in tokens[1:]:
        if expect_limit:
            expect_limit = False
            return token.split("@", 1)[-1].split(":", 1)[0].lower()
        if token in LIMIT_FLAGS:
            expect_limit = True
            continue
        if token.startswith("-"):
            continue
        candidate = token.split("@", 1)[-1].split(":", 1)[0]
        if not candidate or candidate.startswith("/") or candidate.startswith("."):
            continue
        if "/" in candidate or PLAYBOOK_RE.search(candidate):
            continue
        return candidate.lower()
    return ""


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

    if prog in READ_ONLY:
        return True, "чтение и локальный анализ"

    if prog in READ_ONLY_UNLESS_INPLACE:
        inplace = any(
            t == "-i" or t.startswith("-i") or t.startswith("--in-place")
            for t in tokens[1:]
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
        host = _remote_host(tokens)
        if host and host in inventory_hosts(root):
            return True, f"цель {host} внесена в inventory"
        return False, f"хост «{host or 'не определён'}» отсутствует в inventory/ssh-hosts.yaml"

    if prog in DNS_TOOLS:
        zones = inventory_zones(root)
        low = text.lower()
        if any(zone and zone in low for zone in zones):
            return True, "зона внесена в inventory"
        return False, "зона отсутствует в inventory/dns-zones.yaml"

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


def mandatory_confirmation(command: str) -> str:
    """Название стоп-сигнала, если команда его задевает, иначе пустая строка.

    Стоп-сигнал сильнее любого разрешающего правила: разрешение выдаётся на
    команду целиком, поэтому совпадение в любой её части снимает автоматизм.
    """
    text = (command or "").strip()
    for pattern, label in STOP_RE:
        if pattern.search(text):
            return label
    return ""


def evaluate(command: str, root: str | None = None) -> Verdict:
    """Разрешение по профилю. ALLOW — только если рутинен каждый сегмент."""
    root = os.path.realpath(root or _repo_root())
    text = (command or "").strip()
    if not text:
        return Verdict(PASS, "пустая команда")

    stop = mandatory_confirmation(text)
    if stop:
        return Verdict(PASS, f"обязательное подтверждение: {stop}")

    reasons: list[str] = []
    for segment in split_segments(text):
        ok, reason = classify_segment(segment, root)
        if not ok:
            return Verdict(PASS, reason)
        reasons.append(reason)
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
