"""Сервис Secret Hub: единственный процесс, внутри которого существуют значения.

Транспорт — unix-сокет, а не TCP: право обратиться к хабу выдаётся правами на
файл сокета, и «случайно опубликовать порт наружу» здесь нечего. Протокол —
одна JSON-строка запроса, одна JSON-строка ответа.

Главное свойство модуля выражено списком :data:`OPERATIONS`: операции, которая
возвращает значение секрета, в нём нет. Это не соглашение и не дисциплина
вызывающего — ответ собирается из :class:`~factory.secret_hub.store.PortfolioState`
и результатов применения, а в них значений нет по построению. Проверяется тестом
``test_no_read_endpoint``: он перебирает все операции, вызывает каждую и ищет
значение в сериализованном ответе.

Что сервис умеет:

* ``list``   — какие направления описаны;
* ``status`` — настроено ли, проверено ли, когда, версия, отпечаток, потребители;
* ``verify`` — живой read-only запрос к провайдеру и обновление ``verified_at``;
* ``apply``  — применение к инфраструктуре направления;
* ``rotate`` — новая версия из уже введённых значений (перевыдача потребителям);
* ``revoke`` — отзыв активной версии без её удаления;
* ``import`` — перенос существующих файлов credentials внутрь хранилища.

Значения приходят единственным путём — операцией ``store`` от панели. У неё
есть вход, но нет выхода: в ответе версия, отпечаток и исход проверки, а само
значение не возвращается ни одной операцией. Право писать проверяется по uid
пира сокета, см. :data:`PANEL_ONLY_OPERATIONS`.
"""
from __future__ import annotations

import json
import os
import socket
import socketserver
import stat
import struct
import threading
from dataclasses import dataclass
from dataclasses import field as dataclass_field
from datetime import UTC
from pathlib import Path

from factory.errors import BlockedTarget, FactoryError
from factory.redaction import redact
from factory.secret_hub import SECRET_FIELDS
from factory.secret_hub.crypto import MasterKey, inspect_key_file, load_master_key
from factory.secret_hub.registry import HubConfig, Portfolio
from factory.secret_hub.registry import load as load_config
from factory.secret_hub.store import Store

#: Максимальный размер запроса. Управляющие команды коротки; всё, что длиннее,
#: не запрос, а попытка что-то сделать с парсером.
MAX_REQUEST_BYTES = 64 * 1024

#: Права сокета: владелец root, группа управления. Членство в группе даёт право
#: спросить и запустить, но не право увидеть — API значений не отдаёт.
SOCKET_MODE = 0o660

OPERATIONS = ("list", "status", "verify", "apply", "rotate", "revoke", "import",
              "store")

#: Операции, которые принимает только панель. Право проверяется по uid пира
#: unix-сокета (SO_PEERCRED), а не по членству в группе: в группе управления
#: состоит и учётная запись агента, и ей позволено спрашивать, но не писать.
#: «Записать» — это не «прочитать», однако подменить credentials направления
#: означало бы увести весь портфель на чужой токен.
PANEL_ONLY_OPERATIONS = frozenset({"store"})


#: Операции, меняющие состояние направления. Два таких вызова для одного
#: направления обязаны идти по очереди: параллельные `apply` дерутся за одни и
#: те же файлы, а параллельные `rotate` создают две версии, из которых
#: применяется неизвестно какая.
MUTATING_OPERATIONS = frozenset({"apply", "rotate", "revoke", "import", "store"})


