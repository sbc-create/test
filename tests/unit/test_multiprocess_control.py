"""REQ-DISTRIBUTED: ограничение и идемпотентность общие для процессов.

Проверка идёт настоящими процессами, а не потоками и не подменой времени.
Прежняя редакция хранила счётчик в памяти, и любой однопроцессный тест
показывал бы её исправной: предел «30 в минуту» при двух экземплярах означал
шестьдесят, а повтор после таймаута создавал второе задание. Такие свойства
нельзя проверить изнутри одного процесса.
"""
import json
import os
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

from factory import queue as queue_mod
from factory.paths import PATHS
from factory.site_engine.api import ratelimit

REPO = Path(__file__).resolve().parents[2]
SITE = "mp-site"
TOKEN = "mp-token"
ENV_EXTRA = {
    "SITE_ENGINE_CONTROL_WRITES": "1",
    "SITE_ENGINE_CONTROL_TOKENS": f"{TOKEN}=read,jobs:write,config:write,cache:write",
    "SITE_ENGINE_ENVIRONMENT": "test",
}

РАБОТНИК = textwrap.dedent('''
    import json, os, sys
    from pathlib import Path as _P
    sys.path.insert(0, os.environ["REPO"])
    from factory.paths import PATHS
    PATHS.root = _P(os.environ["ROOT"])
    from factory.site_engine.api.control import ControlApi

    корень = os.environ["ROOT"]
    api = ControlApi(root=корень, env=dict(os.environ))
    ключ = os.environ.get("IDEM_KEY") or ""
    сколько = int(os.environ.get("REPEATS", "1"))
    итог = []
    for i in range(сколько):
        заголовки = {"Authorization": "Bearer " + os.environ["TOKEN"]}
        if ключ:
            заголовки["Idempotency-Key"] = ключ
        тело = json.loads(os.environ.get("BODY", "{}"))
        r = api.handle(os.environ.get("METHOD", "POST"), os.environ["PATH_"],
                       body=тело, headers=заголовки)
        код = (r.body.get("error") or {}).get("code", "")
        итог.append({"status": r.status, "code": код,
                     "replay": bool(r.body.get("idempotentReplay"))})
    print(json.dumps(итог))
''')


@pytest.fixture
def sandbox(tmp_path, monkeypatch):
    monkeypatch.setattr(PATHS, "root", tmp_path)
    profiles = tmp_path / "config" / "site-profiles"
    profiles.mkdir(parents=True)
    образец = json.loads(
        (REPO / "config" / "site-profiles" / "lords-01.json").read_text(encoding="utf-8"))
    образец.update({"site_id": SITE, "domains": ["mp.test"], "canonical_host": "mp.test"})
    (profiles / f"{SITE}.json").write_text(json.dumps(образец, ensure_ascii=False),
                                           encoding="utf-8")
    for sub in ("queue/inbox", "queue/processing", "queue/done", "queue/failed",
                "queue/quarantine", "var/locks", "var/audit", "var/state"):
        (tmp_path / sub).mkdir(parents=True, exist_ok=True)
    return tmp_path


def запустить(sandbox, *, путь, метод="POST", тело=None, ключ="", повторов=1):
    среда = {**os.environ, **ENV_EXTRA,
             "REPO": str(REPO), "ROOT": str(sandbox), "TOKEN": TOKEN,
             "PATH_": путь, "METHOD": метод,
             "BODY": json.dumps(тело or {}), "IDEM_KEY": ключ,
             "REPEATS": str(повторов), "FACTORY_ROOT": str(sandbox)}
    return subprocess.Popen([sys.executable, "-c", РАБОТНИК],
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                            env=среда, text=True)


def собрать(процессы):
    итоги = []
    for p in процессы:
        out, err = p.communicate(timeout=120)
        assert p.returncode == 0, f"процесс упал: {err[:400]}"
        итоги.extend(json.loads(out.strip().splitlines()[-1]))
    return итоги


def test_два_процесса_не_создают_второго_задания(sandbox):
    """Повтор после таймаута обязан вернуть прежний ответ, а не поставить ещё одно."""
    процессы = [
        запустить(sandbox, путь=f"/api/v1/sites/{SITE}/jobs",
                  тело={"action": "reindex"}, ключ="shared-key-1")
        for _ in range(2)
    ]
    итоги = собрать(процессы)
    успехов = [r for r in итоги if r["status"] == 202]
    файлов = list((sandbox / "queue" / "inbox").glob("*.json"))
    assert len(файлов) == 1, f"создано заданий: {len(файлов)}, ответы: {итоги}"
    assert len(успехов) >= 1
    # Второй процесс либо повторил ответ, либо застал заявку в работе — и то и
    # другое верно; недопустимо только второе задание.
    прочие = [r for r in итоги if r not in успехов or r["replay"]]
    assert прочие or len(успехов) == 2


