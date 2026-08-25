"""Перенос существующих credentials в Secret Hub.

Задание разделяет две вещи, и модуль тоже:

* **обнаружение** — какие файлы credentials существуют. Выполняется без чтения
  содержимого: только путь, права, владелец, размер. Эту часть безопасно
  вызывать откуда угодно, в том числе из сессии агента: она физически не может
  напечатать значение, потому что не открывает файл;
* **импорт** — чтение значений и запись их в хранилище. Выполняется только
  внутри root-процесса сервиса, проверяет значения живым запросом и не печатает
  их ни при каком исходе.

Старые файлы не удаляются. После подтверждённого применения их можно
заархивировать (``archive=True``) — копия ложится рядом с правами 0600, а
оригинал остаётся на месте до полной приёмки. «Не удалять рабочие credentials до
полной приёмки» — требование задания, и удаления в этом модуле нет вовсе.
"""
from __future__ import annotations

import os
import shutil
import stat
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from factory.errors import BlockedSecret
from factory.secret_hub import SECRET_FIELDS
from factory.secret_hub.crypto import Secret

#: Куда складываются архивные копии прежних файлов.
ARCHIVE_ROOT = Path("/var/lib/site-factory-secret-hub/imported")


@dataclass(frozen=True)
class Found:
    """Найденный файл credentials. Содержимого здесь нет и быть не может."""

    portfolio: str
    field: str
    path: Path
    #: ``True`` — файл есть, ``False`` — файла нет, ``None`` — не измерено.
    #: Троичность здесь не педантизм: каталог ``/etc/site-factory/secrets``
    #: закрыт для сессии агента намеренно, и отвечать «файл есть» на основании
    #: того, что нам не дали посмотреть, — это выдумка ровно того сорта,
    #: который фабрике запрещён.
    exists: bool | None
    mode: str | None
    owner_uid: int | None
    size: int | None
    problems: tuple[str, ...]

    @property
    def usable(self) -> bool:
        return bool(self.exists) and bool(self.size)

    def as_dict(self) -> dict:
        return {
            "portfolio": self.portfolio,
            "field": self.field,
            "path": str(self.path),
            "exists": self.exists,
            "mode": self.mode,
            "owner_uid": self.owner_uid,
            "size_bytes": self.size,
            "usable": self.usable,
            "problems": list(self.problems),
        }


def discover(config, portfolio_id: str | None = None) -> list[Found]:
    """Что уже лежит на хосте. Файлы не открываются — только ``stat``.

    Именно поэтому обнаружение безопасно вызывать из обычной сессии: «файл есть,
    720 байт, root:root 0400» — это факт о файле, а не о секрете.
    """
    out: list[Found] = []
    portfolios = ([config.portfolio(portfolio_id)] if portfolio_id
                  else list(config.portfolios))
    for portfolio in portfolios:
        for consumer in portfolio.consumers:
            for field_name in SECRET_FIELDS:
                out.append(_inspect(portfolio.id, field_name, consumer.path_for(field_name)))
    return out


def _inspect(portfolio: str, field_name: str, path: Path) -> Found:
    problems: list[str] = []
    try:
        info = path.stat()
    except FileNotFoundError:
        return Found(portfolio, field_name, path, False, None, None, None,
                     ("файл не найден",))
    except PermissionError:
        return Found(portfolio, field_name, path, None, None, None, None,
                     ("каталог закрыт для текущей учётной записи: состояние не измерено",))
    except OSError as exc:
        return Found(portfolio, field_name, path, False, None, None, None,
                     (f"не проверен ({exc.__class__.__name__})",))
    mode_bits = stat.S_IMODE(info.st_mode)
    if mode_bits & 0o077:
        problems.append(f"файл доступен группе или миру ({mode_bits:04o})")
    if info.st_uid != 0:
        problems.append(f"владелец uid={info.st_uid}, ожидается root")
    if info.st_size == 0:
        problems.append("файл пуст")
    return Found(portfolio, field_name, path, True, format(mode_bits, "04o"), info.st_uid,
                 info.st_size, tuple(problems))


