#!/usr/bin/env python3
"""Назначение шаблона новому домену: атомарно, повторяемо, без переназначений.

## Правила, из которых всё следует

Домен получает СЛЕДУЮЩИЙ свободный совместимый шаблон и остаётся на нём
навсегда, пока владелец не решит иначе. Отсюда три свойства, которые и
проверяются тестами:

* **повтор даёт то же самое.** Повторный приём того же домена возвращает уже
  выданный шаблон, а не следующий. Иначе один домен съедал бы пул.
* **одновременность не даёт дубля.** Два домена, пришедшие одновременно, не
  могут получить один шаблон: резервирование идёт под файловой блокировкой, а
  запись ledger — атомарной заменой.
* **обрыв не теряет шаблон.** Падение после резервирования и до подтверждения
  не должно ни выдать шаблон дважды, ни потерять его: резерв виден в ledger и
  доигрывается, а не начинается заново.

Порядок выбора детерминирован: по числовому идентификатору шаблона. Хеш домена
здесь запрещён — он выдаёт разным доменам один шаблон при коллизии и делает
результат невоспроизводимым.

Назначение НЕ включает домен, не меняет DNS и не трогает индексацию. Это запись
в реестре, а не выкладка.
"""

from __future__ import annotations

import datetime as _dt
import fcntl
import json
import os
import pathlib
import re
import tempfile

#: Точный домен: без wildcard и без подстановки TLD. Домен, которого нет в
#: заявке целиком, — это другой домен, а не «похожий».
ДОМЕН = re.compile(r"^(?!-)[a-z0-9-]{1,63}(?:\.[a-z0-9-]{1,63})+$")

НАЗНАЧАЕМЫЙ = "ASSIGNABLE"
ЗАРЕЗЕРВИРОВАН = "RESERVED"


class ОтказНазначения(Exception):
    """Назначение невозможно. Причина всегда названа."""


class НетСовместимого(ОтказНазначения):
    """BLOCKED_NO_COMPATIBLE_TEMPLATE: подходящего шаблона в пуле нет."""


class ПулИсчерпан(ОтказНазначения):
    """Свободных шаблонов не осталось. Это не повод выдать занятый."""


def _сейчас() -> str:
    return _dt.datetime.now(_dt.timezone.utc).isoformat()