@dataclass
class Hub:
    """Логика хаба без транспорта. Тестируется напрямую, без сокета."""

    config: HubConfig
    master: MasterKey
    store: Store
    #: Замки по направлениям. Глобального замка здесь нет намеренно: `enroll`
    #: держит форму до пятнадцати минут, и общий замок сделал бы `status`
    #: недоступным на всё это время.
    _locks: dict = dataclass_field(default_factory=dict)
    _locks_guard: threading.Lock = dataclass_field(default_factory=threading.Lock)

    def _portfolio_lock(self, portfolio_id: str) -> threading.RLock:
        with self._locks_guard:
            return self._locks.setdefault(portfolio_id, threading.RLock())

    def _peer_may_write(self, peer_uid: int | None) -> bool:
        """Может ли пир записывать credentials.

        ``None`` означает вызов внутри процесса (root-команда, тесты) — там
        проверять нечего. Из сокета uid приходит от ядра: подделать его
        клиент не может, в отличие от любого поля в теле запроса.
        """
        if peer_uid is None:
            return True
        if peer_uid == 0:
            return True
        return peer_uid == _panel_uid(self.config.panel_user)

    # --- операции ---------------------------------------------------------
    def op_list(self, _: dict) -> dict:
        return {
            "portfolios": [
                {
                    "portfolio": p.id,
                    "title": p.title,
                    "enabled": p.enabled,
                    "deployable": p.deployable,
                    "consumers": [c.id for c in p.consumers],
                    "blocked_target": p.blocked_target.as_dict() if p.blocked_target else None,
                }
                for p in self.config.portfolios
            ]
        }

    def op_status(self, payload: dict) -> dict:
        requested = payload.get("portfolio")
        targets = [self.config.portfolio(requested)] if requested else list(self.config.portfolios)
        rows = [self._status_row(p) for p in targets]
        return {
            "master_key": inspect_key_file().as_dict(),
            "store": {
                "path": str(self.config.db_path),
                "permission_problems": self.store.check_permissions(),
            },
            "portfolios": rows,
        }

    def _status_row(self, portfolio: Portfolio) -> dict:
        from factory.secret_hub import consumers as consumers_mod

        state = self.store.state(portfolio.id)
        row = {
            "portfolio": portfolio.id,
            "title": portfolio.title,
            "configured": state.configured,
            "verified": state.verified,
            "updated_at": state.updated_at,
            "verified_at": state.verified_at,
            "fingerprint": state.fingerprint,
            "version": state.active_version,
            "status": state.status,
            "consumers": consumers_mod.describe(portfolio),
            "deployment": [d.as_dict() for d in state.deployments],
        }
        if portfolio.blocked_target is not None:
            row["status"] = portfolio.blocked_target.status
            row["blocked_target"] = portfolio.blocked_target.as_dict()
        return row

    def op_verify(self, payload: dict) -> dict:
        from factory.secret_hub import provider

        portfolio = self.config.portfolio(_require(payload, "portfolio"))
        state = self.store.state(portfolio.id)
        if not state.configured:
            return {
                "portfolio": portfolio.id,
                "outcome": "not_configured",
                "reason": "Направление не настроено: проверять нечего.",
            }
        values = self.store.reveal_for_apply(portfolio.id)
        result = provider.verify(self.config.verify, values["api_token"], values["publisher_id"],
                                 portfolio=portfolio.id)
        if result.ok and state.active_version is not None:
            self.store.mark_verified(portfolio.id, state.active_version)
        response = {"portfolio": portfolio.id, **result.as_dict()}
        response["verified_at"] = self.store.state(portfolio.id).verified_at
        return response

    def op_apply(self, payload: dict) -> dict:
        from factory.secret_hub import consumers as consumers_mod
        from factory.secret_hub import provider

        portfolio = self.config.portfolio(_require(payload, "portfolio"))
        if portfolio.blocked_target is not None:
            raise BlockedTarget(
                f"Направление «{portfolio.id}»: {portfolio.blocked_target.reason}",
                field=portfolio.id,
                required_input=portfolio.blocked_target.required_input,
                blocks_stage="STAGING_DEPLOY",
            )
        state = self.store.state(portfolio.id)
        if not state.configured:
            return {"portfolio": portfolio.id, "ok": False, "status": "not_configured",
                    "reason": "Направление не настроено: применять нечего."}

        # Бэкап хранилища до единой мутации на хосте. Требование задания:
        # «перед применением сделать backup зашифрованного хранилища».
        backup = self.store.backup(self.config.backup_dir, tag=f"apply-{portfolio.id}")

        values = self.store.reveal_for_apply(portfolio.id)
        result = provider.verify(self.config.verify, values["api_token"], values["publisher_id"],
                                 portfolio=portfolio.id)
        if not result.ok:
            # Применять непроверенное к работающему сайту нельзя: работающий
            # сайт при этом ничем не рискует — мы просто ничего не трогаем.
            return {"portfolio": portfolio.id, "ok": False, "status": "verification_failed",
                    "reason": result.reason, "verify": result.as_dict(),
                    "store_backup": str(backup)}
        self.store.mark_verified(portfolio.id, state.active_version or 0)

        report = consumers_mod.apply_portfolio(
            portfolio, values, version=state.active_version,
            backup_root=self.config.store_dir / "consumer-backups",
            restart=bool(payload.get("restart", True)),
        )
        for consumer_result in report.results:
            self.store.record_deployment(
                portfolio.id, consumer_result.consumer_id,
                version=state.active_version if consumer_result.status == "applied" else None,
                status=consumer_result.status, detail=consumer_result.detail,
            )
        return {"portfolio": portfolio.id, "store_backup": str(backup), **report.as_dict()}

    def op_rotate(self, payload: dict) -> dict:
        """Перевыдача действующего значения новой версией.

        Ротация без нового значения не выдумывает токен: она создаёт новую
        версию из уже проверенного набора и заново применяет его потребителям.
        Смена самого значения — это ввод через форму, а не `rotate`.
        """
        portfolio = self.config.portfolio(_require(payload, "portfolio"))
        state = self.store.state(portfolio.id)
        if not state.configured:
            return {"portfolio": portfolio.id, "ok": False, "status": "not_configured",
                    "reason": "Направление не настроено: ротировать нечего."}
        self.store.backup(self.config.backup_dir, tag=f"rotate-{portfolio.id}")
        values = self.store.reveal_for_apply(portfolio.id)
        version = self.store.put(portfolio.id, values, provider=self.config.provider_name,
                                 verified_at=None)
        response = {"portfolio": portfolio.id, "ok": True, "status": "rotated", "version": version}
        if payload.get("apply", True) and portfolio.deployable:
            response["apply"] = self.op_apply({"portfolio": portfolio.id,
                                               "restart": payload.get("restart", True)})
        return response

    def op_revoke(self, payload: dict) -> dict:
        portfolio = self.config.portfolio(_require(payload, "portfolio"))
        self.store.backup(self.config.backup_dir, tag=f"revoke-{portfolio.id}")
        version = self.store.revoke(portfolio.id)
        # Файлы у потребителей не стираются: снятие credentials с работающего
        # сайта — отдельное решение оператора, а не побочный эффект отзыва.
        # Отзыв означает «эта версия больше не выдаётся», и статус это покажет.
        return {"portfolio": portfolio.id, "ok": True, "status": "revoked",
                "revoked_version": version,
                "note": "Значение сохранено для отката. Файлы у потребителей не изменены: "
                        "снятие credentials с работающего сайта выполняется отдельно."}

    def op_store(self, payload: dict) -> dict:
        """Принимает новые значения от панели. Наружу ничего не возвращает.

        Единственная операция API, у которой значения есть во входе. В выходе
        их нет и быть не может: ответ — версия, отпечаток и исход проверки.
        Асимметрия намеренная: панель обязана уметь записать новый токен и
        обязана не уметь прочитать записанный.
        """
        from factory.errors import BlockedInput
        from factory.secret_hub.crypto import Secret

        portfolio = self.config.portfolio(_require(payload, "portfolio"))
        api_token = str(payload.get("api_token") or "")
        publisher_id = str(payload.get("publisher_id") or "")
        if not api_token.strip() or not publisher_id.strip():
            raise BlockedInput(
                "Оба поля обязательны: пустое поле — не разрешение работать без значения.",
                field="api_token/publisher_id",
                required_input="Непустые API Token и Publisher ID",
                blocks_stage="VALIDATING",
            )
        values = {
            "api_token": Secret(api_token, label=f"{portfolio.id}/api_token"),
            "publisher_id": Secret(publisher_id, label=f"{portfolio.id}/publisher_id"),
        }
        result = self.store_verified(portfolio.id, values)
        # Значения не переживают обработчик: ни в локальных именах, ни в теле
        # запроса, которое вызывающий может залогировать.
        del values, api_token, publisher_id
        payload.pop("api_token", None)
        payload.pop("publisher_id", None)

        response = {
            "portfolio": portfolio.id,
            "stored": bool(result.get("stored")),
            "version": result.get("version"),
            "fingerprint": result.get("fingerprint"),
            "verify": result.get("verify"),
        }
        if not result.get("stored"):
            response["ok"] = False
            response["reason"] = result.get("reason", "провайдер не подтвердил credentials")
        return response

    def op_import(self, payload: dict) -> dict:
        from factory.secret_hub import migrate

        return migrate.import_existing(self, _require(payload, "portfolio"),
                                       archive=bool(payload.get("archive", False)))

    # --- запись значений (только изнутри процесса) ------------------------
    def store_verified(self, portfolio_id: str, values: dict) -> dict:
        """Проверить и записать. Единственный путь, которым значение попадает в базу.

        Метод не является операцией API: он вызывается формой ввода и импортом,
        которые живут внутри этого же процесса. Неверные значения не пишутся —
        проверка идёт до ``put``, а не после.
        """
        from factory.secret_hub import provider

        result = provider.verify(self.config.verify, values["api_token"], values["publisher_id"],
                                 portfolio=portfolio_id)
        if not result.may_store:
            return {"stored": False, "verify": result.as_dict(), "reason": result.reason}
        self.store.backup(self.config.backup_dir, tag=f"pre-store-{portfolio_id}")
        version = self.store.put(portfolio_id, values, provider=self.config.provider_name,
                                 verified_at=_now())
        return {"stored": True, "version": version, "verify": result.as_dict(),
                "fingerprint": self.store.state(portfolio_id).fingerprint}

    # --- диспетчер --------------------------------------------------------
    def handle(self, request: dict, *, peer_uid: int | None = None) -> dict:
        op = request.get("op")
        if op not in OPERATIONS:
            return {"ok": False, "error": "unknown_operation",
                    "reason": f"Неизвестная операция «{op}». Доступны: {', '.join(OPERATIONS)}."}
        if op in PANEL_ONLY_OPERATIONS and not self._peer_may_write(peer_uid):
            return {"ok": False, "error": "BLOCKED_AUTHORIZATION",
                    "reason": "Запись credentials разрешена только процессу панели.",
                    "field": "peer_uid",
                    "required_input": "Запрос от учётной записи панели или root",
                    "blocks_stage": "VALIDATING"}
        handler = getattr(self, f"op_{op}")
        try:
            if op in MUTATING_OPERATIONS and request.get("portfolio"):
                with self._portfolio_lock(str(request["portfolio"])):
                    payload = handler(request)
            else:
                payload = handler(request)
        except FactoryError as exc:
            return {"ok": False, "error": exc.status, **exc.as_blocker()}
        except Exception as exc:  # pragma: no cover - защитная сетка
            return {"ok": False, "error": "QUARANTINED",
                    "reason": redact(f"{exc.__class__.__name__}: {exc}")}
        payload.setdefault("ok", True)
        return payload


