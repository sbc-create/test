"""robots.txt по RFC 9309: группы по user-agent, `*` и `$`, самое длинное
совпадение, при равной длине побеждает Allow.

Стандартный urllib.robotparser шаблонов не понимает: он и пропускал бы
закрытые через `/*?` адреса, и закрывал открытые. Для аудита, который
обязан соблюдать правила источника, это недопустимо.
"""

from __future__ import annotations

import re
import urllib.parse


def _compile(pattern: str) -> re.Pattern:
    anchored = pattern.endswith("$")
    if anchored:
        pattern = pattern[:-1]
    rx = "".join(".*" if ch == "*" else re.escape(ch) for ch in pattern)
    return re.compile(rx + ("$" if anchored else ""))


class Robots:
    def __init__(self, text: str):
        self.groups: list[tuple[list[str], list[tuple[bool, str, re.Pattern]]]] = []
        agents: list[str] = []
        rules: list = []
        in_rules = False
        for raw in text.splitlines():
            line = raw.split("#", 1)[0].strip()
            if ":" not in line:
                continue
            key, val = (s.strip() for s in line.split(":", 1))
            key = key.lower()
            if key == "user-agent":
                if in_rules:
                    self.groups.append((agents, rules))
                    agents, rules, in_rules = [], [], False
                agents.append(val.lower())
            elif key in ("allow", "disallow"):
                in_rules = True
                if val:
                    if not val.startswith(("/", "*")):
                        val = "/" + val
                    rules.append((key == "allow", val, _compile(val)))
        if agents:
            self.groups.append((agents, rules))

    def _rules_for(self, ua: str) -> list:
        token = ua.split("/")[0].lower()
        specific = [r for a, r in self.groups if any(x != "*" and x in token for x in a)]
        if specific:
            return [x for g in specific for x in g]
        return [x for a, r in self.groups if "*" in a for x in r]

    def can_fetch(self, ua: str, url: str) -> bool:
        p = urllib.parse.urlsplit(url)
        path = (p.path or "/") + (("?" + p.query) if p.query else "")
        if path == "/robots.txt":
            return True
        best_len, allowed = -1, True
        for allow, raw, rx in self._rules_for(ua):
            if rx.match(path):
                n = len(raw)
                if n > best_len or (n == best_len and allow):
                    best_len, allowed = n, allow
        return allowed
