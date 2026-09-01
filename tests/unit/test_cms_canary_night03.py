"""CMS canary: настоящие запросы к настоящему серверу на временном порту."""
from __future__ import annotations

import json
import os
import socket
import threading
import urllib.error
import urllib.request
from pathlib import Path

import pytest

from factory.site_engine import audit as audit_mod
from factory.site_engine.access import Principal, Role
from factory.site_engine.api import ControlPlaneApi
from factory.site_engine.cms.server import serve
from factory.site_engine.commands import CommandLog


def свободный_порт() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture
def стенд(monkeypatch):
    monkeypatch.setenv("SITE_ENGINE_API_ENABLED", "1")
    api = ControlPlaneApi(
        read_api=None,
        commands=CommandLog(),
        audit=audit_mod.AuditLog(),
        principals={
            "owner": Principal("owner", (Role.OWNER,)),
            "viewer": Principal("viewer", (Role.VIEWER,)),
            "operator": Principal("operator", (Role.OPERATOR,)),
        },
        collectors={
            "sites": lambda: [{"id": "s1", "site_id": "s1", "site_type": "showcase",
                               "domains": ["s1.example"]}],
            "audit-events": lambda: [],
            "jobs": lambda: [{"id": "t.timer", "name": "t.timer", "service": "t.service"}],
            "deployments": lambda: [],
        },
        env=dict(os.environ),
    )
    порт = свободный_порт()
    сервер, canary = serve(api, host="127.0.0.1", port=порт)
    поток = threading.Thread(target=сервер.serve_forever, daemon=True)
    поток.start()
    ключи = {имя: canary.выдать_ключ(имя) for имя in api.principals}
    try:
        yield f"http://127.0.0.1:{порт}", ключи, api
    finally:
        сервер.shutdown()
        сервер.server_close()


def запрос(адрес: str, ключ: str | None = None, данные: bytes | None = None):
    req = urllib.request.Request(адрес, data=данные)
    if ключ:
        req.add_header("Cookie", f"sf_session={ключ}")
    try:
        with urllib.request.urlopen(req, timeout=10) as ответ:
            return ответ.status, ответ.read().decode("utf-8")
    except urllib.error.HTTPError as ошибка:
        return ошибка.code, ошибка.read().decode("utf-8")


class TestДоступ:
    def test_без_ключа_не_пускает(self, стенд):
        база, _, _ = стенд
        код, тело = запрос(f"{база}/sites")
        assert код == 401
        assert "Ключ сеанса" in тело

    def test_неверный_ключ_не_пускает(self, стенд):
        база, _, _ = стенд
        assert запрос(f"{база}/login?key=made-up-key")[0] == 401

    def test_все_разделы_отвечают(self, стенд):
        база, ключи, _ = стенд
        for путь in ("/", "/sites", "/content", "/editorial", "/shelves",
                     "/schedule", "/jobs", "/releases", "/users", "/audit"):
            код, _ = запрос(f"{база}{путь}", ключи["owner"])
            assert код == 200, путь

    def test_несуществующий_раздел_404(self, стенд):
        база, ключи, _ = стенд
        assert запрос(f"{база}/no-such-section", ключи["owner"])[0] == 404


class TestПраваВИнтерфейсе:
    def test_кнопка_публикации_только_у_владельца(self, стенд):
        база, ключи, _ = стенд
        _, у_владельца = запрос(f"{база}/releases", ключи["owner"])
        _, у_наблюдателя = запрос(f"{база}/releases", ключи["viewer"])
        assert "Опубликовать" in у_владельца
        assert "Опубликовать" not in у_наблюдателя

    def test_наблюдатель_не_подаёт_опасную_команду(self, стенд):
        база, ключи, _ = стенд
        данные = b"kind=release.publish&site_id=s1&confirmed=1&payload=%7B%7D"
        код, тело = запрос(f"{база}/jobs", ключи["viewer"], данные)
        assert код == 200          # страница с объяснением, а не поломка
        assert "403" in тело and "нет права" in тело


class TestКомандыИАудит:
    def test_повтор_не_создаёт_вторую_запись_аудита(self, стенд):
        база, ключи, api = стенд
        данные = b"kind=ingestion.run&site_id=s1&idempotency_key=k1&payload=%7B%7D"
        первый = запрос(f"{база}/jobs", ключи["operator"], данные)
        второй = запрос(f"{база}/jobs", ключи["operator"], данные)
        assert "202" in первый[1]
        assert "повтор" in второй[1]
        assert len(api.audit) == 1


