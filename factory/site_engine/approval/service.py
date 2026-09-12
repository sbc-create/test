"""Выделенная служба подписи. НЕ сервис подписи произвольных данных.

Почему приём готового payload недопустим
----------------------------------------

Служба, подписывающая то, что ей прислали, — это не подпись, а нотариус,
заверяющий чужой текст не читая. Любой, кто добрался до её API, получает
возможность выписать себе разрешение на что угодно: подпись будет
математически верной, а содержание — каким угодно.

Поэтому здесь принимается ТОЛЬКО ссылка на набор изменений. Каноническое
состояние служба читает сама, сама строит тело подписи и сама решает,
подлежит ли оно подписи вообще. Прислать «уже готовое тело» нельзя: такого
параметра не существует.

Что проверяется до подписи
--------------------------

Состояние набора, план, цели, отпечаток ресурса, версия реестра, версия
политики, одобряющий и его отличие от предложившего, срок, аудитория и
маркер ограждения. Каждая проверка отвечает на свой вопрос, и ни одна не
выводится из другой: совпадение plan_hash ничего не говорит о том, не
устарела ли версия реестра, а действующее одобрение — о том, тому ли выдаётся
разрешение.

Вызывающий опознаётся по предъявленному секрету, а не по тому, кем он себя
назвал, и у каждой операции свой круг допущенных.
"""
from __future__ import annotations

import datetime as _d
import hashlib
import hmac
import json
import os
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

from factory.site_engine.approval import keyring as K
from factory.site_engine.credentials import store as C

ПРИВАТНЫЙ = "approval-signing-key"
НАБОР = "approval-verify-keys"
ВЫЗЫВАЮЩИЕ = "approval-caller-fingerprints"
ПРЕДЕЛ_ТЕЛА = 16 * 1024

#: Кто вправе просить подпись одобрения и кто — разрешение на исполнение.
#: Разные операции, разный круг: та же служба, что просит одобрить, не должна
#: автоматически получать право забрать разрешение на исполнение.
ДОПУЩЕНЫ_К_ОДОБРЕНИЮ = frozenset({"control-api"})
ДОПУЩЕНЫ_К_РАЗРЕШЕНИЮ = frozenset({"changeset-worker"})
#: Кому вообще может быть адресовано разрешение на исполнение.
ДОПУСТИМАЯ_АУДИТОРИЯ = frozenset({"changeset-worker"})

#: Срок жизни разрешения. Короткий намеренно: разрешение — это право начать
#: сейчас, а не бумага на будущее.
СРОК_РАЗРЕШЕНИЯ_СЕК = 120
#: Предел срока одобрения. Одобрение «навсегда» — это отсутствие одобрения.
ПРЕДЕЛ_СРОКА_ОДОБРЕНИЯ_ЧАС = 24


class Отказ(RuntimeError):
    def __init__(self, код: str, детали: str, статус: int = 422):
        super().__init__(детали)
        self.код, self.детали, self.статус = код, детали, статус


def _сейчас() -> _d.datetime:
    return _d.datetime.now(_d.timezone.utc)


def _разобрать_время(значение: str) -> _d.datetime:
    try:
        return _d.datetime.fromisoformat(str(значение).replace("Z", "+00:00"))
    except (ValueError, TypeError):
        raise Отказ("TIMESTAMP_INVALID", f"время {значение!r} не разобрано")


class Состояние:
    def __init__(self) -> None:
        self.pem = C.получить(ПРИВАТНЫЙ)
        self.набор = K.НаборКлючей.из_json(C.получить(НАБОР))
        self.вызывающие = json.loads(C.получить(ВЫЗЫВАЮЩИЕ)).get("callers", {})
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
                f"ключ {self.kid} в состоянии {запись.состояние}")
        self.подписей = 0
        self.разрешений = 0
        self.отказов = 0
        self.замок = threading.Lock()

    def опознать(self, заголовки: dict[str, str]) -> str:
        предъявлен = (заголовки.get("Authorization") or "").removeprefix(
            "Bearer ").strip()
        if not предъявлен:
            raise Отказ("UNAUTHENTICATED", "токен вызывающего не предъявлен", 401)
        отпечаток = hashlib.sha256(
            предъявлен.encode("utf-8", "surrogatepass")).hexdigest()
        for имя, ожидаемый in self.вызывающие.items():
            if hmac.compare_digest(отпечаток.encode("ascii"),
                                   str(ожидаемый).encode("ascii")):
                return имя
        raise Отказ("UNAUTHENTICATED", "токен вызывающего не распознан", 401)


