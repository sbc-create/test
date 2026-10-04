#!/usr/bin/env python3
"""Доставка проверок, которые задаёт ИСПОЛНИТЕЛЬ, в репозитории сайтов.

Зачем инструмент, а не правка в каждом репозитории
--------------------------------------------------
`factory/cell/site_checks/` — источник проверок ячейки. Копии лежат в каждом
репозитории сайта, и до сих пор их переносили руками при портировании. Измерено
2026-10-04 по всей сети: канонический `activate_scenarios.py` (6481dedb) не
совпал НИ С ОДНИМ из 11 репозиториев, а заметил расхождение только
`1lordserials1-online`, у которого есть сверка с каноном (`checks/
deploy_request.py`: «договор задаёт исполнитель, а не сайт») — на ней и упал CI.

Почему нельзя просто скопировать канон всем
-------------------------------------------
Расхождение двустороннее. Копия `zonafilm-space` (1b09e557) БОГАЧЕ канона: в ней
отложенный HTTP-сервер и заглушка systemd с памятью состояния — то, чем ловится
активация, не успевшая за 40 секунд (боевой случай 23 сентября, прежняя служба
поднималась 252 секунды). Копирование канона поверх удалило бы эту проверку.

Критерий замены поэтому измеряемый, а не на глаз: копию можно заменить, только
если её отпечаток совпадает с КАКОЙ-ТО ПРОШЛОЙ РЕВИЗИЕЙ канона в истории
фабрики. Тогда она — отставшая версия того же файла, и заменой ничего не
теряется. Если отпечатка в истории нет, копия несёт работу сайта: инструмент её
не трогает и называет расхождение в отчёте.

    python3 automation/local/sync-site-checks.py                  # отчёт по сети
    python3 automation/local/sync-site-checks.py --sync --dry-run # что изменится
    python3 automation/local/sync-site-checks.py --sync --repo lordserial33-biz

Отдельная строка отчёта — риск D138. Прежняя ревизия брала издателя как
`cfg.get('publisher_id_expected') or '10238'`. После D138 номера у доменов
разные, и витрина, не объявившая свой номер, проходит активацию с ЧУЖИМ
издателем семейства lords — проверка подтверждает настройку, которой нет.
Измерено: так живут пять репозиториев yummyani. Канон вместо умолчания
отказывает, но доставить его туда инструмент всё равно не может (их копии не из
истории канона), а выдумать номер издателя не вправе никто: это факт владельца.

После `--sync` обязателен прогон `checks/run.sh` в затронутом репозитории:
инструмент доставляет договор, а не подтверждает его выполнение.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import subprocess
import sys

КОРЕНЬ = pathlib.Path(__file__).resolve().parents[2]
КАНОН = КОРЕНЬ / "factory" / "cell" / "site_checks"
РЕПОЗИТОРИИ = КОРЕНЬ / "var" / "site-repos"

#: Файлы, чей договор прямо объявляет источником исполнителя. Расширять список
#: можно только вместе с таким договором в самой проверке: иначе синхронизация
#: затрёт особенность сайта, про которую никто не спрашивал.
АВТОРИТЕТНЫЕ = ("activate_scenarios.py",)

#: Поля `config/site.json`, без которых канонический файл откажет (D138).
ТРЕБУЕТ = {"activate_scenarios.py": ("publisher_id_expected",)}


def отпечаток(данные: bytes) -> str:
    return hashlib.sha256(данные).hexdigest()[:12]


def история_канона(имя: str) -> dict[str, str]:
    """Отпечатки всех прошлых ревизий канонического файла -> коммит."""
    путь = f"factory/cell/site_checks/{имя}"
    ревизии = subprocess.run(["git", "rev-list", "HEAD", "--", путь],
                             cwd=str(КОРЕНЬ), capture_output=True,
                             text=True).stdout.split()
    найдено: dict[str, str] = {}
    for р in ревизии:
        данные = subprocess.run(["git", "show", f"{р}:{путь}"], cwd=str(КОРЕНЬ),
                                capture_output=True).stdout
        if данные:
            найдено.setdefault(отпечаток(данные), р[:12])
    return найдено


def разобрать(репо: pathlib.Path, истории: dict[str, dict[str, str]]) -> dict:
    """Состояние одного репозитория по авторитетным файлам."""
    к = репо / "config" / "site.json"
    cfg = json.loads(к.read_text(encoding="utf-8")) if к.is_file() else {}
    итог: dict = {"repo": репо.name, "site_id": cfg.get("site_id"), "files": {}}
    for имя in АВТОРИТЕТНЫЕ:
        канон = отпечаток((КАНОН / имя).read_bytes())
        цель = репо / "checks" / имя
        нет_полей = [п for п in ТРЕБУЕТ.get(имя, ()) if not cfg.get(п)]
        их = отпечаток(цель.read_bytes()) if цель.is_file() else None
        предок = истории[имя].get(их or "")
        запись = {
            "present": цель.is_file(), "canon": канон, "theirs": их,
            "ancestor_commit": предок, "missing_fields": нет_полей,
            "sync": False,
        }
        несёт = цель.is_file()
        if not несёт:
            запись["verdict"] = "копии нет — договор этого файла репозиторий не несёт"
        elif их == канон:
            запись["verdict"] = "совпадает с каноном"
        elif предок:
            запись["sync"] = True
            запись["verdict"] = (f"отставшая ревизия канона ({предок}) — заменить, "
                                 "теряется только устаревший код")
        else:
            запись["verdict"] = ("РАСХОДИТСЯ и в истории канона такой версии нет: "
                                 "копия несёт работу сайта, замена её удалит")
        if нет_полей and несёт:
            запись["verdict"] += (f" | РИСК D138: config/site.json не объявляет "
                                  f"{', '.join(нет_полей)}")
        итог["files"][имя] = запись
    return итог


def главная(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--sync", action="store_true", help="доставить канон")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--repo", action="append", default=[],
                   help="только этот каталог репозитория (можно несколько)")
    p.add_argument("--json", action="store_true")
    args = p.parse_args(argv)

    истории = {имя: история_канона(имя) for имя in АВТОРИТЕТНЫЕ}
    отобрать = set(args.repo)
    состояния = []
    for репо in sorted(РЕПОЗИТОРИИ.iterdir()):
        if not (репо / "checks").is_dir():
            continue
        if отобрать and репо.name not in отобрать:
            continue
        состояния.append(разобрать(репо, истории))
    if not состояния:
        print("репозиториев не найдено", file=sys.stderr)
        return 2

    доставлено: list[str] = []
    for с in состояния:
        for имя, з in с["files"].items():
            if not args.sync or not з["sync"]:
                continue
            if з["missing_fields"]:
                continue
            if not args.dry_run:
                (РЕПОЗИТОРИИ / с["repo"] / "checks" / имя).write_bytes(
                    (КАНОН / имя).read_bytes())
            доставлено.append(f"{с['repo']}/{имя}: {з['theirs']} -> {з['canon']}")

    if args.json:
        print(json.dumps({"repos": состояния, "synced": доставлено},
                         ensure_ascii=False, indent=1))
        return 0

    print(f"{'репозиторий':22} {'их':13} {'канон':13} вердикт")
    print("-" * 120)
    for с in состояния:
        for имя, з in с["files"].items():
            print(f"{с['repo'][:22]:22} {str(з['theirs']):13} {з['canon']:13} "
                  f"{з['verdict']}")
    if args.sync:
        print()
        print("доставлено:" if доставлено else "доставлять нечего")
        for строка in доставлено:
            print(f"   {строка}")
        if args.dry_run:
            print("сухой прогон: файлы не менялись")
        elif доставлено:
            print("дальше обязателен прогон checks/run.sh в затронутых репозиториях")
    return 0


if __name__ == "__main__":
    raise SystemExit(главная())
