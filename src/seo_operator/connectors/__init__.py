"""Реестр коннекторов. Импорт модулей здесь обязателен: без него registry пуст
и `build()` падает на KeyError, а цикл молча остаётся без данных."""
from .base import Connector, ConnectorResult, NotConfigured, build, registry
from . import search_console as _search_console   # noqa: F401  (регистрация)
from . import yandex as _yandex                   # noqa: F401  (регистрация)

__all__ = ["Connector", "ConnectorResult", "NotConfigured", "build", "registry"]
