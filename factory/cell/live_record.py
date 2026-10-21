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

from factory.cell import owner_consent, registry

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

# --- объявленный режим индексации против действительного ----------------------
#
# Второй случай той же болезни, что MOD-107: действие произошло, а запись о нём
# не обновилась. Измерено 21.10 проходом
# `automation/local/indexing-registry-vs-live.py`: у ДЕВЯТИ витрин паспорт
# объявляет `indexing.desired_state: CLOSED`, а живые страницы отдают
# `index, follow` — an1meg0.site, an1mego.site, animedia.icu, animedia.space,
# animeg0.site, lordserials22.info, yummyani7.info, yummyani7.site,
# zonafilm12.site. У всех девяти есть якорь согласия владельца, и у всех
# `open_authorized: true`. То есть решение об открытии есть и исполнено, а
# объявленный режим остался закрытым (MOD-55).
#
# Открытых БЕЗ разрешения — ноль. Это важная половина измерения: правка
# приводит запись к действительности, а не открывает ничего.


def _без_noindex(значение: str) -> bool:
    return "noindex" not in (значение or "").lower()


def замер_индексации(домен: str,
                     забрать_с_заголовками=None) -> dict[str, Any]:
    """Живой режим индексации: мета robots и заголовок X-Robots-Tag."""
    if забрать_с_заголовками is not None:
        return забрать_с_заголовками(домен)
    адрес = f"https://{домен}/"
    try:
        with urllib.request.urlopen(
                urllib.request.Request(адрес, headers=ЗАГОЛОВКИ),
                timeout=ТАЙМАУТ) as о:
            тело = о.read().decode("utf-8", "replace")
            заголовок = о.headers.get("X-Robots-Tag") or ""
            код: object = о.status
    except urllib.error.HTTPError as ош:
        return {"код": ош.code, "meta": "", "x_robots_tag": "", "адрес": адрес}
    except Exception as ош:  # noqa: BLE001
        return {"код": type(ош).__name__, "meta": "", "x_robots_tag": "",
                "адрес": адрес}
    м = ROBOTS.search(тело)
    return {"код": код, "meta": м.group(1) if м else "",
            "x_robots_tag": заголовок, "адрес": адрес}


def проверить_индексацию(запись: dict[str, Any], изм: dict[str, Any],
                         согласие: tuple[bool, str, dict[str, Any]]) -> None:
    """Поднять `ЗаписьОтклонена`, если объявлять OPEN нельзя."""
    site_id = запись.get("site_id")
    инд = запись.get("indexing") or {}
    объявлено = str(инд.get("desired_state") or "").strip().upper()
    if объявлено == "OPEN":
        raise ЗаписьОтклонена(
            f"{site_id}: паспорт уже объявляет OPEN — обновлять нечего")
    подтверждено, причина, _ = согласие
    if not подтверждено:
        raise ЗаписьОтклонена(
            f"{site_id}: якоря согласия владельца нет или он негоден"
            f" ({причина}). Объявить OPEN без разрешения — значит выдать"
            " решение, которого не было")
    if инд.get("open_authorized") is not True:
        raise ЗаписьОтклонена(
            f"{site_id}: в паспорте `open_authorized` ="
            f" {инд.get('open_authorized')!r}, а не true: разрешение не"
            " записано там, где его читают")
    if изм["код"] != 200:
        raise ЗаписьОтклонена(
            f"{site_id}: живая витрина отвечает {изм['код']!r} — режим"
            " индексации не измерен")
    if not (_без_noindex(изм["meta"]) and _без_noindex(изм["x_robots_tag"])):
        raise ЗаписьОтклонена(
            f"{site_id}: живая витрина отдаёт noindex (meta"
            f" {изм['meta']!r}, X-Robots-Tag {изм['x_robots_tag']!r}) —"
            " значит объявленный CLOSED ВЕРЕН, и менять его нельзя")


