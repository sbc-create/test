"""Ключи устройств «Кинатеки»: доступ к каталогу без служебного ключа в APK и без adb.

Пишет `devices.json` Control API (`factory/site_engine/api/app_devices.py`), служба
только читает. Сторожится:

* формулы совпадают с Control API — общий тестовый вектор;
* код из панели обменивается на ключ устройства один раз и не после срока;
* ключ устройства открывает каталог, отозванный — нет, со следующего запроса;
* любой неподходящий код получает один и тот же ответ; попытки ограничены;
* сломанный файл устройств доступа не открывает, служебный ключ работает как прежде.
"""
from __future__ import annotations

import importlib.util
import json
import os
import time
import urllib.error
import urllib.request
from pathlib import Path

import pytest

_спец = importlib.util.spec_from_file_location(
    "test_app_read_api_base", Path(__file__).with_name("test_app_read_api.py"))
_основа = importlib.util.module_from_spec(_спец)
_спец.loader.exec_module(_основа)
гет, снимок, служба = _основа.гет, _основа.снимок, _основа.служба
ТАЙТЛ = f"/api/app/v1/titles/{_основа.СЕРИАЛ}"

# Тот же вектор, что в tests/unit/test_admin_kinateka.py (Control API).
СОЛЬ, СЫРОЙ, КОД = bytes(range(16)), bytes(range(100, 124)), "KQ7M4TXP"
ХЭШ_КОДА = "4d6be1c1f88b12fa162d0e39bfa95dd40c335d9fb89df2f189f4f9567d08bab5"
ЗАПЕЧАТАН = "d252fd4e6c9397610adb6273dfd834c4a4957e744c348c42"
ХЭШ_КЛЮЧА = "d58a90fb7915022bfc0a36efbc80eb3b938bb72e32e0bfd0d30572012cafbe05"
КЛЮЧ_УСТРОЙСТВА = "dk_" + СЫРОЙ.hex()


def записать(корень: Path, устройства: list[dict]) -> None:
    путь = корень / "devices.json"
    путь.write_text(json.dumps({"schema": "kinateka-devices/1", "devices": устройства}), encoding="utf-8")
    ст = путь.stat()
    os.utime(путь, ns=(ст.st_atime_ns, ст.st_mtime_ns + int(time.time_ns() % 10**6) + 1))


def устройство(*, срок: str = "2099-01-01T00:00:00Z", отозвано=None) -> dict:
    return {"id": "d-0123456789ab", "name": "Телевизор", "keyHash": ХЭШ_КЛЮЧА, "revokedAt": отозвано,
            "code": None if отозвано else {"salt": СОЛЬ.hex(), "hash": ХЭШ_КОДА, "sealed": ЗАПЕЧАТАН,
                                           "expiresAt": срок}}


def пост(база: str, тело, путь="/api/app/v1/activate"):
    данные = тело if isinstance(тело, bytes) else json.dumps(тело).encode()
    запрос = urllib.request.Request(база + путь, data=данные, method="POST",
                                    headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(запрос, timeout=20) as о:
            return о.status, json.loads(о.read()), dict(о.headers)
    except urllib.error.HTTPError as ош:
        return ош.code, json.loads(ош.read()), dict(ош.headers)


@pytest.fixture()
def с_устройствами(служба, tmp_path):
    м, база = служба
    корень = tmp_path / "app-config"
    корень.mkdir()
    м.Обработчик.устройства = м.ХранилищеУстройств(корень)
    м.Обработчик.активации = {}
    yield м, база, корень
    м.Обработчик.устройства = None


def test_формулы_по_общему_вектору(служба):
    м, _ = служба
    assert м._хэш_кода(СОЛЬ, КОД) == ХЭШ_КОДА
    assert м._распечатать(ЗАПЕЧАТАН, СОЛЬ, КОД) == КЛЮЧ_УСТРОЙСТВА
    assert м.хэш_ключа(КЛЮЧ_УСТРОЙСТВА) == ХЭШ_КЛЮЧА
    assert м.нормальный_код(" kq7m-4txp ") == КОД


def test_код_меняется_на_ключ_один_раз_и_ключ_открывает_каталог(с_устройствами):
    _, база, корень = с_устройствами
    записать(корень, [устройство()])
    assert гет(база, ТАЙТЛ, {"X-App-Key": КЛЮЧ_УСТРОЙСТВА})[0] == 200
    код, тело, заг = пост(база, {"code": "kq7m-4txp"})
    assert код == 200 and тело == {"key": КЛЮЧ_УСТРОЙСТВА, "deviceId": "d-0123456789ab", "name": "Телевизор"}
    assert заг.get("Cache-Control") == "no-store"
    повтор = пост(база, {"code": КОД})
    assert повтор[0] == 403 and повтор[1]["error"]["code"] == "invalid_code"


def test_отзыв_действует_со_следующего_запроса(с_устройствами):
    _, база, корень = с_устройствами
    записать(корень, [устройство()])
    assert гет(база, ТАЙТЛ, {"X-App-Key": КЛЮЧ_УСТРОЙСТВА})[0] == 200
    записать(корень, [устройство(отозвано="2026-10-29T10:00:00Z")])
    assert гет(база, ТАЙТЛ, {"X-App-Key": КЛЮЧ_УСТРОЙСТВА})[0] == 401
    # служебный ключ не задет
    assert гет(база, ТАЙТЛ)[0] == 200


def test_истёкший_неверный_и_чужой_код_отвечают_одинаково(с_устройствами):
    _, база, корень = с_устройствами
    записать(корень, [устройство(срок="2020-01-01T00:00:00Z")])
    ответы = [пост(база, {"code": к}) for к in (КОД, "ABCD2345", "короткий", "")]
    assert {(к, т["error"]["code"]) for к, т, _ in ответы[:2]} == {(403, "invalid_code")}
    assert ответы[2][0] == 403 and ответы[3][0] == 403
    assert пост(база, {"кот": 1})[0] == 400
    assert пост(база, b"not json")[0] == 400
    assert пост(база, {"code": КОД}, путь="/api/app/v1/titles")[0] == 404


def test_попытки_ограничены(с_устройствами):
    м, база, корень = с_устройствами
    записать(корень, [устройство()])
    коды = [пост(база, {"code": "ABCD2345"})[0] for _ in range(м.ПРЕДЕЛ_АКТИВАЦИЙ_В_МИНУТУ)]
    assert set(коды) == {403}
    # верный код после исчерпания предела тоже ждёт — предел не подсказывает, какой код верный
    assert пост(база, {"code": КОД})[0] == 429


def test_сломанный_файл_не_открывает_доступ(с_устройствами):
    _, база, корень = с_устройствами
    (корень / "devices.json").write_text("{не json", encoding="utf-8")
    assert гет(база, ТАЙТЛ, {"X-App-Key": КЛЮЧ_УСТРОЙСТВА})[0] == 401
    assert пост(база, {"code": КОД})[0] == 403
    код, тело, _ = гет(база, "/healthz")
    assert код == 200 and тело["devicesError"] and тело["devicesActive"] == 0
    assert гет(база, ТАЙТЛ)[0] == 200


def test_ключ_без_префикса_устройства_не_сверяется_с_устройствами(с_устройствами):
    _, база, корень = с_устройствами
    записать(корень, [устройство()])
    assert гет(база, ТАЙТЛ, {"X-App-Key": СЫРОЙ.hex()})[0] == 401
