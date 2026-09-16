#!/usr/bin/env python3
"""Очередь выкладки: по витрине на очередь, по витрине на замок.

Почему по витрине
-----------------

Одна общая очередь означала, что зависшая отрисовка Lords держала всё: Yummy,
Zona и Animedia ждали её часами, хотя ни одна из них не пересекается с ней ни
файлом, ни службой. Логическая зависимость там, где нет физической, — это
выдуманное ограничение, и стоило оно суток.

Физическое ограничение существует ровно одно: памяти хватает на **один**
тяжёлый рендер. Оно и выражено отдельно — общим семафором тяжёлых работ, а не
общей очередью. DNS, nginx, TLS и проверки семафора не берут вовсе: они не
рендерят.

Что здесь ещё
-------------

Слияние дубликатов. Две одинаковые заявки на одну витрину — это одна работа,
а не две: вторая не ждёт первую, а поглощается ею. Иначе очередь растёт от
повторных нажатий, и каждая копия делает часовую отрисовку заново.

Запрет воскрешения. Заявка, снятая с очереди, не возвращается в неё после
падения приёмщика. Прежняя схема при перезапуске «продолжала незавершённую
выкладку» — и продолжала бы вытесненную тоже, уже после того, как барьер
объявил другую желаемую ревизию.
"""

from __future__ import annotations

import errno
import fcntl
import json
import os
import re
import time
from contextlib import contextmanager
from pathlib import Path

БАЗА = Path("/var/lib/lords-deploy")
ИМЯ_САЙТА = re.compile(r"^[a-z][a-z0-9-]{2,31}$")
#: Один тяжёлый рендер одновременно: памяти на два не хватает, и это измерено —
#: cgroup упирался в предел 2 ГиБ при 97 530 срабатываниях.
СЕМАФОР_ТЯЖЁЛЫХ = "heavy-render"


class QueueError(Exception):
    """Очередь отказала. Действие не выполнено."""


def _сайт(site: str) -> str:
    if not ИМЯ_САЙТА.match(site or ""):
        raise QueueError(f"имя витрины негодно: {site!r}")
    return site


def каталог_очереди(site: str, *, корень: Path | None = None) -> Path:
    return (корень or БАЗА) / "requests" / _сайт(site)


def каталог_замков(*, корень: Path | None = None) -> Path:
    return (корень or БАЗА) / "locks"


@contextmanager
def замок(имя: str, *, корень: Path | None = None, ждать: float = 0.0):
    """Исключительный замок по имени. Не ждёт, если не просили.

    Ожидание по умолчанию нулевое намеренно: очередь, которая молча ждёт
    часами, выглядит работающей и не является ею. Кто хочет ждать — говорит об
    этом явно и ограничивает время.
    """
    каталог = каталог_замков(корень=корень)
    каталог.mkdir(parents=True, exist_ok=True)
    путь = каталог / f"{имя}.lock"
    ф = open(путь, "a+")
    порог = time.time() + ждать
    while True:
        try:
            fcntl.flock(ф.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            break
        except OSError as ошибка:
            if ошибка.errno not in (errno.EAGAIN, errno.EACCES):
                ф.close()
                raise
            if time.time() >= порог:
                ф.close()
                raise QueueError(f"замок {имя} занят")
            time.sleep(0.2)
    try:
        ф.seek(0)
        ф.truncate()
        ф.write(json.dumps({"pid": os.getpid(),
                            "at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}))
        ф.flush()
        yield путь
    finally:
        fcntl.flock(ф.fileno(), fcntl.LOCK_UN)
        ф.close()


def поставить(site: str, заявка: dict, *, корень: Path | None = None) -> dict:
    """Поставить заявку в очередь витрины, поглощая точный дубликат.

    Дубликатом считается заявка с той же ревизией, тем же артефактом и тем же
    поколением: это буквально та же работа. Отличие хотя бы в одном поле — уже
    другая работа, и она встаёт отдельно.
    """
    каталог = каталог_очереди(site, корень=корень)
    каталог.mkdir(parents=True, exist_ok=True)
    ключ = (заявка.get("revision"), заявка.get("artifact_sha256"),
            заявка.get("generation"))
    for существующая in sorted(каталог.glob("*.json")):
        try:
            прежняя = json.loads(существующая.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        if (прежняя.get("revision"), прежняя.get("artifact_sha256"),
                прежняя.get("generation")) == ключ:
            return {"merged_into": прежняя.get("deployment_id"),
                    "path": str(существующая), "queued": False}
    путь = каталог / f"{заявка['deployment_id']}.json"
    временный = путь.with_suffix(".json.tmp")
    временный.write_text(json.dumps(заявка, ensure_ascii=False, indent=2) + "\n",
                         encoding="utf-8")
    os.chmod(временный, 0o664)
    os.replace(временный, путь)
    return {"path": str(путь), "queued": True,
            "deployment_id": заявка["deployment_id"]}


def снять(site: str, *, корень: Path | None = None) -> dict | None:
    """Снять следующую заявку витрины. Снятая в очередь не возвращается.

    Возврат снятой заявки и есть воскрешение: приёмщик падал, поднимался и
    продолжал работу, которую барьер уже вытеснил. Снятое уходит в `taken/` и
    оттуда не берётся никогда — только читается для отчёта.
    """
    каталог = каталог_очереди(site, корень=корень)
    if not каталог.is_dir():
        return None
    файлы = sorted(каталог.glob("*.json"))
    if not файлы:
        return None
    первый = файлы[0]
    данные = json.loads(первый.read_text(encoding="utf-8"))
    принятые = (корень or БАЗА) / "taken" / _сайт(site)
    принятые.mkdir(parents=True, exist_ok=True)
    метка = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    первый.replace(принятые / f"{первый.stem}.{метка}.json")
    return данные


def ожидает(site: str, *, корень: Path | None = None) -> list[str]:
    каталог = каталог_очереди(site, корень=корень)
    if not каталог.is_dir():
        return []
    return sorted(п.stem for п in каталог.glob("*.json"))


__all__ = ["QueueError", "СЕМАФОР_ТЯЖЁЛЫХ", "замок", "поставить", "снять",
           "ожидает", "каталог_очереди", "каталог_замков"]
