"""Реестр версий артефакта: каждая версия зарегистрирована и не понижается.

Проверка появилась после разбора расхождения в отчётах: в одном значилась
версия 26, в другом 18. Отката не было — 26 не существовало никогда, максимум
по всем ревизиям таблицы равен 18, а число попало в отчёт вписанным вручную,
минуя манифест.

Но за этим расхождением стояла настоящая поломка. Перепин выходил раньше
времени, если отпечаток в предполётной проверке уже совпадал с деревом, и
запись в таблицу версий не добавлялась — молча, с сообщением об успехе.
Отпечаток оказывался закреплён и неизвестен реестру.

Эти проверки закрывают оба случая: отпечаток дерева обязан быть в реестре, а
номера — расти без повторов и пропусков. Число в отчёте после них берётся из
таблицы, а не из памяти.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from factory.templates import digest as digest_mod  # noqa: E402
from scripts.release_input_audit import ARTIFACT_VERSIONS  # noqa: E402

APPLY = ROOT / "automation" / "host" / "lords-canary-apply.sh"


def test_отпечаток_дерева_зарегистрирован():
    """Артефакт, которого нет в реестре, нельзя ни назвать, ни откатить."""
    fingerprint = digest_mod.compute()["template_digest"]
    assert fingerprint in ARTIFACT_VERSIONS, (
        f"отпечаток {fingerprint[:16]}… не зарегистрирован: "
        "запустите scripts/repin_artifact.py"
    )


def test_пин_предполётной_проверки_совпадает_с_деревом():
    """Расхождение пина и дерева останавливает canary — и должно."""
    fingerprint = digest_mod.compute()["template_digest"]
    assert f'EXPECT_DIGEST="{fingerprint}"' in APPLY.read_text(encoding="utf-8"), (
        "пин предполётной проверки отстал от дерева"
    )


def test_номера_версий_не_повторяются():
    """Два артефакта под одним номером — это неразрешимая ссылка при откате."""
    versions = list(ARTIFACT_VERSIONS.values())
    assert len(versions) == len(set(versions)), "номер версии выдан дважды"


def test_номера_идут_подряд_от_единицы():
    """Пропуск в нумерации означает потерянную регистрацию."""
    versions = sorted(ARTIFACT_VERSIONS.values())
    assert versions == list(range(1, len(versions) + 1)), (
        f"нумерация с пропусками: {versions}"
    )


def test_версия_дерева_наибольшая():
    """Понижение версии молча — то, чего проверка не должна допускать."""
    fingerprint = digest_mod.compute()["template_digest"]
    assert ARTIFACT_VERSIONS[fingerprint] == max(ARTIFACT_VERSIONS.values()), (
        "отпечаток дерева зарегистрирован не последней версией: "
        "либо реестр правили руками, либо произошёл откат"
    )


def test_все_ключи_реестра_являются_отпечатками():
    """Ключ не той формы означает правку руками, а не перепин."""
    плохие = [k for k in ARTIFACT_VERSIONS
              if len(k) != 64 or not all(c in "0123456789abcdef" for c in k)]
    assert плохие == [], f"в реестре не отпечатки: {плохие}"
