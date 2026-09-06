#!/usr/bin/env python3
"""Сборщик наблюдений: измеряет то, что можно измерить, и называет остальное.

Центр управления читает наблюдения из файла и ничего не измеряет сам — экран
обязан открываться, даже когда чужой счётчик молчит. Измеряет этот сценарий, и
у него ровно одно правило: **не измеренное не превращается в ноль**.

Что берётся отсюда, с машины:

* здоровье — ответ витрины на её собственном порту;
* свежесть — возраст снимка каталога из манифеста релиза;
* ошибки 4xx/5xx — из журнала обращений, если он читается;
* последнее успешное обновление — из журнала переключений релизов.

Чего здесь нет и почему: посещаемость, позиции в поиске, проиндексированные
страницы и Core Web Vitals приходят из внешних источников. Учётных данных к ним
не передано, и вместо чисел записывается `NOT_CONNECTED` с причиной. Выдуманное
число здесь было бы хуже пустоты: по нему приняли бы решение.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from factory.site_engine import fleet_registry as реестр  # noqa: E402

СЕЙЧАС = "%Y-%m-%dT%H:%M:%SZ"


def _отметка() -> str:
    return time.strftime(СЕЙЧАС, time.gmtime())


def _наблюдение(value, state: str, source: str, reason: str = "") -> dict:
    return {"value": value, "state": state, "source": source,
            "observedAt": _отметка(), "reason": reason}


def _здоровье(порт: int | None) -> dict:
    if not порт:
        return _наблюдение(None, "NOT_CONNECTED", "runtime:health",
                           "порт витрины не объявлен в настройке")
    адрес = f"http://127.0.0.1:{порт}/healthz"
    try:
        из = subprocess.run(["curl", "-s", "-m", "5", "-o", "/dev/null",
                             "-w", "%{http_code}", адрес],
                            capture_output=True, text=True, timeout=15)
    except (OSError, subprocess.SubprocessError) as ошибка:
        return _наблюдение(None, "ERROR", адрес, f"проба не выполнена: {ошибка}")
    код = (из.stdout or "").strip()
    if код == "200":
        return _наблюдение("ok", "CONNECTED", адрес)
    return _наблюдение(код or None, "ERROR", адрес, f"ответ {код or 'нет'}")


def _из_манифеста(рантайм: Path) -> tuple[dict, dict, dict]:
    манифест = рантайм / "current" / "release-manifest.json"
    try:
        данные = json.loads(манифест.read_text(encoding="utf-8"))
    except (OSError, ValueError) as ошибка:
        нет = _наблюдение(None, "ERROR", "release-manifest", f"не читается: {ошибка}")
        return нет, нет, нет
    создан = str(данные.get("created_at") or "")
    возраст = None
    if создан:
        try:
            разобрано = time.strptime(создан.replace("Z", ""), "%Y-%m-%dT%H:%M:%S")
            возраст = int(time.time() - time.mktime(разобрано) + time.timezone)
        except ValueError:
            возраст = None
    свежесть = (_наблюдение(возраст, "CONNECTED", "release-manifest")
                if возраст is not None
                else _наблюдение(None, "NO_DATA", "release-manifest",
                                 "в манифесте нет времени создания"))
    последнее = (_наблюдение(создан, "CONNECTED", "release-manifest") if создан
                 else _наблюдение(None, "NO_DATA", "release-manifest", "время не записано"))
    записей = данные.get("content_count")
    счёт = (_наблюдение(записей, "CONNECTED", "release-manifest")
            if isinstance(записей, int)
            else _наблюдение(None, "NO_DATA", "release-manifest", "счёт записей не записан"))
    return свежесть, последнее, счёт


КОД = re.compile(r'"\s+(\d{3})\s')


def _ошибки(журнал: Path, *, строк: int = 20000) -> tuple[dict, dict]:
    if not журнал.is_file():
        return (_наблюдение(None, "NOT_CONNECTED", str(журнал), "журнала обращений нет"),
                _наблюдение(None, "NOT_CONNECTED", str(журнал), "журнала обращений нет"))
    try:
        из = subprocess.run(["tail", "-n", str(строк), str(журнал)],
                            capture_output=True, text=True, timeout=30)
    except (OSError, subprocess.SubprocessError) as ошибка:
        нет = _наблюдение(None, "ERROR", str(журнал), f"не прочитан: {ошибка}")
        return нет, нет
    четыре = пять = 0
    for строка in (из.stdout or "").splitlines():
        совпадение = КОД.search(строка)
        if not совпадение:
            continue
        код = совпадение.group(1)
        if код.startswith("4"):
            четыре += 1
        elif код.startswith("5"):
            пять += 1
    источник = f"{журнал.name}:последние {строк}"
    return (_наблюдение(четыре, "CONNECTED", источник),
            _наблюдение(пять, "CONNECTED", источник))


def _не_подключено(настройки: dict, имя: str) -> dict:
    о = ((настройки.get("collectors") or {}).get(имя) or {})
    причина = str(о.get("reason") or "источник не подключён")
    return _наблюдение(None, "NOT_CONNECTED", f"collector:{имя}", причина)


def собрать(root: Path, site_id: str, настройки: dict, *, порт: int | None,
            журнал: Path | None) -> dict:
    рантайм = Path(str((настройки.get("runtime") or {}).get("root") or "")) / site_id
    свежесть, последнее, счёт = _из_манифеста(рантайм)
    ошибки4, ошибки5 = _ошибки(журнал) if журнал else (
        _наблюдение(None, "NOT_CONNECTED", "access-log", "журнал витрины не объявлен"),
        _наблюдение(None, "NOT_CONNECTED", "access-log", "журнал витрины не объявлен"))
    из = {
        "collectedAt": _отметка(),
        "health": _здоровье(порт),
        "freshnessSeconds": свежесть,
        "lastSuccessfulRefresh": последнее,
        "contentCountObserved": счёт,
        "errors4xx": ошибки4,
        "errors5xx": ошибки5,
    }
    # Внешние источники: контракт есть, доступа нет. Причина записывается рядом,
    # чтобы на экране было видно, чего именно не хватает.
    for имя in ("visitors", "visits", "pageviews", "playerStarts", "playableShare",
                "emptySearchQueries", "seoVisibility", "iks", "coreWebVitals"):
        из[имя] = _не_подключено(настройки, "analytics")
    for имя in ("indexedPages", "sitemapState", "robotsState", "canonicalState"):
        из[имя] = _не_подключено(настройки, "search_console")
    из["analyticsConnector"] = _не_подключено(настройки, "analytics")
    return из


def main(argv=None) -> int:
    р = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    р.add_argument("--root", default="/srv/site-factory/repo")
    р.add_argument("--site", action="append", default=[],
                   help="витрина; можно повторять. По умолчанию — все из профилей")
    р.add_argument("--port", action="append", default=[],
                   help="site_id=порт для пробы здоровья")
    р.add_argument("--access-log-dir", default="/var/log/nginx")
    args = р.parse_args(argv)

    корень = Path(args.root)
    настройки = реестр.настройка(корень)
    порты = {}
    for пара in args.port:
        если_сайт, _, если_порт = пара.partition("=")
        if если_порт.isdigit():
            порты[если_сайт] = int(если_порт)

    витрины = args.site or реестр._витрины(корень)
    цель = корень / реестр.НАБЛЮДЕНИЯ
    цель.mkdir(parents=True, exist_ok=True)
    for сайт in витрины:
        журнал = Path(args.access_log_dir) / f"{сайт}.access.log"
        данные = собрать(корень, сайт, настройки, порт=порты.get(сайт),
                         журнал=журнал if журнал.is_file() else None)
        файл = цель / f"{сайт}.json"
        временный = файл.with_suffix(".json.tmp")
        временный.write_text(json.dumps(данные, ensure_ascii=False, indent=2),
                             encoding="utf-8")
        os.replace(временный, файл)
        print(f"{сайт}: здоровье {данные['health']['state']}, "
              f"свежесть {данные['freshnessSeconds']['state']}, "
              f"4xx {данные['errors4xx']['value']}, 5xx {данные['errors5xx']['value']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
