"""Ограничение частоты, общее для нескольких процессов.

Прежний счётчик жил в памяти процесса: при двух экземплярах Control API предел
оказывался вдвое выше объявленного, и узнать об этом можно было только по
последствиям. Здесь состояние вынесено в файл и защищено блокировкой, поэтому
предел один на всех, кто работает с одним каталогом состояния.

Почему файл, а не Redis. Redis на этом хосте обслуживает данные витрин
(по базе на витрину). Управляющий слой намеренно не имеет доступа к хранилищам
витрин — см. ADR-002 — и заводить его ради счётчика значит разменять границу на
удобство. Файловая система уже служит очереди, блокировкам и журналу: та же
область надёжности, новой инфраструктуры не появляется. Общий предел за
пределами одного хоста потребует общего хранилища и разобран отдельно в
backlog многосерверной схемы.

Ключи образуют иерархию: среда → витрина → действующее лицо → операция.
Один шумный сайт не должен упирать в предел остальные, поэтому общего счётчика
на весь массив здесь нет.
"""
from __future__ import annotations

import errno
import fcntl
import json
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any


# Ведро: сколько запросов и за какое окно. Окно в секундах, пополнение
# равномерное — так короткий всплеск проходит, а долгий поток упирается.
@dataclass(frozen=True)
class Limit:
    capacity: int
    per_seconds: float

    @property
    def refill_per_second(self) -> float:
        return self.capacity / self.per_seconds


# Пределы по умолчанию. Они рассчитаны против сорвавшегося цикла автоматики,
# а не против злоумышленника: злоумышленника останавливает проверка прав,
# а не счётчик.
DEFAULT_LIMITS: dict[str, Limit] = {
    "actor": Limit(capacity=60, per_seconds=60.0),
    "site": Limit(capacity=30, per_seconds=60.0),
    "operation": Limit(capacity=20, per_seconds=60.0),
    "environment": Limit(capacity=240, per_seconds=60.0),
}

# Ведро, к которому не обращались дольше этого, удаляется: иначе файл состояния
# растёт по числу когда-либо виденных витрин и токенов.
IDLE_TTL_SECONDS = 3600.0

# Сколько ждать блокировку, прежде чем признать хранилище недоступным.
LOCK_TIMEOUT_SECONDS = 2.0


class StoreUnavailable(RuntimeError):
    """Состояние не прочитано и не записано."""


@dataclass
class Decision:
    allowed: bool
    key: str = ""
    limit: int = 0
    retry_after: int = 1
    degraded: bool = False

    def as_error_extra(self) -> dict[str, Any]:
        return {
            "limit_key": self.key,
            "limit": self.limit,
            "retry_after_seconds": self.retry_after,
            "degraded": self.degraded,
        }


