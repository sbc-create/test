"""Мост между PreToolUse-хуком Claude Code и правилами guardrails.

Читает payload хука со stdin, пишет решение о разрешении на stdout. Реализация
на Python нужна затем, чтобы хук и конвейер пользовались одним набором правил.

**Контракт этого модуля: только `allow` или `deny`.** Профиль UNATTENDED_SAFE
работает без человека, поэтому третьего исхода нет: `ask` останавливал бы
автоматический цикл и на неотвечающем терминале превращался бы в зависание, а
не в защиту. Всё, что раньше уходило на подтверждение, теперь запрещается и
записывается в журнал отказов (:func:`record_denial`), чтобы отчёт мог назвать
каждое несостоявшееся действие и его причину.

Запреты при этом не ослаблены: force push, удаление веток, баз, бэкапов,
DNS-зон и репозиториев, обход разрешений и правка самой защитной машинерии
по-прежнему не проходят — они просто отвечают `deny` сразу, а не спрашивают.
"""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

from seo_operator import unattended
from seo_operator.guardrails import ActionContext, Decision, classify

PROFILE = unattended.PROFILE

#: Журнал отказов. Ни одно действие не пропадает молча: раз человека не
#: спрашивают, отчёт обязан уметь показать, что именно было запрещено и почему.
#: Путь переопределяется для тестов; var/ не попадает в git.
DENIAL_LOG_ENV = "FACTORY_DENIAL_LOG"
DEFAULT_DENIAL_LOG = "var/log/unattended-denials.jsonl"


def _repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def denial_log_path() -> Path:
    configured = os.environ.get(DENIAL_LOG_ENV)
    return Path(configured) if configured else _repo_root() / DEFAULT_DENIAL_LOG


def record_denial(tool: str, reason: str, command: str = "") -> None:
    """Дописывает отказ в журнал. Сбой записи не превращает deny в allow."""
    try:
        from factory.redaction import redact
    except Exception:  # pragma: no cover — фабрика необязательна для хука

        def redact(text: str) -> str:
            return text

    entry = {
        "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "profile": PROFILE,
        "tool": tool,
        "decision": "deny",
        "reason": redact(reason)[:2000],
        # Команда проходит редакцию и обрезается: журнал отказов не должен сам
        # стать местом, где оседает секрет.
        "command": redact(command)[:2000],
    }
    try:
        path = denial_log_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except OSError:
        pass


# Инструменты, которые только читают. Безопасны независимо от аргументов.
READ_ONLY_TOOLS = frozenset({"Read", "Glob", "Grep", "NotebookRead", "TodoWrite", "Task"})

# Инструменты самой оболочки: они не касаются ни файловой системы, ни сети, ни
# внешних сервисов — планирование, поиск описаний инструментов, список агентов,
# ведение задач. В неинтерактивном профиле «нет правила» означает отказ, поэтому
# такой список обязан существовать явно: иначе штатная работа останавливается на
# инструменте, который ничего не делает.
HARNESS_LOCAL_TOOLS = frozenset(
    {
        "ToolSearch",
        "Skill",
        "ListAgents",
        "SendMessage",
        "Monitor",
        "EnterPlanMode",
        "ExitPlanMode",
        "EnterWorktree",
        "ExitWorktree",
        "ScheduleWakeup",
        "ReportFindings",
        "TaskCreate",
        "TaskGet",
        "TaskList",
        "TaskUpdate",
        "TaskOutput",
        "TaskStop",
        "CronList",
    }
)

#: Инструменты, которые в неинтерактивном профиле не имеют смысла: они
#: существуют ровно затем, чтобы спросить человека. Отказ здесь — не потеря
#: возможности, а следствие выбранного режима.
INTERACTIVE_TOOLS = frozenset({"AskUserQuestion"})

#: Чтение внешней документации. Разрешается только к хостам, внесённым в
#: `inventory/network-allowlist.yaml` или `inventory/reference-sources.yaml`:
#: в CLOSED_WORLD источник приходит из задания владельца, а не из инициативы
#: агента. Поиск по интернету хостом не ограничивается и потому запрещён.
WEB_READ_TOOLS = frozenset({"WebFetch"})
WEB_SEARCH_TOOLS = frozenset({"WebSearch"})

# Tools that write inside the working tree. Safe under UNATTENDED_SAFE because
# the session works in its own branch and cannot push without authorization.
BRANCH_LOCAL_WRITE_TOOLS = frozenset({"Write", "Edit", "MultiEdit", "NotebookEdit"})

# GitHub через штатные инструменты. Чтение и работа с pull request — обычная
# часть цикла; всё, что удаляет или переносит владение, остаётся за человеком.
GITHUB_READ_PREFIXES = (
    "mcp__github__get_",
    "mcp__github__list_",
    "mcp__github__search_",
    "mcp__github__issue_read",
    "mcp__github__pull_request_read",
    "mcp__github__actions_get",
    "mcp__github__actions_list",
)
GITHUB_WRITE_TOOLS = frozenset(
    {
        "mcp__github__create_pull_request",
        "mcp__github__update_pull_request",
        "mcp__github__create_branch",
        "mcp__github__add_comment_to_pending_review",
        "mcp__github__pull_request_review_write",
        "mcp__github__add_reply_to_pull_request_comment",
        "mcp__github__resolve_review_thread",
        "mcp__github__unresolve_review_thread",
        "mcp__github__update_pull_request_branch",
        "mcp__github__subscribe_pr_activity",
        "mcp__github__unsubscribe_pr_activity",
    }
)
#: Необратимое или выходящее за репозиторий — только через человека.
GITHUB_BLOCKED_TOOLS = frozenset(
    {
        "mcp__github__delete_file",
        "mcp__github__create_repository",
        "mcp__github__fork_repository",
        "mcp__github__run_secret_scanning",
    }
)

