"""Контракт свидетельства host-attestation: форма, перечень, сборка, разбор.

Одно место, где объявлено, что считается ПОЛНЫМ измерением живого флота.
Перечень обязательных проверок живёт здесь, а не в скрипте, который их
выполняет: иначе выпавшую проверку заметить некому — свидетельство без неё
выглядело бы точно так же, как свидетельство с ней.
"""
from __future__ import annotations

import datetime as _dt
import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

ВЕРСИЯ_СХЕМЫ = "host-attestation/1.0.0"

#: Корень репозитория: отсюда берётся схема для разбора.
КОРЕНЬ = Path(__file__).resolve().parents[3]
СХЕМА = КОРЕНЬ / "schemas/host-attestation.schema.json"

#: Каталог, куда host-контур кладёт свидетельства. Имя файла — candidate SHA:
#: свидетельство принадлежит дереву, а не дате прогона.
#:
#: Путь берётся из настройки развёртывания по той же причине, что и корни
#: доказательств журнала: каталог — свойство установки, а не контракта. Обойти
#: ворота переменной нельзя: пустой каталог означает «свидетельства нет», и
#: релиз блокируется именно этим.
КАТАЛОГ_ПО_УМОЛЧАНИЮ = КОРЕНЬ / "artifacts/host-attestation"


def каталог_свидетельств(каталог: Path | None = None) -> Path:
    if каталог is not None:
        return каталог
    объявленный = os.environ.get("HOST_ATTESTATION_DIR", "").strip()
    return Path(объявленный) if объявленный else КАТАЛОГ_ПО_УМОЛЧАНИЮ

ДОПУСТИМЫЕ_СТАТУСЫ = ("PASS", "FAIL", "BLOCKED")


@dataclass(frozen=True)
class Проверка:
    """Объявленная проверка живого хоста."""

    check_id: str
    title: str
    required: bool = True


#: Обязательный состав измерения.
#:
#: Ровно те факты, которые нельзя установить из репозитория: они существуют
#: только на работающем хосте. Каждый прежде утверждался тестом в герметичном
#: прогоне и потому либо не выполнялся вовсе, либо проверял, на какой машине
#: запущен pytest.
ПРОВЕРКИ: tuple[Проверка, ...] = (
    Проверка("fleet.census",
             "Перепись флота: число сайтов и production в реестре"),
    Проверка("fleet.public_domains",
             "Публичные домены отвечают, и отвечают только на чтение"),
    Проверка("registry.version",
             "Версия живого реестра совпадает с объявленной базовой линией"),
    Проверка("registry.synthetic_records",
             "Синтетические записи реестра не изменялись"),
    Проверка("ledger.backup",
             "Резервная копия канонического журнала создаётся и восстанавливается"),
    Проверка("ledger.secrets_not_exposed",
             "В канонической ленте, манифестах и журнале секретов нет"),
    Проверка("systemd.listeners",
             "Control API слушает ровно один раз, дублирующих слушателей нет"),
    Проверка("systemd.no_orphan_processes",
             "Осиротевших экземпляров службы на хосте не осталось"),
    Проверка("templates.credential_boundary",
             "Граница учётных данных юнита templates-cp-consumer"),
)

ПО_ИДЕНТИФИКАТОРУ: dict[str, Проверка] = {п.check_id: п for п in ПРОВЕРКИ}

#: Идентификаторы обязательных проверок. Свидетельство, где нет хотя бы одной,
#: неполно — и релиз по нему не выпускается.
ОБЯЗАТЕЛЬНЫЕ: frozenset[str] = frozenset(
    п.check_id for п in ПРОВЕРКИ if п.required)


class АттестацияНевалидна(ValueError):
    """Документ не является свидетельством объявленной формы."""

    def __init__(self, код: str, detail: str) -> None:
        super().__init__(f"{код}: {detail}")
        self.код = код
        self.detail = detail


@dataclass
class Результат:
    """Исход одной проверки живого хоста."""

    check_id: str
    status: str
    detail: str
    measured_at: str
    observed: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.status not in ДОПУСТИМЫЕ_СТАТУСЫ:
            raise АттестацияНевалидна(
                "HOST_ATTESTATION_MALFORMED",
                f"статус {self.status!r} не объявлен; допустимы {ДОПУСТИМЫЕ_СТАТУСЫ}")
        if self.check_id not in ПО_ИДЕНТИФИКАТОРУ:
            raise АттестацияНевалидна(
                "HOST_ATTESTATION_MALFORMED",
                f"проверка {self.check_id!r} не объявлена в контракте")

    def в_документ(self) -> dict[str, Any]:
        объявлена = ПО_ИДЕНТИФИКАТОРУ[self.check_id]
        тело: dict[str, Any] = {
            "check_id": self.check_id,
            "title": объявлена.title,
            "required": объявлена.required,
            "status": self.status,
            "detail": self.detail,
            "measured_at": self.measured_at,
        }
        if self.observed:
            тело["observed"] = self.observed
        return тело


