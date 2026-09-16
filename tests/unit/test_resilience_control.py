"""REQ-RESILIENCE: перезапуск и конкуренция не превращаются в тихую порчу.

Три случая, каждый из которых уже случался в этом контуре или в соседних:

**Перезапуск между попытками.** Служба повторяет запрос, а между попытками её
перезапустили. Если память о ключе повтора жила только в процессе, повтор
выполнится второй раз — и второй раз уже поверх изменившегося состояния.

**Одновременные операции по одной витрине.** Обновление каталога и правка
настроек идут параллельно. Записать поверх — потерять чужое изменение и не
сообщить об этом ни одной из сторон.

**Отказ на середине.** Операция прервалась после проверки, но до записи.
Витрина обязана остаться на прежнем состоянии целиком, а не наполовину.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from factory import locks
from factory.paths import PATHS
from factory.site_engine.api.control import ControlApi

REPO = Path(__file__).resolve().parents[2]
САЙТ = "lords-01"
ТОКЕН = "tok-rw"
ENV = {
    "SITE_ENGINE_CONTROL_WRITES": "1",
    "SITE_ENGINE_CONTROL_TOKENS": f"{ТОКЕН}=read,config:write",
}
ЗАГОЛОВКИ = {"Authorization": f"Bearer {ТОКЕН}"}


@pytest.fixture
def песочница(tmp_path, monkeypatch):
    monkeypatch.setattr(PATHS, "root", tmp_path)
    профили = tmp_path / "config" / "site-profiles"
    профили.mkdir(parents=True)
    образец = json.loads(
        (REPO / "config" / "site-profiles" / f"{САЙТ}.json").read_text(encoding="utf-8"))
    (профили / f"{САЙТ}.json").write_text(json.dumps(образец, ensure_ascii=False),
                                          encoding="utf-8")
    for под in ("var/audit", "var/state", "var/locks", "queue/inbox"):
        (tmp_path / под).mkdir(parents=True, exist_ok=True)
    return tmp_path


def _api(песочница):
    """Новый экземпляр — это и есть перезапуск службы для наших целей."""
    return ControlApi(root=песочница, env=ENV)


def _патч(api, changes, ключ=None, **ещё):
    заголовки = dict(ЗАГОЛОВКИ)
    if ключ:
        заголовки["idempotency-key"] = ключ
    return api.handle("PATCH", f"/api/v1/sites/{САЙТ}/settings", headers=заголовки,
                      body={"changes": changes, **ещё})


def _профиль(песочница):
    return json.loads(
        (песочница / "config" / "site-profiles" / f"{САЙТ}.json").read_text(encoding="utf-8"))


def test_повтор_переживает_перезапуск_службы(песочница):
    первый = _патч(_api(песочница), {"keep_releases": 5}, "restart-1")
    assert первый.body["applied"] is True

    # Служба перезапущена: новый экземпляр, новая память процесса.
    второй = _патч(_api(песочница), {"keep_releases": 5}, "restart-1")
    assert второй.body.get("idempotentReplay") is True, (
        "память о ключе жила только в процессе — повтор выполнился заново")
    assert _профиль(песочница)["keep_releases"] == 5


def test_занятая_витрина_отказывает_а_не_ждёт_вечно(песочница):
    api = _api(песочница)
    with locks.site_lock(САЙТ, "staging", timeout=1.0):
        ответ = _патч(api, {"keep_releases": 6})
    assert ответ.status == 409
    assert ответ.body["error"]["code"] == "site_busy"
    assert "keep_releases" not in _профиль(песочница), "изменение прошло мимо замка"


def test_после_освобождения_замка_операция_проходит(песочница):
    api = _api(песочница)
    with locks.site_lock(САЙТ, "staging", timeout=1.0):
        pass
    ответ = _патч(api, {"keep_releases": 7})
    assert ответ.status == 200 and ответ.body["applied"] is True


def test_конкурентная_правка_замечена_по_версии(песочница):
    api = _api(песочница)
    вид = api.handle("GET", f"/api/v1/settings/{САЙТ}", headers=ЗАГОЛОВКИ, body=None)
    версия = вид.body.get("configVersion") or vid_версия(вид)

    # Кто-то другой изменил профиль между чтением и записью.
    _патч(_api(песочница), {"keep_releases": 8})

    ответ = _патч(api, {"keep_releases": 9}, expectedVersion=версия)
    assert ответ.status == 409
    assert ответ.body["error"]["code"] == "version_conflict"
    assert _профиль(песочница)["keep_releases"] == 8, "чужое изменение потеряно"


def vid_версия(ответ) -> str:
    """Версия конфигурации из представления настроек, как бы её ни назвали."""
    тело = ответ.body or {}
    for имя in ("configVersion", "version", "currentVersion"):
        if тело.get(имя):
            return str(тело[имя])
    вложенное = тело.get("settings") or {}
    return str(вложенное.get("configVersion") or "")


def test_отказ_не_оставляет_половины(песочница):
    """Негодное значение среди годных не применяет ни одного."""
    api = _api(песочница)
    ответ = _патч(api, {"keep_releases": 5, "refresh_interval_minutes": 1})
    assert ответ.status == 422
    профиль = _профиль(песочница)
    assert "keep_releases" not in профиль or профиль.get("keep_releases") != 5, (
        "годное значение применено, хотя запрос отклонён целиком")
    assert "refresh_interval_minutes" not in профиль
