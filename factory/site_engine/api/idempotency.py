"""Идемпотентность, надёжная между процессами и перезапусками.

Прежняя редакция проверяла наличие записи, а результат сохраняла позже. Между
этими двумя действиями второй процесс успевал не найти записи и выполнить ту же
команду ещё раз: повтор после таймаута создавал второе задание. Здесь заявка
делается атомарно, до выполнения.

Три состояния и почему они разные:

* **RESERVED** — заявка наша, команду выполняем мы.
* **IN_PROGRESS** — заявку держит кто-то другой и срок аренды не истёк. Ответ
  409, а не ожидание: повтор пришёл потому, что клиент не дождался первого,
  и заставлять его ждать снова значит удваивать таймаут вместо ответа.
* **REPLAY** / **CONFLICT** — команда уже выполнена. Тот же отпечаток запроса
  возвращает прежний ответ; другой отпечаток под тем же ключом — конфликт,
  потому что это другая команда под уже использованным ключом.

Аренда нужна на случай смерти процесса после заявки: без неё ключ остался бы
занят навсегда и повтор никогда бы не прошёл. По истечении аренды заявка
переходит к новому исполнителю — с записью об этом.
"""
from __future__ import annotations

import errno
import fcntl
import hashlib
import json
import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# Сколько заявка считается живой без результата. Больше самой долгой мутации,
# но меньше терпения клиента: иначе застрявшая заявка блокирует повторы дольше,
# чем кто-либо готов ждать.
LEASE_SECONDS = 120.0

# Сколько хранится результат. Повтор после этого срока выполнится заново — это
# осознанный размен: вечное хранение превращает каталог в свалку, а окно в
# сутки покрывает любые разумные повторы.
RESULT_TTL_SECONDS = 24 * 3600.0

RESERVED = "reserved"
IN_PROGRESS = "in_progress"
REPLAY = "replay"
CONFLICT = "conflict"
TAKEOVER = "takeover"


@dataclass
class Reservation:
    state: str
    key: str = ""
    stored: dict[str, Any] = field(default_factory=dict)
    holder: str = ""
    age_seconds: float = 0.0

    @property
    def may_execute(self) -> bool:
        return self.state in (RESERVED, TAKEOVER)


def fingerprint(method: str, path: str, body: dict[str, Any]) -> str:
    blob = json.dumps({"m": method, "p": path, "b": body}, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


class IdempotencyStore:
    def __init__(self, state_dir: Path | str, *, now=time.time, owner: str | None = None) -> None:
        self._dir = Path(state_dir) / "control-idempotency"
        self._now = now
        # Кто держит заявку: полезно в журнале, когда заявка зависла и нужно
        # понять, какой процесс её не завершил.
        self._owner = owner or f"pid-{os.getpid()}"

    def _path(self, key: str) -> Path:
        return self._dir / f"{hashlib.sha256(key.encode()).hexdigest()[:32]}.json"

    def reserve(self, key: str, fp: str) -> Reservation:
        self._dir.mkdir(parents=True, exist_ok=True)
        path = self._path(key)
        now = float(self._now())
        запись = {"fingerprint": fp, "state": "in_progress", "owner": self._owner,
                  "leased_at": now, "key_hint": key[:64]}
        try:
            # O_EXCL: создание либо удалось, либо кто-то уже создал. Проверить
            # наличие и потом создать — это те же два действия, между которыми
            # успевает второй процесс.
            fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        except FileExistsError:
            return self._inspect(path, fp, now)
        except OSError as exc:
            if exc.errno != errno.EEXIST:
                raise
            return self._inspect(path, fp, now)
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(запись, fh, ensure_ascii=False)
            fh.flush()
            os.fsync(fh.fileno())
        return Reservation(RESERVED, key=key)

    def _inspect(self, path: Path, fp: str, now: float) -> Reservation:
        try:
            with open(path, "r+", encoding="utf-8") as fh:
                fcntl.flock(fh.fileno(), fcntl.LOCK_EX)
                try:
                    fh.seek(0)
                    raw = fh.read()
                    данные = json.loads(raw) if raw.strip() else {}
                except json.JSONDecodeError:
                    данные = {}
                if not isinstance(данные, dict):
                    данные = {}

                сохранённый = данные.get("fingerprint")
                состояние = данные.get("state")

                if состояние == "done":
                    if сохранённый != fp:
                        return Reservation(CONFLICT, stored=данные)
                    if now - float(данные.get("done_at", now)) > RESULT_TTL_SECONDS:
                        # Срок хранения вышел: заявка берётся заново.
                        return self._claim(fh, fp, now, TAKEOVER)
                    return Reservation(REPLAY, stored=данные)

                # Заявка не завершена.
                if сохранённый != fp and сохранённый is not None:
                    return Reservation(CONFLICT, stored=данные)
                возраст = now - float(данные.get("leased_at", now))
                if возраст <= LEASE_SECONDS:
                    return Reservation(IN_PROGRESS, holder=str(данные.get("owner", "")),
                                       age_seconds=возраст)
                # Аренда истекла: исполнитель, судя по всему, умер.
                return self._claim(fh, fp, now, TAKEOVER)
        except FileNotFoundError:
            # Запись убрали между попыткой создания и осмотром: пусть вызывающий
            # попробует ещё раз, а не получит ложный конфликт.
            return Reservation(RESERVED)

    def _claim(self, fh, fp: str, now: float, state: str) -> Reservation:
        запись = {"fingerprint": fp, "state": "in_progress", "owner": self._owner,
                  "leased_at": now, "taken_over": True}
        fh.seek(0)
        fh.truncate()
        json.dump(запись, fh, ensure_ascii=False)
        fh.flush()
        os.fsync(fh.fileno())
        return Reservation(state)

    def commit(self, key: str, fp: str, status: int, body: dict[str, Any]) -> None:
        path = self._path(key)
        запись = {"fingerprint": fp, "state": "done", "status": status, "body": body,
                  "owner": self._owner, "done_at": float(self._now())}
        # Через временный файл и переименование: прерванная запись результата
        # оставила бы обрезанный JSON, который выглядит как испорченная заявка.
        tmp = path.with_suffix(".tmp")
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(запись, fh, ensure_ascii=False)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, path)

    def release(self, key: str) -> None:
        """Снять незавершённую заявку.

        Нужно, когда команда отклонена до выполнения: держать ключ занятым
        после отказа значит запретить исправленный повтор с тем же ключом.
        """
        path = self._path(key)
        try:
            with open(path, "r+", encoding="utf-8") as fh:
                fcntl.flock(fh.fileno(), fcntl.LOCK_EX)
                fh.seek(0)
                raw = fh.read()
                данные = json.loads(raw) if raw.strip() else {}
            if isinstance(данные, dict) and данные.get("state") == "in_progress":
                path.unlink(missing_ok=True)
        except (FileNotFoundError, json.JSONDecodeError):
            return

    def cleanup(self, *, older_than: float = RESULT_TTL_SECONDS) -> int:
        """Удалить просроченные записи. Вызывается по расписанию, не в запросе."""
        if not self._dir.is_dir():
            return 0
        now = float(self._now())
        убрано = 0
        for path in self._dir.glob("*.json"):
            try:
                данные = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            отметка = float(данные.get("done_at") or данные.get("leased_at") or now)
            срок = older_than if данные.get("state") == "done" else LEASE_SECONDS * 4
            if now - отметка > срок:
                path.unlink(missing_ok=True)
                убрано += 1
        return убрано
