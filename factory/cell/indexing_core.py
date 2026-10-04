#!/usr/bin/env python3
"""Реестр индексируемости семейства Yummy — чтение и запись ОДНОЙ записи.

Что это за файл
---------------

У семейства Yummy решение о режиме индексации живёт не в нашем файле
состояния, а в собственном реестре площадки:

    {"schema": "indexing-core-registry/1.0",
     "domains": {"<домен>": {exact_domain, tenant_id, compose_service,
                             desired_state, policy_revision,
                             owner_authorization_id, reason, policy_digest}}}

Его читает `src/nova_core_indexability.py` — модуль, закреплённый в
`pins.lock.json` каждой ячейки и вызываемый точкой входа ПРИ ИМПОРТЕ
(`ИНДЕКСАЦИЯ_ОТКРЫТА = resolve_or_exit()`). Путь к реестру объявляет сам
выпуск переменной `INDEXING_CORE_REGISTRY` в `config/site.json`.

Измерено 2026-10-04 на живом хосте: все пять витрин Yummy — ячейки
(`/srv/<учётная запись>/current`), все пять объявляют ОДИН файл
`/srv/lords/.frontend/indexing-core-registry.json`, и `yummyani.site` с
`yummyani.org` отдают страницы без `noindex` именно потому, что их записи в нём
говорят `desired_state: OPEN`. То есть механизм существует, работает и доказан
двумя открытыми production-доменами.

Почему запись идёт ЗДЕСЬ, а не вторым оркестратором
---------------------------------------------------

Соблазн был завести для Yummy отдельный путь: свой файл состояния рядом с
нашими, свой читатель, своё решение. Это было бы ВТОРОЕ решение об одном и том
же: домен открыт, если так сказал реестр ядра, и наш файл ничего бы не изменил
— кроме того, что два источника разошлись бы молча, а fail-closed сторож
площадки при первом же прогоне закрыл бы два работающих домена.

Поэтому штатная операция индексации не подменяет механизм, а ПОЛЬЗУЕТСЯ им:
меняет ровно одну запись того самого файла, который читает витрина, оставляя
остальные записи байт в байт, и перезапускает юнит — потому что режим
резолвится при импорте, и без перезапуска запись в файле осталась бы решением,
о котором работающий процесс не знает.

Что здесь НЕ делается
---------------------

* запись не СОЗДАЁТСЯ: отсутствие домена в реестре — это отсутствие решения
  владельца о нём, и придумать запись значило бы придумать решение;
* `owner_authorization_id` не придумывается: он переписывается из якоря
  согласия владельца (`/var/lib/site-cells/owner-consent/<домен>.json`),
  который создаёт только root;
* чужие записи не трогаются и не перечитываются из «шаблона»: файл общий на
  пять доменов, два из которых открыты, и потеря чужой записи закрыла бы
  работающий сайт;
* отпечаток не копируется: он пересчитывается тем же алгоритмом, которым его
  считает сам модуль площадки.
"""
from __future__ import annotations

import json
import os
import pathlib
import tempfile
import time
from typing import Any

#: Схема, которую понимает читатель площадки. Другая версия — не повод
#: «попробовать»: формат читает чужой код, и угадывать его нельзя.
СХЕМА = "indexing-core-registry/1.0"

#: Имя модуля-читателя внутри выпуска ячейки.
ЧИТАТЕЛЬ = "src/nova_core_indexability.py"

#: Переменная выпуска, которой объявлен путь к реестру.
ПЕРЕМЕННАЯ = "INDEXING_CORE_REGISTRY"

#: Чем точка входа ПОЛЬЗУЕТСЯ реестром. Наличия модуля недостаточно: файл,
#: который никто не вызывает, режим не решает.
ВЫЗОВЫ = ("resolve_or_exit", "resolve_indexing_open")


class РеестрЯдра(RuntimeError):
    """Реестр ядра не поддаётся работе с названной причиной."""


def корни_выпуска(аккаунт: str) -> tuple[pathlib.Path, ...]:
    """Где лежит выпущенный код ячейки, в порядке доверия."""
    return (pathlib.Path(f"/srv/{аккаунт}/current"),
            pathlib.Path(f"/srv/{аккаунт}/app"))


