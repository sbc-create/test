"""Ворота релиза: запрет на выкладку, меняющую политику индексации незаметно.

Ворота отвечают на один вопрос — чем состояние, которое собираются выложить,
отличается от разрешённого владельцем и от того, что работает сейчас. Ответ
«ничем» открывает выкладку; любой другой её останавливает, и останавливает ДО
изменений, а не после.

Изменение политики обязано быть видимым различием: домен, было, стало,
основание. Изменение, которого никто не собирался делать, отличается от
задуманного только тем, что его никто не назвал, — и ворота существуют, чтобы
это различие проявилось.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from factory.indexing.policy import CLOSED, OPEN, IndexingPolicy, PolicyError


@dataclass(frozen=True)
class MatrixChange:
    domain: str
    before: str
    after: str
    reason: str

    def __str__(self) -> str:
        return f"{self.domain}: {self.before} → {self.after} ({self.reason})"


@dataclass
class GateResult:
    allowed: bool
    blockers: list[str] = field(default_factory=list)
    changes: list[MatrixChange] = field(default_factory=list)
    expected_matrix: dict = field(default_factory=dict)

    def report(self) -> str:
        строки = []
        if self.changes:
            строки.append("Изменения политики индексации:")
            строки += [f"  {c}" for c in self.changes]
        else:
            строки.append("Изменений политики индексации нет.")
        if self.blockers:
            строки.append("Выкладка запрещена:")
            строки += [f"  !! {b}" for b in self.blockers]
        return "\n".join(строки)


def check(
    candidate: IndexingPolicy,
    *,
    allowed_open: set[str],
    allowed_closed: set[str],
    live: dict[str, str] | None = None,
    approved_changes: set[str] | None = None,
) -> GateResult:
    """Сверить кандидата с разрешением владельца и с живым состоянием.

    ``allowed_open`` и ``allowed_closed`` — матрица, которую владелец разрешил.
    ``live`` — фактическое состояние доменов, если его удалось измерить;
    ``None`` означает «неизвестно», и это само по себе блокирует выкладку:
    сравнивать не с чем.
    ``approved_changes`` — домены, изменение которых в этой выкладке
    предусмотрено. Всё остальное, что изменилось, — незапланированное.
    """
    результат = GateResult(allowed=True, expected_matrix=candidate.matrix())
    одобрено = {d.lower() for d in (approved_changes or set())}

    факт_open = set(candidate.open_domains)
    факт_closed = set(candidate.closed_domains)

    лишние_открытые = факт_open - allowed_open
    for домен in sorted(лишние_открытые):
        результат.blockers.append(
            f"{домен}: кандидат открывает домен, которого нет в разрешённой матрице"
        )
    не_открытые = allowed_open - факт_open
    for домен in sorted(не_открытые):
        результат.blockers.append(
            f"{домен}: владелец разрешил OPEN, кандидат его не открывает"
        )
    лишние_закрытые = факт_closed - allowed_closed
    for домен in sorted(лишние_закрытые):
        результат.blockers.append(
            f"{домен}: кандидат знает домен, которого нет в разрешённой матрице"
        )
    нет_в_кандидате = allowed_closed - факт_closed
    for домен in sorted(нет_в_кандидате):
        результат.blockers.append(
            f"{домен}: разрешённый домен отсутствует в кандидате"
        )

    if live is None:
        результат.blockers.append(
            "исходное живое состояние неизвестно: сравнивать кандидата не с чем"
        )
    else:
        for домен, решение in sorted(candidate.decisions.items()):
            было = live.get(домен)
            if было is None:
                результат.blockers.append(
                    f"{домен}: живое состояние не измерено, выкладка вслепую запрещена"
                )
                continue
            if было != решение.expected:
                изменение = MatrixChange(домен, было, решение.expected, решение.reason)
                результат.changes.append(изменение)
                if домен not in одобрено:
                    результат.blockers.append(
                        f"{домен}: незапланированное изменение {было} → {решение.expected}"
                    )
        лишние_живые = set(live) - set(candidate.decisions)
        for домен in sorted(лишние_живые):
            результат.blockers.append(
                f"{домен}: домен обслуживается, но профиля в кандидате нет"
            )

    результат.allowed = not результат.blockers
    return результат


def require(result: GateResult) -> None:
    """Остановить выкладку, если ворота её не пропустили."""
    if not result.allowed:
        raise PolicyError("ворота релиза не пропускают выкладку:\n" + result.report())


def matrix_from_live(states: dict[str, str]) -> dict[str, str]:
    """Привести измеренное состояние к словарю домен → open|closed."""
    приведено = {}
    for домен, состояние in states.items():
        значение = состояние.lower()
        if значение not in (OPEN, CLOSED):
            raise PolicyError(
                f"{домен}: состояние {состояние!r} не является ни {OPEN}, ни {CLOSED}. "
                "Промежуточное состояние не может служить основанием для выкладки"
            )
        приведено[домен.lower()] = значение
    return приведено
