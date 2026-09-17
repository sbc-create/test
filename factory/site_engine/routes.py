"""Реестр адресов: устойчивая личность записи отдельно от её имени.

Дефект, который этот модуль устраняет, стоил 0,4 % каталога — 207 записей из
53 116. Прежняя схема давала второму тайтлу с тем же именем адрес `X-2`, не
проверяя, что `X-2` — законный адрес другого тайтла, которого зовут «X 2». Один
затирал другого, и потерянный не имел адреса вовсе.

Три свойства, ради которых написан реестр.

**Личность отделена от имени.** Адрес принадлежит `content_id`, а не строке
названия. Переименование тайтла у поставщика больше не отбирает адрес у соседа.

**Порядок обхода не влияет на адреса.** Прежняя схема раздавала суффиксы в
порядке ответа API: тот же каталог, пришедший в другом порядке, давал другие
адреса. Здесь владелец адреса записан в реестре, а новичкам адрес считается от
их собственного `content_id`.

**Новый адрес не может столкнуться с естественным.** Разделитель — два дефиса,
а `slugify` схлопывает любую их серию в один. Значит, `X--a1b2c3` не получится
ни из какого названия, и пространства имён не пересекаются по построению.
"""
from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable
from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
from pathlib import Path

SCHEMA_VERSION = "1.0"

#: Разделитель адреса-разрешения. Два дефиса выбраны не для красоты: `slugify`
#: схлопывает `-{2,}` в один дефис, поэтому такая последовательность не может
#: появиться в адресе, выведенном из названия. Это и делает новые адреса
#: неспособными столкнуться со старыми.
SEPARATOR = "--"

#: Длина различающей части. Шесть шестнадцатеричных знаков — 16,7 млн значений
#: на группу коллизии, где записей обычно две. Вероятность совпадения внутри
#: группы пренебрежима, но проверяется явно, а не принимается на веру.
DISCRIMINATOR_LENGTH = 6


class RouteError(Exception):
    pass


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def discriminator(content_id: str, length: int = DISCRIMINATOR_LENGTH) -> str:
    """Различающая часть адреса, выведенная из личности записи.

    Зависит только от `content_id`, поэтому повторный импорт даёт тот же адрес,
    а порядок обхода на него не влияет вовсе.
    """
    return hashlib.sha256(content_id.encode("utf-8")).hexdigest()[:length]


@dataclass(frozen=True)
class Route:
    content_id: str
    site_id: str
    canonical_path: str
    collision_group: str
    legacy_paths: tuple[str, ...] = ()
    route_version: int = 1
    created_at: str = field(default_factory=_now)
    updated_at: str = field(default_factory=_now)

    def as_dict(self) -> dict:
        return {
            "content_id": self.content_id,
            "site_id": self.site_id,
            "canonical_path": self.canonical_path,
            "collision_group": self.collision_group,
            "legacy_paths": list(self.legacy_paths),
            "route_version": self.route_version,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, raw: dict) -> Route:
        return cls(
            content_id=raw["content_id"],
            site_id=raw["site_id"],
            canonical_path=raw["canonical_path"],
            collision_group=raw["collision_group"],
            legacy_paths=tuple(raw.get("legacy_paths") or ()),
            route_version=int(raw.get("route_version", 1)),
            created_at=raw.get("created_at") or _now(),
            updated_at=raw.get("updated_at") or _now(),
        )


@dataclass(frozen=True)
class Candidate:
    """Запись, которой нужен адрес."""

    content_id: str
    base_slug: str