def _конфигурация(аккаунт: str) -> tuple[dict[str, Any], pathlib.Path | None]:
    for корень in корни_выпуска(аккаунт):
        п = корень / "config" / "site.json"
        if not п.is_file():
            continue
        try:
            return json.loads(п.read_text(encoding="utf-8")), п
        except (OSError, ValueError):
            return {}, п
    return {}, None


def связанный_читатель(аккаунт: str) -> dict[str, Any]:
    """Читает ли ВЫПУЩЕННЫЙ код режим из реестра ядра — и каким файлом.

    Отвечает не «есть ли файл», а «подключён ли механизм»: модуль на месте,
    путь к реестру объявлен выпуском, точка входа модуль ВЫЗЫВАЕТ, и
    объявленный реестр читается. Любой невыполненный пункт называется.
    """
    итог: dict[str, Any] = {"account": аккаунт, "connected": False,
                            "module": "", "registry": "", "entrypoint": "",
                            "calls": False}
    if not аккаунт:
        итог["reason"] = "учётная запись не названа: выпуск искать негде"
        return итог

    модуль = None
    for корень in корни_выпуска(аккаунт):
        п = корень / ЧИТАТЕЛЬ
        if п.is_file():
            модуль = п
            break
    if модуль is None:
        итог["reason"] = (f"в выпуске нет {ЧИТАТЕЛЬ}: витрина режим из реестра "
                          "ядра не читает")
        return итог
    итог["module"] = str(модуль)

    конфиг, путь_конфига = _конфигурация(аккаунт)
    итог["config"] = str(путь_конфига or "")
    объявлено = str((конфиг.get("environment") or {}).get(ПЕРЕМЕННАЯ) or "").strip()
    if not объявлено:
        итог["reason"] = (f"выпуск не объявил {ПЕРЕМЕННАЯ} в "
                          f"{путь_конфига or 'config/site.json'}: читатель есть, "
                          "а какой реестр он читает — не сказано. Подставлять "
                          "путь по соседству нельзя: чужой реестр выглядел бы "
                          "своим")
        return итог
    итог["registry"] = объявлено

    # Точка входа обязана ВЫЗЫВАТЬ резолвер. Модуль, который никто не
    # вызывает, режим не решает, и «читатель на месте» было бы неправдой.
    точка = None
    for корень in корни_выпуска(аккаунт):
        каталог = корень / "src"
        if not каталог.is_dir():
            continue
        найдено = sorted(каталог.glob("*frontend*.py"))
        if найдено:
            точка = найдено[0]
            break
    if точка is None:
        итог["reason"] = "в выпуске нет точки входа: вызвать резолвер нечему"
        return итог
    итог["entrypoint"] = str(точка)
    try:
        текст = точка.read_text(encoding="utf-8", errors="replace")
    except OSError as ош:
        итог["reason"] = f"{точка} не читается: {type(ош).__name__}"
        return итог
    if "nova_core_indexability" not in текст:
        итог["reason"] = (f"{точка.name} не импортирует nova_core_indexability: "
                          "модуль лежит рядом, но режим решает не он")
        return итог
    итог["calls"] = any(в in текст for в in ВЫЗОВЫ)
    if not итог["calls"]:
        итог["reason"] = (f"{точка.name} импортирует читателя, но не вызывает "
                          f"ни {' / '.join(ВЫЗОВЫ)}: решение не принимается")
        return итог

    файл = pathlib.Path(объявлено)
    if not файл.is_file():
        итог["reason"] = (f"объявленного реестра {файл} нет: режим индексации не "
                          "должен меняться от отсутствия файла, и подставлять "
                          "другой нельзя")
        return итог
    try:
        данные = json.loads(файл.read_text(encoding="utf-8"))
    except (OSError, ValueError) as ош:
        итог["reason"] = f"{файл} не читается: {type(ош).__name__}"
        return итог
    итог["schema"] = данные.get("schema")
    if данные.get("schema") != СХЕМА:
        итог["reason"] = (f"{файл}: схема {данные.get('schema')!r}, а читатель "
                          f"площадки понимает {СХЕМА!r}")
        return итог
    итог["connected"] = True
    итог["domains_known"] = sorted((данные.get("domains") or {}))
    return итог


