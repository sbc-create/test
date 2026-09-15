"""Реестр доступности видео у поставщика.

Витрина не имеет права показывать карточку, за которой нет видео. Но и снимать
карточку с публикации по одному отказу нельзя: сеть моргает, поставщик отвечает
429 и 5xx, и запись, у которой видео есть, исчезла бы из каталога на ровном
месте. Поэтому здесь два разных понятия.

`observed_status` — что ответил поставщик прямо сейчас. `effective_status` — что
витрина считает правдой. Второе меняется медленно и только по достаточному
основанию: карантин наступает после трёх независимых ответов 204, а выход из
него требует полной цепочки подтверждений. Всё, что похоже на сбой связи, даёт
`UNKNOWN` и не трогает последнее достоверное значение.

Идентичность записи — только пара «профиль поставщика + его собственный
идентификатор». Ни названия, ни года, ни slug, ни KP/MAL/IMDb здесь нет и быть
не должно: попытка подобрать источник по названию уже приводила к подстановке
другой части франшизы.
"""

from __future__ import annotations

import fcntl
import json
import os
import re
import tempfile
import uuid as _uuid
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

#: Версия формата файла состояния. Читатель обязан отвергнуть незнакомую версию,
#: а не догадываться о значении полей.
СХЕМА_ВЕРСИЯ = 1

AVAILABLE = "AVAILABLE"
SOURCE_UNAVAILABLE = "SOURCE_UNAVAILABLE"
UNKNOWN = "UNKNOWN"

СТАТУСЫ = (AVAILABLE, SOURCE_UNAVAILABLE, UNKNOWN)

#: Сколько независимых ответов 204 подряд нужно, чтобы отправить запись в
#: карантин. Повторы внутри одной проверки независимыми не считаются — их
#: складывает вызывающая сторона, а не этот модуль.
ПОРОГ_КАРАНТИНА = 3

#: Собственный идентификатор записи в каталоге поставщика.
ИДЕНТИФИКАТОР = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"
)


class ПовреждённоеСостояние(Exception):
    """Файл состояния нечитаем или не соответствует схеме.

    Поднимается вместо тихого возврата пустого реестра: пустой реестр, записанный
    поверх целого, стёр бы историю подтверждений и вернул бы из карантина все
    записи разом.
    """


def _сейчас() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


@dataclass(frozen=True)
class Наблюдение:
    """Один ответ поставщика по одной записи.

    `подтверждено` — отдельное и более сильное утверждение, чем `AVAILABLE`:
    оно означает пройденную цепочку «плейлист → реальный cvhId/vkId → дескриптор
    200 → та же сущность». Только оно возвращает запись из карантина.
    """

    http: int | None
    items: int = 0
    stream: bool = False
    entity_ok: bool = True
    media_ok: bool = False
    reason: str = ""

    @property
    def подтверждено(self) -> bool:
        return bool(
            self.http == 200
            and self.stream
            and self.entity_ok
            and self.media_ok
            and self.items > 0
        )


def наблюдаемый_статус(набл: Наблюдение) -> tuple[str, str]:
    """Классификация одного ответа. Возвращает (статус, причина).

    Строгость здесь намеренная. `SOURCE_UNAVAILABLE` наблюдается только при 204:
    это единственный ответ, которым поставщик прямо говорит «такого контента у
    меня нет». Ответ 200 без дорожки — не то же самое: тайтл у поставщика есть,
    и завтра дорожка может появиться, поэтому запись не отправляется в карантин,
    но и рабочей не считается.
    """
    if набл.http == 204:
        return SOURCE_UNAVAILABLE, "NO_CONTENT_AT_PROVIDER"
    if набл.http == 200:
        if not набл.entity_ok:
            return UNKNOWN, "WRONG_ENTITY"
        if набл.stream and набл.items > 0:
            return AVAILABLE, "OK"
        return UNKNOWN, "NO_STREAM_IN_PLAYLIST"
    if набл.http in (401, 403):
        return UNKNOWN, "AUTH"
    if набл.http == 429:
        return UNKNOWN, "RATE_LIMITED"
    if набл.http is not None and 500 <= набл.http < 600:
        return UNKNOWN, "PROVIDER_5XX"
    return UNKNOWN, набл.reason or "TRANSPORT"


