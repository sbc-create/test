"""Канонический контур предложения SEO-контента.

Путь: снимок фактов реестра → замысел авторства → черновик модели →
каноническое предложение → набор изменений → журнал.

Модель порождает содержимое и не делает ни одной устойчивой записи.
Каноническую запись выполняет control-plane и только он.
"""
from __future__ import annotations

import os as _os


def подключить_адаптер(путь: str | None = None) -> None:
    """Зарегистрировать адаптер SEO в контуре изменений.

    Вызывается явно. Молчаливая регистрация при импорте однажды подключила бы
    адаптер туда, где его не ждали, и `changeset.adapter.seo` считался бы
    доступным там, где исполнять нечем.
    """
    from factory.site_engine.changeset import adapter as _A
    from .adapter import SeoContentAdapter
    if SeoContentAdapter.resource_type in _A.РЕЕСТР:
        return
    _A.зарегистрировать(SeoContentAdapter.resource_type,
                        SeoContentAdapter(путь))


def адаптер_подключён() -> bool:
    from factory.site_engine.changeset import adapter as _A
    from .adapter import SeoContentAdapter
    return SeoContentAdapter.resource_type in _A.РЕЕСТР


if _os.environ.get("SEO_ENABLE_CONTENT_ADAPTER") == "1":
    подключить_адаптер()
