"""
UNATTENDED_SAFE policy engine.

Единственный источник истины для PreToolUse enforcement. Fail-closed:
любая ошибка разбора, неизвестный инструмент или неразобранная конструкция => DENY.

Слой 1 (permissions в settings.json) отсекает очевидное.
Слой 2 (sandbox) ограничивает побочные эффекты.
Слой 3 (этот движок) — обязательный enforcement команд, путей и targets.
Текст в CLAUDE.md защитой НЕ является.

Модуль намеренно без внешних зависимостей: hook обязан работать даже если
venv сломан или пакет не установлен.
"""
from __future__ import annotations

import json
import os
import re
import shlex
from dataclasses import dataclass, field
from pathlib import Path

ALLOW = "allow"
DENY = "deny"
ASK = "ask"

# --------------------------------------------------------------------------
# Пути
# --------------------------------------------------------------------------

# Никогда не изменяется SEO-контуром (GR-012).
PROTECTED_PATH_PREFIXES = (
    ".claude/settings.json",
    ".claude/settings.unattended.json",
    ".claude/hooks/",
    "automation/approved-commands/",
    "inventory/authorization/",
    "seo/PROTECTED_GUARDRAILS.yaml",
    "src/seo_operator/guardrails.py",
    "src/seo_operator/audit.py",
)

# Секреты — не читать, не писать, не копировать (GR-003).
SECRET_PATH_PATTERNS = (
    r"(^|/)\.env(\.|$)",
    r"(^|/)\.envrc$",
    r"(^|/)\.netrc$",
    r"(^|/)\.pgpass$",
    r"(^|/)\.ssh/",
    r"(^|/)\.aws/(credentials|config)$",
    r"(^|/)\.docker/config\.json$",
    r"(^|/)\.git-credentials$",
    r"(^|/)id_(rsa|ed25519|ecdsa)(\.pub)?$",
    r"(^|/)secrets?\.(ya?ml|json|toml|ini)$",
    r"(^|/)service[-_]account.*\.json$",
    r"(^|/)credentials\.json$",
    r"(^|/)token(s)?\.json$",
    r"\.pem$",
    r"\.p12$",
    r"\.pfx$",
    r"\.key$",
)

# Куда разрешена запись помимо собственного worktree.
WRITABLE_EXTRA_PREFIXES = (
    "/tmp/claude-",
    "/var/tmp/seo-operator/",
)

# Единственные пути, где допустим рекурсивный delete.
DISPOSABLE_PATH_PREFIXES = (
    "/tmp/claude-",
    "/var/tmp/seo-operator/",
    "node_modules",
    ".pytest_cache",
    "__pycache__",
    "dist",
    "build",
    ".seo-state/tmp",
)

# --------------------------------------------------------------------------
# Команды
# --------------------------------------------------------------------------

READ_ONLY_BINARIES = {
    "cat", "head", "tail", "less", "wc", "sort", "uniq", "cut", "tr", "nl",
    "grep", "egrep", "fgrep", "rg", "ag", "find", "fd", "ls", "stat", "file",
    "du", "df", "pwd", "which", "type", "basename", "dirname", "realpath",
    "date", "echo", "printf", "true", "false", "test", "diff", "cmp", "comm",
    "jq", "yq", "xmllint", "column", "tee", "awk", "sed",
}

SAFE_WRITE_BINARIES = {
    "mkdir", "touch", "cp", "mv", "ln",
}

BUILD_TEST_BINARIES = {
    "python", "python3", "pip", "pip3", "pytest", "tox", "ruff", "black",
    "mypy", "flake8", "isort", "node", "npm", "npx", "pnpm", "yarn", "tsc",
    "eslint", "prettier", "jest", "vitest", "playwright", "make", "just",
}