@dataclass
class Запись:
    """Состояние одной пары «профиль + идентификатор поставщика»."""

    provider_profile: str
    provider_uuid: str
    observed_status: str = UNKNOWN
    effective_status: str = UNKNOWN
    http: int | None = None
    reason: str = ""
    items: int = 0
    consecutive_204_count: int = 0
    checked_at: str | None = None
    last_available_at: str | None = None
    last_confirmed_at: str | None = None

    def как_словарь(self) -> dict[str, Any]:
        return {
            "provider_profile": self.provider_profile,
            "provider_uuid": self.provider_uuid,
            "observed_status": self.observed_status,
            "effective_status": self.effective_status,
            "http": self.http,
            "reason": self.reason,
            "items": self.items,
            "consecutive_204_count": self.consecutive_204_count,
            "checked_at": self.checked_at,
            "last_available_at": self.last_available_at,
            "last_confirmed_at": self.last_confirmed_at,
        }

    @staticmethod
    def из_словаря(д: dict[str, Any]) -> Запись:
        профиль = str(д.get("provider_profile") or "").strip()
        ид = str(д.get("provider_uuid") or "").strip().lower()
        if not профиль or not ИДЕНТИФИКАТОР.match(ид):
            raise ПовреждённоеСостояние(f"негодный ключ записи: {д!r:.120}")
        статус = str(д.get("effective_status") or UNKNOWN)
        if статус not in СТАТУСЫ:
            raise ПовреждённоеСостояние(f"незнакомый статус {статус!r}")
        набл = str(д.get("observed_status") or UNKNOWN)
        if набл not in СТАТУСЫ:
            raise ПовреждённоеСостояние(f"незнакомый observed_status {набл!r}")
        счёт = д.get("consecutive_204_count", 0)
        if not isinstance(счёт, int) or счёт < 0:
            raise ПовреждённоеСостояние("consecutive_204_count не целое неотрицательное")
        return Запись(
            provider_profile=профиль,
            provider_uuid=ид,
            observed_status=набл,
            effective_status=статус,
            http=д.get("http"),
            reason=str(д.get("reason") or ""),
            items=int(д.get("items") or 0),
            consecutive_204_count=счёт,
            checked_at=д.get("checked_at"),
            last_available_at=д.get("last_available_at"),
            last_confirmed_at=д.get("last_confirmed_at"),
        )


def ключ(профиль: str, ид: str) -> str:
    return f"{профиль}:{ид.lower()}"


@dataclass
class Реестр:
    """Версионированный снимок доступности. Хранится одним файлом."""

    generation_id: str = field(default_factory=lambda: _uuid.uuid4().hex)
    created_at: str = field(default_factory=_сейчас)
    записи: dict[str, Запись] = field(default_factory=dict)

    # ---- переходы --------------------------------------------------------

    def обновить(self, профиль: str, ид: str, набл: Наблюдение,
                 сейчас: str | None = None) -> Запись:
        """Применяет одно наблюдение и возвращает новое состояние записи.

        Здесь и живёт вся защита от дребезга. Три правила, которые легко
        нарушить по невнимательности и каждое из которых уже стоило бы витрине
        карточек:

        1. `UNKNOWN` не меняет `effective_status` и не обнуляет счётчик 204 —
           иначе обрыв связи посреди серии отказов сбросил бы накопленное
           основание, и карантин не наступил бы никогда.
        2. Ответ 204 повышает счётчик, но переводит в карантин только на третий
           раз — один отказ не повод снимать работающую карточку.
        3. Выход из карантина требует полной цепочки подтверждений, а не просто
           ответа 200: поставщик умеет отвечать 200 на соседнюю часть франшизы.
        """
        ид = ид.lower()
        if not ИДЕНТИФИКАТОР.match(ид):
            raise ValueError(f"идентификатор поставщика негоден: {ид!r}")
        к = ключ(профиль, ид)
        сейчас = сейчас or _сейчас()
        запись = self.записи.get(к) or Запись(provider_profile=профиль, provider_uuid=ид)
        статус, причина = наблюдаемый_статус(набл)

        запись.observed_status = статус
        запись.http = набл.http
        запись.reason = причина
        запись.items = набл.items
        запись.checked_at = сейчас

        if статус == AVAILABLE:
            запись.consecutive_204_count = 0
            запись.last_available_at = сейчас
            if набл.подтверждено:
                запись.last_confirmed_at = сейчас
            # Из карантина выпускает только подтверждённая цепочка.
            if запись.effective_status == SOURCE_UNAVAILABLE:
                if набл.подтверждено:
                    запись.effective_status = AVAILABLE
            else:
                запись.effective_status = AVAILABLE
        elif статус == SOURCE_UNAVAILABLE:
            запись.consecutive_204_count += 1
            if запись.consecutive_204_count >= ПОРОГ_КАРАНТИНА:
                запись.effective_status = SOURCE_UNAVAILABLE
            # До порога последнее достоверное значение сохраняется как есть.
        else:
            # UNKNOWN: ничего, кроме отметки о проверке, не меняется.
            pass

        self.записи[к] = запись
        return запись

    # ---- выборки ---------------------------------------------------------

    def карантин(self, профиль: str | None = None) -> set[str]:
        return {
            з.provider_uuid
            for з in self.записи.values()
            if з.effective_status == SOURCE_UNAVAILABLE
            and (профиль is None or з.provider_profile == профиль)
        }

    def публикуемо(self, профиль: str, ид: str) -> bool:
        """Можно ли показывать запись как играющую.

        Запись, которую ни разу не удалось достоверно подтвердить, играющей не
        считается: неизвестность — не разрешение публиковать.
        """
        з = self.записи.get(ключ(профиль, ид))
        if з is None:
            return False
        return з.effective_status == AVAILABLE

    def сводка(self, профиль: str | None = None) -> dict[str, int]:
        итог = {AVAILABLE: 0, SOURCE_UNAVAILABLE: 0, UNKNOWN: 0}
        for з in self.записи.values():
            if профиль is None or з.provider_profile == профиль:
                итог[з.effective_status] = итог.get(з.effective_status, 0) + 1
        return итог

    # ---- сериализация ----------------------------------------------------

    def как_словарь(self) -> dict[str, Any]:
        return {
            "schema_version": СХЕМА_ВЕРСИЯ,
            "generation_id": self.generation_id,
            "created_at": self.created_at,
            "entries": {к: з.как_словарь() for к, з in sorted(self.записи.items())},
        }