class SharedRateLimiter:
    """Общее для процессов ограничение частоты на файле с блокировкой."""

    def __init__(
        self,
        state_dir: Path | str,
        *,
        limits: dict[str, Limit] | None = None,
        now=time.time,
        degraded_capacity: int = 5,
    ) -> None:
        self._path = Path(state_dir) / "control-ratelimit.json"
        self._limits = dict(limits or DEFAULT_LIMITS)
        self._now = now
        # Запасной счётчик в памяти на случай недоступного хранилища. Он
        # намеренно строже общего: продолжать обслуживать надо, но раздавать
        # полный предел каждому процессу, не видя общего состояния, нельзя.
        self._degraded_capacity = degraded_capacity
        self._degraded: dict[str, list[float]] = {}
        self._last_error: str = ""

    @property
    def last_error(self) -> str:
        return self._last_error

    # ---- состояние ------------------------------------------------------

    def _open_locked(self):
        self._path.parent.mkdir(parents=True, exist_ok=True)
        deadline = self._now() + LOCK_TIMEOUT_SECONDS
        # Дескриптор возвращается наружу удерживающим блокировку, поэтому
        # менеджер контекста здесь неприменим: закрыть его обязан вызывающий,
        # после записи состояния.
        handle = open(self._path, "a+", encoding="utf-8")  # noqa: SIM115
        while True:
            try:
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                return handle
            except OSError as exc:
                if exc.errno not in (errno.EACCES, errno.EAGAIN):
                    handle.close()
                    raise StoreUnavailable(str(exc)) from exc
                if self._now() >= deadline:
                    handle.close()
                    raise StoreUnavailable("ожидание блокировки превышено") from exc
                time.sleep(0.01)

    def _read(self, handle) -> dict[str, Any]:
        handle.seek(0)
        raw = handle.read()
        if not raw.strip():
            return {}
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            # Испорченное состояние счётчика — не повод отказать в обслуживании
            # и не повод молча продолжить: оно сбрасывается, а факт виден в
            # last_error и в метрике.
            self._last_error = "состояние счётчика не разобрано, сброшено"
            return {}
        return data if isinstance(data, dict) else {}

    def _write(self, handle, data: dict[str, Any]) -> None:
        # Запись на месте под удерживаемой блокировкой: замена файла порвала бы
        # блокировку, которую держат другие процессы по этому же inode.
        payload = json.dumps(data, ensure_ascii=False)
        handle.seek(0)
        handle.truncate()
        handle.write(payload)
        handle.flush()
        os.fsync(handle.fileno())

    # ---- решение --------------------------------------------------------

    def check(self, keys: dict[str, str]) -> Decision:
        """Списать по одному разрешению с каждого применимого ведра.

        Все ведра проверяются и списываются под одной блокировкой: проверка
        по одному оставила бы частично списанные разрешения при отказе на
        последнем ведре.
        """
        now = float(self._now())
        try:
            handle = self._open_locked()
        except StoreUnavailable as exc:
            self._last_error = str(exc)
            return self._degraded_check(keys, now)
        try:
            state = self._read(handle)
            buckets: dict[str, Any] = state.get("buckets", {})
            применимые: list[tuple[str, Limit]] = []
            for вид, значение in keys.items():
                предел = self._limits.get(вид)
                if предел is None or not значение:
                    continue
                применимые.append((f"{вид}:{значение}", предел))

            # Сначала посмотреть, хватает ли всем; списывать только потом.
            нехватка: tuple[str, Limit, float] | None = None
            остатки: dict[str, float] = {}
            for ключ, предел in применимые:
                ведро = buckets.get(ключ)
                if ведро is None:
                    остаток = float(предел.capacity)
                else:
                    прошло = max(0.0, now - float(ведро.get("t", now)))
                    остаток = min(float(предел.capacity),
                                  float(ведро.get("n", предел.capacity))
                                  + прошло * предел.refill_per_second)
                остатки[ключ] = остаток
                if остаток < 1.0 and нехватка is None:
                    нехватка = (ключ, предел, остаток)

            if нехватка is not None:
                ключ, предел, остаток = нехватка
                # Отказ тоже сохраняется: иначе пополнение считалось бы от
                # момента последнего успеха и предел стал бы мягче.
                buckets[ключ] = {"n": остаток, "t": now}
                state["buckets"] = self._prune(buckets, now)
                self._write(handle, state)
                нужно = (1.0 - остаток) / предел.refill_per_second
                return Decision(False, ключ, предел.capacity, max(1, int(нужно) + 1))

            for ключ, _ in применимые:
                buckets[ключ] = {"n": остатки[ключ] - 1.0, "t": now}
            state["buckets"] = self._prune(buckets, now)
            self._write(handle, state)
            return Decision(True)
        except StoreUnavailable as exc:
            self._last_error = str(exc)
            return self._degraded_check(keys, now)
        except OSError as exc:
            self._last_error = f"ошибка ввода-вывода: {exc}"
            return self._degraded_check(keys, now)
        finally:
            try:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
                handle.close()
            except OSError:
                pass

    def _prune(self, buckets: dict[str, Any], now: float) -> dict[str, Any]:
        return {k: v for k, v in buckets.items()
                if now - float(v.get("t", now)) <= IDLE_TTL_SECONDS}

    def _degraded_check(self, keys: dict[str, str], now: float) -> Decision:
        """Хранилище недоступно.

        Ни отказать всем, ни пропустить всех: и то и другое превращает сбой
        счётчика в аварию обслуживания. Действует строгий счётчик в памяти
        этого процесса, а факт деградации возвращается вызывающему и уходит
        в метрику — иначе тихий переход в этот режим останется незамеченным.
        """
        ключ = f"actor:{keys.get('actor', 'unknown')}"
        окно = self._degraded.setdefault(ключ, [])
        окно[:] = [t for t in окно if now - t < 60.0]
        if len(окно) >= self._degraded_capacity:
            return Decision(False, ключ, self._degraded_capacity, 60, degraded=True)
        окно.append(now)
        return Decision(True, ключ, self._degraded_capacity, 1, degraded=True)
