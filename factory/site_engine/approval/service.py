"""Выделенная служба подписи одобрений.

Единственный процесс в контуре, которому принадлежит приватный ключ. Всё
остальное — Control API, рабочий процесс, адаптеры — получает публичный
ключ и проверяет подпись у себя, без обращения сюда. Обратное означало бы,
что проверка одобрения зависит от доступности ещё одной службы.

Служба слушает только петлю. Подписывает не «что попало»: вызывающий
предъявляет собственный token, а тело подписи приходит уже каноническим —
signer не строит его сам и потому не может подписать не то, что показали
одобряющему.
"""
from __future__ import annotations

import json
import os
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from factory.site_engine.approval import keyring as K
from factory.site_engine.credentials import store as C

ПРИВАТНЫЙ = "approval-signing-key"
НАБОР = "approval-verify-keys"
ТОКЕН = "approval-signer-token"
ПРЕДЕЛ_ТЕЛА = 64 * 1024


class Состояние:
    def __init__(self) -> None:
        self.pem = C.получить(ПРИВАТНЫЙ)
        self.набор = K.НаборКлючей.из_json(C.получить(НАБОР))
        self.токен = C.получить(ТОКЕН)
        ключ = K.приватный_из_pem(self.pem)
        self.kid = K.kid_публичного(ключ.public_key())
        запись = self.набор.ключи.get(self.kid)
        if запись is None:
            raise K.KeyringError(
                "SIGNING_KEY_NOT_IN_KEYSET",
                f"приватный ключ {self.kid} отсутствует в наборе проверки: "
                f"подписанное им никто не сможет проверить")
        if запись.состояние != "ACTIVE":
            raise K.KeyringError(
                "SIGNING_KEY_NOT_ACTIVE",
                f"ключ {self.kid} в состоянии {запись.состояние}: подписывать "
                f"выведенным из обращения ключом нельзя")
        self.подписано = 0
        self.замок = threading.Lock()


class Обработчик(BaseHTTPRequestHandler):
    состояние: Состояние = None            # назначается при запуске
    server_version = "site-factory-approval-signer/1.0"

    def log_message(self, *_):             # тела запросов в журнал не идут
        pass

    def _ответ(self, код: int, тело: dict) -> None:
        сырое = json.dumps(тело, ensure_ascii=False).encode("utf-8")
        self.send_response(код)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(сырое)))
        self.end_headers()
        self.wfile.write(сырое)

    def do_GET(self):
        if self.path == "/jwks":
            # Публичный ключ секретом не является: его раздача и есть смысл
            # асимметричной схемы.
            self._ответ(200, json.loads(self.состояние.набор.в_json()))
            return
        if self.path in ("/healthz", "/health"):
            self._ответ(200, {"ready": True, "alg": K.АЛГОРИТМ,
                              "active_kid": self.состояние.kid,
                              "signed": self.состояние.подписано})
            return
        self._ответ(404, {"error_code": "NOT_FOUND"})

    def do_POST(self):
        if self.path != "/sign":
            self._ответ(404, {"error_code": "NOT_FOUND"})
            return
        предъявлен = (self.headers.get("Authorization") or "").removeprefix(
            "Bearer ").strip()
        import hmac as _hmac
        if not предъявлен or not _hmac.compare_digest(
                предъявлен.encode("utf-8", "surrogatepass"),
                self.состояние.токен.encode("utf-8", "surrogatepass")):
            self._ответ(401, {"error_code": "UNAUTHENTICATED",
                              "detail": "token подписи не предъявлен или не распознан"})
            return
        длина = int(self.headers.get("Content-Length") or 0)
        if длина <= 0 or длина > ПРЕДЕЛ_ТЕЛА:
            self._ответ(413, {"error_code": "BODY_SIZE",
                              "detail": f"тело обязано быть в пределах {ПРЕДЕЛ_ТЕЛА} байт"})
            return
        try:
            запрос = json.loads(self.rfile.read(длина) or b"{}")
        except ValueError:
            self._ответ(400, {"error_code": "BODY_MALFORMED"})
            return
        тело = запрос.get("body")
        if not isinstance(тело, str) or not тело:
            self._ответ(422, {"error_code": "BODY_REQUIRED",
                              "detail": "каноническое тело подписи обязательно"})
            return
        подпись = K.подписать(self.состояние.pem, тело)
        with self.состояние.замок:
            self.состояние.подписано += 1
        self._ответ(200, {"signature": подпись, "kid": self.состояние.kid,
                          "alg": K.АЛГОРИТМ})


def запустить(хост: str = "127.0.0.1", порт: int = 8795) -> int:
    Обработчик.состояние = Состояние()
    сервер = ThreadingHTTPServer((хост, порт), Обработчик)
    print(f"[approval-signer] слушает {хост}:{порт}, активный kid "
          f"{Обработчик.состояние.kid}", flush=True)
    try:
        сервер.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        сервер.server_close()
    return 0


if __name__ == "__main__":
    порт = int(os.environ.get("APPROVAL_SIGNER_PORT", "8795"))
    sys.exit(запустить(порт=порт))
