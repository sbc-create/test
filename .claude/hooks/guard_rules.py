"""Детерминированные запреты фабрики.

Модуль намеренно не зависит ни от чего, кроме stdlib: хуки должны работать даже
в окружении без установленных зависимостей проекта. Функции чистые и покрыты
tests/unit/test_guard_rules.py — правило, которое нельзя протестировать, не правило.
"""
from __future__ import annotations

import os
import re
from dataclasses import dataclass
from typing import Iterable

ALLOW = "allow"
DENY = "deny"
PASS = "pass"  # хук не высказывается, решают обычные permission rules

SEPARATORS = ("&&", "||", ";", "|&", "|", "&", "\n")

# Обёртки, которые исполняют свой аргумент как команду.
# Список расширен после security review: env/flock/watch/setsid/ionice/chroot и
# контейнерные раннеры точно так же запускают произвольную команду, и без них
# `env ssh prod reboot` проходил проверку.
WRAPPERS = {
    "timeout", "time", "nice", "nohup", "stdbuf", "command", "builtin", "noglob", "xargs",
    "env", "flock", "watch", "setsid", "ionice", "chrt", "taskset", "unbuffer", "script",
    "sudo_wrapper", "runuser", "chroot", "proot", "doas_wrapper",
}
# Обёртки, для которых срезается ещё и значение опции (например `timeout 30 cmd`).
WRAPPER_TAKES_VALUE = {"timeout", "nice", "stdbuf", "flock", "ionice", "chrt", "taskset", "watch"}

#: Интерпретаторы: содержимое их `-c` разбирается рекурсивно.
SHELL_INTERPRETERS = {"bash", "sh", "zsh", "dash", "ksh", "csh", "tcsh", "fish"}
INTERPRETERS = {"bash", "sh", "zsh", "dash", "ksh", "csh", "tcsh", "fish",
                "python", "python2", "python3", "perl", "ruby", "node", "nodejs", "php", "deno", "bun"}
#: Раннеры, запускающие команду внутри контейнера/окружения.
CONTAINER_RUNNERS = {"docker", "podman", "nerdctl", "kubectl", "devbox", "mise", "direnv", "npx", "pnpm", "yarn", "bunx"}


@dataclass(frozen=True)
class Decision:
    decision: str
    reason: str = ""
    rule_id: str = ""


HEREDOC_RE = re.compile(r"<<-?\s*(['\"]?)([A-Za-z_][A-Za-z0-9_]*)\1")


def strip_heredoc_bodies(command: str) -> tuple[str, list[str]]:
    """Отделяет тела heredoc от самой команды.

    Тело heredoc — это данные (`cat > file <<'PY' … PY`), а не команда: разбирать
    его как код значит блокировать запись исходников, которые лишь упоминают
    запрещённое имя. Исключение — интерпретаторы (`bash <<'EOF'`), которые тело
    действительно исполняют: их тела возвращаются отдельно для рекурсивного разбора.
    """
    match = HEREDOC_RE.search(command)
    if not match:
        return command, []
    marker = match.group(2)
    head = command[: match.start()]
    tail = command[match.end():]
    lines = tail.split("\n")
    body_lines: list[str] = []
    rest_lines: list[str] = []
    closed = False
    for line in lines[1:] if lines and not lines[0].strip() else lines:
        if not closed and line.strip() == marker:
            closed = True
            continue
        (rest_lines if closed else body_lines).append(line)
    remainder = head + (" " + "\n".join(rest_lines) if rest_lines else "")
    first = os.path.basename((head.split() or [""])[0])
    # Оболочка исполняет тело как shell-код, скриптовый интерпретатор — как свой язык.
    kind = "shell" if first in SHELL_INTERPRETERS else ("script" if first in INTERPRETERS else "")
    executed = f"{kind}\n" + "\n".join(body_lines) if kind else ""
    nested_remainder, nested_bodies = (remainder, []) if not HEREDOC_RE.search(remainder) else strip_heredoc_bodies(remainder)
    bodies = ([executed] if executed else []) + nested_bodies
    return nested_remainder, bodies


