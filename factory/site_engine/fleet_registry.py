"""Совместимость: модуль переехал в домен fleet.

Псевдоним, а не копия: прежнее имя указывает на тот же объект модуля.

Обёртка временная: снять её можно, когда последний потребитель перейдёт на
`factory.site_engine.fleet.fleet_registry`, и не раньше.
"""
from __future__ import annotations

import sys

from factory.site_engine.fleet import fleet_registry as _модуль

sys.modules[__name__] = _модуль
