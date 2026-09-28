"""Стандарт версии шаблона: релиз обязан описывать сам себя.

Манифесты отвечали на вопрос «какая ревизия» и молчали обо всём остальном.
Нельзя было ответить, та ли это версия шаблона, что на соседней витрине, из
того же ли артефакта собран релиз и какому поколению барьера принадлежит.
Каждый раз ответ добывался чтением чужих логов.
"""

from __future__ import annotations

import pytest

from automation.deploy import lords_version as v

ГОДНЫЙ = {
    "template_name": "lords_dark",
    "template_semver": "1.4.0",
    "template_revision": "a" * 40,
    "template_digest": "1" * 64,
    "artifact_sha256": "2" * 64,
    "content_snapshot_sha256": "3" * 64,
    "content_snapshot_at_utc": "2026-09-09T17:00:00Z",
    "site_config_sha256": "4" * 64,
    "generation": 3,
    "built_at_utc": "2026-09-09T18:00:00Z",
    "build_duration_seconds": 2100,
    "release_id": "31014bb44d6f",
    "previous_release_id": "8bc82400e443",
    "rollback_release_id": "8bc82400e443",
}


def test_полный_манифест_проходит():
    assert v.нарушения(dict(ГОДНЫЙ)) == []


@pytest.mark.parametrize("поле", v.ОБЯЗАТЕЛЬНЫЕ)
def test_отсутствие_любого_поля_это_нарушение(поле):
    манифест = dict(ГОДНЫЙ)
    манифест.pop(поле)
    беды = v.нарушения(манифест)
    assert any(поле in б for б in беды)


@pytest.mark.parametrize("версия", ["1.4", "v1.4.0", "latest", "", "1.4.0.1"])
def test_версия_не_semver_отвергается(версия):
    assert v.нарушения({**ГОДНЫЙ, "template_semver": версия})


def test_сокращённая_ревизия_отвергается():
    """Сокращение однажды указало на другой коммит — полный SHA или ничего."""
    assert v.нарушения({**ГОДНЫЙ, "template_revision": "a" * 12})


@pytest.mark.parametrize("поле", ["template_digest", "artifact_sha256",
                                  "content_snapshot_sha256", "site_config_sha256"])
def test_отпечатки_обязаны_быть_sha256(поле):
    assert v.нарушения({**ГОДНЫЙ, поле: "коротко"})


@pytest.mark.parametrize("поколение", [0, -1, "3", True, None])
def test_поколение_обязано_быть_целым_и_положительным(поколение):
    assert v.нарушения({**ГОДНЫЙ, "generation": поколение})


def test_пустая_цель_отката_при_истории_это_нарушение():
    assert v.нарушения({**ГОДНЫЙ, "rollback_release_id": ""})


def test_первый_релиз_витрины_может_не_иметь_цели_отката():
    """Требовать её от первого релиза значило бы требовать её выдумать."""
    assert v.нарушения({**ГОДНЫЙ, "previous_release_id": "",
                        "rollback_release_id": ""}) == []