def путь_реестра(аккаунт: str) -> tuple[pathlib.Path | None, str]:
    """(файл реестра, чем он объявлен). Без объявления выпуска — None.

    Умолчания нет сознательно: реестр решает режим пяти доменов, и
    подставленный «похожий» путь открыл бы или закрыл не тот сайт.
    """
    конфиг, путь_конфига = _конфигурация(аккаунт)
    объявлено = str((конфиг.get("environment") or {}).get(ПЕРЕМЕННАЯ) or "").strip()
    if объявлено:
        return pathlib.Path(объявлено), f"{путь_конфига}: environment.{ПЕРЕМЕННАЯ}"
    return None, (f"выпуск учётной записи {аккаунт or '(не названа)'} не объявил "
                  f"{ПЕРЕМЕННАЯ}")


def _модуль_площадки(аккаунт: str):
    """Загрузить читатель площадки ИЗ ВЫПУСКА — его же алгоритмом проверять.

    Своя копия алгоритма отпечатка разошлась бы с чужой при первом же
    изменении формата, и расхождение увидел бы только сторож площадки.
    """
    import importlib.util
    for корень in корни_выпуска(аккаунт):
        п = корень / ЧИТАТЕЛЬ
        if not п.is_file():
            continue
        спец = importlib.util.spec_from_file_location(
            f"nova_core_indexability_{аккаунт.replace('-', '_')}", п)
        if спец is None or спец.loader is None:
            continue
        модуль = importlib.util.module_from_spec(спец)
        спец.loader.exec_module(модуль)
        return модуль
    raise РеестрЯдра(
        f"в выпуске {аккаунт} нет {ЧИТАТЕЛЬ}: проверить запись его же "
        "алгоритмом нечем, а своя копия алгоритма разошлась бы с площадкой")


def прочитать(файл: pathlib.Path) -> dict[str, Any]:
    try:
        данные = json.loads(pathlib.Path(файл).read_text(encoding="utf-8"))
    except OSError as ош:
        raise РеестрЯдра(f"{файл} не читается: {type(ош).__name__}: {ош}") from None
    except ValueError as ош:
        raise РеестрЯдра(f"{файл} не разбирается как JSON: {ош}") from None
    if данные.get("schema") != СХЕМА:
        raise РеестрЯдра(
            f"{файл}: схема {данные.get('schema')!r} вместо {СХЕМА!r}")
    if not isinstance(данные.get("domains"), dict) or not данные["domains"]:
        raise РеестрЯдра(f"{файл}: карты domains нет или она пуста")
    return данные


def запись(файл: pathlib.Path, домен: str) -> dict[str, Any]:
    """Запись одного домена. Отсутствие — отказ, а не пустая запись."""
    данные = прочитать(файл)
    ключ = (домен or "").strip().lower()
    for имя, зп in (данные.get("domains") or {}).items():
        if not isinstance(зп, dict):
            continue
        если = str(зп.get("exact_domain") or имя).strip().lower()
        if если == ключ:
            return dict(зп)
    raise РеестрЯдра(
        f"{файл}: домена {ключ} в реестре нет. Это отсутствие решения владельца "
        "о нём, а не повод создать запись: придуманная запись была бы "
        "придуманным решением")


