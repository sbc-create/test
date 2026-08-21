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
WRAPPERS = {"timeout", "time", "nice", "nohup", "stdbuf", "command", "builtin", "noglob", "xargs"}
# Обёртки, для которых срезается ещё и опция (например `timeout 30 cmd`).
WRAPPER_TAKES_VALUE = {"timeout", "nice", "stdbuf"}


@dataclass(frozen=True)
class Decision:
    decision: str
    reason: str = ""
    rule_id: str = ""


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
            # срезаем числовой/опциональный аргумент обёртки
            while tokens and (tokens[0].startswith("-") or (head in WRAPPER_TAKES_VALUE and re.fullmatch(r"[0-9]+[smhd]?", tokens[0]))):
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


def evaluate_subcommand(sub: str) -> Decision:
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

    if prog in READERS and SECRET_PATH_RE.search(" " + stripped):
        return Decision(DENY, "Чтение секретных файлов запрещено. Секреты доступны только через secret_ref в момент исполнения.", "G-SECRET")

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


def evaluate_bash(command: str) -> Decision:
    if PIPE_TO_SHELL_RE.search(command):
        return Decision(DENY, "Загрузка кода из сети напрямую в интерпретатор запрещена в любом режиме.", "G-PIPESH")
    for sub in split_subcommands(command):
        d = evaluate_subcommand(sub)
        if d.decision == DENY:
            return d
    return Decision(PASS)


PROTECTED_WRITE_PATTERNS: tuple[tuple[str, str], ...] = (
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
