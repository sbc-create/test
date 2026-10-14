"""Согласованность слоёв, закрывающих витрину от индексации.

Индексацию витрины закрывают четыре независимых слоя: заголовок
``X-Robots-Tag``, ``robots.txt``, мета-тег в HTML и флаг публикации в профиле.
Пока они говорят одно и то же, состояние понятно и надёжно: чтобы открыть сайт,
нужно снять все четыре.

Опасно не открытое и не закрытое состояние, а **расхождение**. Оно означает, что
один слой уже сняли, а остальные держат, — и сайт держится не замыслом, а тем,
из четырёх запретов пока действуют не все. Заметить это со стороны почти
невозможно: снаружи сайт по-прежнему не индексируется, и отчёт, считающий только
«индексируется или нет», покажет прежнее благополучие.

Так и случилось 2026-09-15. На ``yummyani.site`` выкатили мета-тег
``index, follow`` и наполнили карту сайта, а заголовок и ``robots.txt`` остались
запрещающими. Фактически сайт не индексировался, но HTML уже звал робота, и до
полного открытия оставалась одна выкладка. Суточный цикл этого не увидел: он
такого вопроса не задавал. Здесь этот вопрос задан.

Модуль ничего не меняет. Он умеет только прочитать четыре слоя и сказать, что
они разошлись.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

CLOSED = "CLOSED"
OPEN = "OPEN"
MIXED = "MIXED"

#: Порядок важен: он же порядок снятия при будущем открытии. Заголовок снимается
#: последним, потому что он один перекрывает остальные слои.
LAYERS = ("profile_flag", "meta_robots", "robots_txt", "x_robots_tag")

_DISALLOW_ALL = re.compile(r"(?im)^\s*Disallow:\s*/\s*$")


@dataclass(frozen=True)
class LockState:
    site_id: str
    x_robots_tag: bool
    robots_txt: bool
    meta_robots: bool
    profile_flag: bool
    #: Какие слои удалось измерить. Неизмеренный слой в вердикт не входит —
    #: иначе отсутствие источника профиля превратилось бы в расхождение на всех
    #: витринах сразу, то есть в ложную тревогу вместо настоящей.
    measured: tuple[str, ...] = LAYERS

    @property
    def closed_layers(self) -> tuple[str, ...]:
        return tuple(n for n in LAYERS if n in self.measured and getattr(self, n))

    @property
    def open_layers(self) -> tuple[str, ...]:
        return tuple(n for n in LAYERS if n in self.measured and not getattr(self, n))

    @property
    def unmeasured_layers(self) -> tuple[str, ...]:
        return tuple(n for n in LAYERS if n not in self.measured)

    @property
    def verdict(self) -> str:
        if not self.open_layers:
            return CLOSED
        if not self.closed_layers:
            return OPEN
        return MIXED


def read_state(
    site_id: str,
    *,
    response_headers: str,
    robots_txt: str,
    html: str,
    profile_indexing_enabled: bool | None,
    profile_measured: bool = True,
) -> LockState:
    """Собрать состояние слоёв из того, что витрина отдала.

    Различаются два разных «нет». ``profile_measured=False`` — источник профиля
    в этой раскладке недоступен вообще, слой не измерялся и в вердикт не входит.
    ``profile_indexing_enabled=None`` при измеренном слое — профиль есть, но
    прочитать значение не удалось; такой слой считается НЕзакрытым, потому что
    закрытость надо подтвердить, а не предположить.

    Разница существенна. Первое молчит там, где сказать нечего. Второе поднимает
    тревогу там, где ответ был обязан быть и его нет.
    """
    meta = re.search(r'name=["\']robots["\'][^>]*content=["\']([^"\']*)["\']', html, re.I)
    measured = LAYERS if profile_measured else tuple(n for n in LAYERS if n != "profile_flag")
    return LockState(
        site_id=site_id,
        x_robots_tag="noindex" in response_headers.lower(),
        robots_txt=bool(_DISALLOW_ALL.search(robots_txt)),
        meta_robots=bool(meta and "noindex" in meta.group(1).lower()),
        profile_flag=profile_indexing_enabled is False,
        measured=measured,
    )


def findings(state: LockState, *, expected: str = "closed") -> list[dict]:
    """Две разные находки, и путать их нельзя.

    ``LCK-001`` — слои говорят разное. Витрина держится не замыслом, а тем, что
    из запретов действуют не все; куда она при этом «склоняется», неважно.

    ``LCK-002`` — слои согласованы, но согласованы не на том, что решил владелец.
    Это не дефект конфигурации, а расхождение с решением: либо решение не
    доведено до публичного адреса, либо состояние изменили без решения.

    ``expected`` — ``"open"`` или ``"closed"``, из реестра портфеля. Умолчание
    ``"closed"``: открытие это письменное решение, а не то, что случается само.
    """
    if state.verdict == MIXED:
        return _mixed_finding(state)
    if state.verdict != expected.upper():
        return [
            {
                "id": "LCK-002",
                "category": "indexing",
                "severity": "критично",
                "summary": (
                    f"состояние индексации {state.verdict} расходится с решением "
                    f"владельца {expected.upper()}"
                ),
                "affected_urls": [],
                "recommendation": (
                    "привести витрину к решению владельца либо изменить решение "
                    "в реестре портфеля — расхождение не должно жить молча"
                ),
                "evidence": f"слои: закрыты {state.closed_layers}, открыты {state.open_layers}",
            }
        ]
    return []


def _mixed_finding(state: LockState) -> list[dict]:
    return [
        {
            "id": "LCK-001",
            "category": "indexing",
            "severity": "критично",
            "summary": (
                f"слои запрета индексации разошлись: сняты {', '.join(state.open_layers)}, "
                f"держат {', '.join(state.closed_layers)}"
            ),
            "affected_urls": [],
            "recommendation": (
                "привести слои к одному состоянию: либо вернуть снятые, либо снять "
                "остальные осознанным решением владельца"
            ),
            "evidence": (
                "витрина не индексируется, пока держит хотя бы заголовок или robots.txt, "
                "но держится не замыслом, а остатком запретов"
            ),
        }
    ]


def summarize(states: list[LockState]) -> dict:
    """Сводка для отчёта. Частично снятый замок считается отдельно от снятого."""
    return {
        "total": len(states),
        "closed": sum(1 for s in states if s.verdict == CLOSED),
        "mixed": sum(1 for s in states if s.verdict == MIXED),
        "open": sum(1 for s in states if s.verdict == OPEN),
        "mixed_sites": [s.site_id for s in states if s.verdict == MIXED],
    }
