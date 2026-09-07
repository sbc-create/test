"""Совместимость: модуль переехал в домен релизов.

Псевдоним, а не копия: прежнее имя указывает на тот же объект модуля. Здесь это
особенно важно — на `factory.lords.refresh_release` ссылается закреплённая оснастка
боевых витрин, и ломать этот путь нельзя.
"""
from __future__ import annotations

import sys

from factory.releases import refresh_release as _модуль

sys.modules[__name__] = _модуль
