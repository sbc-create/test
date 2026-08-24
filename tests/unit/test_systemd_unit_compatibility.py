"""REQ-SYSTEMD: unit-файлы разворачиваются на systemd, который стоит на целевом хосте.

Дефект, ради которого написан файл: `Environment=YANDEX_OAUTH_TOKEN_FILE=%d/...`.
Специфер `%d` («каталог credentials») появился в systemd 250, а Ubuntu 22.04
везёт 249. На 249 строка не разворачивается и остаётся literal-ом `%d/...`,
после чего сервис падает на «файл секрета не найден» — то есть выглядит как
проблема с секретом, хотя секрет на месте. `systemd-analyze verify` такую
строку не ловит: синтаксически она корректна.

Проверяется не «в файле нет символа», а два свойства: unit не пользуется
спецификаторами новее целевой версии, и путь к credential вычисляется даже
когда `Environment=` не задан вовсе.
"""
from __future__ import annotations

import os
import re

import pytest

from factory.analytics import credentials as creds
from factory.paths import PATHS

UNIT_DIR = PATHS.automation / "host" / "systemd"
UNITS = sorted(UNIT_DIR.glob("*.service")) + sorted(UNIT_DIR.glob("*.timer"))

#: Минимальная версия systemd на целевом хосте. Ubuntu 22.04 LTS везёт 249.
TARGET_SYSTEMD = 249

#: Спецификаторы, появившиеся позже целевой версии. Ключ — версия введения.
SPECIFIERS_NEWER_THAN_TARGET = {
    "%d": 250,   # каталог credentials
    "%D": 250,   # каталог shared data
}


@pytest.mark.parametrize("unit", UNITS, ids=lambda p: p.name)
def test_no_specifier_newer_than_the_target_systemd(unit) -> None:
    text = unit.read_text(encoding="utf-8")
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue  # в комментарии специфер объясняется, а не используется
        for specifier, introduced in SPECIFIERS_NEWER_THAN_TARGET.items():
            assert specifier not in stripped, (
                f"{unit.name}: специфер {specifier} появился в systemd {introduced}, "
                f"а целевой хост несёт {TARGET_SYSTEMD}: строка останется literal-ом. "
                f"Строка: {stripped}"
            )


@pytest.mark.parametrize("unit", UNITS, ids=lambda p: p.name)
def test_credential_path_matches_the_unit_name(unit) -> None:
    """Если путь к credential задан явно, он обязан указывать в свой же каталог."""
    text = unit.read_text(encoding="utf-8")
    if "LoadCredential=" not in text:
        return
    match = re.search(r"^Environment=YANDEX_OAUTH_TOKEN_FILE=(\S+)", text, re.M)
    if match is None:
        return  # путь берётся из CREDENTIALS_DIRECTORY — тоже корректно
    path = match.group(1)
    assert path.startswith("/run/credentials/"), path
    # `%n` — полное имя unit'а: именно так systemd называет каталог credentials.
    assert "%n" in path or unit.name in path, (
        f"{unit.name}: путь {path} не связан с именем unit'а — при переименовании "
        "или копировании в другой unit он будет указывать в чужой каталог"
    )
    name = re.search(r"LoadCredential=([^:]+):", text).group(1)
    assert path.endswith("/" + name), (
        f"{unit.name}: LoadCredential кладёт «{name}», а путь ведёт к «{path}»"
    )


@pytest.mark.parametrize("unit", UNITS, ids=lambda p: p.name)
def test_units_never_carry_a_secret_value(unit) -> None:
    text = unit.read_text(encoding="utf-8")
    for variable in creds.FORBIDDEN_VALUE_ENV:
        assert f"{variable}=" not in text, (
            f"{unit.name}: значение токена не передаётся переменной {variable}"
        )


def test_token_path_resolves_without_an_environment_line(tmp_path, monkeypatch) -> None:
    """Главная страховка: путь находится и тогда, когда unit его не задал.

    Это делает контур независимым от версии systemd: `CREDENTIALS_DIRECTORY`
    выставляется той же версией, что поддерживает `LoadCredential`.
    """
    directory = tmp_path / "credentials"
    directory.mkdir()
    secret = directory / creds.CREDENTIAL_NAME
    secret.write_text("y0_AgAAAABunitTESTtoken0123456789", encoding="utf-8")
    secret.chmod(0o400)

    monkeypatch.delenv(creds.TOKEN_FILE_ENV, raising=False)
    monkeypatch.setenv(creds.CREDENTIALS_DIR_ENV, str(directory))
    for name in creds.FORBIDDEN_VALUE_ENV:
        monkeypatch.delenv(name, raising=False)

    assert creds.token_path() == secret
    assert creds.inspect_token_file().ok
    from factory.redaction import forget_secrets

    assert creds.load_token().reveal().startswith("y0_")
    forget_secrets()


def test_explicit_environment_wins_over_the_credentials_directory(tmp_path, monkeypatch) -> None:
    """Явно заданный путь сильнее: иначе отладочная подмена молча игнорируется."""
    directory = tmp_path / "credentials"
    directory.mkdir()
    (directory / creds.CREDENTIAL_NAME).write_text("x", encoding="utf-8")
    explicit = tmp_path / "elsewhere"
    explicit.write_text("y", encoding="utf-8")

    monkeypatch.setenv(creds.CREDENTIALS_DIR_ENV, str(directory))
    monkeypatch.setenv(creds.TOKEN_FILE_ENV, str(explicit))
    assert creds.token_path() == explicit


def test_unresolved_specifier_would_be_caught(tmp_path, monkeypatch) -> None:
    """Нераскрытый специфер обязан давать понятную ошибку, а не «файла нет».

    Так выглядел дефект на сервере: путь `%d/yandex_oauth` — это относительный
    путь от рабочего каталога, и сообщение «файл секрета не найден» уводило в
    сторону секрета вместо unit-файла.
    """
    monkeypatch.setenv(creds.TOKEN_FILE_ENV, "%d/yandex_oauth")
    monkeypatch.delenv(creds.CREDENTIALS_DIR_ENV, raising=False)
    status = creds.inspect_token_file()
    assert not status.exists
    assert "%d" in status.path, "путь с нераскрытым специфером обязан быть виден в отчёте"


def test_installed_unit_agrees_with_the_repository_template() -> None:
    """Если unit уже установлен на этом хосте, шаблон не должен от него отставать.

    Тест не требует установленного unit'а: на машине разработчика его нет, и
    это нормально. Но если он есть, расхождение по спецификаторам означает, что
    следующая переустановка вернёт сломанную строку.
    """
    installed = "/etc/systemd/system/site-factory-analytics-apply.service"
    if not os.path.exists(installed):
        pytest.skip("unit не установлен на этой машине")
    with open(installed, encoding="utf-8") as handle:
        text = handle.read()
    for line in text.splitlines():
        stripped = line.strip()
        if stripped and not stripped.startswith("#"):
            assert "%d" not in stripped, (
                "установленный unit содержит %d — на systemd 249 он не развернётся"
            )
