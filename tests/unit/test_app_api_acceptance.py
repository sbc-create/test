"""Приёмка API различает четыре разных случая, а не «не работает».

Повод. Разработчик приложения сообщил: `https://animedia.icu/api/app/v1/healthz`
возвращает 308. Измерено: 308 — это перенаправление САМОЙ ВИТРИНЫ на путь со
слешем (она так отвечает на любой неизвестный адрес), а за ним 404 и её же
страница «не найдено». То есть маршрута API нет вовсе — служба не установлена.
Это ровно то, что нельзя путать с остальным: отказом авторизации (401),
ненастроенным ключом (503), мёртвой службой за живым маршрутом (502) и рабочим
состоянием (200).

Поэтому инструмент приёмки обязан называть случай, а не возвращать «расхождение».
Здесь это и сторожится — на подставном сервере, без сети и без боевой службы.

Отдельно сторожится главное утверждение контракта: пустой `sources` с причиной
`NO_SOURCE_CONTRACT_RELEASED` — это ОЖИДАЕМЫЙ ответ, а внезапно непустой список
— расхождение. Прямых ссылок у фабрики нет, и появиться они могут только с
разрешением провайдера; молча принять их значило бы выдать неизвестно откуда
взявшийся поток за разрешённый.
"""
from __future__ import annotations

import importlib.util
import json
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

КОРЕНЬ = Path(__file__).resolve().parents[2]
СЦЕНАРИЙ = КОРЕНЬ / "automation" / "local" / "app-api-acceptance.py"
КЛЮЧ = "probe-key-ascii-only"
СЕРИАЛ = "01915145-2c16-7ba4-8353-42b73d657fdc"


def _модуль():
    спец = importlib.util.spec_from_file_location("app_api_acceptance", СЦЕНАРИЙ)
    м = importlib.util.module_from_spec(спец)
    sys.modules["app_api_acceptance"] = м
    спец.loader.exec_module(м)
    return м


class _Ответы:
    """Что подставной сервер отвечает на каждый путь."""

    def __init__(self, сценарий: str) -> None:
        self.сценарий = сценарий


