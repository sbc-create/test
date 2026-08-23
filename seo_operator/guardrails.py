"""Classification of actions into allowed, requires-approval, and blocked.

This is the safety core. It is deliberately a pure function over a described
action, with no side effects, so it can be exhaustively tested and reused by
both the Python pipeline and the PreToolUse shell hook.

Design rule: the classifier **fails closed**. An action that matches no allow
rule is never implicitly permitted; it falls through to BLOCKED or APPROVAL
depending on whether it touches a protected surface.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum


class Decision(str, Enum):
    ALLOW = "allow"
    REQUIRE_APPROVAL = "require_approval"
    BLOCK = "block"


@dataclass(frozen=True)
class Verdict:
    decision: Decision
    rule: str
    reason: str

    @property
    def allowed(self) -> bool:
        return self.decision is Decision.ALLOW


# --------------------------------------------------------------------------
# Always blocked. These are never permitted, in any mode, with any approval
# flag set by the operator itself. Only a human acting outside the operator
# can perform them.
# --------------------------------------------------------------------------
BLOCKED_PATTERNS: list[tuple[str, str]] = [
    (r"\bDROP\s+(TABLE|DATABASE|SCHEMA)\b", "destructive SQL: DROP"),
    (r"\bTRUNCATE\b", "destructive SQL: TRUNCATE"),
    (r"\bDELETE\s+FROM\b(?!.*\bWHERE\b)", "unbounded DELETE without WHERE"),
    (r"\bALTER\s+TABLE\b.*\bDROP\s+COLUMN\b", "destructive migration"),
    (r"git\s+push\b.*(--force\b|-f\b|\+refs)", "force push"),
    (r"git\s+push\b.*:\s*refs/heads/", "remote branch deletion via refspec"),
    (r"git\s+push\b[^\n]*\s--delete\b|git\s+push\b[^\n]*\s-d\b", "remote branch deletion"),
    (r"git\s+push\b[^\n]*\s:[A-Za-z0-9._/-]+", "remote branch deletion via refspec"),
    (r"git\s+push\b[^|;]*\b(main|master)\b", "push directly to main/master"),
    (r"\brm\s+-rf\s+/(?!tmp|home/user/test/var)", "recursive delete outside scratch"),
    (r"\b(dropdb|dropuser)\b", "database/user deletion"),
    (r"aws\s+s3\s+rb\b", "bucket deletion"),
    (r"aws\s+s3\s+rm\b.*--recursive", "recursive object deletion"),
    (r"\b(backup|backups|snapshot)\b.*\b(rm|delete|destroy|purge)\b", "backup deletion"),
    (r"\b(rm|delete|destroy|purge)\b.*\b(backup|backups)\b", "backup deletion"),
    (r"\bterraform\s+destroy\b", "infrastructure destruction"),
    (r"\bdocker\s+(rm|rmi)\s+-f\b", "forced container/image removal"),
    # Secret exfiltration and credential widening.
    # `env VAR=1 cmd` sets one variable for one command; it prints nothing.
    # Blocking it blocked ordinary work (`env FACTORY_CLOSED_WORLD=0 pytest`)
    # without closing any exfiltration path, so only the dump itself is blocked.
    (r"(?:^|[;&|]\s*)printenv\b", "environment dump"),
    (r"(?:^|[;&|]\s*)env\s*(?:\||>|;|$)", "environment dump"),
    (
        r"\becho\s+\$\{?(AWS_SECRET|GITHUB_TOKEN|GH_TOKEN|.*_SECRET|.*_TOKEN|.*API_KEY)",
        "secret value output",
    ),
    (r"\bcat\b.*(\.env|credentials|id_rsa|\.pem|\.p12|token)", "credential file read"),
    (r"\b(chmod|chown)\b.*\b(0?777)\b", "permission widening"),
    (r"\bgcloud\s+.*add-iam-policy-binding\b", "credential/IAM widening"),
    (r"\baws\s+iam\s+(create|attach|put)", "credential/IAM widening"),
    # Disabling the safety machinery itself.
    (r"--no-verify\b", "bypassing git hooks"),
    (r"--dangerously-skip-permissions\b", "disabling permission checks"),
    (r"\bbypassPermissions\b", "disabling permission checks"),
    (r"(rm|mv|chmod\s+-x)\s+.*\.claude/hooks/", "disabling hooks"),
    (r"\bpytest\b.*(--no-cov\b.*)?\b(-p\s+no:|--co\b.*--exitfirst)", "disabling test plugins"),
    (r"\b(skip|xfail|disable)\b.*\btests?\b.*\bto\s+(pass|green)\b", "skipping tests to go green"),
    # DNS outside the approved manifest is handled separately (needs manifest
    # context) but any registrar-level mutation is unconditionally blocked.
    (r"\b(domain|domains)\b.*\b(delete|transfer|release)\b", "domain deletion/transfer"),
    (r"\bnameservers?\b.*\bset\b", "nameserver mutation"),
]

# --------------------------------------------------------------------------
# Safe by default under UNATTENDED_SAFE. Read-only inspection, local analysis,
# and work confined to the operator's own branch/worktree.
# --------------------------------------------------------------------------
ALLOWED_PATTERNS: list[tuple[str, str]] = [
    (
        r"^git\s+(status|log|diff|show|branch|rev-parse|rev-list|ls-files|ls-remote"
        r"|fetch|blame|describe|shortlog|count-objects|cat-file|for-each-ref|bundle"
        r"|ls-tree|merge-base|name-rev|grep|whatchanged)\b",
        "read-only git",
    ),
    (
        # `cherry-pick` относится к тому же классу, что merge и rebase: локальный
        # перенос коммитов в собственную ветку. Без него перенос работы между
        # ветками останавливался на середине — сама операция проходила, а
        # `--continue`, `--abort` и `--quit` отклонялись, и репозиторий оставался
        # в незавершённом состоянии. Разрушительные формы (`push --force`,
        # `reset --hard`, `--no-verify`) по-прежнему запрещены отдельными
        # правилами выше и до этого списка не доходят.
        r"^git\s+(add|commit|checkout|switch|restore|stash|merge|rebase|tag"
        r"|cherry-pick|revert)\b",
        "git work in own branch",
    ),
    # Unstaging is ordinary; `reset --hard` discards uncommitted work and is not.
    (r"^git\s+reset\b(?!.*--hard)", "unstage files"),
    # Pushing the operator's own branch is ordinary work. Force pushes are
    # blocked above, and pushes naming main/master never reach here.
    (r"^git\s+push\b(?!.*--force)(?!.*\s-f\b).*\bclaude/", "push to own branch"),
    (
        r"^(ls|cat|head|tail|wc|find|grep|rg|sed\s+-n|awk|sort|uniq|diff|stat|file|tree|jq)\b",
        "read-only inspection",
    ),
    (r"^(python3?|\.venv/bin/python3?)\b", "local python"),
    (r"^(pytest|\.venv/bin/pytest|.*-m\s+pytest)\b", "tests"),
    (r"^(ruff|\.venv/bin/ruff)\b", "lint"),
    (r"^(npm|node|npx)\s+(run\s+)?(test|lint|build|ci)\b", "build/test"),
    (r"^\./scripts/(verify|record-evidence|build-bundle)\.sh\b", "repository checks"),
    (r"^\./bin/seo-operator\b", "operator CLI"),
    (r"^(mkdir|touch|cp|mv)\b(?!.*\s/(etc|usr|bin|boot|var/lib)\b)", "local file work"),
    (r"^cd\s+(?!/(etc|usr|bin|boot|var/lib))\S+$", "directory navigation"),
    (r"^(echo|printf)\b(?!.*\$)", "literal output"),
    (r"^(true|:)$", "no-op"),
    (r"^curl\s+(-[a-zA-Z]+\s+)*(-X\s+(GET|HEAD)\s+)?https?://", "HTTP read (crawl/render)"),
    (r"^(wc|md5sum|sha256sum)\b", "local hashing"),
]

# --------------------------------------------------------------------------
# Production mutation surfaces. Allowed only with an explicit, per-action
# authorization token — never by the operator's own default.
# --------------------------------------------------------------------------
PRODUCTION_PATTERNS: list[tuple[str, str]] = [
    (r"\bproduction\b|\bprod\b", "production surface"),
    (r"^git\s+push\b", "push to remote"),
    (r"\b(kubectl|helm)\s+(apply|delete|rollout)\b", "cluster mutation"),
    (r"\bterraform\s+apply\b", "infrastructure mutation"),
    (r"\bpublish\b|\bdeploy\b", "deployment"),
    (r"\bPOST\b|\bPUT\b|\bDELETE\b|\bPATCH\b", "write HTTP method"),
]


# Commands that merely *write* their heredoc body to a file. Their payload is
# data, not instructions, so classifying it as a command produces false
# positives: a test fixture or a document quoting a dangerous string would be
# refused. Anything that feeds a heredoc to an interpreter is NOT in this list.
DATA_SINK_RE = re.compile(
    r"^\s*(?:"
    r"(?:cat|tee)\b"
    # `git commit -F -` and friends read a *message* from the heredoc. Treating
    # it as a command means a commit message that merely names a protected
    # action cannot be written.
    r"|git\s+(?:commit|tag|notes)\b[^|]*(?:-F|--file)\b"
    r")(?![^|]*\|\s*(?:ba)?sh\b)",
    re.IGNORECASE,
)

HEREDOC_RE = re.compile(r"<<-?\s*(['\"]?)([A-Za-z_][A-Za-z0-9_]*)\1")


def strip_data_heredocs(command: str) -> str:
    """Remove heredoc bodies that are written to a file rather than executed.

    Without this, writing a test that *mentions* a destructive statement is
    itself treated as issuing one. The body is only stripped when the receiving
    command is a plain file sink; a heredoc piped into a shell or an
    interpreter keeps its body and stays subject to every rule.
    """
    lines = command.split("\n")
    out: list[str] = []
    skipping_until: str | None = None

    for line in lines:
        if skipping_until is not None:
            if line.strip() == skipping_until:
                skipping_until = None
            continue

        match = HEREDOC_RE.search(line)
        # The sink is the command immediately before the heredoc marker, which
        # is rarely at the start of the line: it usually sits after `&&` in a
        # chain. Checking only the line start missed every real invocation.
        sink = ""
        if match:
            before = line[: match.start()]
            parts = split_segments(before)
            sink = parts[-1] if parts else before
        if match and DATA_SINK_RE.match(sink.strip()):
            skipping_until = match.group(2)
            out.append(HEREDOC_RE.sub("", line))
            continue

        out.append(line)

    return "\n".join(out)


@dataclass
class ActionContext:
    """Everything the classifier needs to judge an action."""

    command: str
    environment: str = "sandbox"  # sandbox | staging | production
    production_authorization: str | None = None
    site_id: str | None = None
    approved_domains: frozenset[str] = field(default_factory=frozenset)


def _match(patterns: list[tuple[str, str]], text: str) -> tuple[str, str] | None:
    for pattern, label in patterns:
        if re.search(pattern, text, flags=re.IGNORECASE):
            return pattern, label
    return None


# Shell operators that separate independently executed commands. Splitting on
# them matters: classifying the whole line lets a safe leading command vouch for
# whatever is chained after it, so `git status && unknown-binary` would pass on
# the strength of `git status` alone.
SEVERITY = {Decision.ALLOW: 0, Decision.REQUIRE_APPROVAL: 1, Decision.BLOCK: 2}

# `|&` — сокращение для `2>&1 |`, перевод строки разделяет команды так же,
# как `;`. Без них хвост составной команды классифицировался вместе с
# головой, и безопасное начало ручалось за небезопасное продолжение.
_OPERATORS = ("&&", "||", ";", "|&", "|", "\n")


def split_segments(command: str) -> list[str]:
    """Split a command line into independently executed segments.

    Operators inside quotes do not split, so a grep pattern such as
    ``"a\\|b"`` stays one segment. An unbalanced quote is treated as quoting to
    the end of the line, which keeps the tail inside one segment and therefore
    still subject to every rule.
    """
    segments: list[str] = []
    current: list[str] = []
    quote: str | None = None
    i = 0

    while i < len(command):
        char = command[i]

        if quote:
            current.append(char)
            if char == quote and (i == 0 or command[i - 1] != "\\"):
                quote = None
            i += 1
            continue

        if char in ("'", '"'):
            quote = char
            current.append(char)
            i += 1
            continue

        matched = next((op for op in _OPERATORS if command.startswith(op, i)), None)
        if matched:
            segments.append("".join(current))
            current = []
            i += len(matched)
            continue

        current.append(char)
        i += 1

    segments.append("".join(current))
    return [seg.strip() for seg in segments if seg.strip()]


def _classify_segment(segment: str, ctx: ActionContext) -> Verdict:
    hit = _match(BLOCKED_PATTERNS, segment)
    if hit:
        return Verdict(Decision.BLOCK, hit[0], f"protected action: {hit[1]}")

    prod = _match(PRODUCTION_PATTERNS, segment)
    if prod and ctx.environment == "production":
        if not ctx.production_authorization:
            return Verdict(
                Decision.REQUIRE_APPROVAL,
                prod[0],
                f"production mutation without authorization: {prod[1]}",
            )
        return Verdict(Decision.ALLOW, prod[0], f"authorized production action: {prod[1]}")

    hit = _match(ALLOWED_PATTERNS, segment)
    if hit:
        return Verdict(Decision.ALLOW, hit[0], f"safe: {hit[1]}")

    return Verdict(
        Decision.BLOCK,
        "default-deny",
        f"no allow rule matched for segment {segment.split()[0]!r}; "
        "unknown actions are denied by default",
    )


def classify(ctx: ActionContext) -> Verdict:
    """Classify one action. Order matters: blocks are checked first and win."""
    command = ctx.command.strip()

    if not command:
        return Verdict(Decision.BLOCK, "empty", "empty command")

    # Judge the instructions, not the data they write.
    command = strip_data_heredocs(command).strip()
    if not command:
        return Verdict(Decision.BLOCK, "empty", "empty command")

    # Every segment must stand on its own; the most restrictive verdict wins.
    verdicts = [_classify_segment(seg, ctx) for seg in split_segments(command)]
    if not verdicts:
        return Verdict(Decision.BLOCK, "empty", "empty command")
    return max(verdicts, key=lambda v: SEVERITY[v.decision])


def check_dns(hostname: str, approved: frozenset[str]) -> Verdict:
    """DNS work is confined to hostnames named in an approved site manifest."""
    host = hostname.strip().lower().rstrip(".")
    if not host:
        return Verdict(Decision.BLOCK, "dns-empty", "empty hostname")
    for domain in approved:
        d = domain.lower()
        if host == d or host.endswith("." + d):
            return Verdict(Decision.ALLOW, "dns-approved", f"{host} within approved {d}")
    return Verdict(Decision.BLOCK, "dns-unapproved", f"{host} is not in the approved manifest")
