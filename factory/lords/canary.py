"""Совместимость: модуль переехал в домен релизов.

Псевдоним, а не копия: прежнее имя указывает на тот же объект модуля. Здесь это
особенно важно — на `factory.lords.canary` ссылается закреплённая оснастка
боевых витрин, и ломать этот путь нельзя.
"""
from __future__ import annotations

import sys

from factory.releases import canary as _модуль

sys.modules[__name__] = _модуль
