"""Запись о выпуске витрины, выложенной НЕ на этом узле, — по живому замеру.

Зачем это нужно, и дефект назван числами (MOD-107). Поле `deployed` в паспорте
ячейки пишет `factory cell release`, когда артефакт собирается НА ЭТОМ узле.
Партия K2 из восьми витрин выложена на цель `k2-zomro-01`, выпуск прошёл мимо
этого пути — и измерено 20.10, подтверждено 21.10: у всех восьми `status`
остался `planned`, `deployed` и `release` пусты, `last_update` — 2026-10-13, а
витрины при этом отдают 200 и КАЖДАЯ свой build-id (`9d516ae97730-lords-10`,
`a1e296bbce04-lords-11`, …). Запись о восьми живых выпусках просто отсутствует.

Чем эта запись отличается от записи локальной сборки, и почему подменять одну
другой нельзя:

* у локальной сборки есть АРТЕФАКТ, и `release_digest` считается по нему.
  Здесь артефакта нет, и `release_digest` остаётся `null`. Поставить туда
  что-нибудь означало бы придумать отпечаток, которого никто не считал;
* источник сведений называется прямо: `source: "live-probe"`, адрес замера и
  его время. По записи должно быть видно, что выпуск УВИДЕН, а не собран;
* замер обязателен. Нет живого build-id — отказ, а не пустая запись.

Три отказа, названные заранее, потому что каждый из них защищает от своей
неправды:

1. **нет живого build-id** — записывать нечего;
2. **индексация живой витрины противоречит паспорту** (паспорт говорит
   `CLOSED`, витрина отдаёт `index`) — тогда расхождение важнее записи о
   выпуске, и запись не делается, пока противоречие не разобрано;
3. **цель витрины — этот узел** — значит выпуск обязан идти штатным путём
   (`factory cell release`), и обходить его замером нельзя.
"""
from __future__ import annotations

import datetime as dt
import re
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Callable

from factory.cell import registry

ЗАГОЛОВКИ = {"User-Agent": "site-factory-cell-record/1 (release bookkeeping)"}
ТАЙМАУТ = 20

#: `data-build-id` в разметке главной. Тот же признак, которым пользуется
#: `automation/local/availability-sweep.py`: витрина, отдающая СВОЙ build-id,
#: выпущена.
BUILD_ID = re.compile(r'data-build-id="([^"]+)"')
ROBOTS = re.compile(
    r'<meta[^>]+name=["\']robots["\'][^>]+content=["\']([^"\']*)["\']', re.I)

#: Этот узел. Витрину, выложенную здесь, записывает штатный путь сборки.
ЭТОТ_УЗЕЛ = "claude-control-01"


class ЗаписьОтклонена(Exception):
    """Запись о выпуске не сделана, и причина названа."""


def _забрать(адрес: str) -> tuple[object, str]:
    try:
        with urllib.request.urlopen(
                urllib.request.Request(адрес, headers=ЗАГОЛОВКИ),
                timeout=ТАЙМАУТ) as о:
            return о.status, о.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as ош:
        return ош.code, ""
    except Exception as ош:  # noqa: BLE001 — причина уходит в отказ
        return type(ош).__name__, ""


def замер(домен: str, *, забрать: Callable[[str], tuple[object, str]] | None = None
          ) -> dict[str, Any]:
    """Живой замер витрины: код, build-id, метка robots."""
    код, тело = (забрать or _забрать)(f"https://{домен}/")
    сборка = BUILD_ID.search(тело or "")
    роботс = ROBOTS.search(тело or "")
    return {
        "домен": домен,
        "код": код,
        "build_id": сборка.group(1) if сборка else "",
        "robots": роботс.group(1) if роботс else "",
        "адрес": f"https://{домен}/",
    }


def _закрыта_по_паспорту(запись: dict[str, Any]) -> bool:
    состояние = str(((запись.get("indexing") or {}).get("desired_state")
                     or "")).upper()
    return состояние == "CLOSED"


def проверить(запись: dict[str, Any], изм: dict[str, Any]) -> None:
    """Поднять `ЗаписьОтклонена`, если записывать нельзя."""
    цель = str(((запись.get("deploy_target") or {}).get("ref") or ""))
    if цель == ЭТОТ_УЗЕЛ:
        raise ЗаписьОтклонена(
            f"{запись.get('site_id')}: цель витрины — этот узел ({цель}),"
            " выпуск обязан идти штатным путём `factory cell release`")
    if изм["код"] != 200 or not изм["build_id"]:
        raise ЗаписьОтклонена(
            f"{запись.get('site_id')}: живого build-id нет"
            f" (код {изм['код']!r}, build-id {изм['build_id']!r}) —"
            " записывать нечего")
    if _закрыта_по_паспорту(запись) and "noindex" not in (изм["robots"] or ""):
        raise ЗаписьОтклонена(
            f"{запись.get('site_id')}: паспорт объявляет индексацию CLOSED, а"
            f" витрина отдаёт robots {изм['robots']!r}. Это расхождение важнее"
            " записи о выпуске: сначала оно, потом запись")


def изменения(изм: dict[str, Any], *, когда: str | None = None) -> dict[str, Any]:
    """Точечные изменения паспорта. `release_digest` остаётся `null`."""
    метка = когда or dt.datetime.now(dt.timezone.utc).strftime(
        "%Y-%m-%dT%H:%M:%SZ")
    return {
        "status": "live",
        "deployed": {
            "release_digest": None,
            "source_commit": None,
            "artifact": None,
            "built_at": None,
            "build_id": изм["build_id"],
            "source": "live-probe",
            "probed_at": метка,
            "evidence": изм["адрес"],
            "robots_seen": изм["robots"],
        },
    }


def записать(site_id: str, *, путь: Path | None = None,
             забрать: Callable[[str], tuple[object, str]] | None = None,
             когда: str | None = None, применять: bool = True) -> dict[str, Any]:
    """Замерить витрину и записать выпуск. `применять=False` — только замер."""
    cell = registry.resolve(site_id, path=путь)
    запись = cell.to_dict()
    изм = замер(запись["domain"], забрать=забрать)
    проверить(запись, изм)
    изменения_ = изменения(изм, когда=когда)
    итог = {"site_id": запись["site_id"], "домен": запись["domain"],
            "было": {"status": запись.get("status"),
                     "deployed": запись.get("deployed")},
            "замер": изм, "изменения": изменения_, "применено": False}
    if применять:
        registry.update(запись["site_id"], изменения_, path=путь)
        итог["применено"] = True
    return итог