def split_subcommands(command: str) -> list[str]:
    """Разбивает составную команду на подкоманды с учётом кавычек."""
    parts: list[str] = []
    buf: list[str] = []
    quote: str | None = None
    i = 0
    while i < len(command):
        ch = command[i]
        if quote:
            buf.append(ch)
            if ch == quote and (i == 0 or command[i - 1] != "\\"):
                quote = None
            i += 1
            continue
        if ch in ("'", '"'):
            quote = ch
            buf.append(ch)
            i += 1
            continue
        matched = next((s for s in SEPARATORS if command.startswith(s, i)), None)
        if matched:
            parts.append("".join(buf))
            buf = []
            i += len(matched)
            continue
        buf.append(ch)
        i += 1
    parts.append("".join(buf))
    return [p.strip() for p in parts if p.strip()]


def strip_wrappers(sub: str) -> str:
    """Срезает `VAR=1 timeout 30 nice cmd …` до фактической команды."""
    tokens = sub.split()
    while tokens:
        head = tokens[0]
        if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*=.*", head):
            tokens = tokens[1:]
            continue
        if head in WRAPPERS:
            tokens = tokens[1:]
            # срезаем опции и значение обёртки: `timeout 30`, `flock /tmp/l`, `nice -n 5`
            while tokens and (
                tokens[0].startswith("-")
                or (head in WRAPPER_TAKES_VALUE and re.fullmatch(r"[0-9]+[smhd]?", tokens[0]))
                or (head == "flock" and not tokens[0].startswith("-") and "/" in tokens[0])
            ):
                tokens = tokens[1:]
            continue
        break
    return " ".join(tokens)


# --- наборы правил -------------------------------------------------------------

REMOTE_EXEC = ("ssh", "scp", "sftp", "rsync", "ansible", "ansible-playbook", "ansible-console", "nc", "ncat", "telnet")
PRIVILEGE = ("sudo", "su", "doas", "pkexec")
FIREWALL_DNS = ("iptables", "ip6tables", "nft", "ufw", "firewall-cmd", "nsupdate", "resolvectl", "route", "ip")
NETWORK_FETCH = ("curl", "wget", "aria2c", "httpie", "http")
DB_CLIENTS = ("mysql", "mysqldump", "psql", "mariadb", "mongo", "redis-cli")

SECRET_PATH_RE = re.compile(
    r"(?:^|[\s'\"=/])(?:\.env(?:\.[\w.-]+)?|secrets/|id_rsa|id_ed25519|id_ecdsa|\.pem|\.p12|\.pfx|"
    r"authorized_keys|\.ssh/|\.aws/credentials|\.npmrc|\.pypirc)",
    re.IGNORECASE,
)
READERS = ("cat", "less", "more", "head", "tail", "bat", "strings", "xxd", "od", "grep", "rg", "awk", "sed", "cp", "mv", "base64", "openssl")

DESTRUCTIVE_RM_RE = re.compile(r"\brm\s+(?:-[a-zA-Z]*\s+)*-{1,2}[a-zA-Z]*[rf]", re.IGNORECASE)
BROAD_PATH_RE = re.compile(
    r"(?:^|\s)(?:/|/\*|~|~/|\$HOME|\.|\./|\*|/etc(?:/|\s|$)|/var(?:/|\s|$)|/usr(?:/|\s|$)|/home(?:/|\s|$)|/opt(?:/|\s|$)|/srv(?:/|\s|$))"
)
DB_DESTRUCTIVE_RE = re.compile(r"\b(?:DROP\s+(?:DATABASE|SCHEMA|TABLE)|TRUNCATE\s+TABLE|DELETE\s+FROM\s+\w+\s*;?\s*$)", re.IGNORECASE)
GIT_DESTRUCTIVE_RE = re.compile(
    r"\bgit\s+(?:.*\s)?(?:push\s+(?:.*\s)?(?:--force\b|-f\b)|reset\s+--hard|clean\s+-[a-zA-Z]*[fd]|filter-branch|update-ref\s+-d|branch\s+-D)",
    re.IGNORECASE,
)
DISK_RE = re.compile(r"\b(?:mkfs(?:\.\w+)?|fdisk|parted|shred|wipefs)\b|\bdd\b[^\n]*\bof=/dev/", re.IGNORECASE)
WORLD_WRITABLE_RE = re.compile(r"\bchmod\s+(?:-R\s+)?(?:0?777|a\+rwx|o\+w)\b", re.IGNORECASE)
BYPASS_RE = re.compile(r"--dangerously-skip-permissions|bypassPermissions|dangerouslyDisableSandbox", re.IGNORECASE)
PROD_PATH_RE = re.compile(r"(?:^|\s)/(?:etc|var/www|var/lib/mysql|srv/www|usr/local/etc)(?:/|\s|$)")


