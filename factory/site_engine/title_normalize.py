"""Совместимость: модуль переехал в домен содержимого.

Псевдоним, а не копия: прежнее имя указывает на тот же объект модуля.

Обёртка временная: снять её можно, когда последний потребитель перейдёт на
`factory.site_engine.catalog.title_normalize`, и не раньше.
"""
from __future__ import annotations

import sys

from factory.site_engine.catalog import title_normalize as _модуль

sys.modules[__name__] = _модуль
