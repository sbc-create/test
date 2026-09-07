"""Совместимость: модуль переехал в домен job_runtime.

Псевдоним, а не копия: прежнее имя указывает на тот же объект модуля.

Обёртка временная: снять её можно, когда последний потребитель перейдёт на
`factory.job_runtime.state`, и не раньше.
"""
from __future__ import annotations

import sys

from factory.job_runtime import state as _модуль

sys.modules[__name__] = _модуль