GIT_READ_SUBCOMMANDS = {
    "status", "diff", "log", "show", "fetch", "branch", "remote", "rev-parse",
    "ls-files", "ls-remote", "blame", "shortlog", "describe", "config",
    "worktree", "stash",
}
GIT_WRITE_SUBCOMMANDS = {"add", "commit", "checkout", "switch", "restore", "merge", "pull", "tag", "push", "init"}

APPROVED_WRAPPER_DIR = "automation/approved-commands/"

# Явные deny-паттерны по всей нормализованной строке команды.
DENY_PATTERNS: list[tuple[str, str]] = [
    # --- разрушительное удаление ---
    (r"\brm\b[^|;&]*\s-[a-zA-Z]*[rR][a-zA-Z]*f|\brm\b[^|;&]*\s-[a-zA-Z]*f[a-zA-Z]*[rR]", "recursive_force_delete"),
    (r"\brm\b\s+(-\S+\s+)*/(\s|$)", "delete_root"),
    (r"\bshred\b|\bwipefs\b|\bmkfs\b|\bdd\b[^|;&]*\bof=/dev/", "destructive_disk_op"),
    (r":\(\)\s*\{.*\};\s*:", "fork_bomb"),
    # --- база данных ---
    (r"\bDROP\s+(TABLE|DATABASE|SCHEMA|INDEX)\b", "sql_drop"),
    (r"\bTRUNCATE\s+TABLE\b|\bTRUNCATE\s+\w+", "sql_truncate"),
    (r"\bDELETE\s+FROM\b(?![^;]*\bWHERE\b)", "sql_unbounded_delete"),
    (r"\bdropdb\b|\bdropuser\b", "db_drop_cli"),
    (r"\bmigrate\b[^|;&]*\b(down|reset|--fake|--force)\b", "destructive_migration"),
    # --- git история ---
    (r"\bgit\b[^|;&]*\bpush\b[^|;&]*(--force(?!-with-lease)|-f\b)", "force_push"),
    (r"\bgit\b[^|;&]*\bpush\b[^|;&]*--force-with-lease", "force_push_lease"),
    (r"\bgit\b[^|;&]*\bpush\b[^|;&]*--delete", "remote_ref_delete"),
    (r"\bgit\b[^|;&]*\b(filter-branch|filter-repo)\b", "history_rewrite"),
    (r"\bgit\b[^|;&]*\brebase\b", "history_rewrite"),
    (r"\bgit\b[^|;&]*\bcommit\b[^|;&]*--amend", "history_rewrite"),
    (r"\bgit\b[^|;&]*\breset\b[^|;&]*--hard", "hard_reset"),
    (r"\bgit\b[^|;&]*\bpush\b[^|;&]*\s:\S+", "remote_ref_delete"),
    (r"\bgit\b[^|;&]*--no-verify", "hook_bypass"),
    (r"\bgit\b[^|;&]*\bbranch\b[^|;&]*\s-D\b", "branch_force_delete"),
    (r"\bgit\b[^|;&]*\btag\b[^|;&]*\s-d\b", "tag_delete"),
    (r"\bgit\b[^|;&]*\bclean\b[^|;&]*-[a-zA-Z]*[xX]", "git_clean_ignored"),
    # --- секреты ---
    (r"\bprintenv\b|\benv\s*$|\bset\s*\|\s*grep", "env_dump"),
    (r"\b(echo|printf)\b[^|;&]*\$\{?(AWS_|GOOGLE_|YANDEX_|GSC_|CMS_|DB_|OAUTH|TOKEN|SECRET|API_KEY|PASSWORD)", "secret_print"),
    (r"\b(aws|gcloud|az)\b[^|;&]*\b(configure|auth|iam)\b", "credential_management"),
    (r"\bssh-keygen\b|\bssh-add\b|\bssh-copy-id\b", "ssh_credential_op"),
    (r"\bgh\b\s+auth\b|\bgit\s+credential\b", "credential_management"),
    (r"\bkeyctl\b|\bsecret-tool\b|\bpass\s+show\b", "secret_store_read"),
    (r"os\.environ(\.get\(|\[)\s*[\"\']?\w*(TOKEN|SECRET|KEY|PASSWORD|CREDENTIAL|OAUTH)", "secret_read_in_code"),
    (r"process\.env\.\w*(TOKEN|SECRET|KEY|PASSWORD|CREDENTIAL|OAUTH)", "secret_read_in_code"),
    (r"\bos\.getenv\(\s*[\"\']?\w*(TOKEN|SECRET|KEY|PASSWORD|CREDENTIAL|OAUTH)", "secret_read_in_code"),
    # --- система / root ---
    (r"\bsudo\b|\bsu\s+-|\bdoas\b", "privilege_escalation"),
    (r"\b(useradd|usermod|userdel|groupadd|passwd|chpasswd)\b", "os_user_change"),
    (r"\b(sshd|systemctl|service)\b[^|;&]*\b(sshd|ssh)\b", "ssh_daemon_change"),
    (r"\b(iptables|nft|ufw|firewall-cmd)\b", "firewall_change"),
    (r"\b(apt|apt-get|yum|dnf|apk|pacman)\b\s+(install|remove|purge|upgrade)", "system_package_change"),
    (r"\bchmod\b[^|;&]*\b777\b|\bchmod\b[^|;&]*-R\s+[0-7]{3,4}\s+/", "broad_permission_change"),
    (r"\bchown\b[^|;&]*-R\s+\S+\s+/(\s|$|etc|usr|var)", "broad_ownership_change"),
    (r"\bmount\b|\bumount\b|\blosetup\b", "filesystem_mount"),
    # --- обход защиты ---
    (r"--dangerously-skip-permissions|--bypass-permissions", "guard_bypass"),
    (r"\b(pytest|npm\s+test|jest)\b[^|;&]*(--no-\S*verify|--ignore=tests|-p\s+no:\S+)", "test_disable"),
    (r"\bSKIP_HOOKS?=|\bNO_VERIFY=|\bDISABLE_GUARD", "guard_bypass"),
    (r"\bchmod\b[^|;&]*\.claude/hooks", "hook_disable"),
    (r"\b(rm|mv|truncate)\b[^|;&]*\.claude/(hooks|settings)", "hook_disable"),
    # --- удалённое исполнение / обфускация ---
    (r"\b(curl|wget)\b[^|;&]*\|\s*(ba)?sh\b", "remote_code_execution"),
    (r"\bbase64\b[^|;&]*(-d|--decode)[^|;&]*\|\s*(ba)?sh\b", "obfuscated_execution"),
    (r"\beval\b\s+[\"'$]", "eval_dynamic"),
    (r"\b(ba)?sh\s+-c\s+[\"']?\$", "dynamic_shell"),
    (r"\bnc\b\s+-[a-z]*l|\bncat\b\s+-[a-z]*l|\bsocat\b", "network_listener"),
    # --- DNS / инфраструктура ---
    (r"\b(cloudflare|cf-cli|route53|dnscontrol)\b", "dns_mutation"),
    (r"\bnsupdate\b", "dns_mutation"),
    # --- деньги / внешние сервисы ---
    (r"\b(stripe|paddle|billing)\b[^|;&]*\b(create|subscribe|charge)\b", "spend"),
    # --- SEO-специфичные запреты ---
    (r"\bDELETE\b[^|;&]*\bFROM\b[^|;&]*\bcomments?\b", "mass_comment_delete"),
]

