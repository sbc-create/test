"""Канонический контур изменений Control Plane.

Один набор изменений проходит путь: предложение, валидация, одобрение,
применение, проверка, при необходимости откат. Второго реестра, второго
журнала и параллельного хранилища состояния здесь нет намеренно.
"""


import os as _os


def подключить_тестовый_адаптер() -> None:
    """Зарегистрировать детерминированный адаптер для испытаний.

    Вызывается только при CHANGESET_ENABLE_FAKE_ADAPTER=1. В рабочем контуре
    реестр адаптеров пуст, и это не упущение: механизм доказывается до того,
    как к нему подводят то, что способно что-то испортить.
    """
    from . import adapter, fake_adapter
    if fake_adapter.FakeAdapter.resource_type in adapter.РЕЕСТР:
        return
    adapter.зарегистрировать(fake_adapter.FakeAdapter.resource_type,
                             fake_adapter.FakeAdapter())


if _os.environ.get("CHANGESET_ENABLE_FAKE_ADAPTER") == "1":
    подключить_тестовый_адаптер()
