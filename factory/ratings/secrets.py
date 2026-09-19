"""Загрузка секретов ratings. Токены никогда не логируются."""

from __future__ import annotations

import os
import stat
from pathlib import Path


class SecretError(RuntimeError):
    pass


def load_secret_file(path: Path | str) -> str:
    """Читает секрет. Права файла не шире 0600."""
    p = Path(path)
    if not p.is_file():
        raise SecretError(f"секрет не найден: {p}")
    mode = p.stat().st_mode
    if mode & (stat.S_IRWXG | stat.S_IRWXO):
        raise SecretError(
            f"права {p} слишком широкие ({oct(mode & 0o777)}); требуется не шире 0600"
        )
    return p.read_text(encoding="utf-8").strip()


def resolve_shikimori_token() -> str | None:
    """OAuth-токен Shikimori через штатный secret storage, если задан.

    GraphQL публичного чтения может работать без токена; при наличии —
    передаём Authorization. Значение никогда не возвращается в лог/отчёт.
    """
    cred_dir = os.environ.get("CREDENTIALS_DIRECTORY")
    cred_name = os.environ.get("SHIKIMORI_TOKEN_CREDENTIAL", "shikimori_api_token")
    if cred_dir:
        path = Path(cred_dir) / cred_name
        if path.is_file():
            return load_secret_file(path)
    env_path = os.environ.get("SHIKIMORI_TOKEN_FILE")
    if env_path:
        return load_secret_file(env_path)
    # Прямой env-токен допускается только для локальных тестов; в отчётах не светим.
    return os.environ.get("SHIKIMORI_TOKEN") or None


def redact_headers(headers: dict[str, str]) -> dict[str, str]:
    """Копия заголовков без Authorization и полных секретов."""
    out = {}
    for k, v in headers.items():
        lk = k.lower()
        if lk in ("authorization", "cookie", "x-api-key"):
            out[k] = "***REDACTED***"
        else:
            out[k] = v
    return out