class TestБезопасность:
    def test_ключ_сеанса_не_попадает_в_разметку(self, стенд):
        база, ключи, _ = стенд
        for путь in ("/", "/users", "/audit"):
            _, тело = запрос(f"{база}{путь}", ключи["owner"])
            assert ключи["owner"] not in тело, путь

    def test_заголовки_запрещают_индексацию_и_кэш(self, стенд):
        база, ключи, _ = стенд
        req = urllib.request.Request(f"{база}/")
        req.add_header("Cookie", f"sf_session={ключи['owner']}")
        with urllib.request.urlopen(req, timeout=10) as ответ:
            assert ответ.headers["X-Robots-Tag"] == "noindex, nofollow"
            assert ответ.headers["Cache-Control"] == "no-store"

    def test_спецификация_отдаётся_без_входа_но_без_данных(self, стенд):
        """OpenAPI — описание договора, а не сведения о сайтах."""
        база, _, _ = стенд
        код, тело = запрос(f"{база}/openapi.json")
        assert код == 200
        документ = json.loads(тело)
        assert документ["openapi"].startswith("3.")
        assert "s1.example" not in тело


class TestКоллекторРейтингов:
    """Оценки берутся из снимка каталога, а не сочиняются.

    Ресурс `ratings` до этого отвечал 501. Подключён к настоящему источнику:
    поля `imdb_rating` и `kinopoisk_rating` каталожного кэша. Проверяется не
    «коллектор что-то вернул», а что он не выдумывает и не прячет отсутствие
    оценки за нулём.
    """

    @staticmethod
    def _коллекторы(tmp_path):
        import importlib.util

        кэш = tmp_path / "cache"
        кэш.mkdir()
        (кэш / "lords-01.json").write_text(json.dumps({"items": [
            {"external_id": "a", "name": "С обеими", "year": 1982,
             "imdb_rating": 6.2, "kinopoisk_rating": 6.684},
            {"external_id": "b", "name": "Только imdb", "year": 2026,
             "imdb_rating": 6.3, "kinopoisk_rating": None},
            {"external_id": "c", "name": "Без оценок", "year": 2026,
             "imdb_rating": None, "kinopoisk_rating": None},
            {"external_id": "d", "name": "Нули как отсутствие", "year": 2026,
             "imdb_rating": 0, "kinopoisk_rating": 0},
        ]}, ensure_ascii=False), encoding="utf-8")

        путь = Path(__file__).resolve().parents[2] / "automation" / "host" / "cms-canary.py"
        spec = importlib.util.spec_from_file_location("canary_под_тестом", путь)
        модуль = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(модуль)
        return модуль.collectors(tmp_path, tmp_path / "lords", кэш)

    def test_записи_без_оценок_не_попадают_в_список(self, tmp_path):
        строки = self._коллекторы(tmp_path)["ratings"]()
        имена = [с["name"] for с in строки]
        assert имена == ["С обеими", "Только imdb"], (
            "запись без оценок и запись с нулями обязаны отсеиваться: "
            "строка «нет оценки» в списке оценок сведений не несёт")

    def test_отсутствующая_оценка_помечена_а_не_обнулена(self, tmp_path):
        строки = self._коллекторы(tmp_path)["ratings"]()
        только_imdb = next(с for с in строки if с["name"] == "Только imdb")
        assert только_imdb["kinopoisk"] == "—", (
            "нуль вместо отсутствующей оценки — выдуманное значение")
        assert только_imdb["imdb"] == 6.3

    def test_происхождение_проставлено(self, tmp_path):
        строки = self._коллекторы(tmp_path)["ratings"]()
        assert all(с["provenance"] == "cdnvideohub" for с in строки)
        assert all(с["site_id"] == "lords-01" for с in строки)

    def test_календарь_остаётся_отключённым(self, tmp_path):
        """Синтетический источник не подключают: это выдуманные даты."""
        строки = self._коллекторы(tmp_path)["schedules"]()
        assert строки == [], (
            "config/editorial-calendar.json помечен synthetic: подключение "
            "вывело бы в CMS выдуманные даты")
