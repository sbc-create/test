#!/usr/bin/env python3
"""Барьер ревизий: вытесненная заявка не переключит production никогда.

Зачем
-----

Дважды подряд заявка присоединялась к чужому прогону и часами отрисовывала не
то, что просили. Оба раза защита была одна — надежда, что порядок событий
окажется правильным. Порядок оказывался неправильным, и каждый раз это стоило
часов.

Барьер убирает надежду из схемы. У каждой витрины есть монотонное поколение и
объявленная желаемая ревизия. Заявка получает номер поколения при постановке в
очередь и предъявляет его в четырёх местах: при постановке, при захвате, перед
отрисовкой и **непосредственно перед атомарным переключением**. Между третьим и
четвёртым проходят часы, и именно там раньше и происходила подмена.

Заявка, чьё поколение отстало, не «повторяется позже» и не «ждёт своей
очереди»: она заканчивается `STALE_FENCED_NO_CHANGE` и не возобновляется
никогда. Старый артефакт разрешён только явным откатом — и тот заводит **новое**
поколение, а не воскрешает старое.

Устройство
----------

Состояние барьера — один файл на витрину, читаемый кем угодно и изменяемый
только владельцем очереди. Запись атомарна: половина файла читается как
испорченный JSON, а испорченный барьер хуже отсутствующего, потому что молча
разрешает всё.
"""

from __future__ import annotations

import json
import os
import re
import time
from dataclasses import dataclass, asdict
from pathlib import Path

БАЗА = Path("/var/lib/lords-deploy/fence")
ХЕКС40 = re.compile(r"^[0-9a-f]{40}$")
ХЕКС64 = re.compile(r"^[0-9a-f]{64}$")
ИМЯ_САЙТА = re.compile(r"^[a-z][a-z0-9-]{2,31}$")

#: Итог заявки, вытесненной более новым поколением. Отдельный статус, а не
#: «ошибка»: ничего не сломалось, просто эта работа больше не нужна.
ВЫТЕСНЕНА = "STALE_FENCED_NO_CHANGE"


class FenceError(Exception):
    """Барьер отказал. Действие не выполнено."""


@dataclass(frozen=True)
class Барьер:
    """Объявленное желаемое состояние витрины."""

    site: str
    generation: int
    desired_revision: str
    desired_artifact_sha256: str
    updated_at_utc: str
    reason: str = ""

    def as_dict(self) -> dict:
        return asdict(self)


def _путь(site: str, корень: Path | None = None) -> Path:
    if not ИМЯ_САЙТА.match(site or ""):
        raise FenceError(f"имя витрины негодно: {site!r}")
    return (корень or БАЗА) / f"{site}.json"


def прочитать(site: str, *, корень: Path | None = None) -> Барьер | None:
    """Текущий барьер витрины. `None` — барьера ещё нет.

    Испорченный файл — это отказ, а не «барьера нет»: молча разрешить всё в
    момент, когда защита сломана, значит потерять её ровно тогда, когда она
    нужнее всего.
    """
    путь = _путь(site, корень)
    if not путь.is_file():
        return None
    try:
        данные = json.loads(путь.read_text(encoding="utf-8"))
    except json.JSONDecodeError as ошибка:
        raise FenceError(f"барьер {site} испорчен: {ошибка}") from ошибка
    try:
        return Барьер(
            site=данные["site"], generation=int(данные["generation"]),
            desired_revision=данные["desired_revision"],
            desired_artifact_sha256=данные["desired_artifact_sha256"],
            updated_at_utc=данные.get("updated_at_utc", ""),
            reason=данные.get("reason", ""),
        )
    except (KeyError, TypeError, ValueError) as ошибка:
        raise FenceError(f"барьер {site} неполон: {ошибка}") from ошибка


def объявить(site: str, revision: str, artifact_sha256: str, *,
             reason: str = "", корень: Path | None = None) -> Барьер:
    """Объявить новое желаемое состояние. Поколение растёт всегда.

    Растёт даже когда ревизия та же: повторное объявление — это осознанное
    решение выложить заново, и все заявки прежнего поколения обязаны быть
    вытеснены им. Иначе «повторить ту же выкладку» означало бы гонку между
    старой и новой попыткой.
    """
    if not ХЕКС40.match(revision or ""):
        raise FenceError(f"ревизия должна быть полным SHA: {revision!r}")
    if not ХЕКС64.match(artifact_sha256 or ""):
        raise FenceError(f"отпечаток артефакта негоден: {artifact_sha256!r}")
    прежний = прочитать(site, корень=корень)
    поколение = (прежний.generation + 1) if прежний else 1
    новый = Барьер(site=site, generation=поколение, desired_revision=revision,
                   desired_artifact_sha256=artifact_sha256,
                   updated_at_utc=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                   reason=reason[:300])
    _записать(новый, корень=корень)
    return новый


def _записать(барьер: Барьер, *, корень: Path | None = None) -> None:
    путь = _путь(барьер.site, корень)
    путь.parent.mkdir(parents=True, exist_ok=True)
    временный = путь.with_suffix(".json.tmp")
    временный.write_text(json.dumps(барьер.as_dict(), ensure_ascii=False, indent=2) + "\n",
                         encoding="utf-8")
    os.chmod(временный, 0o644)
    os.replace(временный, путь)


def проверить(site: str, *, generation: int, revision: str, artifact_sha256: str,
              этап: str, корень: Path | None = None) -> dict:
    """Пропустить заявку дальше или объявить её вытесненной.

    Вызывается в четырёх местах: постановка, захват, перед отрисовкой и перед
    переключением. Возвращает решение, а не бросает исключение: вытеснение —
    нормальный исход, а не поломка, и путать их значит писать в журнал «отказ»
    там, где произошёл порядок.
    """
    барьер = прочитать(site, корень=корень)
    if барьер is None:
        return {"stage": этап, "allowed": False, "verdict": ВЫТЕСНЕНА,
                "reason": "барьер витрины не объявлен"}
    if generation < барьер.generation:
        return {"stage": этап, "allowed": False, "verdict": ВЫТЕСНЕНА,
                "reason": f"поколение {generation} вытеснено {барьер.generation}",
                "fence": барьер.as_dict()}
    if generation > барьер.generation:
        return {"stage": этап, "allowed": False, "verdict": ВЫТЕСНЕНА,
                "reason": (f"поколение {generation} выше объявленного "
                           f"{барьер.generation}: заявка не из этой очереди"),
                "fence": барьер.as_dict()}
    if revision != барьер.desired_revision:
        return {"stage": этап, "allowed": False, "verdict": ВЫТЕСНЕНА,
                "reason": (f"ревизия {revision[:12]} не совпала с желаемой "
                           f"{барьер.desired_revision[:12]}"),
                "fence": барьер.as_dict()}
    if artifact_sha256 != барьер.desired_artifact_sha256:
        return {"stage": этап, "allowed": False, "verdict": ВЫТЕСНЕНА,
                "reason": "отпечаток артефакта не совпал с желаемым",
                "fence": барьер.as_dict()}
    return {"stage": этап, "allowed": True, "verdict": "ok",
            "fence": барьер.as_dict()}


__all__ = ["Барьер", "FenceError", "ВЫТЕСНЕНА", "объявить", "прочитать", "проверить"]
