"""Единый модуль оценок 1–10.

Три вида оценок живут раздельно и не перезаписывают друг друга:

* ``external``  — снимки рейтингов разрешённых внешних источников;
* ``community`` — оценки посетителей, целое 1–10, одна активная на identity;
* ``editorial`` — наша редакционная оценка, целое 1–10, только по RBAC.

Раздельность — свойство схемы, а не соглашение вызывающего кода: у каждого
вида своя таблица, свой путь записи и свой ключ. Ни одна запись одного вида
не может оказаться в таблице другого, поэтому «редакционная оценка выдала
себя за пользовательскую» — не ошибка, которую нужно ловить проверкой, а
состояние, которого в этой схеме не существует.
"""

from __future__ import annotations

MODULE_VERSION = "unified-ratings/1.0.0"

#: Внутренняя нормализованная шкала. 0 в неё не входит: ноль означает
#: «оценки нет», а не «оценка ноль», и эти состояния не должны совпадать.
SCALE_MIN = 1.0
SCALE_MAX = 10.0

#: Версии адаптеров — попадают в provenance каждого снимка.
ADAPTER_VERSION_ANILIST = "anilist-graphql/1.0.0"
ADAPTER_VERSION_KITSU = "kitsu-jsonapi/1.0.0"
ADAPTER_VERSION_SIMKL = "simkl-rest/1.0.0"
ADAPTER_VERSION_SHIKIMORI = "shikimori-graphql/1.0.0"
ADAPTER_VERSION_PROVIDER_FEED = "provider-feed/1.0.0"

__all__ = [
    "MODULE_VERSION",
    "SCALE_MIN",
    "SCALE_MAX",
    "ADAPTER_VERSION_ANILIST",
    "ADAPTER_VERSION_KITSU",
    "ADAPTER_VERSION_SIMKL",
    "ADAPTER_VERSION_SHIKIMORI",
    "ADAPTER_VERSION_PROVIDER_FEED",
]