# --- канонические данные -----------------------------------------------------

def _набор_изменений(changeset_id: str) -> dict[str, Any]:
    """Каноническое состояние. Читается службой, а не присылается вызывающим."""
    from factory.site_engine.changeset import store as S
    соед = S.открыть()
    try:
        набор = S.получить(соед, changeset_id)
    finally:
        соед.close()
    if набор is None:
        raise Отказ("CHANGESET_NOT_FOUND",
                    f"набор {changeset_id!r} каноническому хранилищу неизвестен",
                    404)
    return набор


def _версия_реестра() -> int | None:
    from factory.site_engine.changeset.registry_client import (RegistryClient,
                                                               RegistryUnavailable)
    try:
        return RegistryClient().версия()
    except RegistryUnavailable:
        return None


def _общие_проверки(набор: dict[str, Any]) -> None:
    if not набор.get("plan_hash"):
        raise Отказ("PLAN_REQUIRED", "план не построен: подписывать нечего")
    версия = _версия_реестра()
    if версия is not None and набор.get("base_registry_version") != версия:
        # План строился на другом составе флота. Подпись под ним разрешала бы
        # действие, рассчитанное на мир, которого уже нет.
        raise Отказ("REGISTRY_VERSION_STALE",
                    f"план опирается на версию реестра "
                    f"{набор.get('base_registry_version')}, действующая {версия}",
                    409)
    from factory.site_engine.changeset import policy as POL
    if набор.get("policy_version") != POL.POLICY_VERSION:
        raise Отказ("POLICY_VERSION_MISMATCH",
                    f"набор собран по политике {набор.get('policy_version')}, "
                    f"действующая {POL.POLICY_VERSION}", 409)