def переписать(файл: pathlib.Path, домен: str, *, режим: str,
               authorization_id: str, причина: str, аккаунт: str,
               dry_run: bool = True) -> dict[str, Any]:
    """Сменить режим ОДНОГО домена в реестре ядра.

    Остальные записи остаются байт в байт. Результат проверяется читателем
    ПЛОЩАДКИ до подмены файла: расходящийся с её правилами реестр закрыл бы
    пять доменов разом, и узнали бы об этом по упавшей витрине.
    """
    файл = pathlib.Path(файл)
    ключ = (домен or "").strip().lower()
    желаемое = (режим or "").strip().upper()
    if желаемое not in ("OPEN", "CLOSED"):
        raise РеестрЯдра(f"режим {режим!r} не OPEN и не CLOSED")
    if not str(authorization_id or "").strip():
        raise РеестрЯдра(
            f"{ключ}: идентификатор разрешения владельца пуст. Он переписывается "
            "из якоря согласия и не придумывается: пустое поле — не разрешение")

    данные = прочитать(файл)
    имя_ключа = ""
    for имя, зп in данные["domains"].items():
        if isinstance(зп, dict) and str(зп.get("exact_domain") or имя).strip().lower() == ключ:
            имя_ключа = имя
            break
    if not имя_ключа:
        raise РеестрЯдра(
            f"{файл}: домена {ключ} в реестре нет — запись не создаётся")

    было = dict(данные["domains"][имя_ключа])
    итог: dict[str, Any] = {
        "registry": str(файл), "domain": ключ, "key": имя_ключа,
        "before": {"desired_state": было.get("desired_state"),
                   "policy_revision": было.get("policy_revision"),
                   "owner_authorization_id": было.get("owner_authorization_id")},
        "untouched": sorted(к for к in данные["domains"] if к != имя_ключа),
    }
    if str(было.get("desired_state") or "").strip().upper() == желаемое \
            and str(было.get("owner_authorization_id") or "") == str(authorization_id):
        итог["changed"] = False
        итог["note"] = "запись уже в этом режиме с этим разрешением"
        итог["after"] = итог["before"]
        return итог

    стало = dict(было)
    стало["exact_domain"] = ключ
    стало["desired_state"] = желаемое
    стало["policy_revision"] = int(было.get("policy_revision") or 0) + 1
    стало["owner_authorization_id"] = str(authorization_id)
    стало["reason"] = причина
    стало.pop("policy_digest", None)

    модуль = _модуль_площадки(аккаунт)
    стало["policy_digest"] = модуль._digest_entry({
        **стало, "tenant_id": стало.get("tenant_id") or "",
    })
    новое = json.loads(json.dumps(данные))      # глубокая копия без правки живой
    новое["domains"][имя_ключа] = стало

    # ПРОВЕРКА ЧУЖИМ КОДОМ ДО ПОДМЕНЫ. Читатель площадки отвергает дубли
    # доменов и тенантов, неизвестные состояния и пустые поля; его отказ
    # здесь — это отказ операции, а не упавшая через минуту витрина.
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", suffix=".json",
                                     delete=False) as вр:
        json.dump(новое, вр, ensure_ascii=False, indent=2, sort_keys=False)
        вр.write("\n")
        проба = pathlib.Path(вр.name)
    try:
        разобрано = модуль.load_domains(проба)
        if ключ not in разобрано:
            raise РеестрЯдра(
                f"после правки читатель площадки домена {ключ} не видит")
        if режим_читателя(разобрано[ключ]) != желаемое:
            raise РеестрЯдра(
                f"после правки читатель площадки считает режим "
                f"{режим_читателя(разобрано[ключ])!r} вместо {желаемое!r}")
        for чужой in итог["untouched"]:
            чк = str((данные["domains"][чужой] or {}).get("exact_domain")
                     or чужой).strip().lower()
            if чк not in разобрано:
                raise РеестрЯдра(
                    f"после правки читатель площадки потерял чужой домен {чк}: "
                    "запись отклонена целиком")
            if разобрано[чк]["indexing_open"] != (
                    str((данные["domains"][чужой] or {}).get("desired_state")
                        or "").strip().upper() == "OPEN"):
                raise РеестрЯдра(
                    f"после правки режим чужого домена {чк} изменился: "
                    "запись отклонена целиком")
        итог["verified_by"] = str(модуль.__file__)
        итог["after"] = {"desired_state": стало["desired_state"],
                         "policy_revision": стало["policy_revision"],
                         "owner_authorization_id": стало["owner_authorization_id"],
                         "policy_digest": стало["policy_digest"]}
        if dry_run:
            итог["changed"] = False
            итог["dry_run"] = True
            return итог
        # Копия ДО подмены: откат операции не должен зависеть от того, что
        # прежнее значение кто-то помнит. Имя несёт время — копия предыдущей
        # правки не затирается следующей.
        копия = файл.with_name(
            f"{файл.name}.bak.{time.strftime('%Y%m%dT%H%M%SZ', time.gmtime())}")
        копия.write_text(json.dumps(данные, ensure_ascii=False, indent=2) + "\n",
                         encoding="utf-8")
        итог["backup"] = str(копия)
        # Подмена одним переименованием в том же каталоге: витрина, читающая
        # файл в этот момент, видит либо прежний, либо новый, но не половину.
        рядом = файл.with_name(файл.name + ".new")
        рядом.write_text(json.dumps(новое, ensure_ascii=False, indent=2) + "\n",
                         encoding="utf-8")
        os.replace(рядом, файл)
        итог["changed"] = True
        return итог
    finally:
        проба.unlink(missing_ok=True)


def режим_читателя(запись_читателя: dict[str, Any]) -> str:
    """Режим так, как его понял читатель площадки."""
    return "OPEN" if запись_читателя.get("indexing_open") else "CLOSED"