def _require(payload: dict, name: str) -> str:
    value = payload.get(name)
    if not value:
        from factory.errors import BlockedInput

        raise BlockedInput(
            f"Не передан обязательный параметр «{name}».",
            field=name, required_input=name, blocks_stage="VALIDATING",
        )
    return str(value)


def _panel_uid(user: str | None) -> int | None:
    """uid учётной записи панели или ``None``, если её на хосте нет."""
    if not user:
        return None
    import pwd

    try:
        return pwd.getpwnam(user).pw_uid
    except KeyError:
        return None


def _now() -> str:
    from datetime import datetime

    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


# --- транспорт ------------------------------------------------------------
class _Handler(socketserver.StreamRequestHandler):
    hub: Hub

    def handle(self) -> None:
        raw = self.rfile.readline(MAX_REQUEST_BYTES + 1)
        if len(raw) > MAX_REQUEST_BYTES:
            self._reply({"ok": False, "error": "request_too_large"})
            return
        try:
            request = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            self._reply({"ok": False, "error": "bad_request"})
            return
        if not isinstance(request, dict):
            self._reply({"ok": False, "error": "bad_request"})
            return
        self._reply(self.hub.handle(request, peer_uid=self._peer_uid()))

    def _peer_uid(self) -> int | None:
        """uid процесса на том конце сокета, по данным ядра.

        ``SO_PEERCRED`` возвращает то, что ядро знает о подключившемся
        процессе. Это единственный источник, которому здесь можно верить: любое
        поле в теле запроса клиент пишет сам.
        """
        try:
            raw = self.connection.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED,
                                             struct.calcsize("3i"))
            _pid, uid, _gid = struct.unpack("3i", raw)
            return uid
        except (OSError, AttributeError, struct.error):
            # Не смогли измерить — значит не подтвердили. Право записи выдаётся
            # только по подтверждённому uid, поэтому здесь безопаснее вернуть
            # заведомо не подходящее значение, чем None («вызов изнутри»).
            return -1

    def _reply(self, payload: dict) -> None:
        # redact поверх готового ответа — последняя сетка. Значений здесь быть
        # не должно и по построению их нет; сетка стоит на случай, если кто-то
        # добавит поле, не подумав.
        text = redact(json.dumps(payload, ensure_ascii=False))
        self.wfile.write(text.encode("utf-8") + b"\n")


