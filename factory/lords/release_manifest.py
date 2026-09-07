"""Совместимость: модуль переехал в домен релизов.

Псевдоним, а не копия: прежнее имя указывает на тот же объект модуля. Здесь это
особенно важно — на `factory.lords.release_manifest` ссылается закреплённая оснастка
боевых витрин, и ломать этот путь нельзя.
"""
from __future__ import annotations

import sys

from factory.releases import release_manifest as _модуль

sys.modules[__name__] = _модуль