def изменения_индексации(запись: dict[str, Any], изм: dict[str, Any],
                         согласие: tuple[bool, str, dict[str, Any]], *,
                         когда: str | None = None) -> dict[str, Any]:
    """Точечное изменение блока `indexing`. Прочие его поля сохраняются.

    ПОЛЯ ТОЛЬКО ТЕ, ЧТО РАЗРЕШЕНЫ СХЕМОЙ. У блока `indexing` в
    `schemas/site-cells.schema.json` стоит `additionalProperties: false`, и
    первая версия этой функции добавляла `confirmed_at`, `evidence`,
    `robots_seen` — схема такую запись отвергла бы. Ослаблять схему ради
    удобства записи нельзя, а место для происхождения в ней уже есть: это
    `reason` и `open_authorization_*`.

    ПРЕЖНЯЯ ПРИЧИНА ЗАМЕНЯЕТСЯ, А НЕ ОСТАЁТСЯ РЯДОМ. Она описывает закрытое
    состояние («noindex отдают и рантайм, и заголовок nginx»), и при
    `desired_state: OPEN` читалась бы как действующее описание — ровно тот
    случай «устаревшая причина правдоподобна», который записан отдельным
    дефектом (MOD-42). Новая причина называет замер: адрес, время, что отдала
    живая витрина и чем подтверждено разрешение.
    """
    метка = когда or dt.datetime.now(dt.timezone.utc).strftime(
        "%Y-%m-%dT%H:%M:%SZ")
    _, причина_согласия, данные = согласие
    инд = dict(запись.get("indexing") or {})
    видно = изм["meta"] or изм["x_robots_tag"] or "без метки"
    инд["desired_state"] = "OPEN"
    инд["reason"] = (
        f"Открыто и проверено живым замером {метка}: {изм['адрес']} отдаёт"
        f" robots {видно!r}. Запись приведена к действительному режиму"
        f" (прежде стояло CLOSED при открытых страницах — MOD-55)."
        f" Разрешение владельца: {причина_согласия}.")
    ид = str(данные.get("id") or "")
    if ид:
        инд["open_authorization_id"] = ид
    return {"indexing": инд}


def записать_индексацию(site_id: str, *, путь: Path | None = None,
                        замер=None, когда: str | None = None,
                        согласие_корень: Path | None = None,
                        применять: bool = True) -> dict[str, Any]:
    """Сверить объявленный режим индексации с действительным и СОСТАВИТЬ правку.

    ПРАВКА НЕ ПРИМЕНЯЕТСЯ, И ЭТО НЕ НЕДОДЕЛКА. `registry.update` намеренно НЕ
    пускает блок `indexing` в точечное обновление: его перечень разрешённых
    полей блока не содержит, и попытка даёт
    `RegistryError: эти поля паспорта не обновляются точечно: ['indexing']`.
    Проверено прямым вызовом. Единственное место, которое этот блок пишет, —
    `factory/cell/newsite.py` при создании ячейки; пути обновления после
    создания в фабрике НЕТ.

    То есть девять паспортов устарели (MOD-55), и штатного способа это
    исправить не существует. Ослаблять защиту `update` ради удобства записи я
    не стал: блок объявляет режим индексации, и открывать ему точечный путь —
    решение архитектурной линии, а не моё.

    Поэтому функция делает всё, что можно сделать честно: замеряет живой режим,
    проверяет якорь согласия владельца, составляет правку в полях, разрешённых
    схемой, и возвращает её КАК ПРЕДЛОЖЕНИЕ. `применять=True` даёт отказ с
    названной причиной, а не тихое ничего.
    """
    cell = registry.resolve(site_id, path=путь)
    запись = cell.to_dict()
    изм = замер_индексации(запись["domain"], забрать_с_заголовками=замер)
    согласие = owner_consent.проверить(запись["site_id"], запись["domain"],
                                       корень=согласие_корень)
    проверить_индексацию(запись, изм, согласие)
    изменения_ = изменения_индексации(запись, изм, согласие, когда=когда)
    итог = {
        "site_id": запись["site_id"], "домен": запись["domain"],
        "было": {"desired_state":
                 (запись.get("indexing") or {}).get("desired_state")},
        "замер": изм, "согласие": согласие[1],
        "предложение": изменения_, "применено": False,
        "почему_не_применено":
            "registry.update не пускает блок `indexing` в точечное обновление"
            " (проверено вызовом: RegistryError «эти поля паспорта не"
            " обновляются точечно»). Единственный писатель блока —"
            " newsite.py при создании ячейки. Открыть точечный путь для"
            " `indexing` — решение архитектурной линии.",
    }
    if применять:
        raise ЗаписьОтклонена(
            f"{запись['site_id']}: правка составлена, но применить её нечем —"
            f" {итог['почему_не_применено']}")
    return итог