class _Server(socketserver.ThreadingUnixStreamServer):
    daemon_threads = True
    allow_reuse_address = True
    # Очередь ожидающих подключений. Значение socketserver по умолчанию — 5, и
    # при восьми одновременных клиентах ядро отвергает лишние с EAGAIN: клиент
    # видит «ресурс временно недоступен» вместо ответа. Панель обращается к
    # хабу в один поток, но `factory secrets status` из нескольких сессий и
    # параллельные проверки упираются в этот предел — а обнаружился он на
    # медленном раннере CI, а не здесь.
    request_queue_size = 64


def serve(config: HubConfig | None = None, *, master: MasterKey | None = None,
          ready: threading.Event | None = None) -> None:
    """Запускает сервис. Вызывается только root-owned unit'ом."""
    config = config or load_config()
    master = master or load_master_key()
    store = Store(config.db_path, master)
    hub = Hub(config, master, store)

    socket_path = config.socket_path
    socket_path.parent.mkdir(parents=True, exist_ok=True, mode=0o755)
    if socket_path.exists():
        socket_path.unlink()

    handler = type("_BoundHandler", (_Handler,), {"hub": hub})
    # umask на время создания сокета: без него файл появляется с правами,
    # которые оставил вызывающий, и на короткое время может быть доступен миру.
    previous = os.umask(0o177)
    try:
        server = _Server(str(socket_path), handler)
    finally:
        os.umask(previous)
    os.chmod(socket_path, SOCKET_MODE)
    _apply_socket_group(socket_path, config.control_group)
    if ready is not None:
        ready.set()
    try:
        server.serve_forever()
    finally:
        server.server_close()
        if socket_path.exists():
            socket_path.unlink()