def _host_from_fetch(sub: str) -> str | None:
    m = re.search(r"https?://([^/\s'\"]+)", sub)
    return m.group(1).lower() if m else None


def network_allowlist() -> set[str]:
    """Allowlist текущего задания. Пусто = сеть в режиме B запрещена."""
    raw = os.environ.get("FACTORY_NETWORK_ALLOWLIST", "")
    return {h.strip().lower() for h in raw.split(",") if h.strip()}


def closed_world() -> bool:
    """Fail-closed: закрытый мир действует всегда, кроме явного FACTORY_CLOSED_WORLD=0.

    Режим A (research) снимает ограничение осознанно и только на время сбора базы знаний.
    """
    return os.environ.get("FACTORY_CLOSED_WORLD", "1") != "0"


def _is_localhost(host: str) -> bool:
    return host.split(":")[0] in {"127.0.0.1", "localhost", "::1", "[::1]"}


SUBSTITUTION_RE = re.compile(r"\$\(([^()]*)\)|`([^`]*)`")
DASH_C_RE = re.compile(r"(?:^|\s)-c\s+(?P<q>['\"])(?P<body>.*?)(?P=q)\s*$", re.S)
DASH_C_BARE_RE = re.compile(r"(?:^|\s)-c\s+(?P<body>\S.*)$", re.S)
FIND_EXEC_RE = re.compile(r"-(?:exec|execdir)\s+(?P<body>.+)$", re.S)
REDIRECT_READ_RE = re.compile(r"<\s*([^\s<>|&;]+)")
DECODE_TO_SHELL_RE = re.compile(
    r"\b(?:base64|xxd|openssl\s+enc|uudecode|gunzip|zcat)\b[^|]*\|\s*(?:sudo\s+)?"
    r"(?:ba|z|k|da|)sh\b|\b(?:echo|printf)\b[^|]*\|\s*(?:base64|xxd)[^|]*\|\s*(?:ba|z|k|da|)sh\b",
    re.IGNORECASE,
)


def _nested_fragments(stripped: str, raw: str = "") -> list[str]:
    """Команды, спрятанные внутри подстановок, `-c`, find -exec и раннеров."""
    fragments: list[str] = []
    for source in (raw or stripped, stripped):
        for group in SUBSTITUTION_RE.findall(source):
            fragments.extend(part for part in group if part.strip())
    tokens = stripped.split()
    if not tokens:
        return fragments
    prog = os.path.basename(tokens[0])
    if prog in INTERPRETERS:
        match = DASH_C_RE.search(stripped) or DASH_C_BARE_RE.search(stripped)
        if match:
            fragments.append(match.group("body"))
    if prog in ("find", "fd"):
        match = FIND_EXEC_RE.search(stripped)
        if match:
            # терминатор `\;` / `;` / `+` мог быть срезан разбиением на подкоманды
            fragments.append(match.group("body").rstrip("\\;+ ").strip())
    if prog in CONTAINER_RUNNERS and len(tokens) > 1:
        rest = tokens[1:]
        while rest and (rest[0].startswith("-") or rest[0] in ("exec", "run", "compose", "--")):
            rest = rest[1:]
        if prog in ("docker", "podman", "nerdctl", "kubectl") and rest:
            rest = rest[1:]        # имя контейнера/пода
        if rest:
            fragments.append(" ".join(rest))
    if prog == "xargs":
        rest = [t for t in tokens[1:] if not t.startswith("-")]
        if rest:
            fragments.append(" ".join(rest))
    return fragments


