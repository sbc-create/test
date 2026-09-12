"""Единое versioned-отображение сущности каталога в адрес витрины.

Зачем одно место
----------------

Адрес карточки, перечень маршрутов и разрешение адреса рантаймом обязаны
происходить из ОДНОГО правила. Пока их было три — генератор списков брал
полный каталог, генератор страниц брал выборку, а рантайм раздавал файлы, —
рассогласование жило на стыке и не обнаруживалось ни одной из трёх сторон:
каждая была исправна по-своему.

Идентичность сущности, а не домен
---------------------------------

Ключ — стабильный слаг произведения. Домен в адрес не входит и входить не
должен: одна и та же сущность на трёх витринах обязана иметь один и тот же
маршрут, иначе переезд домена переписывал бы все ссылки.

Детерминированность
-------------------

Один и тот же вход даёт один и тот же перечень и один и тот же отпечаток.
Отпечаток карты — то, чем релиз сверяется сам с собой: несовпадение означает,
что карточки и страницы собраны из разных списков.
"""
from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass

ВЕРСИЯ = "lords-urlmap/1.0.0"

#: Допустимый вид слага. Всё прочее адресом не становится: адрес, собранный
#: из непроверенной строки, однажды окажется чужим путём.
СЛАГ = re.compile(r"^[a-z0-9][a-z0-9\-]{0,190}$")
ПРЕФИКС = "/title/"


class UrlMapError(ValueError):
    def __init__(self, код: str, детали: str):
        super().__init__(детали)
        self.error_code, self.detail = код, детали


def нормализовать(адрес: str) -> str:
    """Канонический вид адреса. Совпадает с правилом рантайма."""
    а = (адрес or "/").split("#")[0].split("?")[0]
    while "//" in а:
        а = а.replace("//", "/")
    if not а.startswith("/"):
        а = "/" + а
    а = а.lower()
    if а != "/" and "." not in а.rsplit("/", 1)[-1] and not а.endswith("/"):
        а += "/"
    return а


def маршрут(slug: str) -> str:
    """Единственное определение канонического адреса произведения."""
    s = (slug or "").strip().lower()
    if not СЛАГ.match(s):
        raise UrlMapError("SLUG_INVALID",
                          f"слаг {slug!r} не является идентичностью сущности")
    return f"{ПРЕФИКС}{s}/"


def слаг_из_маршрута(адрес: str) -> str | None:
    а = нормализовать(адрес)
    if not а.startswith(ПРЕФИКС):
        return None
    хвост = а[len(ПРЕФИКС):].strip("/")
    return хвост if хвост and "/" not in хвост else None


@dataclass(frozen=True)
class Карта:
    """Перечень канонических маршрутов опубликованных сущностей."""
    version: str
    routes: tuple[tuple[str, str], ...]        # (slug, route), отсортировано

    @property
    def слаги(self) -> frozenset[str]:
        return frozenset(с for с, _ in self.routes)

    @property
    def адреса(self) -> frozenset[str]:
        return frozenset(а for _, а in self.routes)

    def в_словарь(self) -> dict:
        return {"version": self.version,
                "routes": {с: а for с, а in self.routes}}

    @property
    def отпечаток(self) -> str:
        сырое = json.dumps(self.в_словарь(), ensure_ascii=False, sort_keys=True,
                           separators=(",", ":"))
        return hashlib.sha256(сырое.encode("utf-8")).hexdigest()


def построить(слаги) -> Карта:
    """Карта маршрутов по множеству опубликованных сущностей.

    Порядок фиксирован сортировкой: перечень, зависящий от порядка обхода,
    давал бы разный отпечаток при одном и том же содержимом.
    """
    уникальные = sorted({(s or "").strip().lower() for s in слаги if s})
    пары, занятые = [], {}
    for s in уникальные:
        а = маршрут(s)
        if а in занятые:
            raise UrlMapError(
                "ROUTE_COLLISION",
                f"адрес {а} занят сущностями {занятые[а]!r} и {s!r}")
        занятые[а] = s
        пары.append((s, а))
    return Карта(version=ВЕРСИЯ, routes=tuple(пары))


@dataclass(frozen=True)
class Паритет:
    orphan_targets: tuple[str, ...]     # карточка есть, маршрута нет
    unreferenced_routes: tuple[str, ...]  # маршрут есть, карточки нет
    collisions: tuple[str, ...]

    @property
    def ок(self) -> bool:
        return not self.orphan_targets and not self.collisions


def паритет(цели_карточек, карта: Карта) -> Паритет:
    """Сходятся ли адреса карточек с перечнем маршрутов.

    Маршрут без карточки нарушением не является: страница может быть доступна
    по прямому адресу и не попадать ни в один список. Карточка без маршрута —
    является всегда: это обещание страницы, которой нет.
    """
    цели = {нормализовать(ц) for ц in цели_карточек}
    адреса = карта.адреса
    осиротевшие = tuple(sorted(цели - адреса))
    неупомянутые = tuple(sorted(адреса - цели))
    return Паритет(orphan_targets=осиротевшие,
                   unreferenced_routes=неупомянутые, collisions=())