def _сервер(сценарий: str, источники: dict | None = None,
            ломать_кодированные: bool = False):
    источники = источники or {"sources": [], "reason": "NO_SOURCE_CONTRACT_RELEASED"}

    class Обработчик(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def log_message(self, *_а):  # тишина в выводе проверок
            pass

        def _json(self, код: int, тело):
            данные = json.dumps(тело).encode()
            self.send_response(код)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(данные)))
            self.send_header("X-Catalog-Revision", "r-1")
            self.end_headers()
            self.wfile.write(данные)

        def do_GET(self):  # noqa: N802
            путь = self.path
            # Исправленная служба раскрывает процентные последовательности по
            # сегментам, поэтому `%3A` и `:` для неё одно и то же. Подставной
            # сервер делает так же — иначе проверка инструмента шла бы против
            # поведения, которого в службе нет. Флаг `ломать_кодированные`
            # воспроизводит ПРЕЖНЮЮ службу: 404 на закодированную форму.
            if "%3A" in путь or "%3a" in путь:
                if ломать_кодированные:
                    return self._json(404, {"error": {"code": "not_found"}})
                путь = путь.replace("%3A", ":").replace("%3a", ":")
            if сценарий == "перенаправление":
                self.send_response(308)
                self.send_header("Location", путь.rstrip("/") + "/")
                self.send_header("Content-Length", "0")
                self.end_headers()
                return
            if сценарий == "маршрута нет":
                тело = b"<html><title>404</title></html>"
                self.send_response(404)
                self.send_header("Content-Type", "text/html")
                self.send_header("Content-Length", str(len(тело)))
                self.end_headers()
                self.wfile.write(тело)
                return
            if сценарий == "служба молчит":
                self.send_response(502)
                self.send_header("Content-Length", "0")
                self.end_headers()
                return
            if путь.startswith("/api/app/v1/healthz"):
                if сценарий == "ключ не настроен":
                    return self._json(503, {"ok": False, "ready": False,
                                            "keyConfigured": False,
                                            "reason": "файл ключа не задан"})
                return self._json(200, {"ok": True, "ready": True,
                                        "keyConfigured": True, "titles": 2,
                                        "catalogRevision": "r-1"})
            if self.headers.get("X-App-Key") != КЛЮЧ:
                return self._json(401, {"error": {"code": "unauthorized"}})
            if путь.startswith("/api/app/v1/titles?"):
                return self._json(200, {"items": [
                    {"contentId": СЕРИАЛ, "title": "Северный ветер",
                     "artwork": {"posterUrl": "https://poster/x.webp"}}],
                    "rule": "added"})
            if путь.startswith("/api/app/v1/search"):
                return self._json(200, {"items": [{"contentId": СЕРИАЛ}]})
            if путь == f"/api/app/v1/titles/{СЕРИАЛ}":
                return self._json(200, {"contentId": СЕРИАЛ, "title": "Северный ветер",
                                        "artwork": {"posterUrl": "https://poster/x.webp"}})
            if путь.startswith("/api/app/v1/seasons%2F"):
                return self._json(
                    400, {"error": {"code": "bad_request",
                                    "message": "в сегменте пути закодирован разделитель"}})
            if (путь.startswith("/api/app/v1/seasons/")
                    and ":s99/episodes" in путь):
                return self._json(404, {"error": {"code": "not_found",
                                                  "message": "такого сезона нет"}})
            if путь == f"/api/app/v1/titles/{СЕРИАЛ}/seasons":
                return self._json(200, [{"seasonId": f"{СЕРИАЛ}:s1", "number": 1,
                                         "episodeCount": 2}])
            if путь == f"/api/app/v1/seasons/{СЕРИАЛ}:s1/episodes":
                return self._json(200, [{"episodeId": f"{СЕРИАЛ}:s1:e1"}])
            if "/sources" in путь:
                return self._json(200, источники)
            return self._json(404, {"error": {"code": "not_found"}})

    с = ThreadingHTTPServer(("127.0.0.1", 0), Обработчик)
    поток = threading.Thread(target=с.serve_forever, daemon=True)
    поток.start()
    return с, f"http://127.0.0.1:{с.server_port}"


@pytest.fixture()
def ключ(tmp_path) -> Path:
    ф = tmp_path / "key"
    ф.write_text(КЛЮЧ, encoding="utf-8")
    return ф


def _прогон(м, база: str, ключ: Path):
    return м.главное(["--base", база, "--key-file", str(ключ)])


def test_рабочая_служба_проходит_целиком(ключ, capsys):
    м = _модуль()
    с, база = _сервер("всё работает")
    try:
        код = _прогон(м, база, ключ)
    finally:
        с.shutdown()
    вывод = capsys.readouterr().out
    assert код == 0, вывод
    assert "расхождений: 0" in вывод
    assert "NO_SOURCE_CONTRACT_RELEASED" in вывод


@pytest.mark.parametrize(("сценарий", "сказано"), [
    ("перенаправление", "служба не установлена"),
    ("маршрута нет", "маршрута нет"),
    ("служба молчит", "служба не отвечает"),
    ("ключ не настроен", "ключ клиента на сервере не настроен"),
])
def test_случай_называется_а_не_сводится_к_расхождению(ключ, capsys, сценарий, сказано):
    м = _модуль()
    с, база = _сервер(сценарий)
    try:
        код = _прогон(м, база, ключ)
    finally:
        с.shutdown()
    вывод = capsys.readouterr().out
    assert код == 1, вывод
    assert сказано in вывод, вывод
    assert "дальше не проверялось" in вывод, (
        "после нерабочего состояния остальные проверки бессмысленны")