def evaluate_subcommand(sub: str, depth: int = 0) -> Decision:
    stripped = strip_wrappers(sub)
    if not stripped:
        return Decision(PASS)
    tokens = stripped.split()
    prog = os.path.basename(tokens[0]) if tokens else ""
    low = stripped.lower()

    if BYPASS_RE.search(stripped):
        return Decision(DENY, "Запрещён обход системы разрешений/песочницы.", "G-BYPASS")

    if prog in PRIVILEGE:
        return Decision(DENY, "Неконтролируемый sudo/su запрещён. Привилегированные операции выполняет deployment-слой по sudo_allowlist из inventory.", "G-PRIV")

    if prog in REMOTE_EXEC:
        return Decision(
            DENY,
            f"Прямой удалённый доступ `{prog}` запрещён. Используй `python3 -m factory deploy <site_id> --environment <env>`: wrapper проверяет manifest, allowlist целей, авторизацию, backup, lock и quality gates.",
            "G-REMOTE",
        )

    if prog in FIREWALL_DNS and prog != "ip" or (prog == "ip" and len(tokens) > 1 and tokens[1] in {"route", "addr", "link"} and any(t in {"add", "del", "change"} for t in tokens)):
        return Decision(DENY, f"Изменение сетевой конфигурации/DNS через `{prog}` вне manifest запрещено.", "G-NET-CFG")

    if DISK_RE.search(stripped):
        return Decision(DENY, "Операции форматирования/затирания дисков запрещены.", "G-DISK")

    if WORLD_WRITABLE_RE.search(stripped):
        return Decision(DENY, "world-writable права запрещены (§3.9).", "G-PERM777")

    if DESTRUCTIVE_RM_RE.search(stripped):
        target_part = stripped[stripped.lower().index("rm") + 2 :]
        args = [t for t in target_part.split() if not t.startswith("-")]
        if not args or any(BROAD_PATH_RE.search(" " + a) for a in args):
            return Decision(DENY, "Рекурсивное удаление по широкому пути запрещено. Удаляй точный подкаталог внутри var/ или queue/.", "G-RM")

    if GIT_DESTRUCTIVE_RE.search(stripped):
        return Decision(DENY, "Деструктивные git-операции (force push, reset --hard, clean, filter-branch, branch -D) запрещены.", "G-GIT")

    if DB_DESTRUCTIVE_RE.search(stripped):
        return Decision(DENY, "DROP/TRUNCATE и безусловный DELETE запрещены. Миграции выполняются blueprint-слоем после backup.", "G-DB")

    if prog in DB_CLIENTS:
        return Decision(DENY, f"Прямой доступ к СУБД через `{prog}` запрещён: работа с БД идёт через deployment-слой с backup и lock.", "G-DBCLI")

    # Секретный путь запрещён в любой команде, а не только у известных «читалок»:
    # `python3 -c "open('.env')"` и `while read l; do :; done < .env` читают ровно то же.
    if SECRET_PATH_RE.search(" " + stripped) or any(
        SECRET_PATH_RE.search(" " + target) for target in REDIRECT_READ_RE.findall(stripped)
    ):
        return Decision(
            DENY,
            "Обращение к секретному файлу запрещено. Секреты доступны только через secret_ref в момент исполнения.",
            "G-SECRET",
        )

    # Записывать в защищённые пути через shell тоже нельзя: иначе правила защиты
    # переписываются тем же механизмом, который они охраняют.
    for target in re.findall(r">>?\s*([^\s<>|&;]+)", stripped):
        if evaluate_write(target).decision == DENY:
            return Decision(DENY, f"Запись в защищённый путь «{target}» запрещена.", "G-WRITE")
    if prog in ("tee", "cp", "mv", "install", "ln", "truncate", "sed", "dd", "rsync", "chmod", "chown"):
        for token in stripped.split()[1:]:
            candidate = token.strip("'\"")
            if evaluate_write(candidate).decision == DENY:
                return Decision(DENY, f"Изменение защищённого пути «{candidate}» запрещено.", "G-WRITE")

    # Рекурсивный разбор вложенных команд: подстановки, `-c`, find -exec, раннеры.
    if depth < 3:
        for fragment in _nested_fragments(stripped, sub):
            nested = evaluate_bash(fragment, depth + 1)
            if nested.decision == DENY:
                return Decision(nested.decision, f"Вложенная команда: {nested.reason}", nested.rule_id)

    if prog in NETWORK_FETCH:
        host = _host_from_fetch(stripped)
        allow = network_allowlist()
        if host and _is_localhost(host):
            return Decision(PASS)
        if closed_world() and (not host or host not in allow):
            return Decision(
                DENY,
                f"Сетевой доступ к «{host or 'неизвестному хосту'}» не входит в network_allowlist задания. В режиме CLOSED_WORLD произвольная загрузка запрещена.",
                "G-EGRESS",
            )

    if PROD_PATH_RE.search(" " + stripped) and prog in {"tee", "cp", "mv", "install", "touch", "mkdir", "ln", "chown", "chmod"}:
        return Decision(DENY, "Прямая запись в системные/производственные пути запрещена: это делает deployment-слой.", "G-PRODPATH")

    return Decision(PASS)