def _apply_socket_group(socket_path: Path, group: str | None) -> None:
    """Выдаёт группе управления право обратиться к сокету.

    Отсутствие группы — не повод открыть сокет всем: тогда хаб останется
    доступен только root, и это правильный отказ по умолчанию.
    """
    if not group or os.geteuid() != 0:
        return
    import grp
    import shutil as shutil_mod

    try:
        grp.getgrnam(group)
    except KeyError:
        return
    shutil_mod.chown(socket_path, group=group)
    os.chmod(socket_path, SOCKET_MODE)


def socket_status(socket_path: Path) -> dict:
    """Состояние сокета без обращения к нему — для `status` и проверок."""
    try:
        info = socket_path.stat()
    except FileNotFoundError:
        return {"path": str(socket_path), "exists": False}
    except OSError as exc:
        return {"path": str(socket_path), "exists": None,
                "problem": f"не проверен ({exc.__class__.__name__})"}
    mode = stat.S_IMODE(info.st_mode)
    return {
        "path": str(socket_path),
        "exists": True,
        "is_socket": stat.S_ISSOCK(info.st_mode),
        "mode": format(mode, "04o"),
        "owner_is_root": info.st_uid == 0,
        "world_accessible": bool(mode & 0o007),
    }


def request(socket_path: Path, payload: dict, *, timeout: float = 120.0) -> dict:
    """Один запрос к сервису. Используется клиентом CLI."""
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as sock:
        sock.settimeout(timeout)
        sock.connect(str(socket_path))
        sock.sendall(json.dumps(payload, ensure_ascii=False).encode("utf-8") + b"\n")
        chunks: list[bytes] = []
        while True:
            chunk = sock.recv(65536)
            if not chunk:
                break
            chunks.append(chunk)
            if chunks[-1].endswith(b"\n"):
                break
    return json.loads(b"".join(chunks).decode("utf-8"))


#: Значения, которых не должно быть ни в одном ответе. Список используется
#: тестом «нет endpoint'а чтения» и проверкой отсутствия значений в логах.
FORBIDDEN_RESPONSE_KEYS = frozenset(SECRET_FIELDS) | {"value", "secret", "token", "plaintext"}
