"""REQ-SEC: правило «чтение файла с секретом» смотрит на имя файла, а не на подстроку.

Правило было подстрочным: под него попадала любая команда, где после `cat`
где-нибудь встречалось слово `credentials` или `token` — включая создание
исходника `credentials.py` и чтение документа про политику токенов. Правило,
которое останавливает обычную работу, рано или поздно снимают целиком, поэтому
оно сужено, а не ослаблено: настоящие секретные файлы обязаны по-прежнему
блокироваться, и первый список этого файла — доказательство.
"""
from __future__ import annotations

import pytest

from seo_operator.guardrails import ActionContext, Decision, classify


def _decision(command: str) -> Decision:
    return classify(ActionContext(command=command, environment="sandbox")).decision


#: Реальные секретные файлы. Каждый обязан остаться запрещённым.
BLOCKED = [
    "cat .env",
    "cat ./.env",
    "cat /srv/app/.env.production",
    "cat ~/.ssh/id_rsa",
    "cat /home/deploy/.ssh/id_ed25519",
    "cat ~/.ssh/authorized_keys",
    "cat deploy.pem",
    "cat /etc/ssl/private/site.key",
    "cat /opt/bundle.p12",
    "cat /opt/app/credentials",
    "cat /etc/site-factory/store/yandex_oauth_token",
    "cat /var/lib/app/tokens",
]

#: Обычная работа. Ни одна из команд не является чтением секрета.
NOT_BLOCKED = [
    "cat > factory/analytics/credentials.py",
    "cat factory/analytics/credentials.py",
    "cat docs/api-token-policy.md",
    "cat seo_operator/token_helpers.py",
    "cat tests/unit/test_credentials.py",
    "cat README.md",
]


@pytest.mark.parametrize("command", BLOCKED)
def test_real_secret_files_stay_blocked(command: str) -> None:
    assert _decision(command) is Decision.BLOCK, f"секретный файл перестал быть запрещён: {command}"


@pytest.mark.parametrize("command", NOT_BLOCKED)
def test_ordinary_files_are_not_credential_reads(command: str) -> None:
    assert _decision(command) is not Decision.BLOCK, f"обычная работа заблокирована: {command}"


def test_writing_a_file_is_not_a_read() -> None:
    """`cat > file` — запись. Её разбирает слой записи, а не правило чтения секретов."""
    assert _decision("cat > /tmp/claude-scratch/notes.txt") is not Decision.BLOCK
