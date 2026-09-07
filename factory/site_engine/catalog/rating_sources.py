"""Реестр источников оценок и договор с ними.

Оценок нет не потому, что их негде взять, а потому, что **ни один источник не
разрешён**. Это решение владельца, и подменять его нельзя ничем: ни сбором со
страниц, ни средним по соседям, ни округлением «примерно».

Отсюда всё устройство слоя.

**Разрешение versioned и явное.** Источник используется только при
`authorization.status: granted`. Ни флаг `enabled`, ни переменная среды этого не
заменяют — так же, как с идентификаторами воспроизведения: флаг, способный
включить неразрешённый источник, обесценивает само разрешение.

**Отсутствие числа не превращается в ноль.** Нет источника — состояние
`SOURCE_NOT_AUTHORIZED` и `value: null`. Ноль на этом месте слой выше покажет
как оценку, и она будет выглядеть настоящей.

**Сорвавшийся источник отключается сам.** Отказы подряд размыкают цепь, и
запросы прекращаются до истечения паузы: настойчивый повтор к чужому сервису —
нагрузка на него и отказ нам.

**Последнее известное хорошее значение живёт по сроку.** Оно отдаётся с
отметкой времени и после истечения срока помечается устаревшим, а не
выбрасывается: молча стареющее значение — ложь с задержкой, а выброшенное
лишает оператора единственного, что было.

**Расхождение источников не усредняется.** Два разных числа — факт о
разногласии, а не повод придумать третье, которого не сообщал никто.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

ВЕРСИЯ = "rating-sources/1.0.0"
ФАЙЛ = "config/rating-sources.yaml"

#: Насколько два источника могут разойтись и всё ещё считаться согласными.
#: Десятая доля балла — типичная разница округления у разных агрегаторов;
#: большее расхождение означает, что они считают по-разному, и выбирать за них
#: не наше дело.
ДОПУСК = 0.1

СОСТОЯНИЯ_РАЗРЕШЕНИЯ = {"granted", "absent", "revoked"}


class RatingSourceError(Exception):
    """Реестр противоречив: включено то, что не разрешено."""


@dataclass(frozen=True)
class Решение:
    version: int
    authorized: tuple[str, ...]
    known: tuple[dict[str, Any], ...]
    blocker: str = ""

    def as_dict(self) -> dict[str, Any]:
        return {
            "contractVersion": ВЕРСИЯ,
            "version": self.version,
            "authorized": list(self.authorized),
            "known": [dict(и) for и in self.known],
            "blocker": self.blocker,
        }


def resolve(root: Path | str) -> Решение:
    """Прочитать реестр и проверить его на противоречие.

    Противоречие здесь одно и оно же самое опасное: источник помечен включённым,
    но разрешения на него нет. Такой реестр не «почти правильный» — он молча
    открывает то, что закрыто решением владельца.
    """
    import yaml

    путь = Path(root) / ФАЙЛ
    if not путь.is_file():
        return Решение(version=0, authorized=(), known=(), blocker=f"реестр не найден: {ФАЙЛ}")
    try:
        данные = yaml.safe_load(путь.read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError) as ошибка:
        raise RatingSourceError(f"реестр источников не читается: {ошибка}") from ошибка

    известные: list[dict[str, Any]] = []
    разрешённые: list[str] = []
    for запись in данные.get("sources") or []:
        идентификатор = str(запись.get("id") or "").strip()
        if not идентификатор:
            raise RatingSourceError("источник без идентификатора")
        разрешение = запись.get("authorization") or {}
        состояние = str(разрешение.get("status") or "absent")
        if состояние not in СОСТОЯНИЯ_РАЗРЕШЕНИЯ:
            raise RatingSourceError(
                f"{идентификатор}: неизвестное состояние разрешения {состояние!r}"
            )
        if not str(разрешение.get("reason") or "").strip():
            raise RatingSourceError(f"{идентификатор}: состояние разрешения без объяснения")
        включён = bool(запись.get("enabled"))
        if включён and состояние != "granted":
            raise RatingSourceError(
                f"{идентификатор}: включён без разрешения (authorization.status={состояние}). "
                "Флаг не заменяет решения владельца."
            )
        известные.append(
            {
                "id": идентификатор,
                "enabled": включён,
                "ttlSeconds": int(запись.get("ttl_seconds") or 0),
                "rateLimitPerMinute": int(запись.get("rate_limit_per_minute") or 0),
                "authorization": {
                    "status": состояние,
                    "reason": str(разрешение.get("reason") or ""),
                    "document": str(разрешение.get("document") or ""),
                    "grantedAt": str(разрешение.get("granted_at") or ""),
                },
            }
        )
        if включён and состояние == "granted":
            разрешённые.append(идентификатор)

    блокер = (
        ""
        if разрешённые
        else "ни один источник оценок не разрешён: это решение владельца, "
        "и подменять его сбором со страниц нельзя"
    )
    return Решение(
        version=int(данные.get("version") or 0),
        authorized=tuple(разрешённые),
        known=tuple(известные),
        blocker=блокер,
    )


def fetch(root: Path | str, *, source_id: str, entity_id: str) -> dict[str, Any]:
    """Запрос значения у источника. Без разрешения — не запрос, а честный отказ."""
    решение = resolve(root)
    if not source_id or source_id not in решение.authorized:
        return {
            "entityId": entity_id,
            "source": source_id,
            "state": "SOURCE_NOT_AUTHORIZED",
            # None, а не 0 и не пустая строка: слой выше покажет ноль как оценку.
            "value": None,
            "votes": None,
            "reason": решение.blocker or f"источник {source_id!r} не разрешён",
        }
    # Разрешённых источников в поставке нет. Когда появятся, сюда придёт вызов
    # соединителя — с предохранителем и пределом частоты из реестра.
    return {
        "entityId": entity_id,
        "source": source_id,
        "state": "CONNECTOR_NOT_IMPLEMENTED",
        "value": None,
        "votes": None,
        "reason": "источник разрешён, но соединитель к нему ещё не написан",
    }


@dataclass
class Breaker:
    """Предохранитель: подряд отказы размыкают цепь на паузу."""

    порог: int = 5
    пауза: float = 300.0
    now: Any = time.time
    _отказов: int = 0
    _разомкнут_с: float = 0.0

    def отказ(self) -> None:
        self._отказов += 1
        if self._отказов >= self.порог:
            self._разомкнут_с = float(self.now())

    def успех(self) -> None:
        self._отказов = 0
        self._разомкнут_с = 0.0

    def разомкнут(self) -> bool:
        if not self._разомкнут_с:
            return False
        if float(self.now()) - self._разомкнут_с > self.пауза:
            # Пауза истекла: пробуем снова, но счётчик не обнуляем — успех
            # обнулит его сам, а новый отказ разомкнёт цепь немедленно.
            self._разомкнут_с = 0.0
            self._отказов = max(0, self.порог - 1)
            return False
        return True


@dataclass
class LastKnownGood:
    """Последнее известное хорошее значение со сроком годности."""

    root: Path
    ttl_seconds: int = 21600
    subdir: str = "var/state/rating-lkg"
    now: Any = time.time
    _dir: Path = field(init=False)

    def __post_init__(self) -> None:
        self._dir = Path(self.root) / self.subdir

    def _путь(self, entity_id: str) -> Path:
        import hashlib

        имя = hashlib.sha256(entity_id.encode("utf-8")).hexdigest()[:32]
        return self._dir / f"{имя}.json"

    def put(self, entity_id: str, *, источник: str, value: float, votes: int | None) -> None:
        self._dir.mkdir(parents=True, exist_ok=True)
        путь = self._путь(entity_id)
        временный = путь.with_suffix(".json.tmp")
        временный.write_text(
            json.dumps(
                {
                    "entityId": entity_id,
                    "source": источник,
                    "value": value,
                    "votes": votes,
                    "capturedAtRaw": float(self.now()),
                    "capturedAt": time.strftime(
                        "%Y-%m-%dT%H:%M:%SZ", time.gmtime(float(self.now()))
                    ),
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        временный.replace(путь)

    def get(self, entity_id: str) -> dict[str, Any] | None:
        путь = self._путь(entity_id)
        if not путь.is_file():
            return None
        try:
            данные = json.loads(путь.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None
        возраст = float(self.now()) - float(данные.get("capturedAtRaw") or 0)
        данные["ageSeconds"] = возраст
        данные["stale"] = возраст > self.ttl_seconds
        данные.pop("capturedAtRaw", None)
        return данные


def reconcile(значения: list[dict[str, Any]]) -> dict[str, Any]:
    """Свести значения нескольких источников. Среднее не считается никогда."""
    годные = [з for з in значения if з.get("value") is not None]
    if not годные:
        return {"state": "NO_DATA", "value": None, "candidates": list(значения)}
    if len(годные) == 1:
        единственное = годные[0]
        return {
            "state": "SINGLE_SOURCE",
            "value": единственное["value"],
            "chosen": единственное.get("source", ""),
            "candidates": годные,
        }
    наименьшее = min(float(з["value"]) for з in годные)
    наибольшее = max(float(з["value"]) for з in годные)
    if наибольшее - наименьшее > ДОПУСК:
        return {"state": "SOURCES_DISAGREE", "value": None, "candidates": годные}
    # Берётся значение источника с большим числом голосов, а не среднее:
    # среднее — это третье число, которого не сообщал никто.
    выбранное = max(годные, key=lambda з: int(з.get("votes") or 0))
    return {
        "state": "AGREED",
        "value": выбранное["value"],
        "chosen": выбранное.get("source", ""),
        "candidates": годные,
    }