#: Раньше здесь было три исхода. `REQUIRE_APPROVAL` больше не отображается в
#: `ask`: неинтерактивный профиль обязан ответить сам, и безопасный ответ на
#: «нужно решение человека» — отказ, а не разрешение.
DECISION_MAP = {
    Decision.ALLOW: "allow",
    Decision.REQUIRE_APPROVAL: "deny",
    Decision.BLOCK: "deny",
}


def decide(payload: dict) -> dict:
    tool = payload.get("tool_name", "")
    tool_input = payload.get("tool_input", {}) or {}

    if tool in READ_ONLY_TOOLS:
        return _out("allow", f"{tool}: read-only инструмент")

    if tool in HARNESS_LOCAL_TOOLS:
        return _out("allow", f"{tool}: инструмент оболочки, среды не касается")

    if tool in INTERACTIVE_TOOLS:
        return _deny(tool, f"{tool}: профиль {PROFILE} работает без подтверждений человека")

    if tool in WEB_SEARCH_TOOLS:
        return _deny(
            tool,
            f"{tool}: поиск по интернету не ограничен хостом — в CLOSED_WORLD запрещён",
        )

    if tool in WEB_READ_TOOLS:
        url = str(tool_input.get("url", ""))
        host = _host_of(url)
        approved = unattended.network_hosts()
        if host and host in approved:
            return _out("allow", f"{tool}: {host} внесён в разрешённые источники")
        return _deny(tool, f"{tool}: хост «{host or 'не определён'}» не внесён в inventory", url)

    if tool in BRANCH_LOCAL_WRITE_TOOLS:
        path = str(tool_input.get("file_path", ""))
        if "/.claude/hooks/" in path or path.endswith("settings.json"):
            # Правка защитной машинерии тем же агентом, которого она ограничивает,
            # снимает защиту её собственным механизмом. Это запрет, а не вопрос:
            # изменения в hooks и settings вносит оператор вручную.
            return _deny(tool, "изменение самой защитной машинерии не выполняется агентом", path)
        return _out("allow", f"{tool}: запись в пределах рабочей ветки")

    if tool in GITHUB_BLOCKED_TOOLS:
        return _deny(tool, f"{tool}: необратимая операция над репозиторием")
    if tool.startswith(GITHUB_READ_PREFIXES):
        return _out("allow", f"{tool}: чтение данных GitHub")
    if tool in GITHUB_WRITE_TOOLS:
        return _out("allow", f"{tool}: работа с pull request в собственной ветке")

    if tool == "Bash":
        command = str(tool_input.get("command", ""))
        environment = payload.get("environment", "sandbox")
        verdict = classify(ActionContext(command=command, environment=environment))

        # Стоп-сигнал профиля сильнее разрешающего правила: `python3 -m factory
        # deploy … --environment production` подходит под «локальный python», но
        # необратимую операцию над production человек подтверждает сам.
        stop = unattended.mandatory_confirmation(command)

        # Явный запрет и требование подтверждения окончательны: профиль
        # UNATTENDED_SAFE не может их отменить, он работает только с командами,
        # которые не подошли ни под одно разрешающее правило (`default-deny`).
        # Раньше такая команда уходила на подтверждение целиком — включая
        # `PYTHONPATH=… python`, `timeout 300 git push origin claude/…` и любой
        # составной вызов, у которого обёртка сдвигала якорь `^`.
        if verdict.decision is Decision.BLOCK and verdict.rule != "default-deny":
            return _deny(tool, verdict.reason, command)
        if verdict.decision is Decision.REQUIRE_APPROVAL:
            return _deny(tool, verdict.reason, command)
        if verdict.decision is Decision.ALLOW:
            if stop:
                # `mandatory_confirmation` возвращает пустую строку, когда все
                # условия production фактически выполнены, поэтому штатный
                # авторизованный выкат сюда не попадает. Попал — значит условие
                # не выполнено, и оно названо в тексте отказа.
                return _deny(tool, f"необратимая операция без выполненных условий: {stop}", command)
            return _out("allow", verdict.reason)

        profile = unattended.evaluate(command)
        if profile.decision == unattended.ALLOW:
            return _out("allow", f"{unattended.PROFILE}: {profile.reason}")
        return _deny(tool, f"{verdict.reason}; профиль: {profile.reason}", command)

    # Неизвестный инструмент: fail closed. Раньше решение уходило человеку;
    # в неинтерактивном профиле «нет правила» означает «нет разрешения».
    return _deny(
        tool,
        f"неизвестный инструмент {tool!r}: правило не описано, действует default-deny",
    )


def _host_of(url: str) -> str:
    from urllib.parse import urlsplit

    try:
        return (urlsplit(url).hostname or "").lower()
    except ValueError:
        return ""


def _deny(tool: str, reason: str, command: str = "") -> dict:
    """Отказ с записью в журнал. Единственный способ ответить «нет» в этом модуле."""
    record_denial(tool, reason, command)
    return _out("deny", reason)


def _out(decision: str, reason: str) -> dict:
    return {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": decision,
            "permissionDecisionReason": reason,
        }
    }


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        print(
            json.dumps(
                _deny("unknown", "не удалось разобрать payload хука — fail closed"),
                ensure_ascii=False,
            )
        )
        return 0
    print(json.dumps(decide(payload), ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