def test_общий_ключ_с_другим_телом_даёт_конфликт_между_процессами(sandbox):
    первый = запустить(sandbox, путь=f"/api/v1/sites/{SITE}/jobs",
                       тело={"action": "reindex"}, ключ="shared-key-2")
    собрать([первый])
    второй = запустить(sandbox, путь=f"/api/v1/sites/{SITE}/jobs",
                       тело={"action": "enrich"}, ключ="shared-key-2")
    итоги = собрать([второй])
    assert итоги[0]["status"] == 409
    assert итоги[0]["code"] == "idempotency_key_reused"


def test_предел_общий_для_процессов(sandbox):
    """Предел в памяти дал бы вдвое больше при двух экземплярах."""
    предел = ratelimit.DEFAULT_LIMITS["operation"].capacity
    на_процесс = предел  # вдвоём заведомо перебирают предел
    процессы = [
        запустить(sandbox, путь=f"/api/v1/sites/{SITE}/jobs",
                  тело={"action": "reindex", "dryRun": True}, повторов=на_процесс)
        for _ in range(2)
    ]
    итоги = собрать(процессы)
    разрешено = sum(1 for r in итоги if r["status"] == 200)
    отказано = sum(1 for r in итоги if r["status"] == 429)
    assert отказано > 0, "общий предел не сработал: похоже, счётчик снова в памяти"
    # Небольшой запас на пополнение ведра за время прогона.
    assert разрешено <= предел + 5, f"разрешено {разрешено} при пределе {предел}"


def test_состояние_предела_переживает_перезапуск(sandbox):
    """Счётчик в файле: новый процесс продолжает с того же места."""
    предел = ratelimit.DEFAULT_LIMITS["operation"].capacity
    первый = запустить(sandbox, путь=f"/api/v1/sites/{SITE}/jobs",
                       тело={"action": "reindex", "dryRun": True}, повторов=предел)
    собрать([первый])
    второй = запустить(sandbox, путь=f"/api/v1/sites/{SITE}/jobs",
                       тело={"action": "reindex", "dryRun": True}, повторов=3)
    итоги = собрать([второй])
    assert any(r["status"] == 429 for r in итоги), (
        "после перезапуска предел начался заново — состояние не общее")


def test_идемпотентность_переживает_перезапуск(sandbox):
    первый = запустить(sandbox, путь=f"/api/v1/sites/{SITE}/jobs",
                       тело={"action": "reindex"}, ключ="survive-1")
    собрать([первый])
    второй = запустить(sandbox, путь=f"/api/v1/sites/{SITE}/jobs",
                       тело={"action": "reindex"}, ключ="survive-1")
    итоги = собрать([второй])
    assert итоги[0]["replay"] is True, "повтор в новом процессе выполнился заново"
    assert len(list((sandbox / "queue" / "inbox").glob("*.json"))) == 1


def test_отказ_не_занимает_ключ_навсегда(sandbox):
    """Исправленный повтор с тем же ключом обязан пройти."""
    плохой = запустить(sandbox, путь=f"/api/v1/sites/{SITE}/jobs",
                       тело={"action": "недопустимо"}, ключ="will-fix")
    итоги = собрать([плохой])
    assert итоги[0]["status"] == 400
    хороший = запустить(sandbox, путь=f"/api/v1/sites/{SITE}/jobs",
                        тело={"action": "reindex"}, ключ="will-fix")
    итоги2 = собрать([хороший])
    assert итоги2[0]["status"] == 202, f"ключ остался занят после отказа: {итоги2}"


def test_недопустимый_ключ_даёт_отказ_а_не_сбой(sandbox):
    """Разбор ключа идёт до конвейера; его отказ обязан стать ответом 400."""
    p = запустить(sandbox, путь=f"/api/v1/sites/{SITE}/jobs",
                  тело={"action": "reindex"}, ключ="ключ-с-кириллицей")
    итоги = собрать([p])
    assert итоги[0]["status"] == 400
    assert итоги[0]["code"] == "invalid_idempotency_key"