def сейчас() -> str:
    """Момент измерения в UTC, без микросекунд: точность тут ничего не решает."""
    return (_dt.datetime.now(_dt.timezone.utc)
            .replace(microsecond=0).isoformat().replace("+00:00", "Z"))


def вердикт(результаты: list[Результат]) -> str:
    """PASS только когда каждая ОБЯЗАТЕЛЬНАЯ проверка прошла.

    Порядок предпочтения умышленный: BLOCKED сильнее FAIL. Провал говорит о
    флоте, недоступность — о том, что о флоте ничего не известно, и второе
    опаснее: провал виден, а неизмеренное легко принять за исправное.
    """
    обязательные = [р for р in результаты
                    if ПО_ИДЕНТИФИКАТОРУ[р.check_id].required]
    if any(р.status == "BLOCKED" for р in обязательные):
        return "BLOCKED"
    if any(р.status == "FAIL" for р in обязательные):
        return "FAIL"
    if {р.check_id for р in обязательные} != ОБЯЗАТЕЛЬНЫЕ:
        # Неполный набор не бывает PASS: отсутствующая проверка — это не
        # «нет замечаний», а «не смотрели».
        return "BLOCKED"
    return "PASS"


def собрать(*, candidate_sha: str, hostname: str, control_host: bool,
            evidence_root: str, результаты: list[Результат],
            measured_at: str | None = None) -> dict[str, Any]:
    """Свидетельство целиком. Вердикт вычисляется, а не принимается снаружи."""
    return {
        "schema_version": ВЕРСИЯ_СХЕМЫ,
        "candidate_sha": candidate_sha,
        "measured_at": measured_at or сейчас(),
        "host": {"hostname": hostname, "control_host": control_host,
                 "evidence_root": evidence_root},
        "verdict": вердикт(результаты),
        "checks": [р.в_документ() for р in результаты],
    }


def _валидатор():
    from jsonschema import Draft202012Validator, FormatChecker
    схема = json.loads(СХЕМА.read_text(encoding="utf-8"))
    return Draft202012Validator(схема, format_checker=FormatChecker())


def проверить_схему(документ: Any) -> None:
    """Соответствие объявленной форме. Несоответствие — отказ, не предупреждение."""
    ошибки = sorted(_валидатор().iter_errors(документ), key=lambda о: list(о.path))
    if ошибки:
        путь = "/".join(str(ч) for ч in ошибки[0].path) or "<корень>"
        raise АттестацияНевалидна(
            "HOST_ATTESTATION_MALFORMED",
            f"{путь}: {ошибки[0].message}")


def разобрать(сырое: str | bytes | dict[str, Any]) -> dict[str, Any]:
    """Разобрать и проверить свидетельство. Любая неясность — исключение."""
    if isinstance(сырое, str | bytes):
        try:
            документ = json.loads(сырое)
        except ValueError as ош:
            raise АттестацияНевалидна(
                "HOST_ATTESTATION_MALFORMED",
                f"свидетельство не разбирается как JSON: {ош}") from ош
    else:
        документ = сырое
    if not isinstance(документ, dict):
        raise АттестацияНевалидна("HOST_ATTESTATION_MALFORMED",
                                  "свидетельство не является объектом")
    проверить_схему(документ)
    return документ


def путь_свидетельства(candidate_sha: str,
                       каталог: Path | None = None) -> Path:
    return каталог_свидетельств(каталог) / f"{candidate_sha}.json"


def записать(документ: dict[str, Any], *, каталог: Path | None = None) -> Path:
    """Записать свидетельство под именем своего candidate SHA."""
    проверить_схему(документ)
    путь = путь_свидетельства(документ["candidate_sha"], каталог)
    путь.parent.mkdir(parents=True, exist_ok=True)
    путь.write_text(json.dumps(документ, ensure_ascii=False, indent=2,
                               sort_keys=True) + "\n", encoding="utf-8")
    return путь
