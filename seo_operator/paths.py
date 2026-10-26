"""Корни путей служб SEO-оператора (MOD-198).

Код, состояние служб и живые реестры при переносе служб в выпуск уезжают в
разные стороны, поэтому корней три:

* ``CODE_ROOT`` — где лежит этот код (выпуск или рабочая копия). Отсюда —
  схемы, сценарии и настройки поведения (задания редактора, ``config/editor-run.json``):
  откат выпуска ссылкой правильно откатывает и их.
* ``SEO_STATE_ROOT`` — состояние служб: ``var/`` и ``artifacts/``. Писатель и
  читатель одного файла берут этот корень, а не свою переменную.
* ``SEO_REGISTRY_ROOT`` — живые реестры (очередь техзадач, опыты, ячейки,
  аналитика, источники, недостатки, журнал изменений, портфель). Их правят
  сессии через git, а службы читают. **Корень обязан быть рабочей копией под
  git и никогда — каталогом выпуска**: служба с замороженной копией очереди не
  видит новых задач и молча расходится с сессиями, а ``git -C`` по каталогу
  выпуска отказывает. Нарушение — ``RegistryRootError`` при первом обращении к
  реестру, а не тихое чтение старых данных.

Без переменных оба корня равны корню кода — поведение прежнее, шаг обратим.
"""
from __future__ import annotations

import os
from pathlib import Path

CODE_ROOT = Path(__file__).resolve().parents[1]


class RegistryRootError(RuntimeError):
    """Живые реестры читаются не из рабочей копии под git."""


def _корень(имя: str) -> Path:
    значение = os.environ.get(имя)
    return Path(значение).resolve() if значение else CODE_ROOT


def state_root() -> Path:
    return _корень("SEO_STATE_ROOT")


def registry_root() -> Path:
    корень = _корень("SEO_REGISTRY_ROOT")
    # Рабочая копия: .git — каталог (основная копия) или файл (git worktree).
    if not (корень / ".git").exists():
        raise RegistryRootError(
            f"живые реестры читаются из {корень}, а это не рабочая копия под git "
            "(каталог выпуска?). Задайте SEO_REGISTRY_ROOT — путь к рабочей копии")
    return корень


def state(*части: str) -> Path:
    return state_root().joinpath(*части)


def registry(*части: str) -> Path:
    return registry_root().joinpath(*части)


def code(*части: str) -> Path:
    return CODE_ROOT.joinpath(*части)
