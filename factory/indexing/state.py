"""Контракт потребителя: как SEO узнаёт желаемое состояние индексации.

SEO **читает** состояние и никогда его не пишет. Команды OPEN и CLOSE
принадлежат Core: у него durable registry, Action Ledger, revision и одобрение
владельца. Здесь нет и не должно появиться ни одной функции, меняющей желаемое
состояние, — второй писатель означал бы два ответа на вопрос «открыт ли сайт»,
и расходиться они начали бы в первый же день.

Почему контракт появился именно так. Желаемое состояние уже жило в трёх местах:

* ``config/site-profiles/<site_id>.json`` — ``seo_profile.indexing_enabled``;
* ``config/portfolio.json`` — ``indexing_expected`` у SEO-оператора;
* список доменов прямо в коде посредника на хосте.

Совпадали они случайно. Контракт не добавляет четвёртого места: он объявляет
**интерфейс** и одну действующую привязку к тому источнику, который проходит
схему репозитория и сверяется с реестром флота. Остальные становятся
производными и обязаны совпадать — это проверяется тестами.

Разделение ответственности:

===========  ==================================================================
SEO          читает snapshot, согласует слои, ищет дрейф, блокирует релиз
Core         durable registry, Action Ledger, revision, единственные OPEN/CLOSE
Templates    отображает уже вычисленный snapshot и состояния не определяет
===========  ==================================================================

Поведение при отказе провайдера описано в :class:`ResolvedState` и
:func:`resolve`: неизвестный сайт закрыт, а известный не меняет состояние молча.
Недоступность реестра — причина заблокировать релиз, а не повод передумать
насчёт живого сайта.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Protocol

from factory.indexing.policy import (
    CLOSED,
    FLEET_REGISTRY,
    OPEN,
    PolicyError,
    compile_policy,
    normalize_domain,
)

#: Причина, по которой у сайта нет записанного решения. Новый сайт закрыт, и
#: это записанный факт, а не умолчание «наверное, нельзя».
NO_DECISION_REASON = "решения об индексации не принимали"


class ProviderUnavailable(RuntimeError):
    """Реестр состояний недоступен.

    Это не «состояние неизвестно, считаем закрытым». Для уже зарегистрированного
    сайта смена состояния из-за недоступности реестра — это и есть та авария,
    ради предотвращения которой контур написан.
    """


class ProviderCorrupt(RuntimeError):
    """Прочитанное состояние не является состоянием. Релиз блокируется."""


@dataclass(frozen=True)
class IndexingState:
    """Минимальная read-модель. Больше SEO знать не нужно, меньше — нельзя."""

    site_id: str
    domain: str
    desired_state: str
    revision: int
    updated_at: str
    source_event_id: str
    last_known_good_revision: int
    reason: str = ""

    def __post_init__(self) -> None:
        if self.desired_state not in (OPEN, CLOSED):
            raise ProviderCorrupt(
                f"{self.site_id}: desired_state={self.desired_state!r}, "
                f"допустимо только {OPEN!r} или {CLOSED!r}"
            )
        if self.revision < 0:
            raise ProviderCorrupt(f"{self.site_id}: отрицательная revision")

    @property
    def open(self) -> bool:
        return self.desired_state == OPEN


@dataclass(frozen=True)
class StateSnapshot:
    """Состояние всего флота, снятое одной revision.

    Одна revision на весь снимок — не удобство, а требование: заголовок,
    мета-тег, canonical, ``robots.txt`` и карта сайта обязаны вычисляться из
    одного и того же снимка. Иначе публикуется смешанное состояние, в котором
    часть слоёв уже открыта, а часть ещё закрыта.
    """

    revision: int
    taken_at: str
    states: dict[str, IndexingState] = field(default_factory=dict)
    source: str = ""

    def by_domain(self, host: str) -> IndexingState | None:
        имя = normalize_domain(host)
        for состояние in self.states.values():
            if состояние.domain == имя:
                return состояние
        return None

    @property
    def open_domains(self) -> tuple[str, ...]:
        return tuple(sorted(с.domain for с in self.states.values() if с.open))

    @property
    def closed_domains(self) -> tuple[str, ...]:
        return tuple(sorted(с.domain for с in self.states.values() if not с.open))

    def matrix(self) -> dict:
        return {
            "open": list(self.open_domains),
            "closed": list(self.closed_domains),
            "open_count": len(self.open_domains),
            "closed_count": len(self.closed_domains),
            "revision": self.revision,
        }


class IndexingStateProvider(Protocol):
    """Источник желаемого состояния.

    Намеренно без методов записи: у SEO нет и не будет способа открыть или
    закрыть сайт. Реализация, добавившая сюда мутацию, нарушает разделение
    ответственности, а не расширяет интерфейс.
    """

    def snapshot(self) -> StateSnapshot:
        """Состояние всего флота одной revision."""
        ...


@dataclass
class GitProfileProvider:
    """Действующая привязка: версионируемые профили сайтов и реестр флота.

    Это **временный** источник до того, как Core выдаст durable registry с
    собственной revision. Он выбран не произвольно: профиль проходит схему
    ``site-profile.schema.json``, реестр перечисляет обслуживаемые домены, и
    оба меняются только через обзор изменений. То есть «одобрение владельца»
    здесь — это принятый PR, а ``source_event_id`` — коммит.

    Revision выводится из коммита дерева, а не из времени: время идёт вперёд
    само по себе, и состояние, привязанное к нему, начинает «меняться» без
    единого решения.
    """

    profiles_dir: Path
    fleet_path: Path | None = None
    revision: int = 0
    source_event_id: str = ""
    updated_at: str = ""

    def snapshot(self) -> StateSnapshot:
        каталог = Path(self.profiles_dir)
        реестр = self.fleet_path or каталог.parent / FLEET_REGISTRY.name
        try:
            политика = compile_policy(каталог, fleet_path=Path(реестр))
        except PolicyError as ошибка:
            # Повреждённый вход — не повод считать всё закрытым: это повод
            # остановить релиз. Разница принципиальна: «закрыть всё» — тоже
            # изменение живого состояния.
            raise ProviderCorrupt(str(ошибка)) from ошибка

        снято = self.updated_at or datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        состояния: dict[str, IndexingState] = {}
        for домен, решение in политика.decisions.items():
            состояния[решение.site_id] = IndexingState(
                site_id=решение.site_id,
                domain=домен,
                desired_state=решение.expected,
                revision=self.revision,
                updated_at=снято,
                source_event_id=self.source_event_id or "uncommitted",
                last_known_good_revision=self.revision,
                reason=решение.reason,
            )
        return StateSnapshot(
            revision=self.revision, taken_at=снято, states=состояния,
            source=f"git:{каталог}",
        )


@dataclass
class CoreLedgerProvider:
    """Привязка к durable registry Core. Ещё не подключена.

    Ветка ``claude/fleet-core-003-r2`` содержит контракт
    ``DesiredObservedState`` и Action Ledger, но ни состояния индексации, ни
    команд OPEN/CLOSE, ни revision в ней нет. Пока их нет, провайдер честно
    сообщает о недоступности вместо того, чтобы возвращать выдуманное
    состояние: выдуманное «закрыто» закрыло бы живую витрину, выдуманное
    «открыто» открыло бы непроверенную.
    """

    endpoint: str = ""

    def snapshot(self) -> StateSnapshot:
        raise ProviderUnavailable(
            "durable registry Core не реализован: в claude/fleet-core-003-r2 "
            "нет состояния индексации, команд OPEN/CLOSE и revision"
        )


@dataclass
class ResolvedState:
    """Результат чтения состояния вместе с тем, можно ли выкладывать релиз."""

    snapshot: StateSnapshot
    from_last_known_good: bool = False
    release_blocked: bool = False
    blockers: list[str] = field(default_factory=list)

    def report(self) -> str:
        строки = [f"revision={self.snapshot.revision} источник={self.snapshot.source}"]
        if self.from_last_known_good:
            строки.append("взят подтверждённый last-known-good снимок")
        if self.blockers:
            строки.append("Релиз заблокирован:")
            строки += [f"  !! {b}" for b in self.blockers]
        return "\n".join(строки)


def resolve(
    provider: IndexingStateProvider,
    *,
    last_known_good: StateSnapshot | None = None,
) -> ResolvedState:
    """Прочитать состояние, не меняя его ни при каком исходе.

    Три исхода, и все три названы:

    * провайдер ответил — работаем с его снимком;
    * провайдер недоступен, но есть подтверждённый снимок — берём его и
      **блокируем релиз**: действующий production продолжает работать как был,
      а новая выкладка ждёт восстановления реестра;
    * провайдер недоступен и подтверждённого снимка нет — блокируем релиз и
      не публикуем ничего. Пустая матрица здесь означала бы «закрыть всё».
    """
    try:
        снимок = provider.snapshot()
    except ProviderCorrupt as ошибка:
        if last_known_good is None:
            return ResolvedState(
                snapshot=StateSnapshot(revision=-1, taken_at="", source="none"),
                release_blocked=True,
                blockers=[f"состояние повреждено и подтверждённого снимка нет: {ошибка}"],
            )
        return ResolvedState(
            snapshot=last_known_good, from_last_known_good=True, release_blocked=True,
            blockers=[f"состояние повреждено: {ошибка}"],
        )
    except ProviderUnavailable as ошибка:
        if last_known_good is None:
            return ResolvedState(
                snapshot=StateSnapshot(revision=-1, taken_at="", source="none"),
                release_blocked=True,
                blockers=[f"реестр недоступен и подтверждённого снимка нет: {ошибка}"],
            )
        return ResolvedState(
            snapshot=last_known_good, from_last_known_good=True, release_blocked=True,
            blockers=[f"реестр недоступен: {ошибка}"],
        )

    if last_known_good is not None and снимок.revision < last_known_good.revision:
        # Старый релиз не может переписать более новую revision. Это тот самый
        # случай, когда восстановление файлов прежней выкладки возвращает и
        # прежнее состояние индексации.
        return ResolvedState(
            snapshot=last_known_good, from_last_known_good=True, release_blocked=True,
            blockers=[
                f"устаревшая revision {снимок.revision} против подтверждённой "
                f"{last_known_good.revision}: старый артефакт не переписывает новое решение"
            ],
        )
    return ResolvedState(snapshot=снимок)


def state_for_host(снимок: StateSnapshot, host: str) -> IndexingState:
    """Решение по хосту запроса. Неизвестный хост закрыт — это правило 1."""
    найдено = снимок.by_domain(host)
    if найдено is not None:
        return найдено
    имя = normalize_domain(host)
    return IndexingState(
        site_id="", domain=имя, desired_state=CLOSED, revision=снимок.revision,
        updated_at=снимок.taken_at, source_event_id="unknown-host",
        last_known_good_revision=снимок.revision, reason=NO_DECISION_REASON,
    )


def load_snapshot(path: Path) -> StateSnapshot:
    """Прочитать сохранённый снимок (подтверждённый last-known-good)."""
    текст = Path(path).read_text(encoding="utf-8")
    if not текст.strip():
        raise ProviderCorrupt(f"{Path(path).name}: снимок пуст")
    try:
        данные = json.loads(текст)
    except ValueError as ошибка:
        raise ProviderCorrupt(f"{Path(path).name}: снимок не разбирается — {ошибка}") from ошибка
    состояния = {
        sid: IndexingState(**з) for sid, з in (данные.get("states") or {}).items()
    }
    return StateSnapshot(
        revision=int(данные["revision"]), taken_at=данные.get("taken_at", ""),
        states=состояния, source=данные.get("source", ""),
    )


def dump_snapshot(снимок: StateSnapshot, path: Path) -> Path:
    """Сохранить снимок детерминированно.

    Это запись **наблюдения**, а не желаемого состояния: файл нужен, чтобы
    следующий запуск мог сослаться на подтверждённый снимок при недоступности
    реестра. Изменить решение владельца им нельзя.
    """
    тело = {
        "revision": снимок.revision,
        "taken_at": снимок.taken_at,
        "source": снимок.source,
        "states": {
            sid: {
                "site_id": с.site_id, "domain": с.domain,
                "desired_state": с.desired_state, "revision": с.revision,
                "updated_at": с.updated_at, "source_event_id": с.source_event_id,
                "last_known_good_revision": с.last_known_good_revision,
                "reason": с.reason,
            }
            for sid, с in sorted(снимок.states.items())
        },
    }
    цель = Path(path)
    цель.parent.mkdir(parents=True, exist_ok=True)
    цель.write_text(
        json.dumps(тело, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    return цель
