"""Редактирование секретов во всём, что покидает процесс.

Правило: значение секрета не попадает в git, лог, отчёт, скриншот, fixture и prompt.
Функция `redact` применяется к каждому тексту перед записью в артефакт или журнал.
"""
from __future__ import annotations

import os
import re
from typing import Any, Iterable

PLACEHOLDER = "«REDACTED»"

#: Имена полей, значение которых всегда скрывается.
#: Границы обязательны: без них «passed» попадает под «pass» и булево значение
#: превращается в «REDACTED», ломая схему результата задания.
SENSITIVE_KEY_RE = re.compile(
    r"(?i)(?:^|[_\-])(?:password|passwd|pass|secret|token|api[_-]?key|access[_-]?key|private[_-]?key|"
    r"client[_-]?secret|authorization|cookie|session|credential|license[_-]?key)(?:$|[_\-])"
    r"|^(?:password|passwd|secret|token|apikey|api_key|authorization|cookie|credential)$"
)

#: Значения, узнаваемые по форме, независимо от имени поля.
VALUE_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH |DSA |PGP )?PRIVATE KEY-----.*?-----END [^-]*PRIVATE KEY-----", re.S),
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    re.compile(r"\bgh[pousr]_[A-Za-z0-9]{20,}\b"),
    re.compile(r"\bvk1\.a\.[A-Za-z0-9_\-]{20,}"),
    re.compile(r"\bey[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}\b"),  # JWT
    re.compile(r"://[^/\s:@]+:([^/\s@]+)@"),  # credentials в URL
)

#: `secret_ref` — это ссылка, а не секрет: его прятать не нужно и вредно.
SAFE_REF_RE = re.compile(r"^(env|file|vault|secret):[A-Za-z0-9_./-]+$")


def _env_secret_values() -> list[str]:
    """Фактические значения секретов из окружения — вырезаются буквально."""
    out: list[str] = []
    for key, value in os.environ.items():
        if not value or len(value) < 8:
            continue
        if SENSITIVE_KEY_RE.search(key):
            out.append(value)
    return out


def redact(text: str, extra_values: Iterable[str] = ()) -> str:
    if not text:
        return text
    result = text
    for value in list(extra_values) + _env_secret_values():
        if value and len(value) >= 8:
            result = result.replace(value, PLACEHOLDER)
    for pattern in VALUE_PATTERNS:
        if pattern.pattern.startswith("://"):
            result = pattern.sub(lambda m: m.group(0).replace(m.group(1), PLACEHOLDER), result)
        else:
            result = pattern.sub(PLACEHOLDER, result)
    # key=value / "key": "value" в логах и конфигурации
    result = re.sub(
        r"(?i)\b([A-Za-z0-9_\-]*(?:pass(?:word|wd)?|secret|token|api[_-]?key|access[_-]?key|"
        r"client[_-]?secret|license[_-]?key))\b(\s*[:=]\s*)(\"?)([^\s\"',;]+)(\3)",
        lambda m: m.group(1) + m.group(2) + m.group(3) + (m.group(4) if SAFE_REF_RE.match(m.group(4)) else PLACEHOLDER) + m.group(5),
        result,
    )
    return result


def redact_obj(obj: Any) -> Any:
    """Рекурсивно редактирует структуру данных перед сериализацией."""
    if isinstance(obj, dict):
        out = {}
        for key, value in obj.items():
            if isinstance(key, str) and SENSITIVE_KEY_RE.search(key) and not key.endswith("_ref"):
                out[key] = PLACEHOLDER if value not in (None, "", [], {}) else value
            else:
                out[key] = redact_obj(value)
        return out
    if isinstance(obj, list):
        return [redact_obj(v) for v in obj]
    if isinstance(obj, str):
        return redact(obj)
    return obj
