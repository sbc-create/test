"""Жив ли контейнер — по `State`, а не по строке состояния.

Измерено 2026-10-15 соседней сессией: `docker compose ps` показывал
«Up 13 days (healthy)» у контейнера, у которого `docker inspect .State`
отвечал `Status=exited`, `Running=false`, `ExitCode=1`,
`FinishedAt=2026-10-10T03:42:57Z`. Строка состояния устарела на пять суток, и
по ней доклад утверждал «контейнеры healthy», тогда как исполнитель заданий был
мёртв.

У нас тот же шаблон встречался в чтении режима индексации семейства, чей режим
решает переменная контейнера: контейнер находился по `docker ps`, а дальше
читались переменные — без вопроса, работает ли он. Переменные остановленного
контейнера о работающем режиме не говорят.
"""
import json

from factory.qwen import indexing


class Запуск:
    """Подставной `subprocess.run`: по аргументам отдаёт нужный ответ."""

    def __init__(self, состояние: dict):
        self.состояние = состояние

    def __call__(self, аргументы, **_):
        class Ответ:
            returncode = 0
            stdout = ""

        о = Ответ()
        if аргументы[:2] == ["docker", "ps"]:
            о.stdout = "yummy-web-1\n"
        elif аргументы[:2] == ["docker", "inspect"]:
            о.stdout = json.dumps([{
                "Config": {"Env": ["SITE_URL=https://example.test",
                                   "SEO_INDEXING_ENABLED=true",
                                   "APP_ENV=production"]},
                "State": self.состояние,
            }])
        return о


def _подменить(monkeypatch, состояние):
    import subprocess
    monkeypatch.setattr(subprocess, "run", Запуск(состояние))
    monkeypatch.setattr("shutil.which", lambda _: "/usr/bin/docker")


def test_работающий_контейнер_читается(monkeypatch):
    _подменить(monkeypatch, {"Running": True, "Status": "running"})
    итог = indexing.читатель_контейнера("example.test")
    assert итог["found"] is True
    assert итог["SEO_INDEXING_ENABLED"] == "true"
    assert итог["permits_open"] is True


def test_остановленный_контейнер_не_читается_как_живой(monkeypatch):
    """Тот самый дефект: переменные мёртвого контейнера выглядели рабочими."""
    _подменить(monkeypatch, {"Running": False, "Status": "exited",
                             "ExitCode": 1,
                             "FinishedAt": "2026-10-10T03:42:57Z"})
    итог = indexing.читатель_контейнера("example.test")
    assert итог["found"] is False
    assert "не работает" in итог["reason"]
    assert "exited" in итог["reason"]
    assert "2026-10-10" in итог["reason"], "в причине нет времени остановки"


def test_причина_называет_код_выхода(monkeypatch):
    _подменить(monkeypatch, {"Running": False, "Status": "exited",
                             "ExitCode": 137, "FinishedAt": "2026-10-11T00:00:00Z"})
    итог = indexing.читатель_контейнера("example.test")
    assert "ExitCode=137" in итог["reason"]


def test_без_поля_состояния_контейнер_живым_не_считается(monkeypatch):
    """Отсутствие `State` — не разрешение считать его работающим."""
    _подменить(monkeypatch, {})
    итог = indexing.читатель_контейнера("example.test")
    assert итог["found"] is False
    assert "не работает" in итог["reason"]
