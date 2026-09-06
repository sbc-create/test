"""REQ-AI-READONLY: служебная учётная запись с правом чтения ничего не меняет.

Нейросети выдают токен, чтобы она могла посмотреть флот и предложить изменение.
Опасность здесь не в злом умысле, а в обычной ошибке: перепутанный маршрут,
повторённый пример из документации, вызов «на всякий случай». Поэтому право
чтения обязано быть именно правом чтения — не соглашением, а отказом.

Проверяется каждый изменяющий маршрут договора, а не выбранные вручную: маршрут,
о котором забыли, — это дыра ровно там, где её не искали.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from factory.paths import PATHS
from factory.site_engine.api import openapi
from factory.site_engine.api.control import ControlApi

REPO = Path(__file__).resolve().parents[2]
САЙТ = "lords-01"
ЧИТАТЕЛЬ = "tok-ro"
ПИСАТЕЛЬ = "tok-rw"

ENV = {
    "SITE_ENGINE_CONTROL_WRITES": "1",
    "SITE_ENGINE_CONTROL_TOKENS": (
        f"{ЧИТАТЕЛЬ}=read"
        f"|{ПИСАТЕЛЬ}=read,config:write,jobs:write,review:write,operators:write"
    ),
}
H_ЧИТАТЕЛЬ = {"Authorization": f"Bearer {ЧИТАТЕЛЬ}"}
H_ПИСАТЕЛЬ = {"Authorization": f"Bearer {ПИСАТЕЛЬ}"}


@pytest.fixture
def песочница(tmp_path, monkeypatch):
    monkeypatch.setattr(PATHS, "root", tmp_path)
    профили = tmp_path / "config" / "site-profiles"
    профили.mkdir(parents=True)
    образец = json.loads(
        (REPO / "config" / "site-profiles" / f"{САЙТ}.json").read_text(encoding="utf-8"))
    (профили / f"{САЙТ}.json").write_text(json.dumps(образец, ensure_ascii=False),
                                          encoding="utf-8")
    for под in ("var/audit", "var/state", "var/locks", "queue/inbox", "artifacts/jobs"):
        (tmp_path / под).mkdir(parents=True, exist_ok=True)
    return tmp_path


@pytest.fixture
def api(песочница):
    return ControlApi(root=песочница, env=ENV)


def _изменяющие() -> list[tuple[str, str]]:
    из = []
    for путь, о in openapi.ЗАПИСЬ.items():
        метод = str(о.get("method", "")).upper()
        if метод in ("POST", "PATCH", "PUT", "DELETE"):
            из.append((метод, путь.replace("{siteId}", САЙТ).replace("{jobId}", "job-1")))
    return sorted(set(из))


ИЗМЕНЯЮЩИЕ = _изменяющие()

#: Маршруты, у которых пробный прогон доступен по праву чтения — с причиной.
#:
#: Правило простое: пробный прогон требует того же права, что и сама операция,
#: **кроме** случая, когда он читает ровно то, что читателю и так доступно
#: другим маршрутом. Групповой предпросмотр разбора смотрит в очередь, которую
#: читатель открывает через GET; запрещать ему тот же взгляд под другим адресом
#: значило бы охранять не данные, а форму запроса.
#:
#: Исключение названо здесь, а не растворено в коде: молчаливое исключение
#: неотличимо от забытой проверки.
ЧТЕНИЕ_ДОПУСКАЕТСЯ = {
    ("POST", "/api/v1/review-queue/batch"):
        "пробный прогон читает очередь разбора, доступную читателю через GET",
}


def test_договор_вообще_содержит_изменяющие_маршруты():
    assert ИЗМЕНЯЮЩИЕ, "в договоре нет изменяющих маршрутов — проверка бессмысленна"


@pytest.mark.parametrize("метод,путь", ИЗМЕНЯЮЩИЕ, ids=lambda з: str(з))
def test_читающий_токен_не_допускается_ни_к_одному_изменению(api, метод, путь):
    ответ = api.handle(метод, путь, headers=H_ЧИТАТЕЛЬ, body={})
    причина = ЧТЕНИЕ_ДОПУСКАЕТСЯ.get((метод, путь))
    if причина and ответ.status == 200:
        # Допущено осознанно — и допущено может быть только чтение.
        assert ответ.body.get("dryRun") is True, (
            f"{метод} {путь}: исключение объявлено для пробного прогона, "
            f"а маршрут вернул не пробный прогон ({причина})")
        return
    assert ответ.status != 200, f"{метод} {путь}: изменение принято токеном на чтение"
    код = (ответ.body.get("error") or {}).get("code", "")
    assert ответ.status in (400, 401, 403, 404, 405, 409, 422), (
        f"{метод} {путь}: неожиданный код {ответ.status} ({код})")


def test_настройки_не_меняются_читающим_токеном(api, песочница):
    путь = песочница / "config" / "site-profiles" / f"{САЙТ}.json"
    было = путь.read_bytes()
    ответ = api.handle("PATCH", f"/api/v1/sites/{САЙТ}/settings", headers=H_ЧИТАТЕЛЬ,
                       body={"changes": {"keep_releases": 9}})
    assert ответ.status == 403
    assert путь.read_bytes() == было, "профиль изменён токеном на чтение"


def test_пишущий_токен_меняет_и_это_видно(api, песочница):
    """Обратная сторона проверки: запрет обязан быть про право, а не про поломку."""
    ответ = api.handle("PATCH", f"/api/v1/sites/{САЙТ}/settings", headers=H_ПИСАТЕЛЬ,
                       body={"changes": {"keep_releases": 9}})
    assert ответ.status == 200 and ответ.body["applied"] is True
    профиль = json.loads(
        (песочница / "config" / "site-profiles" / f"{САЙТ}.json").read_text(encoding="utf-8"))
    assert профиль["keep_releases"] == 9


def test_читающий_токен_видит_флот(api):
    """Право чтения обязано оставаться правом чтения — не запретом смотреть."""
    ответ = api.handle("GET", "/api/v1/fleet", headers=H_ЧИТАТЕЛЬ, body=None)
    assert ответ.status == 200
    assert ответ.body["total"] >= 1


def test_сухой_прогон_читающему_токену_тоже_закрыт(api):
    """Пробный запуск ничего не меняет, но и он требует права менять.

    Разница существенная: dry-run показывает разницу с текущим состоянием, то
    есть отвечает на вопрос «что будет, если применю». Тому, кто применять не
    вправе, этот ответ не нужен, а вот утечка текущих значений — вполне.
    """
    ответ = api.handle("PATCH", f"/api/v1/sites/{САЙТ}/settings", headers=H_ЧИТАТЕЛЬ,
                       body={"changes": {"keep_releases": 9}, "dryRun": True})
    assert ответ.status == 403


def test_отказ_называет_причину_а_не_молчит(api):
    ответ = api.handle("PATCH", f"/api/v1/sites/{САЙТ}/settings", headers=H_ЧИТАТЕЛЬ,
                       body={"changes": {"keep_releases": 9}})
    ошибка = ответ.body.get("error") or {}
    assert ошибка.get("code"), "отказ без кода: вызывающему нечего разбирать"
    assert ошибка.get("message"), "отказ без объяснения"
    assert ответ.body.get("correlationId"), "отказ без correlation id: инцидент не связать"


def _очередь_на_диске(песочница) -> dict[str, bytes]:
    """Содержимое очереди разбора. Сравнивается содержимое, а не список файлов.

    Обращение к API само по себе заводит трассировку и создаёт пустые каталоги
    состояния — это устройство запроса, а не действие пробного прогона.
    Требовать неизменности всего каталога значило бы проверять не то.
    """
    основа = песочница / "var" / "state" / "review-queue"
    return {str(p.relative_to(основа)): p.read_bytes()
            for p in основа.rglob("*") if p.is_file()}


def test_исключение_для_чтения_действительно_ничего_не_меняет(api, песочница):
    """Проверка самого исключения: пробный прогон обязан остаться чтением."""
    api.handle("GET", "/api/v1/review-queue", headers=H_ЧИТАТЕЛЬ, body=None)
    было = _очередь_на_диске(песочница)
    ответ = api.handle("POST", "/api/v1/review-queue/batch", headers=H_ЧИТАТЕЛЬ,
                       body={"mode": "dryRun", "conflictCode": "x",
                             "fromValue": "a", "toValue": "b"})
    assert ответ.status == 200 and ответ.body.get("dryRun") is True
    assert _очередь_на_диске(песочница) == было, "пробный прогон изменил очередь разбора"


def test_применение_группового_действия_читателю_закрыто(api):
    ответ = api.handle("POST", "/api/v1/review-queue/batch", headers=H_ЧИТАТЕЛЬ,
                       body={"mode": "apply", "conflictCode": "x",
                             "fromValue": "a", "toValue": "b"})
    assert ответ.status == 403
