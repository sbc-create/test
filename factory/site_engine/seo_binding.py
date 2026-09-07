"""Совместимость: модуль переехал в домен insights.

Псевдоним, а не копия: прежнее имя указывает на тот же объект модуля.

Обёртка временная: снять её можно, когда последний потребитель перейдёт на
`factory.site_engine.insights.seo_binding`, и не раньше.
"""
from __future__ import annotations

import sys

from factory.site_engine.insights import seo_binding as _модуль

sys.modules[__name__] = _модуль