def test_непустой_источник_это_расхождение(ключ, capsys):
    """Поток, появившийся без разрешения провайдера, молча принимать нельзя."""
    м = _модуль()
    с, база = _сервер("всё работает",
                      источники={"sources": [{"url": "https://откуда-то/x.m3u8"}],
                                 "reason": None})
    try:
        код = _прогон(м, база, ключ)
    finally:
        с.shutdown()
    вывод = capsys.readouterr().out
    assert код == 1, вывод
    assert "источники серии" in вывод


def test_пустой_файл_ключа_это_не_проверка(tmp_path, capsys):
    м = _модуль()
    пустой = tmp_path / "empty"
    пустой.write_text("", encoding="utf-8")
    код = м.главное(["--base", "http://127.0.0.1:1", "--key-file", str(пустой)])
    assert код == 2, "нечем проверять — это отдельный исход, а не провал службы"


def test_ключ_не_печатается(ключ, capsys):
    м = _модуль()
    с, база = _сервер("всё работает")
    try:
        _прогон(м, база, ключ)
    finally:
        с.shutdown()
    assert КЛЮЧ not in capsys.readouterr().out


def test_число_серий_не_выдаётся_за_воспроизведение(ключ, capsys):
    м = _модуль()
    с, база = _сервер("всё работает")
    try:
        _прогон(м, база, ключ)
    finally:
        с.shutdown()
    вывод = capsys.readouterr().out
    assert "ЧИСЛО ИЗ СНИМКА" in вывод
    assert "доказательством воспроизведения не является" in вывод


# --- кодированные идентификаторы --------------------------------------------
#
# Проверка инструмента, а не службы: приёмка обязана ПОЙМАТЬ службу, которая
# отвечает 404 на `%3A`. Именно такой службой API был до 2026-10-11, и именно
# это прошло мимо прежней приёмки — в её выводе отдельного результата для
# кодированных идентификаторов не было вовсе.


def test_кодированные_идентификаторы_показаны_отдельно(ключ, capsys):
    м = _модуль()
    с, база = _сервер("всё работает")
    try:
        код = _прогон(м, база, ключ)
    finally:
        с.shutdown()
    вывод = capsys.readouterr().out
    assert код == 0, вывод
    assert "кодированные идентификаторы" in вывод
    for строка in ("серии сезона: «:» и %3A", "серии сезона: «:» и %3a",
                   "источники серии: «:» и %3A",
                   "несуществующий сезон, %3A",
                   "закодированный разделитель %2F"):
        assert строка in вывод, строка
    assert "тела совпадают" in вывод


def test_служба_отвечающая_404_на_кодированный_id_не_проходит(ключ, capsys):
    """Главная польза проверки: прежняя служба обязана быть отвергнута."""
    м = _модуль()
    с, база = _сервер("всё работает", ломать_кодированные=True)
    try:
        код = _прогон(м, база, ключ)
    finally:
        с.shutdown()
    вывод = capsys.readouterr().out
    assert код == 1, вывод
    assert "[НЕТ] серии сезона: «:» и %3A" in вывод, вывод
    assert "коды 200 и 404" in вывод


def test_равные_коды_при_разных_телах_тоже_расхождение(ключ, capsys, monkeypatch):
    """Сверяются данные, а не только коды: иначе дефект стал бы незаметным."""
    м = _модуль()
    с, база = _сервер("всё работает")
    приёмка = м.Приёмка(база, ключ.read_text(encoding="utf-8"))
    приёмка.ид_сезона = f"{СЕРИАЛ}:s1"
    приёмка.ид_серии = f"{СЕРИАЛ}:s1:e1"
    настоящий = приёмка.запрос
    def подмена(путь, **прочее):
        код, тело, заголовки = настоящий(путь, **прочее)
        if "%3A" in путь and isinstance(тело, list):
            тело = тело + [{"episodeId": "лишняя"}]
        return код, тело, заголовки
    monkeypatch.setattr(приёмка, "запрос", подмена)
    try:
        приёмка.кодированные()
    finally:
        с.shutdown()
    вывод = capsys.readouterr().out
    assert "РАЗНЫЕ" in вывод, вывод
    assert приёмка.расхождений > 0
