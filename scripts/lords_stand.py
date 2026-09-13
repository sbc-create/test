#!/usr/bin/env python3
"""Локальный стенд витрины: запуск, готовность, остановка, доказательство.

Почему отдельный модуль, а не две строки в каждом сценарии
---------------------------------------------------------

Уборка «найди процессы, в чьей командной строке встречается http.server, и
пошли им сигнал» однажды совпала САМА С СОБОЙ: строка поиска входит в
командную строку самого сценария уборки, он убил собственную обёртку, и
фоновая задача завершилась кодом 144. Сервер при этом был исправен. Отличить
это от настоящего падения по коду возврата нельзя — только по способу
остановки.

Поэтому здесь:

* порт назначает операционная система, а не человек — два стенда рядом не
  дерутся за номер;
* готовность определяется ответом, а не таймером;
* останавливается РОВНО тот процесс, который был запущен, по его
  идентификатору, а не по совпадению строки;
* после остановки проверяется и отсутствие процесса, и освобождение порта.
"""
from __future__ import annotations

import contextlib
import dataclasses
import errno
import pathlib
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request


class СтендНеПоднялся(RuntimeError):
    pass


def свободный_порт() -> int:
    """Порт, назначенный ядром. Закрываем сразу: занимать будет сервер."""
    with contextlib.closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


def порт_занят(порт: int) -> bool:
    with contextlib.closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as s:
        s.settimeout(0.5)
        return s.connect_ex(("127.0.0.1", порт)) == 0


@dataclasses.dataclass
class Стенд:
    корень: pathlib.Path
    порт: int
    процесс: subprocess.Popen
    поднялся_за: float

    @property
    def база(self) -> str:
        return f"http://127.0.0.1:{self.порт}"

    @property
    def pid(self) -> int:
        return self.процесс.pid

    def остановить(self, срок: float = 10.0) -> dict:
        """Остановка и доказательство её полноты.

        Возвращает исход: сигнал, код, освободился ли порт, жив ли процесс.
        `EXPECTED_TERMINATION` — это про способ, а не про код: остановленный
        нами сервер и упавший сервер дают разные поля.
        """
        if self.процесс.poll() is None:
            self.процесс.terminate()
        try:
            код = self.процесс.wait(timeout=срок)
        except subprocess.TimeoutExpired:
            self.процесс.kill()
            код = self.процесс.wait(timeout=срок)
        # Порт освобождается не мгновенно: ждём по факту, а не «на всякий
        # случай» фиксированной паузой.
        до = time.monotonic()
        while порт_занят(self.порт) and time.monotonic() - до < срок:
            time.sleep(0.05)
        return {"pid": self.pid, "returncode": код,
                "signal": -код if код is not None and код < 0 else None,
                "shell_code": (128 - код) if код is not None and код < 0 else код,
                "process_alive": self.процесс.poll() is None,
                "port_released": not порт_занят(self.порт),
                "outcome": "EXPECTED_TERMINATION"}


def поднять(корень, *, срок: float = 20.0) -> Стенд:
    корень = pathlib.Path(корень)
    if not (корень / "index.html").is_file():
        raise СтендНеПоднялся(f"{корень}: это не собранная витрина")
    порт = свободный_порт()
    начало = time.monotonic()
    процесс = subprocess.Popen(
        [sys.executable, "-m", "http.server", str(порт), "--bind", "127.0.0.1"],
        cwd=str(корень), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    пока = time.monotonic()
    while time.monotonic() - пока < срок:
        if процесс.poll() is not None:
            raise СтендНеПоднялся(
                f"сервер вышел до готовности, код {процесс.returncode}")
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{порт}/", timeout=1) as о:
                if о.status == 200:
                    return Стенд(корень, порт, процесс, time.monotonic() - начало)
        except (urllib.error.URLError, OSError):
            time.sleep(0.05)
    процесс.terminate()
    raise СтендНеПоднялся(f"стенд не ответил 200 за {срок} с")


@contextlib.contextmanager
def стенд(корень, **кв):
    с = поднять(корень, **кв)
    try:
        yield с
    finally:
        с.остановить()


if __name__ == "__main__":
    корень = sys.argv[1] if len(sys.argv) > 1 else "var/lords-candidate"
    with стенд(корень) as с:
        print(f"поднялся за {с.поднялся_за:.2f} с, порт {с.порт}, pid {с.pid}")
    print("остановлен")