# Команды, которые всегда требуют approved wrapper.
WRAPPER_REQUIRED_PATTERNS: list[tuple[str, str]] = [
    (r"\b(kubectl|helm|terraform|ansible|pulumi)\b", "infra_tool"),
    (r"\bdocker\b\s+(run|exec|push|rm|rmi)\b", "container_mutation"),
    (r"\bssh\b\s+\S+@", "remote_shell"),
    (r"\brsync\b[^|;&]*::|\brsync\b[^|;&]*\S+@", "remote_sync"),
    (r"\bpsql\b|\bmysql\b|\bmongo(sh)?\b|\bredis-cli\b", "direct_db_access"),
]

# Разделители, по которым разбираем составную команду.
SEGMENT_SPLIT = re.compile(r"\s*(?:\|\||&&|;|\||\n)\s*")
SUBSTITUTION = re.compile(r"\$\([^)]*\)|`[^`]*`|<\([^)]*\)")


@dataclass
class Decision:
    permission: str
    reason: str
    rule: str = ""
    segments: list[str] = field(default_factory=list)

    def as_hook_output(self, tool_name: str) -> dict:
        return {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": self.permission,
                "permissionDecisionReason": f"[{self.rule or 'policy'}] {self.reason}",
            }
        }


def _norm(path: str, repo_root: str) -> str:
    """Нормализует путь относительно корня репозитория, разворачивая .. и ~."""
    p = os.path.expanduser(path)
    if not os.path.isabs(p):
        p = os.path.join(repo_root, p)
    p = os.path.normpath(p)
    try:
        rel = os.path.relpath(p, repo_root)
    except ValueError:
        return p
    return p if rel.startswith("..") else rel


