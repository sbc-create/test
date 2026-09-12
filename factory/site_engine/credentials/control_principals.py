"""Ротация токенов управляющего слоя с сохранением областей прав.

Почему это отдельный инструмент
-------------------------------

Служебные личности журнала опознаются по отпечаткам, и там отзыв — это
запись в реестре. Токены управляющего слоя устроены иначе: Control API
разбирает строку `токен=области|токен=области` и сравнивает предъявленное с
самим значением. Значит отзыв здесь — это ЗАМЕНА значения: старое перестаёт
быть принципалом и отвергается тем же кодом, что и любое чужое.

Области прав переносятся дословно. Ротация, попутно меняющая права, — это
уже не ротация, а изменение доступа, и обнаруживают его тогда, когда что-то
перестало работать.

Значения не печатаются. Наружу идёт только соответствие прежнего отпечатка
новому — по нему видно, что замена состоялась, и нельзя восстановить ни то,
ни другое.
"""
from __future__ import annotations

import hashlib
import json
import os
import secrets
from pathlib import Path
from typing import Any

ФАЙЛ = Path(os.environ.get("SITE_FACTORY_CREDENTIALS_DIR",
                           "/etc/site-factory/credentials")) / "site-engine-control-tokens"
#: Длина нового значения. Та же, что у прежних: 48 байт urlsafe.
ДЛИНА = 48


class PrincipalError(RuntimeError):
    def __init__(self, код: str, детали: str):
        super().__init__(детали)
        self.error_code, self.detail = код, детали


def _отпечаток(значение: str) -> str:
    return hashlib.sha256(значение.encode("utf-8")).hexdigest()


def разобрать(сырое: str) -> list[tuple[str, list[str]]]:
    итог = []
    for кусок in сырое.strip().split("|"):
        кусок = кусок.strip()
        if not кусок or "=" not in кусок:
            continue
        токен, _, области = кусок.partition("=")
        if токен.strip():
            итог.append((токен.strip(),
                         [о.strip() for о in области.split(",") if о.strip()]))
    return итог


def собрать(принципалы: list[tuple[str, list[str]]]) -> str:
    return "|".join(f"{т}={','.join(о)}" for т, о in принципалы)


def состояние(путь: Path | None = None) -> list[dict[str, Any]]:
    п = путь or ФАЙЛ
    if not п.is_file():
        return []
    return [{"fingerprint": _отпечаток(т)[:12], "scopes": sorted(о)}
            for т, о in разобрать(п.read_text("utf-8"))]


def ротировать(путь: Path | None = None) -> dict[str, Any]:
    """Заменить значения, сохранив области. Прежние перестают быть принципалами."""
    п = путь or ФАЙЛ
    if not п.is_file():
        raise PrincipalError("PRINCIPALS_MISSING", f"{п} не найден")
    прежние = разобрать(п.read_text("utf-8"))
    if not прежние:
        raise PrincipalError("PRINCIPALS_EMPTY", "принципалов нет")

    новые, соответствие = [], []
    for токен, области in прежние:
        новое = secrets.token_urlsafe(ДЛИНА)
        новые.append((новое, области))
        соответствие.append({"previous_fingerprint": _отпечаток(токен)[:12],
                             "new_fingerprint": _отпечаток(новое)[:12],
                             "scopes": sorted(области)})

    врем = п.with_suffix(п.suffix + ".new")
    старый_umask = os.umask(0o077)
    try:
        врем.write_text(собрать(новые) + "\n", encoding="utf-8")
        os.chmod(врем, 0o400)
        os.replace(врем, п)
    finally:
        os.umask(старый_umask)

    # Проверка на месте: области обязаны совпасть дословно.
    стало = разобрать(п.read_text("utf-8"))
    if [sorted(о) for _, о in стало] != [sorted(о) for _, о in прежние]:
        raise PrincipalError("SCOPES_CHANGED",
                             "области прав изменились при ротации")
    return {"rotated": len(соответствие), "mapping": соответствие}


if __name__ == "__main__":
    import sys
    если = sys.argv[1] if len(sys.argv) > 1 else "status"
    if если == "rotate":
        print(json.dumps(ротировать(), ensure_ascii=False, indent=1))
    else:
        print(json.dumps({"principals": состояние()}, ensure_ascii=False, indent=1))