def _read_value(path: Path, label: str) -> Secret:
    """Чтение значения. Вызывается только root-процессом.

    Содержимое файла не попадает ни в сообщение об ошибке, ни в лог: в текст
    исключения уходит только класс ошибки и путь.
    """
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise BlockedSecret(
            f"Файл {path} не прочитан ({exc.__class__.__name__}).",
            field=str(path),
            required_input="Доступ на чтение для root-процесса сервиса",
            blocks_stage="VALIDATING",
        ) from None
    value = raw.strip()
    if not value:
        raise BlockedSecret(
            f"Файл {path} пуст: импортировать нечего.",
            field=str(path),
            required_input="Непустое значение credentials",
            blocks_stage="VALIDATING",
        )
    return Secret(value, label=label)


def import_existing(hub, portfolio_id: str, *, archive: bool = False) -> dict:
    """Читает существующие файлы направления и кладёт значения в хранилище.

    Проверка идёт до записи: импортировать неработающий токен в центральное
    хранилище значило бы раздать его всем сайтам направления.
    """
    if os.geteuid() != 0:
        raise BlockedSecret(
            "Импорт выполняется только root-процессом: он читает файлы секретов.",
            field="euid",
            required_input="Запуск внутри site-factory-secret-hub.service",
            blocks_stage="VALIDATING",
        )
    portfolio = hub.config.portfolio(portfolio_id)
    if portfolio.blocked_target is not None:
        from factory.errors import BlockedTarget

        raise BlockedTarget(
            f"Направление «{portfolio.id}»: {portfolio.blocked_target.reason}",
            field=portfolio.id,
            required_input=portfolio.blocked_target.required_input,
            blocks_stage="VALIDATING",
        )

    found = discover(hub.config, portfolio_id)
    sources: dict[str, Found] = {}
    for item in found:
        if item.usable and item.field not in sources:
            sources[item.field] = item
    missing = [f for f in SECRET_FIELDS if f not in sources]
    if missing:
        return {
            "portfolio": portfolio.id,
            "imported": False,
            "status": "nothing_to_import",
            "reason": f"не найдены существующие значения: {', '.join(missing)}",
            "discovered": [f.as_dict() for f in found],
        }

    values = {name: _read_value(sources[name].path, f"{portfolio.id}/{name}")
              for name in SECRET_FIELDS}
    result = hub.store_verified(portfolio.id, values)
    del values

    response = {
        "portfolio": portfolio.id,
        "imported": bool(result.get("stored")),
        "version": result.get("version"),
        "fingerprint": result.get("fingerprint"),
        "verify": result.get("verify"),
        "sources": [sources[name].as_dict() for name in SECRET_FIELDS],
    }
    if not result.get("stored"):
        response["status"] = "verification_failed"
        response["reason"] = result.get("reason", "провайдер не подтвердил credentials")
        return response

    response["status"] = "imported"
    if archive:
        response["archived"] = [str(p) for p in
                                _archive([sources[name].path for name in SECRET_FIELDS],
                                         portfolio.id)]
    else:
        response["archived"] = []
        response["note"] = ("Оригиналы не тронуты. Архивировать их следует только после "
                            "подтверждённого применения: --archive.")
    return response


def _archive(paths: list[Path], portfolio_id: str) -> list[Path]:
    """Копия прежних файлов с правами 0600. Оригиналы остаются на месте.

    Именно копия, а не перемещение: до полной приёмки рабочие credentials должны
    оставаться там, где их сейчас читает работающий сайт.
    """
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    directory = ARCHIVE_ROOT / portfolio_id / stamp
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(directory, 0o700)
    out: list[Path] = []
    for path in paths:
        target = directory / path.name
        shutil.copy2(path, target)
        os.chmod(target, 0o600)
        if os.geteuid() == 0:
            shutil.chown(target, user="root", group="root")
        out.append(target)
    return out


def report(config, portfolio_id: str | None = None) -> dict:
    """Отчёт об обнаруженных файлах — без чтения. Для CLI и для `status`."""
    found = discover(config, portfolio_id)
    return {
        "discovered": [f.as_dict() for f in found],
        "note": ("Содержимое файлов не читалось: это обнаружение, а не импорт. "
                 "Импорт выполняется root-процессом командой `factory secrets import`."),
    }
