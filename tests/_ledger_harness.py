"""Эфемерный Audit Ledger для тестов: одна реализация на всех потребителей.

Порядок запуска здесь не придуман заново. Он перенесён из `tests/audit/run_tests.py`,
который поднимал экземпляр для ручного прогона, и вынесен сюда, чтобы pytest и
скрипт пользовались одним и тем же кодом. Вторая реализация того же запуска
разошлась бы с первой молча, и разошлась бы именно в том месте, где проверка
перестала бы что-либо значить.

Отличие от прежнего запуска ровно одно и оно намеренное: экземпляр поднимается
из **рабочего дерева** и поверх **пустой** базы. Прежний брал выложенный релиз
`/srv/site-factory/control-api/current` и копию канонического журнала, поэтому
существовал только на хосте, где всё это уже выложено. В CI такого хоста нет, а
тест, который там не запускается, ничего не гарантирует.

Чего здесь нет и не будет:

* боевых учётных данных. Токены генерируются для прогона, серверу передаются
  только их SHA-256 отпечатки — значения не покидают тестовый процесс;
* обращения к каноническому журналу. База создаётся пустой во временном
  каталоге и удаляется вместе с ним;
* мягкой деградации. Не поднявшаяся служба — это провал прогона, а не повод
  пропустить тесты: `ЖурналНеПоднялся` обязан долететь до pytest. Пропуск
  превратил бы «служба сломана» в «всё хорошо», а именно это и нужно поймать.
"""

from __future__ import annotations

import contextlib
import ctypes
import hashlib
import json
import os
import shutil
import signal
import socket
import sqlite3
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path

КОРЕНЬ = Path(__file__).resolve().parent.parent

#: Токены прогона. Значения фиксированы, чтобы падение было воспроизводимым, и
#: бессмысленны за его пределами: сервер сверяет отпечатки, а отпечаток чужого
#: токена не подойдёт ни к одной настоящей службе.
ТОКЕНЫ = {
    "AUDIT_TOKEN_ARCHITECT": "test-only-architect-token",
    "AUDIT_TOKEN_REGISTRY": "test-only-registry-token",
    "AUDIT_TOKEN_QWEN": "test-only-qwen-token",
    "AUDIT_TOKEN_TEMPLATES": "test-only-templates-token",
}

#: Сигнал ребёнку при смерти родителя. Без него убитая -9 обвязка оставляет
#: экземпляр жить: `finally` не выполняется, порт остаётся занят, и следующий
#: прогон падает на чужом сервере, приняв его за свой.
PR_SET_PDEATHSIG = 1

#: Сколько ждать готовности. Запас на медленный CI, но не бесконечность: вечное
#: ожидание не отличается от зависания.
ГОТОВНОСТЬ_СЕК = 60.0


class ЖурналНеПоднялся(RuntimeError):
    """Служба не стартовала или не ответила на /health в отведённое время."""


def _умереть_с_родителем() -> None:
    with contextlib.suppress(OSError):
        ctypes.CDLL("libc.so.6", use_errno=True).prctl(PR_SET_PDEATHSIG, signal.SIGKILL, 0, 0, 0)


def свободный_порт() -> int:
    """Порт выбирает ядро. Фиксированный номер столкнул бы два прогона на хосте."""
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


@dataclass
class Экземпляр:
    """Поднятый экземпляр журнала и всё, что нужно потребителю."""

    порт: int
    каталог: Path
    процесс: subprocess.Popen
    окружение: dict[str, str] = field(default_factory=dict)

    @property
    def адрес(self) -> str:
        return f"http://127.0.0.1:{self.порт}"

    @property
    def журнал_службы(self) -> str:
        файл = self.каталог / "server.log"
        return файл.read_text(encoding="utf-8") if файл.is_file() else ""

    def погасить(self) -> None:
        """Завершить службу и убрать временные данные. Вызывается всегда."""
        if self.процесс.poll() is None:
            self.процесс.terminate()
            try:
                self.процесс.wait(timeout=30)
            except subprocess.TimeoutExpired:
                self.процесс.kill()
                self.процесс.wait(timeout=10)
        shutil.rmtree(self.каталог, ignore_errors=True)


#: Сайты эфемерного реестра. Это идентификаторы прогона, а не перепись флота:
#: набору важно лишь, что реестр НЕ ПУСТ.
САЙТЫ_ПРОГОНА = ("ephemeral-ledger-site-a", "ephemeral-ledger-site-b")


