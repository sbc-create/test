"""Приём событий Registry: курсор, идемпотентность, разрывы и сверка.

Что здесь обязательно и почему
------------------------------

Доставка — at-least-once, поэтому повтор считается нормой, а не ошибкой:
идемпотентность обеспечивается по `event_id`, а не «мы такого не видели».

Курсор двигается только после сохранённой проекции и в той же транзакции.
Подтвердить раньше записи — значит однажды потерять событие при падении
между ними и не узнать об этом.

Разрыв последовательности не «исправляется» пропуском. `seq` монотонен;
дырка означает, что события мы не увидим никогда, и единственный честный
ответ — полная сверка со снимком. Та же сверка идёт при старте и по
расписанию, чтобы пропущенный сайт обнаруживался не позже пятнадцати минут
даже при полном молчании ленты.

Событие, которое не удалось применить, уходит в DLQ после ограниченного
числа попыток с экспоненциальной задержкой и джиттером. Бесконечный повтор
одного отравленного события останавливает всю ленту.

Обычные опросы и сердцебиение в журнал аудита не пишутся: там должны быть
значимые события жизненного цикла и отказы, а не шум.
"""

from __future__ import annotations

import json
import os
import random
import signal
import sqlite3
import sys
import time
from typing import Any, Callable

from factory.templates_cp.projection import Проекция
from factory.templates_cp.registry_client import (RegistryClient,
                                                  RegistryUnavailable, Сайт)

#: Типы, которые меняют состав production. Имена — из объявленного AsyncAPI.
РЕГИСТРАЦИЯ = "site.registered.v1"
ОБНОВЛЕНИЕ = "site.updated.v1"
АКТИВАЦИЯ = "site.activated.v1"
ВЫВОД = "site.retired.v1"
ИЗВЕСТНЫЕ = {РЕГИСТРАЦИЯ, ОБНОВЛЕНИЕ, АКТИВАЦИЯ, ВЫВОД}

#: Периодическая сверка. Требование — обнаружить пропажу не позже 15 минут;
#: берём половину бюджета, чтобы одна неудачная попытка не съела весь срок.
ПЕРИОД_СВЕРКИ = 450.0
ПРЕДЕЛ_ПОПЫТОК = 5
БАЗОВАЯ_ЗАДЕРЖКА = 0.5


class Замок:
    """Ровно один экземпляр потребителя.

    Второй процесс с тем же курсором — это гонка за позицию в ленте:
    оба двигают курсор, каждый видит половину событий, и проекция
    расходится с Registry без единой ошибки в журнале.
    """

    def __init__(self, путь: str) -> None:
        self.путь = путь
        self._соед: sqlite3.Connection | None = None

    def захватить(self) -> bool:
        # Занятость — обычный исход, а не сбой: второй экземпляр обязан
        # спокойно уйти, а не упасть с трассировкой.
        try:
            self._соед = sqlite3.connect(self.путь, timeout=1)
            self._соед.execute("CREATE TABLE IF NOT EXISTS lock_holder(pid INTEGER)")
            self._соед.execute("BEGIN EXCLUSIVE")
        except sqlite3.OperationalError:
            if self._соед is not None:
                self._соед.close()
            self._соед = None
            return False
        self._соед.execute("DELETE FROM lock_holder")
        self._соед.execute("INSERT INTO lock_holder(pid) VALUES(?)", (os.getpid(),))
        return True

    def отпустить(self) -> None:
        if self._соед is not None:
            try:
                self._соед.commit()
            finally:
                self._соед.close()
                self._соед = None