class RouteRegistry:
    """Кто каким адресом владеет, с историей.

    Реестр — источник правды об адресах. Витрина не выводит адрес из названия
    самостоятельно: она спрашивает реестр. Иначе два места в коде однажды
    ответят по-разному, и внутренние ссылки поведут в никуда.
    """

    def __init__(self, site_id: str, routes: Iterable[Route] = ()) -> None:
        self.site_id = site_id
        self._by_content: dict[str, Route] = {}
        self._by_path: dict[str, str] = {}
        for route in routes:
            self._register(route)

    # ------------------------------------------------------------------ чтение
    def path_for(self, content_id: str) -> str:
        try:
            return self._by_content[content_id].canonical_path
        except KeyError:
            raise RouteError(f"адрес для {content_id} не назначен") from None

    def route_for(self, content_id: str) -> Route | None:
        return self._by_content.get(content_id)

    def owner_of(self, path: str) -> str | None:
        return self._by_path.get(path)

    def __len__(self) -> int:
        return len(self._by_content)

    def __iter__(self):
        return iter(sorted(self._by_content.values(), key=lambda r: r.content_id))

    # ------------------------------------------------------------------ запись
    def _register(self, route: Route) -> None:
        занято = self._by_path.get(route.canonical_path)
        if занято is not None and занято != route.content_id:
            raise RouteError(
                f"адрес {route.canonical_path} уже принадлежит {занято}, "
                f"нельзя отдать его {route.content_id}"
            )
        prev = self._by_content.get(route.content_id)
        if prev is not None:
            self._by_path.pop(prev.canonical_path, None)
        self._by_content[route.content_id] = route
        self._by_path[route.canonical_path] = route.content_id

    def assign(self, candidates: Iterable[Candidate]) -> dict[str, str]:
        """Назначить адреса, сохранив все уже выданные.

        Порядок важен и продиктован требованием «работающие ссылки не ломать».

        Сперва за каждой записью закрепляется адрес, который у неё уже есть.
        Первая редакция этого не делала: она признавала владельцем только
        базовый адрес группы и выселяла всех прочих на `--`-адреса. На живом
        каталоге это переставило бы 5 435 работающих ссылок — записи, законно
        занявшие `X-2` и ни с кем не конфликтующие.

        Затем адреса получают те, у кого их нет: базовый, если он свободен,
        иначе выведенный из `content_id`. От порядка обхода результат не
        зависит — ни на первом шаге, ни на втором.
        """
        все = list(candidates)
        итог: dict[str, str] = {}
        занято: set[str] = set()

        # Шаг первый: за каждым остаётся то, чем он уже владеет.
        for cand in все:
            прежний = self._by_content.get(cand.content_id)
            if прежний is not None and self._by_path.get(прежний.canonical_path) == cand.content_id:
                итог[cand.content_id] = прежний.canonical_path
                занято.add(прежний.canonical_path)

        # Шаг второй: остальным — свободный базовый или собственный.
        по_группам: dict[str, list[Candidate]] = {}
        for cand in все:
            if cand.content_id not in итог:
                по_группам.setdefault(cand.base_slug, []).append(cand)

        for group in sorted(по_группам):
            # Внутри группы порядок фиксируется по content_id, а не по тому,
            # в каком порядке поставщик вернул записи.
            for cand in sorted(по_группам[group], key=lambda c: c.content_id):
                if group not in занято:
                    путь = group
                else:
                    путь = f"{group}{SEPARATOR}{discriminator(cand.content_id)}"
                    if путь in занято:
                        # Совпадение различающей части внутри группы —
                        # событие пренебрежимо редкое, но проверяемое, а не
                        # принимаемое на веру.
                        raise RouteError(
                            f"различающая часть адреса {путь} уже занята; "
                            "требуется удлинить её для этой группы"
                        )
                итог[cand.content_id] = путь
                занято.add(путь)
                self._assign_one(cand, путь, group)

        self._check_no_duplicates()
        return итог

    def move(self, content_id: str, new_path: str) -> Route:
        """Намеренный перенос адреса.

        Обычное переименование тайтла у поставщика адрес НЕ двигает: слаг —
        человекочитаемое представление, а личность несёт `content_id`, и
        работающая ссылка важнее совпадения адреса с текущим названием.

        Но миграция маршрутов иногда нужна по-настоящему — например при смене
        схемы адресов. Тогда она делается этим вызовом: явно, с записью
        прежнего адреса в историю и повышением версии, чтобы с него встало
        перенаправление.
        """
        прежний = self._by_content.get(content_id)
        if прежний is None:
            raise RouteError(f"нечего переносить: {content_id} не имеет адреса")
        if прежний.canonical_path == new_path:
            return прежний
        занято = self._by_path.get(new_path)
        if занято is not None and занято != content_id:
            raise RouteError(
                f"адрес {new_path} принадлежит {занято}; перенос отобрал бы его"
            )
        self._by_path.pop(прежний.canonical_path, None)
        обновлён = replace(
            прежний,
            canonical_path=new_path,
            legacy_paths=tuple(
                dict.fromkeys((*прежний.legacy_paths, прежний.canonical_path))
            ),
            route_version=прежний.route_version + 1,
            updated_at=_now(),
        )
        self._register(обновлён)
        return обновлён

    def _assign_one(self, cand: Candidate, path: str, group: str) -> None:
        prev = self._by_content.get(cand.content_id)
        if prev is not None and prev.canonical_path == path:
            return
        legacy = ()
        version = 1
        created = _now()
        if prev is not None:
            # Прежний адрес не забывается: с него ставится перенаправление, и
            # ссылка, которую кто-то сохранил, продолжает работать.
            legacy = tuple(dict.fromkeys((*prev.legacy_paths, prev.canonical_path)))
            version = prev.route_version + 1
            created = prev.created_at
            self._by_path.pop(prev.canonical_path, None)
        self._register(
            Route(
                content_id=cand.content_id,
                site_id=self.site_id,
                canonical_path=path,
                collision_group=group,
                legacy_paths=legacy,
                route_version=version,
                created_at=created,
                updated_at=_now(),
            )
        )

    def _check_no_duplicates(self) -> None:
        пути: dict[str, str] = {}
        for route in self._by_content.values():
            прежний = пути.get(route.canonical_path)
            if прежний is not None:
                raise RouteError(
                    f"адрес {route.canonical_path} назначен дважды: "
                    f"{прежний} и {route.content_id}"
                )
            пути[route.canonical_path] = route.content_id

    # ---------------------------------------------------------------- хранение
    def save(self, path: Path) -> Path:
        payload = {
            "schema_version": SCHEMA_VERSION,
            "site_id": self.site_id,
            "routes": [r.as_dict() for r in self],
        }
        path.parent.mkdir(parents=True, exist_ok=True)
        # Запись через временный файл и атомарную замену: оборванная запись
        # реестра оставила бы витрину без адресов вовсе.
        tmp = path.with_suffix(path.suffix + ".tmp")
        tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
                       encoding="utf-8")
        tmp.replace(path)
        return path

    @classmethod
    def load(cls, path: Path, site_id: str | None = None) -> RouteRegistry:
        if not path.exists():
            return cls(site_id or "")
        raw = json.loads(path.read_text(encoding="utf-8"))
        if raw.get("schema_version") != SCHEMA_VERSION:
            raise RouteError(
                f"реестр версии {raw.get('schema_version')!r}, ожидается {SCHEMA_VERSION}"
            )
        return cls(raw["site_id"], (Route.from_dict(r) for r in raw.get("routes", ())))

    def redirects(self) -> dict[str, str]:
        """Прежние адреса и их нынешние цели."""
        out: dict[str, str] = {}
        for route in self:
            for legacy in route.legacy_paths:
                if legacy != route.canonical_path:
                    out[legacy] = route.canonical_path
        return out


def seed_from_live(site_id: str, assigned: dict[str, str]) -> RouteRegistry:
    """Реестр, повторяющий то, что уже опубликовано.

    Нужен один раз, при переходе. Владение базовыми адресами берётся из живого
    состояния, а не назначается заново, — иначе первое же применение реестра
    переставило бы работающие ссылки.
    """
    registry = RouteRegistry(site_id)
    for content_id, path in sorted(assigned.items()):
        if registry.owner_of(path) is not None:
            # На живой витрине адрес физически один, и второй претендент на
            # него — как раз потерянная запись. Ей адрес назначит `assign`.
            continue
        registry._register(
            Route(
                content_id=content_id,
                site_id=site_id,
                canonical_path=path,
                collision_group=path,
            )
        )
    return registry