def _реестр(каталог: Path) -> Path:
    """Пустой реестр молча выключает проверку site_id — поэтому он не пустой.

    `ledger_api.известные_сайты()` при отсутствующем файле возвращает пустое
    множество, а вызывающий превращает пустое в `None`, и `store.append`
    пропускает проверку идентификатора целиком. То есть без реестра событие с
    любым выдуманным `site_id` принимается с кодом 201 — и набор, который
    как раз это и проверяет, краснеет не потому, что проверка сломана, а
    потому, что её не на чем выполнить.

    Двух записей достаточно: тесты подают заведомо неизвестные идентификаторы
    и ждут отказа. Совпадать с настоящим флотом этим именам не нужно и не
    следует — выдумывать состав боевого реестра здесь было бы неправдой.
    """
    путь = каталог / "registry.sqlite3"
    с = sqlite3.connect(путь)
    try:
        с.executescript(
            """
            CREATE TABLE site (
              site_id TEXT PRIMARY KEY,
              environment TEXT NOT NULL,
              lifecycle_state TEXT NOT NULL,
              canonical_domain TEXT
            );
            CREATE TABLE outbox (
              seq INTEGER PRIMARY KEY AUTOINCREMENT,
              event_id TEXT NOT NULL UNIQUE,
              event_type TEXT NOT NULL,
              site_id TEXT NOT NULL,
              correlation_id TEXT NOT NULL,
              causation_id TEXT,
              occurred_at TEXT NOT NULL,
              aggregate_version INTEGER NOT NULL,
              registry_version INTEGER NOT NULL
            );
            """
        )
        for site_id in САЙТЫ_ПРОГОНА:
            с.execute(
                "INSERT INTO site (site_id, environment, lifecycle_state, "
                "canonical_domain) VALUES (?, 'test', 'ACTIVE', ?)",
                (site_id, f"{site_id}.invalid"),
            )
            с.execute(
                "INSERT INTO outbox (event_id, event_type, site_id, "
                "correlation_id, causation_id, occurred_at, aggregate_version, "
                "registry_version) VALUES (?, 'site.registered.v1', ?, ?, NULL, "
                "?, 1, ?)",
                (
                    f"ephemeral-registry-event-{site_id}",
                    site_id,
                    f"ephemeral-corr-{site_id}",
                    "2026-01-01T00:00:00Z",
                    1,
                ),
            )
        с.commit()
    finally:
        с.close()
    return путь


def _учётные_данные(каталог: Path) -> Path:
    """Каталог учётных данных прогона: только отпечатки, не значения.

    Сервер опознаёт службы по SHA-256 отпечаткам. Раздать ему сами токены
    значило бы вернуть модель, в которой утечка на стороне проверяющего выдаёт
    личности всех служб сразу.
    """
    креды = каталог / "credentials"
    креды.mkdir(parents=True, exist_ok=True)
    отпечатки = {
        имя.removeprefix("AUDIT_TOKEN_").lower(): hashlib.sha256(значение.encode()).hexdigest()
        for имя, значение in ТОКЕНЫ.items()
    }
    (креды / "audit-token-fingerprints").write_text(
        json.dumps({"services": отпечатки, "revoked": []}), encoding="utf-8"
    )
    return креды


def поднять(*, корень: Path | None = None, python: str | None = None) -> Экземпляр:
    """Поднять журнал поверх пустой временной базы и дождаться готовности.

    Не возвращает управление, пока `/api/v1/audit/health` не ответил: тест,
    начавшийся раньше готовности, измерял бы скорость старта, а не поведение.
    """
    корень = Path(корень or КОРЕНЬ)
    python = python or sys.executable
    порт = свободный_порт()
    каталог = Path(tempfile.mkdtemp(prefix="ledger-tests-"))

    окр = dict(
        os.environ,
        SITE_ENGINE_CONTROL_WRITES="0",
        AUDIT_LEDGER_DB=str(каталог / "ledger.sqlite3"),
        AUDIT_API_BASE=f"http://127.0.0.1:{порт}",
        AUDIT_FEED=str(каталог / "feed.jsonl"),
        SITE_ENGINE_HTTP="1",
        SITE_ENGINE_ADMIN="1",
        SITE_ENGINE_API_ENABLED="1",
        CREDENTIALS_DIRECTORY=str(_учётные_данные(каталог)),
        REGISTRY_DB=str(_реестр(каталог)),
        **ТОКЕНЫ,
    )

    лог = (каталог / "server.log").open("w")
    процесс = subprocess.Popen(
        [
            str(python),
            "-m",
            "factory.site_engine.api.server",
            "--root",
            str(корень),
            "--host",
            "127.0.0.1",
            "--port",
            str(порт),
        ],
        cwd=str(корень),
        env=окр,
        preexec_fn=_умереть_с_родителем,
        stdout=лог,
        stderr=subprocess.STDOUT,
    )
    экземпляр = Экземпляр(порт=порт, каталог=каталог, процесс=процесс, окружение=окр)

    предел = time.monotonic() + ГОТОВНОСТЬ_СЕК
    while time.monotonic() < предел:
        if процесс.poll() is not None:
            лог.close()
            хвост = экземпляр.журнал_службы[-2000:]
            экземпляр.погасить()
            raise ЖурналНеПоднялся(
                f"служба журнала завершилась с кодом {процесс.returncode}:\n{хвост}"
            )
        try:
            with urllib.request.urlopen(
                f"http://127.0.0.1:{порт}/api/v1/audit/health", timeout=3
            ) as о:
                if о.status == 200:
                    лог.close()
                    return экземпляр
        except (urllib.error.URLError, OSError):
            time.sleep(0.25)

    лог.close()
    хвост = экземпляр.журнал_службы[-2000:]
    экземпляр.погасить()
    raise ЖурналНеПоднялся(f"журнал не ответил на /health за {ГОТОВНОСТЬ_СЕК:.0f} с:\n{хвост}")