class Потребитель:
    def __init__(self, клиент: RegistryClient, проекция: Проекция,
                 журнал: Callable[[str, dict], None] | None = None,
                 сон: Callable[[float], None] = time.sleep) -> None:
        self.клиент = клиент
        self.проекция = проекция
        self.журнал = журнал or (lambda вид, данные: None)
        self.сон = сон
        self.остановлен = False
        self.разрывов = 0
        self.дубликатов = 0
        self.не_по_порядку = 0

    # --- применение одного события --------------------------------------
    def _применить(self, событие: dict[str, Any]) -> None:
        тип = событие.get("event_type")
        сид = событие.get("site_id")
        версия = событие.get("registry_version")
        if тип == ВЫВОД:
            self.проекция.отключить(сид, версия)
            return
        if тип in (РЕГИСТРАЦИЯ, ОБНОВЛЕНИЕ, АКТИВАЦИЯ):
            # Событие сообщает ФАКТ изменения, а не полное состояние, и
            # запись берётся из снимка Registry.
            #
            # Не из `/api/v1/sites/{id}`: под этим адресом живёт запись Site
            # Engine (domains, locale, modules, theme) — другой ресурс с тем
            # же префиксом. У неё нет ни `environment`, ни `lifecycle_state`,
            # и потребитель, спросивший её, снимал production-признак со всех
            # девяти сайтов сразу. Поштучного маршрута у Registry нет.
            снимок = self.клиент.снимок()
            запись = next((с for с in снимок.сайты if с.site_id == сид), None)
            if запись is None:
                # В снимке сайта нет — значит он не production ACTIVE.
                # Это не ошибка события, а его смысл.
                self.проекция.отключить(сид, версия)
                return
            with self.проекция.соед:
                self.проекция._записать_сайт(запись, версия, активен=True)
            return
        # Неизвестный тип — не ошибка: контракт расширяется аддитивно.
        # Потребитель обязан пережить незнакомое поле и незнакомый тип.
        self.журнал("event.ignored", {"event_type": тип, "event_id": событие.get("event_id")})

    def обработать(self, событие: dict[str, Any], курсор: str | None) -> str:
        """Вернуть исход: applied | duplicate | dlq."""
        ид = событие.get("event_id")
        if not ид:
            self.проекция.в_dlq(событие, "нет event_id", 1)
            return "dlq"
        if self.проекция.уже_обработано(ид):
            self.дубликатов += 1
            # Курсор всё равно двигаем: повтор уже учтён, стоять на месте
            # значит перечитывать одно и то же вечно.
            self.проекция.зафиксировать(событие, курсор)
            return "duplicate"
        задержка = БАЗОВАЯ_ЗАДЕРЖКА
        for попытка in range(1, ПРЕДЕЛ_ПОПЫТОК + 1):
            try:
                self._применить(событие)
                self.проекция.зафиксировать(событие, курсор)
                return "applied"
            except Exception as ош:                    # применение не удалось
                if попытка >= ПРЕДЕЛ_ПОПЫТОК:
                    self.проекция.в_dlq(событие, f"{type(ош).__name__}: {ош}"[:200], попытка)
                    self.журнал("event.dlq", {"event_id": ид, "reason": type(ош).__name__})
                    # Курсор двигаем: отравленное событие лежит в DLQ, и
                    # останавливать на нём всю ленту нельзя.
                    self.проекция.зафиксировать(событие, курсор)
                    return "dlq"
                self.сон(задержка + random.uniform(0, задержка / 2))
                задержка *= 2
        return "dlq"

    # --- один проход по ленте --------------------------------------------
    def один_проход(self) -> dict[str, int]:
        свод = {"applied": 0, "duplicate": 0, "dlq": 0, "gap": 0}
        курсор = self.проекция.курсор
        ожидаемый = int(курсор) + 1 if курсор else 1
        пачка = self.клиент.события(курсор)
        for событие in пачка.get("items", []):
            seq = событие.get("seq")
            if isinstance(seq, int):
                if seq < ожидаемый:
                    self.не_по_порядку += 1
                elif seq > ожидаемый:
                    # Разрыв: пропущенного уже не получить, помогает только
                    # полная сверка со снимком.
                    свод["gap"] += 1
                    self.разрывов += 1
                    self.журнал("registry.gap", {"expected": ожидаемый, "got": seq})
                    self.сверить(причина="gap")
                ожидаемый = max(ожидаемый, seq + 1)
            исход = self.обработать(событие, пачка.get("next_cursor") or событие.get("seq"))
            свод[исход] = свод.get(исход, 0) + 1
        return свод

    # --- полная сверка ----------------------------------------------------
    def сверить(self, причина: str = "periodic") -> bool:
        try:
            снимок = self.клиент.снимок()
        except RegistryUnavailable as ош:
            self.журнал("registry.unavailable", {"reason": str(ош), "phase": причина})
            return False
        было = self.проекция.производственные(свежая=False, источник="projection").идентификаторы
        self.проекция.применить_снимок(снимок)
        стало = self.проекция.производственные(свежая=True, источник="snapshot").идентификаторы
        if было != стало:
            self.журнал("projection.reconciled",
                        {"reason": причина, "added": sorted(стало - было),
                         "removed": sorted(было - стало)})
        return True

    # --- повторный разбор отложенных событий -------------------------------
    def разобрать_dlq(self) -> dict[str, Any]:
        """Прогнать отложенные события заново текущим кодом.

        DLQ существует, чтобы её разбирали после устранения причины, а не
        чтобы она копилась вечно. Событие, которое теперь применяется,
        применяется и уходит из очереди; то, что снова не удалось, остаётся
        на месте вместе с новой причиной — молча выбрасывать его нельзя.
        """
        свод = {"reprocessed": 0, "still_failing": 0, "total": 0}
        for запись in self.проекция.очередь_разбора():
            свод["total"] += 1
            событие = запись["event"]
            if not событие.get("event_id"):
                свод["still_failing"] += 1
                continue
            try:
                self._применить(событие)
            except Exception as ош:
                свод["still_failing"] += 1
                self.журнал("dlq.still_failing",
                            {"event_id": запись["event_id"],
                             "reason": f"{type(ош).__name__}: {ош}"[:200]})
                continue
            # Отметка об обработке ставится до удаления из очереди: иначе
            # падение между ними вернуло бы событие как необработанное.
            self.проекция.зафиксировать(событие, self.проекция.курсор)
            self.проекция.убрать_из_dlq(запись["event_id"])
            свод["reprocessed"] += 1
            self.журнал("dlq.reprocessed", {"event_id": запись["event_id"]})
        return свод

    # --- служба ------------------------------------------------------------
    def служить(self, шагов: int | None = None, пауза: float = 5.0) -> None:
        self.сверить(причина="startup")
        сделано = 0
        while not self.остановлен and (шагов is None or сделано < шагов):
            try:
                self.один_проход()
            except RegistryUnavailable as ош:
                # Недоступность Registry — не повод падать: проекция
                # остаётся, но отвечает STALE.
                self.журнал("registry.unavailable", {"reason": str(ош), "phase": "poll"})
            if time.time() - self.проекция.последняя_сверка > ПЕРИОД_СВЕРКИ:
                self.сверить(причина="periodic")
            сделано += 1
            if шагов is None or сделано < шагов:
                self.сон(пауза)

    def остановить(self, *_: Any) -> None:
        self.остановлен = True


def main() -> int:
    база = os.environ.get("TEMPLATES_CP_BASE", "http://127.0.0.1:8790")
    путь = os.environ.get("TEMPLATES_CP_STATE", "/var/lib/templates-cp/projection.sqlite3")
    os.makedirs(os.path.dirname(путь), exist_ok=True)
    замок = Замок(путь + ".lock")
    if not замок.захватить():
        print("[templates-cp] уже работает другой экземпляр", file=sys.stderr)
        return 3
    проекция = Проекция(путь)
    потребитель = Потребитель(RegistryClient(база), проекция,
                              журнал=lambda вид, д: print(
                                  f"[templates-cp] {вид} {json.dumps(д, ensure_ascii=False)}"))
    signal.signal(signal.SIGTERM, потребитель.остановить)
    signal.signal(signal.SIGINT, потребитель.остановить)
    try:
        потребитель.служить()
    finally:
        проекция.закрыть()
        замок.отпустить()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