def _записать_атомарно(путь: pathlib.Path, данные: dict) -> None:
    """Запись через временный файл и замену.

    Прямая запись оставляет обрезанный JSON, если процесс умрёт на середине, —
    и тогда реестр теряется целиком вместе со всеми назначениями.
    """
    путь.parent.mkdir(parents=True, exist_ok=True)
    fd, врем = tempfile.mkstemp(dir=str(путь.parent), prefix=f".{путь.name}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as файл:
            json.dump(данные, файл, ensure_ascii=False, indent=2)
            файл.write("\n")
            файл.flush()
            os.fsync(файл.fileno())
        os.replace(врем, путь)
    except BaseException:
        pathlib.Path(врем).unlink(missing_ok=True)
        raise


class Реестр:
    """Пул шаблонов и ledger назначений в одном каталоге."""

    def __init__(self, корень: pathlib.Path) -> None:
        self.корень = pathlib.Path(корень)
        self.пул_файл = self.корень / "template-pool.json"
        self.ledger_файл = self.корень / "assignments.json"
        self.замок_файл = self.корень / ".assignment.lock"

    # --- чтение -----------------------------------------------------------
    def пул(self) -> dict:
        return json.loads(self.пул_файл.read_text(encoding="utf-8"))

    def ledger(self) -> dict:
        if not self.ledger_файл.is_file():
            return {"schema_version": 1, "assignments": []}
        return json.loads(self.ledger_файл.read_text(encoding="utf-8"))

    def назначение(self, домен: str) -> dict | None:
        for запись in self.ledger()["assignments"]:
            if запись["exact_domain"] == домен:
                return запись
        return None

    # --- выбор ------------------------------------------------------------
    @staticmethod
    def совместим(шаблон: dict, возможности: set[str], ленты: set[str]) -> bool:
        """Шаблон подходит, если домен закрывает всё, что шаблон требует."""
        if not set(шаблон["required_feeds"]) <= ленты:
            return False
        return bool(set(шаблон["capabilities"]) & возможности) and set(шаблон["capabilities"]) <= возможности

    def _свободные(self, пул: dict, занятые: set[str]) -> list[dict]:
        return [
            ш for ш in пул["templates"]
            if ш["status"] == НАЗНАЧАЕМЫЙ
            and ш["template_id"] not in занятые
            and not ш["assigned_domain"]
        ]

    # --- назначение --------------------------------------------------------
    def назначить(self, домен: str, *, возможности: set[str], ленты: set[str],
                  site_id: str = "") -> dict:
        """Вернуть назначение домена, выдав новое только если его ещё нет."""
        домен = домен.strip().lower()
        if not ДОМЕН.match(домен):
            raise ОтказНазначения(f"домен не является точным именем: {домен!r}")

        self.корень.mkdir(parents=True, exist_ok=True)
        with open(self.замок_файл, "a+") as замок:
            # Блокировка на весь цикл «прочитать — выбрать — записать».
            # Без неё два одновременных приёма прочитают один и тот же пул и
            # выберут один и тот же шаблон.
            fcntl.flock(замок.fileno(), fcntl.LOCK_EX)
            try:
                ledger = self.ledger()
                for запись in ledger["assignments"]:
                    if запись["exact_domain"] == домен:
                        # Повтор возвращает выданное. Ровно то же самое, включая
                        # резерв, не доведённый до подтверждения.
                        return запись

                пул = self.пул()
                занятые = {з["template_id"] for з in ledger["assignments"]}
                свободные = self._свободные(пул, занятые)
                if not свободные:
                    raise ПулИсчерпан(
                        f"свободных ASSIGNABLE-шаблонов нет: занято {len(занятые)} из "
                        f"{len(пул['templates'])}"
                    )

                подходящие = [ш for ш in свободные if self.совместим(ш, возможности, ленты)]
                if not подходящие:
                    raise НетСовместимого(
                        "BLOCKED_NO_COMPATIBLE_TEMPLATE: ни один свободный шаблон не "
                        f"совместим с возможностями {sorted(возможности)} и лентами {sorted(ленты)}"
                    )

                # Детерминированный порядок: по идентификатору. Случайность и
                # хеш домена здесь запрещены.
                выбран = min(подходящие, key=lambda ш: ш["template_id"])
                запись = {
                    "exact_domain": домен,
                    "site_id": site_id or домен.split(".")[0],
                    "template_id": выбран["template_id"],
                    "slug": выбран["slug"],
                    "version": выбран["version"],
                    "state": ЗАРЕЗЕРВИРОВАН,
                    "reserved_at": _сейчас(),
                    "activated_at": None,
                    "decision_id": f"LORDS-TEMPLATE-ASSIGN-{выбран['template_id']}-{домен}",
                    "artifact_digest": выбран["artifact_digest"],
                }
                ledger["assignments"].append(запись)
                _записать_атомарно(self.ledger_файл, ledger)
                return запись
            finally:
                fcntl.flock(замок.fileno(), fcntl.LOCK_UN)

    def активировать(self, домен: str) -> dict:
        """Пометить назначение действующим. Резерв не теряется, если шага не было."""
        with open(self.замок_файл, "a+") as замок:
            fcntl.flock(замок.fileno(), fcntl.LOCK_EX)
            try:
                ledger = self.ledger()
                for запись in ledger["assignments"]:
                    if запись["exact_domain"] == домен.strip().lower():
                        if запись["state"] != "ACTIVE":
                            запись["state"] = "ACTIVE"
                            запись["activated_at"] = _сейчас()
                            _записать_атомарно(self.ledger_файл, ledger)
                        return запись
                raise ОтказНазначения(f"домен {домен} не имеет назначения")
            finally:
                fcntl.flock(замок.fileno(), fcntl.LOCK_UN)