PIPE_TO_SHELL_RE = re.compile(
    r"\b(?:curl|wget|aria2c)\b[^|]*\|\s*(?:sudo\s+)?(?:ba|z|k|da|)sh\b|"
    r"\b(?:curl|wget)\b[^|]*\|\s*(?:python3?|perl|ruby|node)\b",
    re.IGNORECASE,
)


#: Вызовы shell из кода интерпретатора: содержимое разбирается как команда.
SHELL_CALL_RE = re.compile(
    r"(?:os\.system|os\.popen|subprocess\.(?:run|call|check_call|check_output|Popen)|"
    r"commands\.getoutput|child_process\.exec(?:Sync)?|shell_exec|system)\s*\(",
)
QUOTED_RE = re.compile(r"""['"]([^'"\n]{2,200})['"]""")


def evaluate_interpreter_body(body: str, depth: int = 0) -> Decision:
    """Разбирает тело, которое исполнит интерпретатор.

    Полноценный анализ произвольного кода невозможен — и это честно записано в
    docs/SECURITY.md: hook останавливает неосторожный обход, а настоящая граница
    задаётся permission-правилами и правами файловой системы. Здесь ловится то,
    что ловится надёжно: обращение к секретным путям и запуск shell-команд.
    """
    if SECRET_PATH_RE.search(" " + body):
        return Decision(DENY, "Код обращается к секретному пути.", "G-SECRET")
    for match in SHELL_CALL_RE.finditer(body):
        tail = body[match.end(): match.end() + 400]
        quoted = QUOTED_RE.findall(tail)
        # Список аргументов (`subprocess.run(["rm", "-rf", "/"])`) опасен именно в
        # склеенном виде: каждый токен по отдельности безобиден.
        candidates = quoted + ([" ".join(quoted)] if len(quoted) > 1 else [])
        for candidate in candidates:
            decision = evaluate_bash(candidate, depth + 1)
            if decision.decision == DENY:
                return decision
    return Decision(PASS)