def is_protected_path(path: str, repo_root: str) -> bool:
    rel = _norm(path, repo_root)
    if os.path.isabs(rel):
        return False
    rel = rel.replace(os.sep, "/")
    return any(rel == p.rstrip("/") or rel.startswith(p) for p in PROTECTED_PATH_PREFIXES)


def is_secret_path(path: str) -> bool:
    normalized = os.path.expanduser(path).replace(os.sep, "/")
    return any(re.search(pat, normalized) for pat in SECRET_PATH_PATTERNS)


def is_writable_path(path: str, repo_root: str) -> bool:
    rel = _norm(path, repo_root)
    if not os.path.isabs(rel):
        return True  # внутри worktree
    return any(rel.startswith(pref) for pref in WRITABLE_EXTRA_PREFIXES)


def is_disposable_path(path: str, repo_root: str) -> bool:
    rel = _norm(path, repo_root).replace(os.sep, "/")
    return any(rel.startswith(p) or f"/{p}" in f"/{rel}" for p in DISPOSABLE_PATH_PREFIXES)


def split_segments(command: str) -> list[str]:
    """Разбивает составную команду. Подстановки вытаскиваются как отдельные сегменты."""
    segments: list[str] = []
    inner = SUBSTITUTION.findall(command)
    for sub in inner:
        body = sub[2:-1] if sub.startswith("$(") else sub.strip("`")
        if sub.startswith("<("):
            body = sub[2:-1]
        segments.extend(split_segments(body))
    stripped = SUBSTITUTION.sub(" __SUBST__ ", command)
    for part in SEGMENT_SPLIT.split(stripped):
        part = part.strip()
        if part:
            segments.append(part)
    return segments


def _strip_env_prefix(tokens: list[str]) -> list[str]:
    """Убирает `env` и присваивания VAR=value перед именем бинаря."""
    out = list(tokens)
    while out:
        t = out[0]
        if t == "env":
            out = out[1:]
            continue
        if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*=.*", t):
            out = out[1:]
            continue
        break
    return out


def _binary_of(segment: str) -> tuple[str, list[str]]:
    try:
        tokens = shlex.split(segment)
    except ValueError:
        return "__UNPARSEABLE__", []
    tokens = _strip_env_prefix(tokens)
    if not tokens:
        return "", []
    return os.path.basename(tokens[0]), tokens[1:]


