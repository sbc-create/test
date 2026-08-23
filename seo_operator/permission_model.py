"""Модель разрешений Claude Code: правила настроек плюс решения хуков.

Нужна для проверок. Матрица разрешений обязана отвечать на вопрос «остановится
ли работа?», а он решается не одним слоем: правило `deny` в `.claude/settings.json`
сильнее любого разрешения хука, а хук сильнее списков `ask` и `allow`. Проверять
только хук — значит доказывать половину утверждения.

Порядок разрешения (документация Claude Code, раздел permissions):

1. `deny` в настройках — абсолютный запрет, хук его не отменяет;
2. решение PreToolUse-хука: `deny`, затем `ask`, затем `allow`;
3. `ask` в настройках;
4. `allow` в настройках;
5. иначе — обычный запрос подтверждения.
"""

from __future__ import annotations

import fnmatch
import json
import os
import re
from dataclasses import dataclass
from pathlib import Path

DENY = "deny"
ASK = "ask"
ALLOW = "allow"
PROMPT = "ask"  # отсутствие правила означает подтверждение, а не разрешение

RULE_RE = re.compile(r"^(?P<tool>[A-Za-z_][A-Za-z0-9_]*)(?:\((?P<arg>.*)\))?$", re.S)


@dataclass(frozen=True)
class Rule:
    tool: str
    pattern: str | None

    def matches(self, tool: str, argument: str) -> bool:
        if self.tool != tool:
            return False
        if self.pattern is None:
            return True
        if tool == "Bash":
            return _bash_matches(self.pattern, argument)
        return _path_matches(self.pattern, argument)


def _bash_matches(pattern: str, command: str) -> bool:
    """Правило для Bash сравнивает префикс команды.

    Формы `cmd:*` и `cmd *` означают «команда начинается с cmd»; форма без
    подстановки — точное совпадение.
    """
    command = command.strip()
    if pattern.endswith(":*"):
        return command.startswith(pattern[:-2].strip())
    if "*" in pattern:
        return fnmatch.fnmatchcase(command, pattern) or command.startswith(pattern.split("*", 1)[0])
    return command == pattern


def _path_matches(pattern: str, path: str) -> bool:
    candidate = path.replace("\\", "/")
    pattern = pattern.replace("\\", "/")
    if pattern.startswith("~/"):
        pattern = os.path.expanduser(pattern)
    if pattern.startswith("./"):
        pattern = pattern[2:]
    for variant in {candidate, candidate.lstrip("./"), os.path.basename(candidate)}:
        if fnmatch.fnmatchcase(variant, pattern):
            return True
        if pattern.startswith("**/") and fnmatch.fnmatchcase(variant, pattern[3:]):
            return True
        if pattern.endswith("/**") and variant.startswith(pattern[:-3]):
            return True
        if fnmatch.fnmatchcase(variant, "*/" + pattern):
            return True
    return False


def load_rules(settings_path: Path) -> dict[str, list[Rule]]:
    settings = json.loads(Path(settings_path).read_text(encoding="utf-8"))
    permissions = settings.get("permissions", {})
    groups: dict[str, list[Rule]] = {}
    for group in (DENY, ASK, ALLOW):
        groups[group] = [_parse(rule) for rule in permissions.get(group, [])]
    return groups


def _parse(rule: str) -> Rule:
    match = RULE_RE.match(rule.strip())
    if not match:
        return Rule(tool=rule.strip(), pattern=None)
    return Rule(tool=match.group("tool"), pattern=match.group("arg"))


def settings_decision(groups: dict[str, list[Rule]], tool: str, argument: str) -> str | None:
    for group in (DENY, ASK, ALLOW):
        if any(rule.matches(tool, argument) for rule in groups.get(group, [])):
            return group
    return None


def resolve(settings: str | None, hook: str | None) -> str:
    """Итоговое решение по слоям. `hook` — `allow`/`deny`/`ask`/`pass`/None."""
    if settings == DENY:
        return DENY
    if hook in (DENY, ASK, ALLOW):
        return hook
    if settings in (ASK, ALLOW):
        return settings
    return PROMPT
