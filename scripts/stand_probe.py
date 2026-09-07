#!/usr/bin/env python3
"""Чтение страниц стенда — одна реализация на все аудиты витрин.

`fetch` был выписан дословно дважды: в `lords_live_defects.py` и
`lords_release_baseline.py`. Совпадали и сроки, и обработка отказов — совпадали
случайно, и ничто не мешало одной копии разойтись.

Расхождение здесь тихое и дорогое. Аудит, у которого отказ HTTP превращается в
пустую строку, а у соседнего — в исключение, даёт разные отчёты об одном и том
же стенде, и разница читается как разница витрин.

Возвращается пара «код ответа, тело». `None` в коде означает, что ответа не
было вовсе: соединение не состоялось, имя не разрешилось, вышел срок. Это
отдельное состояние, и путать его с ответом сервера нельзя.
"""

from __future__ import annotations

import urllib.error
import urllib.parse
import urllib.request

TIMEOUT = 30


def fetch(base: str, path: str, *, timeout: int = TIMEOUT) -> tuple[int | None, str]:
    """Одна страница стенда. Отказ — состояние, а не исключение.

    Путь кодируется: в адресах витрин встречается кириллица, и без кодирования
    запрос не уходит вовсе.
    """
    try:
        with urllib.request.urlopen(base + urllib.parse.quote(path), timeout=timeout) as r:
            return r.status, r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as error:
        # Ответ сервера, пусть и с кодом ошибки: тело у него есть и оно значимо.
        return error.code, error.read().decode("utf-8", "replace")
    except (urllib.error.URLError, OSError) as error:
        return None, str(error)[:160]


__all__ = ["TIMEOUT", "fetch"]