def evaluate_bash(command: str, depth: int = 0) -> Decision:
    # Тела heredoc отделяются до анализа: они данные, кроме случая, когда их
    # читает интерпретатор — тогда они разбираются как вложенный код.
    command, heredoc_bodies = strip_heredoc_bodies(command)
    for body in heredoc_bodies:
        kind, _, payload = body.partition("\n")
        if depth >= 3:
            nested = Decision(PASS)
        elif kind == "shell":
            nested = evaluate_bash(payload, depth + 1)
        else:
            nested = evaluate_interpreter_body(payload, depth)
        if nested.decision == DENY:
            return Decision(nested.decision, f"Тело heredoc для интерпретатора: {nested.reason}", nested.rule_id)
    if PIPE_TO_SHELL_RE.search(command):
        return Decision(DENY, "Загрузка кода из сети напрямую в интерпретатор запрещена в любом режиме.", "G-PIPESH")
    if DECODE_TO_SHELL_RE.search(command):
        return Decision(DENY, "Исполнение декодированного из base64/архива кода запрещено.", "G-PIPESH")
    for sub in split_subcommands(command):
        d = evaluate_subcommand(sub, depth)
        if d.decision == DENY:
            return d
    return Decision(PASS)


PROTECTED_WRITE_PATTERNS: tuple[tuple[str, str], ...] = (
    (r"(^|/)\.claude/", "Конфигурация правил и хуков не редактируется агентом: иначе защита снимается тем же механизмом, который она охраняет. Изменения вносит оператор вручную."),
    (r"(^|/)inventory/(ssh-hosts|dns-zones|dle-licenses)\.yaml$", "Реестр целей, зон и лицензий меняет оператор: запись sudo_allowlist исполняется на целевом хосте с повышенными правами."),
    (r"(^|/)\.env(\.|$)", "Файлы окружения с секретами не редактируются агентом."),
    (r"(^|/)secrets/", "Каталог secrets/ недоступен для записи."),
    (r"(^|/)knowledge/KNOWLEDGE_FREEZE\.yaml$", "Freeze меняется только скриптом `python3 -m factory knowledge freeze` через skill /research-freeze."),
    (r"(^|/)blueprints/dle20/dist/", "Лицензионный дистрибутив DLE не хранится в git."),
    (r"\.(pem|key|p12|pfx)$", "Ключевой материал не создаётся и не редактируется агентом."),
    (r"(^|/)id_(rsa|ed25519|ecdsa)", "SSH-ключи не создаются агентом."),
    (r"(^|/)inventory/known_hosts", "known_hosts обновляется оператором, а не агентом."),
)


def evaluate_write(path: str) -> Decision:
    norm = path.replace("\\", "/")
    for pattern, reason in PROTECTED_WRITE_PATTERNS:
        if re.search(pattern, norm):
            return Decision(DENY, reason, "G-WRITE")
    return Decision(PASS)


SECRET_CONTENT_PATTERNS: tuple[tuple[str, str], ...] = (
    (r"-----BEGIN (?:RSA |EC |OPENSSH |DSA |PGP )?PRIVATE KEY-----", "приватный ключ"),
    (r"\bAKIA[0-9A-Z]{16}\b", "AWS access key id"),
    (r"\bgh[pousr]_[A-Za-z0-9]{20,}\b", "GitHub token"),
    (r"\bvk1\.a\.[A-Za-z0-9_\-]{20,}", "VK access token"),
    (r"(?i)\b(?:password|passwd|secret|api[_-]?key|access[_-]?token|client[_-]?secret)\b\s*[:=]\s*['\"]?[A-Za-z0-9_\-\.]{12,}", "значение секрета в открытом виде"),
)

SECRET_CONTENT_ALLOW = re.compile(r"secret_ref|env:[A-Z_]+|<64 hex>|\bexample\b|XXXX|REDACTED|\$\{[A-Z_]+\}", re.IGNORECASE)


def scan_secret_content(text: str) -> list[str]:
    findings: list[str] = []
    for line in text.splitlines():
        if SECRET_CONTENT_ALLOW.search(line):
            continue
        for pattern, label in SECRET_CONTENT_PATTERNS:
            if re.search(pattern, line):
                findings.append(label)
                break
    return findings


def iter_rule_ids() -> Iterable[str]:
    return ("G-BYPASS", "G-PRIV", "G-REMOTE", "G-NET-CFG", "G-DISK", "G-PERM777", "G-RM", "G-GIT", "G-DB", "G-DBCLI", "G-SECRET", "G-EGRESS", "G-PIPESH", "G-PRODPATH", "G-WRITE")
