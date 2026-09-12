"""Чтение учётных данных только через systemd LoadCredential.

Почему не окружение
-------------------

Переменная окружения — не граница. Она наследуется потомками, видна в
`/proc/<pid>/environ`, попадает в дампы и трассировки, и — главное —
`EnvironmentFile` отдаётся юниту ЦЕЛИКОМ. Положив в один файл девять
служебных личностей и приватный ключ подписи, мы выдаём каждой службе всё
сразу; никакой `unset` после старта этого уже не отменяет, потому что к
первой строке кода значение уже побывало в процессе.

`LoadCredential` устроен иначе: systemd читает файл от root и кладёт ровно
запрошенный кусок в приватный tmpfs-каталог `$CREDENTIALS_DIRECTORY` этого
юнита. Чужого там нет физически, а не по договорённости.

Строгий режим
-------------

Модуль ОТКАЗЫВАЕТСЯ брать значение из окружения. Тихий откат на переменную
вернул бы ровно ту дыру, ради которой всё делается, и вернул бы незаметно.
Послабление существует только на время поэтапного перевода служб и
включается явным `SITE_FACTORY_ALLOW_ENV_CREDENTIALS=1`.

Наружу значение не логируется никогда. Для диагностики есть отпечаток —
двенадцать шестнадцатеричных знаков SHA-256: восстановить по нему значение
нельзя, а ответить на вопрос «тот же ключ или другой» можно.
"""
from __future__ import annotations

import hashlib
import os
from pathlib import Path

#: Послабление на время миграции. В рабочем контуре не выставляется:
#: наличие этой переменной само по себе является дефектом конфигурации.
ПОСЛАБЛЕНИЕ = "SITE_FACTORY_ALLOW_ENV_CREDENTIALS"


class CredentialError(RuntimeError):
    def __init__(self, code: str, detail: str):
        super().__init__(detail)
        self.error_code, self.detail = code, detail


def каталог() -> Path | None:
    к = os.environ.get("CREDENTIALS_DIRECTORY", "").strip()
    return Path(к) if к else None


def послабление_включено() -> bool:
    return os.environ.get(ПОСЛАБЛЕНИЕ, "").strip() in ("1", "true", "yes")


def отпечаток(значение: str | bytes) -> str:
    """Чем сравнивать значения, не показывая их."""
    b = значение.encode("utf-8") if isinstance(значение, str) else значение
    return hashlib.sha256(b).hexdigest()[:12]


def полный_отпечаток(значение: str | bytes) -> str:
    b = значение.encode("utf-8") if isinstance(значение, str) else значение
    return hashlib.sha256(b).hexdigest()


def есть(имя: str) -> bool:
    к = каталог()
    return bool(к and (к / имя).is_file())


def получить(имя: str, *, запасная_переменная: str | None = None) -> str:
    """Вернуть значение по имени credential.

    `запасная_переменная` действует ТОЛЬКО при явном послаблении и только на
    время миграции. Без послабления её наличие ничего не меняет — кроме того,
    что отказ становится объяснимым.
    """
    к = каталог()
    if к is not None:
        ф = к / имя
        if ф.is_file():
            значение = ф.read_text("utf-8").strip()
            if значение:
                return значение
            raise CredentialError("CREDENTIAL_EMPTY", f"credential {имя} пуст")
    if запасная_переменная and послабление_включено():
        значение = os.environ.get(запасная_переменная, "").strip()
        if значение:
            return значение
    if запасная_переменная and os.environ.get(запасная_переменная, "").strip():
        # Значение в окружении есть, но брать его нельзя — и промолчать тоже
        # нельзя: иначе служба «просто не работает» без объяснимой причины.
        raise CredentialError(
            "CREDENTIAL_ENV_FORBIDDEN",
            f"{имя}: значение доступно только через переменную окружения "
            f"{запасная_переменная}; передача учётных данных окружением "
            f"запрещена — юнит обязан объявить LoadCredential")
    raise CredentialError(
        "CREDENTIAL_MISSING",
        f"credential {имя} не передан: юнит обязан объявить "
        f"LoadCredential={имя}:<путь>")


def получить_или_none(имя: str, *, запасная_переменная: str | None = None) -> str | None:
    try:
        return получить(имя, запасная_переменная=запасная_переменная)
    except CredentialError:
        return None


def перечислить() -> list[str]:
    """Имена доступных credentials. Значения при этом не читаются."""
    к = каталог()
    if к is None or not к.is_dir():
        return []
    return sorted(п.name for п in к.iterdir() if п.is_file())
