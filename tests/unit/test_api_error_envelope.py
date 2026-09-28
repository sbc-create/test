"""REQ-API-ENVELOPE: поле `error` в ответе означает отказ, и только отказ.

Вызывающий отличает отказ от ответа по форме `body["error"]["code"]`. Успешный
ответ, положивший под тем же именем строку, ломает эту форму — и разбор падает
не там, где ошибся автор ответа, а у того, кто его читает.

Найдено на живом примере: реестр шаблонов отдавал `"error": ""` как «ошибок
чтения нет», и проверка описания маршрутов упала с `AttributeError` на строке.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from factory.site_engine.api.control import ControlApi
from factory.site_engine.api.openapi import ЗАПИСЬ

ROOT = Path(__file__).resolve().parents[2]
ENV = {"SITE_ENGINE_CONTROL_TOKENS": "t=read,jobs:write,config:write,review:write"}
H = {"Authorization": "Bearer t"}

ЧИТАЮЩИЕ = sorted(
    п for п, о in ЗАПИСЬ.items()
    if str(о.get("method", "")).lower() == "get" and "{" not in п
)


@pytest.fixture
def api():
    return ControlApi(root=ROOT, env=ENV)


def test_есть_что_проверять():
    assert ЧИТАЮЩИЕ, "в договоре нет читающих маршрутов без параметров"


@pytest.mark.parametrize("путь", ЧИТАЮЩИЕ)
def test_успешный_ответ_не_занимает_поле_error(api, путь):
    ответ = api.handle("GET", путь, headers=H, body=None)
    if ответ.status != 200:
        return
    поле = (ответ.body or {}).get("error")
    assert поле is None or isinstance(поле, dict), (
        f"{путь}: успешный ответ положил в error {type(поле).__name__} — "
        "вызывающий отличает отказ от ответа по форме error.code")


def test_отказ_несёт_объект_error(api):
    ответ = api.handle("GET", "/api/v1/чего-нет", headers=H, body=None)
    assert ответ.status >= 400
    assert isinstance(ответ.body["error"], dict)
    assert ответ.body["error"].get("code")
