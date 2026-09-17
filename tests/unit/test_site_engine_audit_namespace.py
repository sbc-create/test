"""Пространство имён `factory.site_engine.audit`: один объект под одним именем.

Дефект, ради которого файл существует. В дереве одновременно оказались модуль
`factory/site_engine/audit.py` и пакет `factory/site_engine/audit/`. Пакет всегда
побеждает модуль с тем же именем, поэтому `audit.py` — единственное определение
`AuditEvent`, `AuditLog` и `event` — стал недостижим. Редакционный слой продолжал
импортировать эти имена, и сбор pytest падал целиком:

    ImportError: cannot import name 'AuditLog' from 'factory.site_engine.audit'

Один упавший импорт обрывает сбор всего набора, поэтому цена такой коллизии — не
один красный тест, а ноль выполненных.
"""
from __future__ import annotations

import importlib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
ДВИЖОК = ROOT / "factory" / "site_engine"


def test_модуль_и_пакет_не_делят_одно_имя():
    """Ни один пакет не затеняет одноимённый модуль рядом с собой."""
    коллизии = [
        каталог.name
        for каталог in sorted(ДВИЖОК.rglob("*"))
        if каталог.is_dir()
        and (каталог / "__init__.py").exists()
        and каталог.with_suffix(".py").exists()
    ]
    assert not коллизии, (
        f"пакет и модуль делят имя: {коллизии}; "
        "модуль при этом недостижим, а его содержимое — мёртвый код"
    )


def test_редакционный_слой_импортируется():
    """Сбор pytest не должен обрываться на импорте редакционного слоя."""
    модуль = importlib.import_module("factory.site_engine.editorial")
    assert модуль.EditorialService is not None


def test_журнал_аудита_достижим_и_дописывается():
    """`AuditLog`, на котором держится редакционный слой, работает, а не просто импортируется."""
    редакция = importlib.import_module("factory.site_engine.editorial")
    журнал = редакция.AuditLog()
    запись = редакция.audit_event(
        actor="tester", action="draft.create", subject="d:1", reason="регрессия"
    )
    журнал.record(запись)
    assert len(журнал) == 1
    assert журнал.for_actor("tester") == (запись,)