def разобрать(текст: str) -> Реестр:
    """Разбор файла состояния с проверкой схемы."""
    try:
        сырое = json.loads(текст)
    except ValueError as e:
        raise ПовреждённоеСостояние(f"не разбирается как JSON: {e}") from e
    if not isinstance(сырое, dict):
        raise ПовреждённоеСостояние("корень не объект")
    версия = сырое.get("schema_version")
    if версия != СХЕМА_ВЕРСИЯ:
        raise ПовреждённоеСостояние(f"схема {версия!r}, ожидалась {СХЕМА_ВЕРСИЯ}")
    поколение = str(сырое.get("generation_id") or "").strip()
    if not поколение:
        raise ПовреждённоеСостояние("нет generation_id")
    записи_сырые = сырое.get("entries")
    if not isinstance(записи_сырые, dict):
        raise ПовреждённоеСостояние("entries не объект")
    записи: dict[str, Запись] = {}
    for к, д in записи_сырые.items():
        if not isinstance(д, dict):
            raise ПовреждённоеСостояние(f"запись {к!r} не объект")
        з = Запись.из_словаря(д)
        if к != ключ(з.provider_profile, з.provider_uuid):
            raise ПовреждённоеСостояние(f"ключ {к!r} не совпадает с содержимым")
        записи[к] = з
    return Реестр(
        generation_id=поколение,
        created_at=str(сырое.get("created_at") or _сейчас()),
        записи=записи,
    )


def загрузить(путь: Path) -> Реестр:
    """Читает состояние. Отсутствие файла — пустой реестр, порча — исключение."""
    if not путь.exists():
        return Реестр()
    return разобрать(путь.read_text(encoding="utf-8"))


def сохранить(путь: Path, реестр: Реестр) -> None:
    """Атомарная запись: временный файл рядом, fsync, проверка, переименование.

    Промежуточный разбор записанного — не перестраховка. Оборванная запись даёт
    синтаксически битый файл, и без проверки он бы заменил целое предыдущее
    поколение, а следующий запуск начал бы с пустого реестра и выпустил из
    карантина всё сразу.
    """
    путь.parent.mkdir(parents=True, exist_ok=True)
    реестр.generation_id = _uuid.uuid4().hex
    данные = json.dumps(реестр.как_словарь(), ensure_ascii=False, indent=1)

    описатель, временный = tempfile.mkstemp(
        dir=str(путь.parent), prefix=f".{путь.name}.", suffix=".tmp"
    )
    try:
        with os.fdopen(описатель, "w", encoding="utf-8") as ф:
            ф.write(данные)
            ф.write("\n")
            ф.flush()
            os.fsync(ф.fileno())
        # Проверяем ровно то, что легло на диск, а не то, что собирались писать.
        разобрать(Path(временный).read_text(encoding="utf-8"))
        os.replace(временный, путь)
    except Exception:
        Path(временный).unlink(missing_ok=True)
        raise


class Блокировка:
    """Взаимное исключение пятиминутной и суточной проверок.

    Обе пишут один файл. Без блокировки более медленная затёрла бы результат
    более свежей, и запись, только что вернувшаяся из карантина, снова
    оказалась бы снятой.
    """

    def __init__(self, путь: Path) -> None:
        self.путь = путь
        self._ф = None

    def __enter__(self) -> Блокировка:
        self.путь.parent.mkdir(parents=True, exist_ok=True)
        self._ф = open(self.путь, "a+")
        fcntl.flock(self._ф.fileno(), fcntl.LOCK_EX)
        return self

    def __exit__(self, *_: object) -> None:
        if self._ф is not None:
            fcntl.flock(self._ф.fileno(), fcntl.LOCK_UN)
            self._ф.close()
            self._ф = None


def применить_наблюдения(путь: Path, профиль: str,
                         наблюдения: Iterable[tuple[str, Наблюдение]],
                         сейчас: str | None = None) -> Реестр:
    """Загрузить, применить пачку наблюдений, сохранить — под блокировкой.

    Повторный запуск с теми же наблюдениями идемпотентен по эффекту: счётчик 204
    растёт, но `effective_status` уже не меняется, а `AVAILABLE` остаётся
    `AVAILABLE`.
    """
    with Блокировка(путь.with_suffix(путь.suffix + ".lock")):
        реестр = загрузить(путь)
        for ид, набл in наблюдения:
            реестр.обновить(профиль, ид, набл, сейчас=сейчас)
        сохранить(путь, реестр)
    return реестр
