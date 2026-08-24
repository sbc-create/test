"""Редактирование секретов во всём, что покидает процесс.

Правило: значение секрета не попадает в git, лог, отчёт, скриншот, fixture и prompt.
Функция `redact` применяется к каждому тексту перед записью в артефакт или журнал.
"""
from __future__ import annotations

import os
import re
from collections.abc import Iterable
from typing import Any

PLACEHOLDER = "«REDACTED»"

#: Имена полей, значение которых всегда скрывается.
#: Границы обязательны: без них «passed» попадает под «pass» и булево значение
#: превращается в «REDACTED», ломая схему результата задания.
SENSITIVE_KEY_RE = re.compile(
    r"(?i)(?:^|[_\-])(?:password|passwd|pwd|pass|secret|token|api[_-]?key|access[_-]?key|private[_-]?key|"
    r"client[_-]?secret|authorization|auth|cookie|session|credential|credentials|license[_-]?key|"
    r"service[_-]?key|dsn|passphrase)(?:$|[_\-])"
    r"|^(?:password|passwd|pwd|secret|token|apikey|api_key|authorization|auth|cookie|credential|dsn)$"
)

#: Переменные окружения, которые никогда не являются секретом: их значения
#: вырезать нельзя, иначе из логов пропадут пути и локали.
NON_SECRET_ENV = {
    "PATH", "HOME", "PWD", "OLDPWD", "SHELL", "TERM", "LANG", "LC_ALL", "USER", "LOGNAME",
    "HOSTNAME", "TMPDIR", "EDITOR", "SHLVL", "_", "PYTHONPATH", "NODE_PATH", "TZ",
    "HTTP_PROXY", "HTTPS_PROXY", "NO_PROXY", "http_proxy", "https_proxy", "no_proxy",
}

#: Строка выглядит как секрет: длинная, без пробелов, с высокой долей уникальных символов.
def _looks_like_secret(value: str) -> bool:
    if len(value) < 20 or " " in value or "/" in value and value.startswith("/"):
        return False
    if not re.fullmatch(r"[A-Za-z0-9_\-\.=+:~]{20,}", value):
        return False
    return len(set(value)) >= 12

#: Значения, узнаваемые по форме, независимо от имени поля.
#: Набор расширен после security review: Slack/Google/Stripe и «голые»
#: высокоэнтропийные токены раньше проходили в артефакты как есть.
VALUE_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"\bxox[baprse]-[A-Za-z0-9-]{10,}\b"),                 # Slack
    re.compile(r"\bAIza[0-9A-Za-z_\-]{30,}\b"),                       # Google API key
    re.compile(r"\b(?:sk|pk|rk)_(?:live|test)_[0-9A-Za-z]{16,}\b"),   # Stripe
    re.compile(r"\bglpat-[0-9A-Za-z_\-]{16,}\b"),                     # GitLab
    re.compile(r"\bnpm_[0-9A-Za-z]{30,}\b"),                          # npm
    re.compile(r"\bs3cr3t\b", re.IGNORECASE),
    re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH |DSA |PGP )?PRIVATE KEY-----.*?-----END [^-]*PRIVATE KEY-----", re.S),
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    re.compile(r"\bgh[pousr]_[A-Za-z0-9]{20,}\b"),
    re.compile(r"\bvk1\.a\.[A-Za-z0-9_\-]{20,}"),
    # Яндекс OAuth: современная форма `y0_…`/`y0__…` и историческая `AQAA…`.
    # Форма взята из вида выданных токенов, а не из документации, поэтому это
    # дополнительная сетка поверх register_secret, а не замена ей.
    re.compile(r"\by0_+[A-Za-z0-9_\-]{20,}"),
    re.compile(r"\bAQAA[A-Za-z0-9_\-]{20,}"),
    re.compile(r"(?i)\bOAuth\s+[A-Za-z0-9_\-.]{20,}"),  # заголовок Authorization целиком
    re.compile(r"\bey[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}\b"),  # JWT
    re.compile(r"://[^/\s:@]+:([^/\s@]+)@"),  # credentials в URL
)

#: Пары «секретный ключ = значение» в логах и конфигурации.
KEY_VALUE_RE = re.compile(
    r"(?i)\b(?P<key>[A-Za-z0-9_\-]*(?:pass(?:word|wd|phrase)?|pwd|secret|token|api[_-]?key|"
    r"access[_-]?key|client[_-]?secret|license[_-]?key|service[_-]?key|credentials?|dsn|auth))\b"
    r"(?P<sep>\s*[:=]\s*)(?P<quote>\"?)(?P<value>[^\s\"',;]+)(?P=quote)"
)

#: `secret_ref` — это ссылка, а не секрет: его прятать не нужно и вредно.
SAFE_REF_RE = re.compile(r"^(env|file|vault|secret):[A-Za-z0-9_./-]+$")


#: Значения, которые процесс узнал во время работы: прочитанный из файла токен,
#: ответ secret-хранилища. Переменной окружения у них нет, а в артефакт они
#: попасть не должны. Реестр живёт только в памяти процесса и никуда не пишется.
_REGISTERED_SECRETS: set[str] = set()


def register_secret(value: str) -> None:
    """Запоминает фактическое значение секрета, чтобы `redact` вырезал его буквально.

    Вызывается тем, кто секрет прочитал, сразу после чтения. Короткие значения
    игнорируются: вырезать из логов строку в пять символов опаснее, чем оставить.
    """
    if value and len(value) >= 8:
        _REGISTERED_SECRETS.add(value)


def registered_secret_count() -> int:
    """Сколько значений под защитой. Сами значения наружу не отдаются никогда."""
    return len(_REGISTERED_SECRETS)


def forget_secrets() -> None:
    """Очистка реестра. Нужна тестам и ротации, в рабочем пути не вызывается."""
    _REGISTERED_SECRETS.clear()


def _env_secret_values() -> list[str]:
    """Фактические значения секретов из окружения — вырезаются буквально.

    Помимо «секретно названных» переменных вырезаются значения, которые выглядят
    как секрет: имя переменной не всегда содержит слово из списка
    (`FACTORY_STAGING_AUTH_*`, `VK_SERVICE_KEY`, `DB_DSN` раньше не попадали).
    """
    out: list[str] = []
    for key, value in os.environ.items():
        if not value or len(value) < 8 or key in NON_SECRET_ENV:
            continue
        if SENSITIVE_KEY_RE.search(key) or _looks_like_secret(value):
            out.append(value)
    return out


def redact(text: str, extra_values: Iterable[str] = ()) -> str:
    if not text:
        return text
    result = text
    for value in list(extra_values) + sorted(_REGISTERED_SECRETS) + _env_secret_values():
        if value and len(value) >= 8:
            result = result.replace(value, PLACEHOLDER)
    for pattern in VALUE_PATTERNS:
        if pattern.pattern.startswith("://"):
            result = pattern.sub(lambda m: m.group(0).replace(m.group(1), PLACEHOLDER), result)
        else:
            result = pattern.sub(PLACEHOLDER, result)
    # key=value / "key": "value" в логах и конфигурации.
    # Именованные группы: перенумерация при расширении списка ключей ломала обратную ссылку.
    result = KEY_VALUE_RE.sub(
        lambda m: (
            m.group("key") + m.group("sep") + m.group("quote")
            + (m.group("value") if SAFE_REF_RE.match(m.group("value")) else PLACEHOLDER)
            + m.group("quote")
        ),
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
