"""Совместимость: модуль переехал в домен содержимого.

Псевдоним, а не копия: прежнее имя указывает на тот же объект модуля.

Обёртка временная: снять её можно, когда последний потребитель перейдёт на
`factory.site_engine.catalog.catalog_identity`, и не раньше.
"""
from __future__ import annotations

import sys

from factory.site_engine.catalog import catalog_identity as _модуль

sys.modules[__name__] = _модуль