def _nested_shell_payload(binary: str, args: list[str]) -> str | None:
    """Возвращает тело `sh -c "..."` / `xargs cmd` / `find -exec cmd` для рекурсивной проверки."""
    if binary in {"sh", "bash", "zsh", "dash"}:
        for i, a in enumerate(args):
            if a == "-c" and i + 1 < len(args):
                return args[i + 1]
    if binary == "xargs":
        rest = [a for a in args if not a.startswith("-")]
        return " ".join(rest) if rest else None
    if binary in {"find", "fd"}:
        for flag in ("-exec", "-execdir", "-delete", "-x"):
            if flag in args:
                if flag == "-delete":
                    return "rm -rf __find_delete__"
                idx = args.index(flag)
                return " ".join(a for a in args[idx + 1:] if a not in {";", "+", "\\;"})
    if binary in {"timeout", "nice", "nohup", "stdbuf", "setsid"}:
        rest = [a for a in args if not a.startswith("-") and not a.isdigit()]
        return " ".join(rest) if rest else None
    return None


def check_command(command: str, repo_root: str, depth: int = 0) -> Decision:
    if depth > 4:
        return Decision(DENY, "Слишком глубокая вложенность команд.", "nesting_depth")

    full = command.strip()
    if not full:
        return Decision(DENY, "Пустая команда.", "empty")

    # 1. Deny-паттерны по всей строке (ловят обфускацию через кавычки/склейку).
    for pattern, rule in DENY_PATTERNS:
        if re.search(pattern, full, re.IGNORECASE):
            return Decision(DENY, f"Команда попадает под безусловный запрет: {rule}.", rule)

    segments = split_segments(full)
    for seg in segments:
        if seg == "__SUBST__":
            continue
        binary, args = _binary_of(seg)

        if binary == "__UNPARSEABLE__":
            return Decision(DENY, "Команду не удалось разобрать — fail-closed.", "unparseable", segments)
        if not binary:
            continue

        # Повторная проверка по РАЗКАВЫЧЕННОЙ форме: `e''cho`, `s"u"do`, `rm -r"f"`
        # проходят сырой regex, но после shlex превращаются в обычную команду.
        dequoted = " ".join([binary] + args)
        if dequoted != seg:
            for pattern, rule in DENY_PATTERNS:
                if re.search(pattern, dequoted, re.IGNORECASE):
                    return Decision(
                        DENY,
                        f"Команда после снятия кавычек попадает под запрет: {rule}.",
                        f"dequoted:{rule}", segments)

        # Вложенные оболочки / exec-обёртки проверяем рекурсивно.
        payload = _nested_shell_payload(binary, args)
        if payload:
            nested = check_command(payload, repo_root, depth + 1)
            if nested.permission != ALLOW:
                return Decision(nested.permission, f"Вложенная команда ({binary}): {nested.reason}", nested.rule, segments)

        # Утверждённая обёртка — единственный путь к Tier2/Tier3 операциям.
        if seg.startswith(APPROVED_WRAPPER_DIR) or f"/{APPROVED_WRAPPER_DIR}" in seg.split()[0]:
            continue

        for pattern, rule in WRAPPER_REQUIRED_PATTERNS:
            if re.search(pattern, seg, re.IGNORECASE):
                return Decision(
                    DENY,
                    f"Операция '{rule}' допустима только через {APPROVED_WRAPPER_DIR}.",
                    f"wrapper_required:{rule}",
                    segments,
                )

        # Пути: чтение секретов и запись в protected.
        for token in args:
            if token.startswith("-"):
                continue
            if is_secret_path(token):
                return Decision(DENY, f"Обращение к secret-пути: {token}", "secret_path", segments)
            if binary in SAFE_WRITE_BINARIES or binary in {"tee", "truncate"}:
                if is_protected_path(token, repo_root):
                    return Decision(DENY, f"Запись в protected path: {token}", "protected_path", segments)
                if not is_writable_path(token, repo_root):
                    return Decision(DENY, f"Запись вне worktree и утверждённых путей: {token}", "path_outside_worktree", segments)

        # Перенаправление вывода в защищённые/внешние пути.
        for m in re.finditer(r">>?\s*(\S+)", seg):
            target = m.group(1)
            if is_protected_path(target, repo_root):
                return Decision(DENY, f"Перенаправление в protected path: {target}", "protected_path", segments)
            if is_secret_path(target):
                return Decision(DENY, f"Перенаправление в secret path: {target}", "secret_path", segments)
            if not is_writable_path(target, repo_root):
                return Decision(DENY, f"Перенаправление вне worktree: {target}", "path_outside_worktree", segments)

        if binary == "rm":
            for token in args:
                if token.startswith("-"):
                    continue
                if not is_disposable_path(token, repo_root):
                    return Decision(DENY, f"Удаление вне disposable path: {token}", "delete_outside_disposable", segments)

        if binary == "git":
            sub = next((a for a in args if not a.startswith("-")), "")
            if sub == "push":
                if not any(a.startswith("claude/") or a.startswith("seo/") for a in args):
                    return Decision(
                        DENY,
                        "push разрешён только в собственные ветки claude/* и seo/*.",
                        "push_branch_scope",
                        segments,
                    )
            elif sub not in GIT_READ_SUBCOMMANDS | GIT_WRITE_SUBCOMMANDS:
                return Decision(DENY, f"Неизвестная git-подкоманда: {sub}", "git_unknown", segments)
            continue

        if binary in READ_ONLY_BINARIES | SAFE_WRITE_BINARIES | BUILD_TEST_BINARIES:
            continue
        if binary in {"seo", "cd", "export", "source", "."}:
            continue

        return Decision(
            DENY,
            f"Бинарь '{binary}' не входит в allow-list UNATTENDED_SAFE (fail-closed).",
            "binary_not_allowlisted",
            segments,
        )

    return Decision(ALLOW, "Команда в пределах UNATTENDED_SAFE.", "allow", segments)


