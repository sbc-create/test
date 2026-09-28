"""Шаблонный контракт направления Lords.

Пакет описывает то, что уже работает: манифест шаблона, реестр блоков главной,
проверки манифеста и scaffold нового шаблона. Ничего, кроме этого, здесь нет —
ingestion, Content API и служебная логика шаблону не принадлежат и при создании
нового шаблона не копируются.
"""

from factory.templates.contract import (  # noqa: F401
    BLOCKS,
    Block,
    Problem,
    load_manifest,
    renderer_blocks,
    validate_manifest,
    validate_repository,
)