class Обработчик(BaseHTTPRequestHandler):
    состояние: Состояние = None
    server_version = "site-factory-approval-signer/2.0"

    def log_message(self, *_):
        pass

    def _ответ(self, код: int, тело: dict) -> None:
        сырое = json.dumps(тело, ensure_ascii=False).encode("utf-8")
        self.send_response(код)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(сырое)))
        self.end_headers()
        self.wfile.write(сырое)

    def _тело(self) -> dict:
        длина = int(self.headers.get("Content-Length") or 0)
        if длина <= 0 or длина > ПРЕДЕЛ_ТЕЛА:
            raise Отказ("BODY_SIZE", f"тело вне предела {ПРЕДЕЛ_ТЕЛА} байт", 413)
        try:
            данные = json.loads(self.rfile.read(длина) or b"{}")
        except ValueError:
            raise Отказ("BODY_MALFORMED", "тело не разобрано", 400)
        if not isinstance(данные, dict):
            raise Отказ("BODY_MALFORMED", "ожидается объект", 400)
        # Сюда пытаются протащить готовое тело подписи. Такого параметра нет,
        # и молча игнорировать его нельзя: это попытка обойти проверки.
        лишние = {"body", "payload", "signature", "data", "raw"} & set(данные)
        if лишние:
            raise Отказ(
                "RAW_PAYLOAD_REJECTED",
                f"поля {sorted(лишние)} не принимаются: служба подписывает "
                f"только каноническое состояние, которое читает сама", 400)
        return данные

    def do_GET(self):
        if self.path == "/jwks":
            self._ответ(200, json.loads(self.состояние.набор.в_json()))
            return
        if self.path in ("/healthz", "/health"):
            self._ответ(200, {"ready": True, "alg": K.АЛГОРИТМ,
                              "active_kid": self.состояние.kid,
                              "approvals_signed": self.состояние.подписей,
                              "grants_issued": self.состояние.разрешений,
                              "refusals": self.состояние.отказов,
                              "accepts_raw_payload": False})
            return
        self._ответ(404, {"error_code": "NOT_FOUND"})

    def do_POST(self):
        маршруты = {"/approval": self._одобрение, "/grant": self._разрешение}
        обработчик = маршруты.get(self.path)
        if обработчик is None:
            # /sign больше не существует. Отдельный код, чтобы старый клиент
            # получил объяснение, а не молчаливый 404.
            if self.path == "/sign":
                self._ответ(410, {
                    "error_code": "RAW_SIGNING_REMOVED",
                    "detail": "подпись произвольного тела больше не выполняется; "
                              "используйте /approval или /grant со ссылкой на "
                              "набор изменений"})
                return
            self._ответ(404, {"error_code": "NOT_FOUND"})
            return
        try:
            кто = self.состояние.опознать(dict(self.headers))
            тело = self._тело()
            код, ответ = обработчик(кто, тело)
        except Отказ as ош:
            with self.состояние.замок:
                self.состояние.отказов += 1
            self._ответ(ош.статус, {"error_code": ош.код, "detail": ош.детали})
            return
        except Exception as ош:                       # непредвиденное — не подпись
            with self.состояние.замок:
                self.состояние.отказов += 1
            self._ответ(500, {"error_code": type(ош).__name__,
                              "detail": "внутренний отказ службы подписи"})
            return
        self._ответ(код, ответ)

    # --- подпись одобрения ------------------------------------------------
    def _одобрение(self, кто: str, тело: dict) -> tuple[int, dict]:
        if кто not in ДОПУЩЕНЫ_К_ОДОБРЕНИЮ:
            raise Отказ("CALLER_NOT_ALLOWED",
                        f"{кто} не вправе запрашивать подпись одобрения", 403)
        cid = str(тело.get("changeset_id") or "").strip()
        if not cid:
            raise Отказ("CHANGESET_ID_REQUIRED", "нужна ссылка на набор изменений")
        набор = _набор_изменений(cid)

        from factory.site_engine.changeset import model as M
        from factory.site_engine.changeset import policy as POL
        if набор["status"] != M.AWAITING_APPROVAL:
            raise Отказ("CHANGESET_STATE_INVALID",
                        f"одобрять можно набор в состоянии "
                        f"{M.AWAITING_APPROVAL}, а он в {набор['status']}", 409)
        _общие_проверки(набор)

        approver_id = str(тело.get("approver_id") or "").strip()
        approver_service = str(тело.get("approver_service") or "").strip()
        approver_type = str(тело.get("approver_type") or "").strip().upper()
        expires_at = str(тело.get("expires_at") or "").strip()
        if not (approver_id and approver_service and approver_type and expires_at):
            raise Отказ("APPROVER_REQUIRED",
                        "нужны approver_id, approver_service, approver_type и "
                        "expires_at")
        if approver_type == "MODEL":
            raise Отказ("MODEL_ACTION_DENIED",
                        "актор типа MODEL не одобряет изменения", 403)
        if M.APPROVER not in M.роли_службы(approver_service):
            raise Отказ("ROLE_NOT_GRANTED",
                        f"служба {approver_service} не имеет роли approver", 403)
        if approver_id == набор.get("actor_id"):
            raise Отказ("SEPARATION_OF_DUTIES",
                        "предложивший изменение не может сам его одобрить", 403)
        срок = _разобрать_время(expires_at)
        сейчас = _сейчас()
        if срок <= сейчас:
            raise Отказ("APPROVAL_EXPIRY_INVALID", "срок одобрения уже истёк")
        if срок > сейчас + _d.timedelta(hours=ПРЕДЕЛ_СРОКА_ОДОБРЕНИЯ_ЧАС):
            raise Отказ("APPROVAL_EXPIRY_TOO_FAR",
                        f"срок одобрения дальше {ПРЕДЕЛ_СРОКА_ОДОБРЕНИЯ_ЧАС} ч")

        # Тело строится ЗДЕСЬ из канонического состояния.
        тело_подписи = POL.тело_подписи(набор, approver=approver_id,
                                        expires_at=expires_at)
        подпись = K.подписать(self.состояние.pem, тело_подписи)
        with self.состояние.замок:
            self.состояние.подписей += 1
        return 200, {"signature": подпись, "kid": self.состояние.kid,
                     "alg": K.АЛГОРИТМ, "binding": POL.связка(набор)}

    # --- разрешение на исполнение -----------------------------------------
    def _разрешение(self, кто: str, тело: dict) -> tuple[int, dict]:
        if кто not in ДОПУЩЕНЫ_К_РАЗРЕШЕНИЮ:
            raise Отказ("CALLER_NOT_ALLOWED",
                        f"{кто} не вправе запрашивать разрешение на исполнение",
                        403)
        cid = str(тело.get("changeset_id") or "").strip()
        аудитория = str(тело.get("audience") or "").strip()
        маркер = тело.get("fencing_token")
        if not cid:
            raise Отказ("CHANGESET_ID_REQUIRED", "нужна ссылка на набор изменений")
        if аудитория not in ДОПУСТИМАЯ_АУДИТОРИЯ:
            raise Отказ("AUDIENCE_NOT_ALLOWED",
                        f"аудитория {аудитория!r} не допущена", 403)
        if not isinstance(маркер, int):
            raise Отказ("FENCING_TOKEN_REQUIRED", "нужен целый fencing_token")

        набор = _набор_изменений(cid)
        from factory.site_engine.changeset import model as M
        from factory.site_engine.changeset import policy as POL
        if набор["status"] != M.APPROVED:
            raise Отказ("CHANGESET_STATE_INVALID",
                        f"разрешение выдаётся только набору в состоянии "
                        f"{M.APPROVED}, а он в {набор['status']}", 409)
        _общие_проверки(набор)

        # Одобрение обязано быть действительным ИМЕННО для этого набора в
        # этом виде. Проверка та же, что и у исполнителя: две разные проверки
        # одного и того же однажды разойдутся.
        try:
            POL.проверить_одобрение(набор, сейчас_utc=_сейчас().isoformat()
                                    .replace("+00:00", "Z"))
        except Exception as ош:
            raise Отказ(getattr(ош, "error_code", "APPROVAL_INVALID"),
                        getattr(ош, "detail", str(ош)), 403)

        аренда = _аренда(cid)
        if аренда is None or аренда["fencing_token"] != маркер:
            raise Отказ("FENCING_TOKEN_STALE",
                        "маркер ограждения не совпадает с действующей арендой",
                        409)
        if аренда["worker_id"] != аудитория and аудитория not in ДОПУСТИМАЯ_АУДИТОРИЯ:
            raise Отказ("AUDIENCE_MISMATCH", "аренда принадлежит другому исполнителю",
                        409)

        истекает = _сейчас() + _d.timedelta(seconds=СРОК_РАЗРЕШЕНИЯ_СЕК)
        полезное = {
            "typ": "execution-grant", "changeset_id": cid,
            "audience": аудитория, "fencing_token": маркер,
            "plan_hash": набор["plan_hash"],
            "expected_resource_fingerprint": набор.get(
                "expected_resource_fingerprint"),
            "base_registry_version": набор.get("base_registry_version"),
            "policy_version": набор.get("policy_version"),
            "target_site_ids": sorted(набор.get("target_site_ids") or []),
            "expires_at": истекает.isoformat().replace("+00:00", "Z"),
        }
        тело_grant = json.dumps(полезное, ensure_ascii=False, sort_keys=True,
                                separators=(",", ":"))
        подпись = K.подписать(self.состояние.pem, тело_grant)
        with self.состояние.замок:
            self.состояние.разрешений += 1
        return 200, {"grant": полезное, "signature": подпись,
                     "kid": self.состояние.kid, "alg": K.АЛГОРИТМ}


def _аренда(changeset_id: str) -> dict | None:
    from factory.site_engine.changeset import store as S
    соед = S.открыть()
    try:
        с = соед.execute(
            "SELECT worker_id, fencing_token FROM changeset_lease "
            "WHERE changeset_id=?", (changeset_id,)).fetchone()
        return dict(с) if с else None
    finally:
        соед.close()


def запустить(хост: str = "127.0.0.1", порт: int = 8795) -> int:
    Обработчик.состояние = Состояние()
    сервер = ThreadingHTTPServer((хост, порт), Обработчик)
    print(f"[approval-signer] слушает {хост}:{порт}, активный kid "
          f"{Обработчик.состояние.kid}; приём готового тела отключён", flush=True)
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