def check_file_write(path: str, repo_root: str) -> Decision:
    if is_secret_path(path):
        return Decision(DENY, f"Запись в secret path запрещена: {path}", "secret_path")
    if is_protected_path(path, repo_root):
        return Decision(DENY, f"Protected kernel не изменяется SEO-контуром: {path}", "protected_path")
    if not is_writable_path(path, repo_root):
        return Decision(DENY, f"Запись вне worktree и утверждённых путей: {path}", "path_outside_worktree")
    return Decision(ALLOW, "Запись внутри собственного worktree.", "allow")


def check_file_read(path: str, repo_root: str) -> Decision:
    if is_secret_path(path):
        return Decision(DENY, f"Чтение secret path запрещено: {path}", "secret_path")
    return Decision(ALLOW, "Чтение несекретного файла.", "allow")


def evaluate(tool_name: str, tool_input: dict, repo_root: str) -> Decision:
    """Главная точка входа. Неизвестный инструмент => DENY (fail-closed)."""
    if tool_name == "Bash":
        cmd = tool_input.get("command")
        if not isinstance(cmd, str):
            return Decision(DENY, "Отсутствует поле command.", "malformed_input")
        return check_command(cmd, repo_root)

    if tool_name in {"Write", "Edit", "NotebookEdit"}:
        path = tool_input.get("file_path") or tool_input.get("notebook_path")
        if not isinstance(path, str):
            return Decision(DENY, "Отсутствует file_path.", "malformed_input")
        return check_file_write(path, repo_root)

    if tool_name == "Read":
        path = tool_input.get("file_path")
        if not isinstance(path, str):
            return Decision(DENY, "Отсутствует file_path.", "malformed_input")
        return check_file_read(path, repo_root)

    if tool_name in {"Glob", "Grep", "TodoWrite", "Task", "ListAgents"}:
        return Decision(ALLOW, "Read-only/организационный инструмент.", "allow")

    if tool_name in {"WebFetch", "WebSearch"}:
        return Decision(ALLOW, "Сетевое чтение разрешено; исполнение загруженного кода запрещено отдельно.", "allow")

    return Decision(DENY, f"Инструмент '{tool_name}' не в allow-list — fail-closed.", "tool_not_allowlisted")
