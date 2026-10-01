"""Разбор /healthz различает «нет ответа» и «код не тот».

Зачем эта проверка существует
-----------------------------

2026-09-30 в 07:10 установщик выложил две витрины и обе объявил ОТКАЗОМ:

    ОТКАЗ an1mego.site: файл на месте (32f05a208b1e), но /healthz отвечает
    runtime_digest_match=нет ответа — процесс исполняет не его

Независимая публичная проверка тут же показала, что обе витрины исправны:
`runtime_digest_match: true`, адрес в подвале, HTTP 200. Кода, «который не тот»,
не было вовсе.

Причина: разбор ответа жил однострочником внутри одинарных кавычек оболочки, и
`\\"` оставалось обратным слешем с кавычкой. Python 3.10 запрещает обратный слеш
в выражении f-строки, поэтому фрагмент падал с `SyntaxError` ВСЕГДА — при любом
состоянии витрины. Ошибку глотал `2>/dev/null`, `|| echo` подставлял «нет
ответа», а сообщение объявляло установленное несовпадение кода.

Отсюда два требования, которые и проверяются ниже:

1. разбор обязан быть отдельным файлом, который компилируется и тестируется, —
   а не строкой чужого языка внутри оболочки;
2. исходы обязаны РАЗЛИЧАТЬСЯ. «Ответа нет», «ответ не JSON», «поля нет» и
   «поле равно false» — четыре разных утверждения, и только последнее говорит
   о коде.
"""
from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import pytest

КОРЕНЬ = Path(__file__).resolve().parents[2]
РАЗБОРЩИК = КОРЕНЬ / "automation" / "host" / "healthz-digest.py"
УСТАНОВЩИК = КОРЕНЬ / "automation" / "host" / "apply-episode-availability-root.sh"


def _модуль():
    спец = importlib.util.spec_from_file_location("_healthz_digest", РАЗБОРЩИК)
    модуль = importlib.util.module_from_spec(спец)
    sys.modules["_healthz_digest"] = модуль
    спец.loader.exec_module(модуль)
    return модуль


class _Стенд:
    """Крошечный сервер, отвечающий ровно тем, что просит тест."""

    def __init__(self, тело: bytes | None, код: int = 200):
        внешнее = self

        class Обработчик(BaseHTTPRequestHandler):
            def do_GET(self):  # noqa: N802
                self.send_response(код)
                self.end_headers()
                if внешнее.тело is not None:
                    self.wfile.write(внешнее.тело)

            def log_message(self, *а):  # тишина в выводе теста
                return

        self.тело = тело
        self.сервер = HTTPServer(("127.0.0.1", 0), Обработчик)
        self.порт = self.сервер.server_address[1]

    def __enter__(self):
        threading.Thread(target=self.сервер.serve_forever, daemon=True).start()
        return self

    def __exit__(self, *а):
        self.сервер.shutdown()


def test_разборщик_компилируется():
    """Файл, а не строка внутри оболочки: у него есть свой синтаксис."""
    assert РАЗБОРЩИК.is_file(), РАЗБОРЩИК
    compile(РАЗБОРЩИК.read_text(encoding="utf-8"), str(РАЗБОРЩИК), "exec")


def test_поле_true_это_ok():
    м = _модуль()
    тело = json.dumps({"runtime_digest_match": True, "build_id": "b1",
                       "runtime_sha256": "a" * 64, "artifact_sha256": "b" * 64,
                       "runtime_digest_scope": "artifact_files"}).encode()
    with _Стенд(тело) as с:
        исход, подробно = м.опросить(str(с.порт), 5)
    assert исход == "ok"
    # Хеш ФАЙЛА и хеш АРТЕФАКТА печатаются оба: у ячейки с манифестом из
    # нескольких файлов они не совпадают никогда, и это не дефект выкладки.
    assert "runtime_sha256=aaaaaaaaaaaa" in подробно
    assert "artifact_sha256=bbbbbbbbbbbb" in подробно
    assert "scope=artifact_files" in подробно


def test_поле_false_это_mismatch():
    """Единственный исход, дающий право сказать «процесс исполняет не тот файл»."""
    м = _модуль()
    with _Стенд(json.dumps({"runtime_digest_match": False}).encode()) as с:
        исход, _ = м.опросить(str(с.порт), 5)
    assert исход == "mismatch"


def test_нет_поля_это_не_mismatch():
    м = _модуль()
    with _Стенд(json.dumps({"ok": True}).encode()) as с:
        исход, подробно = м.опросить(str(с.порт), 5)
    assert исход == "no-field", подробно


def test_не_json_это_не_mismatch():
    м = _модуль()
    with _Стенд(b"<html>503</html>") as с:
        исход, _ = м.опросить(str(с.порт), 5)
    assert исход == "bad-json"


def test_пустое_тело_это_нет_ответа():
    м = _модуль()
    with _Стенд(b"") as с:
        исход, _ = м.опросить(str(с.порт), 5)
    assert исход == "no-answer"


def test_закрытый_порт_это_нет_ответа():
    """Порт закрыт — это молчание, а не приговор коду."""
    м = _модуль()
    стенд = _Стенд(b"{}")
    порт = стенд.порт  # сервер не запускаем: порт свободен
    исход, подробно = м.опросить(str(порт), 2)
    assert исход == "no-answer", подробно


@pytest.mark.parametrize("тело,ожидание", [
    (json.dumps({"runtime_digest_match": True}).encode(), 0),
    (json.dumps({"runtime_digest_match": False}).encode(), 1),
    ("не json".encode("utf-8"), 1),
])
def test_код_возврата_ноль_только_у_ok(тело, ожидание):
    with _Стенд(тело) as с:
        готово = subprocess.run([sys.executable, str(РАЗБОРЩИК), str(с.порт), "5"],
                                capture_output=True, text=True, timeout=30)
    assert готово.returncode == ожидание, готово.stdout + готово.stderr


def test_установщик_не_несёт_в_себе_чужой_язык():
    """Однострочник Python внутри кавычек оболочки больше не живёт.

    Проверяется не стиль, а способ отказа: такой однострочник парсится
    оболочкой молча и падает только при выполнении, а вывод падения глушится
    перенаправлением. Ровно так и появился отчёт о несовпадении кода, которого
    никто не измерял.
    """
    текст = УСТАНОВЩИК.read_text(encoding="utf-8")
    assert "healthz-digest.py" in текст, "разбор ответа обязан быть отдельным файлом"
    assert "runtime_digest_match=нет ответа" not in текст, (
        "формулировка, выдающая отсутствие ответа за несовпадение кода")
    # Вердикт витрины и вердикт «не дозвонились» обязаны идти РАЗНЫМИ ветками.
    assert 'verdict" = "mismatch"' in текст or '"$verdict" = "mismatch"' in текст
    assert '"$verdict" != "ok"' in текст


def test_строгая_проверка_кода_не_подменена_кодом_200():
    """HTTP 200 сам по себе выкладкой не считается — сверка байтов осталась."""
    текст = УСТАНОВЩИК.read_text(encoding="utf-8")
    assert 'sha_of "$live"' in текст, "сверка байтов установленного файла убрана"
    assert 'markers_present "$live"' in текст, "проверка признаков исправления убрана"
    assert 'ожидался $have_code' in текст, "сравнение с репозиторием убрано"
