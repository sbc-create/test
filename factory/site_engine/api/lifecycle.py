"""Жизненный цикл службы под systemd.

Служба обязана сообщать supervisor не «я запустилась», а «я готова
обслуживать»: между этими состояниями находится протокол запуска, и подъём
зависимой службы до его завершения приводит к отказам, которые выглядят как
случайные.

Здесь три механизма:

* **READY=1** — отправляется после того, как протокол пройден и сокет слушает.
  До этого systemd держит запуск незавершённым, а `TimeoutStartSec` ограничивает
  ожидание. Так `systemctl start` возвращается тогда, когда служба и правда
  готова.
* **WATCHDOG=1** — периодическая отметка живости. Зависший цикл обслуживания
  перестаёт её слать, и systemd перезапускает службу. Без этого зависание
  выглядит как работа: процесс жив, порт слушает, ответов нет.
* **STOPPING=1 и слив** — по SIGTERM служба перестаёт принимать новые запросы,
  дожидается завершения начатых и только потом выходит. Обрыв запроса на
  середине изменяющей операции оставил бы состояние, о котором клиент не узнает.
"""
from __future__ import annotations

import os
import socket
import threading
import time


class Notifier:
    """Отправитель уведомлений systemd.

    Работает и вне systemd: если NOTIFY_SOCKET не задан, все вызовы —
    пустышки. Иначе служба нельзя было бы запустить руками для отладки.
    """

    def __init__(self, address: str | None = None) -> None:
        self._address = address if address is not None else os.environ.get("NOTIFY_SOCKET", "")
        self._sock: socket.socket | None = None
        if self._address:
            try:
                self._sock = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM | socket.SOCK_CLOEXEC)
            except OSError:
                self._sock = None

    @property
    def active(self) -> bool:
        return bool(self._address and self._sock)

    def send(self, message: str) -> bool:
        if not self.active:
            return False
        адрес = self._address
        # Абстрактный сокет: systemd передаёт его с ведущим '@'.
        путь = "\0" + адрес[1:] if адрес.startswith("@") else адрес
        try:
            self._sock.sendto(message.encode("utf-8"), путь)  # type: ignore[union-attr]
            return True
        except OSError:
            return False

    def ready(self, status: str = "") -> bool:
        сообщение = "READY=1"
        if status:
            сообщение += f"\nSTATUS={status}"
        return self.send(сообщение)

    def watchdog(self) -> bool:
        return self.send("WATCHDOG=1")

    def stopping(self, status: str = "") -> bool:
        сообщение = "STOPPING=1"
        if status:
            сообщение += f"\nSTATUS={status}"
        return self.send(сообщение)

    def status(self, text: str) -> bool:
        return self.send(f"STATUS={text}")


def watchdog_interval() -> float:
    """Половина периода, назначенного systemd.

    Половина, а не весь: отметка, отправленная ровно к сроку, приходит после
    него при малейшей задержке, и служба перезапускается на ровном месте.
    """
    сырое = os.environ.get("WATCHDOG_USEC", "")
    try:
        микросекунды = int(сырое)
    except ValueError:
        return 0.0
    if микросекунды <= 0:
        return 0.0
    return (микросекунды / 1_000_000.0) / 2.0


class Lifecycle:
    """Состояние обслуживания: приём запросов, счёт начатых, слив."""

    def __init__(self, *, drain_timeout: float = 25.0, now=time.time) -> None:
        self._lock = threading.Lock()
        self._inflight = 0
        self._accepting = True
        self._drain_timeout = drain_timeout
        self._now = now
        self._idle = threading.Event()
        self._idle.set()

    @property
    def accepting(self) -> bool:
        with self._lock:
            return self._accepting

    @property
    def inflight(self) -> int:
        with self._lock:
            return self._inflight

    def enter(self) -> bool:
        """Начать обслуживание запроса. False — служба сливается."""
        with self._lock:
            if not self._accepting:
                return False
            self._inflight += 1
            self._idle.clear()
            return True

    def leave(self) -> None:
        with self._lock:
            self._inflight = max(0, self._inflight - 1)
            if self._inflight == 0:
                self._idle.set()

    def begin_drain(self) -> None:
        with self._lock:
            self._accepting = False
            if self._inflight == 0:
                self._idle.set()

    def wait_drained(self, timeout: float | None = None) -> bool:
        """Дождаться завершения начатых запросов.

        Возвращает False по истечении срока: тогда вызывающий обязан решить,
        обрывать ли остаток. Молча ждать вечно нельзя — systemd всё равно
        пришлёт SIGKILL по TimeoutStopSec, и слив окажется бессмысленным.
        """
        срок = self._drain_timeout if timeout is None else timeout
        return self._idle.wait(timeout=срок)
