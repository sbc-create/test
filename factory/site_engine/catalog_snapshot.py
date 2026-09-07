"""Чтение снимка каталога витрины: файл поставщика и его возраст.

Способность принадлежит домену каталога, а не управляющему контуру. Жила она в
`api/overview.py`, и домен каталога брал её оттуда по приватному имени —
направление было перевёрнуто дважды: контур управления обязан зависеть от
доменов, а не они от него, и берётся интерфейс, а не устройство.

Перенос сделан без единой правки логики. Поведение закреплено
`tests/unit/test_site_catalog_read.py` — теми же девятью проверками, что были
написаны до переноса.
"""
from __future__ import annotations

import datetime as dt
import json
import os
from pathlib import Path
from typing import Any


def _сейчас() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


def снимок(root: Path | str, env: dict[str, str] | None, site_id: str
           ) -> tuple[Any | None, int | None]:
    """Каталог витрины и его возраст в секундах.

    `(None, None)` означает «источник недоступен» и покрывает четыре разных
    случая: подкаталог не задан, задан пустой строкой, файла нет, файл не
    разбирается. Все четыре — отсутствие данных, а не пустой каталог, и
    подменять их пустым списком нельзя.
    """
    env = env if env is not None else os.environ
    подкаталог = str(env.get("SITE_ENGINE_CATALOG_DIR", "")).strip()
    if not подкаталог:
        return None, None
    # Путь может быть абсолютным: каталог поставщика законно живёт вне
    # репозитория, и приклеивать к нему корень значило бы искать var/...
    # внутри /srv/....
    основа = Path(подкаталог)
    if not основа.is_absolute():
        основа = Path(root) / основа
    путь = основа / f"{site_id}.json"
    if not путь.is_file():
        return None, None
    try:
        данные = json.loads(путь.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None, None
    # Возраст не бывает отрицательным: файл из будущего случается при
    # рассинхронизации часов, и «свежесть из будущего» читалась бы как ошибка
    # измерения там, где её нет.
    возраст = max(0, int(_сейчас().timestamp() - путь.stat().st_mtime))
    return данные, возраст
